"""Statement PDF import: parsing, cross-checks, storage, and graceful failure."""
from decimal import Decimal

import pytest

from backend import statement_parser as sp
from statement_fixtures import make_pdf, statement_text


def test_parses_one_account():
    [st] = sp.parse_text(statement_text())
    assert (st.bank, st.account_last4, st.period) == ("BAC", "1111", "2026-09")
    assert st.card_last4s == ["1112"]
    assert str(st.cut_date) == "2026-09-18" and str(st.cash_due_date) == "2026-10-03"
    crc, usd = st.amounts["CRC"], st.amounts["USD"]
    assert crc["closing_balance"] == Decimal("3500.00") and usd["closing_balance"] == Decimal("41.00")
    assert crc["min_payment"] == Decimal("1000.00") and crc["cash_payment"] == Decimal("3300.00")
    assert crc["interest_charged"] == Decimal("200.00")      # reversal of an earlier cycle is not counted
    assert crc["voluntary_total"] == Decimal("120.00")
    assert crc["apr"] == Decimal("35.88") and usd["apr"] == Decimal("29.64")
    assert st.points_assigned == Decimal("1234.50")
    [fl] = st.financing_lines
    assert (fl.installment_number, fl.installments_total, fl.installment_amount) == (3, 6, Decimal("50.00"))
    assert st.status == "ok" and st.warnings == []


def test_parses_two_accounts_in_one_pdf():
    sts = sp.parse_text(statement_text(sections=2))
    assert [s.account_last4 for s in sts] == ["1111", "2221"]
    assert all(s.brand == "AMERICAN EXPRESS" for s in sts)


def test_purchase_total_mismatch_is_flagged_not_trusted():
    [st] = sp.parse_text(statement_text(purchases_crc="9,999.00"))
    assert st.status == "needs_review"
    assert any("purchase lines add up" in w for w in st.warnings)


def test_balance_that_doesnt_add_up_is_flagged():
    [st] = sp.parse_text(statement_text(closing_crc="1.00"))
    assert st.status == "needs_review"
    assert any("closing balance" in w for w in st.warnings)


def test_reordered_and_renamed_layout_is_flagged_rather_than_misread():
    text = statement_text().replace("Saldo al corte", "Balance final").replace("Fecha de corte", "Cierre")
    [st] = sp.parse_text(text)
    assert st.status == "needs_review"
    assert any("closing balance" in w for w in st.warnings) and any("cut date" in w for w in st.warnings)


def test_not_a_statement():
    with pytest.raises(sp.StatementError):
        sp.parse_text("hello world, this is a grocery list " * 10)
    with pytest.raises(sp.StatementError):
        sp.extract_text(b"not a pdf at all")


def test_upload_stores_and_links_card(client):
    card = client.post("/api/cards", json={"name": "Test Amex", "last_four": "1112", "color": "#112233"}).json()
    r = client.post("/api/statements/upload", files={"file": ("s.pdf", make_pdf(statement_text()), "application/pdf")})
    assert r.status_code == 200, r.text
    [row] = r.json()
    assert row["card_id"] == card["id"] and row["card_name"] == "Test Amex"
    assert row["status"] == "ok" and row["closing_balance_crc"] == "3500.00"
    assert row["payments_crc"] == "500.00"          # stored positive
    assert row["financing_lines"][0]["installments_total"] == 6

    # Re-uploading the same month updates it instead of duplicating.
    client.post("/api/statements/upload", files={"file": ("s.pdf", make_pdf(statement_text()), "application/pdf")})
    assert len(client.get("/api/statements").json()) == 1


def test_upload_without_matching_card_warns_then_reparse_links_it(client):
    pdf = make_pdf(statement_text())
    [row] = client.post("/api/statements/upload", files={"file": ("s.pdf", pdf, "application/pdf")}).json()
    assert row["card_id"] is None and row["status"] == "needs_review"
    assert any("No card in the app matches" in w for w in row["warnings"])

    client.post("/api/cards", json={"name": "Late Card", "last_four": "1112", "color": "#112233"})
    [again] = client.post("/api/statements/reparse").json()
    assert again["card_name"] == "Late Card" and again["status"] == "ok"


