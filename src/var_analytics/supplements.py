"""Import cited match facts with exact provider reconciliation and preserved provenance."""

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import text

from var_analytics.extract import Snapshot
from var_analytics.load import load_snapshot
from var_analytics.transform_validate import RecordValidationError, identity

TABLES = ["decision", "var_involvement", "added_time"]
SOURCE_CODE = "worldcup2022_cited_evidence"


class MatchIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(gt=0)
    date: date
    home: str = Field(min_length=1)
    away: str = Field(min_length=1)
    score: tuple[int, int]


class Fact(BaseModel):
    model_config = ConfigDict(extra="forbid")
    match_id: int = Field(gt=0)
    period: int = Field(ge=1, le=4)
    source: HttpUrl
    context: str = Field(min_length=1)


class Announcement(Fact):
    minutes: int = Field(ge=0, strict=True)


class Review(Fact):
    key: str = Field(min_length=1)
    minute: int | None = Field(default=None, ge=0)
    category: Literal["PENALTY", "GOAL", "FOUL", "PENALTY_REVIEW", "GOAL_REVIEW"]
    outcome: Literal["UPHELD", "OVERTURNED"]
    linked_event_id: UUID | None = None
    summary: str = Field(min_length=1)


def cited_id(kind: str, key: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"cited-worldcup2022/{kind}/{key}")


def extract_evidence(path: Path) -> Snapshot:
    content = path.read_bytes()
    document = json.loads(content)
    if document["version"] != "cited-facts-v1":
        raise ValueError("Unsupported evidence format")
    matches = document["matches"]
    if pd.DataFrame(matches).id.duplicated().any():
        raise ValueError("Duplicate match identities")
    lookup = {match["id"]: match for match in matches}
    observations = []
    for kind, field in (("added_time", "announcements"), ("var_review", "reviews")):
        for fact in document[field]:
            key = f"{fact['match_id']}/{fact['period']}" if kind == "added_time" else fact["key"]
            observations.append(
                dict(
                    entity_kind=kind,
                    external_key=key,
                    record_locator=f"{fact['source']}#cited-{kind}-{key}",
                    raw_payload={
                        "fact": fact,
                        "match": lookup[fact["match_id"]],
                        "verified_on": document["verified_on"],
                        "method": document["method"],
                    },
                )
            )
    return Snapshot(hashlib.sha256(content).hexdigest(), document["version"], observations)


def transform_evidence(snapshot: Snapshot) -> dict[str, list[dict]]:
    rows = {name: [] for name in TABLES}
    if not snapshot.observations:
        raise ValueError("Empty evidence set")
    frame = pd.DataFrame(snapshot.observations)
    if frame.duplicated(["entity_kind", "external_key"]).any():
        raise RecordValidationError(frame.iloc[0].record_locator, "Duplicate evidence keys")
    linked = set()
    for item in snapshot.observations:
        locator, raw = item["record_locator"], item["raw_payload"]
        try:
            match = MatchIdentity.model_validate(raw["match"])
            date.fromisoformat(raw["verified_on"])
            kind = item["entity_kind"]
            if kind not in {"added_time", "var_review"}:
                raise ValueError("Unsupported evidence kind")
            fact = (Announcement if kind == "added_time" else Review).model_validate(raw["fact"])
            if match.id != fact.match_id or fact.source.scheme != "https":
                raise ValueError("Match identity mismatch or non-HTTPS citation")
            mid = identity("match", match.id)
            if kind == "added_time":
                rows["added_time"].append(
                    dict(
                        match_id=mid,
                        period_code=fact.period,
                        announced_minutes=fact.minutes,
                        announced_seconds=None,
                        source_record_id=locator,
                    )
                )
                continue
            if fact.linked_event_id:
                if fact.linked_event_id in linked:
                    raise ValueError("Repeated linked event needs explicit review-order support")
                linked.add(fact.linked_event_id)
                did = identity("decision", fact.linked_event_id)
            else:
                if fact.category not in {"GOAL_REVIEW", "PENALTY_REVIEW"}:
                    raise ValueError("Unlinked reviewed claims need a review decision category")
                did = cited_id("decision", fact.key)
                rows["decision"].append(
                    dict(
                        decision_id=did,
                        match_id=mid,
                        decision_type_code=fact.category,
                        outcome_code=None,
                        period_code=fact.period,
                        minute=fact.minute,
                        second=None,
                        description=fact.summary,
                        source_record_id=locator,
                    )
                )
            rows["var_involvement"].append(
                dict(
                    var_involvement_id=cited_id("review", fact.key),
                    decision_id=did,
                    review_kind="review",
                    outcome_code=fact.outcome,
                    period_code=fact.period,
                    # Reported incident clocks are not the start of the subsequent review.
                    minute=None,
                    second=None,
                    duration_seconds=None,
                    description=fact.summary,
                    source_record_id=locator,
                )
            )
        except (ValueError, KeyError, TypeError) as exc:
            raise RecordValidationError(locator, str(exc)) from exc
    return rows


