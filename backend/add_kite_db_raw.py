"""Dev helper: seed Zerodha exchange_config via raw sqlite.

Credentials from env (KITE_API_KEY / KITE_API_SECRET or ZERODHA_*).
"""
import os
import sqlite3
import sys

api_key = os.environ.get("KITE_API_KEY") or os.environ.get("ZERODHA_API_KEY")
api_secret = os.environ.get("KITE_API_SECRET") or os.environ.get("ZERODHA_API_SECRET")
if not api_key or not api_secret:
    print(
        "Set KITE_API_KEY and KITE_API_SECRET (or ZERODHA_*) before running.",
        file=sys.stderr,
    )
    sys.exit(1)

db_path = os.environ.get("STERLING_DB_PATH", "sterling.db")
conn = sqlite3.connect(db_path)
try:
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM exchange_config WHERE name='zerodha'")
    if cursor.fetchone():
        print("Zerodha already exists")
    else:
        cursor.execute("PRAGMA table_info(exchange_config)")
        columns = cursor.fetchall()
        print("Columns:", [c[1] for c in columns])

        try:
            cursor.execute(
                """
                INSERT INTO exchange_config
                    (id, name, display_name, api_key, api_secret, is_paper, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "zerodha_default",
                    "zerodha",
                    "Zerodha Kite",
                    api_key,
                    api_secret,
                    1,
                    1,
                ),
            )
            conn.commit()
            print("Added Zerodha exchange!")
        except Exception as e:
            print("Error inserting:", e)
finally:
    conn.close()
