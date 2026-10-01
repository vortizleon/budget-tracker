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
