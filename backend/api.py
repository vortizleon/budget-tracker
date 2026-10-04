"""FastAPI application with REST API endpoints."""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from starlette.requests import Request
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field

from . import models, schemas, crud, analytics, budgets, payoff, forecast, gmail_client
from .database import get_db, init_db
from .sync import TransactionSyncer

# Initialize FastAPI app
app = FastAPI(
    title="Budgeting App API",
    description="Personal budgeting and expense tracking application",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static files and templates
BASE_DIR = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "frontend" / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "frontend" / "templates"))


# ============================================================================
# Root & Frontend Routes
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize database on startup."""
    init_db()


# Each sidebar view has its own URL (/budgets, /analytics, ...) so reloading
# or sharing a link keeps you on that view - they all serve the same page and
# app.js picks the view from the path. Keep in sync with VIEWS in app.js.
SPA_VIEWS = ["budgets", "transactions", "analytics", "forecast", "categories", "cards", "settings"]


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main SPA page."""
    return templates.TemplateResponse("index.html", {"request": request})


for _view in SPA_VIEWS:
    app.add_api_route(f"/{_view}", read_root, methods=["GET"], response_class=HTMLResponse, include_in_schema=False)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now()}


# ============================================================================
# Card Endpoints
# ============================================================================

@app.get("/api/cards", response_model=List[schemas.CardResponse])
async def get_cards(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get list of cards."""
    cards = crud.get_cards(db, skip=skip, limit=limit, active_only=active_only)

    # Add spending totals to each card
    card_responses = []
    for card in cards:
        # Calculate totals
        spent_crc = sum(
            t.amount for t in card.transactions
            if t.currency == "CRC" and t.transaction_type == "purchase"
        )
        spent_usd = sum(
            t.amount for t in card.transactions
            if t.currency == "USD" and t.transaction_type == "purchase"
        )

        # Calculate utilization
        util_crc = None
        if card.credit_limit_crc and card.credit_limit_crc > 0:
            util_crc = float((spent_crc / card.credit_limit_crc) * 100)

        util_usd = None
        if card.credit_limit_usd and card.credit_limit_usd > 0:
            util_usd = float((spent_usd / card.credit_limit_usd) * 100)

        card_response = schemas.CardResponse.model_validate(card)
        card_response.total_spent_crc = spent_crc
        card_response.total_spent_usd = spent_usd
        card_response.utilization_crc = round(util_crc, 2) if util_crc else None
        card_response.utilization_usd = round(util_usd, 2) if util_usd else None

        card_responses.append(card_response)

    return card_responses


@app.get("/api/cards/{card_id}", response_model=schemas.CardResponse)
async def get_card(card_id: int, db: Session = Depends(get_db)):
    """Get a single card by ID."""
    card = crud.get_card(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


@app.post("/api/cards", response_model=schemas.CardResponse, status_code=201)
async def create_card(card: schemas.CardCreate, db: Session = Depends(get_db)):
    """Create a new card."""
    return crud.create_card(db, card)


@app.put("/api/cards/{card_id}", response_model=schemas.CardResponse)
async def update_card(
    card_id: int,
    card_update: schemas.CardUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a card.

    When updating default_category_id, all transactions from this card
    that are uncategorized or using the old default will be updated
    to use the new default category.
    """
    updated_card = crud.update_card(db, card_id, card_update)
    if not updated_card:
        raise HTTPException(status_code=404, detail="Card not found")
    return updated_card


@app.delete("/api/cards/{card_id}", status_code=204)
async def delete_card(card_id: int, db: Session = Depends(get_db)):
    """Soft delete a card."""
    success = crud.delete_card(db, card_id)
    if not success:
        raise HTTPException(status_code=404, detail="Card not found")


# ============================================================================
# Category Endpoints
# ============================================================================

@app.get("/api/categories", response_model=List[schemas.CategoryResponse])
async def get_categories(
    skip: int = 0,
    limit: int = 100,
    category_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of categories."""
    categories = crud.get_categories(db, skip=skip, limit=limit, category_type=category_type)

    # Add transaction counts
    category_responses = []
    for category in categories:
        cat_response = schemas.CategoryResponse.model_validate(category)
        cat_response.transaction_count = len(category.transactions)
        cat_response.total_amount = sum(t.amount for t in category.transactions)
        category_responses.append(cat_response)

    return category_responses


@app.get("/api/categories/{category_id}", response_model=schemas.CategoryResponse)
async def get_category(category_id: int, db: Session = Depends(get_db)):
    """Get a single category by ID."""
    category = crud.get_category(db, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@app.post("/api/categories", response_model=schemas.CategoryResponse, status_code=201)
async def create_category(category: schemas.CategoryCreate, db: Session = Depends(get_db)):
    """Create a new category."""
    return crud.create_category(db, category)


@app.put("/api/categories/{category_id}", response_model=schemas.CategoryResponse)
async def update_category(
    category_id: int,
    category_update: schemas.CategoryUpdate,
    db: Session = Depends(get_db)
):
    """Update a category."""
    updated_category = crud.update_category(db, category_id, category_update)
    if not updated_category:
        raise HTTPException(status_code=404, detail="Category not found")
    return updated_category


@app.delete("/api/categories/{category_id}", status_code=204)
async def delete_category(category_id: int, db: Session = Depends(get_db)):
    """Delete a category (only if no transactions use it)."""
    success = crud.delete_category(db, category_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete category with existing transactions"
        )


# ============================================================================
# Categorization Rule Endpoints
# ============================================================================

def _rule_to_response(rule: models.CategorizationRule) -> schemas.CategorizationRuleResponse:
    match_type, value = crud.commerce_pattern_to_match(rule.commerce_pattern)
    return schemas.CategorizationRuleResponse(
        id=rule.id,
        match_type=match_type,
        value=value,
        category_id=rule.category_id,
        priority=rule.priority,
        is_active=rule.is_active,
        created_at=rule.created_at
    )


@app.get("/api/categorization-rules", response_model=List[schemas.CategorizationRuleResponse])
async def get_categorization_rules(category_id: Optional[int] = None, db: Session = Depends(get_db)):
    """Get categorization rules, optionally filtered by category."""
    rules = crud.get_categorization_rules(db, category_id=category_id)
    return [_rule_to_response(r) for r in rules]


@app.post("/api/categorization-rules", response_model=schemas.CategorizationRuleResponse, status_code=201)
async def create_categorization_rule(rule: schemas.CategorizationRuleCreate, db: Session = Depends(get_db)):
    """Create a categorization rule."""
    db_rule = crud.create_categorization_rule(db, rule)
    return _rule_to_response(db_rule)


@app.delete("/api/categorization-rules/{rule_id}", status_code=204)
async def delete_categorization_rule(rule_id: int, db: Session = Depends(get_db)):
    """Delete a categorization rule."""
    if not crud.delete_categorization_rule(db, rule_id):
        raise HTTPException(status_code=404, detail="Rule not found")


# ============================================================================
# Account Endpoints
# ============================================================================

@app.get("/api/accounts", response_model=List[schemas.AccountResponse])
async def get_accounts(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    include_balances: bool = Query(True, description="Include calculated available balance"),
    db: Session = Depends(get_db)
):
    """Get list of accounts with optional balance calculations."""
    accounts = crud.get_accounts(db, skip=skip, limit=limit, active_only=active_only)

    if include_balances:
        account_responses = []
        for account in accounts:
            acc_response = schemas.AccountResponse.model_validate(account)
            acc_response.available_balance = crud.get_account_available_balance(db, account.id)
            account_responses.append(acc_response)
        return account_responses

    return [schemas.AccountResponse.model_validate(acc) for acc in accounts]


@app.get("/api/accounts/{account_id}", response_model=schemas.AccountResponse)
async def get_account(
    account_id: int,
    include_balance: bool = Query(True, description="Include calculated available balance"),
    db: Session = Depends(get_db)
):
    """Get a single account by ID with optional balance calculation."""
    account = crud.get_account(db, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    acc_response = schemas.AccountResponse.model_validate(account)
    if include_balance:
        acc_response.available_balance = crud.get_account_available_balance(db, account.id)

    return acc_response


@app.post("/api/accounts", response_model=schemas.AccountResponse, status_code=201)
async def create_account(account: schemas.AccountCreate, db: Session = Depends(get_db)):
    """Create a new account."""
    return crud.create_account(db, account)


@app.put("/api/accounts/{account_id}", response_model=schemas.AccountResponse)
async def update_account(
    account_id: int,
    account_update: schemas.AccountUpdate,
    db: Session = Depends(get_db)
):
    """Update an account."""
    updated_account = crud.update_account(db, account_id, account_update)
    if not updated_account:
        raise HTTPException(status_code=404, detail="Account not found")
    return updated_account


@app.get("/api/balances/summary", response_model=schemas.BalanceSummary)
async def get_balance_summary(db: Session = Depends(get_db)):
    """
    Get comprehensive balance summary for all accounts.

    Provides two-panel view:
    - Panel 1: Manual balances (what user set)
    - Panel 2: Available balances (after pending transactions)

    Separates savings accounts as 'do not touch' money.
    """
    accounts = crud.get_accounts(db, active_only=True)

    account_details = []
    savings_details = []
    total_manual_crc = Decimal(0)
    total_manual_usd = Decimal(0)
    total_available_crc = Decimal(0)
    total_available_usd = Decimal(0)

    for account in accounts:
        manual_balance = account.current_balance or Decimal(0)
        available_balance = crud.get_account_available_balance(db, account.id) or Decimal(0)

        detail = schemas.AccountBalanceDetail(
            account_id=account.id,
            account_name=account.name,
            account_type=account.account_type,
            currency=account.currency,
            manual_balance=manual_balance,
            available_balance=available_balance,
            pending_amount=manual_balance - available_balance
        )

        if account.account_type == "savings":
            savings_details.append(detail)
        else:
            account_details.append(detail)
            if account.currency == "CRC":
                total_manual_crc += manual_balance
                total_available_crc += available_balance
            elif account.currency == "USD":
                total_manual_usd += manual_balance
                total_available_usd += available_balance

    return schemas.BalanceSummary(
        accounts=account_details,
        total_manual_crc=total_manual_crc,
        total_manual_usd=total_manual_usd,
        total_available_crc=total_available_crc,
        total_available_usd=total_available_usd,
        savings_accounts=savings_details
    )


# ============================================================================
# Transaction Endpoints
# ============================================================================

@app.get("/api/transactions")
async def get_transactions(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    card_ids: Optional[str] = None,  # Comma-separated IDs
    category_ids: Optional[str] = None,  # Comma-separated IDs
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    currency: Optional[str] = None,
    transaction_type: Optional[str] = None,
    search: Optional[str] = None,
    is_reconciled: Optional[bool] = None,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get filtered list of transactions."""
    # Parse comma-separated IDs
    card_id_list = [int(id) for id in card_ids.split(",")] if card_ids else None
    category_id_list = [int(id) for id in category_ids.split(",")] if category_ids else None

    # Create filters object
    filters = schemas.TransactionFilters(
        start_date=start_date,
        end_date=end_date,
        card_ids=card_id_list,
        category_ids=category_id_list,
        min_amount=min_amount,
        max_amount=max_amount,
        currency=currency,
        transaction_type=transaction_type,
        search=search,
        is_reconciled=is_reconciled,
        skip=skip,
        limit=limit
    )

    transactions, total = crud.get_transactions(db, filters)
    totals_by_currency = crud.get_transactions_totals(db, filters)

    # Convert to response objects
    transaction_responses = []
    for transaction in transactions:
        trans_response = schemas.TransactionResponse.model_validate(transaction)
        if transaction.card:
            trans_response.card = schemas.CardResponse.model_validate(transaction.card)
        if transaction.category:
            trans_response.category = schemas.CategoryResponse.model_validate(transaction.category)
        if transaction.account:
            trans_response.account = schemas.AccountResponse.model_validate(transaction.account)
        transaction_responses.append(trans_response)

    return {
        "transactions": transaction_responses,
        "total": total,
        "skip": skip,
        "limit": limit,
        "totals_by_currency": totals_by_currency
    }


@app.get("/api/transactions/{transaction_id}", response_model=schemas.TransactionResponse)
async def get_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Get a single transaction by ID."""
    transaction = crud.get_transaction(db, transaction_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@app.post("/api/transactions", response_model=schemas.TransactionResponse, status_code=201)
async def create_transaction(
    transaction: schemas.TransactionCreate,
    db: Session = Depends(get_db)
):
    """Create a new transaction."""
    return crud.create_transaction(db, transaction)


@app.put("/api/transactions/{transaction_id}", response_model=schemas.TransactionResponse)
async def update_transaction(
    transaction_id: int,
    transaction_update: schemas.TransactionUpdate,
    db: Session = Depends(get_db)
):
    """Update a transaction."""
    updated_transaction = crud.update_transaction(db, transaction_id, transaction_update)
    if not updated_transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return updated_transaction


@app.delete("/api/transactions/{transaction_id}", status_code=204)
async def delete_transaction(transaction_id: int, db: Session = Depends(get_db)):
    """Delete a transaction."""
    success = crud.delete_transaction(db, transaction_id)
    if not success:
        raise HTTPException(status_code=404, detail="Transaction not found")


@app.patch("/api/transactions/bulk-categorize")
async def bulk_categorize_transactions(
    bulk_request: schemas.BulkCategorizeRequest,
    db: Session = Depends(get_db)
):
    """Bulk categorize transactions."""
    updated_count = crud.bulk_categorize(
        db,
        bulk_request.transaction_ids,
        bulk_request.category_id
    )
    return {"updated": updated_count}


# ============================================================================
# Analytics Endpoints
# ============================================================================

@app.get("/api/analytics/spending-by-category", response_model=List[schemas.SpendingByCategory])
async def get_spending_by_category(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get spending breakdown by category."""
    return analytics.get_spending_by_category(
        db,
        start_date=start_date,
        end_date=end_date,
        currency=currency
    )


@app.get("/api/analytics/daily-spending", response_model=List[schemas.DailySpending])
async def get_daily_spending(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: str = "CRC",
    db: Session = Depends(get_db)
):
    """Get daily spending totals over a date range."""
    return analytics.get_daily_spending(
        db,
        start_date=start_date,
        end_date=end_date,
        currency=currency
    )


@app.get("/api/analytics/monthly-trends", response_model=List[schemas.MonthlyTrend])
async def get_monthly_trends(
    months_back: int = 6,
    currency: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get monthly spending trends."""
    return analytics.get_monthly_trends(db, months_back=months_back, currency=currency)


@app.get("/api/analytics/top-merchants", response_model=List[schemas.TopMerchant])
async def get_top_merchants(
    limit: int = 10,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    currency: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get top merchants by spending."""
    return analytics.get_top_merchants(
        db,
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        currency=currency
    )


@app.get("/api/analytics/card-utilization", response_model=List[schemas.CardUtilization])
async def get_card_utilization(db: Session = Depends(get_db)):
    """Get credit card utilization statistics."""
    return analytics.get_card_utilization(db)


@app.get("/api/analytics/month-forecast", response_model=schemas.MonthForecast)
async def get_month_forecast(db: Session = Depends(get_db)):
    """Projected month-end spending per category at the current pace."""
    return forecast.get_month_forecast(db)


@app.get("/api/analytics/dashboard-summary", response_model=schemas.DashboardSummary)
async def get_dashboard_summary(db: Session = Depends(get_db)):
    """Get dashboard summary statistics."""
    return analytics.get_dashboard_summary(db)


# ============================================================================
# Email Source Endpoints
# ============================================================================

@app.get("/api/email-sources", response_model=List[schemas.EmailSourceResponse])
async def get_email_sources(active_only: bool = True, db: Session = Depends(get_db)):
    """Get list of email sources."""
    return crud.get_email_sources(db, active_only=active_only)


@app.post("/api/email-sources", response_model=schemas.EmailSourceResponse, status_code=201)
async def create_email_source(
    source: schemas.EmailSourceCreate,
    db: Session = Depends(get_db)
):
    """Create a new email source."""
    return crud.create_email_source(db, source)


@app.put("/api/email-sources/{source_id}", response_model=schemas.EmailSourceResponse)
async def update_email_source(
    source_id: int,
    source_update: schemas.EmailSourceUpdate,
    db: Session = Depends(get_db)
):
    """Update an email source."""
    updated_source = crud.update_email_source(db, source_id, source_update)
    if not updated_source:
        raise HTTPException(status_code=404, detail="Email source not found")
    return updated_source


# ============================================================================
# Installment Plan Endpoints ("tasa cero")
# ============================================================================

@app.get("/api/installment-plans", response_model=List[schemas.InstallmentPlanResponse])
async def get_installment_plans(db: Session = Depends(get_db)):
    """Get all installment plans."""
    return crud.get_installment_plans(db)


@app.post("/api/installment-plans", response_model=schemas.InstallmentPlanResponse, status_code=201)
async def create_installment_plan(plan: schemas.InstallmentPlanCreate, db: Session = Depends(get_db)):
    """Create an installment plan - generates all of its monthly charges immediately."""
    db_plan = crud.create_installment_plan(db, plan)
    return crud._installment_plan_to_response(db, db_plan)


@app.delete("/api/installment-plans/{plan_id}", status_code=204)
async def delete_installment_plan(plan_id: int, db: Session = Depends(get_db)):
    """Delete an installment plan and all of its generated transactions."""
    if not crud.delete_installment_plan(db, plan_id):
        raise HTTPException(status_code=404, detail="Installment plan not found")


# ============================================================================
# Budget & Income Endpoints
# ============================================================================

def _check_month(month: Optional[str]) -> None:
    try:
        budgets.parse_month(month)
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM")


@app.get("/api/budgets", response_model=schemas.BudgetOverview)
async def get_budget_overview(month: Optional[str] = None, db: Session = Depends(get_db)):
    """Budgets, income and spending for a month ("YYYY-MM", default: current).
    The first call ever also seeds the suggested budgets."""
    _check_month(month)
    return budgets.get_overview(db, month)


@app.put("/api/budgets")
async def upsert_budget(data: schemas.BudgetUpsert, db: Session = Depends(get_db)):
    """Create or update a category's budget (by % of income or fixed amount)."""
    try:
        budget = budgets.upsert_budget(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"id": budget.id}


@app.patch("/api/budgets/{budget_id}", status_code=204)
async def set_budget_protected(budget_id: int, data: schemas.BudgetProtectedUpdate, db: Session = Depends(get_db)):
    """Lock/unlock a budget against being reduced for debt payments."""
    if not budgets.set_protected(db, budget_id, data.is_protected):
        raise HTTPException(status_code=404, detail="Budget not found")


@app.delete("/api/budgets/{budget_id}", status_code=204)
async def delete_budget(budget_id: int, db: Session = Depends(get_db)):
    """Remove a category's budget."""
    if not budgets.delete_budget(db, budget_id):
        raise HTTPException(status_code=404, detail="Budget not found")


@app.post("/api/budgets/reset-suggested")
async def reset_budgets_to_suggested(db: Session = Depends(get_db)):
    """Replace all budgets with the suggested starting percentages."""
    return {"budgets": budgets.reset_to_suggested(db)}


@app.put("/api/budget-settings", response_model=schemas.BudgetSettingsResponse)
async def update_budget_settings(update: schemas.BudgetSettingsUpdate, db: Session = Depends(get_db)):
    """Update expected monthly income and/or the USD->CRC rate."""
    return budgets.update_settings(db, update)


@app.post("/api/income", response_model=schemas.IncomeEntryResponse, status_code=201)
async def create_income(data: schemas.IncomeEntryCreate, db: Session = Depends(get_db)):
    """Log a received payment."""
    try:
        return budgets.create_income(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.delete("/api/income/{income_id}", status_code=204)
async def delete_income(income_id: int, db: Session = Depends(get_db)):
    """Delete a logged payment."""
    if not budgets.delete_income(db, income_id):
        raise HTTPException(status_code=404, detail="Income entry not found")


# ============================================================================
# Card Billing Cycle Endpoints
# ============================================================================

@app.get("/api/cards/{card_id}/billing-cycles", response_model=List[schemas.CardBillingCycle])
async def get_card_billing_cycles(card_id: int, db: Session = Depends(get_db)):
    """Group a card's purchases into statement cycles based on its cutoff day."""
    card = crud.get_card(db, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    if not card.cutoff_day:
        raise HTTPException(status_code=400, detail="Card has no cutoff day set")
    return crud.get_card_billing_cycles(db, card_id, card.cutoff_day)


@app.get("/api/cards/{card_id}/payoff-plan", response_model=schemas.CardPayoffPlanResponse)
async def get_card_payoff_plan(card_id: int, db: Session = Depends(get_db)):
    """A card's saved payoff plan (if any) and its recent monthly spend."""
    if not crud.get_card(db, card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    return payoff.get_plan(db, card_id)


@app.put("/api/cards/{card_id}/payoff-plan", response_model=schemas.CardPayoffPlanResponse)
async def save_card_payoff_plan(
    card_id: int,
    data: schemas.CardPayoffPlanUpdate,
    db: Session = Depends(get_db)
):
    """Create or replace a card's payoff plan."""
    if not crud.get_card(db, card_id):
        raise HTTPException(status_code=404, detail="Card not found")
    return payoff.save_plan(db, card_id, data)


@app.delete("/api/cards/{card_id}/payoff-plan", status_code=204)
async def delete_card_payoff_plan(card_id: int, db: Session = Depends(get_db)):
    """Delete a card's payoff plan."""
    if not payoff.delete_plan(db, card_id):
        raise HTTPException(status_code=404, detail="Payoff plan not found")


# ============================================================================
# Subscription Endpoints
# ============================================================================

@app.get("/api/subscriptions", response_model=List[schemas.SubscriptionResponse])
async def get_subscriptions(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    currency: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of subscriptions."""
    return crud.get_subscriptions(db, skip=skip, limit=limit, active_only=active_only, currency=currency)


@app.get("/api/subscriptions/{subscription_id}", response_model=schemas.SubscriptionResponse)
async def get_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """Get a single subscription by ID."""
    subscription = crud.get_subscription(db, subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return subscription


@app.post("/api/subscriptions", response_model=schemas.SubscriptionResponse, status_code=201)
async def create_subscription(
    subscription: schemas.SubscriptionCreate,
    db: Session = Depends(get_db)
):
    """Create a new subscription."""
    return crud.create_subscription(db, subscription)


@app.put("/api/subscriptions/{subscription_id}", response_model=schemas.SubscriptionResponse)
async def update_subscription(
    subscription_id: int,
    subscription_update: schemas.SubscriptionUpdate,
    db: Session = Depends(get_db)
):
    """Update a subscription."""
    updated = crud.update_subscription(db, subscription_id, subscription_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return updated


@app.delete("/api/subscriptions/{subscription_id}", status_code=204)
async def delete_subscription(subscription_id: int, db: Session = Depends(get_db)):
    """Soft delete a subscription."""
    if not crud.delete_subscription(db, subscription_id):
        raise HTTPException(status_code=404, detail="Subscription not found")


# ============================================================================
# Sync Endpoint
# ============================================================================

@app.post("/api/sync/trigger", response_model=schemas.SyncResponse)
async def trigger_sync(
    sync_request: schemas.SyncRequest,
    db: Session = Depends(get_db)
):
    """Trigger Gmail sync - either a rolling N-day window (days_back) or an
    explicit start_date/end_date backfill, same as `finance-app sync`."""
    email_sources = crud.get_email_sources(db, active_only=True)

    if not email_sources:
        return schemas.SyncResponse(
            success=False,
            message="No email sources configured",
            new_transactions=0,
            skipped_duplicates=0,
            sources_synced=0,
            errors=["No active email sources found"]
        )

    try:
        after_date = datetime.strptime(sync_request.start_date, "%Y-%m-%d") if sync_request.start_date else None
        # Gmail's "before:" is exclusive, so bump by a day to include end_date itself.
        before_date = (
            datetime.strptime(sync_request.end_date, "%Y-%m-%d") + timedelta(days=1)
            if sync_request.end_date else None
        )

        syncer = TransactionSyncer(db)
        result = syncer.sync_all_active_sources(
            days_back=sync_request.days_back,
            after_date=after_date,
            before_date=before_date,
        )

        return schemas.SyncResponse(
            success=True,
            message=f"Synced {result['total_saved']} new transactions from {len(email_sources)} sources",
            new_transactions=result['total_saved'],
            skipped_duplicates=result['total_skipped'],
            sources_synced=len(email_sources),
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/maintenance/recategorize")
async def recategorize_transactions(all: bool = False, db: Session = Depends(get_db)):
    """Re-apply categorization rules to existing transactions - mirrors
    `finance-app recategorize`. Only touches `Uncategorized` transactions
    unless `all=true`. Deliberately doesn't go through TransactionSyncer
    (which opens a Gmail connection on init) since this never touches Gmail."""
    recategorize_all = all
    query = db.query(models.Transaction)
    if not recategorize_all:
        uncategorized = db.query(models.Category).filter(models.Category.name == "Uncategorized").first()
        if uncategorized:
            query = query.filter(models.Transaction.category_id == uncategorized.id)

    rules = db.query(models.CategorizationRule).filter(
        models.CategorizationRule.is_active == True
    ).order_by(models.CategorizationRule.priority.desc()).all()

    def match(commerce_name):
        if not commerce_name:
            return None
        name = commerce_name.strip().upper()
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

    transactions = query.all()
    updated = 0
    for txn in transactions:
        category_id = match(txn.commerce_name)
        if category_id and category_id != txn.category_id:
            txn.category_id = category_id
            updated += 1

    db.commit()
    return {"checked": len(transactions), "updated": updated}


class CredentialsUpload(BaseModel):
    content: str = Field(..., max_length=50_000)


@app.get("/api/settings/credentials")
async def get_credentials_status():
    """Whether the Google OAuth client file / Gmail login are in place."""
    base = gmail_client.BASE_DIR
    return {
        "has_credentials": (base / gmail_client.CREDENTIALS_NAME).exists(),
        "has_token": (base / "token.json").exists(),
    }


@app.post("/api/settings/credentials")
async def upload_credentials(upload: CredentialsUpload):
    """Save the Google OAuth client file uploaded from the Settings page as
    credentials.json. Replacing it with a different client invalidates the
    stored Gmail login, so token.json is removed and the next sync logs in again."""
    try:
        gmail_client.parse_client_json(upload.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    base = gmail_client.BASE_DIR
    target = base / gmail_client.CREDENTIALS_NAME
    token = base / "token.json"
    previous = target.read_text() if target.exists() else None
    tmp = target.with_suffix(".json.tmp")
    tmp.write_text(upload.content)
    tmp.chmod(0o600)
    tmp.replace(target)

    token_removed = False
    if previous is not None and previous != upload.content and token.exists():
        token.unlink()
        token_removed = True
    return {"saved": True, "replaced": previous is not None, "token_removed": token_removed}


@app.post("/api/maintenance/reconnect-gmail")
async def reconnect_gmail():
    """Discard the stored Gmail token, same as `finance-app refresh-oauth` -
    the next sync will prompt a fresh login in the browser."""
    token_path = Path(__file__).resolve().parent.parent / "token.json"
    existed = token_path.exists()
    if existed:
        token_path.unlink()
    return {"reconnected": True, "had_existing_token": existed}


@app.get("/api/sync/status")
async def get_sync_status(db: Session = Depends(get_db)):
    """Get sync status information."""
    # Get last transaction import time
    last_transaction = db.query(models.Transaction.created_at).order_by(
        models.Transaction.created_at.desc()
    ).first()

    email_sources = crud.get_email_sources(db, active_only=True)

    return {
        "last_sync": last_transaction[0] if last_transaction else None,
        "active_sources": len(email_sources),
        "sources": [
            {"name": source.name, "email": source.email_address}
            for source in email_sources
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
