"""Credit card payoff plans: stored balances/payments per card, plus the
card's recent spending rate to project how new purchases slow the payoff.
The month-by-month projection runs in the frontend so "what if I pay X"
updates live while typing."""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from . import models, schemas

AVG_WINDOW_DAYS = 90
DAYS_PER_MONTH = Decimal("30.44")


def get_avg_monthly_spend(db: Session, card_id: int) -> tuple[Decimal, Decimal, int]:
    """(crc, usd, days) - the card's average monthly purchases over the last
    90 days, or over however much history exists if it's less than that
    (e.g. right after a "start from 0" resync), so a short history isn't
    diluted into a misleadingly low average. Tasa Cero installments are
    left out - their future charges are known exactly, see
    get_scheduled_installments()."""
    today = date.today()
    oldest = db.query(func.min(models.Transaction.date)).scalar()
    start = today - timedelta(days=AVG_WINDOW_DAYS - 1)
    if oldest and oldest > start:
        start = oldest
    days = max((today - start).days + 1, 1)

    rows = db.query(
        models.Transaction.currency, func.sum(models.Transaction.amount)
    ).filter(
        models.Transaction.card_id == card_id,
        models.Transaction.transaction_type == "purchase",
        models.Transaction.installment_plan_id.is_(None),
        models.Transaction.date >= start,
        models.Transaction.date <= today,
    ).group_by(models.Transaction.currency).all()
    totals = {currency: Decimal(total or 0) for currency, total in rows}

    def monthly(currency: str) -> Decimal:
        value = totals.get(currency, Decimal(0)) * DAYS_PER_MONTH / days
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return monthly("CRC"), monthly("USD"), days


def get_scheduled_installments(db: Session, card_id: int, as_of: date) -> dict[str, list[Decimal]]:
    """Tasa Cero charges still to come on the card after `as_of` (the
    balance entered already includes earlier ones), as per-currency lists
    indexed by month - index 0 = as_of's month, matching the projection."""
    rows = db.query(models.Transaction).filter(
        models.Transaction.card_id == card_id,
        models.Transaction.installment_plan_id.isnot(None),
        models.Transaction.date > as_of,
    ).all()
    schedule: dict[str, list[Decimal]] = {"CRC": [], "USD": []}
    for t in rows:
        months = schedule[t.currency]
        index = _months_between(as_of.replace(day=1), t.date.replace(day=1))
        while len(months) <= index:
            months.append(Decimal(0))
        months[index] += Decimal(t.amount)
    return schedule


def get_plan(db: Session, card_id: int, as_of: date = None) -> schemas.CardPayoffPlanResponse:
    plan = db.query(models.CardPayoffPlan).filter(models.CardPayoffPlan.card_id == card_id).first()
    crc, usd, days = get_avg_monthly_spend(db, card_id)
    installments = get_scheduled_installments(db, card_id, as_of or (plan.balance_as_of if plan else date.today()))
    latest = (
        db.query(models.Statement)
        .filter(models.Statement.card_id == card_id)
        .order_by(models.Statement.period.desc())
        .first()
    )
    snapshot = None
    if latest:
        snapshot = schemas.StatementSnapshot(
            period=latest.period, cut_date=latest.cut_date,
            balance_crc=latest.closing_balance_crc, balance_usd=latest.closing_balance_usd,
            annual_rate_crc=latest.apr_crc, annual_rate_usd=latest.apr_usd,
            min_payment_crc=latest.min_payment_crc, min_payment_usd=latest.min_payment_usd,
        )
    return schemas.CardPayoffPlanResponse(
        statement=snapshot,
        card_id=card_id,
        plan=schemas.CardPayoffPlanUpdate.model_validate(plan, from_attributes=True) if plan else None,
        avg_monthly_spend_crc=crc,
        avg_monthly_spend_usd=usd,
        avg_based_on_days=days,
        scheduled_installments_crc=installments["CRC"],
        scheduled_installments_usd=installments["USD"],
    )


def save_plan(db: Session, card_id: int, data: schemas.CardPayoffPlanUpdate) -> schemas.CardPayoffPlanResponse:
    plan = db.query(models.CardPayoffPlan).filter(models.CardPayoffPlan.card_id == card_id).first()
    if plan is None:
        plan = models.CardPayoffPlan(card_id=card_id)
        db.add(plan)
    for field, value in data.model_dump().items():
        setattr(plan, field, value)
    db.commit()
    return get_plan(db, card_id)


