import streamlit as st
import sqlite3
import bcrypt
import pyotp
import secrets
import hashlib
import re
import json
from datetime import datetime, timedelta
from functools import wraps

from constants import (
    DB_PATH, MIN_PASSWORD_LENGTH, MAX_LOGIN_ATTEMPTS, ACCOUNT_LOCKOUT_MINUTES,
    SESSION_EXPIRY_DAYS,
)


def get_current_user_company():
    if 'user' not in st.session_state or not st.session_state.user:
        return None
    if 'company_id' in st.session_state.user:
        return st.session_state.user['company_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT company_id FROM users WHERE id = ?", (st.session_state.user['user_id'],))
    row = c.fetchone()
    conn.close()
    company_id = row[0] if row else None
    if company_id:
        st.session_state.user['company_id'] = company_id
    return company_id


def normalize_email(email):
    return email.strip().lower() if isinstance(email, str) else email


# ============================================================
# SECURITY FUNCTIONS
# ============================================================

def hash_password(pwd):
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd.encode('utf-8'), salt)
    return hashed.decode('utf-8'), salt.decode('utf-8')

def verify_password(pwd, hashed):
    return bcrypt.checkpw(pwd.encode('utf-8'), hashed.encode('utf-8'))

def check_user_password_hash(user_id):
    """Debug function to inspect stored password hashes."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, password_hash FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()

    if user:
        # Removed sensitive debug logging for security
        pass


def validate_password_strength(pwd):
    if len(pwd) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if not re.search(r"[A-Z]", pwd):
        return False, "Must contain uppercase letter"
    if not re.search(r"[a-z]", pwd):
        return False, "Must contain lowercase letter"
    if not re.search(r"\d", pwd):
        return False, "Must contain a number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", pwd):
        return False, "Must contain a special character"
    return True, "Strong password"

def log_audit(user_id, action, details, ip=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO audit_log (user_id, action, details, ip_address, created_at) VALUES (?,?,?,?,?)",
                  (user_id, action, details, ip, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Audit log error: {e}")


def log_auth_event(user_id, email, event_type, status, ip_address=None, user_agent=None, error_message=None):
    """Log authentication events for security tracking"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO auth_logs (user_id, email, event_type, status, ip_address, user_agent, error_message, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, email, event_type, status, ip_address, user_agent, error_message, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_current_user_data():
    if 'user' not in st.session_state:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'invite_code' in columns:
        c.execute("SELECT id, username, email, role, company_id, manager_id, supervisor_id, hire_date, totp_enabled, invite_code FROM users WHERE id = ?", (st.session_state.user['user_id'],))
    else:
        c.execute("SELECT id, username, email, role, company_id, manager_id, supervisor_id, hire_date, totp_enabled, NULL as invite_code FROM users WHERE id = ?", (st.session_state.user['user_id'],))
    row = c.fetchone()
    conn.close()
    return row


# ============================================================
# SESSION MANAGEMENT (Persistent Login Fix)
# ============================================================

def generate_session_token():
    return secrets.token_urlsafe(32)

def hash_session_token(token: str) -> str:
    """Hash a session token before storing/looking it up, so a leaked DB
    (or backup) doesn't hand out usable session tokens directly."""
    return hashlib.sha256(token.encode()).hexdigest()

