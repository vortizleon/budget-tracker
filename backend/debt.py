"""What the user's credit-card debt costs, computed from imported statements.

Statements are the bank's own record, so interest, insurance and rates come
from them rather than being estimated. USD amounts are converted to CRC with
the budget settings' exchange rate so totals can be compared and added.
"""
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from . import budgets, models, schemas

HISTORY_MONTHS = 12
ZERO = Decimal(0)


def _d(value) -> Decimal:
    return Decimal(value) if value is not None else ZERO


def _crc(crc, usd, rate: Decimal) -> Decimal:
    return _d(crc) + _d(usd) * rate


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

    cards = []
    total_debt = interest = insurance = minimum = ZERO
    debt_crc = debt_usd = ZERO
    weighted_rate_num = ZERO
    future_installments = ZERO
    for st in latest:
        card_debt = _crc(st.closing_balance_crc, st.closing_balance_usd, rate)
        card_interest = _crc(st.interest_crc, st.interest_usd, rate)
        total_debt += card_debt
        debt_crc += _d(st.closing_balance_crc)
        debt_usd += _d(st.closing_balance_usd)
        interest += card_interest
        insurance += _crc(st.insurance_crc, st.insurance_usd, rate)
        minimum += _crc(st.min_payment_crc, st.min_payment_usd, rate)
        weighted_rate_num += (
            _d(st.closing_balance_crc) * _d(st.apr_crc)
            + _d(st.closing_balance_usd) * rate * _d(st.apr_usd)
        )
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
        future_installments_crc=future_installments,
        cards=cards,
        history=history,
    )
