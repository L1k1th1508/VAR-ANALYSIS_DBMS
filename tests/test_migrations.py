from pathlib import Path

import pytest
from sqlalchemy import text

from var_analytics.migrate import migrate

pytestmark = pytest.mark.integration
MIGRATIONS = Path(__file__).resolve().parents[1] / "sql" / "migrations"


def test_repeated_migration_is_noop(test_urls):
    assert migrate(test_urls["owner"]) == []


def test_reverse_and_forward_scripts_in_rolled_back_test_transaction(owner):
    # Only the isolated test database is available through this fixture.
    assert owner.scalar(text("SELECT current_database()")) == "var_analytics_test"
    for path in sorted(MIGRATIONS.glob("*.down.sql"), reverse=True):
        owner.connection.driver_connection.execute(path.read_text(encoding="utf-8"), prepare=False)
    assert owner.scalar(text("SELECT to_regnamespace('var')")) is None
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if not path.name.endswith(".down.sql"):
            owner.connection.driver_connection.execute(path.read_text(encoding="utf-8"), prepare=False)
    assert owner.scalar(text("SELECT to_regclass('var.football_match')")) is not None
