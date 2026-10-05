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
