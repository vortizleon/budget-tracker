"""CLI script to sync transactions from Gmail to database."""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import SessionLocal, init_db
from backend.models import Transaction, Card, Category, EmailSource, CategorizationRule
from backend.gmail_client import GmailClient
from backend.email_parser import EmailParser
from backend import debt


class TransactionSyncer:
    """Syncs Gmail bank emails to database."""

    def __init__(self, db: Session):
        """
        Initialize syncer.

        Args:
            db: Database session
        """
        self.db = db
        self.gmail_client = GmailClient()
        self.parser = EmailParser()

    def find_card_by_last_four(self, last_four: str) -> int:
        """
        Find card ID by last 4 digits.

        Args:
            last_four: Last 4 digits of card

        Returns:
            Card ID or None
        """
        if not last_four:
            return None

        card = self.db.query(Card).filter(
            Card.last_four == last_four,
            Card.is_active == True
        ).first()

        return card.id if card else None

    def match_categorization_rule(self, commerce_name: str):
        """
        Check commerce_name against active CategorizationRules.

        A pattern wrapped in '%' on both ends is a contains-match, trailing
        '%' is a starts-with match, leading '%' is an ends-with match, and a
        bare pattern is an exact match (all case-insensitive).

        Args:
            commerce_name: Commerce name from transaction

        Returns:
            Matching category ID, or None if no rule applies
        """
        if not commerce_name:
            return None

        name = commerce_name.strip().upper()
        rules = self.db.query(CategorizationRule).filter(
            CategorizationRule.is_active == True
        ).order_by(CategorizationRule.priority.desc()).all()

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

    def find_or_create_category(self, commerce_name: str) -> int:
        """
        Find category for transaction: first by CategorizationRule match,
        falling back to "Uncategorized".

        Args:
            commerce_name: Commerce name from transaction

        Returns:
            Category ID
        """
        rule_category_id = self.match_categorization_rule(commerce_name)
        if rule_category_id:
            return rule_category_id

        category = self.db.query(Category).filter(
            Category.name == "Uncategorized"
        ).first()

        if not category:
            category = Category(
                name="Uncategorized",
                category_type="expense"
            )
            self.db.add(category)
            self.db.commit()
            self.db.refresh(category)

        return category.id

    def find_category_by_name(self, name: str) -> int:
        """
        Find a category by exact name, falling back to Uncategorized.

        Args:
            name: Category name (e.g. "Rent/Mortgage")

        Returns:
            Category ID
        """
        category = self.db.query(Category).filter(Category.name == name).first()
        if category:
            return category.id
        return self.find_or_create_category(None)

    def transaction_exists(self, gmail_message_id: str) -> bool:
        """
        Check if transaction already exists in database.

        Args:
            gmail_message_id: Gmail message ID

        Returns:
            True if exists, False otherwise
        """
        exists = self.db.query(Transaction).filter(
            Transaction.gmail_message_id == gmail_message_id
        ).first() is not None

        return exists

    def save_transaction(self, parsed_data: dict) -> bool:
        """
        Save parsed transaction to database.

        Args:
            parsed_data: Parsed transaction dictionary

        Returns:
            True if saved, False if skipped (duplicate)
        """
        gmail_id = parsed_data.get('gmail_message_id')

        # Check for duplicate
        if self.transaction_exists(gmail_id):
            return False

        # Find card
        card_id = self.find_card_by_last_four(parsed_data.get('card_last_four'))

        # A payment the user already logged by hand shouldn't be added again
        # when the bank's own email for it arrives.
        if parsed_data['transaction_type'] == 'payment' and debt.manual_payment_exists(
            self.db, card_id, parsed_data['currency'], parsed_data['amount'], parsed_data['date']
        ):
            return False

        # Find or create category (an explicit hint, e.g. the recurring rent
        # transfer, overrides the default "Uncategorized" bucket)
        suggested_category = parsed_data.get('suggested_category')
        if suggested_category:
            category_id = self.find_category_by_name(suggested_category)
        else:
            category_id = self.find_or_create_category(parsed_data.get('commerce_name'))

        # Create transaction
        transaction = Transaction(
            date=parsed_data['date'],
            amount=parsed_data['amount'],
            currency=parsed_data['currency'],
            commerce_name=parsed_data.get('commerce_name'),
            description=parsed_data.get('description'),
            transaction_type=parsed_data['transaction_type'],
            card_id=card_id,
            category_id=category_id,
            gmail_message_id=gmail_id,
            raw_email_body=parsed_data.get('raw_email_body', '')[:1000]
        )

        self.db.add(transaction)
        self.db.commit()

        return True

    def sync(
        self,
        bank_email: str,
        keywords: list = None,
        days_back: int = 30,
        max_emails: int = 100
    ):
        """
        Sync transactions from Gmail.

        Args:
            bank_email: Bank's email address
            keywords: Keywords to search for in subject
            days_back: How many days back to search
            max_emails: Maximum emails to fetch
        """
        print("\n" + "="*60)
        print("Starting Gmail → Database Sync")
        print("="*60)

        # Fetch emails from Gmail
        print(f"\n📧 Fetching emails from {bank_email}...")
        emails = self.gmail_client.fetch_bank_emails(
            bank_email=bank_email,
            keywords=keywords or ['compra', 'pago', 'purchase', 'payment'],
            days_back=days_back,
            max_results=max_emails
        )

        if not emails:
            print("✗ No emails found matching criteria")
            return

        # Parse emails
        print(f"\n📝 Parsing {len(emails)} emails...")
        parsed_transactions = self.parser.parse_email_batch(emails)

        if not parsed_transactions:
            print("✗ No transactions could be parsed")
            return

        # Save to database
        print(f"\n💾 Saving transactions to database...")
        saved_count = 0
        skipped_count = 0

        for transaction_data in parsed_transactions:
            if self.save_transaction(transaction_data):
                saved_count += 1
                print(f"  ✓ Saved: {transaction_data['date']} - "
                      f"{transaction_data['commerce_name']} - "
                      f"{transaction_data['amount']} {transaction_data['currency']}")
            else:
                skipped_count += 1

        # Summary
        print("\n" + "="*60)
        print("Sync Complete!")
        print("="*60)
        print(f"✓ New transactions: {saved_count}")
        print(f"⊘ Duplicates skipped: {skipped_count}")
        print(f"📊 Total processed: {len(parsed_transactions)}")

        # Show transaction summary
        self.show_summary()

    def sync_all_active_sources(
        self,
        days_back: int = 30,
        max_emails: int = 100,
        after_date=None,
        before_date=None
    ) -> dict:
        """
        Sync transactions from every active EmailSource in the database.

        Args:
            days_back: How many days back to search (ignored if after_date is given)
            max_emails: Maximum emails to fetch per source
            after_date: Explicit lower bound - use with before_date to backfill
                a specific gap without re-fetching the whole rolling window
            before_date: Explicit upper bound (exclusive)

        Returns:
            Summary dict with total_saved, total_skipped, and per-source results
        """
        email_sources = self.db.query(EmailSource).filter(EmailSource.is_active == True).all()

        if not email_sources:
            print("✗ No email sources configured!")
            print("\nPlease add email sources first:")
            print("  Run: python backend/init_db.py")
            print("  Choose option 4: Add an email source")
            return {"total_saved": 0, "total_skipped": 0, "sources": []}

        print("📧 Configured Email Sources:")
        print("-" * 60)
        for source in email_sources:
            print(f"  • {source.name}")
            print(f"    Email: {source.email_address}")
            print(f"    Keywords: {source.subject_keywords}")
        print("-" * 60)

        total_saved = 0
        total_skipped = 0
        source_results = []

        for source in email_sources:
            print(f"\n{'='*60}")
            print(f"Syncing from: {source.name} ({source.email_address})")
            print(f"{'='*60}")

            emails = self.gmail_client.fetch_bank_emails(
                bank_email=source.email_address,
                keywords=source.get_keywords_list(),
                days_back=days_back,
                max_results=max_emails,
                after_date=after_date,
                before_date=before_date
            )

            if not emails:
                print(f"✗ No emails found from {source.name}")
                source_results.append({"name": source.name, "saved": 0, "skipped": 0})
                continue

            print(f"\n📝 Parsing {len(emails)} emails...")
            parsed_transactions = self.parser.parse_email_batch(emails)

            if not parsed_transactions:
                print(f"✗ No transactions could be parsed from {source.name}")
                source_results.append({"name": source.name, "saved": 0, "skipped": 0})
                continue

            print(f"\n💾 Saving transactions to database...")
            saved_count = 0
            skipped_count = 0

            for transaction_data in parsed_transactions:
                if self.save_transaction(transaction_data):
                    saved_count += 1
                    print(f"  ✓ Saved: {transaction_data['date']} - "
                          f"{transaction_data['commerce_name']} - "
                          f"{transaction_data['amount']} {transaction_data['currency']}")
                else:
                    skipped_count += 1

            total_saved += saved_count
            total_skipped += skipped_count
            source_results.append({"name": source.name, "saved": saved_count, "skipped": skipped_count})

            print(f"\n✓ From {source.name}: {saved_count} new, {skipped_count} duplicates")

        print("\n" + "="*60)
        print("Overall Sync Summary")
        print("="*60)
        print(f"✓ Total new transactions: {total_saved}")
        print(f"⊘ Total duplicates skipped: {total_skipped}")
        print(f"📧 Sources synced: {len(email_sources)}")

        return {"total_saved": total_saved, "total_skipped": total_skipped, "sources": source_results}

    def show_summary(self):
        """Show database statistics."""
        print("\n" + "-"*60)
        print("Database Summary")
        print("-"*60)

        total_transactions = self.db.query(func.count(Transaction.id)).scalar()
        total_amount_crc = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.currency == 'CRC',
            Transaction.transaction_type == 'purchase'
        ).scalar() or 0

        total_amount_usd = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.currency == 'USD',
            Transaction.transaction_type == 'purchase'
        ).scalar() or 0

        total_cards = self.db.query(func.count(Card.id)).scalar()

        print(f"Total transactions: {total_transactions}")
        print(f"Total cards: {total_cards}")
        print(f"Total purchases (CRC): ₡{total_amount_crc:,.2f}")
        print(f"Total purchases (USD): ${total_amount_usd:,.2f}")
        print("-"*60)


