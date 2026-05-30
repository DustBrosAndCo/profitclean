import sqlite3
import sys
sys.path.insert(0, 'd:\\DBAPP')

from app import migrate_database

print("Running migrate_database()...")
migrate_database()
print("Migration complete!")

# Verify the columns were added
DB='profitclean.db'
conn=sqlite3.connect(DB)
c=conn.cursor()

c.execute("PRAGMA table_info(worker_badges)")
cols = [row[1] for row in c.fetchall()]
print(f"Worker badges columns after migration: {cols}")

# Test the query
try:
    c.execute("SELECT badge_name, badge_icon, earned_at FROM worker_badges WHERE worker_id = ? AND company_id = ? ORDER BY earned_at", (1, 1))
    results = c.fetchall()
    print(f"✅ Query successful, found {len(results)} rows")
except Exception as e:
    print(f"❌ Query failed: {e}")

conn.close()
