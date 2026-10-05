"""SQLAlchemy models for the budgeting app."""
from sqlalchemy import (
    Column, Integer, String, Boolean, DECIMAL, Date, DateTime, Text, ForeignKey
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Card(Base):
    """Credit or debit card."""
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # e.g., "Visa Gold"
    last_four = Column(String(4))  # Last 4 digits
    card_type = Column(String)  # "credit" or "debit"

    # Multi-currency support
    supports_crc = Column(Boolean, default=True)
    supports_usd = Column(Boolean, default=True)

    # Credit card specific
    credit_limit_crc = Column(DECIMAL(12, 2))
    credit_limit_usd = Column(DECIMAL(12, 2))
    payment_due_day = Column(Integer)  # Day of month (1-31)
    cutoff_day = Column(Integer)  # Statement cutoff day (1-31)

    bank = Column(String)

    # UI customization
    color = Column(String, default="#4F46E5")  # HEX color for card display

    # Default category for new transactions from this card
    default_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    transactions = relationship("Transaction", back_populates="card")
    default_category = relationship("Category", foreign_keys=[default_category_id])

    def __repr__(self):
        return f"<Card(name='{self.name}', last_four='{self.last_four}')>"


class Account(Base):
    """Bank account or cash account."""
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    account_type = Column(String)  # "checking", "savings", "cash"
    iban = Column(String)  # IBAN number
    account_number = Column(String)  # Alternative account ID
    currency = Column(String, default="CRC")
    current_balance = Column(DECIMAL(12, 2))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    transactions = relationship("Transaction", back_populates="account")

    def __repr__(self):
        return f"<Account(name='{self.name}', type='{self.account_type}')>"


class Category(Base):
    """Expense or income category."""
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    category_type = Column(String, default="expense")  # "expense" or "income"
    parent_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # UI customization
    color = Column(String, default="#6B7280")  # HEX color for category badges
    icon = Column(String, default="📁")  # Emoji or icon identifier

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    parent = relationship("Category", remote_side=[id], backref="subcategories")
    transactions = relationship("Transaction", back_populates="category")
    rules = relationship("CategorizationRule", back_populates="category")

    def __repr__(self):
        return f"<Category(name='{self.name}', type='{self.category_type}')>"


class Transaction(Base):
    """Financial transaction (purchase or payment)."""
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String, nullable=False)  # "CRC" or "USD"
    commerce_name = Column(String)  # Where money was spent/received
    description = Column(Text)
    transaction_type = Column(String, nullable=False)  # "purchase" or "payment"

    # Foreign keys
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Gmail tracking
    gmail_message_id = Column(String, unique=True, index=True)
    raw_email_body = Column(Text)  # Store for debugging

    # Set when this is one installment of a "tasa cero" plan (see
    # InstallmentPlan) rather than a single real-time purchase.
    installment_plan_id = Column(Integer, ForeignKey("installment_plans.id"), nullable=True)
    installment_number = Column(Integer, nullable=True)  # 1-based, e.g. 3 of 12

    # Metadata
    is_reconciled = Column(Boolean, default=False)
    notes = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    card = relationship("Card", back_populates="transactions")
    account = relationship("Account", back_populates="transactions")
    category = relationship("Category", back_populates="transactions")
    installment_plan = relationship("InstallmentPlan", back_populates="transactions")

    def __repr__(self):
        return f"<Transaction(date='{self.date}', amount={self.amount} {self.currency}, commerce='{self.commerce_name}')>"


class InstallmentPlan(Base):
    """A 0%-interest installment purchase ("tasa cero") split across N
    equal monthly charges. Creating one eagerly generates its N Transaction
    rows (dated and amounted up front) rather than relying on a scheduler -
    this app has no background process, only on-demand syncs/commands."""
    __tablename__ = "installment_plans"

    id = Column(Integer, primary_key=True, index=True)
    description = Column(String, nullable=False)  # e.g. "Laptop Dell"
    total_amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String, nullable=False)  # "CRC" or "USD"
    num_installments = Column(Integer, nullable=False)  # total original installment count
    charge_day = Column(Integer, nullable=False, default=18)  # day of month each installment is dated

    # 1 for a brand-new plan. For one already in progress elsewhere (e.g. a
    # bank's own "17 of 18 cuotas" tracker), set this to the next unpaid
    # installment number so only the remaining charges get generated, while
    # installment_number on each still reflects the true "X of Y" count.
    starting_installment_number = Column(Integer, nullable=False, default=1)

    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    card = relationship("Card")
    category = relationship("Category")
    transactions = relationship(
        "Transaction", back_populates="installment_plan",
        order_by="Transaction.installment_number"
    )

    def __repr__(self):
        return f"<InstallmentPlan(description='{self.description}', total={self.total_amount} {self.currency}, n={self.num_installments})>"


