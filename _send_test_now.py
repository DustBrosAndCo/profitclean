import sqlite3, smtplib, os
from datetime import datetime

DB='profitclean.db'
RECIPIENT='dustbrosco@gmail.com'

print('Looking up SMTP settings in', DB)
if not os.path.exists(DB):
    print('Database not found:', DB)
    raise SystemExit(1)

conn=sqlite3.connect(DB)
c=conn.cursor()
try:
    c.execute("PRAGMA table_info(business_profile)")
    cols=[r[1] for r in c.fetchall()]
    # Build a safe select based on available columns
    smtp_server = None
    smtp_port = None
    smtp_email = None
    smtp_password = None

    if not cols:
        print('business_profile table missing or has no columns')
        raise SystemExit(1)

    select_cols = []
    if 'smtp_server' in cols:
        select_cols.append('smtp_server')
    if 'smtp_port' in cols:
        select_cols.append('smtp_port')
    if 'smtp_email' in cols:
        select_cols.append('smtp_email')
    if 'smtp_password' in cols:
        select_cols.append('smtp_password')

    # If no SMTP columns exist, still attempt to read any row to confirm table exists
    if select_cols:
        query = 'SELECT ' + ', '.join(select_cols) + ' FROM business_profile LIMIT 1'
        c.execute(query)
        row = c.fetchone()
        if row:
            # map row values to variables based on select_cols order
            for i, col in enumerate(select_cols):
                val = row[i]
                if col == 'smtp_server':
                    smtp_server = val
                elif col == 'smtp_port':
                    smtp_port = val
                elif col == 'smtp_email':
                    smtp_email = val
                elif col == 'smtp_password':
                    smtp_password = val
    else:
        # No SMTP-related columns; check if any business_profile row exists
        c.execute('SELECT 1 FROM business_profile LIMIT 1')
        if not c.fetchone():
            print('No business_profile rows found.')
            raise SystemExit(1)

    smtp_server = smtp_server or 'smtp.gmail.com'
    smtp_port = int(smtp_port) if smtp_port else 587
    smtp_email = smtp_email or ''
    smtp_password = smtp_password or ''
    print('Using SMTP server:', smtp_server, 'port:', smtp_port, 'from:', smtp_email)
finally:
    conn.close()

print('Attempting to send test email to', RECIPIENT)
try:
    server = smtplib.SMTP(smtp_server, smtp_port, timeout=15)
    server.ehlo()
    try:
        server.starttls()
        server.ehlo()
    except Exception as e:
        print('STARTTLS not available or failed:', e)
    if smtp_email and smtp_password:
        try:
            server.login(smtp_email, smtp_password)
            print('SMTP login succeeded')
        except Exception as e:
            print('SMTP login failed:', e)
            server.quit()
            raise

    msg = f"Subject: Test Email from ProfitClean\n\nThis is a test email sent at {datetime.now().isoformat()} to verify SMTP settings."
    server.sendmail(smtp_email or f'no-reply@{smtp_server}', [RECIPIENT], msg)
    server.quit()
    print('Test email sent successfully to', RECIPIENT)
except Exception as e:
    print('Failed to send test email:', e)
    raise
