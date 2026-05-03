"""
Database configuration - SQLite + SQLAlchemy

Resolution order for the database URL:
  1. Any of the known URL-style env vars (DATABASE_URL, POSTGRES_URL, etc.)
  2. Construct a URL from individual PG* vars that Railway always injects
     (PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE)
  3. Fall back to local SQLite for development
"""

import os
import logging

logger = logging.getLogger(__name__)

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


def _resolve_database_url() -> str:
    # ── 1. Try all URL-style environment variable names ──────────────────────
    url_candidates = [
        "DATABASE_URL",
        "DATABASE_PRIVATE_URL",
        "POSTGRES_URL",
        "POSTGRES_PRIVATE_URL",
        "POSTGRESQL_URL",
    ]
    for var in url_candidates:
        url = os.getenv(var, "").strip()
        if url:
            logger.info("✅ DB URL from env var: %s", var)
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url

    # ── 2. Build URL from individual PG* variables (Railway always sets these
    #       when a Postgres service is linked, even if DATABASE_URL is absent) ─
    pghost = os.getenv("PGHOST", "").strip()
    pgport = os.getenv("PGPORT", "5432").strip()
    pguser = os.getenv("PGUSER", "").strip()
    pgpass = os.getenv("PGPASSWORD", "").strip()
    pgdb   = os.getenv("PGDATABASE", "railway").strip()

    if pghost and pguser:
        url = f"postgresql://{pguser}:{pgpass}@{pghost}:{pgport}/{pgdb}"
        logger.info("✅ DB URL built from PG* variables (host: %s)", pghost)
        return url

    # ── 3. Log ALL environment variables that mention PG or DATABASE so the
    #       deploy log tells us exactly what Railway injected ─────────────────
    debug_vars = {
        k: ("***" if any(s in k.upper() for s in ["PASS", "SECRET", "KEY"]) else v)
        for k, v in os.environ.items()
        if any(s in k.upper() for s in ["DATABASE", "POSTGRES", "PG"])
    }
    logger.warning(
        "⚠️  No PostgreSQL credentials found. Falling back to SQLite.\n"
        "    DB-related env vars visible to app: %s\n"
        "    Fix: in Railway → web service → Variables, add:\n"
        "    DATABASE_URL = ${{Postgres.DATABASE_URL}}",
        debug_vars or "(none)",
    )
    return "sqlite:///./tamil_ocr.db"


DATABASE_URL = _resolve_database_url()

_is_sqlite   = "sqlite"     in DATABASE_URL
_is_postgres = "postgresql" in DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_pre_ping=True,
    pool_size=5     if _is_postgres else 1,
    max_overflow=10 if _is_postgres else 0,
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db():
    """Create all tables and apply incremental column migrations."""
    from app.models import transaction, market_rate, ocr_session, feedback, customer, loan  # noqa: F401

    logger.info("📦 create_all → %s", str(engine.url).split("@")[-1])
    Base.metadata.create_all(bind=engine)
    logger.info("✅ All tables created / verified")
    _run_migrations()


def _run_migrations():
    """Safely add new columns to existing tables without dropping data."""
    import sqlalchemy as sa

    migrations = [
        ("transactions", "grade",              "VARCHAR(1)"),
        ("transactions", "was_manually_added", "BOOLEAN DEFAULT FALSE"),
    ]

    with engine.connect() as conn:
        for table, col, sql_type in migrations:
            try:
                if _is_postgres:
                    conn.execute(sa.text(
                        f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} {sql_type}"
                    ))
                else:
                    conn.execute(sa.text(
                        f"ALTER TABLE {table} ADD COLUMN {col} {sql_type}"
                    ))
                conn.commit()
            except Exception:
                conn.rollback()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
