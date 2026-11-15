"""Owner-only, checksummed SQL migrations. No destructive command is exposed."""

import hashlib
from pathlib import Path

from sqlalchemy import text

from var_analytics.db import engine_for

ROOT = Path(__file__).resolve().parents[2]


def migrate(url: str) -> list[str]:
    applied = []
    engine = engine_for(url)
    with engine.connect() as conn:
        version = int(conn.scalar(text("SHOW server_version_num")))
        if version // 10000 != 16:
            raise RuntimeError("This project requires PostgreSQL 16. No migrations were applied.")
        if conn.scalar(text("SELECT current_user")) != "db_owner":
            raise PermissionError("Run migrations using db_owner, not an application credential.")
    for path in sorted((ROOT / "sql" / "migrations").glob("*.sql")):
        if path.name.endswith(".down.sql"):
            continue
        script = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(script.encode()).hexdigest()
        with engine.begin() as conn:
            conn.execute(text("SELECT pg_advisory_xact_lock(77761001)"))
            exists = conn.scalar(text("SELECT to_regclass('var.schema_migration')"))
            previous = (
                conn.scalar(
                    text("SELECT checksum FROM var.schema_migration WHERE version=:v"), {"v": path.name}
                )
                if exists
                else None
            )
            if previous:
                if previous != checksum:
                    raise RuntimeError(
                        f"Applied migration changed: {path.name}. Add a new migration instead."
                    )
                continue
            conn.connection.driver_connection.execute(script, prepare=False)
            conn.execute(
                text("INSERT INTO var.schema_migration(version,checksum) VALUES(:v,:c)"),
                {"v": path.name, "c": checksum},
            )
            applied.append(path.name)
    return applied


def refresh(url: str) -> None:
    with engine_for(url).begin() as conn:
        conn.execute(text("REFRESH MATERIALIZED VIEW var.mv_referee_stat_summary"))
