import sqlite3

conn = sqlite3.connect('sterling.db')
cursor = conn.cursor()

# Check if zerodha exists
cursor.execute("SELECT id FROM exchange_config WHERE name='zerodha'")
if cursor.fetchone():
    print("Zerodha already exists")
else:
    # Insert it
    # We don't know the exact schema, let's look it up
    cursor.execute("PRAGMA table_info(exchange_config)")
    columns = cursor.fetchall()
    print("Columns:", [c[1] for c in columns])
    
    # insert statement
    try:
        cursor.execute("""
            INSERT INTO exchange_config (id, name, display_name, api_key, api_secret, is_paper, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, ('zerodha_default', 'zerodha', 'Zerodha Kite', 'dummy_key', 'dummy_secret', 1, 1))
        conn.commit()
        print("Added Zerodha exchange!")
    except Exception as e:
        print("Error inserting:", e)

conn.close()
