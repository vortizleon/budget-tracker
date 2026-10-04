"""CRUD (Create, Read, Update, Delete) operations for database models."""
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func, extract
from typing import List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_DOWN
import calendar

from . import models, schemas


# ============================================================================
# Card CRUD Operations
# ============================================================================

def get_cards(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True) -> List[models.Card]:
    """Get list of cards."""
    query = db.query(models.Card)
    if active_only:
        query = query.filter(models.Card.is_active == True)
    return query.offset(skip).limit(limit).all()


def get_card(db: Session, card_id: int) -> Optional[models.Card]:
    """Get a single card by ID."""
    return db.query(models.Card).filter(models.Card.id == card_id).first()


def create_card(db: Session, card: schemas.CardCreate) -> models.Card:
    """Create a new card."""
    db_card = models.Card(**card.model_dump())
    db.add(db_card)
    db.commit()
    db.refresh(db_card)
    return db_card


def update_card(db: Session, card_id: int, card_update: schemas.CardUpdate) -> Optional[models.Card]:
    """Update an existing card."""
    db_card = get_card(db, card_id)
    if not db_card:
        return None

    update_data = card_update.model_dump(exclude_unset=True)

    # Check if default_category_id is being updated
    if 'default_category_id' in update_data:
        new_category_id = update_data['default_category_id']

        # Update all transactions from this card to use the new default category
        # Only update transactions that don't already have a category or have the old default
        db.query(models.Transaction).filter(
            models.Transaction.card_id == card_id,
            or_(
                models.Transaction.category_id.is_(None),
                models.Transaction.category_id == db_card.default_category_id
            )
        ).update({"category_id": new_category_id}, synchronize_session=False)

    for field, value in update_data.items():
        setattr(db_card, field, value)

    db.commit()
    db.refresh(db_card)
    return db_card


def delete_card(db: Session, card_id: int) -> bool:
    """Soft delete a card (set is_active=False)."""
    db_card = get_card(db, card_id)
    if not db_card:
        return False

    db_card.is_active = False
    db.commit()
    return True


# ============================================================================
# Category CRUD Operations
# ============================================================================

def get_categories(db: Session, skip: int = 0, limit: int = 100, category_type: Optional[str] = None) -> List[models.Category]:
    """Get list of categories."""
    query = db.query(models.Category)
    if category_type:
        query = query.filter(models.Category.category_type == category_type)
    return query.offset(skip).limit(limit).all()


def get_category(db: Session, category_id: int) -> Optional[models.Category]:
    """Get a single category by ID."""
    return db.query(models.Category).filter(models.Category.id == category_id).first()


def create_category(db: Session, category: schemas.CategoryCreate) -> models.Category:
    """Create a new category."""
    db_category = models.Category(**category.model_dump())
    db.add(db_category)
    db.commit()
    db.refresh(db_category)
    return db_category


def update_category(db: Session, category_id: int, category_update: schemas.CategoryUpdate) -> Optional[models.Category]:
    """Update an existing category."""
    db_category = get_category(db, category_id)
    if not db_category:
        return None

    update_data = category_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_category, field, value)

    db.commit()
    db.refresh(db_category)
    return db_category


def delete_category(db: Session, category_id: int) -> bool:
    """Delete a category (only if no transactions use it)."""
    db_category = get_category(db, category_id)
    if not db_category:
        return False

    # Check if category has transactions
    transaction_count = db.query(models.Transaction).filter(
        models.Transaction.category_id == category_id
    ).count()

    if transaction_count > 0:
        return False  # Can't delete category with transactions

    db.delete(db_category)
    db.commit()
    return True


# ============================================================================
# Categorization Rule CRUD Operations
# ============================================================================

def commerce_pattern_to_match(pattern: str) -> tuple[str, str]:
    """Convert a stored '%'-wildcard commerce_pattern to (match_type, value)."""
    if pattern.startswith('%') and pattern.endswith('%') and len(pattern) > 1:
        return 'contains', pattern[1:-1]
    if pattern.endswith('%'):
        return 'starts_with', pattern[:-1]
    if pattern.startswith('%'):
        return 'ends_with', pattern[1:]
    return 'exact', pattern


