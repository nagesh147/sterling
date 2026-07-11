import sqlite3

_ALLOWED_TABLES = frozenset({
    "positions",
    "signal_history",
    "calibration_trades",
    "pnl_history",
})


def check():
    conn = sqlite3.connect("sterling_paper.db")
    try:
        cursor = conn.cursor()
        for t in sorted(_ALLOWED_TABLES):
            # Table names cannot be bound as parameters; restrict to allowlist.
            cursor.execute(f'SELECT COUNT(*) FROM "{t}";')
            print(f"Table {t} has {cursor.fetchone()[0]} rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    check()
