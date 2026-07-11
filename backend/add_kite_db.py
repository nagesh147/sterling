"""Dev helper: seed a Zerodha exchange_config row via SQLAlchemy.

Credentials must come from the environment — never hardcode secrets.
  KITE_API_KEY / KITE_API_SECRET  (preferred)
  or ZERODHA_API_KEY / ZERODHA_API_SECRET
"""
import os
import sys

from app.persistence.session import SessionLocal
from app.persistence.models import ExchangeConfigModel

api_key = os.environ.get("KITE_API_KEY") or os.environ.get("ZERODHA_API_KEY")
api_secret = os.environ.get("KITE_API_SECRET") or os.environ.get("ZERODHA_API_SECRET")
if not api_key or not api_secret:
    print(
        "Set KITE_API_KEY and KITE_API_SECRET (or ZERODHA_*) before running.",
        file=sys.stderr,
    )
    sys.exit(1)

db = SessionLocal()
try:
    if not db.query(ExchangeConfigModel).filter_by(name="zerodha").first():
        db.add(ExchangeConfigModel(
            id="zerodha_default",
            name="zerodha",
            display_name="Zerodha Kite",
            api_key=api_key,
            api_secret=api_secret,
            is_paper=True,
            is_active=True,
        ))
        db.commit()
        print("Added Zerodha exchange")
    else:
        print("Zerodha exchange already exists")
finally:
    db.close()
