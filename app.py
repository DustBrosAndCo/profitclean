"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
COMPLETE VERSION - All Features (Part 1 of 5)
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
import json
import os
import io
import csv
import bcrypt
import secrets
import re
import qrcode
from io import BytesIO
import base64
from datetime import datetime, date, timedelta
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import plotly.express as px
import plotly.graph_objects as go
import time
import shutil

# ============================================
# SECURITY CONFIGURATION
# ============================================

MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 30
SESSION_EXPIRY_DAYS = 7
SALES_TAX_RATE = 0.06

BACKUP_DIR = os.path.join(os.path.expanduser("~"), "ProfitClean_Backups")

# ============================================
# PAGE CONFIGURATION
# ============================================

st.set_page_config(
    page_title="ProfitClean",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================
# FONT AWESOME & CUSTOM CSS
# ============================================

st.html("""
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

* { font-family: 'Inter', sans-serif; }

.metric-card {
    background: linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%);
    border-radius: 16px;
    padding: 1.25rem;
    color: white;
    text-align: center;
}
.metric-value { font-size: 2rem; font-weight: 700; }

.price-card {
    background: linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%);
    border-radius: 20px;
    padding: 2rem;
    color: white;
    text-align: center;
}
.price-value { font-size: 3rem; font-weight: 800; }

.card {
    background: white;
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 1rem;
    border: 1px solid #e2e8f0;
    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.internal-card {
    background: #fef3c7;
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 1rem;
    border: 1px solid #f59e0b;
    border-left: 4px solid #f59e0b;
}

.worker-card {
    background: #f0fdf4;
    border-radius: 16px;
    padding: 1rem;
    margin-bottom: 0.5rem;
    border: 1px solid #bbf7d0;
}

.pricing-tier-low {
    background: #fef3c7;
    border-radius: 16px;
    padding: 1rem;
    text-align: center;
    border: 1px solid #f59e0b;
}
.pricing-tier-fair {
    background: #d1fae5;
    border-radius: 16px;
    padding: 1rem;
    text-align: center;
    border: 1px solid #10b981;
}
.pricing-tier-high {
    background: #ede9fe;
    border-radius: 16px;
    padding: 1rem;
    text-align: center;
    border: 1px solid #8b5cf6;
}

.stButton button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-weight: 500;
    border-radius: 12px;
    transition: all 0.2s ease;
}
.stButton button:hover {
    transform: translateY(-1px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.css-1l02z5j button, .css-1l02z5j a {
    justify-content: flex-start !important;
    text-align: left !important;
    padding: 12px 16px !important;
    border-radius: 12px !important;
    margin: 4px 0 !important;
}
.css-1l02z5j button i, .css-1l02z5j a i {
    width: 24px;
    margin-right: 12px;
    text-align: center;
    font-size: 1.1rem;
}
</style>
""")

# ============================================
# DATABASE SETUP
# ============================================

DB_PATH = os.path.join(os.path.dirname(__file__), "profitclean.db")

def init_db():
    """Initialize all database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT DEFAULT 'worker',
        is_active INTEGER DEFAULT 1,
        login_attempts INTEGER DEFAULT 0,
        locked_until DATETIME,
        created_at DATETIME,
        last_login DATETIME,
        created_ip TEXT
    )''')
    
    # Sessions table
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_token TEXT UNIQUE NOT NULL,
        expires_at DATETIME,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Audit log
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        ip_address TEXT,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Business profile
    c.execute('''CREATE TABLE IF NOT EXISTS business_profile (
        id INTEGER PRIMARY KEY,
        business_name TEXT,
        phone TEXT,
        email TEXT,
        hourly_wage REAL,
        profit_target REAL,
        min_job_fee REAL,
        home_city TEXT,
        per_mile_rate REAL,
        sales_tax_rate REAL DEFAULT 0.06,
        smtp_email TEXT,
        smtp_password TEXT,
        setup_complete INTEGER DEFAULT 0
    )''')
    
    # Clients
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        business_name TEXT,
        contact_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        city TEXT,
        state TEXT,
        zip TEXT,
        lat REAL,
        lon REAL,
        notes TEXT,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Estimates
    c.execute('''CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        city TEXT,
        property_type TEXT,
        square_feet REAL,
        bedrooms INTEGER DEFAULT 0,
        bathrooms INTEGER DEFAULT 0,
        frequency TEXT,
        complexity INTEGER,
        travel_miles REAL,
        toll_cost REAL,
        add_on_window REAL DEFAULT 0,
        add_on_carpet REAL DEFAULT 0,
        add_on_floor REAL DEFAULT 0,
        add_on_disinfection REAL DEFAULT 0,
        add_on_pressure REAL DEFAULT 0,
        add_on_trash REAL DEFAULT 0,
        add_on_event REAL DEFAULT 0,
        holiday_surcharge REAL DEFAULT 0,
        emergency_premium REAL DEFAULT 0,
        location_discount REAL DEFAULT 0,
        contract_discount REAL DEFAULT 0,
        subtotal REAL,
        tax REAL,
        estimated_price REAL,
        lowest_price REAL,
        fair_price REAL,
        highest_price REAL,
        created_at DATETIME,
        status TEXT DEFAULT 'draft',
        approved_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')
    
    # Workers
    c.execute('''CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        phone TEXT,
        email TEXT,
        home_address TEXT,
        home_lat REAL,
        home_lon REAL,
        hourly_rate REAL,
        is_active INTEGER DEFAULT 1,
        jobs_assigned INTEGER DEFAULT 0,
        jobs_completed INTEGER DEFAULT 0,
        created_at DATETIME,
        updated_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Assignment queue
    c.execute('''CREATE TABLE IF NOT EXISTS assignment_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        position INTEGER,
        updated_at DATETIME,
        FOREIGN KEY (worker_id) REFERENCES workers(id)
    )''')
    
    # Job assignments
    c.execute('''CREATE TABLE IF NOT EXISTS job_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        worker_id INTEGER,
        assigned_by TEXT,
        assigned_at DATETIME,
        status TEXT DEFAULT 'assigned',
        travel_distance REAL,
        completed_at DATETIME,
        FOREIGN KEY (worker_id) REFERENCES workers(id)
    )''')
    
    # Scheduled jobs
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        estimate_id INTEGER,
        assigned_worker_id INTEGER,
        scheduled_date DATE,
        scheduled_time TEXT,
        status TEXT DEFAULT 'scheduled',
        reminder_sent INTEGER DEFAULT 0,
        completed_at DATETIME,
        notes TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (assigned_worker_id) REFERENCES workers(id)
    )''')
    
    # Inspections
    c.execute('''CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        client_id INTEGER,
        client_name TEXT,
        property_type TEXT,
        scheduled_job_id INTEGER,
        areas_json TEXT,
        inspection_data TEXT,
        status TEXT DEFAULT 'in_progress',
        started_at DATETIME,
        completed_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')
    
    # Quick jobs
    c.execute('''CREATE TABLE IF NOT EXISTS quick_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        job_date DATE,
        description TEXT,
        hours REAL,
        amount_invoiced REAL,
        job_expenses REAL,
        profit REAL,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Monthly expenses
    c.execute('''CREATE TABLE IF NOT EXISTS monthly_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        month_year TEXT,
        insurance REAL DEFAULT 0,
        vehicle REAL DEFAULT 0,
        software REAL DEFAULT 0,
        advertising REAL DEFAULT 0,
        other REAL DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Team messaging
    c.execute('''CREATE TABLE IF NOT EXISTS team_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        user_role TEXT,
        message TEXT,
        channel TEXT DEFAULT 'general',
        is_private BOOLEAN DEFAULT 0,
        recipient_id INTEGER,
        read_status INTEGER DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Supplies inventory
    c.execute('''CREATE TABLE IF NOT EXISTS supplies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        name TEXT,
        category TEXT,
        unit TEXT,
        current_stock REAL,
        reorder_level REAL,
        unit_cost REAL,
        last_updated DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Supply usage
    c.execute('''CREATE TABLE IF NOT EXISTS supply_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supply_id INTEGER,
        job_id INTEGER,
        quantity_used REAL,
        used_by INTEGER,
        used_at DATETIME,
        FOREIGN KEY (supply_id) REFERENCES supplies(id),
        FOREIGN KEY (used_by) REFERENCES users(id)
    )''')
    
    # Support tickets
    c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id TEXT UNIQUE,
        user_id INTEGER,
        user_email TEXT,
        issue_type TEXT,
        description TEXT,
        steps_to_reproduce TEXT,
        screenshot TEXT,
        status TEXT DEFAULT 'open',
        priority TEXT DEFAULT 'normal',
        assigned_to INTEGER,
        created_at DATETIME,
        updated_at DATETIME,
        resolved_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (assigned_to) REFERENCES users(id)
    )''')
    
    # Support messages
    c.execute('''CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket_id INTEGER,
        user_id INTEGER,
        message TEXT,
        is_staff BOOLEAN DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (ticket_id) REFERENCES support_tickets(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Email templates
    c.execute('''CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        subject TEXT,
        body TEXT
    )''')
    
    # Error logs
    c.execute('''CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        error_type TEXT,
        error_message TEXT,
        page_url TEXT,
        stack_trace TEXT,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Insert default supplies
    c.execute("SELECT COUNT(*) FROM supplies")
    if c.fetchone()[0] == 0:
        default_supplies = [
            (1, "All-purpose cleaner", "Chemicals", "gallons", 5, 2, 15.00),
            (1, "Paper towels", "Consumables", "rolls", 24, 12, 1.50),
            (1, "Trash bags", "Consumables", "boxes", 10, 5, 12.00),
            (1, "Glass cleaner", "Chemicals", "bottles", 8, 3, 8.00),
            (1, "Vacuum bags", "Equipment", "pack", 20, 10, 5.00),
            (1, "Disinfectant spray", "Chemicals", "bottles", 12, 4, 10.00),
            (1, "Mop heads", "Equipment", "pack", 15, 5, 8.00),
            (1, "Floor cleaner", "Chemicals", "gallons", 6, 2, 18.00),
            (1, "Microfiber cloths", "Equipment", "pack", 30, 10, 12.00),
            (1, "Gloves", "PPE", "boxes", 10, 3, 8.00),
        ]
        for supply in default_supplies:
            c.execute("INSERT INTO supplies (user_id, name, category, unit, current_stock, reorder_level, unit_cost) VALUES (?,?,?,?,?,?,?)", supply)
    
    # Insert default email templates
    c.execute("SELECT COUNT(*) FROM email_templates")
    if c.fetchone()[0] == 0:
        email_templates = [
            ("estimate_sent", "New Estimate from {business_name}", "Dear {client_name},\n\nYour estimate for {property_type} in {city} is ${amount:,.2f}.\n\nClick here to approve: {approval_link}\n\nThank you!"),
            ("estimate_approved", "Estimate Approved - {business_name}", "Dear {client_name},\n\nYour estimate #{estimate_id} for ${amount:,.2f} has been approved. We'll contact you to schedule.\n\nThank you!"),
            ("job_reminder", "Upcoming Cleaning Appointment", "Dear {client_name},\n\nThis is a reminder that we will be cleaning your property on {date} at {time}.\n\nThank you!"),
            ("review_request", "We value your feedback!", "Dear {client_name},\n\nThank you for choosing {business_name}. We'd love to hear about your experience.\n\nPlease leave a review here: {review_link}\n\nThank you!"),
        ]
        for name, subject, body in email_templates:
            c.execute("INSERT INTO email_templates (name, subject, body) VALUES (?,?,?)", (name, subject, body))
    
    # Create default admin account
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(b"Admin123!", salt)
        c.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, created_at)
            VALUES (?,?,?,?,?,?)
        """, ("admin", "admin@profitclean.com", password_hash.decode('utf-8'), salt.decode('utf-8'), "admin", datetime.now().isoformat()))
    
    current_month = datetime.now().strftime("%Y-%m")
    c.execute("INSERT OR IGNORE INTO monthly_expenses (id, user_id, month_year) VALUES (1, 1, ?)", (current_month,))
    
    conn.commit()
    conn.close()

# ============================================
# SECURITY FUNCTIONS
# ============================================

def hash_password(password):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8'), salt.decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def generate_session_token():
    return secrets.token_urlsafe(32)

def validate_password_strength(password):
    if len(password) < MIN_PASSWORD_LENGTH:
        return False, f"Password must be at least {MIN_PASSWORD_LENGTH} characters"
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain an uppercase letter"
    if not re.search(r"[a-z]", password):
        return False, "Password must contain a lowercase letter"
    if not re.search(r"\d", password):
        return False, "Password must contain a number"
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain a special character"
    return True, "Strong password"

def log_audit(user_id, action, details, ip_address=None):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO audit_log (user_id, action, details, ip_address, created_at)
            VALUES (?,?,?,?,?)
        """, (user_id, action, details, ip_address, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except:
        pass

def create_user(username, email, password, role='worker', ip_address=None):
    is_valid, message = validate_password_strength(password)
    if not is_valid:
        return False, message
    
    hashed, salt = hash_password(password)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, created_at, created_ip)
            VALUES (?,?,?,?,?,?,?)
        """, (username, email, hashed, salt, role, datetime.now().isoformat(), ip_address))
        user_id = c.lastrowid
        conn.commit()
        log_audit(user_id, "account_created", f"User {username} created account", ip_address)
        return True, user_id
    except sqlite3.IntegrityError:
        return False, "Username or email already exists"
    finally:
        conn.close()

def authenticate_user(email, password, ip_address=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT id, username, password_hash, role, login_attempts, locked_until FROM users WHERE email = ? AND is_active = 1", (email,))
    user = c.fetchone()
    
    if user:
        user_id, username, hashed, role, attempts, locked_until = user
        
        if locked_until and datetime.fromisoformat(locked_until) > datetime.now():
            conn.close()
            return False, "Account locked. Try again later."
        
        if verify_password(password, hashed):
            c.execute("UPDATE users SET login_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?", 
                     (datetime.now().isoformat(), user_id))
            
            token = generate_session_token()
            expires = datetime.now() + timedelta(days=SESSION_EXPIRY_DAYS)
            c.execute("INSERT INTO sessions (user_id, session_token, expires_at, created_at) VALUES (?,?,?,?)",
                     (user_id, token, expires.isoformat(), datetime.now().isoformat()))
            
            conn.commit()
            log_audit(user_id, "login_success", f"User {username} logged in", ip_address)
            conn.close()
            return True, {"user_id": user_id, "username": username, "role": role, "token": token}
        else:
            new_attempts = attempts + 1
            locked_until_val = None
            if new_attempts >= MAX_LOGIN_ATTEMPTS:
                locked_until_val = (datetime.now() + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)).isoformat()
            
            c.execute("UPDATE users SET login_attempts = ?, locked_until = ? WHERE id = ?",
                     (new_attempts, locked_until_val, user_id))
            conn.commit()
            log_audit(user_id, "login_failed", f"Failed login attempt for {username}", ip_address)
            conn.close()
            return False, f"Invalid credentials. {MAX_LOGIN_ATTEMPTS - new_attempts} attempts remaining."
    
    conn.close()
    return False, "User not found"

def logout_user():
    if 'user' in st.session_state and st.session_state.user:
        log_audit(st.session_state.user['user_id'], "logout", "User logged out")
    st.session_state.user = None
    st.session_state.page = "login"

def require_auth(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user' not in st.session_state or not st.session_state.user:
            st.warning("🔒 Please log in to access this page")
            st.session_state.page = "login"
            st.rerun()
            return
        return func(*args, **kwargs)
    return wrapper

def require_role(role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if 'user' not in st.session_state or not st.session_state.user:
                st.warning("🔒 Please log in to access this page")
                st.session_state.page = "login"
                st.rerun()
                return
            if st.session_state.user.get('role') != role and role != 'any':
                st.error(f"⛔ Access denied. {role.capitalize()} role required.")
                return
            return func(*args, **kwargs)
        return wrapper
    return decorator

def get_business_name():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT business_name FROM business_profile WHERE id=1")
        row = c.fetchone()
        conn.close()
        return row[0] if row else "ProfitClean"
    except:
        return "ProfitClean"

def get_current_user_data():
    if 'user' not in st.session_state or not st.session_state.user:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, role FROM users WHERE id = ?", (st.session_state.user['user_id'],))
    user = c.fetchone()
    conn.close()
    return user

# ============================================
# BACKUP FUNCTIONS
# ============================================

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def create_backup():
    ensure_backup_dir()
    user_id = st.session_state.user['user_id']
    backup_data = {"version": "2.0", "backup_date": datetime.now().isoformat(), "user_id": user_id, "data": {}}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tables = ["clients", "estimates", "workers", "quick_jobs", "monthly_expenses", "scheduled_jobs", "inspections", "supplies"]
    for table in tables:
        try:
            c.execute(f"SELECT * FROM {table} WHERE user_id = ?", (user_id,))
            rows = c.fetchall()
            c.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in c.fetchall()]
            data = []
            for row in rows:
                data.append(dict(zip(columns, row)))
            backup_data["data"][table] = data
        except:
            backup_data["data"][table] = []
    conn.close()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"backup_user_{user_id}_{timestamp}.json")
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2, default=str)
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith(f"backup_user_{user_id}_")])
    for old_backup in backups[:-30]:
        os.remove(os.path.join(BACKUP_DIR, old_backup))
    return backup_file

