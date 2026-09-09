import sqlite3
conn = sqlite3.connect('platform.db')
c = conn.cursor()
print('DEPOSITS:')
for d in c.execute("SELECT * FROM deposits WHERE user_id = 2").fetchall():
    print(d)

print('\nALL NON-ZERO DEPOSITS:')
for d in c.execute("SELECT * FROM deposits WHERE user_id != 0").fetchall():
    print(d)

print('\nINVOICES FOR USER 2:')
for inv in c.execute("SELECT * FROM invoices WHERE user_id = 2").fetchall():
    print(inv)
