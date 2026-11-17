"""Authenticated, audited maintenance of allowlisted operational records."""

import csv
import hashlib
import io
import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from uuid import NAMESPACE_URL, UUID, uuid5
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import pandas as pd
from pydantic import ConfigDict, Field, HttpUrl, TypeAdapter, ValidationError, create_model
from sqlalchemy import MetaData, and_, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError

from var_analytics.auth import require_admin
from var_analytics.db import admin_engine

ENTITIES = {
    "football_match": "Matches",
    "match_official": "Official appointments",
    "decision": "Decisions",
    "decision_team": "Decision team involvement",
    "var_involvement": "VAR records",
    "card_issued": "Cards",
    "added_time": "Announced added time",
    "match_player": "Match rosters",
    "player": "Players",
    "referee": "Referees",
    "team": "Teams",
    "venue": "Venues",
    "country": "Countries",
    "league": "Leagues",
    "season": "Seasons",
}
MAX_BYTES, MAX_ROWS = 2_000_000, 500
MAX_EXPORT_ROWS = 20_000


def spreadsheet_text(value):
    """Keep untrusted text from becoming a formula when CSV is opened in a spreadsheet."""
    if isinstance(value, str) and (
        value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))
    ):
        return "'" + value
    return value


def serial(value):
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def digest(value):
    return hashlib.sha256(
        json.dumps(serial(value), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@lru_cache(maxsize=4)
def metadata_for(engine):
    metadata = MetaData(schema="var")
    metadata.reflect(bind=engine, only=[*ENTITIES, "data_source", "import_batch", "source_record"])
    return {table.name: table for table in metadata.tables.values()}


@dataclass
class Preview:
    rows: list[dict]
    errors: pd.DataFrame

    @property
    def valid(self):
        return bool(self.rows) and self.errors.empty


@dataclass
class Export:
    rows: list[dict]
    content: bytes


class AdminService:
    def __init__(self, session, engine=None):
        require_admin(session)
        self.session = session
        self.engine = engine if engine is not None else admin_engine()
        with self.engine.connect() as conn:
            self._authorize(conn)
        self.tables = metadata_for(self.engine)

    def _authorize(self, conn=None):
        require_admin(self.session)
        if conn is not None and conn.scalar(text("SELECT current_user")) != "app_admin":
            raise PermissionError("Maintenance requires the app_admin database role.")

    def table(self, name):
        self._authorize()
        if name not in ENTITIES:
            raise ValueError("This table is not available for record maintenance.")
        return self.tables[name]

    def fields(self, name):
        return [c for c in self.table(name).columns if c.name != "source_record_id"]

    def template(self, name):
        output = io.StringIO()
        csv.writer(output).writerow([c.name for c in self.fields(name)])
        return output.getvalue()

    def _selection(self, name, search=""):
        table = self.table(name)
        statement = select(table)
        if search.strip():
            # Values are bound parameters; names only come from reflected allowlisted tables.
            from sqlalchemy import String, cast, or_

            statement = statement.where(
                or_(
                    *[
                        cast(c, String).icontains(search.strip(), autoescape=True)
                        for c in table.columns
                        if c.name != "source_record_id"
                    ]
                )
            )
        return statement.order_by(*table.primary_key)

    def browse(self, name, search=""):
        statement = self._selection(name, search).limit(200)
        with self.engine.connect() as conn:
            return pd.read_sql_query(statement, conn)

    def export_csv(self, name, search=""):
        """Export operational fields only; never silently truncate to the browse limit."""
        fields = [c.name for c in self.fields(name)]
        with self.engine.connect() as conn:
            rows = [
                dict(row)
                for row in conn.execute(self._selection(name, search).limit(MAX_EXPORT_ROWS + 1)).mappings()
            ]
        if len(rows) > MAX_EXPORT_ROWS:
            raise ValueError(
                "More than 20,000 records match. Narrow the search before exporting; no partial file was produced."
            )
        self._authorize()
        exported = [{k: row[k] for k in fields} for row in rows]
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in exported:
            writer.writerow({k: "" if v is None else spreadsheet_text(v) for k, v in row.items()})
        return Export(exported, output.getvalue().encode("utf-8-sig"))

    def references(self, name):
        table = self.table(name)
        targets = {
            fk.column.table.name
            for c in table.columns
            if c.name != "source_record_id"
            for fk in c.foreign_keys
        }
        return sorted(targets)

    def get(self, name, keys):
        table = self.table(name)
        if set(keys) != {c.name for c in table.primary_key}:
            raise ValueError("Provide the complete record key.")
        with self.engine.connect() as conn:
            row = (
                conn.execute(select(table).where(and_(*[table.c[k] == v for k, v in keys.items()])))
                .mappings()
                .first()
            )
            if row is None:
                raise ValueError("Record no longer exists. Reload the records.")
            return dict(row)

    def reference_rows(self, name):
        self._authorize()
        allowed = set(ENTITIES) | {"official_role", "decision_type", "decision_outcome"}
        if name not in allowed:
            raise ValueError("Reference table is not allowed")
        table = self.tables[name]
        with self.engine.connect() as conn:
            return pd.read_sql_query(select(table).limit(200), conn).drop(
                columns="source_record_id", errors="ignore"
            )

    def _parse(self, name, raw, seed):
        self.table(name)
        fields = {}
        cleaned = {
            k: (None if v is None or (isinstance(v, str) and not v.strip()) else v) for k, v in raw.items()
        }
        for c in self.fields(name):
            typ = c.type.python_type
            nullable = c.nullable
            if c.primary_key and typ is UUID and not c.foreign_keys:
                cleaned[c.name] = cleaned.get(c.name) or uuid5(
                    NAMESPACE_URL, f"dashboard-admin/{name}/{seed}"
                )
            rules = {}
            if typ in (int, Decimal):
                if c.name in {"second", "announced_seconds"}:
                    rules.update(ge=0, le=59)
                elif c.name == "period_code":
                    rules.update(ge=1, le=4 if name == "added_time" else 5)
                elif c.name in {"slot_no", "official_slot_no"}:
                    rules.update(gt=0)
                else:
                    rules.update(ge=0)
            if typ is str:
                rules.update(min_length=1, max_length=4000)
            fields[c.name] = (
                typ | None if nullable else typ,
                Field(default=None, **rules) if nullable else Field(**rules),
            )
        model = create_model("AdminRecord", __config__=ConfigDict(extra="forbid"), **fields)
        result = model.model_validate(cleaned).model_dump()
        if name == "football_match":
            if result["home_team_id"] == result["away_team_id"]:
                raise ValueError("Home and away teams must differ.")
            if (result["home_score"] is None) != (result["away_score"] is None):
                raise ValueError("Both match scores must be provided together.")
            if result["status"] == "completed" and result["home_score"] is None:
                raise ValueError("Completed matches require both scores.")
            if result.get("kickoff_at") and result["kickoff_at"].tzinfo is None:
                raise ValueError("UTC kickoff requires an explicit timezone offset.")
            if result.get("timezone_name"):
                try:
                    ZoneInfo(result["timezone_name"])
                except ZoneInfoNotFoundError as exc:
                    raise ValueError("Unknown timezone name.") from exc
        if name == "var_involvement" and result.get("outcome_code") not in {None, "UPHELD", "OVERTURNED"}:
            raise ValueError("Use a recorded UPHELD/OVERTURNED outcome or leave it blank.")
        return result

    def preview_csv(self, name, content):
        self.table(name)
        if len(content) > MAX_BYTES:
            raise ValueError("CSV must be at most 2 MB.")
        try:
            decoded = content.decode("utf-8-sig")
            header = next(csv.reader(io.StringIO(decoded)))
            if len(header) != len(set(header)):
                raise ValueError("CSV contains duplicate column names.")
            if any(len(row) != len(header) for row in list(csv.reader(io.StringIO(decoded)))[1:] if row):
                raise ValueError("Each CSV row must have the same number of columns as the header.")
            frame = pd.read_csv(io.StringIO(decoded), dtype=str, keep_default_na=False)
        except (UnicodeDecodeError, pd.errors.ParserError, pd.errors.EmptyDataError, StopIteration) as exc:
            raise ValueError("Upload a valid UTF-8 CSV with a header row.") from exc
        if frame.empty or len(frame) > MAX_ROWS:
            raise ValueError("CSV must contain between 1 and 500 records.")
        errors, rows = [], []
        content_hash = hashlib.sha256(content).hexdigest()
        for i, row in enumerate(frame.to_dict("records"), 2):
            try:
                rows.append(self._parse(name, row, f"{content_hash}/{i}"))
            except (ValueError, TypeError) as exc:
                reason = (
                    "Invalid fields: " + ", ".join(str(e["loc"][0]) for e in exc.errors())
                    if isinstance(exc, ValidationError)
                    else str(exc)
                )
                errors.append({"CSV line": i, "Problem": reason})
        if not errors:
            primary = [c.name for c in self.table(name).primary_key]
            if pd.DataFrame(serial(rows)).duplicated(primary).any():
                errors.append({"CSV line": "Multiple", "Problem": "Duplicate primary keys in this upload."})
        return Preview(rows, pd.DataFrame(errors))

    def import_csv(self, name, content, citation, reason):
        preview = self.preview_csv(name, content)
        if not preview.valid:
            raise ValueError("Resolve the CSV preview errors before importing.")
        return self._write(
            name, "create", preview.rows, citation, reason, raw={"csv_utf8": content.decode("utf-8-sig")}
        )

    def create(self, name, values, citation, reason):
        return self._write(name, "create", [values], citation, reason)

    def update(self, name, original, values, citation, reason):
        return self._write(name, "update", [values], citation, reason, original=original)

    def delete(self, name, original, citation, reason, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError("Confirm the exact record deletion before continuing.")
        return self._write(name, "delete", [original], citation, reason, original=original)

    def _write(self, name, operation, values, citation, reason, *, original=None, raw=None, nonce=None):
        table = self.table(name)
        try:
            url = TypeAdapter(HttpUrl).validate_python(citation.strip())
        except ValidationError:
            raise ValueError("Provide a valid HTTPS source citation.") from None
        if url.scheme != "https" or len(citation) > 2000 or len(reason.strip()) < 5:
            raise ValueError(
                "Provide an HTTPS source citation and a change reason of at least five characters."
            )
        fingerprint = digest([name, operation, values, citation.strip(), reason.strip(), original, nonce])
        primary = [c.name for c in table.primary_key]
        batch, source, record = (self.tables[k] for k in ("import_batch", "data_source", "source_record"))
        with self.engine.connect() as conn:
            self._authorize(conn)
            conn.execute(text("SELECT pg_advisory_lock(77761002)"))
            conn.commit()
            try:
                with conn.begin():
                    conn.execute(
                        insert(source)
                        .values(
                            source_code="dashboard_admin",
                            name="Administrator cited records",
                            reference_url="https://github.com/L1k1th1508/VAR-ANALYSIS_DBMS",
                            source_kind="manual",
                            attribution_text="User-supplied facts and citations; original evidence is retained.",
                        )
                        .on_conflict_do_nothing()
                    )
                    sid = conn.scalar(
                        select(source.c.data_source_id).where(source.c.source_code == "dashboard_admin")
                    )
                    existing = (
                        conn.execute(
                            select(batch).where(
                                batch.c.data_source_id == sid,
                                batch.c.input_fingerprint == fingerprint,
                                batch.c.transform_version == "admin-records-v1",
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if existing:
                        if existing["status"] != "success":
                            raise ValueError(
                                "This operation previously failed. Correct the data or reason before retrying."
                            )
                        return {"status": "already_loaded", "batch_id": existing["import_batch_id"]}
                    bid = conn.scalar(
                        insert(batch)
                        .values(
                            data_source_id=sid,
                            input_fingerprint=fingerprint,
                            transform_version="admin-records-v1",
                            status="pending",
                            extracted_count=len(values),
                        )
                        .returning(batch.c.import_batch_id)
                    )
                    evidence = []
                    for i, value in enumerate(values):
                        payload = serial(
                            {
                                "operation": operation,
                                "table": name,
                                "submitted": value,
                                "before": original,
                                "citation": citation.strip(),
                                "reason": reason.strip(),
                                "admin_session_id": self.session.session_id,
                                "upload": raw if i == 0 else None,
                            }
                        )
                        evidence.append(
                            conn.scalar(
                                insert(record)
                                .values(
                                    import_batch_id=bid,
                                    entity_kind=f"admin_{name}",
                                    external_key=str(i),
                                    record_locator=f"{citation.strip()}#admin-{bid}-{i}",
                                    raw_payload=payload,
                                    payload_sha256=digest(payload),
                                    validation_status="pending",
                                )
                                .returning(record.c.source_record_id)
                            )
                        )
                try:
                    with conn.begin():
                        self._authorize(conn)
                        for i, value in enumerate(values):
                            submitted = {k: v for k, v in value.items() if k != "source_record_id"}
                            parsed = self._parse(name, submitted, f"{fingerprint}/{i}")
                            if operation != "create":
                                if any(parsed[k] != original[k] for k in primary):
                                    raise ValueError("Record keys cannot be changed.")
                                predicate = and_(*[table.c[k] == original[k] for k in primary])
                                current = (
                                    conn.execute(select(table).where(predicate).with_for_update())
                                    .mappings()
                                    .first()
                                )
                                if current is None or digest(dict(current)) != digest(original):
                                    raise ValueError(
                                        "This record changed or was deleted. Reload it before saving."
                                    )
                            if operation == "delete":
                                conn.execute(table.delete().where(predicate))
                            elif operation == "update":
                                conn.execute(
                                    table.update()
                                    .where(predicate)
                                    .values(**parsed, source_record_id=evidence[i])
                                )
                            else:
                                conn.execute(table.insert().values(**parsed, source_record_id=evidence[i]))
                        conn.execute(
                            record.update()
                            .where(record.c.import_batch_id == bid)
                            .values(validation_status="accepted")
                        )
                        conn.execute(
                            batch.update()
                            .where(batch.c.import_batch_id == bid)
                            .values(status="success", finished_at=func.now(), accepted_count=len(values))
                        )
                    return {"status": "success", "batch_id": bid, "records": len(values)}
                except Exception as exc:
                    with conn.begin():
                        conn.execute(
                            record.update()
                            .where(record.c.import_batch_id == bid)
                            .values(
                                validation_status="rejected",
                                validation_errors=[{"reason": "Operation rolled back; see batch error."}],
                            )
                        )
                        conn.execute(
                            batch.update()
                            .where(batch.c.import_batch_id == bid)
                            .values(
                                status="failed",
                                finished_at=func.now(),
                                rejected_count=len(values),
                                error_summary=f"{type(exc).__name__}: administrator operation rolled back",
                            )
                        )
                    if isinstance(exc, IntegrityError):
                        code = getattr(exc.orig, "sqlstate", "")
                        explanation = {
                            "23503": "A linked record is missing, or other records still depend on this row.",
                            "23505": "That record key already exists. Use Edit to change it.",
                            "23514": "The record violates a database integrity rule.",
                            "23502": "A required database field is missing.",
                        }.get(code, "The database rejected this change.")
                        raise ValueError(explanation + " No domain changes were saved.") from None
                    if isinstance(exc, ValidationError):
                        raise ValueError("Invalid record fields. No domain changes were saved.") from None
                    raise
            finally:
                conn.rollback()
                conn.execute(text("SELECT pg_advisory_unlock(77761002)"))
                conn.commit()
