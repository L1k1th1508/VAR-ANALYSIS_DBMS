from pathlib import Path

import pytest
from argon2 import PasswordHasher
from streamlit.testing.v1 import AppTest

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
