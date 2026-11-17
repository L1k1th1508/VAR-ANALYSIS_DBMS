from pathlib import Path

import pytest
from argon2 import PasswordHasher
from streamlit.testing.v1 import AppTest
from test_admin import CITATION, REASON, admin_db, country_values, session  # noqa: F401

pytestmark = pytest.mark.integration


def render_page(name):
    from var_analytics.ui import pages

    getattr(pages, name)()


@pytest.mark.parametrize(
    "name", ["home", "matches", "referees", "var", "teams", "added_time", "management", "quality"]
)
def test_eight_pages_empty_database(monkeypatch, test_urls, name):
    monkeypatch.setenv("READER_DATABASE_URL", test_urls["reader"])
    app = AppTest.from_function(render_page, args=(name,)).run(timeout=30)
    assert not app.exception
    assert not app.error
    assert len(app.title) == 1


def test_navigation_and_administrator_session(monkeypatch, test_urls):
    monkeypatch.setenv("READER_DATABASE_URL", test_urls["reader"])
    monkeypatch.setenv("ADMIN_DATABASE_URL", test_urls["admin"])
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", PasswordHasher().hash("test-only password"))
    root = Path(__file__).resolve().parents[1]
    app = AppTest.from_file(str(root / "app.py")).run(timeout=30)
    assert not app.exception and not app.error
    admin = AppTest.from_function(render_page, args=("management",)).run(timeout=30)
    admin.text_input[0].set_value("wrong password")
    admin.button[0].click().run(timeout=30)
    assert not admin.exception and len(admin.error) == 1
    admin.text_input[0].set_value("test-only password")
    admin.button[0].click().run(timeout=30)
    assert not admin.exception and len(admin.success) == 1
    admin.button[0].click().run(timeout=30)
    assert not admin.exception and len(admin.text_input) == 1


@pytest.mark.integration
def test_authenticated_page_add_edit_and_confirmation_controls(admin_db, test_urls, monkeypatch):  # noqa: F811
    service, owner = admin_db
    monkeypatch.setenv("READER_DATABASE_URL", test_urls["reader"])
    monkeypatch.setenv("ADMIN_DATABASE_URL", test_urls["admin"])
    app = AppTest.from_string("from var_analytics.ui.pages import management\nmanagement()")
    app.session_state["admin_session"] = service.session
    app.run(timeout=30)
    assert not app.exception and not app.error
    app.selectbox(key="manage_entity").select("country").run(timeout=30)
    app.radio(key="manage_action").set_value("Add a record").run(timeout=30)
    assert not app.exception
    values = country_values()
    for key, value in values.items():
        app.text_input(key=f"add_country_{key}").set_value(value)
    app.text_input(key="add_country_citation").set_value(CITATION)
    app.text_area(key="add_country_reason").set_value(REASON)
    next(b for b in app.button if b.label == "Save new record").click().run(timeout=30)
    assert not app.exception and not app.error and app.success
    app.radio(key="manage_action").set_value("Browse and edit").run(timeout=30)
    app.text_input(key="search_country").set_value(values["country_id"]).run(timeout=30)
    assert not app.exception and not app.error
    assert next(b for b in app.button if b.label == "Delete record").disabled
    app.radio(key="manage_action").set_value("Import CSV").run(timeout=30)
    assert not app.exception and not app.error
    assert len(app.get("file_uploader")) == 1
