"""Create local development secrets without printing or committing them."""

import secrets
from pathlib import Path

from argon2 import PasswordHasher

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    raise SystemExit("Existing .env preserved. Edit it deliberately if configuration needs to change.")
values = {
    name: secrets.token_urlsafe(32)
    for name in ("POSTGRES_PASSWORD", "DB_OWNER_PASSWORD", "APP_READER_PASSWORD", "APP_ADMIN_PASSWORD")
}
password = secrets.token_urlsafe(20)
values["ADMIN_PASSWORD_HASH"] = "'" + PasswordHasher().hash(password) + "'"
for prefix, role, key in [
    ("OWNER", "db_owner", "DB_OWNER_PASSWORD"),
    ("READER", "app_reader", "APP_READER_PASSWORD"),
    ("ADMIN", "app_admin", "APP_ADMIN_PASSWORD"),
]:
    values[f"{prefix}_DATABASE_URL"] = (
        f"postgresql+psycopg://{role}:{values[key]}@localhost:55432/var_analytics"
    )
    values[f"TEST_{prefix}_DATABASE_URL"] = (
        f"postgresql+psycopg://{role}:{values[key]}@localhost:55433/var_analytics_test"
    )
path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n", encoding="utf-8")
credentials = root / ".cache" / "initial-admin-password.txt"
credentials.parent.mkdir(exist_ok=True)
credentials.write_text(password, encoding="utf-8")
print("Created ignored .env and .cache/initial-admin-password.txt. No secret values printed.")