def match_to_commerce_pattern(match_type: str, value: str) -> str:
    """Convert a UI (match_type, value) pair to a stored commerce_pattern."""
    if match_type == 'contains':
        return f"%{value}%"
    if match_type == 'starts_with':
        return f"{value}%"
    if match_type == 'ends_with':
        return f"%{value}"
    return value  # exact (and, for now, regex - stored as-is)


def get_categorization_rules(
    db: Session,
    category_id: Optional[int] = None
) -> List[models.CategorizationRule]:
    """Get categorization rules, optionally filtered by category."""
    query = db.query(models.CategorizationRule)
    if category_id is not None:
        query = query.filter(models.CategorizationRule.category_id == category_id)
    return query.order_by(
        models.CategorizationRule.priority.desc(),
        models.CategorizationRule.id
    ).all()


def create_categorization_rule(
    db: Session,
    rule: schemas.CategorizationRuleCreate
) -> models.CategorizationRule:
    """Create a categorization rule from a (match_type, value) pair."""
    db_rule = models.CategorizationRule(
        commerce_pattern=match_to_commerce_pattern(rule.match_type, rule.value),
        category_id=rule.category_id,
        priority=rule.priority,
        is_active=rule.is_active
    )
    db.add(db_rule)
    db.commit()
    db.refresh(db_rule)
    return db_rule


def delete_categorization_rule(db: Session, rule_id: int) -> bool:
    """Delete a categorization rule."""
    db_rule = db.query(models.CategorizationRule).filter(
        models.CategorizationRule.id == rule_id
    ).first()
    if not db_rule:
        return False

    db.delete(db_rule)
    db.commit()
    return True


# ============================================================================
# Account CRUD Operations
# ============================================================================

def get_accounts(db: Session, skip: int = 0, limit: int = 100, active_only: bool = True) -> List[models.Account]:
    """Get list of accounts."""
    query = db.query(models.Account)
    if active_only:
        query = query.filter(models.Account.is_active == True)
    return query.offset(skip).limit(limit).all()


def get_account(db: Session, account_id: int) -> Optional[models.Account]:
    """Get a single account by ID."""
    return db.query(models.Account).filter(models.Account.id == account_id).first()


def create_account(db: Session, account: schemas.AccountCreate) -> models.Account:
    """Create a new account."""
    db_account = models.Account(**account.model_dump())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account


def update_account(db: Session, account_id: int, account_update: schemas.AccountUpdate) -> Optional[models.Account]:
    """Update an existing account."""
    db_account = get_account(db, account_id)
    if not db_account:
        return None

    update_data = account_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_account, field, value)

    db.commit()
    db.refresh(db_account)
    return db_account


def get_account_available_balance(db: Session, account_id: int) -> Optional[Decimal]:
    """
    Calculate available balance for an account.

    Available balance = current_balance - purchases + payments

    Args:
        db: Database session
        account_id: Account ID

    Returns:
        Decimal of available balance, or None if account not found
    """
    account = get_account(db, account_id)
    if not account:
        return None

    current_balance = account.current_balance or Decimal(0)

    # Sum purchases (money out)
    purchases = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.account_id == account_id,
            models.Transaction.currency == account.currency,
            models.Transaction.transaction_type == 'purchase'
        )
    ).scalar() or Decimal(0)

    # Sum payments (money in)
    payments = db.query(func.sum(models.Transaction.amount)).filter(
        and_(
            models.Transaction.account_id == account_id,
            models.Transaction.currency == account.currency,
            models.Transaction.transaction_type == 'payment'
        )
    ).scalar() or Decimal(0)

    # Available = current balance - purchases + payments
    return current_balance - purchases + payments


# ============================================================================
# Transaction CRUD Operations
# ============================================================================

