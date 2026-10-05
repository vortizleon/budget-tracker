"""Analytics and aggregation functions for budgeting insights."""
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_
from typing import List, Optional, Tuple
from datetime import date, datetime, timedelta
from decimal import Decimal
from calendar import monthrange

from . import models, schemas


def get_spending_by_category(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None,
    transaction_type: str = "purchase"
) -> List[schemas.SpendingByCategory]:
    """
    Get spending breakdown by category.

    Args:
        db: Database session
        start_date: Filter start date (optional)
        end_date: Filter end date (optional)
        currency: Filter by currency (optional)
        transaction_type: "purchase" or "payment" (default: "purchase")

    Returns:
        List of SpendingByCategory objects
    """
    query = db.query(
        models.Category.id,
        models.Category.name,
        models.Category.color,
        models.Category.icon,
        func.sum(models.Transaction.amount).label('total_amount'),
        func.count(models.Transaction.id).label('transaction_count')
    ).join(
        models.Transaction, models.Transaction.category_id == models.Category.id
    ).filter(
        models.Transaction.transaction_type == transaction_type
    )

    # Apply filters
    if start_date:
        query = query.filter(models.Transaction.date >= start_date)
    if end_date:
        query = query.filter(models.Transaction.date <= end_date)
    if currency:
        query = query.filter(models.Transaction.currency == currency)

    query = query.group_by(
        models.Category.id,
        models.Category.name,
        models.Category.color,
        models.Category.icon
    ).order_by(func.sum(models.Transaction.amount).desc())

    results = query.all()

    # Calculate total for percentages
    total = sum(r.total_amount for r in results) if results else Decimal(0)

    # Convert to schema objects
    spending_data = []
    for r in results:
        percentage = float((r.total_amount / total) * 100) if total > 0 else 0
        spending_data.append(
            schemas.SpendingByCategory(
                category_id=r.id,
                category_name=r.name,
                category_color=r.color,
                category_icon=r.icon,
                total_amount=r.total_amount,
                transaction_count=r.transaction_count,
                percentage=round(percentage, 2)
            )
        )

    return spending_data


def get_daily_spending(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: str = "CRC"
) -> List[schemas.DailySpending]:
    """
    Get daily spending totals over a date range (zero-filled for days with
    no spending, so the result is a continuous series for charting).

    Args:
        db: Database session
        start_date: Range start (default: 29 days before end_date)
        end_date: Range end (default: today)
        currency: "CRC" or "USD" (default: "CRC")

    Returns:
        List of DailySpending objects, one per day in the range
    """
    if not end_date:
        end_date = datetime.now().date()
    if not start_date:
        start_date = end_date - timedelta(days=29)

    query = db.query(
        models.Transaction.date,
        func.sum(models.Transaction.amount).label('total'),
        func.count(models.Transaction.id).label('count')
    ).filter(
        and_(
            models.Transaction.date >= start_date,
            models.Transaction.date <= end_date,
            models.Transaction.currency == currency,
            models.Transaction.transaction_type == 'purchase'
        )
    ).group_by(models.Transaction.date)

    results = {r.date: (r.total, r.count) for r in query.all()}

    daily = []
    current_date = start_date
    while current_date <= end_date:
        total, count = results.get(current_date, (Decimal(0), 0))
        daily.append(schemas.DailySpending(date=current_date, total=total, transaction_count=count))
        current_date += timedelta(days=1)

    return daily


