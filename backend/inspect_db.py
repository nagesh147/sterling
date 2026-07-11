import sqlite3

_ALLOWED_TABLES = frozenset({"positions", "signal_history"})


def inspect_more():
    conn = sqlite3.connect("sterling_paper.db")
    try:
        cursor = conn.cursor()
        for t in sorted(_ALLOWED_TABLES):
            # PRAGMA does not accept bound identifiers; tables are allowlisted.
            cursor.execute(f'PRAGMA table_info("{t}");')
            print(f"\n{t} schema:")
            for row in cursor.fetchall():
                print(row)
    finally:
        conn.close()


if __name__ == "__main__":
    inspect_more()
