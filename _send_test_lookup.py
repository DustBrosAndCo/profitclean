import sqlite3
DB='profitclean.db'
conn=sqlite3.connect(DB)
c=conn.cursor()
try:
    c.execute("PRAGMA table_info(business_profile)")
    cols=[r[1] for r in c.fetchall()]
    print('COLUMNS:', cols)
    c.execute('SELECT id, company_id, business_name, smtp_server, smtp_port, smtp_email, smtp_password FROM business_profile')
    rows=c.fetchall()
    if not rows:
        print('NO_ROWS')
    for r in rows:
        print(r)
except Exception as e:
    print('ERROR',e)
finally:
    conn.close()
