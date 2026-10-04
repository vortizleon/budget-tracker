"""Smoke tests: the app installs cleanly, starts, and serves every page.

These would have caught the missing `jinja2` dependency (a clean install could
not even import backend.api).
"""
import importlib

import pytest

MODULES = [
    "backend.api", "backend.manage", "backend.sync", "backend.init_db",
    "backend.analytics", "backend.forecast", "backend.payoff", "backend.budgets",
    "backend.migrate_schema", "backend.gmail_client", "backend.email_parser", "backend.crud",
]


@pytest.mark.parametrize("name", MODULES)
def test_module_imports(name):
    importlib.import_module(name)


def test_health(client):
    assert client.get("/health").json()["status"] == "healthy"


@pytest.mark.parametrize("view", ["", "budgets", "transactions", "analytics", "forecast", "categories", "cards", "settings"])
def test_every_page_is_served(client, view):
    r = client.get(f"/{view}")
    assert r.status_code == 200
    assert "<html" in r.text.lower()


def test_cards_api_starts_empty(client):
    r = client.get("/api/cards")
    assert r.status_code == 200
    assert r.json() == []
