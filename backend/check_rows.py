import sqlite3

def check():
    conn = sqlite3.connect('sterling_paper.db')
    cursor = conn.cursor()
    
    for t in ['positions', 'signal_history', 'calibration_trades', 'pnl_history']:
        cursor.execute(f"SELECT COUNT(*) FROM {t};")
        print(f"Table {t} has {cursor.fetchone()[0]} rows.")

if __name__ == '__main__':
    check()