class EmailSource(Base):
    """Email sources for bank notifications."""
    __tablename__ = "email_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # e.g., "BAC San José"
    email_address = Column(String, nullable=False, unique=True)  # e.g., "notificacion@notificacionesbaccr.com"
    subject_keywords = Column(String)  # Comma-separated keywords, e.g., "compra,pago"
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<EmailSource(name='{self.name}', email='{self.email_address}')>"

    def get_keywords_list(self):
        """Return keywords as a list."""
        if self.subject_keywords:
            return [k.strip() for k in self.subject_keywords.split(',')]
        return []


class CategorizationRule(Base):
    """Rules for automatic transaction categorization."""
    __tablename__ = "categorization_rules"

    id = Column(Integer, primary_key=True, index=True)
    commerce_pattern = Column(String, nullable=False)  # e.g., "UBER%", "WALMART%"
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    priority = Column(Integer, default=0)  # Higher priority = applied first
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    category = relationship("Category", back_populates="rules")

    def __repr__(self):
        return f"<CategorizationRule(pattern='{self.commerce_pattern}', category_id={self.category_id})>"


class Subscription(Base):
    """Monthly subscription tracking for awareness."""
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)  # e.g., "Netflix", "Spotify"
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String, nullable=False)  # "CRC" or "USD"
    billing_day = Column(Integer, nullable=False)  # Day of month (1-31)

    # Optional category reference (for organization only)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    # Metadata
    is_active = Column(Boolean, default=True)
    notes = Column(Text)  # Additional notes about the subscription
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    category = relationship("Category")

    def __repr__(self):
        return f"<Subscription(name='{self.name}', amount={self.amount} {self.currency}, day={self.billing_day})>"


class Budget(Base):
    """Monthly spending budget for one expense category.

    Exactly one of `percentage` / `amount` is set - whichever the user typed
    last is the anchor, and the other is derived from the month's income
    (see budgets.py). So a fixed bill like rent can stay at a set amount
    while flexible categories scale with income. Amounts are always CRC."""
    __tablename__ = "budgets"

    id = Column(Integer, primary_key=True, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, unique=True)
    percentage = Column(DECIMAL(5, 2), nullable=True)  # % of monthly income
    amount = Column(DECIMAL(12, 2), nullable=True)  # fixed CRC amount
    # Essentials that can't be cut (rent, utilities). Debt payments shrink
    # every other budget instead.
    is_protected = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    category = relationship("Category")

    def __repr__(self):
        return f"<Budget(category_id={self.category_id}, percentage={self.percentage}, amount={self.amount})>"


class IncomeEntry(Base):
    """A paycheck (or other income) the user logs by hand when it arrives -
    the bank alert emails only cover spending, so income isn't synced."""
    __tablename__ = "income_entries"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)  # month it counts toward = this date's month
    amount = Column(DECIMAL(12, 2), nullable=False)
    currency = Column(String, nullable=False, default="CRC")  # "CRC" or "USD"
    description = Column(String)  # e.g. "1st payment"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<IncomeEntry(date='{self.date}', amount={self.amount} {self.currency})>"


