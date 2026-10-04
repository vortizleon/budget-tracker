"""Adding a transaction by hand: validation and automatic categorization.

The tests share one throwaway database, so every test uses its own unique names.
"""
import uuid

import pytest


def uid():
    return uuid.uuid4().hex[:8].upper()


def make_category(client, name=None):
    r = client.post("/api/categories", json={"name": name or f"Cat-{uid()}", "category_type": "expense"})
    assert r.status_code == 201, r.text
    return r.json()


def make_card(client, **extra):
    r = client.post("/api/cards", json={"name": f"Card-{uid()}", "card_type": "credit", **extra})
    assert r.status_code == 201, r.text
    return r.json()


def add_rule(client, category_id, value, match_type="contains"):
    r = client.post("/api/categorization-rules", json={"match_type": match_type, "value": value, "category_id": category_id})
    assert r.status_code == 201, r.text


def new_tx(client, **overrides):
    body = {"date": "2026-10-01", "amount": "12500.50", "currency": "CRC",
            "commerce_name": f"Shop-{uid()}", "transaction_type": "purchase"}
    body.update(overrides)
    return client.post("/api/transactions", json=body)


def test_manual_transaction_is_saved_and_listed(client):
    cat, card = make_category(client), make_card(client)
    r = new_tx(client, commerce_name="Soda Tapia", card_id=card["id"], category_id=cat["id"], notes="almuerzo")
    assert r.status_code == 201, r.text
    tx = r.json()
    assert (tx["commerce_name"], tx["currency"], tx["transaction_type"]) == ("Soda Tapia", "CRC", "purchase")
    assert tx["card_id"] == card["id"] and tx["category_id"] == cat["id"] and tx["notes"] == "almuerzo"
    listed = client.get("/api/transactions", params={"limit": 500}).json()["transactions"]
    assert tx["id"] in [t["id"] for t in listed]


def test_payment_type_and_usd_are_accepted(client):
    r = new_tx(client, transaction_type="payment", currency="USD", amount="40")
    assert r.status_code == 201
    assert (r.json()["transaction_type"], r.json()["currency"]) == ("payment", "USD")


def test_category_is_picked_by_a_matching_rule(client):
    token = uid()
    cat = make_category(client)
    add_rule(client, cat["id"], f"MERCADO{token}")
    tx = new_tx(client, commerce_name=f"Auto mercado{token.lower()} Escazu").json()   # case-insensitive "contains"
    assert tx["category_id"] == cat["id"]


def test_card_default_category_is_used_when_no_rule_matches(client):
    default_cat = make_category(client)
    card = make_card(client, default_category_id=default_cat["id"])
    assert new_tx(client, card_id=card["id"]).json()["category_id"] == default_cat["id"]


def test_rule_beats_card_default(client):
    token = uid()
    rule_cat, default_cat = make_category(client), make_category(client)
    add_rule(client, rule_cat["id"], f"UBER{token}", match_type="starts_with")
    card = make_card(client, default_category_id=default_cat["id"])
    tx = new_tx(client, commerce_name=f"Uber{token} Trip", card_id=card["id"]).json()
    assert tx["category_id"] == rule_cat["id"]


def test_explicit_category_beats_rule_and_default(client):
    token = uid()
    rule_cat, picked = make_category(client), make_category(client)
    add_rule(client, rule_cat["id"], f"NETFLIX{token}")
    tx = new_tx(client, commerce_name=f"Netflix{token}", category_id=picked["id"]).json()
    assert tx["category_id"] == picked["id"]


def test_no_rule_and_no_card_default_leaves_it_uncategorized(client):
    assert new_tx(client).json()["category_id"] is None


@pytest.mark.parametrize("override, status, message", [
    ({"amount": "0"}, 400, "Amount must be greater than 0"),
    ({"amount": "-5"}, 400, "Amount must be greater than 0"),
    ({"currency": "EUR"}, 400, "Currency must be CRC or USD"),
    ({"transaction_type": "refund"}, 400, "Type must be purchase or payment"),
    ({"card_id": 999999}, 404, "Card not found"),
    ({"category_id": 999999}, 404, "Category not found"),
])
def test_invalid_input_is_rejected_with_a_clear_message(client, override, status, message):
    r = new_tx(client, **override)
    assert r.status_code == status
    assert r.json()["detail"] == message


def test_a_manual_transaction_can_be_deleted(client):
    tx = new_tx(client).json()
    assert client.delete(f"/api/transactions/{tx['id']}").status_code == 204
    assert client.get(f"/api/transactions/{tx['id']}").status_code == 404
