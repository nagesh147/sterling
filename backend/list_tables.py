import sqlite3
conn = sqlite3.connect('sterling_paper.db')
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
print("Tables:", cursor.fetchall())

cursor.execute("PRAGMA table_info(exchanges)")
print("Cols:", [c[1] for c in cursor.fetchall()])
conn.close()