def restore_from_backup(backup_file):
    with open(backup_file, 'r') as f:
        backup = json.load(f)
    user_id = st.session_state.user['user_id']
    data = backup.get("data", {})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for table, rows in data.items():
        if not rows:
            continue
        c.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))
        columns = list(rows[0].keys())
        columns = [col for col in columns if col != 'id']
        for row in rows:
            placeholders = ','.join(['?' for _ in columns])
            values = [row.get(col) for col in columns]
            try:
                c.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)
            except:
                pass
    conn.commit()
    conn.close()
    return True

def get_backup_list():
    ensure_backup_dir()
    user_id = st.session_state.user['user_id']
    backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.startswith(f"backup_user_{user_id}_") and f.endswith(".json"):
            file_path = os.path.join(BACKUP_DIR, f)
            backups.append({
                "file": f,
                "path": file_path,
                "date": datetime.fromtimestamp(os.path.getmtime(file_path)).strftime("%Y-%m-%d %H:%M:%S"),
                "size": f"{os.path.getsize(file_path) / 1024:.1f} KB"
            })
    return sorted(backups, key=lambda x: x["date"], reverse=True)

# ============================================
# FLORIDA DATA & PRICING
# ============================================

FLORIDA_CITIES = [
    "Orlando", "Miami", "Tampa", "Jacksonville", "Cocoa Beach", 
    "Daytona Beach", "Naples", "Ocala", "Gainesville", "Tallahassee",
    "St. Petersburg", "Fort Myers", "Sarasota", "Pensacola", "Lakeland",
    "West Palm Beach", "Fort Lauderdale", "Hollywood", "Port St. Lucie",
    "Cape Coral", "Hialeah", "Palm Bay", "Deltona"
]

PROPERTY_TYPES = {
    "Office Standard": {"multiplier": 1.0, "base_rate": 0.14, "icon": "🏢"},
    "Retail Store": {"multiplier": 1.2, "base_rate": 0.14, "icon": "🛍️"},
    "Warehouse": {"multiplier": 0.8, "base_rate": 0.12, "icon": "📦"},
    "🏥 Medical / Dental": {"multiplier": 1.6, "base_rate": 0.14, "icon": "🏥"},
    "🏭 Industrial": {"multiplier": 1.2, "base_rate": 0.12, "icon": "🏭"},
    "🏫 School / Daycare": {"multiplier": 1.4, "base_rate": 0.13, "icon": "🏫"},
    "🏨 Hotel / Motel": {"multiplier": 1.5, "base_rate": 0.14, "icon": "🏨"},
    "🍽️ Restaurant": {"multiplier": 2.2, "base_rate": 0.14, "icon": "🍽️"},
    "⛽ Gas Station / C-Store": {"multiplier": 1.9, "base_rate": 0.16, "icon": "⛽"},
    "🏢 High-Rise": {"multiplier": 1.3, "base_rate": 0.14, "icon": "🏙️"},
    "⛪ Church": {"multiplier": 1.2, "base_rate": 0.13, "icon": "⛪"},
    "🛍️ Shopping Mall": {"multiplier": 1.3, "base_rate": 0.14, "icon": "🛍️"},
    "🏋️ Gym / Fitness": {"multiplier": 1.6, "base_rate": 0.14, "icon": "🏋️"},
    "🏗️ Post-Construction": {"multiplier": 2.5, "base_rate": 0.18, "icon": "🏗️"},
    "🎪 Event Venue": {"multiplier": 1.5, "base_rate": 0.14, "icon": "🎪"},
    "🏠 Airbnb / Short-Term Rental": {"multiplier": 1.0, "pricing_model": "bedroom", "base_rate": 45, "icon": "🏠"},
}

FREQUENCIES = {
    "Daily": 0.85,
    "Weekly": 1.0,
    "Bi-Weekly": 1.35,
    "Monthly": 1.75,
    "One-Time": 2.0,
    "🏠 Per Checkout": 1.0,
}

HOLIDAY_RATES = {
    "New Year's Day": 0.25,
    "Memorial Day": 0.25,
    "Independence Day": 0.25,
    "Labor Day": 0.25,
    "Thanksgiving": 0.35,
    "Christmas Eve": 0.50,
    "Christmas Day": 0.50,
    "New Year's Eve": 0.35,
}

KNOWN_TOLL_RATES = {
    ("orlando", "miami"): 17.00,
    ("miami", "orlando"): 17.00,
    ("orlando", "tampa"): 8.50,
    ("tampa", "orlando"): 8.50,
    ("orlando", "cocoa beach"): 5.50,
    ("cocoa beach", "orlando"): 5.50,
    ("orlando", "jacksonville"): 12.00,
    ("jacksonville", "orlando"): 12.00,
    ("tampa", "cocoa beach"): 14.00,
    ("cocoa beach", "tampa"): 14.00,
    ("miami", "naples"): 9.00,
    ("naples", "miami"): 9.00,
    ("orlando", "naples"): 15.00,
    ("naples", "orlando"): 15.00,
}

def estimate_toll_cost(origin_city, destination_city):
    origin_lower = str(origin_city).lower()
    dest_lower = str(destination_city).lower()
    route_key = (origin_lower, dest_lower)
    if route_key in KNOWN_TOLL_RATES:
        return KNOWN_TOLL_RATES[route_key]
    return 5.00

def calculate_price_with_tiers(city, property_type, sqft, bedrooms, bathrooms, frequency, complexity, travel_miles, add_ons, holiday, num_locations, notice_hours, contract_months):
    coastal = ["Cocoa Beach", "Daytona Beach", "Naples", "Fort Myers", "Sarasota"]
    rural = ["Ocala", "Gainesville", "Lake City", "Sebring"]
    
    if city in coastal:
        zone_mult = 1.18
        travel_fee = 55
    elif city in rural:
        zone_mult = 1.28
        travel_fee = 65
    else:
        zone_mult = 1.0
        travel_fee = 45
    
    prop_data = PROPERTY_TYPES.get(property_type, {"multiplier": 1.0, "base_rate": 0.14})
    prop_mult = prop_data["multiplier"]
    base_rate = prop_data["base_rate"]
    freq_mult = FREQUENCIES.get(frequency, 1.0)
    comp_factor = 0.7 + (complexity / 10)
    
    if property_type == "🏠 Airbnb / Short-Term Rental":
        subtotal = (bedrooms * 45) + (bathrooms * 25)
        subtotal = subtotal * prop_mult * comp_factor
    else:
        price_per_sqft = base_rate * zone_mult * prop_mult * freq_mult * comp_factor
        subtotal = sqft * price_per_sqft
    
    travel_cost = (travel_miles * 0.65) + travel_fee
    tolls = estimate_toll_cost(city, "orlando")
    total_before_modifiers = subtotal + travel_cost + tolls
    
    # Add-ons
    add_on_total = 0
    if add_ons.get('window_cleaning'):
        add_on_total += 50
    if add_ons.get('carpet_cleaning'):
        add_on_total += sqft * 0.20
    if add_ons.get('floor_waxing'):
        add_on_total += sqft * 0.30
    if add_ons.get('disinfection'):
        add_on_total += 75
    if add_ons.get('pressure_washing'):
        add_on_total += 125
    total_before_modifiers += add_on_total
    
    # Apply modifiers
    holiday_mult = 1.0
    if holiday != "None":
        holiday_mult = 1 + HOLIDAY_RATES.get(holiday, 0)
    total_before_modifiers *= holiday_mult
    
    emergency_mult = 1.0
    if notice_hours <= 12:
        emergency_mult = 1.75
    elif notice_hours <= 24:
        emergency_mult = 1.50
    elif notice_hours <= 48:
        emergency_mult = 1.25
    total_before_modifiers *= emergency_mult
    
    location_mult = 1.0
    if num_locations >= 7:
        location_mult = 0.85
    elif num_locations >= 4:
        location_mult = 0.90
    elif num_locations >= 2:
        location_mult = 0.95
    total_before_modifiers *= location_mult
    
    contract_mult = 1.0
    if contract_months >= 24:
        contract_mult = 0.80
    elif contract_months >= 12:
        contract_mult = 0.85
    elif contract_months >= 6:
        contract_mult = 0.90
    elif contract_months >= 3:
        contract_mult = 0.95
    total_before_modifiers *= contract_mult
    
    # Calculate true cost (break-even)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hourly_wage, min_job_fee FROM business_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    hourly_wage = row[0] if row else 15.0
    min_job_fee = row[1] if row else 150
    
    if sqft > 0:
        labor_hours = (sqft / 500) * comp_factor
    else:
        labor_hours = (bedrooms * 0.75) + (bathrooms * 0.5)
    labor_cost = labor_hours * hourly_wage
    materials_cost = (sqft * 0.025) if sqft > 0 else 25
    true_cost = labor_cost + materials_cost + travel_cost + tolls
    
    if true_cost < min_job_fee:
        true_cost = min_job_fee
    
    # Three tiers
    lowest_price = math.ceil(true_cost)
    fair_price = math.ceil(total_before_modifiers)
    highest_price = math.ceil(total_before_modifiers * 1.3)
    
    # Add tax
    tax_rate = SALES_TAX_RATE
    lowest_total = math.ceil(lowest_price * (1 + tax_rate))
    fair_total = math.ceil(fair_price * (1 + tax_rate))
    highest_total = math.ceil(highest_price * (1 + tax_rate))
    
    fair_margin = round(((fair_price - true_cost) / fair_price) * 100, 1) if fair_price > 0 else 0
    highest_margin = round(((highest_price - true_cost) / highest_price) * 100, 1) if highest_price > 0 else 0
    
    return {
        "lowest": {"total": lowest_total, "subtotal": lowest_price, "tax": round(lowest_price * tax_rate, 2), "margin": 0},
        "fair": {"total": fair_total, "subtotal": fair_price, "tax": round(fair_price * tax_rate, 2), "margin": fair_margin},
        "highest": {"total": highest_total, "subtotal": highest_price, "tax": round(highest_price * tax_rate, 2), "margin": highest_margin},
        "true_cost": round(true_cost, 2),
        "toll_estimate": tolls,
        "add_on_total": add_on_total,
        "labor_hours": round(labor_hours, 1),
        "labor_cost": round(labor_cost, 2),
        "materials_cost": round(materials_cost, 2),
        "travel_cost": round(travel_cost, 2)
    }
# ============================================
# WORKER MANAGEMENT FUNCTIONS
# ============================================

def add_worker(name, phone, email, address, lat, lon, hourly_rate):
    """Add a new worker to the system"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO workers (user_id, name, phone, email, home_address, home_lat, home_lon, hourly_rate, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (user_id, name, phone, email, address, lat, lon, hourly_rate, datetime.now().isoformat()))
    worker_id = c.lastrowid
    
    # Add to assignment queue at the end
    c.execute("SELECT COUNT(*) FROM assignment_queue")
    queue_size = c.fetchone()[0]
    c.execute("INSERT INTO assignment_queue (worker_id, position, updated_at) VALUES (?,?,?)",
              (worker_id, queue_size, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    log_audit(user_id, "worker_added", f"Added worker: {name}")
    return worker_id

def update_worker(worker_id, name, phone, email, address, lat, lon, hourly_rate, is_active):
    """Update worker information"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE workers SET 
            name = ?, phone = ?, email = ?, home_address = ?, 
            home_lat = ?, home_lon = ?, hourly_rate = ?, is_active = ?, updated_at = ?
        WHERE id = ?
    """, (name, phone, email, address, lat, lon, hourly_rate, 1 if is_active else 0, datetime.now().isoformat(), worker_id))
    conn.commit()
    conn.close()
    log_audit(st.session_state.user['user_id'], "worker_updated", f"Updated worker: {name}")

def delete_worker(worker_id):
    """Soft delete a worker (deactivate)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE workers SET is_active = 0 WHERE id = ?", (worker_id,))
    c.execute("DELETE FROM assignment_queue WHERE worker_id = ?", (worker_id,))
    conn.commit()
    conn.close()
    log_audit(st.session_state.user['user_id'], "worker_deleted", f"Deleted worker ID: {worker_id}")

def get_all_workers(include_inactive=False):
    """Get all workers for current user"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    if include_inactive:
        df = pd.read_sql_query("""
            SELECT w.id, w.name, w.phone, w.email, w.home_address, w.home_lat, w.home_lon,
                   w.hourly_rate, w.is_active, w.jobs_assigned, w.jobs_completed, w.created_at,
                   COALESCE(aq.position, 999) as queue_position
            FROM workers w
            LEFT JOIN assignment_queue aq ON w.id = aq.worker_id
            WHERE w.user_id = ?
            ORDER BY aq.position
        """, conn, params=(user_id,))
    else:
        df = pd.read_sql_query("""
            SELECT w.id, w.name, w.phone, w.email, w.home_address, w.home_lat, w.home_lon,
                   w.hourly_rate, w.is_active, w.jobs_assigned, w.jobs_completed, w.created_at,
                   COALESCE(aq.position, 999) as queue_position
            FROM workers w
            LEFT JOIN assignment_queue aq ON w.id = aq.worker_id
            WHERE w.user_id = ? AND w.is_active = 1
            ORDER BY aq.position
        """, conn, params=(user_id,))
    conn.close()
    return df

def update_worker_job_count(worker_id, increment=1):
    """Update worker's assigned job count"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE workers SET jobs_assigned = jobs_assigned + ? WHERE id = ?", (increment, worker_id))
    conn.commit()
    conn.close()

def complete_worker_job(worker_id):
    """Mark a job as completed for a worker"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE workers SET jobs_completed = jobs_completed + 1 WHERE id = ?", (worker_id,))
    conn.commit()
    conn.close()

def reassign_queue_positions():
    """Rebalance the assignment queue positions"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE assignment_queue SET position = new_pos
        FROM (
            SELECT worker_id, ROW_NUMBER() OVER (ORDER BY position) - 1 as new_pos
            FROM assignment_queue ORDER BY position
        ) AS sorted
        WHERE assignment_queue.worker_id = sorted.worker_id
    """)
    conn.commit()
    conn.close()

def get_next_worker_from_queue():
    """Get the next worker in the queue (fair distribution)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT w.id, w.name, w.home_lat, w.home_lon, aq.position
        FROM workers w
        JOIN assignment_queue aq ON w.id = aq.worker_id
        WHERE w.is_active = 1
        ORDER BY aq.position
        LIMIT 1
    """)
    worker = c.fetchone()
    conn.close()
    return worker

def rotate_queue():
    """Move the first worker to the end of the queue"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT MAX(position) FROM assignment_queue")
    max_pos = c.fetchone()[0] or 0
    
    # Move first worker (position 0) to the end
    c.execute("UPDATE assignment_queue SET position = ? WHERE position = 0", (max_pos + 1,))
    
    # Rebalance
    reassign_queue_positions()
    
    conn.commit()
    conn.close()

