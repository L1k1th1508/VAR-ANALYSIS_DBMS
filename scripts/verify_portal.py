"""Verify the local portal; create and remove one temporary software-test note.

Football facts are queried read-only. The temporary note contains no football claims.
"""

from pathlib import Path
from uuid import uuid4

import httpx

root = Path(__file__).resolve().parents[1]
base = "http://127.0.0.1:3000"
with httpx.Client(base_url=base, timeout=40, headers={"Origin": base}) as c:
    assert c.get("/api/notes").status_code == 401
    assert c.post("/api/session", json={"password": "deliberately-invalid"}).status_code == 401
    login = c.post(
        "/api/session", json={"password": (root / ".cache/initial-admin-password.txt").read_text()}
    )
    assert login.status_code == 200, login.text
    assert "HttpOnly" in login.headers["set-cookie"]
    assert c.get("/api/session").json()["authenticated"]
    assert (
        c.post("/api/notes", json={"title": "", "body": "x", "sourceUrl": "https://example.org"}).status_code
        == 400
    )
    body = {
        "title": "Temporary software verification " + uuid4().hex,
        "body": "Temporary application test annotation; not a football observation.",
        "sourceUrl": "https://github.com/L1k1th1508/VAR-ANALYSIS_DBMS",
    }
    created = c.post("/api/notes", json=body)
    assert created.status_code == 201, created.text
    id = created.json()["id"]
    try:
        note = next(n for n in c.get("/api/notes").json() if n["_id"] == id)
        assert (
            c.put(
                "/api/notes",
                json={
                    **body,
                    "id": id,
                    "revision": note["revision"],
                    "body": "Updated temporary software verification.",
                },
            ).status_code
            == 200
        )
        assert c.put("/api/notes", json={**body, "id": id, "revision": note["revision"]}).status_code == 409
        assert (
            c.request("DELETE", "/api/notes", json={"id": id, "revision": note["revision"]}).status_code
            == 409
        )
    finally:
        rows = c.get("/api/notes").json()
        current = next(n for n in rows if n["_id"] == id)
        assert (
            c.request("DELETE", "/api/notes", json={"id": id, "revision": current["revision"]}).status_code
            == 200
        )
    assert c.post("/api/notes", headers={"Origin": "https://example.org"}, json=body).status_code == 403
    assert c.delete("/api/session").status_code == 200
    assert c.get("/api/notes").status_code == 401
print(
    "PASS: login, HttpOnly cookie, authorization, validation, Mongo CRUD, stale edit/delete, origin guard and logout"
)
