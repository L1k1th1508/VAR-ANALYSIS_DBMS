"""Integration fixtures use local audited source records, never a fabricated demo."""

import hashlib
import json
import os
from datetime import date, time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import pytest
from dotenv import load_dotenv
from sqlalchemy import MetaData, text

from var_analytics.db import engine_for
from var_analytics.migrate import migrate

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def test_urls():
    load_dotenv(ROOT / ".env")
    urls = {r: os.getenv(f"TEST_{r.upper()}_DATABASE_URL", "") for r in ("owner", "reader", "admin")}
    if not all(urls.values()):
        pytest.skip("Isolated PostgreSQL test credentials are not configured")
    for url in urls.values():
        with engine_for(url).connect() as conn:
            assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test", (
                "Refusing non-test database"
            )
            assert int(conn.scalar(text("SHOW server_version_num"))) // 10000 == 16
    migrate(urls["owner"])
    return urls


@pytest.fixture
def owner(test_urls):
    with engine_for(test_urls["owner"]).connect() as conn:
        transaction = conn.begin()
        try:
            yield conn
        finally:
            transaction.rollback()


@pytest.fixture
def tables(owner):
    metadata = MetaData(schema="var")
    metadata.reflect(bind=owner)
    return {table.name: table for table in metadata.tables.values()}


@pytest.fixture
def source_case(owner, tables):
    return seed_source_case(owner, tables)


@pytest.fixture
def admin_case(test_urls, tables):
    with engine_for(test_urls["admin"]).connect() as conn:
        transaction = conn.begin()
        try:
            yield conn, seed_source_case(conn, tables)
        finally:
            transaction.rollback()


def seed_source_case(owner, tables):
    """Seed source-backed test copies inside a transaction rolled back after each test.

    Tests deliberately attempt invalid mutations; none enter the application/demo DB.
    This is a schema fixture, not a selected ingestion adapter or finalized ETL.
    """
    folder = ROOT / "data" / "raw" / "statsbomb"
    if not (folder / "manifest.json").exists():
        pytest.skip("Run scripts/audit_sources.py for local source-backed integrity fixtures")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    matches = json.loads((folder / "data/matches/43/106.json").read_bytes())
    matches = [m for m in matches if m["match_id"] in manifest["selected_match_ids"]]
    source = owner.execute(
        tables["data_source"]
        .insert()
        .values(
            source_code="statsbomb_schema_test",
            name="StatsBomb local schema fixture",
            reference_url="https://github.com/hudl/open-data",
            source_kind="provider",
        )
        .returning(tables["data_source"].c.data_source_id)
    ).scalar_one()
    batch = owner.execute(
        tables["import_batch"]
        .insert()
        .values(
            data_source_id=source,
            input_fingerprint=manifest["revision"],
            transform_version="schema-test",
            status="pending",
        )
        .returning(tables["import_batch"].c.import_batch_id)
    ).scalar_one()

    observations = {}

    def evidence(kind, key, raw):
        if (kind, key) in observations:
            return observations[(kind, key)]
        serialized = json.dumps(raw, sort_keys=True, ensure_ascii=False).encode()
        record_id = owner.execute(
            tables["source_record"]
            .insert()
            .values(
                import_batch_id=batch,
                entity_kind=kind,
                external_key=str(key),
                record_locator=f"{kind}/{key}",
                payload_sha256=hashlib.sha256(serialized).hexdigest(),
                raw_payload=raw,
                validation_status="accepted",
            )
            .returning(tables["source_record"].c.source_record_id)
        ).scalar_one()
        observations[(kind, key)] = record_id
        return record_id

    def identity(kind, key):
        return uuid5(NAMESPACE_URL, f"statsbomb-schema-test/{kind}/{key}")

    inserted = set()

    def insert(table, key, record, **values):
        pk = identity(table, key)
        if (table, pk) not in inserted:
            owner.execute(
                tables[table].insert().values(**{f"{table}_id": pk}, source_record_id=record, **values)
            )
            inserted.add((table, pk))
        return pk

    ids = []
    for match in matches:
        record = evidence("match", match["match_id"], match)
        league = insert(
            "league",
            match["competition"]["competition_id"],
            record,
            name=match["competition"]["competition_name"],
            competition_kind="international",
        )
        season = insert(
            "season",
            match["season"]["season_id"],
            record,
            league_id=league,
            label=match["season"]["season_name"],
        )
        home = insert(
            "team", match["home_team"]["home_team_id"], record, name=match["home_team"]["home_team_name"]
        )
        away = insert(
            "team", match["away_team"]["away_team_id"], record, name=match["away_team"]["away_team_name"]
        )
        mid = identity("match", match["match_id"])
        owner.execute(
            tables["football_match"]
            .insert()
            .values(
                match_id=mid,
                season_id=season,
                home_team_id=home,
                away_team_id=away,
                home_score=match["home_score"],
                away_score=match["away_score"],
                status="completed",
                match_date=date.fromisoformat(match["match_date"]),
                kickoff_local=time.fromisoformat(match["kick_off"]),
                source_record_id=record,
            )
        )
        ref = insert("referee", match["referee"]["id"], record, name=match["referee"]["name"])
        owner.execute(
            tables["match_official"]
            .insert()
            .values(
                match_id=mid, role_code="MAIN_REFEREE", slot_no=1, referee_id=ref, source_record_id=record
            )
        )
        ids.append(
            {"match": mid, "home": home, "away": away, "record": record, "referee": ref, "original": match}
        )
    first = ids[0]
    original_id = first["original"]["match_id"]
    events = json.loads((folder / f"data/events/{original_id}.json").read_bytes())
    card_event = next(
        e for e in events if e.get("foul_committed", {}).get("card") or e.get("bad_behaviour", {}).get("card")
    )
    lineup = json.loads((folder / f"data/lineups/{original_id}.json").read_bytes())
    team_entry = next(t for t in lineup if t["team_id"] == card_event["team"]["id"])
    player_entry = next(p for p in team_entry["lineup"] if p["player_id"] == card_event["player"]["id"])
    record = evidence("lineup-player", player_entry["player_id"], player_entry)
    player = insert("player", player_entry["player_id"], record, name=player_entry["player_name"])
    player_team = identity("team", team_entry["team_id"])
    owner.execute(
        tables["match_player"]
        .insert()
        .values(match_id=first["match"], player_id=player, team_id=player_team, source_record_id=record)
    )
    foul = next(e for e in events if e["type"]["name"] == "Foul Committed")
    record = evidence("event", foul["id"], foul)
    did = identity("decision", foul["id"])
    owner.execute(
        tables["decision"]
        .insert()
        .values(
            decision_id=did,
            match_id=first["match"],
            decision_type_code="FOUL",
            period_code=foul["period"],
            minute=foul["minute"],
            second=foul["second"],
            source_order=foul["index"],
            source_record_id=record,
        )
    )
    owner.execute(
        tables["decision_team"]
        .insert()
        .values(
            decision_id=did,
            team_id=identity("team", foul["team"]["id"]),
            involvement_code="recorded_team",
            source_record_id=record,
        )
    )
    return {
        "matches": ids,
        "player": player,
        "player_team": player_team,
        "decision": did,
        "record": record,
        "card_event": card_event,
        "batch": batch,
    }