def get_monthly_trends(
    db: Session,
    months_back: int = 6,
    currency: Optional[str] = None
) -> List[schemas.MonthlyTrend]:
    """
    Get monthly spending trends.

    Args:
        db: Database session
        months_back: How many months to go back (default: 6)
        currency: Filter by currency (optional)

    Returns:
        List of MonthlyTrend objects
    """
    # Calculate start date
    start_date = datetime.now().date().replace(day=1) - timedelta(days=months_back * 30)

    # Query for CRC totals by month
    query_crc = db.query(
        func.strftime('%Y-%m', models.Transaction.date).label('month'),
        func.sum(models.Transaction.amount).label('total')
    ).filter(
        and_(
            models.Transaction.date >= start_date,
            models.Transaction.currency == 'CRC',
            models.Transaction.transaction_type == 'purchase'
        )
    ).group_by(func.strftime('%Y-%m', models.Transaction.date))

    # Query for USD totals by month
    query_usd = db.query(
        func.strftime('%Y-%m', models.Transaction.date).label('month'),
        func.sum(models.Transaction.amount).label('total')
    ).filter(
        and_(
            models.Transaction.date >= start_date,
            models.Transaction.currency == 'USD',
            models.Transaction.transaction_type == 'purchase'
        )
    ).group_by(func.strftime('%Y-%m', models.Transaction.date))

    # Query for transaction counts
    query_count = db.query(
        func.strftime('%Y-%m', models.Transaction.date).label('month'),
        func.count(models.Transaction.id).label('count')
    ).filter(
        and_(
            models.Transaction.date >= start_date,
            models.Transaction.transaction_type == 'purchase'
        )
    ).group_by(func.strftime('%Y-%m', models.Transaction.date))

    # Get results
    crc_results = {r.month: r.total for r in query_crc.all()}
    usd_results = {r.month: r.total for r in query_usd.all()}
    count_results = {r.month: r.count for r in query_count.all()}

    # Build monthly trends
    trends = []
    current_date = start_date
    while current_date <= datetime.now().date():
        month_key = current_date.strftime('%Y-%m')
        trends.append(
            schemas.MonthlyTrend(
                month=month_key,
                total_crc=crc_results.get(month_key, Decimal(0)),
                total_usd=usd_results.get(month_key, Decimal(0)),
                transaction_count=count_results.get(month_key, 0)
            )
        )

        # Move to next month
        if current_date.month == 12:
            current_date = current_date.replace(year=current_date.year + 1, month=1)
        else:
            current_date = current_date.replace(month=current_date.month + 1)

    return trends


def get_top_merchants(
    db: Session,
    limit: int = 10,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None
) -> List[schemas.TopMerchant]:
    """
    Get top merchants by spending.

    Args:
        db: Database session
        limit: Number of top merchants to return (default: 10)
        start_date: Filter start date (optional)
        end_date: Filter end date (optional)
        currency: Filter by currency (optional)

    Returns:
        List of TopMerchant objects
    """
    query = db.query(
        models.Transaction.commerce_name,
        models.Transaction.currency,
        func.sum(models.Transaction.amount).label('total_amount'),
        func.count(models.Transaction.id).label('transaction_count')
    ).filter(
        and_(
            models.Transaction.commerce_name.isnot(None),
            models.Transaction.transaction_type == 'purchase'
        )
    )

    # Apply filters
    if start_date:
        query = query.filter(models.Transaction.date >= start_date)
    if end_date:
        query = query.filter(models.Transaction.date <= end_date)
    if currency:
        query = query.filter(models.Transaction.currency == currency)

    query = query.group_by(
        models.Transaction.commerce_name,
        models.Transaction.currency
    ).order_by(func.sum(models.Transaction.amount).desc()).limit(limit)

    results = query.all()

    return [
        schemas.TopMerchant(
            commerce_name=r.commerce_name,
            total_amount=r.total_amount,
            transaction_count=r.transaction_count,
            currency=r.currency
        )
        for r in results
    ]


