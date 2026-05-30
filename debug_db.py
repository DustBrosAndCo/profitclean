import sqlite3
import pandas as pd
from datetime import datetime

DB='profitclean.db'
print('DB path:', DB)
conn = sqlite3.connect(DB)
try:
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_templates'")
    tbl = c.fetchone()
    print('email_templates exists:', tbl)
    if not tbl:
        print('No email_templates table; exiting')
    else:
        c.execute("PRAGMA table_info(email_templates)")
        cols = c.fetchall()
        print('columns:', cols)
        try:
            comps = pd.read_sql_query('SELECT id, name FROM companies WHERE is_active = 1 ORDER BY name', conn)
            print('companies count:', len(comps))
            if len(comps)>0:
                sel = comps['id'].iloc[0]
                print('selected company sample', type(sel), sel)
                try:
                    df = pd.read_sql_query('SELECT id, name, subject, is_active FROM email_templates WHERE company_id = ? ORDER BY name', conn, params=(int(sel),))
                    print('templates rows:', len(df))
                    print(df.head())
                except Exception as e:
                    print('pandas.read_sql_query error:', repr(e))
        except Exception as e:
            print('error querying companies:', repr(e))
finally:
    conn.close()
print('done')
