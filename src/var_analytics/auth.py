"""Server-side administrator capabilities; PostgreSQL independently enforces grants."""

import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from var_analytics.config import settings

_CAPABILITY = object()
SESSION_SECONDS = 1800


@dataclass(frozen=True)
class AdminSession:
    session_id: UUID
    issued_at: float
    capability: object


def authenticate(password: str) -> AdminSession | None:
    encoded = settings().admin_password_hash
    if not encoded or len(password) > 1024:
        return None
    try:
        if PasswordHasher().verify(encoded, password):
            return AdminSession(uuid4(), time.monotonic(), _CAPABILITY)
    except (VerificationError, InvalidHashError):
        pass
    return None


def require_admin(session: AdminSession | None) -> None:
    if not isinstance(session, AdminSession) or session.capability is not _CAPABILITY:
        raise PermissionError("Administrator sign-in is required.")
    age = time.monotonic() - session.issued_at
    if age < 0 or age >= SESSION_SECONDS:
        raise PermissionError("Administrator session has expired. Sign in again.")
