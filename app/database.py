"""
Database configuration - SQLite + SQLAlchemy
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./tamil_ocr.db")

# Railway provides postgres:// but SQLAlchemy requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create all tables and apply incremental column migrations."""
    from app.models import transaction, market_rate, ocr_session, feedback, customer  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Safely add new columns to existing tables without dropping data."""
    import sqlalchemy as sa
    is_postgres = "postgresql" in str(engine.url)
    migrations = [
        # (table, column, sql_type)
        ("transactions", "grade", "VARCHAR(1)"),
    ]
    with engine.connect() as conn:
        for table, col, sql_type in migrations:
            try:
                if is_postgres:
                    conn.execute(sa.text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {sql_type}"
                    ))
                else:
                    # SQLite doesn't support IF NOT EXISTS on ALTER TABLE
                    conn.execute(sa.text(
                        f"ALTER TABLE {table} ADD COLUMN {col} {sql_type}"
                    ))
                conn.commit()
            except Exception:
                conn.rollback()  # Column already exists — safe to ignore


def get_db():
    """Dependency: yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
