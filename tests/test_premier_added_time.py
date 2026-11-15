"""Announced minutes for existing real 2015/16 matches; VAR remains inapplicable."""

import copy
import hashlib
import json
from pathlib import Path

import pytest
from sqlalchemy import text
from streamlit.testing.v1 import AppTest

from var_analytics.analytics_service import AnalyticsService, Scope
from var_analytics.db import engine_for
from var_analytics.extract import Snapshot, mapped_event
from var_analytics.load import load_snapshot
from var_analytics.supplements import extract_evidence, import_premier_added_time, transform_evidence
from var_analytics.transform_validate import RecordValidationError, identity

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def announcement_facts():
    return extract_evidence(ROOT / "data/supplements/premier_league_2015_added_time.json")


@pytest.fixture
def announcement_db(test_urls):
    admin, owner = engine_for(test_urls["admin"]), engine_for(test_urls["owner"])
    folder = ROOT / "data/raw/statsbomb-premier-league"
    if not (folder / "demo_manifest.json").exists():
        pytest.skip("Download Premier League 2015/16 source fixtures")
    manifest = json.loads((folder / "demo_manifest.json").read_bytes())

    def read(path):
        content = (folder / path).read_bytes()
        assert hashlib.sha256(content).hexdigest() == manifest["files"][path]["sha256"]
        return json.loads(content)

    observations = []

    def capture(kind, key, path, raw, **context):
        observations.append(
            dict(
                entity_kind=kind,
                external_key=str(key),
                record_locator=f"https://github.com/hudl/open-data/blob/{manifest['revision']}/{path}#{key}",
                raw_payload=raw,
                **context,
            )
        )

    for match in read("data/matches/2/27.json"):
        mid = match["match_id"]
        if mid not in {3754261, 3754092}:
            continue
        capture("match", mid, "data/matches/2/27.json", match)
        for kind in ("lineups", "events"):
            path = f"data/{kind}/{mid}.json"
            for item in read(path):
                if kind == "lineups":
                    capture("lineup", item["team_id"], path, item, match_id=mid)
                elif mapped_event(item):
                    capture("event", item["id"], path, item, match_id=mid)
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch")) == 0
    try:
        load_snapshot(
            admin,
            Snapshot(
                hashlib.sha256(b"real-added-time-fixtures-v1").hexdigest(), manifest["revision"], observations
            ),
        )
        yield admin, owner
    finally:
        with owner.begin() as conn:
            assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
            conn.execute(
                text("TRUNCATE var.source_record,var.import_batch,var.data_source RESTART IDENTITY CASCADE")
            )
            conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))


def test_real_announcements_preserve_missing_period_and_seconds(announcement_facts):
    plan = transform_evidence(announcement_facts)
    assert len(plan["added_time"]) == 3
    assert plan["var_involvement"] == [] and plan["decision"] == []
    assert all(a["announced_seconds"] is None for a in plan["added_time"])
    assert not any(
        a["match_id"] == identity("match", 3754092) and a["period_code"] == 1 for a in plan["added_time"]
    )


@pytest.mark.integration
def test_historical_announcements_import_and_pages(
    announcement_facts, announcement_db, test_urls, monkeypatch
):
    admin, owner = announcement_db
    with owner.connect() as conn:
        decisions = conn.scalar(text("SELECT count(*) FROM var.decision"))
    assert import_premier_added_time(admin, announcement_facts)["status"] == "success"
    assert import_premier_added_time(admin, announcement_facts)["status"] == "already_loaded"
    service = AnalyticsService(engine_for(test_urls["reader"]))
    scope = Scope(season_id=identity("season", "2/27"))
    assert int(service.totals(scope).matches) == 2
    assert int(service.totals(scope).decisions) == decisions
    assert service.reviews(scope).empty
    periods = service.added_time(scope).set_index("period_code")
    assert periods.loc[1, "announcements"] == 1 and periods.loc[1, "mean_announced_minutes"] == 2
    assert periods.loc[2, "announcements"] == 2 and periods.loc[2, "mean_announced_minutes"] == 5
    assert service.added_time_records(scope).source_url.str.startswith("https://").all()
    monkeypatch.setenv("READER_DATABASE_URL", test_urls["reader"])
    for name in ("var", "added_time"):
        app = AppTest.from_string(f"from var_analytics.ui.pages import {name}\n{name}()")
        app.session_state["scope"] = scope
        app.run(timeout=30)
        assert not app.exception and not app.error
        if name == "added_time":
            assert len(app.dataframe[-1].value) == 3
        else:
            assert any("predates VAR" in i.value for i in app.info)


@pytest.mark.integration
@pytest.mark.parametrize("mutation", ["score", "season", "review"])
def test_invalid_historical_evidence_retained_without_domain_changes(
    announcement_facts, announcement_db, mutation
):
    admin, owner = announcement_db
    if mutation == "score":
        announcement_facts.observations[0]["raw_payload"]["match"]["score"] = [9, 9]
    elif mutation == "season":
        announcement_facts.observations[0]["raw_payload"]["match"]["id"] = 3869685
    else:
        item = copy.deepcopy(announcement_facts.observations[0])
        item.update(entity_kind="var_review", record_locator=item["record_locator"] + "-invalid")
        announcement_facts.observations.append(item)
    with pytest.raises(RecordValidationError):
        import_premier_added_time(admin, announcement_facts)
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.added_time")) == 0
        assert conn.scalar(text("SELECT count(*) FROM var.var_involvement")) == 0
        assert (
            conn.scalar(text("SELECT count(*) FROM var.source_record WHERE validation_status='rejected'"))
            == 1
        )
