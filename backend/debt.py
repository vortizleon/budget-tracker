"""What the user's credit-card debt costs, computed from imported statements.

Statements are the bank's own record, so interest, insurance and rates come
from them rather than being estimated. USD amounts are converted to CRC with
the budget settings' exchange rate so totals can be compared and added.
"""
from collections import Counter, defaultdict
from datetime import date, timedelta
from functools import lru_cache
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from . import budgets, models, schemas, statement_parser

HISTORY_MONTHS = 12
ZERO = Decimal(0)


def _d(value) -> Decimal:
    return Decimal(value) if value is not None else ZERO


def _crc(crc, usd, rate: Decimal) -> Decimal:
    return _d(crc) + _d(usd) * rate


REWARDS_PREFIX = "Redención de puntos"   # points redeemed for a statement credit
INSURANCE_PREFIX = "SEGURO"                # billed on the cut day, listed on the statement in colones


def _sum_since(db: Session, card_id: int, kind: str, currency: str, after: date, today: date) -> Decimal:
    """Total of a card's purchases/payments dated after the statement cut (up to today).
    Points redemptions are credits the bank applies on a later statement - they are not
    counted as payments, so "pay in full" matches the bank's figure."""
    query = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.card_id == card_id,
        models.Transaction.transaction_type == kind,
        models.Transaction.currency == currency,
        models.Transaction.date > after,
        models.Transaction.date <= today,
    )
    if kind == "payment":
        query = query.filter(~models.Transaction.commerce_name.like(f"{REWARDS_PREFIX}%"))
    return _d(query.scalar())


def _rewards_since(db: Session, card_id: int, currency: str, after: date, today: date) -> Decimal:
    total = db.query(func.sum(models.Transaction.amount)).filter(
        models.Transaction.card_id == card_id,
        models.Transaction.transaction_type == "payment",
        models.Transaction.currency == currency,
        models.Transaction.date > after,
        models.Transaction.date <= today,
        models.Transaction.commerce_name.like(f"{REWARDS_PREFIX}%"),
    ).scalar()
    return _d(total)


@lru_cache(maxsize=16)
def _statement_purchase_lines(raw_text: str) -> Dict[str, Counter]:
    """{account last 4: Counter of (currency, amount)} for every purchase on the statement PDF."""
    try:
        parsed = statement_parser.parse_text(raw_text)
    except statement_parser.StatementError:
        return {}
    return {p.account_last4: Counter(p.purchase_lines) for p in parsed}


def _cut_day_purchases_after_statement(db: Session, st: models.Statement) -> Dict[str, Decimal]:
    """Purchases dated ON the cut day that the statement doesn't list: bought after the
    bank's cut-off, so they belong to the next statement and count as owed now.
    Matched against the statement's own purchase lines by currency and amount."""
    totals = {"CRC": ZERO, "USD": ZERO}
    if st.card_id is None or st.cut_date is None or not st.raw_text:
        return totals
    listed = Counter(_statement_purchase_lines(st.raw_text).get(st.account_last4, Counter()))
    rows = db.query(models.Transaction).filter(
        models.Transaction.card_id == st.card_id,
        models.Transaction.transaction_type == "purchase",
        models.Transaction.date == st.cut_date,
    ).order_by(models.Transaction.id).all()
    for t in rows:
        if (t.commerce_name or "").upper().startswith(INSURANCE_PREFIX):
            continue
        key = (t.currency, _d(t.amount))
        if listed[key] > 0:
            listed[key] -= 1          # this one is on the statement
        elif t.currency in totals:
            totals[t.currency] += _d(t.amount)
    return totals


def latest_statements(db: Session) -> List[models.Statement]:
    """The newest statement of each card account."""
    latest = {}
    for row in db.query(models.Statement).order_by(models.Statement.period).all():
        latest[(row.bank, row.account_last4)] = row
    return list(latest.values())


