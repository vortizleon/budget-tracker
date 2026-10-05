"""A financial snapshot of everything in the app, to hand to someone (or an AI
assistant) for advice.

Built from the same numbers the app shows: statements (the bank's own record),
what each card owes now, the cost of the debt, income, budgets, spending trends,
Tasa Cero installments and payoff plans. Account and card numbers, IBANs and
the account holder's name are never included - cards are identified only by the
name given in the app. Individual transactions are left out unless asked for.
"""
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from . import analytics, budgets, debt, models

GLOSSARY = [
    "CRC = Costa Rican colones, USD = US dollars. Card balances are kept separately per currency; "
    "each is paid in its own currency. USD amounts are converted to CRC with the exchange rate below.",
    "Pago de contado = the amount that, paid by the due date, avoids all interest. Pago mínimo = the minimum payment; "
    "paying only it means interest on the whole balance.",
    "Tasa Cero = a 0% installment plan (cuotas) at a merchant; it is not interest-bearing debt but is a fixed monthly commitment.",
    "'Owed now' is an estimate: statement balance - payments since the cut + purchases since the cut. "
    "Points redeemed are a credit applied on a later statement and are not counted as payments.",
    "Interest charged is what the bank billed in the last cycle; 'projected' is a month of interest at today's balance (annual rate / 12).",
]

QUESTIONS = [
    "Given the debt, income and spending below, what is the most effective order to pay it off (consider the interest rates "
    "per currency, the currency of the income, and exchange-rate risk)?",
    "How much can realistically go to debt each month, and how long until it is gone at that pace?",
    "Where is spending highest relative to income, and what is the easiest cut?",
    "What should the order be between a small emergency fund, paying debt, and starting to build capital?",
    "Are there fees or recurring charges (insurance, subscriptions) worth cancelling?",
]


def _n(value: Any) -> Optional[float]:
    return None if value is None else round(float(value), 2)


def _d(value: Any) -> Optional[str]:
    return value.isoformat() if value is not None else None


