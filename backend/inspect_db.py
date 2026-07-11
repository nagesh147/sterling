import sqlite3

# Fixed SQL only — no dynamic identifier interpolation.
_PRAGMA_QUERIES = {
    "positions": 'PRAGMA table_info("positions")',
    "signal_history": 'PRAGMA table_info("signal_history")',
}


def inspect_more():
    conn = sqlite3.connect("sterling_paper.db")
    try:
        cursor = conn.cursor()
        for name, sql in _PRAGMA_QUERIES.items():
            cursor.execute(sql)
            print(f"\n{name} schema:")
            for row in cursor.fetchall():
                print(row)
    finally:
        conn.close()


if __name__ == "__main__":
    inspect_more()