def position_for(db: Session, st: models.Statement, today: date) -> schemas.CardPosition:
    """Where a card stands now: its latest statement, minus the payments made
    since it was cut, plus the purchases since. Payments are in the currency of
    the balance they pay (colones pay colones, dollars pay dollars)."""
    cut = st.cut_date or today
    pay = {"CRC": ZERO, "USD": ZERO}
    buy = {"CRC": ZERO, "USD": ZERO}
    rewards = {"CRC": ZERO, "USD": ZERO}
    if st.card_id is not None:
        late = _cut_day_purchases_after_statement(db, st)
        for cur in pay:
            pay[cur] = _sum_since(db, st.card_id, "payment", cur, cut, today)
            buy[cur] = _sum_since(db, st.card_id, "purchase", cur, cut, today) + late[cur]
            rewards[cur] = _rewards_since(db, st.card_id, cur, cut, today)

    def f(prefix, cur):
        return _d(getattr(st, f"{prefix}_{cur.lower()}"))

    vals = {}
    for cur in ("CRC", "USD"):
        c = cur.lower()
        vals[f"statement_balance_{c}"] = f("closing_balance", cur)
        vals[f"payments_since_{c}"] = pay[cur]
        vals[f"purchases_since_{c}"] = buy[cur]
        vals[f"rewards_since_{c}"] = rewards[cur]
        vals[f"balance_now_{c}"] = f("closing_balance", cur) - pay[cur] + buy[cur]
        vals[f"min_payment_{c}"] = f("min_payment", cur)
        vals[f"cash_payment_{c}"] = f("cash_payment", cur)
        vals[f"remaining_min_{c}"] = max(f("min_payment", cur) - pay[cur], ZERO)
        vals[f"remaining_cash_{c}"] = max(f("cash_payment", cur) - pay[cur], ZERO)

    if st.paid_on is not None or (vals["remaining_cash_crc"] == 0 and vals["remaining_cash_usd"] == 0):
        status = "paid"
    elif vals["remaining_min_crc"] == 0 and vals["remaining_min_usd"] == 0:
        status = "minimum_paid"
    else:
        status = "unpaid"

    return schemas.CardPosition(
        card_id=st.card_id or 0,
        card_name=st.card.name if st.card else f"••••{st.account_last4}",
        period=st.period, cut_date=st.cut_date, cash_due_date=st.cash_due_date,
        days_left=(st.cash_due_date - today).days if st.cash_due_date else None,
        status=status, paid_by_hand_on=st.paid_on, **vals,
    )


def get_positions(db: Session, today: Optional[date] = None) -> List[schemas.CardPosition]:
    today = today or date.today()
    return sorted(
        (position_for(db, st, today) for st in latest_statements(db)),
        key=lambda p: (p.days_left is None, p.days_left if p.days_left is not None else 0),
    )


def position_for_card(db: Session, card_id: int, today: Optional[date] = None) -> Optional[schemas.CardPosition]:
    today = today or date.today()
    for st in latest_statements(db):
        if st.card_id == card_id:
            return position_for(db, st, today)
    return None


# ---- payments the user reports ------------------------------------------------

MANUAL_PAYMENT_NAME = "Card payment (logged by hand)"


def _payment_response(t: models.Transaction) -> schemas.PaymentResponse:
    return schemas.PaymentResponse(
        id=t.id, card_id=t.card_id, card_name=t.card.name if t.card else None,
        date=t.date, amount=t.amount, currency=t.currency, notes=t.notes,
        logged_by_hand=t.gmail_message_id is None,
    )


