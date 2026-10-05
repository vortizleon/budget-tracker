"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel, Field, ConfigDict, StringConstraints
from typing import Annotated, Optional, List
from datetime import date, datetime
from decimal import Decimal


# ============================================================================
# Card Schemas
# ============================================================================

# #rgb / #rrggbb only - colors end up in style attributes in the UI.
HexColor = Annotated[str, StringConstraints(pattern=r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")]


class CardBase(BaseModel):
    """Base card schema with common fields."""
    name: str
    last_four: Optional[str] = None
    card_type: Optional[str] = None  # "credit" or "debit"
    supports_crc: bool = True
    supports_usd: bool = True
    credit_limit_crc: Optional[Decimal] = None
    credit_limit_usd: Optional[Decimal] = None
    payment_due_day: Optional[int] = Field(None, ge=1, le=31)
    cutoff_day: Optional[int] = Field(None, ge=1, le=31)
    bank: Optional[str] = None
    color: str = "#4F46E5"  # Default indigo color
    default_category_id: Optional[int] = None


class CardCreate(CardBase):
    """Schema for creating a new card."""
    color: HexColor = "#4F46E5"


class CardUpdate(BaseModel):
    """Schema for updating a card (all fields optional)."""
    name: Optional[str] = None
    last_four: Optional[str] = None
    card_type: Optional[str] = None
    supports_crc: Optional[bool] = None
    supports_usd: Optional[bool] = None
    credit_limit_crc: Optional[Decimal] = None
    credit_limit_usd: Optional[Decimal] = None
    payment_due_day: Optional[int] = Field(None, ge=1, le=31)
    cutoff_day: Optional[int] = Field(None, ge=1, le=31)
    bank: Optional[str] = None
    color: Optional[HexColor] = None
    default_category_id: Optional[int] = None
    is_active: Optional[bool] = None


class CardResponse(CardBase):
    """Schema for card response with additional fields."""
    id: int
    is_active: bool
    created_at: datetime

    # Calculated fields (can be added by endpoint)
    total_spent_crc: Optional[Decimal] = None
    total_spent_usd: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


class CardBillingCycle(BaseModel):
    """A single billing cycle for a card, with its running totals."""
    cycle_start: date
    cycle_end: date
    due_date: date
    is_current: bool
    total_crc: Decimal
    total_usd: Decimal
    transaction_count: int


# ============================================================================
# Category Schemas
# ============================================================================

class CategoryBase(BaseModel):
    """Base category schema."""
    name: str
    category_type: str = "expense"  # "expense" or "income"
    parent_id: Optional[int] = None
    color: str = "#6B7280"  # Default gray color
    icon: str = "📁"  # Default folder emoji


class CategoryCreate(CategoryBase):
    """Schema for creating a new category."""
    color: HexColor = "#6B7280"


class CategoryUpdate(BaseModel):
    """Schema for updating a category (all fields optional)."""
    name: Optional[str] = None
    category_type: Optional[str] = None
    parent_id: Optional[int] = None
    color: Optional[HexColor] = None
    icon: Optional[str] = None


class CategoryResponse(CategoryBase):
    """Schema for category response."""
    id: int
    created_at: datetime

    # Calculated fields
    transaction_count: Optional[int] = None
    total_amount: Optional[Decimal] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Account Schemas
# ============================================================================

class AccountBase(BaseModel):
    """Base account schema."""
    name: str
    account_type: Optional[str] = None  # "checking", "savings", "cash"
    iban: Optional[str] = None
    account_number: Optional[str] = None
    currency: str = "CRC"
    current_balance: Optional[Decimal] = None


class AccountCreate(AccountBase):
    """Schema for creating a new account."""
    pass


class AccountUpdate(BaseModel):
    """Schema for updating an account (all fields optional)."""
    name: Optional[str] = None
    account_type: Optional[str] = None
    iban: Optional[str] = None
    account_number: Optional[str] = None
    currency: Optional[str] = None
    current_balance: Optional[Decimal] = None
    is_active: Optional[bool] = None


class AccountResponse(AccountBase):
    """Schema for account response."""
    id: int
    is_active: bool
    created_at: datetime
    available_balance: Optional[Decimal] = None  # Calculated field

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Transaction Schemas
# ============================================================================

class TransactionBase(BaseModel):
    """Base transaction schema."""
    date: date
    amount: Decimal
    currency: str  # "CRC" or "USD"
    commerce_name: Optional[str] = None
    description: Optional[str] = None
    transaction_type: str  # "purchase" or "payment"
    card_id: Optional[int] = None
    account_id: Optional[int] = None
    category_id: Optional[int] = None
    notes: Optional[str] = None
    installment_plan_id: Optional[int] = None
    installment_number: Optional[int] = None
    is_reconciled: bool = False


class TransactionCreate(TransactionBase):
    """Schema for creating a new transaction."""
    pass


class TransactionUpdate(BaseModel):
    """Schema for updating a transaction (all fields optional)."""
    date: Optional[date] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    commerce_name: Optional[str] = None
    description: Optional[str] = None
    transaction_type: Optional[str] = None
    card_id: Optional[int] = None
    account_id: Optional[int] = None
    category_id: Optional[int] = None
    notes: Optional[str] = None
    is_reconciled: Optional[bool] = None
    installment_plan_id: Optional[int] = None
    installment_number: Optional[int] = None


class TransactionResponse(TransactionBase):
    """Schema for transaction response with relationships."""
    id: int
    is_reconciled: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Nested objects (optional, can be included with query)
    card: Optional[CardResponse] = None
    account: Optional[AccountResponse] = None
    category: Optional[CategoryResponse] = None

    model_config = ConfigDict(from_attributes=True)


class BulkCategorizeRequest(BaseModel):
    """Schema for bulk categorization request."""
    transaction_ids: List[int]
    category_id: int


# ============================================================================
# Categorization Rule Schemas
# ============================================================================
# The UI deals in (match_type, value) - e.g. ("starts_with", "UBER") - rather
# than the raw '%'-wildcard commerce_pattern stored on the model; crud.py
# converts between the two. "regex" is accepted here for forward-compat but
# not yet implemented by the matcher in sync.py.

class CategorizationRuleBase(BaseModel):
    """Base categorization rule schema."""
    match_type: str = "starts_with"  # "starts_with" | "contains" | "exact" | "regex"
    value: str
    category_id: int
    priority: int = 0
    is_active: bool = True


class CategorizationRuleCreate(CategorizationRuleBase):
    """Schema for creating a new categorization rule."""
    pass


class CategorizationRuleResponse(CategorizationRuleBase):
    """Schema for categorization rule response."""
    id: int
    created_at: datetime


# ============================================================================
# Installment Plan Schemas ("tasa cero")
# ============================================================================

class InstallmentPlanCreate(BaseModel):
    """Schema for creating a new installment plan - generates the
    REMAINING Transaction rows immediately (installments
    starting_installment_number..num_installments), so there's nothing left
    to "run" later. For a brand-new plan leave starting_installment_number
    at 1 and total_amount as the full price. For a plan already in progress
    elsewhere (e.g. a bank's own "17 of 18 cuotas" tracker), set
    total_amount to the REMAINING balance and starting_installment_number
    to the next unpaid installment (18, in that example)."""
    description: str
    total_amount: Decimal
    currency: str  # "CRC" or "USD"
    num_installments: int = Field(ge=1, le=60)
    starting_installment_number: int = Field(default=1, ge=1)
    charge_day: int = Field(default=18, ge=1, le=28)
    card_id: int
    category_id: Optional[int] = None
    first_charge_month: str  # "YYYY-MM" - month of the first GENERATED installment


class InstallmentPlanResponse(BaseModel):
    """Schema for installment plan response."""
    id: int
    description: str
    total_amount: Decimal
    currency: str
    num_installments: int
    starting_installment_number: int
    charge_day: int
    card_id: int
    category_id: Optional[int] = None
    created_at: datetime
    installments_paid: int  # installments whose date is today or earlier

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Email Source Schemas
# ============================================================================

class EmailSourceBase(BaseModel):
    """Base email source schema."""
    name: str
    email_address: str
    subject_keywords: Optional[str] = None


class EmailSourceCreate(EmailSourceBase):
    """Schema for creating a new email source."""
    pass


class EmailSourceUpdate(BaseModel):
    """Schema for updating an email source."""
    name: Optional[str] = None
    email_address: Optional[str] = None
    subject_keywords: Optional[str] = None
    is_active: Optional[bool] = None


class EmailSourceResponse(EmailSourceBase):
    """Schema for email source response."""
    id: int
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Analytics Schemas
# ============================================================================

class SpendingByCategory(BaseModel):
    """Schema for spending by category data."""
    category_id: int
    category_name: str
    category_color: str
    category_icon: str
    total_amount: Decimal
    transaction_count: int
    percentage: float


class DailySpending(BaseModel):
    """Schema for daily spending data point."""
    date: date
    total: Decimal
    transaction_count: int


class MonthlyTrend(BaseModel):
    """Schema for monthly trend data point."""
    month: str  # Format: "2025-01" or "Jan 2025"
    total_crc: Decimal
    total_usd: Decimal
    transaction_count: int


class TopMerchant(BaseModel):
    """Schema for top merchant data."""
    commerce_name: str
    total_amount: Decimal
    transaction_count: int
    currency: str


class SpendingByCard(BaseModel):
    """Schema for per-card spending totals."""
    card_id: int
    card_name: str
    card_color: str
    spent_crc: Decimal
    spent_usd: Decimal


class DashboardSummary(BaseModel):
    """Schema for dashboard summary stats."""
    total_transactions: int
    total_spent_crc: Decimal
    total_spent_usd: Decimal
    total_income_crc: Decimal
    total_income_usd: Decimal
    active_cards: int
    uncategorized_count: int
    this_month_spent_crc: Decimal
    this_month_spent_usd: Decimal
    last_sync: Optional[datetime] = None
    oldest_transaction_date: Optional[date] = None


class AnalyticsResponse(BaseModel):
    """Generic analytics response wrapper."""
    data: List[dict]
    total: Optional[int] = None
    currency: Optional[str] = None


# ============================================================================
# Filter Schemas
# ============================================================================

class TransactionFilters(BaseModel):
    """Schema for transaction filtering parameters."""
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    card_ids: Optional[List[int]] = None
    category_ids: Optional[List[int]] = None
    min_amount: Optional[Decimal] = None
    max_amount: Optional[Decimal] = None
    currency: Optional[str] = None  # "CRC", "USD", or None for both
    transaction_type: Optional[str] = None  # "purchase" or "payment"
    search: Optional[str] = None  # Search commerce_name
    is_reconciled: Optional[bool] = None
    skip: int = 0
    limit: int = 50


# ============================================================================
# Sync Schemas
# ============================================================================

class SyncRequest(BaseModel):
    """Schema for triggering sync."""
    days_back: int = Field(30, ge=1, le=365)
    # Explicit range for backfilling a specific gap - takes priority over
    # days_back when given (end_date is inclusive).
    start_date: Optional[str] = None  # YYYY-MM-DD
    end_date: Optional[str] = None  # YYYY-MM-DD


class SyncResponse(BaseModel):
    """Schema for sync operation response."""
    success: bool
    message: str
    new_transactions: int
    skipped_duplicates: int
    sources_synced: int
    errors: Optional[List[str]] = None


# ============================================================================
# Error Schemas
# ============================================================================

class ErrorResponse(BaseModel):
    """Schema for error responses."""
    detail: str
    error_code: Optional[str] = None


# ============================================================================
# Subscription Schemas
# ============================================================================

class SubscriptionBase(BaseModel):
    """Base subscription schema."""
    name: str
    amount: Decimal
    currency: str  # "CRC" or "USD"
    billing_day: int = Field(..., ge=1, le=31)
    category_id: Optional[int] = None
    notes: Optional[str] = None


class SubscriptionCreate(SubscriptionBase):
    """Schema for creating a new subscription."""
    pass


class SubscriptionUpdate(BaseModel):
    """Schema for updating a subscription (all fields optional)."""
    name: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    billing_day: Optional[int] = Field(None, ge=1, le=31)
    category_id: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SubscriptionResponse(SubscriptionBase):
    """Schema for subscription response."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    category: Optional[CategoryResponse] = None

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Balance Summary Schemas
# ============================================================================

class AccountBalanceDetail(BaseModel):
    """Detailed balance information for a single account."""
    account_id: int
    account_name: str
    account_type: str
    currency: str
    manual_balance: Decimal  # current_balance field
    available_balance: Decimal  # after transactions
    pending_amount: Decimal  # difference


class BalanceSummary(BaseModel):
    """Summary of all account balances."""
    accounts: List[AccountBalanceDetail]
    total_manual_crc: Decimal
    total_manual_usd: Decimal
    total_available_crc: Decimal
    total_available_usd: Decimal
    savings_accounts: List[AccountBalanceDetail]


# ============================================================================
# Budget Schemas
# ============================================================================

class BudgetUpsert(BaseModel):
    """Create or update a category budget. Send exactly one of percentage /
    amount - the other gets derived from the month's income."""
    category_id: int
    percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    amount: Optional[Decimal] = Field(None, ge=0)


class BudgetLine(BaseModel):
    """One category's budget for a given month, with spending against it."""
    id: int
    category_id: int
    category_name: str
    category_color: Optional[str] = None
    category_icon: Optional[str] = None
    anchor: str  # "percentage" or "amount" - which one the user set
    is_protected: bool
    percentage: Decimal  # as planned, before debt
    amount: Decimal  # as planned, before debt
    adjusted_amount: Decimal  # after debt payments (= amount if protected)
    spent: Decimal  # CRC, USD purchases converted at the settings rate
    remaining: Decimal  # adjusted_amount - spent


class BudgetProtectedUpdate(BaseModel):
    is_protected: bool


class BudgetDebtLine(BaseModel):
    """One card's debt payment for the month, from its payoff plan. `amount`
    is only the part of the payment beyond the card's expected new spending
    (that spending is already counted in category budgets)."""
    card_id: int
    card_name: str
    payment_crc: Decimal
    payment_usd: Decimal
    spend_crc: Decimal  # usual purchases + this month's cuotas
    spend_usd: Decimal
    installments_crc: Decimal  # the Tasa Cero part of spend_*
    installments_usd: Decimal
    amount: Decimal  # CRC


class IncomeEntryCreate(BaseModel):
    """Schema for logging a paycheck."""
    date: date
    amount: Decimal = Field(gt=0)
    currency: str = "CRC"
    description: Optional[str] = None


class IncomeEntryResponse(IncomeEntryCreate):
    """Schema for income entry response."""
    id: int
    amount_crc: Decimal

    model_config = ConfigDict(from_attributes=True)


class BudgetSettingsUpdate(BaseModel):
    """Schema for updating budget settings (all fields optional)."""
    expected_monthly_income: Optional[Decimal] = Field(None, ge=0)
    usd_to_crc_rate: Optional[Decimal] = Field(None, gt=0)


class BudgetSettingsResponse(BaseModel):
    """Schema for budget settings response."""
    expected_monthly_income: Optional[Decimal] = None
    usd_to_crc_rate: Decimal

    model_config = ConfigDict(from_attributes=True)


class BudgetOverview(BaseModel):
    """Everything the Budgets view needs for one month."""
    month: str  # "YYYY-MM"
    settings: BudgetSettingsResponse
    income_entries: List[IncomeEntryResponse]
    income_received: Decimal  # CRC total logged for the month
    income_base: Decimal  # what percentages are applied to
    lines: List[BudgetLine]
    debt_lines: List[BudgetDebtLine]
    total_debt: Decimal
    reduction_percentage: Decimal  # how much non-protected budgets shrink for debt
    debt_shortfall: Decimal  # debt that doesn't fit even with flexible budgets at 0
    total_budgeted: Decimal  # adjusted, excluding debt
    total_percentage: Decimal
    total_spent: Decimal
    unbudgeted: Decimal  # income_base - debt - total_budgeted (savings / free money)
    unbudgeted_spent: Decimal  # spending in categories with no budget


# ============================================================================
# Card Payoff Plan Schemas
# ============================================================================

class CardPayoffPlanUpdate(BaseModel):
    """Create or replace a card's payoff plan. monthly_spend_* = None means
    "use the card's recent average"."""
    balance_as_of: date
    balance_crc: Decimal = Field(default=0, ge=0)
    balance_usd: Decimal = Field(default=0, ge=0)
    annual_rate_crc: Decimal = Field(default=0, ge=0, le=200)
    annual_rate_usd: Decimal = Field(default=0, ge=0, le=200)
    monthly_payment_crc: Decimal = Field(default=0, ge=0)
    monthly_payment_usd: Decimal = Field(default=0, ge=0)
    monthly_spend_crc: Optional[Decimal] = Field(default=None, ge=0)
    monthly_spend_usd: Optional[Decimal] = Field(default=None, ge=0)


class StatementSnapshot(BaseModel):
    """The card's latest bank statement, offered as the source for payoff-plan numbers.
    balance_* is the statement balance minus the payments logged since it was cut;
    as_of is today when payments were logged, otherwise the cut date."""
    period: str
    cut_date: Optional[date] = None
    as_of: Optional[date] = None
    balance_crc: Optional[Decimal] = None
    balance_usd: Optional[Decimal] = None
    annual_rate_crc: Optional[Decimal] = None
    annual_rate_usd: Optional[Decimal] = None
    min_payment_crc: Optional[Decimal] = None
    min_payment_usd: Optional[Decimal] = None


class CardPayoffPlanResponse(BaseModel):
    """A card's saved plan (plan=None if none yet) plus the recent average
    monthly spend on the card, used as the default spend estimate."""
    card_id: int
    plan: Optional[CardPayoffPlanUpdate] = None
    avg_monthly_spend_crc: Decimal
    avg_monthly_spend_usd: Decimal
    avg_based_on_days: int  # how many days of history the average covers
    # Tasa Cero charges still to come after balance_as_of, per month
    # (index 0 = the as-of month) - added on top of the average spend.
    scheduled_installments_crc: List[Decimal] = []
    scheduled_installments_usd: List[Decimal] = []
    statement: Optional[StatementSnapshot] = None  # latest imported statement for this card


# ============================================================================
# Month-end Forecast Schemas
# ============================================================================

class ForecastLine(BaseModel):
    """One category's projected month-end spending (CRC)."""
    category_id: Optional[int] = None  # None = transactions with no category
    category_name: str
    category_icon: Optional[str] = None
    budget: Optional[Decimal] = None  # after debt; None = no budget
    spent_so_far: Decimal  # through today, cuotas included
    scheduled: Decimal  # Tasa Cero cuotas still to come this month
    projected: Decimal  # spent_so_far + expected rest + scheduled
    status: str  # "on_track" | "at_risk" | "over" | "no_budget"
    basis: str  # "pace" | "history" | "blend" - how the rest was estimated
    # The pieces behind `projected`, so the UI can show its work:
    typical_month: Optional[Decimal] = None  # usual monthly total (no cuotas); None = no history
    pace_month: Decimal  # this month's regular spending extrapolated to a full month
    rest_from_typical: Decimal  # typical_month - spent (floored at 0)
    rest_from_pace: Decimal  # pace for the days left
    rest: Decimal  # the blended estimate actually used
    pace_weight: Decimal  # 0..1, how much `rest` leans on pace


class MonthForecast(BaseModel):
    """Where the current month is headed at the current pace."""
    month: str  # "YYYY-MM"
    days_elapsed: int
    days_in_month: int
    history_months: int  # full past months used for typical spending
    history_start: Optional[str] = None  # "YYYY-MM" of the first history month
    pace_weight: Decimal  # 0..1 for blended categories - days elapsed / days in month
    income_base: Decimal
    total_debt: Decimal
    spent_so_far: Decimal
    projected_spend: Decimal
    projected_left: Decimal  # income_base - projected_spend - total_debt
    lines: List[ForecastLine]


# ============================================================================
# Statements (bank estado de cuenta)
# ============================================================================

class StatementFinancingLineResponse(BaseModel):
    merchant: Optional[str] = None
    currency: Optional[str] = None
    total_amount: Optional[Decimal] = None
    term_months: Optional[int] = None
    annual_rate: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    installment_amount: Optional[Decimal] = None
    installment_number: Optional[int] = None
    installments_total: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class StatementResponse(BaseModel):
    id: int
    card_id: Optional[int] = None
    card_name: Optional[str] = None
    bank: str
    brand: Optional[str] = None
    loyalty_plan: Optional[str] = None
    account_last4: str
    period: str
    cut_date: Optional[date] = None
    min_due_date: Optional[date] = None
    cash_due_date: Optional[date] = None
    limit_currency: Optional[str] = None
    credit_limit: Optional[Decimal] = None
    available: Optional[Decimal] = None
    points_assigned: Optional[Decimal] = None
    previous_balance_crc: Optional[Decimal] = None
    previous_balance_usd: Optional[Decimal] = None
    purchases_crc: Optional[Decimal] = None
    purchases_usd: Optional[Decimal] = None
    payments_crc: Optional[Decimal] = None
    payments_usd: Optional[Decimal] = None
    interest_crc: Optional[Decimal] = None
    interest_usd: Optional[Decimal] = None
    insurance_crc: Optional[Decimal] = None
    insurance_usd: Optional[Decimal] = None
    other_charges_crc: Optional[Decimal] = None
    other_charges_usd: Optional[Decimal] = None
    min_payment_crc: Optional[Decimal] = None
    min_payment_usd: Optional[Decimal] = None
    cash_payment_crc: Optional[Decimal] = None
    cash_payment_usd: Optional[Decimal] = None
    closing_balance_crc: Optional[Decimal] = None
    closing_balance_usd: Optional[Decimal] = None
    apr_crc: Optional[Decimal] = None
    apr_usd: Optional[Decimal] = None
    paid_on: Optional[date] = None
    status: str
    warnings: List[str] = []
    parser_version: int
    financing_lines: List[StatementFinancingLineResponse] = []

    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Cost of debt (from imported statements)
# ============================================================================

class CostOfDebtMonth(BaseModel):
    period: str  # "2026-09"
    interest_crc: Decimal
    insurance_crc: Decimal


class CostOfDebtCard(BaseModel):
    name: str
    debt_crc: Decimal  # CRC-equivalent
    interest_crc: Decimal
    apr_crc: Optional[Decimal] = None
    apr_usd: Optional[Decimal] = None


class CostOfDebt(BaseModel):
    has_data: bool
    usd_to_crc_rate: Decimal
    period: Optional[str] = None
    statements_needing_review: int = 0
    total_debt_crc: Optional[Decimal] = None   # CRC + USD balances, in CRC
    debt_crc: Optional[Decimal] = None
    debt_usd: Optional[Decimal] = None
    interest_crc: Optional[Decimal] = None     # interest charged on the latest statements
    insurance_crc: Optional[Decimal] = None    # optional insurance/services billed with the card
    monthly_cost_crc: Optional[Decimal] = None
    yearly_cost_crc: Optional[Decimal] = None
    minimum_payment_crc: Optional[Decimal] = None
    interest_share_of_minimum: Optional[Decimal] = None  # 0-1: how much of the minimum is just interest
    average_rate: Optional[Decimal] = None     # balance-weighted % per year
    highest_rate_currency: Optional[str] = None
    apr_crc: Optional[Decimal] = None
    apr_usd: Optional[Decimal] = None
    monthly_income_crc: Optional[Decimal] = None
    cost_share_of_income: Optional[Decimal] = None
    statement_debt_crc: Optional[Decimal] = None   # total at the statement cut, before payments since
    paid_since_crc: Optional[Decimal] = None       # payments logged since the statements were cut
    future_installments_crc: Optional[Decimal] = None  # 0% installments not yet billed
    cards: List[CostOfDebtCard] = []
    history: List[CostOfDebtMonth] = []


class DueStatement(BaseModel):
    """A statement whose payment is due soon (or overdue) and not marked paid."""
    id: int
    card_name: str
    account_last4: str
    period: str
    cash_due_date: date
    days_left: int  # negative = overdue
    min_payment_crc: Optional[Decimal] = None
    min_payment_usd: Optional[Decimal] = None
    cash_payment_crc: Optional[Decimal] = None
    cash_payment_usd: Optional[Decimal] = None


class StatementPaid(BaseModel):
    paid: bool = True


# ============================================================================
# Card payments and where each card stands now
# ============================================================================

class PaymentCreate(BaseModel):
    """A payment the user made toward a card (logged by hand)."""
    card_id: int
    amount: Decimal = Field(gt=0)
    currency: str
    date: date
    notes: Optional[str] = None


class PaymentResponse(BaseModel):
    id: int
    card_id: Optional[int] = None
    card_name: Optional[str] = None
    date: date
    amount: Decimal
    currency: str
    notes: Optional[str] = None
    logged_by_hand: bool  # False = came from a bank email


class CardPosition(BaseModel):
    """Statement figures adjusted by what happened since the statement was cut."""
    card_id: int
    card_name: str
    period: str
    cut_date: Optional[date] = None
    cash_due_date: Optional[date] = None
    days_left: Optional[int] = None  # negative = past the due date
    status: str  # "paid" | "minimum_paid" | "unpaid"
    paid_by_hand_on: Optional[date] = None  # statement manually marked as paid
    statement_balance_crc: Decimal
    statement_balance_usd: Decimal
    payments_since_crc: Decimal
    payments_since_usd: Decimal
    purchases_since_crc: Decimal
    purchases_since_usd: Decimal
    balance_now_crc: Decimal   # estimated: statement - payments + purchases since
    balance_now_usd: Decimal
    min_payment_crc: Decimal
    min_payment_usd: Decimal
    cash_payment_crc: Decimal
    cash_payment_usd: Decimal
    remaining_min_crc: Decimal
    remaining_min_usd: Decimal
    remaining_cash_crc: Decimal
    remaining_cash_usd: Decimal
