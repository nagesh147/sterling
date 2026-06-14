from app.persistence.session import SessionLocal
from app.persistence.models import ExchangeConfigModel

db = SessionLocal()
if not db.query(ExchangeConfigModel).filter_by(name="zerodha").first():
    db.add(ExchangeConfigModel(
        id="zerodha_default",
        name="zerodha",
        display_name="Zerodha Kite",
        api_key="dummy_key",
        api_secret="dummy_secret",
        is_paper=True,
        is_active=True
    ))
    db.commit()
    print("Added Zerodha exchange")
else:
    print("Zerodha exchange already exists")
