import time
from app.services import db

db.init()
db.record_surface_params("BTC", [0.1, 0.2, 0.3, 0.4, 0.5], time.time())

with db._conn() as c:
    row = c.execute("SELECT * FROM iv_surface_params WHERE underlying='BTC'").fetchone()

if row:
    print(f"Success: {dict(row)}")
else:
    print("Failed")