def delete_plan(db: Session, card_id: int) -> bool:
    plan = db.query(models.CardPayoffPlan).filter(models.CardPayoffPlan.card_id == card_id).first()
    if plan is None:
        return False
    db.delete(plan)
    db.commit()
    return True


# ============================================================================
# Projection (mirrors simulatePayoff() in app.js) - used by budgets.py to know
# how much debt payment falls in a given month
# ============================================================================

MAX_MONTHS = 600


def project_payments(balance, annual_rate, payment, spend, installments=()) -> tuple[list[Decimal], bool]:
    """(amount paid in each month, whether the balance ever clears).
    Month 1 = the plan's as-of month; installments[i] is extra Tasa Cero
    charges in month i+1. If it clears, the list ends at the payoff month
    (the last payment may be partial); if not, the full payment just
    continues indefinitely past the end of the list."""
    r = Decimal(annual_rate) / 100 / 12
    balance, payment, spend = Decimal(balance), Decimal(payment), Decimal(spend)
    paid_by_month = []
    while len(paid_by_month) < MAX_MONTHS:
        month = len(paid_by_month)
        extra = installments[month] if month < len(installments) else Decimal(0)
        owed = balance * (1 + r) + spend + extra
        paid = min(payment, owed)
        new_balance = owed - paid
        paid_by_month.append(paid)
        if new_balance <= Decimal("0.005") and month >= len(installments) - 1:
            return paid_by_month, True
        if new_balance >= balance and month >= len(installments):
            return paid_by_month, False  # not shrinking, no more cuotas - never will
        balance = new_balance
    return paid_by_month, False


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month)


def _q(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_debt_for_month(db: Session, month_start: date, usd_rate: Decimal) -> list[schemas.BudgetDebtLine]:
    """Each payoff plan's debt payment for the given month, in CRC - only the
    part of the card payment beyond the card's expected new spending, since
    those purchases are already counted against category budgets."""
    lines = []
    for plan in db.query(models.CardPayoffPlan).all():
        month_index = _months_between(plan.balance_as_of.replace(day=1), month_start)
        if month_index < 0:
            continue  # before the plan started
        avg_crc, avg_usd, _ = get_avg_monthly_spend(db, plan.card_id)
        installments = get_scheduled_installments(db, plan.card_id, plan.balance_as_of)

        parts = {}
        for currency, avg in (("CRC", avg_crc), ("USD", avg_usd)):
            c = currency.lower()
            payment = Decimal(getattr(plan, f"monthly_payment_{c}"))
            spend = getattr(plan, f"monthly_spend_{c}")
            spend = avg if spend is None else Decimal(spend)
            cuotas = installments[currency]
            # This month's cuotas are category spending too (Tasa Cero rows
            # are real transactions), so they come off the debt line as well.
            cuotas_this_month = cuotas[month_index] if month_index < len(cuotas) else Decimal(0)
            spend_this_month = spend + cuotas_this_month
            paid = Decimal(0)
            if payment and (getattr(plan, f"balance_{c}") or cuotas):
                schedule, clears = project_payments(
                    getattr(plan, f"balance_{c}"), getattr(plan, f"annual_rate_{c}"), payment, spend, cuotas
                )
                if month_index < len(schedule):
                    paid = schedule[month_index]
                elif not clears:
                    paid = payment
            parts[currency] = (paid, spend_this_month, max(paid - spend_this_month, Decimal(0)), cuotas_this_month)

        net_crc = parts["CRC"][2] + parts["USD"][2] * Decimal(usd_rate)
        if net_crc <= 0:
            continue
        lines.append(schemas.BudgetDebtLine(
            card_id=plan.card_id,
            card_name=plan.card.name,
            payment_crc=_q(parts["CRC"][0]),
            payment_usd=_q(parts["USD"][0]),
            spend_crc=_q(parts["CRC"][1]),
            spend_usd=_q(parts["USD"][1]),
            installments_crc=_q(parts["CRC"][3]),
            installments_usd=_q(parts["USD"][3]),
            amount=_q(net_crc),
        ))
    return lines
