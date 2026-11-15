"""Source-backed ingestion tests against the disposable PostgreSQL 16 database only."""

import copy
import hashlib
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from streamlit.testing.v1 import AppTest

from var_analytics.db import engine_for
from var_analytics.extract import extract
from var_analytics.load import load_snapshot
from var_analytics.transform_validate import RecordValidationError, transform

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def snapshot():
    folder = ROOT / "data/raw/statsbomb"
    if not (folder / "manifest.json").exists():
        pytest.skip("Download the local source audit fixture first")
    return extract(folder, "manifest.json")


@pytest.fixture
def import_db(test_urls):
    """Committed transaction tests need cleanup in the explicitly disposable DB."""
    owner = engine_for(test_urls["owner"])
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch")) == 0
    try:
        yield engine_for(test_urls["admin"]), owner
    finally:
        with owner.begin() as conn:
            assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
            conn.execute(
                text("TRUNCATE var.source_record,var.import_batch,var.data_source RESTART IDENTITY CASCADE")
            )
            conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))


def test_source_mapping_preserves_known_counts_and_unknowns(snapshot):
    plan = transform(snapshot)
    assert len(plan["football_match"]) == 3
    assert len(plan["team"]) == 4
    assert len(plan["match_official"]) == 3
    assert len(plan["card_issued"]) == 11
    assert all(row["timezone_name"] is None and row["kickoff_at"] is None for row in plan["football_match"])
    assert not any(row["period_code"] == 5 for row in plan["decision"])
    assert not any("official_role_code" in row for row in plan["decision"])


def test_checksum_rejects_tampered_source(snapshot, tmp_path):
    import json

    source = ROOT / "data/raw/statsbomb"
    manifest = json.loads((source / "manifest.json").read_bytes())
    (tmp_path / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    target = tmp_path / "data/matches/43/106.json"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"[]")
    with pytest.raises(ValueError, match="checksum mismatch"):
        extract(tmp_path, "manifest.json")


@pytest.mark.integration
def test_idempotent_admin_import_and_populated_pages(snapshot, import_db, monkeypatch, test_urls):
    admin, owner = import_db
    first = load_snapshot(admin, snapshot)
    repeated = load_snapshot(admin, snapshot)
    assert first["status"] == "success" and repeated["status"] == "already_loaded"
    assert first["batch_id"] == repeated["batch_id"]
    with owner.begin() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.football_match")) == 3
        assert conn.scalar(text("SELECT count(*) FROM var.card_issued")) == 11
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch")) == 1
        assert conn.scalar(text("SELECT count(*) FROM var.var_involvement")) == 0
        assert conn.scalar(text("SELECT count(*) FROM var.added_time")) == 0
        assert not conn.scalar(
            text("SELECT has_table_privilege('app_admin','var.decision_outcome','UPDATE')")
        )
        assert not conn.scalar(text("SELECT has_table_privilege('app_admin','var.official_role','UPDATE')"))
        assert not conn.scalar(
            text("SELECT has_function_privilege('app_admin','var.guard_decision()','EXECUTE')")
        )
        conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))
        assert conn.scalar(text("SELECT sum(matches) FROM var.mv_referee_stat_summary")) == 3
    monkeypatch.setenv("READER_DATABASE_URL", test_urls["reader"])
    for name in ("home", "matches", "referees", "var", "teams", "added_time", "management", "quality"):
        app = AppTest.from_string(f"from var_analytics.ui.pages import {name}\n{name}()").run(timeout=30)
        assert not app.exception and not app.error, name
        if name == "home":
            assert app.metric[0].value == "3"
        if name == "matches":
            assert len(app.selectbox) == 2
            assert list(app.dataframe[-1].value.columns) == ["Field", "Value"]


@pytest.mark.integration
def test_invalid_source_retains_rejection_without_domain_rows(snapshot, import_db):
    admin, owner = import_db
    invalid = copy.deepcopy(snapshot)
    invalid.fingerprint = hashlib.sha256(b"test-only-invalid-copy").hexdigest()
    event = next(o for o in invalid.observations if o["entity_kind"] == "event")
    event["raw_payload"]["second"] = 60
    with pytest.raises(RecordValidationError):
        load_snapshot(admin, invalid)
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.football_match")) == 0
        assert conn.scalar(text("SELECT status FROM var.import_batch")) == "failed"
        assert (
            conn.scalar(text("SELECT count(*) FROM var.source_record WHERE validation_status='rejected'"))
            == 1
        )
        assert conn.scalar(text("SELECT count(*) FROM var.source_record")) == len(snapshot.observations)


@pytest.mark.integration
def test_database_failure_rolls_back_entire_domain_transaction(snapshot, import_db, monkeypatch):
    from var_analytics import load

    admin, owner = import_db
    plan = transform(snapshot)
    plan["card_issued"][0]["second"] = 60  # deliberate test-only database rejection
    monkeypatch.setattr(load, "transform", lambda _: plan)
    with pytest.raises(IntegrityError):
        load_snapshot(admin, snapshot)
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.football_match")) == 0
        assert conn.scalar(text("SELECT count(*) FROM var.country")) == 0
        assert conn.scalar(text("SELECT status FROM var.import_batch")) == "failed"
        assert conn.scalar(text("SELECT count(*) FROM var.source_record")) == len(snapshot.observations)
