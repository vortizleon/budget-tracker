"""Month-end spending forecast: where the current month is headed, per
category, at the current pace.

For each category the rest of the month is estimated two ways and blended
by how far into the month we are:
  - pace:    what's been spent so far, per day, times the days left
  - history: the category's typical monthly total (from past full months)
             minus what's already been spent
Early in the month history dominates (a few days of pace is noise); by the
end, pace does. Categories with fewer than 3 purchases a month (rent, bills)
are lumpy, so they use history alone - one rent payment on the 1st
shouldn't project to 30 rent payments. Tasa Cero cuotas are known exactly,
so they're added as scheduled rather than estimated.
All amounts are CRC, USD converted at the budget settings rate."""
from sqlalchemy.orm import Session
from typing import Dict, Optional
from datetime import date
from decimal import Decimal
from calendar import monthrange

from . import models, schemas, budgets

HISTORY_MONTHS = 3
LUMPY_TXNS_PER_MONTH = 3


def _month_start(year: int, month: int) -> date:
    while month < 1:
        month += 12
        year -= 1
    return date(year, month, 1)


def get_month_forecast(db: Session) -> schemas.MonthForecast:
    today = date.today()
    start, end = budgets.parse_month(None)
    days_in_month = end.day
    days_elapsed = today.day
    days_left = days_in_month - days_elapsed

    overview = budgets.get_overview(db, start.strftime("%Y-%m"))
    rate = Decimal(overview.settings.usd_to_crc_rate)
    budget_by_category = {l.category_id: l.adjusted_amount for l in overview.lines}

    def crc(t: models.Transaction) -> Decimal:
        return Decimal(t.amount) * rate if t.currency == "USD" else Decimal(t.amount)

    # Past full months with data (a month only counts if syncing covered it
    # from its first day, so a half-synced month doesn't drag averages down).
    oldest = db.query(models.Transaction.date).order_by(models.Transaction.date).first()
    history_start = _month_start(start.year, start.month - HISTORY_MONTHS)
    if oldest:
        while history_start < start and history_start < oldest[0]:
            history_start = _month_start(history_start.year, history_start.month + 1)
    history_months = (start.year - history_start.year) * 12 + (start.month - history_start.month) if oldest else 0

    purchases = db.query(models.Transaction).join(
        models.Category, models.Transaction.category_id == models.Category.id, isouter=True
    ).filter(
        models.Transaction.transaction_type == "purchase",
        models.Transaction.date >= history_start,
        models.Transaction.date <= end,
    ).all()

    categories: Dict[Optional[int], dict] = {}

    def bucket(t: models.Transaction) -> Optional[dict]:
        if t.category and t.category.category_type == "income":
            return None
        key = t.category_id
        if key not in categories:
            categories[key] = {
                "name": t.category.name if t.category else "Uncategorized",
                "icon": t.category.icon if t.category else "📁",
                "mtd_regular": Decimal(0), "mtd_cuotas": Decimal(0),
                "scheduled": Decimal(0), "hist_total": Decimal(0), "hist_count": 0,
            }
        return categories[key]

    for t in purchases:
        b = bucket(t)
        if b is None:
            continue
        is_cuota = t.installment_plan_id is not None
        if t.date < start:
            if not is_cuota:  # cuotas are scheduled exactly, keep them out of "typical"
                b["hist_total"] += crc(t)
                b["hist_count"] += 1
        elif t.date <= today:
            b["mtd_cuotas" if is_cuota else "mtd_regular"] += crc(t)
        elif is_cuota:
            b["scheduled"] += crc(t)
        # future-dated non-cuota rows (rare) are ignored - pace covers them

    # Budgeted categories with nothing spent and no history still get a line.
    for line in overview.lines:
        if line.category_id not in categories:
            categories[line.category_id] = {
                "name": line.category_name, "icon": line.category_icon,
                "mtd_regular": Decimal(0), "mtd_cuotas": Decimal(0),
                "scheduled": Decimal(0), "hist_total": Decimal(0), "hist_count": 0,
            }

    weight = Decimal(days_elapsed) / Decimal(days_in_month)
    lines = []
    for category_id, b in categories.items():
        mtd = b["mtd_regular"]
        pace_rest = mtd / days_elapsed * days_left
        typical, hist_rest = None, Decimal(0)
        if history_months == 0:
            basis, rest, line_weight = "pace", pace_rest, Decimal(1)
        else:
            typical = b["hist_total"] / history_months
            hist_rest = max(typical - mtd, Decimal(0))
            if b["hist_count"] / history_months < LUMPY_TXNS_PER_MONTH:
                basis, rest, line_weight = "history", hist_rest, Decimal(0)
            else:
                basis, rest, line_weight = "blend", weight * pace_rest + (1 - weight) * hist_rest, weight

        spent = mtd + b["mtd_cuotas"]
        projected = spent + rest + b["scheduled"]
        budget = budget_by_category.get(category_id)
        if budget is None:
            status = "no_budget"
        elif spent > budget:
            status = "over"
        elif projected > budget:
            status = "at_risk"
        else:
            status = "on_track"

        if projected <= 0 and budget is None:
            continue
        lines.append(schemas.ForecastLine(
            category_id=category_id,
            category_name=b["name"],
            category_icon=b["icon"],
            budget=budgets._q(budget) if budget is not None else None,
            spent_so_far=budgets._q(spent),
            scheduled=budgets._q(b["scheduled"]),
            projected=budgets._q(projected),
            status=status,
            basis=basis,
            typical_month=budgets._q(typical) if typical is not None else None,
            pace_month=budgets._q(mtd / days_elapsed * days_in_month),
            rest_from_typical=budgets._q(hist_rest),
            rest_from_pace=budgets._q(pace_rest),
            rest=budgets._q(rest),
            pace_weight=weight.quantize(Decimal("0.001")) if basis == "blend" else line_weight,
        ))

    # Biggest problems first: over, then at risk (by projected overshoot), then the rest by size.
    order = {"over": 0, "at_risk": 1, "on_track": 2, "no_budget": 3}
    lines.sort(key=lambda l: (order[l.status], -(l.projected - (l.budget or 0)), -l.projected))

    spent_total = sum((l.spent_so_far for l in lines), Decimal(0))
    projected_total = sum((l.projected for l in lines), Decimal(0))
    return schemas.MonthForecast(
        month=start.strftime("%Y-%m"),
        days_elapsed=days_elapsed,
        days_in_month=days_in_month,
        history_months=history_months,
        history_start=history_start.strftime("%Y-%m") if history_months else None,
        pace_weight=weight.quantize(Decimal("0.001")),
        income_base=overview.income_base,
        total_debt=overview.total_debt,
        spent_so_far=budgets._q(spent_total),
        projected_spend=budgets._q(projected_total),
        projected_left=budgets._q(overview.income_base - projected_total - overview.total_debt),
        lines=lines,
    )