def build_snapshot(db: Session, include_transactions: bool = False, today: Optional[date] = None) -> Dict[str, Any]:
    today = today or date.today()
    settings = budgets.get_settings(db)
    rate = Decimal(settings.usd_to_crc_rate)

    # ---- income -------------------------------------------------------------------
    since = today - timedelta(days=185)
    income_rows = (db.query(models.IncomeEntry).filter(models.IncomeEntry.date >= since)
                   .order_by(models.IncomeEntry.date).all())
    income = {
        "expected_monthly_income_crc": _n(settings.expected_monthly_income),
        "logged_last_6_months": [
            {"date": _d(i.date), "amount": _n(i.amount), "currency": i.currency, "description": i.description}
            for i in income_rows
        ],
    }

    # ---- debt: summary, per-card position, statements -----------------------------
    cod = debt.get_cost_of_debt(db)
    positions = {p.card_id: p for p in debt.get_positions(db, today)}
    latest = {st.card_id: st for st in debt.latest_statements(db) if st.card_id is not None}

    cards = []
    for card in db.query(models.Card).filter(models.Card.is_active == True).order_by(models.Card.id).all():
        entry: Dict[str, Any] = {
            "name": card.name, "type": card.card_type, "bank": card.bank,
            "credit_limit_crc": _n(card.credit_limit_crc), "credit_limit_usd": _n(card.credit_limit_usd),
            "statement_cut_day": card.cutoff_day, "payment_due_day": card.payment_due_day,
        }
        st = latest.get(card.id)
        if st:
            entry["latest_statement"] = {
                "period": st.period, "cut_date": _d(st.cut_date), "pay_by": _d(st.cash_due_date),
                "balance_crc": _n(st.closing_balance_crc), "balance_usd": _n(st.closing_balance_usd),
                "minimum_payment_crc": _n(st.min_payment_crc), "minimum_payment_usd": _n(st.min_payment_usd),
                "pay_in_full_crc": _n(st.cash_payment_crc), "pay_in_full_usd": _n(st.cash_payment_usd),
                "interest_charged_crc": _n(st.interest_crc), "interest_charged_usd": _n(st.interest_usd),
                "insurance_and_optional_crc": _n(st.insurance_crc), "insurance_and_optional_usd": _n(st.insurance_usd),
                "interest_rate_crc_pct": _n(st.apr_crc), "interest_rate_usd_pct": _n(st.apr_usd),
                "points_earned": _n(st.points_assigned),
                "needs_review": st.status != "ok",
                "zero_rate_installments": [
                    {"merchant": f.merchant, "currency": f.currency, "monthly": _n(f.installment_amount),
                     "payment": f"{f.installment_number} of {f.installments_total}", "ends": _d(f.end_date)}
                    for f in st.financing_lines
                ],
            }
        pos = positions.get(card.id)
        if pos:
            entry["position_now"] = {
                "status": pos.status, "days_until_due": pos.days_left,
                "owed_now_crc": _n(pos.balance_now_crc), "owed_now_usd": _n(pos.balance_now_usd),
                "paid_since_statement_crc": _n(pos.payments_since_crc), "paid_since_statement_usd": _n(pos.payments_since_usd),
                "purchases_since_statement_crc": _n(pos.purchases_since_crc), "purchases_since_statement_usd": _n(pos.purchases_since_usd),
                "points_redeemed_since_crc": _n(pos.rewards_since_crc),
                "still_to_pay_in_full_crc": _n(pos.remaining_cash_crc), "still_to_pay_in_full_usd": _n(pos.remaining_cash_usd),
                "minimum_left_crc": _n(pos.remaining_min_crc), "minimum_left_usd": _n(pos.remaining_min_usd),
            }
        plan = db.query(models.CardPayoffPlan).filter(models.CardPayoffPlan.card_id == card.id).first()
        if plan:
            entry["payoff_plan"] = {
                "balance_as_of": _d(plan.balance_as_of),
                "balance_crc": _n(plan.balance_crc), "balance_usd": _n(plan.balance_usd),
                "planned_monthly_payment_crc": _n(plan.monthly_payment_crc), "planned_monthly_payment_usd": _n(plan.monthly_payment_usd),
            }
        cards.append(entry)

    history = []
    for st in db.query(models.Statement).order_by(models.Statement.period, models.Statement.account_last4).all():
        history.append({
            "period": st.period, "card": st.card.name if st.card else "(unlinked card)",
            "balance_crc": _n(st.closing_balance_crc), "balance_usd": _n(st.closing_balance_usd),
            "purchases_crc": _n(st.purchases_crc), "purchases_usd": _n(st.purchases_usd),
            "paid_crc": _n(st.payments_crc), "paid_usd": _n(st.payments_usd),
            "interest_crc": _n(st.interest_crc), "interest_usd": _n(st.interest_usd),
            "insurance_crc": _n(st.insurance_crc), "insurance_usd": _n(st.insurance_usd),
        })

    payments = [
        {"date": _d(p.date), "card": p.card_name, "amount": _n(p.amount), "currency": p.currency}
        for p in debt.list_payments(db, limit=40)
        if p.date >= today - timedelta(days=365)
    ]

    # ---- Tasa Cero plans created in the app ---------------------------------------
    installments = []
    for plan in db.query(models.InstallmentPlan).all():
        future = [t for t in plan.transactions if t.date > today]
        if not future:
            continue
        installments.append({
            "description": plan.description, "currency": plan.currency, "card": plan.card.name if plan.card else None,
            "monthly": _n(future[0].amount), "remaining_payments": len(future),
            "remaining_total": _n(sum(t.amount for t in future)), "last_payment": _d(max(t.date for t in future)),
        })

    # ---- spending -----------------------------------------------------------------
    trends = [{"month": t.month, "total_crc": _n(t.total_crc), "total_usd": _n(t.total_usd)}
              for t in analytics.get_monthly_trends(db, months_back=6)]
    by_category = []
    first_of_month = today.replace(day=1)
    for back in range(3, -1, -1):          # three full months plus the current one
        start = (first_of_month - timedelta(days=31 * back)).replace(day=1) if back else first_of_month
        end = (start.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
        month = {"month": start.strftime("%Y-%m"), "crc": [], "usd": []}
        for cur in ("CRC", "USD"):
            rows = analytics.get_spending_by_category(db, start_date=start, end_date=min(end, today), currency=cur)
            month[cur.lower()] = [{"category": r.category_name, "total": _n(r.total_amount)} for r in rows]
        by_category.append(month)

    overview = budgets.get_overview(db, today.strftime("%Y-%m"))
    budget_section = {
        "month": overview.month, "income_used_for_budgets_crc": _n(overview.income_base),
        "total_budgeted_crc": _n(overview.total_budgeted), "total_spent_crc": _n(overview.total_spent),
        "card_debt_payments_planned_crc": _n(overview.total_debt),
        "unbudgeted_crc": _n(overview.unbudgeted),
        "categories": [
            {"category": l.category_name, "budget_crc": _n(l.adjusted_amount), "spent_crc": _n(l.spent),
             "locked": l.is_protected}
            for l in overview.lines
        ],
    }

    subscriptions = [
        {"name": s.name, "amount": _n(s.amount), "currency": s.currency, "billing_day": s.billing_day}
        for s in db.query(models.Subscription).filter(models.Subscription.is_active == True).all()
    ]

    # ---- data quality notes --------------------------------------------------------
    notes = []
    review = db.query(models.Statement).filter(models.Statement.status != "ok").count()
    if review:
        notes.append(f"{review} imported statement(s) are flagged 'needs review' - their figures may be incomplete.")
    if not history:
        notes.append("No bank statements imported, so interest, fees and exact balances are missing.")
    unassigned = (db.query(models.Transaction)
                  .filter(models.Transaction.card_id.is_(None), models.Transaction.date >= today - timedelta(days=60),
                          models.Transaction.transaction_type == "purchase").count())
    if unassigned:
        notes.append(f"{unassigned} purchase(s) in the last 60 days aren't linked to any card.")
    last = db.query(models.Transaction.date).filter(models.Transaction.gmail_message_id.isnot(None)) \
        .order_by(models.Transaction.date.desc()).first()
    if last:
        notes.append(f"Latest synced bank-email transaction: {last[0].isoformat()}.")

    snapshot: Dict[str, Any] = {
        "generated_on": today.isoformat(),
        "usd_to_crc_rate": _n(rate),
        "glossary": GLOSSARY,
        "income": income,
        "debt_summary": {
            "statement_period": cod.period,
            "total_debt_now_crc_equivalent": _n(cod.total_debt_crc),
            "owed_now_crc": _n(cod.debt_crc), "owed_now_usd": _n(cod.debt_usd),
            "total_at_statement_crc_equivalent": _n(cod.statement_debt_crc),
            "paid_since_statements_crc_equivalent": _n(cod.paid_since_crc),
            "interest_charged_last_cycle_crc_equivalent": _n(cod.interest_crc),
            "insurance_and_optional_last_cycle_crc": _n(cod.insurance_crc),
            "monthly_cost_last_statement_crc": _n(cod.monthly_cost_crc),
            "projected_monthly_interest_at_todays_balance_crc": _n(cod.projected_interest_crc),
            "yearly_cost_if_unchanged_crc": _n(cod.yearly_cost_crc),
            "cost_share_of_income_pct": _n(cod.cost_share_of_income * 100) if cod.cost_share_of_income is not None else None,
            "weighted_average_rate_pct": _n(cod.average_rate),
            "highest_rate_currency": cod.highest_rate_currency,
            "rate_crc_pct": _n(cod.apr_crc), "rate_usd_pct": _n(cod.apr_usd),
            "minimum_payments_crc_equivalent": _n(cod.minimum_payment_crc),
            "share_of_minimum_that_is_only_interest_pct": _n(cod.interest_share_of_minimum * 100) if cod.interest_share_of_minimum is not None else None,
            "zero_rate_installments_still_to_bill_crc_equivalent": _n(cod.future_installments_crc),
        } if cod.has_data else None,
        "cards": cards,
        "statement_history": history,
        "payments_reported_last_12_months": payments,
        "zero_rate_installment_plans": installments,
        "monthly_spending_totals": trends,
        "spending_by_category": by_category,
        "budget_this_month": budget_section,
        "subscriptions": subscriptions,
        "data_notes": notes,
    }

    if include_transactions:
        rows = (db.query(models.Transaction).filter(models.Transaction.date >= today - timedelta(days=90))
                .order_by(models.Transaction.date.desc()).all())
        snapshot["transactions_last_90_days"] = [
            {"date": _d(t.date), "type": t.transaction_type, "amount": _n(t.amount), "currency": t.currency,
             "merchant": t.commerce_name, "category": t.category.name if t.category else None,
             "card": t.card.name if t.card else None}
            for t in rows
        ]
    return snapshot


# ---------------------------------------------------------------------------------
# Output formats
# ---------------------------------------------------------------------------------

def to_json(snapshot: Dict[str, Any]) -> str:
    return json.dumps(snapshot, indent=2, ensure_ascii=False)


def _cell(v: Any) -> str:
    if v is None:
        return "-"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v:,.2f}"
    return str(v)