def main():
    """Main entry point for sync script."""
    print("\n🏦 Budgeting App - Gmail Sync Tool\n")

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        # Create syncer
        syncer = TransactionSyncer(db)

        # Get active email sources from database
        email_sources = db.query(EmailSource).filter(EmailSource.is_active == True).all()

        if not email_sources:
            print("✗ No email sources configured!")
            print("\nPlease add email sources first:")
            print("  Run: python backend/init_db.py")
            print("  Choose option 4: Add an email source")
            return

        # Show configured sources
        print("📧 Configured Email Sources:")
        print("-" * 60)
        for source in email_sources:
            print(f"  • {source.name}")
            print(f"    Email: {source.email_address}")
            print(f"    Keywords: {source.subject_keywords}")
        print("-" * 60)

        # Ask for days back
        print("\nHow many days back to search? (default: 30)")
        days_input = input("> ").strip()
        days_back = int(days_input) if days_input.isdigit() else 30

        # Sync from all sources
        total_saved = 0
        total_skipped = 0

        for source in email_sources:
            print(f"\n{'='*60}")
            print(f"Syncing from: {source.name} ({source.email_address})")
            print(f"{'='*60}")

            # Fetch emails from this source
            emails = syncer.gmail_client.fetch_bank_emails(
                bank_email=source.email_address,
                keywords=source.get_keywords_list(),
                days_back=days_back,
                max_results=100
            )

            if not emails:
                print(f"✗ No emails found from {source.name}")
                continue

            # Parse emails
            print(f"\n📝 Parsing {len(emails)} emails...")
            parsed_transactions = syncer.parser.parse_email_batch(emails)

            if not parsed_transactions:
                print(f"✗ No transactions could be parsed from {source.name}")
                continue

            # Save to database
            print(f"\n💾 Saving transactions to database...")
            saved_count = 0
            skipped_count = 0

            for transaction_data in parsed_transactions:
                if syncer.save_transaction(transaction_data):
                    saved_count += 1
                    print(f"  ✓ Saved: {transaction_data['date']} - "
                          f"{transaction_data['commerce_name']} - "
                          f"{transaction_data['amount']} {transaction_data['currency']}")
                else:
                    skipped_count += 1

            total_saved += saved_count
            total_skipped += skipped_count

            print(f"\n✓ From {source.name}: {saved_count} new, {skipped_count} duplicates")

        # Overall summary
        print("\n" + "="*60)
        print("Overall Sync Summary")
        print("="*60)
        print(f"✓ Total new transactions: {total_saved}")
        print(f"⊘ Total duplicates skipped: {total_skipped}")
        print(f"📧 Sources synced: {len(email_sources)}")

        # Show transaction summary
        syncer.show_summary()

    except KeyboardInterrupt:
        print("\n\n✗ Sync cancelled by user")
    except Exception as e:
        print(f"\n✗ Error during sync: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