def log_payment(db: Session, data: schemas.PaymentCreate) -> schemas.PaymentResponse:
    t = models.Transaction(
        date=data.date, amount=data.amount, currency=data.currency,
        commerce_name=MANUAL_PAYMENT_NAME, transaction_type="payment",
        card_id=data.card_id, notes=data.notes,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return _payment_response(t)


def list_payments(db: Session, card_id: Optional[int] = None, limit: int = 30) -> List[schemas.PaymentResponse]:
    query = db.query(models.Transaction).filter(models.Transaction.transaction_type == "payment",
                                                models.Transaction.card_id.isnot(None))
    if card_id is not None:
        query = query.filter(models.Transaction.card_id == card_id)
    rows = query.order_by(models.Transaction.date.desc(), models.Transaction.id.desc()).limit(limit).all()
    return [_payment_response(t) for t in rows]


def delete_payment(db: Session, payment_id: int) -> str:
    """"deleted", "not_found", or "not_manual" (bank-email payments aren't removed here)."""
    t = db.get(models.Transaction, payment_id)
    if t is None or t.transaction_type != "payment":
        return "not_found"
    if t.gmail_message_id is not None:
        return "not_manual"
    db.delete(t)
    db.commit()
    return "deleted"


def manual_payment_exists(db: Session, card_id: Optional[int], currency: str, amount, on: date) -> bool:
    """A hand-logged payment matching one that a bank email is about to add
    (same card, currency and amount, within 3 days) - so it isn't counted twice."""
    if card_id is None:
        return False
    on = on.date() if hasattr(on, "date") and callable(on.date) else on   # datetime -> date
    return db.query(models.Transaction.id).filter(
        models.Transaction.transaction_type == "payment",
        models.Transaction.gmail_message_id.is_(None),
        models.Transaction.card_id == card_id,
        models.Transaction.currency == currency,
        models.Transaction.amount == amount,
        models.Transaction.date >= on - timedelta(days=3),
        models.Transaction.date <= on + timedelta(days=3),
    ).first() is not None


def get_cost_of_debt(db: Session) -> schemas.CostOfDebt:
    settings = budgets.get_settings(db)
    rate = Decimal(settings.usd_to_crc_rate)

    rows = db.query(models.Statement).order_by(models.Statement.period).all()
    if not rows:
        return schemas.CostOfDebt(has_data=False, usd_to_crc_rate=rate)

    by_period: Dict[str, List[models.Statement]] = defaultdict(list)
    for st in rows:
        by_period[st.period].append(st)
    periods = sorted(by_period)

    history = []
    for period in periods[-HISTORY_MONTHS:]:
        sts = by_period[period]
        history.append(schemas.CostOfDebtMonth(
            period=period,
            interest_crc=sum((_crc(s.interest_crc, s.interest_usd, rate) for s in sts), ZERO),
            insurance_crc=sum((_crc(s.insurance_crc, s.insurance_usd, rate) for s in sts), ZERO),
        ))

    latest_period = periods[-1]
    latest = by_period[latest_period]
    today = date.today()
    positions = {st.id: position_for(db, st, today) for st in latest}

    cards = []
    total_debt = interest = insurance = minimum = ZERO
    statement_debt = paid_since = ZERO
    debt_crc = debt_usd = ZERO
    weighted_rate_num = ZERO
    projected_interest = ZERO
    future_installments = ZERO
    for st in latest:
        pos = positions[st.id]
        # What's owed now: the statement balance less payments since (never below zero).
        now_crc, now_usd = max(pos.balance_now_crc, ZERO), max(pos.balance_now_usd, ZERO)
        card_debt = now_crc + now_usd * rate
        card_interest = _crc(st.interest_crc, st.interest_usd, rate)
        total_debt += card_debt
        debt_crc += now_crc
        debt_usd += now_usd
        statement_debt += _crc(st.closing_balance_crc, st.closing_balance_usd, rate)
        paid_since += pos.payments_since_crc + pos.payments_since_usd * rate
        interest += card_interest
        insurance += _crc(st.insurance_crc, st.insurance_usd, rate)
        minimum += _crc(st.min_payment_crc, st.min_payment_usd, rate)
        weighted_rate_num += (
            now_crc * _d(st.apr_crc) + now_usd * rate * _d(st.apr_usd)
        )
        # A month of interest at today's balance (annual rate / 12) - it drops as you pay.
        projected_interest += (now_crc * _d(st.apr_crc) + now_usd * rate * _d(st.apr_usd)) / 100 / 12
        for fl in st.financing_lines:
            if fl.installments_total and fl.installment_number and fl.installment_amount:
                left = max(fl.installments_total - fl.installment_number, 0)
                future_installments += fl.installment_amount * left * (rate if fl.currency == "USD" else 1)
        cards.append(schemas.CostOfDebtCard(
            name=(st.card.name if st.card else f"••••{st.account_last4}"),
            debt_crc=card_debt,
            interest_crc=card_interest,
            apr_crc=st.apr_crc,
            apr_usd=st.apr_usd,
        ))
    cards.sort(key=lambda c: c.debt_crc, reverse=True)

    income = settings.expected_monthly_income
    monthly_cost = interest + insurance
    # Which currency's balance costs more per year (pay that one down first).
    apr_crc = max((_d(s.apr_crc) for s in latest), default=ZERO)
    apr_usd = max((_d(s.apr_usd) for s in latest), default=ZERO)

    return schemas.CostOfDebt(
        has_data=True,
        usd_to_crc_rate=rate,
        period=latest_period,
        statements_needing_review=sum(1 for s in latest if s.status != "ok"),
        total_debt_crc=total_debt,
        debt_crc=debt_crc,
        debt_usd=debt_usd,
        interest_crc=interest,
        insurance_crc=insurance,
        monthly_cost_crc=monthly_cost,
        yearly_cost_crc=monthly_cost * 12,
        minimum_payment_crc=minimum,
        interest_share_of_minimum=(min(interest / minimum, Decimal(1)) if minimum > 0 else None),
        average_rate=(weighted_rate_num / total_debt if total_debt > 0 else None),
        highest_rate_currency=("CRC" if apr_crc >= apr_usd else "USD") if (apr_crc or apr_usd) else None,
        apr_crc=apr_crc or None,
        apr_usd=apr_usd or None,
        monthly_income_crc=income,
        cost_share_of_income=(monthly_cost / income if income and income > 0 else None),
        projected_interest_crc=projected_interest,
        statement_debt_crc=statement_debt,
        paid_since_crc=paid_since,
        future_installments_crc=future_installments,
        cards=cards,
        history=history,
    )
