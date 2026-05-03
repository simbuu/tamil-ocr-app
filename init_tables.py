"""
Standalone table initialisation script.

Run this once to create all tables in the database pointed to by DATABASE_URL:

    python init_tables.py

On Railway you can run it via:  Railway Dashboard → Service → Settings → Run Command
or just redeploy — the app's lifespan handler calls init_db() automatically on startup.
"""

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from app.database import init_db, DATABASE_URL, engine
from app.services.market_rate_service import seed_default_rates

print(f"\n🔌 Connecting to: {str(engine.url).split('@')[-1]}\n")

init_db()
seed_default_rates()

print("\n✅ Done — all tables created and default market rates seeded.\n")