def reconcile(conn, snapshot: Snapshot, *, season_key="43/106", source_code=SOURCE_CODE) -> None:
    """Require exact match/event identity; never guess joins from a team name or clock."""
    for item in snapshot.observations:
        raw = item["raw_payload"]
        expected = MatchIdentity.model_validate(raw["match"])
        mid = identity("match", expected.id)
        match = (
            conn.execute(
                text("""SELECT match_date,home_team,away_team,home_score,away_score,season_id
            FROM var.v_match_catalog WHERE match_id=:id"""),
                {"id": mid},
            )
            .mappings()
            .first()
        )
        wanted = (
            expected.date,
            expected.home,
            expected.away,
            *expected.score,
            identity("season", season_key),
        )
        if match is None or tuple(match.values()) != wanted:
            raise RecordValidationError(item["record_locator"], "Existing match identity/date/score mismatch")
        fact = raw["fact"]
        if fact.get("linked_event_id"):
            decision = conn.execute(
                text("""SELECT match_id,decision_type_code,period_code
                FROM var.decision WHERE decision_id=:id FOR SHARE"""),
                {"id": identity("decision", fact["linked_event_id"])},
            ).first()
            if decision is None or tuple(decision) != (mid, fact["category"], fact["period"]):
                raise RecordValidationError(item["record_locator"], "Linked decision does not match evidence")
        if item["entity_kind"] == "added_time":
            source = conn.scalar(
                text("""SELECT ds.source_code FROM var.added_time a
                JOIN var.source_record sr USING(source_record_id)
                JOIN var.import_batch b USING(import_batch_id) JOIN var.data_source ds USING(data_source_id)
                WHERE a.match_id=:id AND a.period_code=:period"""),
                {"id": mid, "period": fact["period"]},
            )
            if source is not None and source != source_code:
                raise RecordValidationError(
                    item["record_locator"], "Announcement already belongs to another source"
                )


def import_evidence(engine, snapshot: Snapshot) -> dict:
    return load_snapshot(
        engine,
        snapshot,
        transformer=transform_evidence,
        table_order=TABLES,
        transform_version="cited-worldcup2022-v1",
        preflight=reconcile,
        source_info=dict(
            source_code=SOURCE_CODE,
            name="World Cup 2022 cited match evidence",
            source_kind="manual",
            reference_url="https://github.com/L1k1th1508/VAR-ANALYSIS_DBMS/blob/main/docs/source_coverage.md",
            license_reference="Factual annotations with citations; linked articles retain publisher copyright.",
            attribution_text="Match evidence: England Football, The Guardian, Sky Sports, FourFourTwo and AS.",
        ),
    )


def import_premier_added_time(engine, snapshot: Snapshot) -> dict:
    """Announcement-only extension for the existing 2015/16 matches."""

    def announcements_only(source):
        if any(o["entity_kind"] != "added_time" for o in source.observations):
            raise RecordValidationError(
                source.observations[0]["record_locator"],
                "2015/16 accepts announcements only; VAR not applicable",
            )
        return transform_evidence(source)

    return load_snapshot(
        engine,
        snapshot,
        transformer=announcements_only,
        table_order=TABLE_ORDER_ANNOUNCEMENTS,
        transform_version="cited-premier2015-announcements-v1",
        preflight=lambda conn, source: reconcile(
            conn, source, season_key="2/27", source_code="premier2015_announcements"
        ),
        source_info=dict(
            source_code="premier2015_announcements",
            name="Premier League 2015/16 cited announcements",
            source_kind="manual",
            reference_url="https://github.com/L1k1th1508/VAR-ANALYSIS_DBMS/blob/main/docs/premier_league_sources.md",
            license_reference="Factual annotations with citations; linked articles retain publisher copyright.",
            attribution_text="Announced-time evidence: Sports Mole live match coverage.",
        ),
    )


TABLE_ORDER_ANNOUNCEMENTS = ["added_time"]


def import_world_cup_var(engine, snapshot: Snapshot) -> dict:
    """Add the 21 missing interventions; retain the original six records and citations."""

    def reviews_only(source):
        if any(o["entity_kind"] != "var_review" for o in source.observations):
            raise RecordValidationError(
                source.observations[0]["record_locator"], "This supplement accepts VAR reviews only"
            )
        return transform_evidence(source)

    return load_snapshot(
        engine,
        snapshot,
        transformer=reviews_only,
        table_order=["decision", "var_involvement"],
        transform_version="cited-worldcup2022-var-completion-v1",
        preflight=reconcile,
        source_info=dict(
            source_code="worldcup2022_var_completion",
            name="World Cup 2022 remaining cited VAR interventions",
            source_kind="manual",
            reference_url="https://www.espn.com/soccer/story/_/id/37634070/var-review-every-decision-world-cup-analysed",
            license_reference="Brief factual annotations only; ESPN retains copyright in its reporting.",
            attribution_text="Interventions: Dale Johnson, ESPN, 17 December 2022. Match/event identity: StatsBomb.",
        ),
    )