def get_spending_by_card(
    db: Session,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> List[schemas.SpendingByCard]:
    """
    Get per-card purchase totals, per currency.

    Args:
        db: Database session
        start_date: Only count purchases on/after this date (optional)
        end_date: Only count purchases on/before this date (optional)

    Returns:
        List of SpendingByCard objects, one per active card
    """
    cards = db.query(models.Card).filter(models.Card.is_active == True).all()

    date_filters = []
    if start_date:
        date_filters.append(models.Transaction.date >= start_date)
    if end_date:
        date_filters.append(models.Transaction.date <= end_date)

    def total(card_id: int, currency: str) -> Decimal:
        return db.query(func.sum(models.Transaction.amount)).filter(
            and_(
                models.Transaction.card_id == card_id,
                models.Transaction.currency == currency,
                models.Transaction.transaction_type == 'purchase',
                *date_filters
            )
        ).scalar() or Decimal(0)

    return [
        schemas.SpendingByCard(
            card_id=card.id,
            card_name=card.name,
            card_color=card.color,
            spent_crc=total(card.id, 'CRC'),
            spent_usd=total(card.id, 'USD'),
        )
        for card in cards
    ]


def get_dashboard_summary(db: Session) -> schemas.DashboardSummary:
    """
    Get dashboard summary statistics.

    Args:
        db: Database session

    Returns:
        DashboardSummary object
    """
    # Total transactions
    total_transactions = db.query(func.count(models.Transaction.id)).scalar() or 0

    # Total spent (CRC)
    total_spent_crc = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.currency == 'CRC',
            models.Transaction.transaction_type == 'purchase'
        )
    ).scalar() or Decimal(0)

    # Total spent (USD)
    total_spent_usd = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.currency == 'USD',
            models.Transaction.transaction_type == 'purchase'
        )
    ).scalar() or Decimal(0)

    # Total income (CRC)
    total_income_crc = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.currency == 'CRC',
            models.Transaction.transaction_type == 'payment'
        )
    ).scalar() or Decimal(0)

    # Total income (USD)
    total_income_usd = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.currency == 'USD',
            models.Transaction.transaction_type == 'payment'
        )
    ).scalar() or Decimal(0)

    # Active cards
    active_cards = db.query(func.count(models.Card.id)).filter(
        models.Card.is_active == True
    ).scalar() or 0

    # Uncategorized transactions
    uncategorized_count = db.query(func.count(models.Transaction.id)).filter(
        models.Transaction.category_id.is_(None)
    ).scalar() or 0

    # This month spending (CRC) - bounded on both ends, since an
    # installment plan can have future-dated rows (e.g. next month's
    # charge) that must not bleed into "this month".
    now = datetime.now()
    month_start = now.replace(day=1).date()
    month_end = date(now.year, now.month, monthrange(now.year, now.month)[1])
    this_month_crc = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.date >= month_start,
            models.Transaction.date <= month_end,
            models.Transaction.currency == 'CRC',
            models.Transaction.transaction_type == 'purchase'
        )
    ).scalar() or Decimal(0)

    # This month spending (USD)
    this_month_usd = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.date >= month_start,
            models.Transaction.date <= month_end,
            models.Transaction.currency == 'USD',
            models.Transaction.transaction_type == 'purchase'
        )
    ).scalar() or Decimal(0)

    # Last sync time (from most recent transaction)
    last_transaction = db.query(models.Transaction.created_at).order_by(
        models.Transaction.created_at.desc()
    ).first()
    last_sync = last_transaction[0] if last_transaction else None

    # Oldest transaction date
    oldest_transaction = db.query(models.Transaction.date).order_by(
        models.Transaction.date.asc()
    ).first()
    oldest_date = oldest_transaction[0] if oldest_transaction else None

    return schemas.DashboardSummary(
        total_transactions=total_transactions,
        total_spent_crc=total_spent_crc,
        total_spent_usd=total_spent_usd,
        total_income_crc=total_income_crc,
        total_income_usd=total_income_usd,
        active_cards=active_cards,
        uncategorized_count=uncategorized_count,
        this_month_spent_crc=this_month_crc,
        this_month_spent_usd=this_month_usd,
        last_sync=last_sync,
        oldest_transaction_date=oldest_date
    )
