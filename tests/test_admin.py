"""Administrator maintenance tests; source-backed copies only in the disposable database."""

import csv
import io
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

import pytest
from argon2 import PasswordHasher
from sqlalchemy import text

from var_analytics.admin_service import AdminService, spreadsheet_text
from var_analytics.auth import AdminSession, authenticate
from var_analytics.db import engine_for
from var_analytics.extract import extract
from var_analytics.load import load_snapshot

ROOT = Path(__file__).resolve().parents[1]
CITATION = "https://github.com/hudl/open-data"
REASON = "Source-backed maintenance test copy; disposable test database only."


@pytest.fixture
def session(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", PasswordHasher().hash("test-only-admin"))
    return authenticate("test-only-admin")


@pytest.fixture
def admin_db(test_urls, session):
    owner = engine_for(test_urls["owner"])
    admin = engine_for(test_urls["admin"])
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch")) == 0
    folder = ROOT / "data/raw/statsbomb"
    if not (folder / "manifest.json").exists():
        pytest.skip("Download audited source fixtures first")
    try:
        load_snapshot(admin, extract(folder, "manifest.json"))
        yield AdminService(session, admin), owner
    finally:
        with owner.begin() as conn:
            assert conn.scalar(text("SELECT current_database()")) == "var_analytics_test"
            conn.execute(
                text("TRUNCATE var.source_record,var.import_batch,var.data_source RESTART IDENTITY CASCADE")
            )
            conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))


def country_values():
    return {"country_id": str(uuid4()), "name": "France", "iso_code": "FR"}


def test_sessions_required_even_for_direct_calls(session):
    for candidate in (
        None,
        AdminSession(uuid4(), session.issued_at, object()),
        replace(session, issued_at=session.issued_at - 3600),
    ):
        with pytest.raises(PermissionError):
            AdminService(candidate)


@pytest.mark.integration
def test_reader_credentials_cannot_use_admin_service(session, test_urls):
    with pytest.raises(PermissionError, match="app_admin"):
        AdminService(session, engine_for(test_urls["reader"]))


@pytest.mark.integration
def test_create_edit_delete_preserve_audit_and_guard_stale_changes(admin_db):
    service, owner = admin_db
    values = country_values()
    created = service.create("country", values, CITATION, REASON)
    assert created["status"] == "success"
    assert service.create("country", values, CITATION, REASON)["status"] == "already_loaded"
    original = service.get("country", {"country_id": values["country_id"]})
    updated_values = {**values, "name": "French Republic"}
    edited = service.update("country", original, updated_values, CITATION, "Use the country's formal name.")
    assert edited["status"] == "success"
    with pytest.raises(ValueError, match="changed"):
        service.update("country", original, values, CITATION, "A stale edit must be rejected.")
    current = service.get("country", {"country_id": values["country_id"]})
    with pytest.raises(PermissionError, match="Confirm"):
        service.delete("country", current, CITATION, REASON)
    assert (
        service.delete("country", current, CITATION, "Remove this disposable test copy.", confirmed=True)[
            "status"
        ]
        == "success"
    )
    with owner.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT count(*) FROM var.country WHERE country_id=:id"), {"id": values["country_id"]}
            )
            == 0
        )
        payload = conn.scalar(
            text("SELECT raw_payload FROM var.source_record WHERE import_batch_id=:id"),
            {"id": edited["batch_id"]},
        )
        assert payload["before"]["name"] == "France" and payload["submitted"]["name"] == "French Republic"
        assert payload["admin_session_id"] == str(service.session.session_id)


@pytest.mark.integration
def test_csv_preview_duplicate_prevention_and_safe_table_boundary(admin_db):
    service, owner = admin_db
    content = b"country_id,name,iso_code\n,France,FR\n,Morocco,MA\n"
    preview = service.preview_csv("country", content)
    assert preview.valid and len(preview.rows) == 2
    assert "source_record_id" not in service.template("country")
    first = service.import_csv("country", content, CITATION, REASON)
    assert first["status"] == "success"
    assert service.import_csv("country", content, CITATION, REASON)["status"] == "already_loaded"
    with pytest.raises(ValueError, match="not available"):
        service.browse("schema_migration")
    with pytest.raises(ValueError, match="not available"):
        service.create("data_source", {}, CITATION, REASON)
    with owner.connect() as conn:
        assert (
            conn.scalar(
                text("SELECT accepted_count FROM var.import_batch WHERE import_batch_id=:id"),
                {"id": first["batch_id"]},
            )
            == 2
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "content",
    [
        b"name,name\nFrance,France\n",
        b"name,iso_code\nFrance,FR,extra\n",
        b"name,source_record_id\nFrance,123\n",
        b"country_id,name\nwrong,France\n",
        b"country_id,name\n",
        b"\xff\xfe",
        b"name\n" + b"France\n" * 501,
    ],
)
def test_csv_invalid_input_is_blocked(admin_db, content):
    service, _ = admin_db
    try:
        assert not service.preview_csv("country", content).valid
    except ValueError:
        pass


