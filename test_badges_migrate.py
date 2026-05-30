import sqlite3
from datetime import datetime
DB='profitclean.db'

conn=sqlite3.connect(DB)
c=conn.cursor()

# Check schema before
c.execute("PRAGMA table_info(worker_badges)")
cols_before = [row[1] for row in c.fetchall()]
print(f"Columns before migration: {cols_before}")

# Check if company_id exists
has_company_id = 'company_id' in cols_before
print(f"Has company_id: {has_company_id}")

# Try the query that fails
if has_company_id:
    try:
        c.execute("SELECT badge_name, badge_icon, earned_at FROM worker_badges WHERE worker_id = ? AND company_id = ? ORDER BY earned_at", (1, 1))
        results = c.fetchall()
        print(f"Query successful, found {len(results)} rows")
    except Exception as e:
        print(f"Query failed: {e}")
else:
    print("company_id column missing - query will fail")

conn.close()