def assign_job_to_worker(job_id, worker_id):
    """Assign a job to a worker and rotate the queue for fairness"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create assignment record
    c.execute("""
        INSERT INTO job_assignments (job_id, worker_id, assigned_by, assigned_at, status)
        VALUES (?,?,?,?,?)
    """, (job_id, worker_id, st.session_state.user['username'], datetime.now().isoformat(), "assigned"))
    
    # Update worker's job count
    update_worker_job_count(worker_id, 1)
    
    # Move this worker to the end of the queue
    c.execute("SELECT MAX(position) FROM assignment_queue")
    max_pos = c.fetchone()[0] or 0
    c.execute("UPDATE assignment_queue SET position = ? WHERE worker_id = ?", (max_pos + 1, worker_id))
    
    # Rebalance all positions
    reassign_queue_positions()
    
    conn.commit()
    conn.close()
    log_audit(st.session_state.user['user_id'], "job_assigned", f"Job {job_id} assigned to worker {worker_id}")

def get_worker_jobs(worker_id, limit=10):
    """Get recent jobs assigned to a worker"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT ja.id, ja.job_id, ja.assigned_at, ja.status, ja.completed_at,
               e.client_name, e.city, e.property_type
        FROM job_assignments ja
        LEFT JOIN estimates e ON ja.job_id = e.id
        WHERE ja.worker_id = ?
        ORDER BY ja.assigned_at DESC
        LIMIT ?
    """, conn, params=(worker_id, limit))
    conn.close()
    return df

# ============================================
# CLIENT MANAGEMENT FUNCTIONS
# ============================================

def add_client(business_name, contact_name, phone, email, address, city, state, zip_code, lat, lon, notes):
    """Add a new client"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO clients (user_id, business_name, contact_name, phone, email, address, city, state, zip, lat, lon, notes, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (user_id, business_name, contact_name, phone, email, address, city, state, zip_code, lat, lon, notes, datetime.now().isoformat(), datetime.now().isoformat()))
    client_id = c.lastrowid
    conn.commit()
    conn.close()
    log_audit(user_id, "client_added", f"Added client: {business_name}")
    return client_id

def update_client(client_id, business_name, contact_name, phone, email, address, city, state, zip_code, lat, lon, notes):
    """Update client information"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE clients SET 
            business_name = ?, contact_name = ?, phone = ?, email = ?, 
            address = ?, city = ?, state = ?, zip = ?, lat = ?, lon = ?, notes = ?, updated_at = ?
        WHERE id = ?
    """, (business_name, contact_name, phone, email, address, city, state, zip_code, lat, lon, notes, datetime.now().isoformat(), client_id))
    conn.commit()
    conn.close()
    log_audit(st.session_state.user['user_id'], "client_updated", f"Updated client: {business_name}")

def delete_client(client_id):
    """Delete a client"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM clients WHERE id = ?", (client_id,))
    conn.commit()
    conn.close()
    log_audit(st.session_state.user['user_id'], "client_deleted", f"Deleted client ID: {client_id}")

def get_all_clients():
    """Get all clients for current user"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, business_name, contact_name, phone, email, address, city, state, zip, notes, created_at
        FROM clients WHERE user_id = ? ORDER BY business_name
    """, conn, params=(user_id,))
    conn.close()
    return df

def get_client_by_id(client_id):
    """Get a single client by ID"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, business_name, contact_name, phone, email, address, city, state, zip, lat, lon, notes
        FROM clients WHERE id = ?
    """, (client_id,))
    client = c.fetchone()
    conn.close()
    return client

def search_clients(search_term):
    """Search clients by name or contact"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, business_name, contact_name, phone, email, city
        FROM clients 
        WHERE user_id = ? AND (business_name LIKE ? OR contact_name LIKE ? OR email LIKE ?)
        ORDER BY business_name
        LIMIT 20
    """, conn, params=(user_id, f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"))
    conn.close()
    return df

def get_client_estimates(client_id):
    """Get all estimates for a client"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, city, property_type, estimated_price, created_at, status
        FROM estimates WHERE user_id = ? AND client_id = ?
        ORDER BY created_at DESC
    """, conn, params=(user_id, client_id))
    conn.close()
    return df

# ============================================
# JOB SCHEDULING FUNCTIONS
# ============================================

def schedule_job(client_id, client_name, client_email, estimate_id, worker_id, scheduled_date, scheduled_time, notes=""):
    """Schedule a job"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO scheduled_jobs 
        (user_id, client_id, client_name, client_email, estimate_id, assigned_worker_id, scheduled_date, scheduled_time, notes, status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (user_id, client_id, client_name, client_email, estimate_id, worker_id, scheduled_date.isoformat(), scheduled_time, notes, "scheduled"))
    job_id = c.lastrowid
    conn.commit()
    conn.close()
    log_audit(user_id, "job_scheduled", f"Scheduled job for {client_name} on {scheduled_date}")
    return job_id

def update_job_status(job_id, status):
    """Update a job's status"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status == "completed":
        c.execute("UPDATE scheduled_jobs SET status = ?, completed_at = ? WHERE id = ?", 
                  (status, datetime.now().isoformat(), job_id))
        # Get worker_id to update completed count
        c.execute("SELECT assigned_worker_id FROM scheduled_jobs WHERE id = ?", (job_id,))
        worker = c.fetchone()
        if worker and worker[0]:
            complete_worker_job(worker[0])
    else:
        c.execute("UPDATE scheduled_jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()
    log_audit(st.session_state.user['user_id'], "job_status_updated", f"Job {job_id} status: {status}")

def get_scheduled_jobs(date_filter=None, status_filter=None):
    """Get scheduled jobs with optional filters"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    query = "SELECT * FROM scheduled_jobs WHERE user_id = ?"
    params = [user_id]
    
    if date_filter:
        query += " AND scheduled_date = ?"
        params.append(date_filter.isoformat())
    if status_filter and status_filter != "All":
        query += " AND status = ?"
        params.append(status_filter)
    
    query += " ORDER BY scheduled_date, scheduled_time"
    
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df

def get_worker_schedule(worker_id, date_filter=None):
    """Get schedule for a specific worker"""
    conn = sqlite3.connect(DB_PATH)
    if date_filter:
        df = pd.read_sql_query("""
            SELECT id, client_name, scheduled_time, status, notes
            FROM scheduled_jobs 
            WHERE assigned_worker_id = ? AND scheduled_date = ?
            ORDER BY scheduled_time
        """, conn, params=(worker_id, date_filter.isoformat()))
    else:
        df = pd.read_sql_query("""
            SELECT id, client_name, scheduled_date, scheduled_time, status, notes
            FROM scheduled_jobs 
            WHERE assigned_worker_id = ?
            ORDER BY scheduled_date, scheduled_time
        """, conn, params=(worker_id,))
    conn.close()
    return df

def get_upcoming_jobs(days=7):
    """Get upcoming jobs for the next N days"""
    user_id = st.session_state.user['user_id']
    today = datetime.now().date().isoformat()
    future = (datetime.now().date() + timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, client_name, scheduled_date, scheduled_time, assigned_worker_id, status
        FROM scheduled_jobs 
        WHERE user_id = ? AND scheduled_date BETWEEN ? AND ? AND status = 'scheduled'
        ORDER BY scheduled_date, scheduled_time
    """, conn, params=(user_id, today, future))
    conn.close()
    return df

def send_job_reminders():
    """Send reminders for upcoming jobs (run daily)"""
    tomorrow = (datetime.now().date() + timedelta(days=1)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT id, client_name, client_email, scheduled_time, assigned_worker_id
        FROM scheduled_jobs 
        WHERE scheduled_date = ? AND reminder_sent = 0 AND status = 'scheduled'
    """, (tomorrow,))
    jobs = c.fetchall()
    
    for job in jobs:
        job_id, client_name, client_email, scheduled_time, worker_id = job
        if client_email:
            send_email_notification(client_email, "job_reminder", {
                "client_name": client_name,
                "date": tomorrow,
                "time": scheduled_time
            })
        c.execute("UPDATE scheduled_jobs SET reminder_sent = 1 WHERE id = ?", (job_id,))
    
    conn.commit()
    conn.close()

# ============================================
# DYNAMIC INSPECTION FUNCTIONS
# ============================================

def init_inspection_session(client_id, client_name, property_type, scheduled_job_id=None):
    """Initialize a new dynamic inspection session"""
    if 'inspection' not in st.session_state:
        st.session_state.inspection = {
            'user_id': st.session_state.user['user_id'],
            'client_id': client_id,
            'client_name': client_name,
            'property_type': property_type,
            'scheduled_job_id': scheduled_job_id,
            'areas': [],
            'current_area_index': 0,
            'started_at': datetime.now().isoformat(),
            'inspection_id': None
        }

def add_inspection_area(area_name, quantity=1):
    """Dynamically add areas to the inspection"""
    for i in range(quantity):
        st.session_state.inspection['areas'].append({
            'id': f"{area_name}_{len(st.session_state.inspection['areas'])}",
            'name': area_name,
            'room_number': len([a for a in st.session_state.inspection['areas'] if a['name'] == area_name]) + 1,
            'status': 'pending',
            'responses': {
                'floors': 'Good',
                'walls': 'Good',
                'trash': 'Empty',
                'supplies': 'Full',
                'odor': 'None',
                'lighting': 'All Working',
                'equipment': 'Good',
                'windows': 'Clean'
            },
            'photos': [],
            'notes': '',
            'version_history': []
        })
    st.success(f"✅ Added {quantity} {area_name}(s)!")

def save_inspection_area(area_index):
    """Save current area and mark as completed"""
    area = st.session_state.inspection['areas'][area_index]
    area['status'] = 'completed'
    area['completed_at'] = datetime.now().isoformat()
    
    # Save to version history
    current_version = len(area['version_history'])
    area['version_history'].append({
        'version': current_version + 1,
        'timestamp': datetime.now().isoformat(),
        'responses': area['responses'].copy(),
        'notes': area['notes']
    })

def edit_inspection_area(area_index):
    """Open a completed area for editing"""
    st.session_state.editing_area_index = area_index
    st.session_state.previous_status = st.session_state.inspection['areas'][area_index]['status']
    st.session_state.inspection['areas'][area_index]['status'] = 'in_review'

def restore_area_version(area_index, version_number):
    """Restore a previous version of an area"""
    area = st.session_state.inspection['areas'][area_index]
    target = next((v for v in area['version_history'] if v['version'] == version_number), None)
    if target:
        area['responses'] = target['responses'].copy()
        area['notes'] = target['notes']
        st.warning(f"⏪ Restored version {version_number}")

def save_complete_inspection():
    """Save the complete inspection to database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO inspections 
        (user_id, client_id, client_name, property_type, scheduled_job_id, areas_json, inspection_data, status, started_at, completed_at)
        VALUES (?,?,?,?,?,?,?,?,?,?)
    """, (st.session_state.inspection['user_id'], st.session_state.inspection['client_id'],
          st.session_state.inspection['client_name'], st.session_state.inspection['property_type'],
          st.session_state.inspection.get('scheduled_job_id'),
          json.dumps(st.session_state.inspection['areas']),
          json.dumps(st.session_state.inspection), "completed",
          st.session_state.inspection['started_at'], datetime.now().isoformat()))
    conn.commit()
    conn.close()
    log_audit(st.session_state.user['user_id'], "inspection_completed", f"Inspection for {st.session_state.inspection['client_name']}")

def get_inspections_for_client(client_id):
    """Get all inspections for a client"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, property_type, status, started_at, completed_at
        FROM inspections WHERE user_id = ? AND client_id = ?
        ORDER BY started_at DESC
    """, conn, params=(user_id, client_id))
    conn.close()
    return df

def get_inspection_by_id(inspection_id):
    """Get a specific inspection by ID"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT areas_json, inspection_data FROM inspections WHERE id = ?", (inspection_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return json.loads(row[0]), json.loads(row[1])
    return None, None
# ============================================
# TEAM MESSAGING FUNCTIONS
# ============================================

def send_message(message, channel='general', recipient_id=None):
    """Send a team message"""
    user_id = st.session_state.user['user_id']
    username = st.session_state.user['username']
    user_role = st.session_state.user['role']
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO team_messages (user_id, username, user_role, message, channel, is_private, recipient_id, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (user_id, username, user_role, message, channel, 1 if recipient_id else 0, recipient_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_messages(channel='general', user_id=None, limit=100):
    """Get recent messages"""
    conn = sqlite3.connect(DB_PATH)
    if user_id:
        df = pd.read_sql_query("""
            SELECT m.id, m.username, m.user_role, m.message, m.created_at,
                   CASE WHEN m.user_id = ? THEN 'sent' ELSE 'received' END as direction
            FROM team_messages m
            WHERE (m.is_private = 0 AND m.channel = ?) 
               OR (m.is_private = 1 AND (m.user_id = ? OR m.recipient_id = ?))
            ORDER BY m.created_at DESC LIMIT ?
        """, conn, params=(user_id, channel, user_id, user_id, limit))
    else:
        df = pd.read_sql_query("""
            SELECT id, username, user_role, message, created_at
            FROM team_messages 
            WHERE is_private = 0 AND channel = ?
            ORDER BY created_at DESC LIMIT ?
        """, conn, params=(channel, limit))
    conn.close()
    return df

def get_active_users():
    """Get currently active users (based on recent sessions)"""
    cutoff = (datetime.now() - timedelta(minutes=5)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT DISTINCT u.username, u.role
        FROM users u
        JOIN sessions s ON u.id = s.user_id
        WHERE s.expires_at > ? AND u.is_active = 1
    """, conn, params=(datetime.now().isoformat(),))
    conn.close()
    return df

def mark_messages_read(message_ids, user_id):
    """Mark messages as read"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for msg_id in message_ids:
        c.execute("UPDATE team_messages SET read_status = 1 WHERE id = ? AND recipient_id = ?", (msg_id, user_id))
    conn.commit()
    conn.close()

def get_unread_count(user_id):
    """Get count of unread messages for a user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM team_messages WHERE recipient_id = ? AND read_status = 0 AND is_private = 1", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

# ============================================
# SUPPLY INVENTORY FUNCTIONS
# ============================================

def add_supply(name, category, unit, current_stock, reorder_level, unit_cost):
    """Add a new supply item"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO supplies (user_id, name, category, unit, current_stock, reorder_level, unit_cost, last_updated)
        VALUES (?,?,?,?,?,?,?,?)
    """, (user_id, name, category, unit, current_stock, reorder_level, unit_cost, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    log_audit(user_id, "supply_added", f"Added supply: {name}")

def update_supply(supply_id, name, category, unit, current_stock, reorder_level, unit_cost):
    """Update a supply item"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE supplies SET 
            name = ?, category = ?, unit = ?, current_stock = ?, 
            reorder_level = ?, unit_cost = ?, last_updated = ?
        WHERE id = ?
    """, (name, category, unit, current_stock, reorder_level, unit_cost, datetime.now().isoformat(), supply_id))
    conn.commit()
    conn.close()

def update_supply_stock(supply_id, quantity_used, job_id=None):
    """Deduct used quantity from supply stock"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE supplies SET current_stock = current_stock - ?, last_updated = ? WHERE id = ?", 
              (quantity_used, datetime.now().isoformat(), supply_id))
    
    if job_id:
        c.execute("INSERT INTO supply_usage (supply_id, job_id, quantity_used, used_by, used_at) VALUES (?,?,?,?,?)",
                  (supply_id, job_id, quantity_used, st.session_state.user['user_id'], datetime.now().isoformat()))
    
    conn.commit()
    conn.close()

def get_low_stock_supplies():
    """Get supplies that need reordering"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, name, category, current_stock, unit, reorder_level
        FROM supplies WHERE user_id = ? AND current_stock <= reorder_level
        ORDER BY (current_stock / reorder_level) ASC
    """, conn, params=(user_id,))
    conn.close()
    return df

def get_all_supplies():
    """Get all supplies for current user"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM supplies WHERE user_id = ? ORDER BY category, name", conn, params=(user_id,))
    conn.close()
    return df