class BudgetSettings(Base):
    """Single-row table of budget-wide settings."""
    __tablename__ = "budget_settings"

    id = Column(Integer, primary_key=True, index=True)
    # What the user expects to earn per month (CRC). Budgets are computed
    # against this until enough real income has been logged to exceed it, so
    # amounts don't halve between the 1st and 2nd paycheck.
    expected_monthly_income = Column(DECIMAL(12, 2), nullable=True)
    # Converts USD purchases/income into CRC for budget tracking.
    usd_to_crc_rate = Column(DECIMAL(10, 2), nullable=False, default=505)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class CardPayoffPlan(Base):
    """What the user owes on a credit card and how they plan to pay it down.
    CRC and USD are separate balances (as on Costa Rican cards - each is
    paid in its own currency), so every field comes in a pair. The payoff
    projection itself is computed on the fly (frontend), not stored."""
    __tablename__ = "card_payoff_plans"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False, unique=True)
    balance_as_of = Column(Date, nullable=False)  # date the balances were read off the statement/app

    balance_crc = Column(DECIMAL(12, 2), nullable=False, default=0)
    balance_usd = Column(DECIMAL(12, 2), nullable=False, default=0)
    annual_rate_crc = Column(DECIMAL(5, 2), nullable=False, default=0)  # % per year
    annual_rate_usd = Column(DECIMAL(5, 2), nullable=False, default=0)
    monthly_payment_crc = Column(DECIMAL(12, 2), nullable=False, default=0)
    monthly_payment_usd = Column(DECIMAL(12, 2), nullable=False, default=0)

    # Expected new spending per month on the card. NULL = use the card's
    # recent average (see payoff.py).
    monthly_spend_crc = Column(DECIMAL(12, 2), nullable=True)
    monthly_spend_usd = Column(DECIMAL(12, 2), nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    card = relationship("Card")


class Statement(Base):
    """One card account's monthly bank statement (estado de cuenta), parsed
    from the PDF. The statement is the bank's own record, so it is the source
    of truth for balances, interest and fees - the Transactions (from emails)
    are checked against it. raw_text is kept so a parser fix can re-parse
    without re-uploading the PDF."""
    __tablename__ = "statements"

    id = Column(Integer, primary_key=True, index=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True)  # NULL = no card matched yet
    bank = Column(String, nullable=False)
    brand = Column(String)
    loyalty_plan = Column(String)
    account_last4 = Column(String(4), nullable=False)
    card_last4s = Column(String)  # comma-separated card numbers seen in the movements
    period = Column(String, nullable=False)  # "2026-09"
    cut_date = Column(Date)
    min_due_date = Column(Date)
    cash_due_date = Column(Date)

    limit_currency = Column(String)
    credit_limit = Column(DECIMAL(12, 2))
    available = Column(DECIMAL(12, 2))
    points_assigned = Column(DECIMAL(12, 2))

    # Per-currency amounts (CRC / USD pairs). payments are stored positive.
    previous_balance_crc = Column(DECIMAL(14, 2))
    previous_balance_usd = Column(DECIMAL(14, 2))
    purchases_crc = Column(DECIMAL(14, 2))
    purchases_usd = Column(DECIMAL(14, 2))
    payments_crc = Column(DECIMAL(14, 2))
    payments_usd = Column(DECIMAL(14, 2))
    interest_crc = Column(DECIMAL(14, 2))   # interest charged this cycle
    interest_usd = Column(DECIMAL(14, 2))
    insurance_crc = Column(DECIMAL(14, 2))  # voluntary products/services (seguros)
    insurance_usd = Column(DECIMAL(14, 2))
    other_charges_crc = Column(DECIMAL(14, 2))  # IVA and other charges
    other_charges_usd = Column(DECIMAL(14, 2))
    min_payment_crc = Column(DECIMAL(14, 2))
    min_payment_usd = Column(DECIMAL(14, 2))
    cash_payment_crc = Column(DECIMAL(14, 2))  # "pago de contado": pay this to owe no interest
    cash_payment_usd = Column(DECIMAL(14, 2))
    closing_balance_crc = Column(DECIMAL(14, 2))
    closing_balance_usd = Column(DECIMAL(14, 2))
    apr_crc = Column(DECIMAL(7, 4))  # nominal annual rate, %
    apr_usd = Column(DECIMAL(7, 4))

    paid_on = Column(Date)  # when the user marked this statement's payment as made

    status = Column(String, nullable=False, default="ok")  # "ok" | "needs_review"
    warnings_json = Column(Text)  # JSON list of strings
    parser_version = Column(Integer, nullable=False, default=1)
    raw_text = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    card = relationship("Card")
    financing_lines = relationship(
        "StatementFinancingLine", back_populates="statement", cascade="all, delete-orphan"
    )


class StatementFinancingLine(Base):
    """An installment ("tasa cero" / otra línea de financiamiento) listed on a statement."""
    __tablename__ = "statement_financing_lines"

    id = Column(Integer, primary_key=True, index=True)
    statement_id = Column(Integer, ForeignKey("statements.id"), nullable=False)
    merchant = Column(String)
    currency = Column(String)
    total_amount = Column(DECIMAL(14, 2))
    term_months = Column(Integer)
    annual_rate = Column(DECIMAL(7, 4))
    start_date = Column(Date)
    end_date = Column(Date)
    installment_amount = Column(DECIMAL(14, 2))
    installment_number = Column(Integer)
    installments_total = Column(Integer)

    statement = relationship("Statement", back_populates="financing_lines")