def _table(rows: List[Dict[str, Any]], columns: Optional[List[str]] = None) -> str:
    if not rows:
        return "_none_\n"
    cols = columns or list(rows[0].keys())
    out = ["| " + " | ".join(c.replace("_", " ") for c in cols) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(_cell(r.get(c)) for c in cols) + " |")
    return "\n".join(out) + "\n"


def _kv(d: Dict[str, Any]) -> str:
    return "\n".join(f"- **{k.replace('_', ' ')}**: {_cell(v)}" for k, v in d.items() if v is not None) + "\n"


def to_markdown(s: Dict[str, Any]) -> str:
    out = [f"# Personal finance snapshot - {s['generated_on']}", ""]
    out.append("Exported from my budget tracker so you can give financial advice. Amounts are in colones (CRC) and dollars (USD); "
               f"USD is converted at ₡{s['usd_to_crc_rate']:,.2f} per dollar. "
               "No account numbers or personal identifiers are included.\n")
    out.append("## What I'd like help with\n")
    out.extend(f"{i}. {q}" for i, q in enumerate(QUESTIONS, 1))
    out.append("\n## Definitions\n")
    out.extend(f"- {g}" for g in GLOSSARY)

    out.append("\n## Income\n")
    out.append(f"- **Expected monthly income (CRC)**: {_cell(s['income']['expected_monthly_income_crc'])}")
    out.append("\nLogged in the last 6 months:\n")
    out.append(_table(s["income"]["logged_last_6_months"]))

    out.append("\n## Debt summary\n")
    out.append(_kv(s["debt_summary"]) if s["debt_summary"] else "_No statements imported yet._\n")

    out.append("\n## Cards\n")
    for c in s["cards"]:
        out.append(f"### {c['name']}\n")
        out.append(_kv({k: v for k, v in c.items() if k not in ("latest_statement", "position_now", "payoff_plan", "name")}))
        for key, title in (("latest_statement", "Latest statement"), ("position_now", "Where it stands now"), ("payoff_plan", "Payoff plan")):
            if c.get(key):
                body = {k: v for k, v in c[key].items() if k != "zero_rate_installments"}
                out.append(f"**{title}**\n")
                out.append(_kv(body))
                if key == "latest_statement" and c[key]["zero_rate_installments"]:
                    out.append("Zero-rate installments on this statement:\n")
                    out.append(_table(c[key]["zero_rate_installments"]))

    out.append("\n## Statement history (what each month cost)\n")
    out.append(_table(s["statement_history"]))
    out.append("\n## Payments I reported (last 12 months)\n")
    out.append(_table(s["payments_reported_last_12_months"]))
    out.append("\n## Zero-rate (Tasa Cero) plans still running\n")
    out.append(_table(s["zero_rate_installment_plans"]))

    out.append("\n## Spending\n")
    out.append("Monthly totals (all cards and accounts, purchases only):\n")
    out.append(_table(s["monthly_spending_totals"]))
    for m in s["spending_by_category"]:
        out.append(f"\n**{m['month']}** by category\n")
        out.append("CRC:\n")
        out.append(_table(m["crc"]))
        out.append("USD:\n")
        out.append(_table(m["usd"]))

    b = s["budget_this_month"]
    out.append(f"\n## Budget for {b['month']}\n")
    out.append(_kv({k: v for k, v in b.items() if k not in ("categories", "month")}))
    out.append(_table(b["categories"]))

    out.append("\n## Recurring subscriptions\n")
    out.append(_table(s["subscriptions"]))

    if "transactions_last_90_days" in s:
        out.append("\n## Transactions (last 90 days)\n")
        out.append(_table(s["transactions_last_90_days"]))

    out.append("\n## Data notes\n")
    out.extend(f"- {n}" for n in s["data_notes"]) if s["data_notes"] else out.append("_None._")
    return "\n".join(out) + "\n"
