"""CORS is local-only and only one Gmail sync runs at a time."""
from fastapi.testclient import TestClient

from backend import api

client = TestClient(api.app)


def _acao(origin):
    r = client.get("/api/categories", headers={"Origin": origin})
    return r.headers.get("access-control-allow-origin")


def test_cors_allows_local_origins():
    assert _acao("http://localhost:8000") == "http://localhost:8000"
    assert _acao("http://127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_cors_blocks_other_sites():
    assert _acao("https://evil.example") is None
    assert _acao("http://localhost.evil.example") is None


def test_second_sync_is_rejected_while_one_runs():
    assert api._sync_lock.acquire(blocking=False)
    try:
        r = client.post("/api/sync/trigger", json={"days_back": 1})
        assert r.status_code == 409
    finally:
        api._sync_lock.release()
