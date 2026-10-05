"""CORS is local-only, one Gmail sync at a time, colors are validated, card spending takes dates."""
from backend import api


def _acao(client, origin):
    r = client.get("/api/categories", headers={"Origin": origin})
    return r.headers.get("access-control-allow-origin")


def test_cors_allows_local_origins(client):
    assert _acao(client, "http://localhost:8000") == "http://localhost:8000"
    assert _acao(client, "http://127.0.0.1:8000") == "http://127.0.0.1:8000"


def test_cors_blocks_other_sites(client):
    assert _acao(client, "https://evil.example") is None
    assert _acao(client, "http://localhost.evil.example") is None


def test_second_sync_is_rejected_while_one_runs(client):
    assert api._sync_lock.acquire(blocking=False)
    try:
        r = client.post("/api/sync/trigger", json={"days_back": 1})
        assert r.status_code == 409
    finally:
        api._sync_lock.release()


def test_card_and_category_colors_must_be_hex(client):
    bad = client.post("/api/categories", json={"name": "X", "color": "red;background:url(x)"})
    assert bad.status_code == 422
    bad = client.post("/api/cards", json={"name": "C", "color": "\"><script>"})
    assert bad.status_code == 422


def test_spending_by_card_takes_a_date_range(client):
    client.post("/api/cards", json={"name": "C", "color": "#112233"})
    r = client.get("/api/analytics/spending-by-card", params={"start_date": "2026-10-01", "end_date": "2026-10-31"})
    assert r.status_code == 200
    rows = r.json()
    assert rows and all(set(row) == {"card_id", "card_name", "card_color", "spent_crc", "spent_usd"} for row in rows)
