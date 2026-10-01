"""Migrate database schema to add new fields."""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

DB_PATH = "budgeting.db"


def migrate():
    """Add new columns to existing tables."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("🔄 Running database migrations...")

    # Check if color column exists in cards table
    cursor.execute("PRAGMA table_info(cards)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'color' not in columns:
        print("  ✓ Adding 'color' column to cards table...")
        cursor.execute("ALTER TABLE cards ADD COLUMN color VARCHAR DEFAULT '#4F46E5'")
        conn.commit()
    else:
        print("  ⊘ 'color' column already exists in cards table")

    # Check if color and icon columns exist in categories table
    cursor.execute("PRAGMA table_info(categories)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'color' not in columns:
        print("  ✓ Adding 'color' column to categories table...")
        cursor.execute("ALTER TABLE categories ADD COLUMN color VARCHAR DEFAULT '#6B7280'")
        conn.commit()
    else:
        print("  ⊘ 'color' column already exists in categories table")

    if 'icon' not in columns:
        print("  ✓ Adding 'icon' column to categories table...")
        cursor.execute("ALTER TABLE categories ADD COLUMN icon VARCHAR DEFAULT '📁'")
        conn.commit()
    else:
        print("  ⊘ 'icon' column already exists in categories table")

    # Check if default_category_id column exists in cards table
    cursor.execute("PRAGMA table_info(cards)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'default_category_id' not in columns:
        print("  ✓ Adding 'default_category_id' column to cards table...")
        cursor.execute("ALTER TABLE cards ADD COLUMN default_category_id INTEGER REFERENCES categories(id)")
        conn.commit()
    else:
        print("  ⊘ 'default_category_id' column already exists in cards table")

    # Create subscriptions table if it doesn't exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='subscriptions'
    """)
    if not cursor.fetchone():
        print("  ✓ Creating 'subscriptions' table...")
        cursor.execute("""
            CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR NOT NULL,
                amount DECIMAL(12, 2) NOT NULL,
                currency VARCHAR NOT NULL,
                billing_day INTEGER NOT NULL,
                category_id INTEGER REFERENCES categories(id),
                is_active BOOLEAN DEFAULT 1,
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            )
        """)
        conn.commit()
    else:
        print("  ⊘ 'subscriptions' table already exists")

    # Create installment_plans table ("tasa cero") if it doesn't exist
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='installment_plans'
    """)
    if not cursor.fetchone():
        print("  ✓ Creating 'installment_plans' table...")
        cursor.execute("""
            CREATE TABLE installment_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description VARCHAR NOT NULL,
                total_amount DECIMAL(12, 2) NOT NULL,
                currency VARCHAR NOT NULL,
                num_installments INTEGER NOT NULL,
                charge_day INTEGER NOT NULL DEFAULT 18,
                card_id INTEGER NOT NULL REFERENCES cards(id),
                category_id INTEGER REFERENCES categories(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    else:
        print("  ⊘ 'installment_plans' table already exists")

    # Check if installment_plan_id/installment_number columns exist in transactions table
    cursor.execute("PRAGMA table_info(transactions)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'installment_plan_id' not in columns:
        print("  ✓ Adding 'installment_plan_id' column to transactions table...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN installment_plan_id INTEGER REFERENCES installment_plans(id)")
        conn.commit()
    else:
        print("  ⊘ 'installment_plan_id' column already exists in transactions table")

    if 'installment_number' not in columns:
        print("  ✓ Adding 'installment_number' column to transactions table...")
        cursor.execute("ALTER TABLE transactions ADD COLUMN installment_number INTEGER")
        conn.commit()
    else:
        print("  ⊘ 'installment_number' column already exists in transactions table")

    # Check if starting_installment_number column exists in installment_plans table
    cursor.execute("PRAGMA table_info(installment_plans)")
    columns = [col[1] for col in cursor.fetchall()]

    if 'starting_installment_number' not in columns:
        print("  ✓ Adding 'starting_installment_number' column to installment_plans table...")
        cursor.execute("ALTER TABLE installment_plans ADD COLUMN starting_installment_number INTEGER NOT NULL DEFAULT 1")
        conn.commit()
    else:
        print("  ⊘ 'starting_installment_number' column already exists in installment_plans table")

    conn.close()
    print("\n✅ Migration completed successfully!")


if __name__ == "__main__":
    migrate()
