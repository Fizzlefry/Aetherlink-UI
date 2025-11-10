import sqlite3

conn = sqlite3.connect("data/command_center.db")
cur = conn.cursor()
cur.execute('SELECT sql FROM sqlite_master WHERE type="table"')
tables = cur.fetchall()
for table in tables:
    print(table[0])
conn.close()