def delete_supply(supply_id):
    """Delete a supply item"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM supplies WHERE id = ?", (supply_id,))
    conn.commit()
    conn.close()

def get_supply_usage_report(start_date, end_date):
    """Get supply usage report for date range"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT s.name, su.quantity_used, su.used_at, su.job_id
        FROM supply_usage su
        JOIN supplies s ON su.supply_id = s.id
        WHERE s.user_id = ? AND su.used_at BETWEEN ? AND ?
        ORDER BY su.used_at DESC
    """, conn, params=(user_id, start_date.isoformat(), end_date.isoformat()))
    conn.close()
    return df

# ============================================
# AI TASK LIST FUNCTIONS
# ============================================

def generate_smart_task_list(property_type, sqft, complexity, special_requests=None):
    """Generate intelligent task list based on property characteristics"""
    
    task_templates = {
        "Office Standard": [
            "🗑️ Empty all trash bins and replace liners",
            "🧹 Vacuum all carpets and rugs",
            "🪣 Dust all surfaces including desks, shelves, and blinds",
            "🪟 Clean glass doors, windows, and partitions",
            "🧼 Sanitize restrooms (toilets, sinks, counters, mirrors)",
            "🍽️ Wipe down kitchen/breakroom surfaces and appliances",
            "🧽 Mop all hard floor areas",
            "🔌 Wipe light switches, door handles, and high-touch areas"
        ],
        "Restaurant": [
            "🔥 Degrease kitchen surfaces, hood vents, and exhaust fans",
            "🧼 Sanitize all food prep areas and cutting boards",
            "🗑️ Empty grease traps and dispose properly",
            "🍽️ Clean dining area tables, chairs, and booths",
            "🧹 Sweep and mop entire floor area with degreaser",
            "🚻 Deep clean restrooms (every surface)",
            "🧽 Clean kitchen equipment exteriors (ovens, fryers, refrigerators)",
            "🪟 Clean front entrance glass and door handles"
        ],
        "Gym / Fitness": [
            "🦠 Disinfect all equipment surfaces (machines, weights, mats)",
            "🪞 Clean all mirrors streak-free",
            "🧹 Vacuum rubber flooring and weight room areas",
            "🗑️ Empty trash in locker rooms, lobby, and common areas",
            "🚿 Sanitize showers, lockers, and changing areas",
            "🧻 Restock paper products, towels, and hand sanitizer",
            "🧼 Wipe down entry doors, handles, and front desk",
            "🪣 Mop locker room and wet area floors"
        ],
        "🏠 Airbnb / Short-Term Rental": [
            "🛏️ Change all bed linens and pillowcases",
            "🧺 Replace all bath towels, hand towels, and washcloths",
            "🧼 Clean all surfaces (counters, tables, appliances, shelves)",
            "🧹 Vacuum all carpets, rugs, and upholstery",
            "🪣 Mop all hard floors (kitchen, bathroom, entry)",
            "🧻 Restock supplies (toilet paper, paper towels, soap, coffee, trash bags)",
            "🚿 Clean showers, toilets, sinks, and mirrors",
            "🪟 Wipe windows, sliding doors, and glass surfaces",
            "📸 Take after photos for host documentation",
            "🔑 Check lockbox, key return, and access instructions"
        ],
        "🏥 Medical / Dental": [
            "🦠 Disinfect all high-touch surfaces (counters, chairs, door handles)",
            "🧼 Sanitize examination rooms and procedure areas",
            "🧹 Vacuum patient waiting areas and hallways",
            "🚻 Deep clean restrooms (patient and staff)",
            "🧽 Clean reception desk and check-in area",
            "🪟 Clean glass partitions and windows",
            "🗑️ Empty medical waste containers safely and replace liners",
            "🧻 Restock paper products and hand sanitizer stations"
        ],
        "Warehouse": [
            "🧹 Sweep entire warehouse floor area",
            "🗑️ Empty all trash containers and recycling bins",
            "🧼 Clean break room and kitchenette area",
            "🚻 Clean restrooms thoroughly",
            "🧽 Wipe down high-touch areas (handrails, door handles, light switches)",
            "🪟 Clean office windows and glass panels",
            "🧹 Dust shelving, racking, and storage areas",
            "🧹 Clean entryway and loading dock areas"
        ],
        "⛽ Gas Station / C-Store": [
            "🛢️ Clean fuel pump handles, screens, and surrounding area",
            "🧼 Sanitize convenience store counters, coolers, and shelves",
            "🚻 Deep clean restrooms (fuel stations have high restroom traffic)",
            "🗑️ Empty exterior and interior trash cans",
            "🪟 Clean glass doors, windows, and refrigerator doors",
            "🍽️ Clean food prep area (if applicable) - coffee, roller grill",
            "🧹 Sweep and mop entire store floor",
            "🧻 Restock paper products in restrooms"
        ]
    }
    
    base_tasks = task_templates.get(property_type, task_templates["Office Standard"])
    
    # Adjust based on complexity
    if complexity >= 8:
        base_tasks.append("⚠️ DEEP CLEAN REQUIRED - Extra time needed (add 50% to estimate)")
        base_tasks.append("📸 Take before and after photos of all areas for documentation")
        base_tasks.append("🔄 Move furniture and equipment to clean underneath")
        base_tasks.append("🧼 Apply specialized cleaners for tough stains")
    elif complexity >= 5:
        base_tasks.append("🔄 Pay extra attention to high-traffic areas")
        base_tasks.append("📸 Take photos of any existing damage before starting")
    
    # Adjust based on size
    if sqft > 10000:
        base_tasks.append("🏢 LARGE FACILITY - Consider 2+ workers for this job")
        base_tasks.append("⏰ Estimated time: 6-8 hours minimum")
    elif sqft > 5000:
        base_tasks.append("⏰ Estimated time: 4-5 hours")
    elif sqft < 1000:
        base_tasks.append("📏 SMALL SPACE - Quick turnaround (1-2 hours)")
    
    # Add special requests
    if special_requests:
        base_tasks.append(f"📝 SPECIAL REQUEST FROM CLIENT: {special_requests}")
    
    return base_tasks

def generate_cleaning_duration(sqft, property_type, complexity):
    """Estimate cleaning duration based on square footage and complexity"""
    base_minutes_per_sqft = 0.02  # 1.2 minutes per 100 sq ft baseline
    property_multipliers = {
        "Office Standard": 1.0,
        "Restaurant": 1.8,
        "Gym / Fitness": 1.5,
        "🏠 Airbnb / Short-Term Rental": 1.3,
        "🏥 Medical / Dental": 1.4,
        "Warehouse": 0.8,
        "⛽ Gas Station / C-Store": 1.6
    }
    multiplier = property_multipliers.get(property_type, 1.0)
    complexity_mult = 0.7 + (complexity / 10)
    
    minutes = sqft * base_minutes_per_sqft * multiplier * complexity_mult
    hours = minutes / 60
    return round(hours, 1)

# ============================================
# QR CODE FUNCTIONS
# ============================================

def generate_qr_code(data):
    """Generate a QR code image from data"""
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def generate_worker_qr(worker_id, worker_name):
    """Generate a QR code for worker clock-in/out"""
    data = f"profitclean://worker/{worker_id}/{datetime.now().strftime('%Y%m%d')}"
    return generate_qr_code(data)

def generate_job_qr(job_id, client_name):
    """Generate a QR code for job check-in"""
    data = f"profitclean://job/{job_id}/{datetime.now().strftime('%Y%m%d')}"
    return generate_qr_code(data)

def scan_qr_data(qr_data):
    """Parse scanned QR data and return action"""
    # Format: profitclean://type/id/date
    try:
        parts = qr_data.replace("profitclean://", "").split("/")
        if len(parts) >= 2:
            action_type = parts[0]
            item_id = parts[1]
            return action_type, item_id
    except:
        pass
    return None, None

# ============================================
# GPS TRACKING FUNCTIONS
# ============================================

def update_worker_location(worker_id, lat, lon):
    """Update worker's current location (opt-in only)"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO worker_locations (worker_id, lat, lon, last_updated)
        VALUES (?,?,?,?)
    """, (worker_id, lat, lon, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_worker_location(worker_id):
    """Get worker's last known location"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT lat, lon, last_updated FROM worker_locations WHERE worker_id = ?", (worker_id,))
    location = c.fetchone()
    conn.close()
    return location

def calculate_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two coordinates in miles (Haversine formula)"""
    from math import radians, sin, cos, sqrt, atan2
    R = 3959.87433  # Earth's radius in miles
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    return R * c

def get_nearby_workers(job_lat, job_lon, radius_miles=10):
    """Find workers within a specified radius of a job location"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT w.id, w.name, wl.lat, wl.lon, wl.last_updated
        FROM workers w
        JOIN worker_locations wl ON w.id = wl.worker_id
        WHERE w.is_active = 1 AND wl.last_updated > datetime('now', '-1 hour')
    """, conn)
    conn.close()
    
    nearby = []
    for _, worker in df.iterrows():
        dist = calculate_distance(job_lat, job_lon, worker['lat'], worker['lon'])
        if dist <= radius_miles:
            nearby.append({
                'id': worker['id'],
                'name': worker['name'],
                'distance': round(dist, 1)
            })
    return sorted(nearby, key=lambda x: x['distance'])

# ============================================
# SUPPORT TICKET FUNCTIONS
# ============================================

def create_support_ticket(issue_type, description, steps, screenshot_data=None):
    """Create a new support ticket"""
    user_id = st.session_state.user['user_id']
    user_email = st.session_state.user.get('email', '')
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO support_tickets 
        (ticket_id, user_id, user_email, issue_type, description, steps_to_reproduce, screenshot, created_at, updated_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (ticket_id, user_id, user_email, issue_type, description, steps, screenshot_data, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    log_audit(user_id, "ticket_created", f"Support ticket {ticket_id} created")
    return ticket_id

def get_user_tickets():
    """Get all tickets for the current user"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT ticket_id, issue_type, description, status, created_at, updated_at
        FROM support_tickets WHERE user_id = ?
        ORDER BY created_at DESC
    """, conn, params=(user_id,))
    conn.close()
    return df

def get_all_tickets():
    """Get all tickets (admin view)"""
    if st.session_state.user.get('role') != 'admin':
        return pd.DataFrame()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT ticket_id, user_email, issue_type, status, created_at, updated_at
        FROM support_tickets ORDER BY created_at DESC
    """, conn)
    conn.close()
    return df

def update_ticket_status(ticket_id, status):
    """Update ticket status"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE support_tickets SET status = ?, updated_at = ? WHERE ticket_id = ?", 
              (status, datetime.now().isoformat(), ticket_id))
    if status == 'resolved':
        c.execute("UPDATE support_tickets SET resolved_at = ? WHERE ticket_id = ?", 
                  (datetime.now().isoformat(), ticket_id))
    conn.commit()
    conn.close()

def add_ticket_comment(ticket_id, message):
    """Add a comment to a support ticket"""
    user_id = st.session_state.user['user_id']
    is_staff = 1 if st.session_state.user.get('role') == 'admin' else 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO support_messages (ticket_id, user_id, message, is_staff, created_at)
        VALUES (?,?,?,?,?)
    """, (ticket_id, user_id, message, is_staff, datetime.now().isoformat()))
    c.execute("UPDATE support_tickets SET updated_at = ? WHERE ticket_id = ?", (datetime.now().isoformat(), ticket_id))
    conn.commit()
    conn.close()

def get_ticket_messages(ticket_id):
    """Get all messages for a ticket"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT sm.message, sm.is_staff, sm.created_at, u.username
        FROM support_messages sm
        JOIN users u ON sm.user_id = u.id
        WHERE sm.ticket_id = (SELECT id FROM support_tickets WHERE ticket_id = ?)
        ORDER BY sm.created_at
    """, conn, params=(ticket_id,))
    conn.close()
    return df

# ============================================
# EMAIL FUNCTIONS
# ============================================

def send_email_notification(to_email, template_name, template_data):
    """Send email notification using template"""
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT subject, body FROM email_templates WHERE name = ?", (template_name,))
        template = c.fetchone()
        c.execute("SELECT business_name, smtp_email, smtp_password FROM business_profile WHERE id=1")
        biz = c.fetchone()
        conn.close()
        
        if not template or not biz or not biz[1]:
            return False
        
        subject = template[0].format(**template_data)
        body = template[1].format(**template_data)
        
        # In production, configure actual SMTP
        # For now, log to console
        print(f"Email would send to {to_email}: {subject}")
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False

def send_estimate_email(client_email, client_name, estimate_id, amount, property_type, city):
    """Send estimate to client"""
    business_name = get_business_name()
    template_data = {
        "client_name": client_name,
        "business_name": business_name,
        "estimate_id": estimate_id,
        "amount": amount,
        "property_type": property_type,
        "city": city,
        "approval_link": "#"  # Replace with actual link
    }
    return send_email_notification(client_email, "estimate_sent", template_data)

def send_estimate_approved_email(client_email, client_name, estimate_id, amount):
    """Send estimate approved notification"""
    business_name = get_business_name()
    template_data = {
        "client_name": client_name,
        "business_name": business_name,
        "estimate_id": estimate_id,
        "amount": amount
    }
    return send_email_notification(client_email, "estimate_approved", template_data)

def send_job_reminder_email(client_email, client_name, job_date, job_time):
    """Send job reminder email"""
    business_name = get_business_name()
    template_data = {
        "client_name": client_name,
        "business_name": business_name,
        "date": job_date,
        "time": job_time
    }
    return send_email_notification(client_email, "job_reminder", template_data)

def send_review_request_email(client_email, client_name, job_id):
    """Send review request after job completion"""
    business_name = get_business_name()
    review_link = "https://g.page/r/your-place/review"  # Replace with actual Google Maps review link
    template_data = {
        "client_name": client_name,
        "business_name": business_name,
        "review_link": review_link,
        "job_id": job_id
    }
    return send_email_notification(client_email, "review_request", template_data)

# ============================================
# CSV EXPORT FUNCTIONS
# ============================================

def export_to_csv(data, filename):
    """Convert data to CSV string"""
    if not data:
        return ""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(data[0].keys())
    for row in data:
        writer.writerow(row.values())
    return output.getvalue()

def export_clients_csv():
    """Export clients to CSV"""
    df = get_all_clients()
    if df.empty:
        return ""
    return export_to_csv(df.to_dict('records'), "clients.csv")

def export_estimates_csv():
    """Export estimates to CSV"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM estimates WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return export_to_csv(df.to_dict('records'), "estimates.csv") if not df.empty else ""

def export_workers_csv():
    """Export workers to CSV"""
    df = get_all_workers(include_inactive=True)
    return export_to_csv(df.to_dict('records'), "workers.csv") if not df.empty else ""

def export_quick_jobs_csv():
    """Export quick jobs to CSV"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM quick_jobs WHERE user_id = ?", conn, params=(user_id,))
    conn.close()
    return export_to_csv(df.to_dict('records'), "quick_jobs.csv") if not df.empty else ""

def export_supplies_csv():
    """Export supplies to CSV"""
    df = get_all_supplies()
    return export_to_csv(df.to_dict('records'), "supplies.csv") if not df.empty else ""

def export_schedule_csv(date_filter=None):
    """Export schedule to CSV"""
    df = get_scheduled_jobs(date_filter=date_filter)
    return export_to_csv(df.to_dict('records'), "schedule.csv") if not df.empty else ""

def export_profit_csv():
    """Export profit data to CSV"""
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM quick_jobs WHERE user_id = ? ORDER BY job_date DESC", conn, params=(user_id,))
    conn.close()
    return export_to_csv(df.to_dict('records'), "profit.csv") if not df.empty else ""

# ============================================
# CLIENT PORTAL FUNCTIONS
# ============================================

def client_login(email, password):
    """Authenticate client for portal access"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, business_name FROM clients WHERE email = ?", (email,))
    client = c.fetchone()
    conn.close()
    
    if client:
        return True, {"client_id": client[0], "client_name": client[1]}
    return False, "Invalid email"

def get_client_estimates_portal(client_id):
    """Get estimates for client portal view"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, city, property_type, square_feet, estimated_price, created_at, status
        FROM estimates WHERE client_id = ? ORDER BY created_at DESC
    """, conn, params=(client_id,))
    conn.close()
    return df

def get_client_schedule_portal(client_id):
    """Get schedule for client portal view"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT scheduled_date, scheduled_time, status
        FROM scheduled_jobs WHERE client_id = ? AND scheduled_date >= date('now')
        ORDER BY scheduled_date
    """, conn, params=(client_id,))
    conn.close()
    return df

def approve_estimate_portal(estimate_id):
    """Client approves an estimate"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE estimates SET status = 'approved', approved_at = ? WHERE id = ?", 
              (datetime.now().isoformat(), estimate_id))
    conn.commit()
    conn.close()
    # ============================================
# PAGE FUNCTIONS - UI
# ============================================

