import sqlite3
import pandas as pd

def check_db():
    conn = sqlite3.connect('sterling_paper.db')
    df = pd.read_sql_query("SELECT symbol, resolution, count(*) as count FROM ohlcv GROUP BY symbol, resolution;", conn)
    print(df)

if __name__ == '__main__':
    check_db()
