import sqlite3
import pandas as pd
import json

def check_wf():
    conn = sqlite3.connect('sterling_paper.db')
    cursor = conn.cursor()
    cursor.execute("SELECT result_json FROM wf_results LIMIT 1;")
    row = cursor.fetchone()
    if row:
        data = json.loads(row[0])
        print("Keys in result_json:", data.keys())
        if 'trades' in data:
            print("Number of trades in wf_results:", len(data['trades']))
            if len(data['trades']) > 0:
                print("Sample trade:", data['trades'][0])

if __name__ == '__main__':
    check_wf()