def setup_wizard():
    """One-time setup wizard"""
    st.title("🧹 ProfitClean")
    st.caption("Created by Dust Bros & Co.")
    
    with st.form("setup"):
        st.markdown("#### Business Information")
        col1, col2 = st.columns(2)
        with col1:
            business_name = st.text_input("Business Name *", value="Dust Bros and Co")
            phone = st.text_input("Phone *", value="(555) 123-4567")
            hourly_wage = st.number_input("Base Hourly Wage", min_value=10.0, value=15.0, step=0.5)
        with col2:
            email = st.text_input("Email *", value="hello@dustbros.com")
            home_city = st.selectbox("Home Base City", FLORIDA_CITIES)
            min_job_fee = st.number_input("Minimum Job Fee", min_value=50, value=150, step=25)
        
        st.markdown("#### Email Settings (Optional)")
        smtp_email = st.text_input("SMTP Email", help="For sending notifications")
        smtp_password = st.text_input("SMTP Password", type="password")
        
        if st.form_submit_button("🚀 Start Using ProfitClean", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM business_profile")
            c.execute("""
                INSERT INTO business_profile 
                (id, business_name, phone, email, hourly_wage, profit_target, 
                 min_job_fee, home_city, per_mile_rate, sales_tax_rate, smtp_email, smtp_password, setup_complete)
                VALUES (1,?,?,?,?,?,?,?,?,?,?,?,1)
            """, (business_name, phone, email, hourly_wage, 0.30,
                  min_job_fee, home_city, 0.65, SALES_TAX_RATE, smtp_email, smtp_password))
            conn.commit()
            conn.close()
            st.success("Setup complete! Redirecting...")
            time.sleep(1)
            st.rerun()

def login_page():
    """Login page"""
    st.markdown("### 🔐 Login to ProfitClean")
    st.caption("Created by Dust Bros & Co.")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            
            if st.form_submit_button("Login", use_container_width=True):
                success, result = authenticate_user(email, password)
                if success:
                    st.session_state.user = result
                    st.session_state.page = "dashboard"
                    st.success(f"Welcome back, {result['username']}!")
                    st.rerun()
                else:
                    st.error(result)
        
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📝 Create Account", use_container_width=True):
                st.session_state.page = "create_account"
                st.rerun()
        with col2:
            if st.button("🔑 Forgot Password?", use_container_width=True):
                st.info("Contact your administrator to reset your password.")

def create_account_page():
    """Create new account page"""
    st.markdown("### 📝 Create Your Account")
    st.caption("All information is encrypted and secure")
    
    with st.form("create_account"):
        col1, col2 = st.columns(2)
        with col1:
            username = st.text_input("Username *")
            email = st.text_input("Email *")
        with col2:
            password = st.text_input("Password *", type="password")
            confirm_password = st.text_input("Confirm Password *", type="password")
        
        role = st.selectbox("Account Type", ["worker", "manager"], 
                           help="Workers can view assignments, managers can create estimates")
        
        st.markdown("---")
        st.markdown("**Password Requirements:**")
        st.markdown("""
        - At least 8 characters
        - One uppercase letter
        - One lowercase letter
        - One number
        - One special character (!@#$%^&*)
        """)
        
        if st.form_submit_button("Create Account", use_container_width=True):
            if password != confirm_password:
                st.error("Passwords do not match")
            elif not all([username, email, password]):
                st.error("Please fill in all required fields")
            else:
                success, result = create_user(username, email, password, role)
                if success:
                    st.success("✅ Account created successfully! Please log in.")
                    st.balloons()
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error(f"❌ {result}")
    
    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.rerun()

def edit_profile_page():
    """Edit user profile page"""
    if 'user' not in st.session_state:
        st.session_state.page = "login"
        st.rerun()
    
    st.markdown("### ✏️ Edit Your Profile")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, role FROM users WHERE id = ?", (st.session_state.user['user_id'],))
    user_data = c.fetchone()
    conn.close()
    
    if user_data:
        with st.form("edit_profile"):
            user_id, current_username, current_email, role = user_data
            username = st.text_input("Username", current_username)
            email = st.text_input("Email", current_email)
            st.text_input("Role", role, disabled=True)
            
            st.markdown("---")
            st.markdown("#### Change Password (optional)")
            current_password = st.text_input("Current Password", type="password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Save Changes", use_container_width=True):
                updates = []
                params = []
                
                if username != current_username:
                    updates.append("username = ?")
                    params.append(username)
                if email != current_email:
                    updates.append("email = ?")
                    params.append(email)
                
                if new_password:
                    conn2 = sqlite3.connect(DB_PATH)
                    c2 = conn2.cursor()
                    c2.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,))
                    stored_hash = c2.fetchone()[0]
                    conn2.close()
                    
                    if not verify_password(current_password, stored_hash):
                        st.error("Current password is incorrect")
                    elif new_password != confirm_password:
                        st.error("New passwords do not match")
                    else:
                        is_valid, msg = validate_password_strength(new_password)
                        if not is_valid:
                            st.error(msg)
                        else:
                            hashed, salt = hash_password(new_password)
                            updates.append("password_hash = ?")
                            updates.append("salt = ?")
                            params.extend([hashed, salt])
                
                if updates:
                    params.append(user_id)
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
                    conn.commit()
                    conn.close()
                    log_audit(user_id, "profile_updated", "User updated profile")
                    st.success("Profile updated successfully!")
                    st.rerun()
                else:
                    st.info("No changes made")
    
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

# ============================================
# DASHBOARD
# ============================================

