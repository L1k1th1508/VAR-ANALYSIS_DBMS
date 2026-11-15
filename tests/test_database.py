from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from var_analytics.db import engine_for

pytestmark = pytest.mark.integration


def reject(conn, sql, values=None):
    with pytest.raises(DBAPIError), conn.begin_nested():
        conn.execute(text(sql), values or {})


def test_required_objects_and_three_roles(owner):
    names = set(owner.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='var'")))
    assert {
        "country",
        "league",
        "season",
        "team",
        "venue",
        "referee",
        "official_role",
        "football_match",
        "match_official",
        "decision_type",
        "decision_outcome",
        "decision",
        "decision_team",
        "var_involvement",
        "player",
        "card_issued",
        "added_time",
        "data_source",
        "import_batch",
        "source_record",
        "match_player",
    } <= names
    roles = owner.execute(
        text(
            "SELECT rolname,rolsuper,rolcreaterole,rolcreatedb FROM pg_roles "
            "WHERE rolname IN ('db_owner','app_reader','app_admin')"
        )
    ).all()
    assert len(roles) == 3 and all(not any(row[1:]) for row in roles)


def test_self_match_and_missing_completed_scores(owner, source_case):
    mid = source_case["matches"][0]["match"]
    reject(owner, "UPDATE football_match SET away_team_id=home_team_id WHERE match_id=:id", {"id": mid})
    reject(owner, "UPDATE football_match SET home_score=NULL,away_score=NULL WHERE match_id=:id", {"id": mid})


def test_invalid_official_attribution(owner, source_case):
    reject(
        owner,
        "UPDATE decision SET official_role_code='MAIN_REFEREE',official_slot_no=2 WHERE decision_id=:id",
        {"id": source_case["decision"]},
    )
    reject(
        owner,
        "UPDATE decision SET official_role_code='MAIN_REFEREE' WHERE decision_id=:id",
        {"id": source_case["decision"]},
    )


def test_var_only_role_enforced(owner, source_case):
    reject(
        owner,
        "INSERT INTO var_involvement(var_involvement_id,decision_id,review_kind,official_role_code,"
        "official_slot_no,source_record_id) VALUES(:id,:decision,'review','MAIN_REFEREE',1,:record)",
        {"id": uuid4(), "decision": source_case["decision"], "record": source_case["record"]},
    )


def test_card_requires_player_in_same_match(owner, source_case):
    other = source_case["matches"][1]["match"]
    reject(
        owner,
        "INSERT INTO card_issued(card_id,match_id,player_id,card_type,period_code,source_record_id) "
        "VALUES(:id,:match,:player,'yellow',1,:record)",
        {"id": uuid4(), "match": other, "player": source_case["player"], "record": source_case["record"]},
    )


def test_nonparticipant_and_parent_changes_rejected(owner, source_case):
    first = source_case["matches"][0]
    outsider = next(
        m["home"] for m in source_case["matches"] if m["home"] not in (first["home"], first["away"])
    )
    reject(
        owner,
        "UPDATE match_player SET team_id=:team WHERE match_id=:match",
        {"team": outsider, "match": first["match"]},
    )
    reject(
        owner,
        "UPDATE decision_team SET team_id=:team WHERE decision_id=:decision",
        {"team": outsider, "decision": source_case["decision"]},
    )
    col = "home_team_id" if source_case["player_team"] == first["home"] else "away_team_id"
    reject(
        owner,
        f"UPDATE football_match SET {col}=:team WHERE match_id=:match",
        {"team": outsider, "match": first["match"]},
    )


@pytest.mark.parametrize("seconds", [-1, 60])
def test_added_seconds_rejected(owner, source_case, seconds):
    reject(
        owner,
        "INSERT INTO added_time(match_id,period_code,announced_minutes,announced_seconds,source_record_id) "
        "VALUES(:match,1,0,:seconds,:record)",
        {"match": source_case["matches"][0]["match"], "seconds": seconds, "record": source_case["record"]},
    )


def test_unknown_times_and_raw_evidence(owner, source_case):
    mid = source_case["matches"][0]["match"]
    row = owner.execute(
        text(
            "SELECT match_date,kickoff_local,kickoff_at,timezone_name FROM football_match WHERE match_id=:id"
        ),
        {"id": mid},
    ).one()
    assert row.match_date and row.kickoff_local and row.kickoff_at is None and row.timezone_name is None
    reject(owner, "UPDATE football_match SET kickoff_at=now() WHERE match_id=:id", {"id": mid})
    reject(owner, "UPDATE football_match SET timezone_name='Invented/Zone' WHERE match_id=:id", {"id": mid})
    reject(
        owner,
        "UPDATE source_record SET raw_payload='{}'::jsonb WHERE source_record_id=:id",
        {"id": source_case["record"]},
    )


def test_rollback_keeps_original_score(owner, source_case):
    mid = source_case["matches"][0]["match"]
    before = owner.scalar(text("SELECT home_score FROM football_match WHERE match_id=:id"), {"id": mid})
    try:
        with owner.begin_nested():
            owner.execute(
                text("UPDATE football_match SET home_score=home_score+1 WHERE match_id=:id"), {"id": mid}
            )
            raise RuntimeError("test rollback")
    except RuntimeError:
        pass
    assert (
        owner.scalar(text("SELECT home_score FROM football_match WHERE match_id=:id"), {"id": mid}) == before
    )


def test_direct_role_logins_and_escalation_denial(test_urls):
    for role, username in [("reader", "app_reader"), ("admin", "app_admin")]:
        with engine_for(test_urls[role]).connect() as conn:
            assert conn.scalar(text("SELECT current_user")) == username
            conn.rollback()
            reject(conn, "SET ROLE db_owner")
            reject(conn, "CREATE TABLE var.forbidden(id integer)")
            reject(conn, "REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary")
    with engine_for(test_urls["reader"]).connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM v_match_catalog")) is not None
        reject(conn, "UPDATE football_match SET home_score=0 WHERE false")
        reject(conn, "DELETE FROM source_record WHERE false")
        reject(conn, "SELECT raw_payload FROM source_record")
        reject(conn, "SELECT nextval('source_record_source_record_id_seq')")


def test_admin_crud_and_sequence_use(admin_case):
    owner, source_case = admin_case
    did = source_case["decision"]
    owner.execute(
        text("UPDATE decision SET description='Schema-test-only correction' WHERE decision_id=:id"),
        {"id": did},
    )
    assert owner.scalar(text("SELECT description FROM decision WHERE decision_id=:id"), {"id": did})
    owner.execute(
        text(
            "INSERT INTO import_batch(data_source_id,input_fingerprint,transform_version,status) "
            "SELECT data_source_id,'sequence-permission-test','test','pending' FROM import_batch "
            "WHERE import_batch_id=:id"
        ),
        {"id": source_case["batch"]},
    )
    owner.execute(text("DELETE FROM decision_team WHERE decision_id=:id"), {"id": did})
    reject(owner, "DELETE FROM source_record WHERE false")


def test_summary_refresh_has_no_join_fanout(owner, source_case):
    owner.execute(text("REFRESH MATERIALIZED VIEW mv_referee_stat_summary"))
    stats = owner.execute(
        text("SELECT sum(matches),sum(decisions),sum(known_outcomes) FROM mv_referee_stat_summary")
    ).one()
    assert stats[0] == 3 and stats[1] == 1 and stats[2] == 0


def test_future_objects_are_not_public(owner):
    owner.execute(text("CREATE TABLE var.future_sensitive_test(id integer)"))
    assert not owner.scalar(
        text("SELECT has_table_privilege('app_reader','var.future_sensitive_test','SELECT')")
    )
    assert not owner.scalar(
        text("SELECT has_table_privilege('app_admin','var.future_sensitive_test','SELECT')")
    )
