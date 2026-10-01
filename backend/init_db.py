"""Initialize database and create sample data."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import init_db, SessionLocal
from backend.models import Card, Account, Category, EmailSource, Subscription


def create_default_categories(db):
    """Create default expense categories."""
    default_categories = [
        ("Uncategorized", "expense"),
        ("Supermarket", "expense"),
        ("Restaurants", "expense"),
        ("Takeout", "expense"),
        ("Transportation", "expense"),
        ("Entertainment", "expense"),
        ("Shopping", "expense"),
        ("Health", "expense"),
        ("Utilities", "expense"),
        ("Home Services", "expense"),
        ("Rent/Mortgage", "expense"),
        ("Subscriptions", "expense"),
        ("Seguros Tarjetas", "expense"),
        ("Transactions", "expense"),
        ("Salary", "income"),
        ("Other Income", "income"),
    ]

    print("\n📁 Creating default categories...")
    for name, cat_type in default_categories:
        existing = db.query(Category).filter(Category.name == name).first()
        if not existing:
            category = Category(name=name, category_type=cat_type)
            db.add(category)
            print(f"  ✓ Created category: {name}")
        else:
            print(f"  ⊘ Category already exists: {name}")

    db.commit()


def add_sample_card(db):
    """Interactively add a card."""
    print("\n💳 Add a Card")
    print("-" * 40)

    name = input("Card name (e.g., 'Visa Gold'): ").strip()
    if not name:
        print("✗ Card name required")
        return

    last_four = input("Last 4 digits: ").strip()
    card_type = input("Type (credit/debit): ").strip().lower()
    bank = input("Bank name: ").strip()

    print("\nDoes this card support:")
    supports_crc = input("  CRC? (y/n, default y): ").strip().lower() != 'n'
    supports_usd = input("  USD? (y/n, default y): ").strip().lower() != 'n'

    # Credit card specific fields
    payment_due = None
    cutoff = None
    limit_crc = None
    limit_usd = None

    if card_type == 'credit':
        payment_input = input("Payment due day (1-31, or Enter to skip): ").strip()
        if payment_input.isdigit():
            payment_due = int(payment_input)

        cutoff_input = input("Statement cutoff day (1-31, or Enter to skip): ").strip()
        if cutoff_input.isdigit():
            cutoff = int(cutoff_input)

        if supports_crc:
            limit_input = input("Credit limit in CRC (or Enter to skip): ").strip()
            if limit_input:
                limit_crc = float(limit_input.replace(',', ''))

        if supports_usd:
            limit_input = input("Credit limit in USD (or Enter to skip): ").strip()
            if limit_input:
                limit_usd = float(limit_input.replace(',', ''))

    # Create card
    card = Card(
        name=name,
        last_four=last_four,
        card_type=card_type,
        bank=bank,
        supports_crc=supports_crc,
        supports_usd=supports_usd,
        payment_due_day=payment_due,
        cutoff_day=cutoff,
        credit_limit_crc=limit_crc,
        credit_limit_usd=limit_usd,
    )

    db.add(card)
    db.commit()

    print(f"\n✓ Card '{name}' added successfully!")


def add_sample_account(db):
    """Interactively add an account."""
    print("\n🏦 Add an Account")
    print("-" * 40)

    name = input("Account name (e.g., 'Main Checking'): ").strip()
    if not name:
        print("✗ Account name required")
        return

    account_type = input("Type (checking/savings/cash): ").strip().lower()
    iban = input("IBAN (or Enter to skip): ").strip()
    account_number = input("Account number (or Enter to skip): ").strip()
    currency = input("Currency (CRC/USD, default CRC): ").strip().upper() or "CRC"

    balance_input = input("Current balance (or Enter to skip): ").strip()
    balance = float(balance_input.replace(',', '')) if balance_input else None

    # Create account
    account = Account(
        name=name,
        account_type=account_type,
        iban=iban if iban else None,
        account_number=account_number if account_number else None,
        currency=currency,
        current_balance=balance,
    )

    db.add(account)
    db.commit()

    print(f"\n✓ Account '{name}' added successfully!")


def list_cards(db):
    """List all cards."""
    cards = db.query(Card).all()

    if not cards:
        print("\n📝 No cards found. Add some cards first!")
        return

    print("\n💳 Your Cards")
    print("-" * 60)
    for card in cards:
        currencies = []
        if card.supports_crc:
            currencies.append("CRC")
        if card.supports_usd:
            currencies.append("USD")

        print(f"  • {card.name} ({card.bank})")
        print(f"    Last 4: {card.last_four} | Type: {card.card_type}")
        print(f"    Currencies: {', '.join(currencies)}")
        if card.payment_due_day:
            print(f"    Payment due: Day {card.payment_due_day}")
        print()


def list_accounts(db):
    """List all accounts."""
    accounts = db.query(Account).all()

    if not accounts:
        print("\n📝 No accounts found. Add some accounts first!")
        return

    print("\n🏦 Your Accounts")
    print("-" * 60)
    for account in accounts:
        print(f"  • {account.name} ({account.account_type})")
        if account.iban:
            print(f"    IBAN: {account.iban}")
        if account.current_balance is not None:
            print(f"    Balance: {account.currency} {account.current_balance:,.2f}")
        print()


def add_email_source(db):
    """Interactively add an email source."""
    print("\n📧 Add an Email Source")
    print("-" * 40)

    name = input("Source name (e.g., 'BAC San José'): ").strip()
    if not name:
        print("✗ Source name required")
        return

    email = input("Email address (e.g., 'notificacion@notificacionesbaccr.com'): ").strip()
    if not email:
        print("✗ Email address required")
        return

    # Check if already exists
    existing = db.query(EmailSource).filter(EmailSource.email_address == email).first()
    if existing:
        print(f"✗ Email source '{email}' already exists!")
        return

    print("\nNote: Sync will fetch ALL emails from this address and parse them for transaction data.")
    print("Keywords are optional (for reference only, not used for filtering).")
    keywords = input("Subject keywords (optional, press Enter to skip): ").strip()

    if not keywords:
        keywords = None

    # Create email source
    source = EmailSource(
        name=name,
        email_address=email,
        subject_keywords=keywords,
    )

    db.add(source)
    db.commit()

    print(f"\n✓ Email source '{name}' added successfully!")
    print(f"  Email: {email}")
    if keywords:
        print(f"  Keywords (reference): {keywords}")


def list_email_sources(db):
    """List all email sources."""
    sources = db.query(EmailSource).all()

    if not sources:
        print("\n📝 No email sources found. Add some sources first!")
        return

    print("\n📧 Your Email Sources")
    print("-" * 60)
    for source in sources:
        status = "✓ Active" if source.is_active else "✗ Inactive"
        print(f"  • {source.name} ({status})")
        print(f"    Email: {source.email_address}")
        print(f"    Keywords: {source.subject_keywords}")
        print()


def add_subscription(db):
    """Interactively add a subscription."""
    print("\n📅 Add a Subscription")
    print("-" * 40)

    name = input("Subscription name (e.g., 'Netflix'): ").strip()
    if not name:
        print("✗ Subscription name required")
        return

    amount_input = input("Monthly amount: ").strip()
    try:
        amount = float(amount_input.replace(',', ''))
    except ValueError:
        print("✗ Invalid amount")
        return

    currency = input("Currency (CRC/USD, default CRC): ").strip().upper() or "CRC"
    if currency not in ["CRC", "USD"]:
        print("✗ Currency must be CRC or USD")
        return

    billing_day_input = input("Billing day (1-31): ").strip()
    if not billing_day_input.isdigit() or not (1 <= int(billing_day_input) <= 31):
        print("✗ Billing day must be between 1 and 31")
        return

    billing_day = int(billing_day_input)
    notes = input("Notes (optional): ").strip() or None

    subscription = Subscription(
        name=name,
        amount=amount,
        currency=currency,
        billing_day=billing_day,
        notes=notes
    )

    db.add(subscription)
    db.commit()
    print(f"\n✓ Subscription '{name}' added!")


def list_subscriptions(db):
    """List all active subscriptions."""
    subs = db.query(Subscription).filter(Subscription.is_active == True).order_by(Subscription.billing_day).all()

    if not subs:
        print("\n📝 No subscriptions found.")
        return

    print("\n📅 Your Subscriptions")
    print("-" * 60)

    crc_subs = [s for s in subs if s.currency == "CRC"]
    usd_subs = [s for s in subs if s.currency == "USD"]

    if crc_subs:
        print("\n  CRC Subscriptions:")
        for sub in crc_subs:
            print(f"    Day {sub.billing_day:2d}: {sub.name:20s} - ₡{sub.amount:,.2f}")
        print(f"  Total: ₡{sum(s.amount for s in crc_subs):,.2f}/month\n")

    if usd_subs:
        print("\n  USD Subscriptions:")
        for sub in usd_subs:
            print(f"    Day {sub.billing_day:2d}: {sub.name:20s} - ${sub.amount:,.2f}")
        print(f"  Total: ${sum(s.amount for s in usd_subs):,.2f}/month\n")


def interactive_menu(db):
    """Interactive menu for database setup."""
    while True:
        print("\n" + "="*60)
        print("Database Setup & Management")
        print("="*60)
        print("1. Create default categories")
        print("2. Add a card")
        print("3. Add an account")
        print("4. Add an email source")
        print("5. Add a subscription")
        print("6. List cards")
        print("7. List accounts")
        print("8. List email sources")
        print("9. List subscriptions")
        print("10. Exit")
        print()

        choice = input("Choose an option (1-10): ").strip()

        if choice == '1':
            create_default_categories(db)
        elif choice == '2':
            add_sample_card(db)
        elif choice == '3':
            add_sample_account(db)
        elif choice == '4':
            add_email_source(db)
        elif choice == '5':
            add_subscription(db)
        elif choice == '6':
            list_cards(db)
        elif choice == '7':
            list_accounts(db)
        elif choice == '8':
            list_email_sources(db)
        elif choice == '9':
            list_subscriptions(db)
        elif choice == '10':
            print("\n✓ Goodbye!")
            break
        else:
            print("\n✗ Invalid option")


def main():
    """Main entry point."""
    print("\n🏦 Budgeting App - Database Initialization\n")

    # Initialize database
    print("Initializing database...")
    init_db()

    # Create session
    db = SessionLocal()

    try:
        interactive_menu(db)
    except KeyboardInterrupt:
        print("\n\n✗ Cancelled by user")
    finally:
        db.close()


if __name__ == "__main__":
    main()
