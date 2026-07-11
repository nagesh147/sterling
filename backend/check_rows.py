import sqlite3

# Fixed SQL only — no dynamic identifier interpolation.
_COUNT_QUERIES = {
    "positions": 'SELECT COUNT(*) FROM "positions"',
    "signal_history": 'SELECT COUNT(*) FROM "signal_history"',
    "calibration_trades": 'SELECT COUNT(*) FROM "calibration_trades"',
    "pnl_history": 'SELECT COUNT(*) FROM "pnl_history"',
}


def check():
    conn = sqlite3.connect("sterling_paper.db")
    try:
        cursor = conn.cursor()
        for name, sql in _COUNT_QUERIES.items():
            cursor.execute(sql)
            print(f"Table {name} has {cursor.fetchone()[0]} rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    check()

