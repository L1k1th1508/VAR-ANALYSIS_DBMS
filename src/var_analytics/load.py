"""Audited, transactional admin import with independent raw-evidence persistence."""

import hashlib
import json

from sqlalchemy import MetaData, func, select, text
from sqlalchemy.dialects.postgresql import insert

from var_analytics.extract import Snapshot
from var_analytics.transform_validate import TABLE_ORDER, TRANSFORM_VERSION, RecordValidationError, transform


def load_snapshot(engine, snapshot: Snapshot) -> dict:
    """Requires app_admin credentials. Owner refresh is a separate maintenance action."""
    with engine.connect() as conn:
        if conn.scalar(text("SELECT current_user")) != "app_admin":
            raise PermissionError("Imports require the app_admin database role")
        conn.execute(text("SELECT pg_advisory_lock(77761002)"))
        conn.commit()
        try:
            metadata = MetaData(schema="var")
            metadata.reflect(bind=conn, only=[*TABLE_ORDER, "data_source", "import_batch", "source_record"])
            conn.commit()
            tables = {t.name: t for t in metadata.tables.values()}
            source, batch, record = (tables[n] for n in ("data_source", "import_batch", "source_record"))
            with conn.begin():
                conn.execute(
                    insert(source)
                    .values(
                        source_code="statsbomb_open_data",
                        name="StatsBomb Open Data",
                        reference_url="https://github.com/hudl/open-data",
                        source_kind="provider",
                        license_reference=f"https://github.com/hudl/open-data/blob/{snapshot.revision}/LICENSE.pdf",
                        attribution_text="Data provided by StatsBomb. Local research demonstration; raw data not redistributed.",
                    )
                    .on_conflict_do_nothing(index_elements=[source.c.source_code])
                )
                source_id = conn.scalar(
                    select(source.c.data_source_id).where(source.c.source_code == "statsbomb_open_data")
                )
                existing = (
                    conn.execute(
                        select(batch).where(
                            batch.c.data_source_id == source_id,
                            batch.c.input_fingerprint == snapshot.fingerprint,
                            batch.c.transform_version == TRANSFORM_VERSION,
                        )
                    )
                    .mappings()
                    .first()
                )
                if existing:
                    if existing["status"] != "success":
                        raise ValueError(
                            "This snapshot has an incomplete/failed batch. Inspect its evidence before retrying."
                        )
                    return {"status": "already_loaded", "batch_id": existing["import_batch_id"]}
                batch_id = conn.scalar(
                    insert(batch)
                    .values(
                        data_source_id=source_id,
                        input_fingerprint=snapshot.fingerprint,
                        transform_version=TRANSFORM_VERSION,
                        status="pending",
                        extracted_count=len(snapshot.observations),
                    )
                    .returning(batch.c.import_batch_id)
                )
                raw_rows = []
                for item in snapshot.observations:
                    raw_rows.append(
                        {
                            **{
                                k: item[k]
                                for k in ("entity_kind", "external_key", "record_locator", "raw_payload")
                            },
                            "import_batch_id": batch_id,
                            "validation_status": "pending",
                            "payload_sha256": hashlib.sha256(
                                json.dumps(
                                    item["raw_payload"],
                                    sort_keys=True,
                                    ensure_ascii=False,
                                    separators=(",", ":"),
                                ).encode()
                            ).hexdigest(),
                        }
                    )
                for start in range(0, len(raw_rows), 300):
                    conn.execute(insert(record), raw_rows[start : start + 300])
                evidence = dict(
                    conn.execute(
                        select(record.c.record_locator, record.c.source_record_id).where(
                            record.c.import_batch_id == batch_id
                        )
                    ).all()
                )
            try:
                plan = transform(snapshot)
                with conn.begin():
                    for name in TABLE_ORDER:
                        table = tables[name]
                        values = [
                            {**row, "source_record_id": evidence[row["source_record_id"]]}
                            for row in plan[name]
                        ]
                        if not values:
                            continue
                        statement = insert(table)
                        update = {
                            key: statement.excluded[key]
                            for key in values[0]
                            if key not in {c.name for c in table.primary_key}
                        }
                        statement = statement.on_conflict_do_update(
                            index_elements=list(table.primary_key), set_=update
                        )
                        for start in range(0, len(values), 300):
                            conn.execute(statement, values[start : start + 300])
                    conn.execute(
                        record.update()
                        .where(record.c.import_batch_id == batch_id)
                        .values(validation_status="accepted")
                    )
                    conn.execute(
                        batch.update()
                        .where(batch.c.import_batch_id == batch_id)
                        .values(
                            status="success",
                            finished_at=func.now(),
                            accepted_count=len(snapshot.observations),
                        )
                    )
                return {
                    "status": "success",
                    "batch_id": batch_id,
                    "observations": len(snapshot.observations),
                    "rows": {k: len(v) for k, v in plan.items()},
                }
            except Exception as exc:
                # The domain transaction rolled back; retain original evidence and a safe failure summary.
                with conn.begin():
                    rejected = 0
                    if isinstance(exc, RecordValidationError):
                        rejected = conn.execute(
                            record.update()
                            .where(
                                record.c.import_batch_id == batch_id,
                                record.c.record_locator == exc.locator,
                            )
                            .values(validation_status="rejected", validation_errors=[{"reason": exc.reason}])
                        ).rowcount
                    conn.execute(
                        batch.update()
                        .where(batch.c.import_batch_id == batch_id)
                        .values(
                            status="failed",
                            finished_at=func.now(),
                            rejected_count=rejected,
                            error_summary=f"{type(exc).__name__}: import rolled back; inspect validation evidence locally.",
                        )
                    )
                raise
        finally:
            conn.rollback()
            conn.execute(text("SELECT pg_advisory_unlock(77761002)"))
            conn.commit()
