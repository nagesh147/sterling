import sqlite3

def inspect_more():
    conn = sqlite3.connect('sterling_paper.db')
    cursor = conn.cursor()
    
    for t in ['positions', 'signal_history']:
        cursor.execute(f"PRAGMA table_info({t});")
        print(f"\n{t} schema:")
        for row in cursor.fetchall():
            print(row)

if __name__ == '__main__':
    inspect_more()