def _apply_transaction_filters(query, filters: Optional[schemas.TransactionFilters]):
    """Apply TransactionFilters to a query selecting (or joining) Transaction."""
    if not filters:
        return query

    if filters.start_date:
        query = query.filter(models.Transaction.date >= filters.start_date)
    if filters.end_date:
        query = query.filter(models.Transaction.date <= filters.end_date)
    if filters.card_ids:
        query = query.filter(models.Transaction.card_id.in_(filters.card_ids))
    if filters.category_ids:
        query = query.filter(models.Transaction.category_id.in_(filters.category_ids))
    if filters.min_amount:
        query = query.filter(models.Transaction.amount >= filters.min_amount)
    if filters.max_amount:
        query = query.filter(models.Transaction.amount <= filters.max_amount)
    if filters.currency:
        query = query.filter(models.Transaction.currency == filters.currency)
    if filters.transaction_type:
        query = query.filter(models.Transaction.transaction_type == filters.transaction_type)
    if filters.is_reconciled is not None:
        query = query.filter(models.Transaction.is_reconciled == filters.is_reconciled)
    if filters.search:
        query = query.filter(
            models.Transaction.commerce_name.ilike(f"%{filters.search}%")
        )

    return query


def get_transactions(
    db: Session,
    filters: Optional[schemas.TransactionFilters] = None
) -> tuple[List[models.Transaction], int]:
    """
    Get filtered list of transactions with count.

    Returns:
        Tuple of (transactions, total_count)
    """
    query = db.query(models.Transaction).options(
        joinedload(models.Transaction.card),
        joinedload(models.Transaction.category),
        joinedload(models.Transaction.account)
    )
    query = _apply_transaction_filters(query, filters)

    # Order by date desc (must be done before pagination)
    query = query.order_by(models.Transaction.date.desc(), models.Transaction.created_at.desc())

    # Get total count before pagination
    total_count = query.count()

    # Apply pagination
    if filters:
        query = query.offset(filters.skip).limit(filters.limit)

    return query.all(), total_count


def get_transactions_totals(
    db: Session,
    filters: Optional[schemas.TransactionFilters] = None
) -> dict:
    """
    Sum amount and count matching transactions grouped by currency, ignoring
    pagination - used to show a filtered total (e.g. "all Uber transactions")
    rather than just the sum of the current page.

    Returns:
        Dict of {currency: {"total": Decimal, "count": int}}
    """
    query = db.query(
        models.Transaction.currency,
        func.sum(models.Transaction.amount).label('total'),
        func.count(models.Transaction.id).label('count')
    )
    query = _apply_transaction_filters(query, filters)
    query = query.group_by(models.Transaction.currency)

    return {
        row.currency: {'total': row.total, 'count': row.count}
        for row in query.all()
    }


def get_transaction(db: Session, transaction_id: int) -> Optional[models.Transaction]:
    """Get a single transaction by ID."""
    return db.query(models.Transaction).options(
        joinedload(models.Transaction.card),
        joinedload(models.Transaction.category),
        joinedload(models.Transaction.account)
    ).filter(models.Transaction.id == transaction_id).first()


def match_category_rule(db: Session, commerce_name: Optional[str]) -> Optional[int]:
    """Category of the first active categorization rule matching `commerce_name`
    (highest priority first), same matching as the Gmail sync: '%x%' contains,
    'x%' starts with, '%x' ends with, bare 'x' exact - all case-insensitive."""
    if not commerce_name:
        return None
    name = commerce_name.strip().upper()
    rules = db.query(models.CategorizationRule).filter(
        models.CategorizationRule.is_active == True
    ).order_by(models.CategorizationRule.priority.desc()).all()
    for rule in rules:
        pattern = rule.commerce_pattern.strip().upper()
        if pattern.startswith('%') and pattern.endswith('%') and len(pattern) > 1:
            if pattern[1:-1] in name:
                return rule.category_id
        elif pattern.endswith('%'):
            if name.startswith(pattern[:-1]):
                return rule.category_id
        elif pattern.startswith('%'):
            if name.endswith(pattern[1:]):
                return rule.category_id
        elif name == pattern:
            return rule.category_id
    return None


