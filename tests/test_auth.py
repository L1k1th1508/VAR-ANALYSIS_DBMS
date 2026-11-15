import time
from uuid import uuid4

import pytest
from argon2 import PasswordHasher

from var_analytics import auth


def test_authentication_and_service_guard(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", PasswordHasher().hash("test-only password"))
    assert auth.authenticate("wrong password") is None
    session = auth.authenticate("test-only password")
    auth.require_admin(session)
    with pytest.raises(PermissionError):
        auth.require_admin(None)
    with pytest.raises(PermissionError):
        auth.require_admin(auth.AdminSession(uuid4(), time.monotonic(), object()))


def test_expired_session(monkeypatch):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", PasswordHasher().hash("test-only password"))
    session = auth.authenticate("test-only password")
    monkeypatch.setattr(auth.time, "monotonic", lambda: session.issued_at + auth.SESSION_SECONDS)
    with pytest.raises(PermissionError):
        auth.require_admin(session)


@pytest.mark.parametrize("encoded", ["", "bad hash"])
def test_unconfigured_or_bad_hash_fails_closed(monkeypatch, encoded):
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", encoded)
    assert auth.authenticate("anything") is None
