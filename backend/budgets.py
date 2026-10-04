"""Monthly budgets: per-category limits as a % of income or a fixed amount,
manually logged income (paychecks), and spending tracked against both.

All budget math is in CRC; USD purchases/income are converted with the
user-set rate in BudgetSettings."""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Dict, List, Optional, Tuple
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from calendar import monthrange

from . import models, schemas, payoff


# Suggested % of monthly income per category, applied the first time the
# Budgets view is opened. Keyed by lowercase category name and covering both
# this install's categories and init_db.py's defaults; categories not listed
# start without a budget. Adds up to ~85% per install, leaving ~15% unbudgeted
# as savings (roughly the 50/30/20 rule: needs / wants / savings).
SUGGESTED_PERCENTAGES = {
    # Needs
    "rent": 30, "rent/mortgage": 30,
    "supermarket": 12,
    "transportation": 8,
    "home/utilities": 6, "utilities": 4, "home services": 2,
    "health": 3,
    "seguros tarjetas": 2,
    # Wants
    "rests": 5, "restaurants": 5,
    "takeout": 4,
    "bares": 2,
    "entertainment": 4,
    "shopping": 4,
    "subscriptions": 2,
    "other": 3,
}

# Essentials protected from debt cuts by default (lowercase names).
PROTECTED_BY_DEFAULT = {"rent", "rent/mortgage", "home/utilities", "utilities"}

TWO_PLACES = Decimal("0.01")


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def parse_month(month: Optional[str]) -> Tuple[date, date]:
    """'YYYY-MM' (default: current month) -> (first day, last day)."""
    if month:
        year, mon = (int(p) for p in month.split("-"))
    else:
        today = date.today()
        year, mon = today.year, today.month
    return date(year, mon, 1), date(year, mon, monthrange(year, mon)[1])


# ============================================================================
# Settings
# ============================================================================

def get_settings(db: Session) -> models.BudgetSettings:
    """Get the settings row, creating it (and the suggested budgets) on
    first use - that's what makes the suggestion a one-time thing, so
    deleting every budget later doesn't bring the suggestions back."""
    settings = db.query(models.BudgetSettings).first()
    if settings is None:
        settings = models.BudgetSettings(usd_to_crc_rate=Decimal(505))
        db.add(settings)
        if db.query(models.Budget).count() == 0:
            _add_suggested_budgets(db)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, update: schemas.BudgetSettingsUpdate) -> models.BudgetSettings:
    settings = get_settings(db)
    for field, value in update.model_dump(exclude_unset=True).items():
        if field == "usd_to_crc_rate" and value is None:
            continue  # required column
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings


# ============================================================================
# Budgets
# ============================================================================

def _add_suggested_budgets(db: Session) -> int:
    categories = db.query(models.Category).filter(
        models.Category.category_type == "expense"
    ).all()
    added = 0
    for category in categories:
        name = category.name.strip().lower()
        pct = SUGGESTED_PERCENTAGES.get(name)
        if pct:
            db.add(models.Budget(
                category_id=category.id,
                percentage=Decimal(pct),
                is_protected=name in PROTECTED_BY_DEFAULT,
            ))
            added += 1
    return added


def reset_to_suggested(db: Session) -> int:
    """Replace all budgets with the suggested ones."""
    get_settings(db)
    db.query(models.Budget).delete()
    added = _add_suggested_budgets(db)
    db.commit()
    return added


def upsert_budget(db: Session, data: schemas.BudgetUpsert) -> models.Budget:
    if (data.percentage is None) == (data.amount is None):
        raise ValueError("Send exactly one of percentage or amount")
    category = db.query(models.Category).filter(models.Category.id == data.category_id).first()
    if category is None:
        raise LookupError("Category not found")

    budget = db.query(models.Budget).filter(models.Budget.category_id == data.category_id).first()
    if budget is None:
        budget = models.Budget(
            category_id=data.category_id,
            is_protected=category.name.strip().lower() in PROTECTED_BY_DEFAULT,
        )
        db.add(budget)
    budget.percentage = data.percentage
    budget.amount = data.amount
    db.commit()
    db.refresh(budget)
    return budget


def set_protected(db: Session, budget_id: int, is_protected: bool) -> bool:
    budget = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if budget is None:
        return False
    budget.is_protected = is_protected
    db.commit()
    return True


def delete_budget(db: Session, budget_id: int) -> bool:
    budget = db.query(models.Budget).filter(models.Budget.id == budget_id).first()
    if budget is None:
        return False
    db.delete(budget)
    db.commit()
    return True


# ============================================================================
# Income
# ============================================================================

def _to_crc(amount: Decimal, currency: str, rate: Decimal) -> Decimal:
    return Decimal(amount) * Decimal(rate) if currency == "USD" else Decimal(amount)


def _income_to_response(entry: models.IncomeEntry, rate: Decimal) -> schemas.IncomeEntryResponse:
    return schemas.IncomeEntryResponse(
        id=entry.id,
        date=entry.date,
        amount=entry.amount,
        currency=entry.currency,
        description=entry.description,
        amount_crc=_q(_to_crc(entry.amount, entry.currency, rate)),
    )