def create_transaction(db: Session, transaction: schemas.TransactionCreate) -> models.Transaction:
    """Create a new transaction. With no category given it is picked the way synced
    ones are: a matching categorization rule first, then the card's default category."""
    data = transaction.model_dump()
    if data.get("category_id") is None:
        category_id = match_category_rule(db, data.get("commerce_name"))
        if category_id is None and data.get("card_id") is not None:
            card = db.query(models.Card).filter(models.Card.id == data["card_id"]).first()
            category_id = card.default_category_id if card else None
        data["category_id"] = category_id
    db_transaction = models.Transaction(**data)
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


def update_transaction(
    db: Session,
    transaction_id: int,
    transaction_update: schemas.TransactionUpdate
) -> Optional[models.Transaction]:
    """Update an existing transaction."""
    db_transaction = get_transaction(db, transaction_id)
    if not db_transaction:
        return None

    update_data = transaction_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_transaction, field, value)

    db_transaction.updated_at = datetime.now()
    db.commit()
    db.refresh(db_transaction)
    return db_transaction


def delete_transaction(db: Session, transaction_id: int) -> bool:
    """Delete a transaction."""
    db_transaction = get_transaction(db, transaction_id)
    if not db_transaction:
        return False

    db.delete(db_transaction)
    db.commit()
    return True


def bulk_categorize(db: Session, transaction_ids: List[int], category_id: int) -> int:
    """Bulk categorize transactions. Returns count of updated transactions."""
    updated = db.query(models.Transaction).filter(
        models.Transaction.id.in_(transaction_ids)
    ).update(
        {
            models.Transaction.category_id: category_id,
            models.Transaction.updated_at: datetime.now()
        },
        synchronize_session=False
    )
    db.commit()
    return updated


# ============================================================================
# Email Source CRUD Operations
# ============================================================================

def get_email_sources(db: Session, active_only: bool = True) -> List[models.EmailSource]:
    """Get list of email sources."""
    query = db.query(models.EmailSource)
    if active_only:
        query = query.filter(models.EmailSource.is_active == True)
    return query.all()


def get_email_source(db: Session, source_id: int) -> Optional[models.EmailSource]:
    """Get a single email source by ID."""
    return db.query(models.EmailSource).filter(models.EmailSource.id == source_id).first()


def create_email_source(db: Session, source: schemas.EmailSourceCreate) -> models.EmailSource:
    """Create a new email source."""
    db_source = models.EmailSource(**source.model_dump())
    db.add(db_source)
    db.commit()
    db.refresh(db_source)
    return db_source


def update_email_source(
    db: Session,
    source_id: int,
    source_update: schemas.EmailSourceUpdate
) -> Optional[models.EmailSource]:
    """Update an existing email source."""
    db_source = get_email_source(db, source_id)
    if not db_source:
        return None

    update_data = source_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_source, field, value)

    db.commit()
    db.refresh(db_source)
    return db_source


# ============================================================================
# Subscription CRUD Operations
# ============================================================================

def get_subscriptions(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    currency: Optional[str] = None
) -> List[models.Subscription]:
    """Get list of subscriptions."""
    query = db.query(models.Subscription)
    if active_only:
        query = query.filter(models.Subscription.is_active == True)
    if currency:
        query = query.filter(models.Subscription.currency == currency)
    return query.order_by(models.Subscription.billing_day).offset(skip).limit(limit).all()


def get_subscription(db: Session, subscription_id: int) -> Optional[models.Subscription]:
    """Get a single subscription by ID."""
    return db.query(models.Subscription).filter(models.Subscription.id == subscription_id).first()


def create_subscription(db: Session, subscription: schemas.SubscriptionCreate) -> models.Subscription:
    """Create a new subscription."""
    db_subscription = models.Subscription(**subscription.model_dump())
    db.add(db_subscription)
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


def update_subscription(
    db: Session,
    subscription_id: int,
    subscription_update: schemas.SubscriptionUpdate
) -> Optional[models.Subscription]:
    """Update an existing subscription."""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return None

    update_data = subscription_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_subscription, field, value)

    db_subscription.updated_at = datetime.now()
    db.commit()
    db.refresh(db_subscription)
    return db_subscription


