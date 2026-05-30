import sqlite3

DB='profitclean.db'
conn=sqlite3.connect(DB)
c=conn.cursor()

# Check schema
c.execute("PRAGMA table_info(business_profile)")
cols = {row[1]: row[2] for row in c.fetchall()}
print("business_profile columns:")
for col, dtype in cols.items():
    print(f"  {col}: {dtype}")

# Try the failing query
try:
    c.execute("SELECT business_name, phone, email, hourly_wage, min_job_fee, home_city, smtp_email, smtp_password, smtp_server, smtp_port FROM business_profile WHERE company_id = ?", (1,))
    row = c.fetchone()
    print(f"\n✅ Query successful: {row}")
except Exception as e:
    print(f"\n❌ Query failed: {e}")

conn.close()