@pytest.mark.integration
def test_import_failure_rolls_back_valid_first_row_and_retains_evidence(admin_db):
    service, owner = admin_db
    existing = service.browse("country").iloc[0].country_id
    first = uuid4()
    content = f"country_id,name\n{first},France\n{existing},France\n".encode()
    assert service.preview_csv("country", content).valid
    with pytest.raises(ValueError, match="already exists"):
        service.import_csv("country", content, CITATION, REASON)
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.country WHERE country_id=:id"), {"id": first}) == 0
        assert conn.scalar(text("SELECT count(*) FROM var.import_batch WHERE status='failed'")) == 1
        assert (
            conn.scalar(text("SELECT count(*) FROM var.source_record WHERE validation_status='rejected'"))
            == 2
        )


@pytest.mark.integration
def test_references_and_restricted_delete_are_enforced(admin_db):
    service, owner = admin_db
    row = service.browse("football_match").iloc[0]
    original = service.get("football_match", {"match_id": row.match_id})
    with pytest.raises(ValueError, match="depend"):
        service.delete("football_match", original, CITATION, REASON, confirmed=True)
    with pytest.raises(ValueError, match="linked record"):
        service.create(
            "referee", {"name": "Source-backed test copy", "country_id": str(uuid4())}, CITATION, REASON
        )
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.football_match")) == 3


@pytest.mark.integration
def test_clock_validation_and_expired_session_on_existing_service(admin_db):
    service, _ = admin_db
    content = f"match_id,period_code,announced_minutes,announced_seconds\n{uuid4()},2,3,60\n".encode()
    assert not service.preview_csv("added_time", content).valid
    service.session = replace(service.session, issued_at=service.session.issued_at - 3600)
    with pytest.raises(PermissionError):
        service.preview_csv("country", b"name\nFrance\n")
    with pytest.raises(PermissionError):
        service.export_csv("country")


@pytest.mark.parametrize("value", ["=1+1", "+command", "-command", "@SUM(A1)", "  =1+1", "\ttext"])
def test_export_text_cannot_become_a_spreadsheet_formula(value):
    assert spreadsheet_text(value) == "'" + value
    assert spreadsheet_text("France") == "France"
    assert spreadsheet_text(None) is None


@pytest.mark.integration
def test_csv_export_is_complete_typed_and_filterable(admin_db):
    service, owner = admin_db
    before = service.export_csv("country")
    # Source-backed country copies exercise the browse/export boundary only in the disposable DB.
    service.import_csv("country", b"name\n" + b"France\n" * 201, CITATION, REASON)
    result = service.export_csv("country")
    assert len(service.browse("country")) == 200
    assert len(result.rows) == len(before.rows) + 201
    assert result.content.startswith(b"\xef\xbb\xbf")
    parsed = list(csv.DictReader(io.StringIO(result.content.decode("utf-8-sig"))))
    assert len(parsed) == len(result.rows)
    assert "source_record_id" not in parsed[0]
    assert all(row["country_id"] for row in parsed)
    preview = service.preview_csv("country", result.content)
    assert preview.valid and len(preview.rows) == len(parsed)
    filtered = service.export_csv("country", str(result.rows[0]["country_id"]))
    assert len(filtered.rows) == 1
    assert service.export_csv("country", "'; DROP TABLE var.country; --").rows == []
    with pytest.raises(ValueError, match="not available"):
        service.export_csv("data_source")
    with owner.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM var.country")) == len(parsed)


@pytest.mark.integration
def test_export_rejects_oversized_result_without_silent_truncation(admin_db, monkeypatch):
    from var_analytics import admin_service

    service, _ = admin_db
    monkeypatch.setattr(admin_service, "MAX_EXPORT_ROWS", 1)
    with pytest.raises(ValueError, match="Narrow the search"):
        service.export_csv("country")