def test_upload_rejects_garbage(client):
    r = client.post("/api/statements/upload", files={"file": ("x.pdf", b"nope", "application/pdf")})
    assert r.status_code == 422


def test_cost_of_debt_empty_then_from_statement(client):
    assert client.get("/api/analytics/cost-of-debt").json()["has_data"] is False

    client.post("/api/statements/upload", files={"file": ("s.pdf", make_pdf(statement_text()), "application/pdf")})
    d = client.get("/api/analytics/cost-of-debt").json()
    rate = float(d["usd_to_crc_rate"])
    assert d["has_data"] and d["period"] == "2026-09"
    # fixture: closing 3,500 CRC + 41 USD; interest 200 CRC + 1 USD; insurance 120 CRC
    assert float(d["total_debt_crc"]) == pytest.approx(3500 + 41 * rate)
    assert float(d["interest_crc"]) == pytest.approx(200 + 1 * rate)
    assert float(d["monthly_cost_crc"]) == pytest.approx(200 + rate + 120)
    assert float(d["yearly_cost_crc"]) == pytest.approx(12 * float(d["monthly_cost_crc"]))
    assert d["highest_rate_currency"] == "CRC"            # 35.88% vs 29.64%
    # 3 of 6 installments of $50 are still to come
    assert float(d["future_installments_crc"]) == pytest.approx(3 * 50 * rate)
    assert len(d["history"]) == 1


def test_due_soon_and_mark_paid(client):
    from datetime import date, timedelta
    from backend import statements
    from backend.database import SessionLocal

    client.post("/api/cards", json={"name": "Test Amex", "last_four": "1112", "color": "#112233"})
    [row] = client.post("/api/statements/upload", files={"file": ("s.pdf", make_pdf(statement_text()), "application/pdf")}).json()
    due = date(2026, 10, 3)                                   # the fixture's pay-in-full date
    db = SessionLocal()
    try:
        assert statements.due_soon(db, today=due - timedelta(days=10)) == []          # not yet
        [d] = statements.due_soon(db, today=due - timedelta(days=2))
        assert d["days_left"] == 2 and d["card_name"] == "Test Amex"
        [late] = statements.due_soon(db, today=due + timedelta(days=3))                # overdue stays until paid
        assert late["days_left"] == -3
    finally:
        db.close()

    paid = client.post(f"/api/statements/{row['id']}/paid", json={"paid": True}).json()
    assert paid["paid_on"] is not None
    db = SessionLocal()
    try:
        assert statements.due_soon(db, today=due) == []
    finally:
        db.close()
    assert client.post(f"/api/statements/{row['id']}/paid", json={"paid": False}).json()["paid_on"] is None
    assert client.post("/api/statements/9999/paid", json={"paid": True}).status_code == 404


def test_payoff_plan_offers_latest_statement_numbers(client):
    card = client.post("/api/cards", json={"name": "Test Amex", "last_four": "1112", "color": "#112233"}).json()
    assert client.get(f"/api/cards/{card['id']}/payoff-plan").json()["statement"] is None
    client.post("/api/statements/upload", files={"file": ("s.pdf", make_pdf(statement_text()), "application/pdf")})
    snap = client.get(f"/api/cards/{card['id']}/payoff-plan").json()["statement"]
    assert snap["period"] == "2026-09" and snap["cut_date"] == "2026-09-18"
    assert snap["balance_crc"] == "3500.00" and snap["balance_usd"] == "41.00"
    assert snap["annual_rate_crc"] == "35.8800" and snap["min_payment_crc"] == "1000.00"


def _upload_with_card(client):
    card = client.post("/api/cards", json={"name": "Test Amex", "last_four": "1112", "color": "#112233"}).json()
    client.post("/api/statements/upload", files={"file": ("s.pdf", make_pdf(statement_text()), "application/pdf")})
    return card


