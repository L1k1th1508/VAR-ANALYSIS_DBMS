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
from var_analytics.supplements import (
    extract_evidence,
    import_evidence,
    import_world_cup_var,
    transform_evidence,
)
from var_analytics.transform_validate import RecordValidationError, identity

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def evidence():
    return extract_evidence(ROOT / "data/supplements/world_cup_2022_evidence.json")


@pytest.fixture
def evidence_db(test_urls, evidence, request):
    admin, owner = engine_for(test_urls["admin"]), engine_for(test_urls["owner"])
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch")) == 0
    folder = ROOT / "data/raw/statsbomb"
    if not (folder / "demo_manifest.json").exists():
        pytest.skip("Run scripts/fetch_demo.py for World Cup source evidence fixtures")
    base = extract(folder)
    selected = {o["raw_payload"]["match"]["id"] for o in evidence.observations}
    if getattr(request, "param", None) == "complete":
        completion = extract_evidence(ROOT / "data/supplements/world_cup_2022_var_completion.json")
        selected.update(o["raw_payload"]["match"]["id"] for o in completion.observations)
    base.observations = [
        o
        for o in base.observations
        if (o["raw_payload"]["match_id"] if o["entity_kind"] == "match" else o["match_id"]) in selected
    ]
    base.fingerprint = hashlib.sha256(str(sorted(selected)).encode()).hexdigest()
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


def test_complete_intervention_annotations_have_distinct_semantics(evidence):
    completion = extract_evidence(ROOT / "data/supplements/world_cup_2022_var_completion.json")
    original = {o["external_key"] for o in evidence.observations if o["entity_kind"] == "var_review"}
    assert len(completion.observations) == 21
    assert not original.intersection(o["external_key"] for o in completion.observations)
    plan = transform_evidence(completion)
    assert len(plan["decision"]) == 10 and len(plan["var_involvement"]) == 21
    assert sum(r["outcome_code"] == "OVERTURNED" for r in plan["var_involvement"]) == 20
    assert all(r["duration_seconds"] is None and r["minute"] is None for r in plan["var_involvement"])
    by_key = {o["external_key"]: o["raw_payload"]["fact"] for o in completion.observations}
    assert by_key["wal-irn-hennessey"]["category"] == "FOUL"
    assert by_key["wal-irn-hennessey"]["linked_event_id"]
    assert by_key["fra-pol-retake"]["category"] == "PENALTY_REVIEW"
    assert "linked_event_id" not in by_key["fra-pol-retake"]


@pytest.mark.integration
@pytest.mark.parametrize("evidence_db", ["complete"], indirect=True)
def test_full_var_import_preserves_originals_and_filters(evidence, evidence_db, test_urls, monkeypatch):
    admin, owner = evidence_db
    import_evidence(admin, evidence)
    with owner.connect() as conn:
        original = conn.execute(
            text("SELECT var_involvement_id,source_record_id FROM var.var_involvement ORDER BY 1")
        ).all()
        base = conn.scalar(text("SELECT count(*) FROM var.decision"))
        penalties = conn.scalar(text("SELECT count(*) FROM var.decision WHERE decision_type_code='PENALTY'"))
    completion = extract_evidence(ROOT / "data/supplements/world_cup_2022_var_completion.json")
    assert import_world_cup_var(admin, completion)["status"] == "success"
    assert import_world_cup_var(admin, completion)["status"] == "already_loaded"
    with owner.begin() as conn:
        current = dict(
            conn.execute(text("SELECT var_involvement_id,source_record_id FROM var.var_involvement")).all()
        )
        assert all(current[key] == record for key, record in original)
        assert len(current) == 27
        assert conn.scalar(text("SELECT count(*) FROM var.decision")) == base + 10
        assert (
            conn.scalar(text("SELECT count(*) FROM var.decision WHERE decision_type_code='PENALTY'"))
            == penalties
        )
        conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))
    service = AnalyticsService(engine_for(test_urls["reader"]))
    world_cup = Scope(league_id=identity("league", 43), season_id=identity("season", "43/106"))
    reviews = service.reviews(world_cup)
    assert len(reviews) == 27 and reviews.match_id.nunique() == 23
    assert reviews.outcome_code.value_counts().to_dict() == {"OVERTURNED": 25, "UPHELD": 2}
    assert reviews.duration_seconds.isna().all() and reviews.source_record_id.notna().all()
    assert len(service.reviews(Scope(from_date=date(2022, 12, 4), to_date=date(2022, 12, 4)))) == 2
    assert service.reviews(Scope(from_date=date(2022, 12, 18), to_date=date(2022, 12, 18))).empty
    assert service.reviews(Scope(league_id=identity("league", 2))).empty
    monkeypatch.setenv("READER_DATABASE_URL", test_urls["reader"])
    app = AppTest.from_string("from var_analytics.ui.pages import var\nvar()").run(timeout=30)
    assert not app.exception and not app.error
    assert len(app.dataframe[-1].value) == 27
    assert app.metric[0].value == "27" and app.metric[2].value == "92.6%"
    assert any("27 interventions loaded" in info.value for info in app.info)


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
