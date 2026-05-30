import sqlite3
from datetime import datetime
DB='profitclean.db'
conn=sqlite3.connect(DB)
c=conn.cursor()
# pick a worker id
c.execute("SELECT id, company_id FROM users WHERE role='worker' LIMIT 1")
row=c.fetchone()
if not row:
    print('No worker found')
else:
    wid, from_company = row
    c.execute("SELECT id FROM companies WHERE id != ? LIMIT 1", (from_company,))
    dest = c.fetchone()
    if not dest:
        print('No other company to transfer to')
    else:
        dest_id = dest[0]
        try:
            c.execute("UPDATE users SET company_id = ? WHERE id = ?", (dest_id, wid))
            c.execute("INSERT INTO worker_transfers (worker_id, from_company_id, to_company_id, transferred_by, transferred_at) VALUES (?,?,?,?,?)",
                      (wid, from_company, dest_id, 1, datetime.now().isoformat()))
            conn.commit()
            print(f'Transferred worker {wid} from {from_company} to {dest_id}')
            c.execute("SELECT * FROM worker_transfers WHERE worker_id = ? ORDER BY transferred_at DESC LIMIT 1", (wid,))
            print('latest transfer row:', c.fetchone())
        except Exception as e:
            conn.rollback()
            print('error:', e)
conn.close()
