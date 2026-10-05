"""Save parsed statements to the database (upload and re-parse)."""
import json
from datetime import date
from decimal import Decimal
from typing import List

from sqlalchemy.orm import Session

from . import models, statement_parser as sp

# amounts key in the parser -> column prefix on Statement
_AMOUNT_COLUMNS = {
    "previous_balance": "previous_balance", "purchases_total": "purchases",
    "payments_total": "payments", "interest_charged": "interest",
    "voluntary_total": "insurance", "other_charges_total": "other_charges",
    "min_payment": "min_payment", "cash_payment": "cash_payment",
    "closing_balance": "closing_balance", "apr": "apr",
}


def find_card(db: Session, parsed: sp.ParsedStatement):
    """The app's card for this statement: matched by the last 4 digits of the
    card number (as in the movements) or of the account number."""
    candidates = set(parsed.card_last4s) | {parsed.account_last4}
    cards = db.query(models.Card).filter(models.Card.last_four.in_(candidates)).all()
    # Prefer a match on a real card number over the account number.
    for card in cards:
        if card.last_four in parsed.card_last4s:
            return card
    return cards[0] if cards else None


def store(db: Session, parsed: sp.ParsedStatement, raw_text: str) -> models.Statement:
    """Insert, or update the statement already stored for this account and month."""
    warnings = list(parsed.warnings)
    card = find_card(db, parsed)
    if card is None:
        warnings.append(
            f"No card in the app matches ••••{'/'.join(parsed.card_last4s) or parsed.account_last4} - "
            "set the card's last 4 digits in Cards so this statement links to it."
        )

    row = (
        db.query(models.Statement)
        .filter(models.Statement.bank == parsed.bank,
                models.Statement.account_last4 == parsed.account_last4,
                models.Statement.period == parsed.period)
        .first()
    )
    if row is None:
        row = models.Statement(bank=parsed.bank, account_last4=parsed.account_last4, period=parsed.period)
        db.add(row)

    row.card_id = card.id if card else None
    row.brand, row.loyalty_plan = parsed.brand, parsed.loyalty_plan
    row.card_last4s = ",".join(parsed.card_last4s)
    row.cut_date, row.min_due_date, row.cash_due_date = parsed.cut_date, parsed.min_due_date, parsed.cash_due_date
    row.limit_currency, row.credit_limit, row.available = parsed.limit_currency, parsed.credit_limit, parsed.available
    row.points_assigned = parsed.points_assigned
    for key, prefix in _AMOUNT_COLUMNS.items():
        for cur in ("CRC", "USD"):
            value = parsed.amounts[cur].get(key)
            if value is not None and key == "payments_total":
                value = abs(value)
            setattr(row, f"{prefix}_{cur.lower()}", value)
    row.status = "needs_review" if warnings else "ok"
    row.warnings_json = json.dumps(warnings)
    row.parser_version = sp.PARSER_VERSION
    row.raw_text = raw_text

    row.financing_lines.clear()
    for fl in parsed.financing_lines:
        row.financing_lines.append(models.StatementFinancingLine(
            merchant=fl.merchant, currency=fl.currency, total_amount=fl.total_amount,
            term_months=fl.term_months, annual_rate=fl.annual_rate, start_date=fl.start_date,
            end_date=fl.end_date, installment_amount=fl.installment_amount,
            installment_number=fl.installment_number, installments_total=fl.installments_total,
        ))
    return row


def import_pdf(db: Session, pdf_bytes: bytes) -> List[models.Statement]:
    raw_text, parsed = sp.parse_pdf(pdf_bytes)
    rows = [store(db, p, raw_text) for p in parsed]
    db.commit()
    return rows


def reparse_all(db: Session) -> List[models.Statement]:
    """Re-run the current parser over every stored statement's text (after a parser fix)."""
    rows = []
    for raw_text in {r.raw_text for r in db.query(models.Statement).all() if r.raw_text}:
        try:
            parsed = sp.parse_text(raw_text)
        except sp.StatementError:
            continue
        rows.extend(store(db, p, raw_text) for p in parsed)
    db.commit()
    return rows


DUE_WARNING_DAYS = 7


def due_soon(db: Session, today: date = None) -> List[dict]:
    """Latest statement per account whose pay-in-full date is within a week
    (or already passed) and which hasn't been marked paid, soonest first."""
    today = today or date.today()
    latest = {}
    for row in db.query(models.Statement).order_by(models.Statement.period).all():
        latest[(row.bank, row.account_last4)] = row   # later periods overwrite earlier ones
    due = []
    for row in latest.values():
        if row.paid_on is not None or row.cash_due_date is None:
            continue
        days_left = (row.cash_due_date - today).days
        if days_left > DUE_WARNING_DAYS:
            continue
        due.append({
            "id": row.id,
            "card_name": row.card.name if row.card else f"••••{row.account_last4}",
            "account_last4": row.account_last4,
            "period": row.period,
            "cash_due_date": row.cash_due_date,
            "days_left": days_left,
            "min_payment_crc": row.min_payment_crc, "min_payment_usd": row.min_payment_usd,
            "cash_payment_crc": row.cash_payment_crc, "cash_payment_usd": row.cash_payment_usd,
        })
    return sorted(due, key=lambda d: d["days_left"])


def set_paid(db: Session, statement_id: int, paid: bool):
    row = db.get(models.Statement, statement_id)
    if row is None:
        return None
    row.paid_on = date.today() if paid else None
    db.commit()
    return row
