"""Cited evidence reconciliation and analytics in the disposable database only."""

import copy
import hashlib
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from streamlit.testing.v1 import AppTest

from var_analytics.analytics_service import AnalyticsService, Scope
from var_analytics.db import engine_for
from var_analytics.extract import extract
from var_analytics.load import load_snapshot
from var_analytics.supplements import extract_evidence, import_evidence, transform_evidence
from var_analytics.transform_validate import RecordValidationError

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence():
    return extract_evidence(ROOT / "data/supplements/world_cup_2022_evidence.json")


@pytest.fixture
def evidence_db(test_urls, evidence):
    admin, owner = engine_for(test_urls["admin"]), engine_for(test_urls["owner"])
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch")) == 0
    folder = ROOT / "data/raw/statsbomb"
    if not (folder / "demo_manifest.json").exists():
        pytest.skip("Run scripts/fetch_demo.py for seven-match source evidence fixtures")
    base = extract(folder)
    selected = {o["raw_payload"]["match"]["id"] for o in evidence.observations}
    base.observations = [
        o
        for o in base.observations
        if (o["raw_payload"]["match_id"] if o["entity_kind"] == "match" else o["match_id"]) in selected
    ]
    base.fingerprint = hashlib.sha256(b"test-seven-match-source-selection-v1").hexdigest()
    try:
        load_snapshot(admin, base)
        yield admin, owner
    finally:
        with owner.begin() as conn:
            assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
            conn.execute(
                text("TRUNCATE var.source_record,var.import_batch,var.data_source RESTART IDENTITY CASCADE")
            )
            conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))


def test_cited_facts_preserve_missing_timing_and_event_semantics(evidence):
    plan = transform_evidence(evidence)
    assert {k: len(v) for k, v in plan.items()} == {"decision": 3, "var_involvement": 6, "added_time": 15}
    assert all(r["duration_seconds"] is None and r["minute"] is None for r in plan["var_involvement"])
    assert all(r["announced_seconds"] is None for r in plan["added_time"])
    assert {r["decision_type_code"] for r in plan["decision"]} == {"GOAL_REVIEW", "PENALTY_REVIEW"}


@pytest.mark.parametrize("mutation", ["negative_minutes", "duplicate", "invented_duration", "bad_outcome"])
def test_invalid_annotations_are_rejected(evidence, mutation):
    if mutation == "negative_minutes":
        evidence.observations[0]["raw_payload"]["fact"]["minutes"] = -1
    elif mutation == "duplicate":
        evidence.observations.append(copy.deepcopy(evidence.observations[0]))
    else:
        review = next(o for o in evidence.observations if o["entity_kind"] == "var_review")
        if mutation == "invented_duration":
            review["raw_payload"]["fact"]["duration_seconds"] = 30
        else:
            review["raw_payload"]["fact"]["outcome"] = "LIKELY_OVERTURNED"
    with pytest.raises(RecordValidationError):
        transform_evidence(evidence)


@pytest.mark.integration
def test_evidence_import_idempotency_analytics_and_pages(evidence, evidence_db, test_urls, monkeypatch):
    admin, owner = evidence_db
    with owner.connect() as conn:
        base = conn.scalar(text("SELECT count(*) FROM var.decision"))
        penalties = conn.scalar(text("SELECT count(*) FROM var.decision WHERE decision_type_code='PENALTY'"))
    result = import_evidence(admin, evidence)
    assert result["status"] == "success" and result["observations"] == 21
    assert import_evidence(admin, evidence)["status"] == "already_loaded"
    with owner.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.decision")) == base + 3
        assert (
            conn.scalar(text("SELECT count(*) FROM var.decision WHERE decision_type_code='PENALTY'"))
            == penalties
        )
        assert (
            conn.scalar(text("SELECT count(*) FROM var.source_record WHERE validation_status!='accepted'"))
            == 0
        )
        conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))
    service = AnalyticsService(engine_for(test_urls["reader"]))
    reviews = service.reviews(Scope())
    assert len(reviews) == 6 and (reviews.outcome_code == "OVERTURNED").sum() == 5
    assert reviews.match_id.nunique() == 6 and reviews.duration_seconds.isna().all()
    assert reviews.source_url.str.startswith("https://").all()
    periods = service.added_time(Scope()).set_index("period_code")
    assert periods.loc[1, "announcements"] == 6 and periods.loc[2, "announcements"] == 7
    assert periods.loc[1, "mean_announced_minutes"] == pytest.approx(32 / 6)
    assert periods.loc[2, "mean_announced_minutes"] == pytest.approx(50 / 7)
    assert periods.loc[3, "mean_announced_minutes"] == 1 and periods.loc[4, "mean_announced_minutes"] == 3
    assert periods.measured_seconds_n.sum() == 0
    final = Scope(from_date=date(2022, 12, 18), to_date=date(2022, 12, 18))
    assert len(service.added_time_records(final)) == 4 and service.reviews(final).empty
    quarter = Scope(from_date=date(2022, 12, 10), to_date=date(2022, 12, 10))
    assert list(service.added_time_records(quarter).period_code) == [2]
    monkeypatch.setenv("READER_DATABASE_URL", test_urls["reader"])
    for name in ("var", "added_time"):
        app = AppTest.from_string(f"from var_analytics.ui.pages import {name}\n{name}()").run(timeout=30)
        assert not app.exception and not app.error, name
        assert len(app.get("plotly_chart")) == 2
        assert len(app.dataframe[-1].value) == (6 if name == "var" else 15)


@pytest.mark.integration
@pytest.mark.parametrize("mismatch", ["score", "linked_event"])
def test_reconciliation_failure_keeps_evidence_and_base_data(evidence, evidence_db, mismatch):
    admin, owner = evidence_db
    if mismatch == "score":
        evidence.observations[0]["raw_payload"]["match"]["score"] = [99, 0]
    else:
        review = next(o for o in evidence.observations if o["entity_kind"] == "var_review")
        review["raw_payload"]["fact"]["linked_event_id"] = "62233fb1-7200-49ca-aa10-948d071008f0"
    with pytest.raises(RecordValidationError):
        import_evidence(admin, evidence)
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.var_involvement")) == 0
        assert conn.scalar(text("SELECT count(*) FROM var.added_time")) == 0
        assert conn.scalar(text("SELECT count(*) FROM var.football_match")) == 7
        assert (
            conn.scalar(text("SELECT count(*) FROM var.source_record WHERE validation_status='rejected'"))
            == 1
        )
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch WHERE status='failed'")) == 1


@pytest.mark.integration
def test_late_database_failure_rolls_back_supplement(evidence, evidence_db, monkeypatch):
    from var_analytics import supplements

    admin, owner = evidence_db
    plan = transform_evidence(evidence)
    plan["added_time"][-1]["announced_seconds"] = 60
    monkeypatch.setattr(supplements, "transform_evidence", lambda _: plan)
    with pytest.raises(IntegrityError):
        import_evidence(admin, evidence)
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.var_involvement")) == 0
        assert (
            conn.scalar(text("SELECT count(*) FROM var.decision WHERE decision_type_code LIKE '%_REVIEW'"))
            == 0
        )
        assert conn.scalar(text("SELECT count(*) FROM var.football_match")) == 7