def delete_subscription(db: Session, subscription_id: int) -> bool:
    """Soft delete a subscription (set is_active=False)."""
    db_subscription = get_subscription(db, subscription_id)
    if not db_subscription:
        return False

    db_subscription.is_active = False
    db.commit()
    return True


# ============================================================================
# Installment Plan CRUD Operations ("tasa cero")
# ============================================================================

def _add_months(year: int, month: int, n: int) -> tuple[int, int]:
    """Add n months to a (year, month) pair, returning the new pair."""
    total = (year * 12 + (month - 1)) + n
    return total // 12, total % 12 + 1


def create_installment_plan(
    db: Session,
    plan_data: schemas.InstallmentPlanCreate
) -> models.InstallmentPlan:
    """
    Create an installment plan and eagerly generate Transaction rows for
    installments starting_installment_number..num_installments (dated and
    amounted up front - there's no scheduler in this app to create them
    later). total_amount is split only across the GENERATED rows, so for a
    plan already in progress elsewhere, pass the remaining balance and a
    starting_installment_number > 1 - earlier installments aren't
    regenerated. The last row absorbs any rounding remainder so the
    generated rows always sum to exactly total_amount.
    """
    if plan_data.starting_installment_number > plan_data.num_installments:
        raise ValueError("starting_installment_number can't be greater than num_installments")

    plan = models.InstallmentPlan(
        description=plan_data.description,
        total_amount=plan_data.total_amount,
        currency=plan_data.currency,
        num_installments=plan_data.num_installments,
        starting_installment_number=plan_data.starting_installment_number,
        charge_day=plan_data.charge_day,
        card_id=plan_data.card_id,
        category_id=plan_data.category_id,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    rows_to_generate = plan_data.num_installments - plan_data.starting_installment_number + 1
    start_year, start_month = (int(p) for p in plan_data.first_charge_month.split('-'))
    base_amount = (plan_data.total_amount / rows_to_generate).quantize(
        Decimal('0.01'), rounding=ROUND_DOWN
    )
    last_amount = plan_data.total_amount - base_amount * (rows_to_generate - 1)

    for i in range(rows_to_generate):
        year, month = _add_months(start_year, start_month, i)
        day = min(plan_data.charge_day, calendar.monthrange(year, month)[1])
        is_last = i == rows_to_generate - 1
        installment_number = plan_data.starting_installment_number + i

        db.add(models.Transaction(
            date=date(year, month, day),
            amount=last_amount if is_last else base_amount,
            currency=plan_data.currency,
            commerce_name=f"{plan_data.description} (Tasa Cero {installment_number}/{plan_data.num_installments})",
            description=f"Tasa Cero installment {installment_number} of {plan_data.num_installments}",
            transaction_type='purchase',
            card_id=plan_data.card_id,
            category_id=plan_data.category_id,
            installment_plan_id=plan.id,
            installment_number=installment_number,
        ))

    db.commit()
    return plan


def _installment_plan_to_response(db: Session, plan: models.InstallmentPlan) -> schemas.InstallmentPlanResponse:
    generated_paid = db.query(func.count(models.Transaction.id)).filter(
        models.Transaction.installment_plan_id == plan.id,
        models.Transaction.date <= date.today()
    ).scalar() or 0
    # Installments before starting_installment_number were already paid
    # elsewhere (no row was generated for them), so they count too.
    paid = (plan.starting_installment_number - 1) + generated_paid
    return schemas.InstallmentPlanResponse(
        id=plan.id,
        description=plan.description,
        total_amount=plan.total_amount,
        currency=plan.currency,
        num_installments=plan.num_installments,
        starting_installment_number=plan.starting_installment_number,
        charge_day=plan.charge_day,
        card_id=plan.card_id,
        category_id=plan.category_id,
        created_at=plan.created_at,
        installments_paid=paid,
    )


def get_installment_plans(db: Session) -> List[schemas.InstallmentPlanResponse]:
    """Get all installment plans, most recently created first."""
    plans = db.query(models.InstallmentPlan).order_by(
        models.InstallmentPlan.created_at.desc()
    ).all()
    return [_installment_plan_to_response(db, p) for p in plans]


def delete_installment_plan(db: Session, plan_id: int) -> bool:
    """Delete an installment plan and all of its generated transactions."""
    plan = db.query(models.InstallmentPlan).filter(models.InstallmentPlan.id == plan_id).first()
    if not plan:
        return False

    db.query(models.Transaction).filter(
        models.Transaction.installment_plan_id == plan_id
    ).delete()
    db.delete(plan)
    db.commit()
    return True


# ============================================================================
# Credit Card Billing Cycles
# ============================================================================

def get_billing_cycle_for_date(txn_date: date, cutoff_day: int) -> tuple[date, date, date]:
    """
    Given a transaction date and a card's statement cutoff day, return
    (cycle_start, cycle_end, due_date).

    Convention: the cutoff day OPENS the next cycle (confirmed against the
    user's real card) - a purchase on or after the cutoff day starts a new
    cycle running through the day before next month's cutoff; a purchase
    before the cutoff day belongs to the cycle that opened the previous
    month. The due date is the 1st of the month after the cycle ends.
    e.g. cutoff=18: a purchase on Jan 18 (or Jan 19, or Feb 17) falls in the
    Jan18-Feb17 cycle, due Mar 1.
    """
    if txn_date.day >= cutoff_day:
        start_year, start_month = txn_date.year, txn_date.month
    else:
        start_year, start_month = _add_months(txn_date.year, txn_date.month, -1)

    start_day = min(cutoff_day, calendar.monthrange(start_year, start_month)[1])
    cycle_start = date(start_year, start_month, start_day)

    end_year, end_month = _add_months(start_year, start_month, 1)
    end_cutoff_day = min(cutoff_day, calendar.monthrange(end_year, end_month)[1])
    cycle_end = date(end_year, end_month, end_cutoff_day) - timedelta(days=1)

    due_year, due_month = _add_months(cycle_end.year, cycle_end.month, 1)
    due_date = date(due_year, due_month, 1)

    return cycle_start, cycle_end, due_date


def get_card_billing_cycles(db: Session, card_id: int, cutoff_day: int) -> List[schemas.CardBillingCycle]:
    """
    Group a card's purchase transactions into statement cycles based on its
    cutoff day, with each cycle's totals and due date. Covers every cycle
    that has at least one transaction, plus the current in-progress one.
    """
    transactions = db.query(models.Transaction).filter(
        models.Transaction.card_id == card_id,
        models.Transaction.transaction_type == 'purchase'
    ).all()

    today = date.today()
    cycles = {}  # cycle_end -> {cycle_start, due_date, total_crc, total_usd, count}

    for txn in transactions:
        cycle_start, cycle_end, due_date = get_billing_cycle_for_date(txn.date, cutoff_day)
        bucket = cycles.setdefault(cycle_end, {
            'cycle_start': cycle_start, 'due_date': due_date,
            'total_crc': Decimal(0), 'total_usd': Decimal(0), 'count': 0
        })
        bucket['count'] += 1
        if txn.currency == 'CRC':
            bucket['total_crc'] += txn.amount
        else:
            bucket['total_usd'] += txn.amount

    # Make sure the current (possibly empty) cycle always shows up
    current_start, current_end, current_due = get_billing_cycle_for_date(today, cutoff_day)
    cycles.setdefault(current_end, {
        'cycle_start': current_start, 'due_date': current_due,
        'total_crc': Decimal(0), 'total_usd': Decimal(0), 'count': 0
    })

    return [
        schemas.CardBillingCycle(
            cycle_start=data['cycle_start'],
            cycle_end=cycle_end,
            due_date=data['due_date'],
            is_current=(cycle_end == current_end),
            total_crc=data['total_crc'],
            total_usd=data['total_usd'],
            transaction_count=data['count'],
        )
        for cycle_end, data in sorted(cycles.items(), reverse=True)
    ]
