"""Database configuration and session management."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from pathlib import Path

# Get the project root directory
BASE_DIR = Path(__file__).resolve().parent.parent

# Database URL - SQLite file in project root
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR}/budgeting.db")

# Create engine
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # Needed for SQLite
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for FastAPI routes to get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables."""
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()
    print(f"✓ Database initialized at: {DATABASE_URL}")


def _add_missing_columns():
    """create_all() only creates missing tables, not columns added to
    existing ones - add those here (idempotent, runs every startup)."""
    columns = {c["name"] for c in inspect(engine).get_columns("budgets")}
    if "is_protected" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE budgets ADD COLUMN is_protected BOOLEAN NOT NULL DEFAULT 0"))
            # Rent and utilities are the essentials the suggestions protect too.
            conn.execute(text(
                "UPDATE budgets SET is_protected = 1 WHERE category_id IN ("
                "SELECT id FROM categories WHERE lower(name) IN "
                "('rent', 'rent/mortgage', 'home/utilities', 'utilities'))"
            ))