def create_income(db: Session, data: schemas.IncomeEntryCreate) -> schemas.IncomeEntryResponse:
    if data.currency not in ("CRC", "USD"):
        raise ValueError("Currency must be CRC or USD")
    entry = models.IncomeEntry(**data.model_dump())
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _income_to_response(entry, get_settings(db).usd_to_crc_rate)


def delete_income(db: Session, income_id: int) -> bool:
    entry = db.query(models.IncomeEntry).filter(models.IncomeEntry.id == income_id).first()
    if entry is None:
        return False
    db.delete(entry)
    db.commit()
    return True


# ============================================================================
# Monthly overview
# ============================================================================

def _spending_by_category(db: Session, start: date, end: date, rate: Decimal) -> Dict[Optional[int], Decimal]:
    """CRC-equivalent purchase totals for the date range, keyed by category id
    (None for transactions with no category)."""
    rows = db.query(
        models.Transaction.category_id,
        models.Transaction.currency,
        func.sum(models.Transaction.amount),
    ).filter(
        models.Transaction.transaction_type == "purchase",
        models.Transaction.date >= start,
        models.Transaction.date <= end,
    ).group_by(models.Transaction.category_id, models.Transaction.currency).all()

    totals: Dict[Optional[int], Decimal] = {}
    for category_id, currency, total in rows:
        totals[category_id] = totals.get(category_id, Decimal(0)) + _to_crc(total or 0, currency, rate)
    return totals


def get_overview(db: Session, month: Optional[str] = None) -> schemas.BudgetOverview:
    start, end = parse_month(month)
    settings = get_settings(db)
    rate = Decimal(settings.usd_to_crc_rate)

    entries = db.query(models.IncomeEntry).filter(
        models.IncomeEntry.date >= start,
        models.IncomeEntry.date <= end,
    ).order_by(models.IncomeEntry.date).all()
    income_entries = [_income_to_response(e, rate) for e in entries]
    received = sum((e.amount_crc for e in income_entries), Decimal(0))

    # Plan against the expected income until real income exceeds it (e.g. a
    # bonus) - otherwise every budget would be half-size between paychecks.
    expected = Decimal(settings.expected_monthly_income or 0)
    base = max(received, expected)

    spending = _spending_by_category(db, start, end, rate)

    # Planned amounts first (what the user set, before debt).
    budgets = db.query(models.Budget).join(models.Category).order_by(models.Category.name).all()
    planned = []
    for b in budgets:
        if b.amount is not None:
            anchor = "amount"
            amount = Decimal(b.amount)
            percentage = (amount / base * 100) if base > 0 else Decimal(0)
        else:
            anchor = "percentage"
            percentage = Decimal(b.percentage or 0)
            amount = base * percentage / 100
        planned.append((b, anchor, percentage, amount))

    # Debt payments come out of everything that isn't protected - the
    # flexible budgets and the unbudgeted savings - by the same factor.
    debt_lines = payoff.get_debt_for_month(db, start, rate)
    total_debt = sum((d.amount for d in debt_lines), Decimal(0))
    protected_total = sum((a for b, _, _, a in planned if b.is_protected), Decimal(0))
    pool = base - protected_total
    if total_debt <= 0:
        factor, shortfall = Decimal(1), Decimal(0)
    elif pool <= 0:
        factor, shortfall = Decimal(0), total_debt
    else:
        factor = max(pool - total_debt, Decimal(0)) / pool
        shortfall = max(total_debt - pool, Decimal(0))

    lines: List[schemas.BudgetLine] = []
    budgeted_ids = set()
    for b, anchor, percentage, amount in planned:
        adjusted = amount if b.is_protected else amount * factor
        spent = spending.get(b.category_id, Decimal(0))
        budgeted_ids.add(b.category_id)
        lines.append(schemas.BudgetLine(
            id=b.id,
            category_id=b.category_id,
            category_name=b.category.name,
            category_color=b.category.color,
            category_icon=b.category.icon,
            anchor=anchor,
            is_protected=bool(b.is_protected),
            percentage=_q(percentage),
            amount=_q(amount),
            adjusted_amount=_q(adjusted),
            spent=_q(spent),
            remaining=_q(adjusted - spent),
        ))

    total_budgeted = sum((l.adjusted_amount for l in lines), Decimal(0))
    total_spent = sum((l.spent for l in lines), Decimal(0))
    unbudgeted_spent = sum(
        (v for k, v in spending.items() if k not in budgeted_ids), Decimal(0)
    )

    return schemas.BudgetOverview(
        month=start.strftime("%Y-%m"),
        settings=schemas.BudgetSettingsResponse.model_validate(settings),
        income_entries=income_entries,
        income_received=_q(received),
        income_base=_q(base),
        lines=lines,
        debt_lines=debt_lines,
        total_debt=_q(total_debt),
        reduction_percentage=_q((1 - factor) * 100),
        debt_shortfall=_q(shortfall),
        total_budgeted=_q(total_budgeted),
        total_percentage=_q(total_budgeted / base * 100) if base > 0 else _q(
            sum((l.percentage for l in lines), Decimal(0))
        ),
        total_spent=_q(total_spent),
        unbudgeted=_q(base - total_debt - total_budgeted),
        unbudgeted_spent=_q(unbudgeted_spent),
    )