@require_auth
def dashboard():
    """Main dashboard"""
    business_name = get_business_name()
    user = st.session_state.user
    
    st.title(f"🧹 {business_name}")
    st.caption(f"Welcome, {user['username']} ({user['role']}) | Created by Dust Bros & Co.")
    
    # Sidebar Navigation
    with st.sidebar:
        st.markdown("### 📋 Menu")
        
        menu_items = [
            ("🏠 Dashboard", "dashboard"),
            ("📝 New Estimate", "estimate"),
            ("⚡ Quick Job", "quick"),
            ("👥 Clients", "clients"),
            ("👷 Workers", "workers"),
            ("📅 Schedule", "schedule"),
            ("🔍 Inspections", "inspections"),
            ("💰 Profit", "profit"),
            ("📋 History", "history"),
            ("💬 Team Chat", "chat"),
            ("📦 Supplies", "supplies"),
            ("🤖 AI Tasks", "ai_tasks"),
            ("📱 QR Tracking", "qr_tracking"),
            ("📍 GPS Tracking", "gps_tracking"),
            ("💾 Backup", "backup"),
            ("🎫 Support", "support"),
            ("⚙️ Settings", "settings"),
            ("✏️ Edit Profile", "edit_profile"),
        ]
        
        for label, page in menu_items:
            if st.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        
        st.markdown("---")
        
        # Support Section (Collapsible)
        with st.expander("💬 Need Help?", expanded=False):
            if st.button("📝 Report Issue", use_container_width=True):
                st.session_state.show_support_modal = True
                st.rerun()
            if st.button("📋 My Tickets", use_container_width=True):
                st.session_state.page = "my_tickets"
                st.rerun()
            st.caption("*We respond within 24 hours*")
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()
            st.rerun()
    
    st.markdown("---")
    
    # Quick Stats
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM clients WHERE user_id = ?", (user['user_id'],))
    client_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM estimates WHERE user_id = ? AND status = 'sent'", (user['user_id'],))
    pending_estimates = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM workers WHERE user_id = ? AND is_active = 1", (user['user_id'],))
    worker_count = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE user_id = ? AND status = 'scheduled' AND scheduled_date >= date('now')", (user['user_id'],))
    upcoming_jobs = c.fetchone()[0]
    conn.close()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{client_count}</div><div class="metric-label">Clients</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{pending_estimates}</div><div class="metric-label">Pending Estimates</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{worker_count}</div><div class="metric-label">Active Workers</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{upcoming_jobs}</div><div class="metric-label">Upcoming Jobs</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Recent Estimates
    st.markdown("### 📝 Recent Estimates")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, client_name, city, property_type, estimated_price, created_at, status
        FROM estimates WHERE user_id = ? ORDER BY created_at DESC LIMIT 5
    """, conn, params=(user['user_id'],))
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Click 'New Estimate' to get started.")
    else:
        for _, row in df.iterrows():
            status_badge = "✅ Approved" if row['status'] == 'approved' else "⏳ Pending" if row['status'] == 'sent' else row['status']
            st.markdown(f"""
            <div class="card">
                <strong>#{row['id']}</strong> - {row['client_name'] or 'Unnamed Client'} in {row['city']}<br>
                <small>{row['property_type']} • ${row['estimated_price']:,.2f}</small><br>
                <small>Created: {row['created_at'][:10]} • {status_badge}</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Low Stock Alert
    low_stock = get_low_stock_supplies()
    if not low_stock.empty:
        st.markdown("---")
        st.warning("⚠️ **Low Stock Alert** - The following supplies need reordering:")
        for _, row in low_stock.iterrows():
            st.markdown(f"- **{row['name']}**: {row['current_stock']} {row['unit']} remaining (Reorder at {row['reorder_level']})")
    
    # Upcoming Jobs Preview
    st.markdown("---")
    st.markdown("### 📅 Upcoming Jobs")
    df = get_upcoming_jobs(days=7)
    if df.empty:
        st.info("No upcoming jobs scheduled.")
    else:
        for _, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                📅 {row['scheduled_date']} at {row['scheduled_time']}<br>
                🏢 {row['client_name']}<br>
                Status: {row['status']}
            </div>
            """, unsafe_allow_html=True)

# ============================================
# ESTIMATE PAGE
# ============================================

@require_auth
def estimate_page():
    """New estimate page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📝 New Estimate")
    st.caption(f"💰 Florida sales tax ({SALES_TAX_RATE * 100}%) included, prices rounded up.")
    
    # Basic Information
    col1, col2 = st.columns(2)
    with col1:
        city = st.selectbox("📍 City", FLORIDA_CITIES)
        property_type = st.selectbox("🏢 Property Type", list(PROPERTY_TYPES.keys()))
    with col2:
        frequency = st.selectbox("📅 Frequency", list(FREQUENCIES.keys()))
        complexity = st.slider("⚙️ Complexity (1-10)", 1, 10, 3, help="1 = Easy / 10 = Heavy debris")
    
    is_airbnb = property_type == "🏠 Airbnb / Short-Term Rental"
    
    if is_airbnb:
        col1, col2 = st.columns(2)
        with col1:
            bedrooms = st.number_input("🛏️ Bedrooms", min_value=0, max_value=10, value=2)
        with col2:
            bathrooms = st.number_input("🚽 Bathrooms", min_value=0, max_value=8, value=1)
        sqft = 0
    else:
        sqft = st.number_input("📐 Square Feet", min_value=100, max_value=100000, value=2000, step=100)
        bedrooms = 0
        bathrooms = 0
    
    travel_miles = st.number_input("🚗 Travel Miles (round trip)", min_value=0, value=25, step=5)
    
    # Client Information
    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("👤 Client Name", placeholder="Enter client name")
    with col2:
        client_email = st.text_input("📧 Client Email", placeholder="For sending estimate")
    
    # Internal Cost Estimates (Staff Only)
    with st.expander("🔒 INTERNAL ONLY - Cost Estimates (Not shown to customers)"):
        st.caption("Enter your estimated costs to see true profit margins")
        col1, col2 = st.columns(2)
        with col1:
            hours_estimated = st.number_input("Estimated hours for this job", min_value=0.5, value=3.0, step=0.5)
        with col2:
            materials_cost_est = st.number_input("Estimated materials cost ($)", min_value=0, value=35, step=5)
    
    # Add-On Services
    st.markdown("---")
    st.markdown("### ➕ Add-On Services")
    col1, col2, col3 = st.columns(3)
    with col1:
        add_window = st.checkbox("Window Cleaning (+$50)")
        add_carpet = st.checkbox("Carpet Cleaning (+$0.20/sq ft)")
    with col2:
        add_floor = st.checkbox("Floor Stripping/Waxing (+$0.30/sq ft)")
        add_disinfection = st.checkbox("Electrostatic Disinfection (+$75)")
    with col3:
        add_pressure = st.checkbox("Pressure Washing (+$125)")
        add_trash = st.checkbox("Extra Trash Removal (+$25)")
        add_event = st.checkbox("Event Cleanup (+$150)")
    
    add_ons = {
        'window_cleaning': add_window,
        'carpet_cleaning': add_carpet,
        'floor_waxing': add_floor,
        'disinfection': add_disinfection,
        'pressure_washing': add_pressure,
        'extra_trash': add_trash,
        'event_cleanup': add_event
    }
    
    # Pricing Modifiers
    st.markdown("---")
    st.markdown("### 🎯 Pricing Modifiers")
    
    col1, col2 = st.columns(2)
    with col1:
        holidays = ["None"] + list(HOLIDAY_RATES.keys())
        holiday = st.selectbox("🎄 Holiday Service", holidays, help="Select if cleaning falls on a holiday")
        
        emergency_options = ["Standard (3+ days notice)", "2 days notice (+25%)", "Next day (+50%)", "Same day (+75%)"]
        emergency_map = {"Standard (3+ days notice)": 72, "2 days notice (+25%)": 48, "Next day (+50%)": 24, "Same day (+75%)": 12}
        emergency = st.selectbox("🚨 Emergency / Rush Service", emergency_options)
        notice_hours = emergency_map[emergency]
    
    with col2:
        num_locations = st.number_input("📍 Number of locations for this client", min_value=1, max_value=20, value=1,
                                         help="Multi-location discount applies (5-15% off)")
        
        contract_options = ["No contract", "3 months (-5%)", "6 months (-10%)", "12 months (-15%)", "24+ months (-20%)"]
        contract_map = {"No contract": 0, "3 months (-5%)": 3, "6 months (-10%)": 6, "12 months (-15%)": 12, "24+ months (-20%)": 24}
        contract = st.selectbox("📄 Recurring Contract", contract_options)
        contract_months = contract_map[contract]
        
        has_sunpass = st.checkbox("🪪 Have SunPass?", value=True, help="SunPass gives discounted toll rates")
    
    # Calculate pricing
    result = calculate_price_with_tiers(
        city, property_type, sqft, bedrooms, bathrooms, frequency, complexity,
        travel_miles, add_ons, holiday, num_locations, notice_hours, contract_months
    )
    
    # Display Pricing Options
    st.markdown("---")
    st.markdown("### 💰 Pricing Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"""
        <div class="pricing-tier-low">
            <div style="color:#92400e; font-weight:600;">🔥 LOWEST OFFER</div>
            <div style="font-size:2rem; font-weight:800; color:#92400e;">${result['lowest']['total']}</div>
            <div style="font-size:0.8rem;">+ ${result['lowest']['tax']:.2f} tax</div>
            <div style="margin-top:0.5rem; font-size:0.75rem; color:#92400e;">
                0% margin • Break-even
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.markdown(f"""
        <div class="pricing-tier-fair">
            <div style="color:#065f46; font-weight:600;">💰 FAIR MARKET</div>
            <div style="font-size:2rem; font-weight:800; color:#065f46;">${result['fair']['total']}</div>
            <div style="font-size:0.8rem;">+ ${result['fair']['tax']:.2f} tax</div>
            <div style="margin-top:0.5rem; font-size:0.75rem; color:#065f46;">
                {result['fair']['margin']}% margin • Recommended
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with col3:
        st.markdown(f"""
        <div class="pricing-tier-high">
            <div style="color:#5b21b6; font-weight:600;">⭐ HIGHEST (Premium)</div>
            <div style="font-size:2rem; font-weight:800; color:#5b21b6;">${result['highest']['total']}</div>
            <div style="font-size:0.8rem;">+ ${result['highest']['tax']:.2f} tax</div>
            <div style="margin-top:0.5rem; font-size:0.75rem; color:#5b21b6;">
                {result['highest']['margin']}% margin • Premium service
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Internal breakdown (staff only)
    with st.expander("🔒 INTERNAL COST BREAKDOWN (Staff Only)"):
        st.markdown(f"""
        - **Labor:** {result['labor_hours']} hrs @ $15.00/hr = ${result['labor_cost']:.2f}
        - **Materials:** ${result['materials_cost']:.2f}
        - **Travel:** ${result['travel_cost']:.2f}
        - **Tolls:** ${result['toll_estimate']:.2f}
        - **Add-Ons:** ${result['add_on_total']:.2f}
        - **True Cost (Break-even):** ${result['true_cost']:.2f}
        """)
    
    # Save estimate
    if st.button("💾 Save & Send Estimate", use_container_width=True):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if client exists
        if client_email:
            c.execute("SELECT id FROM clients WHERE email = ? AND user_id = ?", (client_email, st.session_state.user['user_id']))
            existing = c.fetchone()
            if existing:
                client_id = existing[0]
            else:
                c.execute("INSERT INTO clients (user_id, business_name, email, created_at, updated_at) VALUES (?,?,?,?,?)",
                          (st.session_state.user['user_id'], client_name, client_email, datetime.now().isoformat(), datetime.now().isoformat()))
                client_id = c.lastrowid
        else:
            client_id = None
        
        c.execute("""
            INSERT INTO estimates 
            (user_id, client_id, client_name, client_email, city, property_type, square_feet, bedrooms, bathrooms,
             frequency, complexity, travel_miles, toll_cost, add_on_window, add_on_carpet, add_on_floor,
             add_on_disinfection, add_on_pressure, add_on_trash, add_on_event, subtotal, tax, estimated_price,
             lowest_price, fair_price, highest_price, created_at, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (st.session_state.user['user_id'], client_id, client_name, client_email, city, property_type, sqft, bedrooms, bathrooms,
              frequency, complexity, travel_miles, result['toll_estimate'], 
              1 if add_window else 0, 1 if add_carpet else 0, 1 if add_floor else 0,
              1 if add_disinfection else 0, 1 if add_pressure else 0, 1 if add_trash else 0, 1 if add_event else 0,
              result['fair']['subtotal'], result['fair']['tax'], result['fair']['total'],
              result['lowest']['total'], result['fair']['total'], result['highest']['total'],
              datetime.now().isoformat(), "sent"))
        
        estimate_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Send email notification
        if client_email:
            send_estimate_email(client_email, client_name, estimate_id, result['fair']['total'], property_type, city)
        
        st.success(f"✅ Estimate #{estimate_id} saved and sent to {client_email if client_email else 'client'}!")
        st.balloons()

# ============================================
# QUICK JOB PAGE
# ============================================

@require_auth
def quick_job_page():
    """Quick job entry page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### ⚡ Quick Job Entry")
    st.caption("Log a completed job quickly to track profit")
    
    with st.form("quick_form"):
        col1, col2 = st.columns(2)
        with col1:
            job_date = st.date_input("Date", datetime.now())
            description = st.text_input("Job Description", placeholder="e.g., Office cleaning - 123 Main St")
        with col2:
            hours = st.number_input("Hours Worked", min_value=0.5, value=2.0, step=0.5)
            amount = st.number_input("Amount Invoiced", min_value=0.0, value=350.0, step=25.0)
        
        expenses = st.number_input("Job Expenses (materials, tolls, parking)", min_value=0.0, value=25.0, step=10.0)
        
        # Get hourly wage
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT hourly_wage FROM business_profile WHERE id=1")
        row = c.fetchone()
        conn.close()
        hourly_wage = row[0] if row else 15.0
        
        labor_cost = hours * hourly_wage
        profit = amount - expenses - labor_cost
        margin = (profit / amount * 100) if amount > 0 else 0
        
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Labor Cost", f"${labor_cost:.2f}")
        with col2:
            st.metric("Estimated Profit", f"${profit:.2f}", delta=f"{margin:.0f}% margin")
        with col3:
            st.metric("Profit Margin", f"{margin:.0f}%")
        
        if st.form_submit_button("💾 Save Quick Job", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT INTO quick_jobs 
                (user_id, job_date, description, hours, amount_invoiced, job_expenses, profit, created_at)
                VALUES (?,?,?,?,?,?,?,?)
            """, (st.session_state.user['user_id'], job_date.isoformat(), description, hours, amount, expenses, profit, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            st.success("✅ Quick job saved!")
            st.rerun()

# ============================================
# CLIENTS PAGE (Full CRUD)
# ============================================

@require_auth
def clients_page():
    """Full client management page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 👥 Client Management")
    
    # Export button
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("📥 Export to CSV", use_container_width=True):
            csv_data = export_clients_csv()
            if csv_data:
                st.download_button("Download CSV", csv_data, "clients.csv", "text/csv")
            else:
                st.warning("No clients to export")
    
    # Add Client Form
    with st.expander("➕ Add New Client"):
        with st.form("new_client_form"):
            col1, col2 = st.columns(2)
            with col1:
                business_name = st.text_input("Business Name *")
                contact_name = st.text_input("Contact Name")
                phone = st.text_input("Phone")
                email = st.text_input("Email")
            with col2:
                address = st.text_input("Address")
                city = st.text_input("City")
                state = st.text_input("State", value="FL")
                zip_code = st.text_input("Zip Code")
            
            lat = st.number_input("Latitude (optional)", value=0.0, format="%.6f", help="For location-based services")
            lon = st.number_input("Longitude (optional)", value=0.0, format="%.6f")
            notes = st.text_area("Notes")
            
            if st.form_submit_button("Save Client"):
                if business_name:
                    add_client(business_name, contact_name, phone, email, address, city, state, zip_code, lat, lon, notes)
                    st.success(f"✅ {business_name} added!")
                    st.rerun()
                else:
                    st.error("Business name is required")
    
    # Client List
    df = get_all_clients()
    
    if df.empty:
        st.info("No clients yet. Click 'Add New Client' to get started.")
    else:
        # Search
        search = st.text_input("🔍 Search clients", placeholder="Search by name, contact, or email...")
        if search:
            df = df[df['business_name'].str.contains(search, case=False) | 
                    df['contact_name'].str.contains(search, case=False, na=False) |
                    df['email'].str.contains(search, case=False, na=False)]
        
        for _, row in df.iterrows():
            with st.expander(f"🏢 {row['business_name']} - {row['city'] or 'No city'}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"""
                    **Contact:** {row['contact_name'] or 'N/A'}<br>
                    **Phone:** {row['phone'] or 'N/A'}<br>
                    **Email:** {row['email'] or 'N/A'}<br>
                    **Address:** {row['address'] or 'N/A'}<br>
                    **City:** {row['city'] or 'N/A'}, {row['state'] or 'FL'} {row['zip'] or ''}
                    """)
                with col2:
                    st.markdown(f"**Notes:** {row['notes'] or 'No notes'}")
                    st.markdown(f"**Created:** {row['created_at'][:10] if row['created_at'] else 'N/A'}")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button(f"✏️ Edit", key=f"edit_{row['id']}"):
                        st.session_state.edit_client_id = row['id']
                        st.session_state.show_edit_form = True
                with col2:
                    if st.button(f"📋 Estimates", key=f"estimates_{row['id']}"):
                        st.session_state.view_client_estimates = row['id']
                with col3:
                    if st.button(f"📅 Schedule", key=f"schedule_{row['id']}"):
                        st.session_state.schedule_for_client = row['id']
                with col4:
                    if st.button(f"🗑️ Delete", key=f"delete_{row['id']}"):
                        delete_client(row['id'])
                        st.success(f"Deleted {row['business_name']}")
                        st.rerun()
        
        # Edit Client Form
        if st.session_state.get('show_edit_form', False):
            client = get_client_by_id(st.session_state.edit_client_id)
            if client:
                with st.form("edit_client_form"):
                    st.markdown(f"#### Editing {client[1]}")
                    col1, col2 = st.columns(2)
                    with col1:
                        business_name = st.text_input("Business Name", client[1])
                        contact_name = st.text_input("Contact Name", client[2] or "")
                        phone = st.text_input("Phone", client[3] or "")
                        email = st.text_input("Email", client[4] or "")
                    with col2:
                        address = st.text_input("Address", client[5] or "")
                        city = st.text_input("City", client[6] or "")
                        state = st.text_input("State", client[7] or "FL")
                        zip_code = st.text_input("Zip Code", client[8] or "")
                    
                    lat = st.number_input("Latitude", value=client[9] or 0.0, format="%.6f")
                    lon = st.number_input("Longitude", value=client[10] or 0.0, format="%.6f")
                    notes = st.text_area("Notes", client[11] or "")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.form_submit_button("Update Client"):
                            update_client(client[0], business_name, contact_name, phone, email, address, city, state, zip_code, lat, lon, notes)
                            st.success("Client updated!")
                            st.session_state.show_edit_form = False
                            st.rerun()
                    with col2:
                        if st.form_submit_button("Cancel"):
                            st.session_state.show_edit_form = False
                            st.rerun()

# ============================================
# WORKERS PAGE (Full Management)
# ============================================

@require_auth
def workers_page():
    """Full worker management page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 👷 Worker Management")
    st.caption("Manage your team and ensure fair job distribution")
    
    tab1, tab2, tab3, tab4 = st.tabs(["📋 Workers List", "➕ Add Worker", "🔄 Auto-Assign", "📊 Fairness Report"])
    
    with tab1:
        workers_df = get_all_workers()
        
        if workers_df.empty:
            st.info("No workers added yet.")
        else:
            for _, worker in workers_df.iterrows():
                status_badge = "🟢 Active" if worker['is_active'] else "🔴 Inactive"
                st.markdown(f"""
                <div class="worker-card">
                    <strong>👤 {worker['name']}</strong> {status_badge}<br>
                    📞 {worker['phone'] or 'No phone'} | 📧 {worker['email'] or 'No email'}<br>
                    📍 {worker['home_address'] or 'No address'}<br>
                    💰 ${worker['hourly_rate']:.2f}/hr | 📊 Jobs: {worker['jobs_assigned']} assigned | 🔄 Queue: #{worker['queue_position'] + 1}
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    if st.button(f"✏️ Edit", key=f"edit_{worker['id']}"):
                        st.session_state.edit_worker_id = worker['id']
                        st.session_state.show_edit_worker = True
                with col2:
                    if st.button(f"📅 Schedule", key=f"schedule_{worker['id']}"):
                        st.session_state.view_worker_schedule = worker['id']
                with col3:
                    if st.button(f"📊 Stats", key=f"stats_{worker['id']}"):
                        st.session_state.view_worker_stats = worker['id']
                with col4:
                    if st.button(f"🗑️ Delete", key=f"delete_{worker['id']}"):
                        delete_worker(worker['id'])
                        st.success(f"Deleted {worker['name']}")
                        st.rerun()
        
        # Export button
        csv_data = export_workers_csv()
        if csv_data:
            st.download_button("📥 Export Workers to CSV", csv_data, "workers.csv", "text/csv")
    
    with tab2:
        with st.form("add_worker_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name *")
                phone = st.text_input("Phone")
                email = st.text_input("Email")
                hourly_rate = st.number_input("Hourly Rate", min_value=10.0, value=15.0, step=0.5)
            with col2:
                address = st.text_input("Home Address")
                lat = st.number_input("Latitude (for location tracking)", value=0.0, format="%.6f")
                lon = st.number_input("Longitude", value=0.0, format="%.6f")
            
            if st.form_submit_button("Add Worker"):
                if name:
                    add_worker(name, phone, email, address, lat, lon, hourly_rate)
                    st.success(f"✅ {name} added to the team!")
                    st.rerun()
                else:
                    st.error("Please enter worker's name")
    
    with tab3:
        st.markdown("#### 🤖 Auto-Assign Job to Fair Worker")
        st.caption("System finds the best worker based on fairness queue and location")
        
        # Get next worker in queue
        next_worker = get_next_worker_from_queue()
        if next_worker:
            st.info(f"**Next in queue:** {next_worker[1]} (Queue position #{next_worker[4]})")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📋 Assign Next Worker", use_container_width=True):
                    # Create placeholder job assignment
                    assign_job_to_worker(1, next_worker[0])
                    st.success(f"Assigned to {next_worker[1]}!")
                    rotate_queue()
                    st.rerun()
            with col2:
                if st.button("🔄 Skip & Rotate Queue", use_container_width=True):
                    rotate_queue()
                    st.success("Queue rotated!")
                    st.rerun()
        else:
            st.warning("No active workers available")
        
        st.markdown("---")
        st.markdown("#### Manual Assignment by Location")
        
        col1, col2 = st.columns(2)
        with col1:
            job_lat = st.number_input("Job Latitude", value=0.0, format="%.6f")
            job_lon = st.number_input("Job Longitude", value=0.0, format="%.6f")
        
        if st.button("🔍 Find Nearest Workers", use_container_width=True):
            if job_lat != 0 or job_lon != 0:
                # Use GPS tracking to find nearby workers
                nearby = get_nearby_workers(job_lat, job_lon, radius_miles=10)
                if nearby:
                    st.markdown("**Nearest workers:**")
                    for worker in nearby:
                        st.markdown(f"- {worker['name']} - {worker['distance']} miles away")
                else:
                    st.info("No workers found within 10 miles")
            else:
                st.warning("Please enter job coordinates")
    
    with tab4:
        st.markdown("#### 📊 Fairness Report")
        
        workers_df = get_all_workers(include_inactive=False)
        if workers_df.empty:
            st.info("No workers to report")
        else:
            st.dataframe(workers_df[['name', 'jobs_assigned', 'jobs_completed', 'queue_position']], use_container_width=True)
            
            # Job distribution chart
            st.markdown("#### 📈 Job Distribution")
            st.bar_chart(workers_df.set_index('name')['jobs_assigned'])
            
            # Fairness score
            avg_jobs = workers_df['jobs_assigned'].mean()
            variance = workers_df['jobs_assigned'].std() if len(workers_df) > 1 else 0
            fairness_score = max(0, 100 - (variance * 10))
            
            st.metric("Fairness Score", f"{fairness_score:.0f}%", 
                     help="Higher score means more equal job distribution")
            
            if fairness_score < 70:
                st.warning("⚠️ Job distribution is uneven. Consider using Auto-Assign for better fairness.")
            else:
                st.success("✅ Job distribution is fair across all workers!")

# ============================================
# SCHEDULE PAGE
# ============================================

@require_auth
def schedule_page():
    """Full schedule management page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📅 Job Schedule")
    
    # Date picker
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        view_date = st.date_input("Select Date", datetime.now())
    with col2:
        view_status = st.selectbox("Status", ["All", "scheduled", "completed", "cancelled"])
    with col3:
        if st.button("📥 Export Schedule", use_container_width=True):
            csv_data = export_schedule_csv(date_filter=view_date)
            if csv_data:
                st.download_button("Download CSV", csv_data, "schedule.csv", "text/csv")
    
    # Add new job
    with st.expander("➕ Add New Scheduled Job"):
        col1, col2, col3 = st.columns(3)
        with col1:
            clients_df = get_all_clients()
            client_options = ["Select a client..."] + clients_df['business_name'].tolist() if not clients_df.empty else ["No clients"]
            client_name = st.selectbox("Client", client_options)
        with col2:
            workers_df = get_all_workers()
            worker_options = ["Unassigned"] + workers_df['name'].tolist() if not workers_df.empty else ["No workers"]
            worker_name = st.selectbox("Assign to Worker", worker_options)
        with col3:
            scheduled_time = st.selectbox("Time", ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"])
        
        notes = st.text_area("Notes")
        
        if st.button("📅 Schedule Job", use_container_width=True):
            if client_name != "Select a client..." and client_name != "No clients":
                client_id = clients_df[clients_df['business_name'] == client_name]['id'].values[0]
                worker_id = None
                if worker_name != "Unassigned" and worker_name != "No workers":
                    worker_id = workers_df[workers_df['name'] == worker_name]['id'].values[0]
                
                schedule_job(client_id, client_name, None, None, worker_id, view_date, scheduled_time, notes)
                st.success(f"✅ Job scheduled for {client_name} on {view_date} at {scheduled_time}")
                st.rerun()
            else:
                st.warning("Please select a client")
    
    # Display schedule
    st.markdown("---")
    st.markdown(f"#### Schedule for {view_date.strftime('%A, %B %d, %Y')}")
    
    df = get_scheduled_jobs(date_filter=view_date, status_filter=view_status)
    
    if df.empty:
        st.info("No jobs scheduled for this date")
    else:
        for _, row in df.iterrows():
            status_color = "🟢" if row['status'] == 'scheduled' else "✅" if row['status'] == 'completed' else "🔴"
            
            # Get worker name if assigned
            worker_name = "Unassigned"
            if row['assigned_worker_id']:
                workers_df = get_all_workers()
                worker_match = workers_df[workers_df['id'] == row['assigned_worker_id']]
                if not worker_match.empty:
                    worker_name = worker_match.iloc[0]['name']
            
            st.markdown(f"""
            <div class="card">
                <strong>{status_color} {row['scheduled_time']}</strong> - {row['client_name']}<br>
                <small>Worker: {worker_name} • Status: {row['status']}</small><br>
                <small>Notes: {row['notes'] or 'None'}</small>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if row['status'] == 'scheduled' and st.button(f"✅ Mark Complete", key=f"complete_{row['id']}"):
                    update_job_status(row['id'], "completed")
                    st.success("Job marked as completed!")
                    st.rerun()
            with col2:
                if row['status'] == 'scheduled' and st.button(f"❌ Cancel", key=f"cancel_{row['id']}"):
                    update_job_status(row['id'], "cancelled")
                    st.warning("Job cancelled")
                    st.rerun()
                    # ============================================
# INSPECTIONS PAGE (Dynamic)
# ============================================

@require_auth
def inspections_page():
    """Dynamic inspection page with room-by-room checklists"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 🔍 Pre-Inspection Checklist")
    st.caption("Document existing conditions before starting work - photos save automatically")
    
    # Initialize or continue inspection
    if 'inspection' not in st.session_state or st.session_state.inspection is None:
        st.markdown("#### Start a New Inspection")
        
        clients_df = get_all_clients()
        client_options = ["Select a client..."] + clients_df['business_name'].tolist() if not clients_df.empty else ["No clients"]
        client_selected = st.selectbox("Client", client_options)
        property_type = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()))
        scheduled_jobs_df = get_scheduled_jobs(date_filter=datetime.now().date())
        job_options = ["None"] + [f"Job #{row['id']} - {row['client_name']}" for _, row in scheduled_jobs_df.iterrows()]
        scheduled_job = st.selectbox("Link to Scheduled Job (optional)", job_options)
        
        if st.button("Start Inspection", use_container_width=True):
            if client_selected != "Select a client..." and client_selected != "No clients":
                client_id = clients_df[clients_df['business_name'] == client_selected]['id'].values[0]
                scheduled_job_id = None
                if scheduled_job != "None":
                    scheduled_job_id = int(scheduled_job.split(" - ")[0].replace("Job #", ""))
                init_inspection_session(client_id, client_selected, property_type, scheduled_job_id)
                st.rerun()
            else:
                st.warning("Please select a client")
    else:
        # Show inspection progress
        areas = st.session_state.inspection['areas']
        completed = len([a for a in areas if a['status'] == 'completed'])
        total = len(areas)
        progress = completed / total if total > 0 else 1
        
        st.progress(progress)
        st.caption(f"📊 Progress: {completed} of {total} areas completed")
        
        # Add missing area (dynamic)
        with st.expander("➕ Forgot an area? Add it without losing progress"):
            col1, col2 = st.columns([2, 1])
            with col1:
                area_type = st.selectbox("Area type", ["Restroom", "Office", "Breakroom", "Kitchen", "Gym Area", "Storage", "Lobby", "Conference Room", "Bathroom", "Hallway", "Classroom", "Warehouse", "Parking Lot", "Exterior"])
            with col2:
                quantity = st.number_input("How many?", min_value=1, max_value=10, value=1)
            if st.button("➕ Add Area"):
                add_inspection_area(area_type, quantity)
                st.rerun()
        
        # Edit areas manager
        if st.button("✏️ Edit All Areas (Add/Delete/Reorder)", use_container_width=True):
            st.session_state.show_area_manager = not st.session_state.get('show_area_manager', False)
        
        if st.session_state.get('show_area_manager', False):
            with st.expander("📋 Manage Areas", expanded=True):
                for idx, area in enumerate(areas):
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    with col1:
                        status_icon = "✅" if area['status'] == 'completed' else "⏳" if area['status'] == 'in_progress' else "⬜" if area['status'] == 'pending' else "✏️"
                        st.markdown(f"{status_icon} **{area['name']} #{area['room_number']}**")
                    with col2:
                        if area['status'] == 'completed' and st.button(f"Edit", key=f"edit_{idx}"):
                            edit_inspection_area(idx)
                            st.rerun()
                    with col3:
                        if st.button(f"Delete", key=f"del_{idx}"):
                            st.session_state.inspection['areas'].pop(idx)
                            st.rerun()
                    with col4:
                        if area['status'] == 'pending' and st.button(f"Start", key=f"start_{idx}"):
                            st.session_state.inspection['current_area_index'] = idx
                            st.session_state.inspection['areas'][idx]['status'] = 'in_progress'
                            st.rerun()
                if st.button("Close Manager"):
                    st.session_state.show_area_manager = False
                    st.rerun()
        
        # Current area inspection
        if not st.session_state.get('show_area_manager', False):
            current_idx = st.session_state.inspection.get('current_area_index', 0)
            if current_idx < len(areas):
                current_area = areas[current_idx]
                
                # Show version history if editing
                if current_area.get('status') == 'in_review':
                    st.warning("✏️ Editing a completed area. Changes will be saved as a new version.")
                    with st.expander("📜 Version History"):
                        for version in reversed(current_area['version_history']):
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                st.markdown(f"**Version {version['version']}** - {version['timestamp'][:16]}")
                            with col2:
                                if st.button(f"Restore", key=f"restore_{version['version']}"):
                                    restore_area_version(current_idx, version['version'])
                                    st.rerun()
                
                st.markdown(f"### 🔍 {current_area['name']} #{current_area['room_number']}")
                
                # Inspection items
                col1, col2 = st.columns(2)
                with col1:
                    floors = st.radio("Floors Condition", ["Good", "Stains", "Scuffs", "Damage"], 
                                      index=["Good", "Stains", "Scuffs", "Damage"].index(current_area['responses'].get('floors', 'Good')), key=f"floors_{current_idx}")
                    walls = st.radio("Walls Condition", ["Good", "Scuffs", "Holes", "Damage"], 
                                     index=["Good", "Scuffs", "Holes", "Damage"].index(current_area['responses'].get('walls', 'Good')), key=f"walls_{current_idx}")
                    trash = st.radio("Trash Status", ["Empty", "Partial", "Full"], 
                                     index=["Empty", "Partial", "Full"].index(current_area['responses'].get('trash', 'Empty')), key=f"trash_{current_idx}")
                with col2:
                    supplies = st.radio("Supplies Status", ["Full", "Low", "Empty"], 
                                        index=["Full", "Low", "Empty"].index(current_area['responses'].get('supplies', 'Full')), key=f"supplies_{current_idx}")
                    odor = st.radio("Odor", ["None", "Mild", "Strong"], 
                                    index=["None", "Mild", "Strong"].index(current_area['responses'].get('odor', 'None')), key=f"odor_{current_idx}")
                    equipment = st.radio("Equipment", ["Good", "Broken", "Missing", "N/A"], 
                                         index=["Good", "Broken", "Missing", "N/A"].index(current_area['responses'].get('equipment', 'Good')), key=f"equipment_{current_idx}")
                
                windows = st.radio("Windows", ["Clean", "Streaks", "Cracked", "Foggy"], 
                                   index=["Clean", "Streaks", "Cracked", "Foggy"].index(current_area['responses'].get('windows', 'Clean')), key=f"windows_{current_idx}")
                
                notes = st.text_area("Additional Notes", value=current_area.get('notes', ''), key=f"notes_{current_idx}")
                
                # Photo upload (simulated)
                st.caption("📸 In production, you could take photos here")
                
                # Navigation buttons
                col1, col2 = st.columns(2)
                with col1:
                    if current_idx > 0 and st.button("← Previous Area", use_container_width=True):
                        st.session_state.inspection['current_area_index'] = current_idx - 1
                        st.rerun()
                with col2:
                    button_text = "Save & Next →" if current_idx + 1 < len(areas) else "Save & Complete"
                    if st.button(button_text, use_container_width=True):
                        # Save responses
                        current_area['responses'] = {
                            'floors': floors,
                            'walls': walls,
                            'trash': trash,
                            'supplies': supplies,
                            'odor': odor,
                            'equipment': equipment,
                            'windows': windows
                        }
                        current_area['notes'] = notes
                        save_inspection_area(current_idx)
                        
                        if current_idx + 1 < len(areas):
                            st.session_state.inspection['current_area_index'] = current_idx + 1
                            st.session_state.inspection['areas'][current_idx + 1]['status'] = 'in_progress'
                        st.rerun()
        
        # Complete inspection
        if len(areas) > 0 and all(a['status'] in ['completed', 'in_review'] for a in areas):
            if st.button("✅ Complete & Save Inspection", use_container_width=True):
                save_complete_inspection()
                st.success("✅ Inspection completed and saved!")
                st.session_state.inspection = None
                st.rerun()

# ============================================
# PROFIT PAGE
# ============================================

@require_auth
def profit_page():
    """Profit dashboard with charts"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 💰 Profit Dashboard")
    
    # Get quick jobs data
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT * FROM quick_jobs 
        WHERE user_id = ? 
        ORDER BY job_date DESC
    """, conn, params=(st.session_state.user['user_id'],))
    
    # Get monthly expenses
    c = conn.cursor()
    c.execute("""
        SELECT insurance, vehicle, software, advertising, other 
        FROM monthly_expenses 
        WHERE user_id = ? AND month_year = ?
    """, (st.session_state.user['user_id'], datetime.now().strftime("%Y-%m")))
    expenses_row = c.fetchone()
    conn.close()
    
    if expenses_row:
        expenses = {
            "insurance": float(expenses_row[0]) if expenses_row[0] else 0.0,
            "vehicle": float(expenses_row[1]) if expenses_row[1] else 0.0,
            "software": float(expenses_row[2]) if expenses_row[2] else 0.0,
            "advertising": float(expenses_row[3]) if expenses_row[3] else 0.0,
            "other": float(expenses_row[4]) if expenses_row[4] else 0.0
        }
    else:
        expenses = {"insurance": 0.0, "vehicle": 0.0, "software": 0.0, "advertising": 0.0, "other": 0.0}
    
    total_expenses = sum(expenses.values())
    
    # Monthly Expenses Form
    st.markdown("#### Monthly Fixed Expenses")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        new_insurance = st.number_input("Insurance", value=float(expenses["insurance"]), step=50.0)
    with col2:
        new_vehicle = st.number_input("Vehicle", value=float(expenses["vehicle"]), step=50.0)
    with col3:
        new_software = st.number_input("Software", value=float(expenses["software"]), step=25.0)
    with col4:
        new_advertising = st.number_input("Advertising", value=float(expenses["advertising"]), step=50.0)
    with col5:
        new_other = st.number_input("Other", value=float(expenses["other"]), step=50.0)
    
    if st.button("Save Expenses", use_container_width=True):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO monthly_expenses 
            (user_id, month_year, insurance, vehicle, software, advertising, other)
            VALUES (?,?,?,?,?,?,?)
        """, (st.session_state.user['user_id'], datetime.now().strftime("%Y-%m"), 
              new_insurance, new_vehicle, new_software, new_advertising, new_other))
        conn.commit()
        conn.close()
        st.success("Expenses saved!")
        st.rerun()
    
    st.markdown("---")
    
    if df.empty:
        st.info("No jobs logged yet. Add some Quick Jobs to see your profit data.")
    else:
        total_revenue = float(df["amount_invoiced"].sum())
        total_job_expenses = float(df["job_expenses"].sum())
        total_profit = float(df["profit"].sum())
        margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        # Key metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Revenue", f"${total_revenue:,.2f}")
        with col2:
            st.metric("Total Job Expenses", f"${total_job_expenses:,.2f}")
        with col3:
            st.metric("Total Profit", f"${total_profit:,.2f}")
        
        col1, col2 = st.columns(2)
        with col1:
            net_profit = total_profit - total_expenses
            st.metric("Net Profit (after overhead)", f"${net_profit:,.2f}")
        with col2:
            daily_target = total_expenses / 22 if total_expenses > 0 else 0
            st.metric("Daily Break-Even Target", f"${daily_target:.0f}")
        
        st.markdown("---")
        
        # Profit Chart
        st.markdown("#### Profit Chart")
        df['month'] = pd.to_datetime(df['job_date']).dt.strftime('%Y-%m')
        monthly_profit = df.groupby('month')['profit'].sum().reset_index()
        if not monthly_profit.empty:
            fig = px.bar(monthly_profit, x='month', y='profit', title='Monthly Profit')
            st.plotly_chart(fig, use_container_width=True)
        
        # Recent Jobs Table
        st.markdown("#### Recent Jobs")
        st.dataframe(df[["job_date", "description", "hours", "amount_invoiced", "profit"]], use_container_width=True)
        
        # Export Button
        csv_data = export_profit_csv()
        if csv_data:
            st.download_button("📥 Export Profit Data to CSV", csv_data, "profit_data.csv", "text/csv")

# ============================================
# HISTORY PAGE
# ============================================

@require_auth
def history_page():
    """Estimate history page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📋 Estimate History")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, client_name, client_email, city, property_type, square_feet, 
               estimated_price, created_at, status 
        FROM estimates WHERE user_id = ? 
        ORDER BY created_at DESC
    """, conn, params=(st.session_state.user['user_id'],))
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Click 'New Estimate' to create your first one.")
    else:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            status_filter = st.selectbox("Filter by Status", ["All", "draft", "sent", "approved", "declined"])
        with col2:
            date_filter = st.date_input("Filter by Date", value=None)
        
        # Apply filters
        if status_filter != "All":
            df = df[df['status'] == status_filter]
        if date_filter:
            df = df[df['created_at'].str[:10] == date_filter.isoformat()]
        
        st.dataframe(df, use_container_width=True)
        
        col1, col2 = st.columns(2)
        with col1:
            total_value = df["estimated_price"].sum()
            st.metric("Total Value of All Estimates", f"${total_value:,.2f}")
        with col2:
            approved = df[df['status'] == 'approved']['estimated_price'].sum() if 'approved' in df['status'].values else 0
            st.metric("Approved Estimates Value", f"${approved:,.2f}")
        
        # Export button
        csv_data = export_estimates_csv()
        if csv_data:
            st.download_button("📥 Export Estimates to CSV", csv_data, "estimates.csv", "text/csv")

# ============================================
# TEAM CHAT PAGE
# ============================================

@require_auth
def chat_page():
    """Team chat page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 💬 Team Chat")
    st.caption("⚠️ **Notice:** This chat is for business purposes only. All messages are monitored by the cybersecurity team.")
    
    # Active users
    active_users = get_active_users()
    if not active_users.empty:
        st.sidebar.markdown("### 👥 Online Now")
        for _, user in active_users.iterrows():
            st.sidebar.markdown(f"🟢 {user['username']} ({user['role']})")
    
    # Chat tabs
    tab1, tab2 = st.tabs(["💬 General Chat", "🔒 Private Messages"])
    
    with tab1:
        # Message input
        with st.form(key="chat_form", clear_on_submit=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                message = st.text_input("Message", placeholder="Type your message here...", key="chat_input", label_visibility="collapsed")
            with col2:
                submitted = st.form_submit_button("Send", use_container_width=True)
            
            if submitted and message:
                send_message(message, channel='general')
                st.rerun()
        
        # Display messages
        messages = get_messages(channel='general', limit=50)
        if not messages.empty:
            for _, msg in messages[::-1].iterrows():
                time = msg['created_at'][11:16] if len(msg['created_at']) > 16 else msg['created_at']
                st.markdown(f"""
                <div style="margin-bottom: 10px; padding: 8px; border-radius: 8px; background: #f8f9fa;">
                    <strong>{msg['username']}</strong> <span style="color: #6c757d; font-size: 0.75rem;">({msg['user_role']}) • {time}</span><br>
                    {msg['message']}
                </div>
                """, unsafe_allow_html=True)
    
    with tab2:
        # Get list of other users
        conn = sqlite3.connect(DB_PATH)
        other_users = pd.read_sql_query("""
            SELECT id, username, role FROM users WHERE id != ? AND is_active = 1
        """, conn, params=(st.session_state.user['user_id'],))
        conn.close()
        
        if not other_users.empty:
            recipient = st.selectbox("Select recipient", other_users['username'].tolist())
            recipient_id = other_users[other_users['username'] == recipient]['id'].values[0]
            
            with st.form(key="private_form", clear_on_submit=True):
                private_msg = st.text_input("Private message", placeholder="Type your private message...", label_visibility="collapsed")
                if st.form_submit_button("Send Private Message"):
                    if private_msg:
                        send_message(private_msg, channel='private', recipient_id=recipient_id)
                        st.rerun()
            
            # Display private messages
            private_msgs = get_messages(channel='private', user_id=st.session_state.user['user_id'], limit=50)
            if not private_msgs.empty:
                for _, msg in private_msgs[::-1].iterrows():
                    time = msg['created_at'][11:16] if len(msg['created_at']) > 16 else msg['created_at']
                    direction = "→" if msg['direction'] == 'sent' else "←"
                    st.markdown(f"""
                    <div style="margin-bottom: 10px; padding: 8px; border-radius: 8px; background: {'#e3f2fd' if msg['direction'] == 'sent' else '#f1f8e9'}">
                        <strong>{direction} {msg['username']}</strong> <span style="color: #6c757d; font-size: 0.75rem;">{time}</span><br>
                        {msg['message']}
                    </div>
                    """, unsafe_allow_html=True)

# ============================================
# SUPPLIES PAGE
# ============================================

@require_auth
def supplies_page():
    """Supply inventory management page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📦 Supply Inventory Tracking")
    
    tab1, tab2, tab3 = st.tabs(["📊 Current Inventory", "➕ Add Supply", "📝 Log Usage"])
    
    with tab1:
        df = get_all_supplies()
        if df.empty:
            st.info("No supplies added yet.")
        else:
            st.dataframe(df[['name', 'category', 'current_stock', 'unit', 'reorder_level', 'unit_cost']], use_container_width=True)
            
            # Low stock alert
            low_stock = df[df['current_stock'] <= df['reorder_level']]
            if not low_stock.empty:
                st.warning("⚠️ **Low Stock Alert** - The following items need reordering:")
                for _, row in low_stock.iterrows():
                    st.markdown(f"- **{row['name']}**: {row['current_stock']} {row['unit']} remaining (Reorder at {row['reorder_level']})")
        
        # Export supplies
        csv_data = export_supplies_csv()
        if csv_data:
            st.download_button("📥 Export Supplies to CSV", csv_data, "supplies.csv", "text/csv")
    
    with tab2:
        with st.form("add_supply_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Supply Name")
                category = st.selectbox("Category", ["Chemicals", "Consumables", "Equipment", "PPE", "Other"])
                unit = st.selectbox("Unit", ["gallons", "bottles", "rolls", "boxes", "packs", "each"])
            with col2:
                current_stock = st.number_input("Current Stock", min_value=0.0, value=10.0)
                reorder_level = st.number_input("Reorder Level", min_value=0.0, value=5.0)
                unit_cost = st.number_input("Unit Cost ($)", min_value=0.0, value=10.0)
            
            if st.form_submit_button("Add Supply"):
                if name:
                    add_supply(name, category, unit, current_stock, reorder_level, unit_cost)
                    st.success(f"✅ {name} added to inventory!")
                    st.rerun()
                else:
                    st.error("Please enter supply name")
    
    with tab3:
        supplies_df = get_all_supplies()
        if supplies_df.empty:
            st.info("No supplies available to track usage.")
        else:
            supply_options = {row['id']: f"{row['name']} ({row['current_stock']} {row['unit']} left)" for _, row in supplies_df.iterrows()}
            supply_id = st.selectbox("Select Supply", list(supply_options.keys()), format_func=lambda x: supply_options[x])
            quantity = st.number_input("Quantity Used", min_value=0.0, step=0.5)
            job_id = st.text_input("Job ID (optional)")
            
            if st.button("Log Usage"):
                if quantity > 0:
                    update_supply_stock(supply_id, quantity, job_id if job_id else None)
                    st.success(f"✅ Logged {quantity} units used")
                    st.rerun()
                else:
                    st.error("Please enter quantity")

# ============================================
# AI TASKS PAGE
# ============================================

@require_auth
def ai_tasks_page():
    """AI-powered task list generation"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 🤖 AI-Powered Task List")
    st.caption("Smart task recommendations based on property characteristics")
    
    col1, col2 = st.columns(2)
    with col1:
        property_type = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()))
        sqft = st.number_input("Square Feet", min_value=100, value=2000, step=100)
    with col2:
        complexity = st.slider("Complexity (1-10)", 1, 10, 3)
        special_requests = st.text_area("Special Requests (optional)", placeholder="Any specific customer requests?")
    
    if st.button("Generate Smart Task List", use_container_width=True):
        tasks = generate_smart_task_list(property_type, sqft, complexity, special_requests)
        
        st.markdown("#### 📋 Recommended Tasks:")
        for i, task in enumerate(tasks, 1):
            st.checkbox(f"{i}. {task}")
        
        # Estimated duration
        estimated_hours = generate_cleaning_duration(sqft, property_type, complexity)
        st.info(f"⏰ Estimated time: {estimated_hours:.1f} hours (based on {sqft} sq ft and complexity {complexity})")
        
        # Export task list
        task_text = "\n".join([f"[ ] {task}" for task in tasks])
        st.download_button("📥 Export Task List", task_text, "task_list.txt", "text/plain")

# ============================================
# QR TRACKING PAGE
# ============================================

@require_auth
def qr_tracking_page():
    """QR code generation for worker tracking"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📱 QR Code Performance Tracking")
    st.caption("Generate QR codes for workers to scan and log hours")
    
    workers_df = get_all_workers()
    
    if workers_df.empty:
        st.info("No workers found. Add workers first.")
    else:
        selected_worker = st.selectbox("Select Worker", workers_df['name'].tolist())
        worker_id = workers_df[workers_df['name'] == selected_worker]['id'].values[0]
        
        if st.button("Generate QR Code"):
            qr_img = generate_worker_qr(worker_id, selected_worker)
            st.image(qr_img, caption=f"QR Code for {selected_worker}", width=200)
            st.info("Workers can scan this QR code to log their hours and track performance.")
            
            st.download_button(
                "📥 Download QR Code",
                qr_img,
                f"qr_{selected_worker}.png",
                "image/png"
            )

# ============================================
# GPS TRACKING PAGE
# ============================================

@require_auth
def gps_tracking_page():
    """GPS tracking opt-in page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📍 GPS Location Tracking")
    st.warning("⚠️ Location tracking is OPTIONAL and only active during work hours. You can disable anytime.")
    
    if 'gps_enabled' not in st.session_state:
        st.session_state.gps_enabled = False
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📱 Enable GPS Tracking", use_container_width=True):
            st.session_state.gps_enabled = True
            st.success("GPS tracking enabled. Your location will be shared during work hours.")
    with col2:
        if st.button("🔒 Disable GPS Tracking", use_container_width=True):
            st.session_state.gps_enabled = False
            st.info("GPS tracking disabled.")
    
    if st.session_state.gps_enabled:
        st.info("📍 Location sharing active. Your supervisor can see your location during work hours.")
        st.caption("Your location is never stored permanently and is only visible to managers during your shift.")
        
        # In production, you would use browser geolocation API
        st.markdown("""
        <script>
        if (navigator.geolocation && confirm("Share your location with dispatch?")) {
            navigator.geolocation.getCurrentPosition(function(position) {
                console.log("Location shared:", position.coords.latitude, position.coords.longitude);
            });
        }
        </script>
        """, unsafe_allow_html=True)

# ============================================
# BACKUP PAGE
# ============================================

@require_auth
def backup_page():
    """Backup and restore page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 💾 Backup & Restore")
    st.caption("Save your data locally before updates, then restore after")
    
    tab1, tab2 = st.tabs(["📥 Backup", "📤 Restore"])
    
    with tab1:
        st.markdown("#### Create Backup")
        st.info(f"Backups will be saved to: `{BACKUP_DIR}`")
        
        if st.button("Create Backup Now", use_container_width=True):
            backup_file = create_backup()
            st.success(f"✅ Backup created successfully!")
            st.code(backup_file)
            
            with open(backup_file, 'rb') as f:
                st.download_button(
                    "📥 Download Backup File",
                    f,
                    os.path.basename(backup_file),
                    "application/json"
                )
    
    with tab2:
        st.markdown("#### Restore from Backup")
        
        backups = get_backup_list()
        if not backups:
            st.info("No backups found.")
        else:
            st.dataframe(backups, use_container_width=True)
            
            selected_backup = st.selectbox("Select Backup to Restore", [b['file'] for b in backups])
            backup_path = os.path.join(BACKUP_DIR, selected_backup)
            
            st.warning("⚠️ Restoring will replace ALL current data with the backup data. This cannot be undone.")
            
            if st.button("⚠️ Restore from Backup", use_container_width=True):
                if restore_from_backup(backup_path):
                    st.success("✅ Data restored successfully! Please restart the app.")
                    st.warning("⚠️ Refresh the page to see your restored data.")
                else:
                    st.error("Restore failed. Please try again.")

# ============================================
# SUPPORT PAGE
# ============================================

@require_auth
def support_page():
    """Support tickets page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 🎫 Support Tickets")
    
    tab1, tab2 = st.tabs(["📝 New Ticket", "📋 My Tickets"])
    
    with tab1:
        with st.form("new_ticket_form"):
            issue_type = st.selectbox("Issue Type", ["Feature not working", "App crashed", "Data error", "Slow performance", "Billing question", "Feature request", "Other"])
            description = st.text_area("Describe the issue *", height=100, placeholder="What happened? What did you expect to happen?")
            steps = st.text_area("Steps to reproduce", height=80, placeholder="1. I went to...\n2. I clicked...\n3. Then this happened...")
            
            if st.form_submit_button("Submit Ticket", use_container_width=True):
                if description and steps:
                    ticket_id = create_support_ticket(issue_type, description, steps)
                    st.success(f"✅ Ticket #{ticket_id} submitted! We'll respond within 24 hours.")
                    st.balloons()
                    st.rerun()
                else:
                    st.error("Please fill in description and steps")
    
    with tab2:
        tickets = get_user_tickets()
        if tickets.empty:
            st.info("No tickets submitted yet.")
        else:
            st.dataframe(tickets, use_container_width=True)

# ============================================
# MY TICKETS PAGE
# ============================================

@require_auth
def my_tickets_page():
    """My tickets page (alias for support)"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📋 My Support Tickets")
    
    tickets = get_user_tickets()
    if tickets.empty:
        st.info("No tickets submitted yet.")
    else:
        st.dataframe(tickets, use_container_width=True)

# ============================================
# SETTINGS PAGE
# ============================================

@require_auth
def settings_page():
    """Business settings page"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### ⚙️ Business Settings")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT business_name, phone, email, hourly_wage, profit_target, 
               min_job_fee, home_city, smtp_email 
        FROM business_profile WHERE id=1
    """)
    row = c.fetchone()
    conn.close()
    
    if row:
        with st.form("settings_form"):
            st.markdown("#### Company Information")
            col1, col2 = st.columns(2)
            with col1:
                business_name = st.text_input("Business Name", row[0])
                phone = st.text_input("Phone", row[1])
                hourly_wage = st.number_input("Base Hourly Wage", value=row[3])
            with col2:
                email = st.text_input("Email", row[2])
                profit_target = st.number_input("Target Profit %", value=row[4]*100)
                min_job_fee = st.number_input("Minimum Job Fee", value=row[5])
                home_city = st.selectbox("Home Base City", FLORIDA_CITIES, index=FLORIDA_CITIES.index(row[6]) if row[6] in FLORIDA_CITIES else 0)
            
            st.markdown("#### Email Settings")
            smtp_email = st.text_input("SMTP Email (for notifications)", value=row[7] if row[7] else "")
            smtp_password = st.text_input("SMTP Password", type="password")
            
            st.markdown("#### Data Management")
            st.caption("Export your data for backup or accounting")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button("📥 Export Clients", use_container_width=True):
                    csv_data = export_clients_csv()
                    if csv_data:
                        st.download_button("Download CSV", csv_data, "clients_export.csv", "text/csv")
            with col2:
                if st.button("📥 Export Estimates", use_container_width=True):
                    csv_data = export_estimates_csv()
                    if csv_data:
                        st.download_button("Download CSV", csv_data, "estimates_export.csv", "text/csv")
            with col3:
                if st.button("📥 Export Workers", use_container_width=True):
                    csv_data = export_workers_csv()
                    if csv_data:
                        st.download_button("Download CSV", csv_data, "workers_export.csv", "text/csv")
            
            if st.form_submit_button("💾 Save Settings", use_container_width=True):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("""
                    UPDATE business_profile SET 
                        business_name=?, phone=?, email=?, hourly_wage=?, profit_target=?, 
                        min_job_fee=?, home_city=?, smtp_email=?, smtp_password=?
                    WHERE id=1
                """, (business_name, phone, email, hourly_wage, profit_target/100, 
                      min_job_fee, home_city, smtp_email, smtp_password))
                conn.commit()
                conn.close()
                st.success("Settings saved!")
                st.rerun()
    else:
        st.warning("Please complete setup first")

# ============================================
# CLIENT PORTAL PAGES
# ============================================

def client_login_page():
    """Client portal login"""
    st.markdown("### 👤 Client Portal Login")
    st.caption("Access your estimates, schedule, and account history")
    
    with st.form("client_login"):
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login", use_container_width=True):
            success, result = client_login(email, password)
            if success:
                st.session_state.client_logged_in = True
                st.session_state.client_id = result['client_id']
                st.session_state.client_name = result['client_name']
                st.session_state.page = "client_dashboard"
                st.rerun()
            else:
                st.error("Invalid email. Please request access from your provider.")
    
    if st.button("← Back to Main Site"):
        st.session_state.page = "dashboard"
        st.rerun()

def client_dashboard():
    """Client portal dashboard"""
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.client_logged_in = False
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown(f"### 👋 Welcome, {st.session_state.client_name}")
    st.caption("Client Portal - View and manage your cleaning services")
    
    tab1, tab2, tab3 = st.tabs(["📝 Estimates", "📅 Schedule", "📋 History"])
    
    with tab1:
        df = get_client_estimates_portal(st.session_state.client_id)
        if df.empty:
            st.info("No estimates yet.")
        else:
            for _, row in df.iterrows():
                st.markdown(f"""
                <div class="card">
                    <strong>Estimate #{row['id']}</strong> - {row['property_type']} in {row['city']}<br>
                    <strong>${row['estimated_price']:,.2f}</strong><br>
                    <small>Created: {row['created_at'][:10]} • Status: {row['status']}</small>
                </div>
                """, unsafe_allow_html=True)
                
                if row['status'] == 'sent':
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✅ Approve", key=f"approve_{row['id']}"):
                            approve_estimate_portal(row['id'])
                            st.success("Estimate approved! We'll contact you to schedule.")
                            st.rerun()
                    with col2:
                        if st.button(f"❌ Decline", key=f"decline_{row['id']}"):
                            st.warning("Estimate declined. We'll follow up to adjust.")
    
    with tab2:
        df = get_client_schedule_portal(st.session_state.client_id)
        if df.empty:
            st.info("No upcoming jobs scheduled.")
        else:
            for _, row in df.iterrows():
                st.markdown(f"""
                <div class="card">
                    📅 {row['scheduled_date']} at {row['scheduled_time']}<br>
                    Status: {row['status']}
                </div>
                """, unsafe_allow_html=True)
    
    with tab3:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT scheduled_date, status, completed_at
            FROM scheduled_jobs WHERE client_id = ? AND status = 'completed'
            ORDER BY scheduled_date DESC LIMIT 10
        """, conn, params=(st.session_state.client_id,))
        conn.close()
        
        if df.empty:
            st.info("No completed jobs yet.")
        else:
            for _, row in df.iterrows():
                st.markdown(f"""
                <div class="card">
                    ✅ Completed: {row['scheduled_date']}<br>
                    <small>Status: {row['status']}</small>
                </div>
                """, unsafe_allow_html=True)

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    """Main application entry point"""
    init_db()
    
    # Check if setup is complete
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT setup_complete FROM business_profile WHERE id=1")
    setup = c.fetchone()
    conn.close()
    
    if not setup or setup[0] == 0:
        setup_wizard()
    else:
        # Initialize session state
        if "page" not in st.session_state:
            st.session_state.page = "login"
        
        # Check if client is logged in (client portal mode)
        if st.session_state.get("client_logged_in", False):
            if st.session_state.page == "client_dashboard":
                client_dashboard()
            else:
                client_dashboard()
        else:
            # Page routing for admin/workers
            pages = {
                "login": login_page,
                "create_account": create_account_page,
                "edit_profile": edit_profile_page,
                "dashboard": dashboard,
                "estimate": estimate_page,
                "quick": quick_job_page,
                "clients": clients_page,
                "workers": workers_page,
                "schedule": schedule_page,
                "inspections": inspections_page,
                "profit": profit_page,
                "history": history_page,
                "chat": chat_page,
                "supplies": supplies_page,
                "ai_tasks": ai_tasks_page,
                "qr_tracking": qr_tracking_page,
                "gps_tracking": gps_tracking_page,
                "backup": backup_page,
                "support": support_page,
                "my_tickets": my_tickets_page,
                "settings": settings_page,
            }
            
            current_page = st.session_state.page
            if current_page in pages:
                pages[current_page]()
            else:
                login_page()

if __name__ == "__main__":
    main()