def test_logged_payments_update_position_status_and_debt(client):
    card = _upload_with_card(client)
    [pos] = client.get("/api/debt/positions").json()
    # fixture: closing 3,500 CRC / 41 USD, minimum 1,000 / 6, pay-in-full 3,300 / 40
    assert pos["status"] == "unpaid" and float(pos["balance_now_crc"]) == 3500
    debt_before = float(client.get("/api/analytics/cost-of-debt").json()["total_debt_crc"])

    # a payment dated before the statement was cut is already inside its balance
    client.post("/api/payments", json={"card_id": card["id"], "amount": "999", "currency": "CRC", "date": "2026-09-10"})
    assert float(client.get("/api/debt/positions").json()[0]["payments_since_crc"]) == 0

    client.post("/api/payments", json={"card_id": card["id"], "amount": "1000", "currency": "CRC", "date": "2026-09-25"})
    client.post("/api/payments", json={"card_id": card["id"], "amount": "6", "currency": "USD", "date": "2026-09-25"})
    pos = client.get("/api/debt/positions").json()[0]
    assert pos["status"] == "minimum_paid"
    assert float(pos["balance_now_crc"]) == 2500 and float(pos["balance_now_usd"]) == 35
    assert float(pos["remaining_cash_crc"]) == 2300 and float(pos["remaining_min_crc"]) == 0

    d = client.get("/api/analytics/cost-of-debt").json()
    assert float(d["total_debt_crc"]) < debt_before
    # a month of interest at today's balance: 2,500 CRC @35.88% + 35 USD @29.64%, /12
    assert float(d["projected_interest_crc"]) == pytest.approx(
        (2500 * 0.3588 + 35 * float(d["usd_to_crc_rate"]) * 0.2964) / 12, rel=1e-4)
    assert float(d["paid_since_crc"]) > 0 and float(d["statement_debt_crc"]) == pytest.approx(debt_before)

    client.post("/api/payments", json={"card_id": card["id"], "amount": "2300", "currency": "CRC", "date": "2026-10-01"})
    client.post("/api/payments", json={"card_id": card["id"], "amount": "34", "currency": "USD", "date": "2026-10-01"})
    assert client.get("/api/debt/positions").json()[0]["status"] == "paid"

    # the payoff planner starts from the balance after those payments
    snap = client.get(f"/api/cards/{card['id']}/payoff-plan").json()["statement"]
    assert float(snap["balance_crc"]) == 200 and snap["as_of"] != snap["cut_date"]


def test_payment_validation_and_delete(client):
    card = _upload_with_card(client)
    bad = client.post("/api/payments", json={"card_id": card["id"], "amount": "0", "currency": "CRC", "date": "2026-10-01"})
    assert bad.status_code == 422
    assert client.post("/api/payments", json={"card_id": card["id"], "amount": "5", "currency": "EUR", "date": "2026-10-01"}).status_code == 400
    assert client.post("/api/payments", json={"card_id": 9999, "amount": "5", "currency": "CRC", "date": "2026-10-01"}).status_code == 404

    made = client.post("/api/payments", json={"card_id": card["id"], "amount": "50", "currency": "CRC", "date": "2026-10-01"}).json()
    assert made["logged_by_hand"] is True and made["card_name"] == "Test Amex"
    assert [p["id"] for p in client.get("/api/payments").json()] == [made["id"]]
    assert client.delete(f"/api/payments/{made['id']}").status_code == 200
    assert client.get("/api/payments").json() == []
    assert client.delete(f"/api/payments/{made['id']}").status_code == 404


def test_bank_email_payment_is_not_double_counted(client):
    from datetime import date
    from decimal import Decimal
    from backend import debt
    from backend.database import SessionLocal
    card = _upload_with_card(client)
    client.post("/api/payments", json={"card_id": card["id"], "amount": "1000", "currency": "CRC", "date": "2026-09-25"})
    db = SessionLocal()
    try:
        assert debt.manual_payment_exists(db, card["id"], "CRC", Decimal("1000"), date(2026, 9, 27))      # within 3 days
        assert not debt.manual_payment_exists(db, card["id"], "CRC", Decimal("1000"), date(2026, 10, 5))  # too far
        assert not debt.manual_payment_exists(db, card["id"], "CRC", Decimal("1001"), date(2026, 9, 25))
        assert not debt.manual_payment_exists(db, card["id"], "USD", Decimal("1000"), date(2026, 9, 25))
    finally:
        db.close()
