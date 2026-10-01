"""Pydantic schemas for API requests and responses."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import date, datetime
from decimal import Decimal


# ============================================================================
# Card Schemas
# ============================================================================

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
    pass


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
    color: Optional[str] = None
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
    utilization_crc: Optional[float] = None  # Percentage
    utilization_usd: Optional[float] = None

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
    pass


class CategoryUpdate(BaseModel):
    """Schema for updating a category (all fields optional)."""
    name: Optional[str] = None
    category_type: Optional[str] = None
    parent_id: Optional[int] = None
    color: Optional[str] = None
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


class CardUtilization(BaseModel):
    """Schema for card utilization data."""
    card_id: int
    card_name: str
    card_color: str
    spent_crc: Decimal
    limit_crc: Optional[Decimal]
    utilization_crc: Optional[float]  # Percentage
    spent_usd: Decimal
    limit_usd: Optional[Decimal]
    utilization_usd: Optional[float]  # Percentage


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