def create_user_session(user_id: int, expires_days: int = 7) -> str:
    """Create a persistent session in the database. Only the hash of the
    token is stored; the raw token is returned for the client to hold."""
    token = generate_session_token()
    expires_at = datetime.now() + timedelta(days=expires_days)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO sessions (user_id, session_token, expires_at, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, hash_session_token(token), expires_at.isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return token

def validate_session_token(token: str):
    """Validate session and return user data"""
    if not token:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT u.id, u.username, u.email, u.role, u.company_id,
               u.manager_id, u.supervisor_id, u.totp_enabled, u.language
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.session_token = ?
          AND s.expires_at > datetime('now')
          AND u.is_active = 1
    """, (hash_session_token(token),))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "user_id": row[0],
            "username": row[1],
            "email": row[2],
            "role": row[3],
            "company_id": row[4],
            "manager_id": row[5],
            "supervisor_id": row[6],
            "totp_enabled": bool(row[7]),
            "language": row[8] or "en"
        }
    return None

def clear_expired_sessions():
    """Cleanup old sessions (run periodically)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
    conn.commit()
    conn.close()


# ============================================================
# AUTHENTICATION FUNCTIONS
# ============================================================

def authenticate_user(email: str, password: str, ip_address=None, user_agent=None):
    """Enhanced authentication with persistent sessions"""
    email = normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    log_auth_event(None, email, "login_attempt", "pending", ip_address, user_agent)
    
    # Get user
    c.execute("""
        SELECT id, username, password_hash, role, company_id,
               manager_id, supervisor_id, totp_enabled, is_active, locked_until, language
        FROM users WHERE lower(email) = ?
    """, (email,))
    user = c.fetchone()

    if not user:
        conn.close()
        log_auth_event(None, email, "login_attempt", "failed", ip_address, user_agent, "User not found")
        return False, "Invalid email or password"

    uid, uname, pwd_hash, role, company_id, mgr_id, sup_id, totp_enabled, is_active, locked_until, language = user
    
    if not is_active:
        conn.close()
        log_auth_event(uid, email, "login_attempt", "failed", ip_address, user_agent, "Account inactive")
        return False, "Account is inactive. Contact your administrator."
    
    # Check lockout. The lockout is temporary (ACCOUNT_LOCKOUT_MINUTES) and
    # auto-clears, so super_admin gets the same brute-force protection as
    # every other role -- a legitimate admin just waits out the lockout.
    if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
        conn.close()
        return False, f"Account locked until {locked_until}. Try again later."

    # Verify password
    if not verify_password(password, pwd_hash):
        # Increment failed attempts
        c.execute("UPDATE users SET login_attempts = login_attempts + 1 WHERE id = ?", (uid,))
        if c.execute("SELECT login_attempts FROM users WHERE id = ?", (uid,)).fetchone()[0] >= MAX_LOGIN_ATTEMPTS:
            lock_until = datetime.now() + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)
            c.execute("UPDATE users SET locked_until = ? WHERE id = ?", (lock_until.isoformat(), uid))
        conn.commit()
        conn.close()
        log_auth_event(uid, email, "login_attempt", "failed", ip_address, user_agent, "Invalid password")
        return False, "Invalid email or password"
    
    # Success - reset attempts
    c.execute("UPDATE users SET login_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?", 
              (datetime.now().isoformat(), uid))
    conn.commit()
    conn.close()
    
    # Create persistent session
    session_token = create_user_session(uid, SESSION_EXPIRY_DAYS)
    
    log_auth_event(uid, email, "login_success", "success", ip_address, user_agent)
    
    user_data = {
        "user_id": uid,
        "username": uname,
        "email": email,
        "role": role,
        "company_id": company_id,
        "manager_id": mgr_id,
        "supervisor_id": sup_id,
        "totp_enabled": bool(totp_enabled),
        "language": language or "en",
        "session_token": session_token
    }

    return True, user_data

def logout_user():
    """Clear current session"""
    if "session_token" in st.session_state:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE session_token = ?", (hash_session_token(st.session_state.session_token),))
        conn.commit()
        conn.close()
    for key in list(st.session_state.keys()):
        if key not in ["page"]:  # preserve page if needed
            del st.session_state[key]


def get_effective_user():
    if st.session_state.get('original_user'):
        return st.session_state.original_user
    return st.session_state.get('user')


# ============================================================
# DECORATORS FOR ROUTE PROTECTION
# ============================================================

def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user' not in st.session_state or not st.session_state.user:
            st.warning("🔒 Please log in")
            st.session_state.page = "login"
            st.rerun()
            return
        return func(*args, **kwargs)
    return wrapper

def require_role(allowed_roles):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'user' not in st.session_state:
                st.warning("Please log in")
                st.session_state.page = "login"
                st.rerun()
                return
            role = st.session_state.user.get('role')
            original = st.session_state.get('original_user')
            effective_role = original.get('role') if original and original.get('role') else role
            if effective_role not in allowed_roles:
                st.error(f"Access denied. Required role: {allowed_roles}")
                return
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# 2FA (TOTP) FUNCTIONS
# ============================================================

def generate_totp_secret():
    return pyotp.random_base32()

def get_totp_uri(secret, email):
    return pyotp.totp.TOTP(secret).provisioning_uri(name=email, issuer_name="ProfitClean")

def verify_totp(secret, code):
    totp = pyotp.TOTP(secret)
    return totp.verify(code)

def generate_backup_codes(count=8):
    codes = [secrets.token_hex(4) for _ in range(count)]
    hashed_codes = [bcrypt.hashpw(c.encode(), bcrypt.gensalt()).decode() for c in codes]
    return codes, hashed_codes

def verify_backup_code(user_id, code):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT backup_codes FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    if row and row[0]:
        stored_codes = json.loads(row[0])
        for i, hashed in enumerate(stored_codes):
            if bcrypt.checkpw(code.encode(), hashed.encode()):
                stored_codes.pop(i)
                c.execute("UPDATE users SET backup_codes = ? WHERE id = ?", (json.dumps(stored_codes), user_id))
                conn.commit()
                conn.close()
                return True
    conn.close()
    return False
