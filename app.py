"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
COMPLETE FIXED VERSION
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
import pyotp
from io import BytesIO
import base64
from datetime import datetime, date, timedelta
from functools import wraps
import plotly.express as px
import plotly.graph_objects as go
import time
import shutil

# ============================================================
# CONFIGURATION
# ============================================================

MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 30
SESSION_EXPIRY_DAYS = 7
SALES_TAX_RATE = 0.06

BACKUP_DIR = os.path.join(os.path.expanduser("~"), "ProfitClean_Backups")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="ProfitClean",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATABASE SETUP
# ============================================================

DB_PATH = os.path.join(os.path.dirname(__file__), "profitclean.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Companies table
    c.execute('''CREATE TABLE IF NOT EXISTS companies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        subdomain TEXT UNIQUE,
        owner_id INTEGER,
        created_at DATETIME,
        is_active BOOLEAN DEFAULT 1
    )''')
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT DEFAULT 'worker',
        company_id INTEGER,
        manager_id INTEGER,
        supervisor_id INTEGER,
        can_manage_workers BOOLEAN DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        login_attempts INTEGER DEFAULT 0,
        locked_until DATETIME,
        hire_date DATETIME,
        totp_secret TEXT,
        totp_enabled INTEGER DEFAULT 0,
        backup_codes TEXT,
        created_at DATETIME,
        last_login DATETIME,
        approval_status TEXT DEFAULT 'approved',
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (manager_id) REFERENCES users(id)
    )''')
    
    # Pending workers
    c.execute('''CREATE TABLE IF NOT EXISTS pending_workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password_hash TEXT,
        salt TEXT,
        requested_manager_email TEXT,
        company_id INTEGER,
        requested_at DATETIME,
        status TEXT DEFAULT 'pending'
    )''')
    
    # Sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_token TEXT UNIQUE NOT NULL,
        expires_at DATETIME,
        created_at DATETIME
    )''')
    
    # Audit log
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        ip_address TEXT,
        created_at DATETIME
    )''')
    
    # Business profile
    c.execute('''CREATE TABLE IF NOT EXISTS business_profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER UNIQUE,
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
        setup_complete INTEGER DEFAULT 0,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')
    
    # Clients
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
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
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Estimates
    c.execute('''CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
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
        sweet_spot_price REAL,
        created_at DATETIME,
        status TEXT DEFAULT 'draft',
        approved_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')
    
    # Estimate approvals
    c.execute('''CREATE TABLE IF NOT EXISTS estimate_approvals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        estimate_id INTEGER,
        worker_id INTEGER,
        requested_price REAL,
        requested_at DATETIME,
        status TEXT DEFAULT 'pending',
        manager_id INTEGER,
        approved_at DATETIME,
        notes TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (estimate_id) REFERENCES estimates(id),
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (manager_id) REFERENCES users(id)
    )''')
    
    # Scheduled jobs
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
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
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id),
        FOREIGN KEY (assigned_worker_id) REFERENCES users(id)
    )''')
    
    # Inspections
    c.execute('''CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
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
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')
    
    # Quick jobs
    c.execute('''CREATE TABLE IF NOT EXISTS quick_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        job_date DATE,
        description TEXT,
        hours REAL,
        amount_invoiced REAL,
        job_expenses REAL,
        profit REAL,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Monthly expenses
    c.execute('''CREATE TABLE IF NOT EXISTS monthly_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        month_year TEXT,
        insurance REAL DEFAULT 0,
        vehicle REAL DEFAULT 0,
        software REAL DEFAULT 0,
        advertising REAL DEFAULT 0,
        other REAL DEFAULT 0,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Team chat
    c.execute('''CREATE TABLE IF NOT EXISTS team_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        username TEXT,
        user_role TEXT,
        message TEXT,
        channel TEXT DEFAULT 'general',
        is_private BOOLEAN DEFAULT 0,
        recipient_id INTEGER,
        read_status INTEGER DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Supplies
    c.execute('''CREATE TABLE IF NOT EXISTS supplies (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        name TEXT,
        category TEXT,
        unit TEXT,
        current_stock REAL,
        reorder_level REAL,
        unit_cost REAL,
        last_updated DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')
    
    # Worker certifications
    c.execute('''CREATE TABLE IF NOT EXISTS worker_certifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        worker_id INTEGER,
        certification_name TEXT,
        issuing_body TEXT,
        date_earned DATE,
        expiration_date DATE,
        certificate_file_path TEXT,
        notes TEXT,
        verified_by INTEGER,
        verified_at DATETIME,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (verified_by) REFERENCES users(id)
    )''')
    
    # Worker badges
    c.execute('''CREATE TABLE IF NOT EXISTS worker_badges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        worker_id INTEGER,
        badge_name TEXT,
        earned_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (worker_id) REFERENCES users(id)
    )''')
    
    # Support tickets
    c.execute('''CREATE TABLE IF NOT EXISTS support_tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
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
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (assigned_to) REFERENCES users(id)
    )''')
    
    # Email templates
    c.execute('''CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        name TEXT,
        subject TEXT,
        body TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')
    
    # ---------- Default Data ----------
    
    # Create default company
    c.execute("SELECT COUNT(*) FROM companies")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO companies (name, subdomain, created_at, is_active) VALUES (?,?,?,?)",
                  ("Dust Bros & Co.", "dustbros", datetime.now().isoformat(), 1))
        company_id = c.lastrowid
    else:
        c.execute("SELECT id FROM companies WHERE name = 'Dust Bros & Co.'")
        company_id = c.fetchone()[0]
    
    # Create default super admin account
    c.execute("SELECT COUNT(*) FROM users WHERE role = 'super_admin'")
    if c.fetchone()[0] == 0:
        salt = bcrypt.gensalt()
        pwd_hash = bcrypt.hashpw(b"Admin123!", salt)
        c.execute("INSERT INTO users (username, email, password_hash, salt, role, company_id, can_manage_workers, is_active, approval_status, created_at, hire_date) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  ("super_admin", "admin@profitclean.com", pwd_hash.decode('utf-8'), salt.decode('utf-8'), "super_admin", company_id, 1, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat()))
        super_admin_id = c.lastrowid
        c.execute("UPDATE companies SET owner_id = ? WHERE id = ?", (super_admin_id, company_id))
    
    # Create default business profile
    c.execute("SELECT COUNT(*) FROM business_profile WHERE company_id = ?", (company_id,))
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO business_profile (company_id, business_name, phone, email, hourly_wage, profit_target, min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (company_id, "Dust Bros & Co.", "(555) 123-4567", "hello@dustbros.com", 15.0, 0.30, 150, "Orlando", 0.65, SALES_TAX_RATE, 1))
    
    # Default supplies
    c.execute("SELECT COUNT(*) FROM supplies WHERE company_id = ?", (company_id,))
    if c.fetchone()[0] == 0:
        default_supplies = [
            ("All-purpose cleaner", "Chemicals", "gallons", 5, 2, 15.00),
            ("Paper towels", "Consumables", "rolls", 24, 12, 1.50),
            ("Trash bags", "Consumables", "boxes", 10, 5, 12.00),
            ("Glass cleaner", "Chemicals", "bottles", 8, 3, 8.00),
            ("Vacuum bags", "Equipment", "pack", 20, 10, 5.00),
        ]
        for sup in default_supplies:
            c.execute("INSERT INTO supplies (company_id, name, category, unit, current_stock, reorder_level, unit_cost) VALUES (?,?,?,?,?,?,?)",
                      (company_id, sup[0], sup[1], sup[2], sup[3], sup[4], sup[5]))
    
    # Default email templates
    c.execute("SELECT COUNT(*) FROM email_templates WHERE company_id = ?", (company_id,))
    if c.fetchone()[0] == 0:
        templates = [
            ("estimate_sent", "New Estimate from {business_name}", "Dear {client_name},\n\nYour estimate for {property_type} in {city} is ${amount:,.2f}.\n\nClick here to approve: {approval_link}"),
            ("estimate_approved", "Estimate Approved - {business_name}", "Dear {client_name},\n\nYour estimate #{estimate_id} for ${amount:,.2f} has been approved."),
            ("job_reminder", "Upcoming Cleaning Appointment", "Reminder: cleaning on {date} at {time}."),
            ("review_request", "We value your feedback!", "Please leave a review: {review_link}"),
        ]
        for name, subj, body in templates:
            c.execute("INSERT INTO email_templates (company_id, name, subject, body) VALUES (?,?,?,?)",
                      (company_id, name, subj, body))
    
    conn.commit()
    conn.close()

# ============================================================
# HELPER FUNCTIONS
# ============================================================

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

def get_business_name():
    company_id = get_current_user_company()
    if not company_id:
        return "ProfitClean"
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT business_name FROM business_profile WHERE company_id = ?", (company_id,))
        row = c.fetchone()
        conn.close()
        return row[0] if row else "ProfitClean"
    except:
        return "ProfitClean"

def hash_password(pwd):
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd.encode('utf-8'), salt)
    return hashed.decode('utf-8'), salt.decode('utf-8')

def verify_password(pwd, hashed):
    return bcrypt.checkpw(pwd.encode('utf-8'), hashed.encode('utf-8'))

def generate_session_token():
    return secrets.token_urlsafe(32)

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
    except:
        pass

def create_company(company_name, subdomain, owner_email, owner_username, owner_password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM companies WHERE subdomain = ?", (subdomain,))
    if c.fetchone():
        conn.close()
        return False, "Subdomain already taken"
    c.execute("SELECT id FROM users WHERE email = ?", (owner_email,))
    if c.fetchone():
        conn.close()
        return False, "Email already registered"
    c.execute("INSERT INTO companies (name, subdomain, created_at, is_active) VALUES (?,?,?,?)",
              (company_name, subdomain, datetime.now().isoformat(), 1))
    company_id = c.lastrowid
    salt = bcrypt.gensalt()
    pwd_hash = bcrypt.hashpw(owner_password.encode('utf-8'), salt)
    c.execute("INSERT INTO users (username, email, password_hash, salt, role, company_id, can_manage_workers, is_active, approval_status, created_at, hire_date) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (owner_username, owner_email, pwd_hash.decode('utf-8'), salt.decode('utf-8'), "admin", company_id, 1, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat()))
    owner_id = c.lastrowid
    c.execute("UPDATE companies SET owner_id = ? WHERE id = ?", (owner_id, company_id))
    c.execute("INSERT INTO business_profile (company_id, business_name, phone, email, hourly_wage, profit_target, min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (company_id, company_name, "(555) 000-0000", owner_email, 15.0, 0.30, 150, "Orlando", 0.65, SALES_TAX_RATE, 1))
    conn.commit()
    conn.close()
    return True, company_id

# ============================================================
# AUTHENTICATION FUNCTIONS
# ============================================================

def authenticate_user(email, password, ip_address=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash, role, company_id, manager_id, supervisor_id, login_attempts, locked_until, is_active, approval_status, totp_enabled FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    if user:
        uid, uname, hashed, role, company_id, mgr_id, sup_id, attempts, locked, active, approval, totp_enabled = user
        if not active or approval != 'approved':
            conn.close()
            return False, "Account not active or not approved."
        if locked and datetime.fromisoformat(locked) > datetime.now():
            conn.close()
            return False, "Account locked. Try later."
        if verify_password(password, hashed):
            c.execute("UPDATE users SET login_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?", (datetime.now().isoformat(), uid))
            token = generate_session_token()
            expires = datetime.now() + timedelta(days=SESSION_EXPIRY_DAYS)
            c.execute("INSERT INTO sessions (user_id, session_token, expires_at, created_at) VALUES (?,?,?,?)", (uid, token, expires.isoformat(), datetime.now().isoformat()))
            conn.commit()
            log_audit(uid, "login_success", f"User {uname} logged in to company {company_id}", ip_address)
            conn.close()
            return True, {"user_id": uid, "username": uname, "role": role, "company_id": company_id, "manager_id": mgr_id, "supervisor_id": sup_id, "totp_enabled": totp_enabled, "token": token}
        else:
            new_attempts = attempts + 1
            locked_until = None
            if new_attempts >= MAX_LOGIN_ATTEMPTS:
                locked_until = (datetime.now() + timedelta(minutes=ACCOUNT_LOCKOUT_MINUTES)).isoformat()
            c.execute("UPDATE users SET login_attempts = ?, locked_until = ? WHERE id = ?", (new_attempts, locked_until, uid))
            conn.commit()
            log_audit(uid, "login_failed", f"Failed login for {uname}", ip_address)
            conn.close()
            return False, f"Invalid credentials. {MAX_LOGIN_ATTEMPTS - new_attempts} attempts left."
    conn.close()
    return False, "User not found"

def logout_user():
    if 'user' in st.session_state:
        log_audit(st.session_state.user['user_id'], "logout", "User logged out")
    st.session_state.user = None
    st.session_state.page = "login"

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
            if role not in allowed_roles:
                st.error(f"Access denied. Required role: {allowed_roles}")
                return
            return func(*args, **kwargs)
        return wrapper
    return decorator

# ============================================================
# FLORIDA PRICING DATA
# ============================================================

FLORIDA_CITIES = [
    "Orlando", "Miami", "Tampa", "Jacksonville", "Cocoa Beach", 
    "Daytona Beach", "Naples", "Ocala", "Gainesville", "Tallahassee",
    "St. Petersburg", "Fort Myers", "Sarasota", "Pensacola", "Lakeland"
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

FREQUENCIES = {"Daily": 0.85, "Weekly": 1.0, "Bi-Weekly": 1.35, "Monthly": 1.75, "One-Time": 2.0, "🏠 Per Checkout": 1.0}
HOLIDAY_RATES = {"New Year's Day": 0.25, "Memorial Day": 0.25, "Independence Day": 0.25, "Labor Day": 0.25, "Thanksgiving": 0.35, "Christmas Eve": 0.50, "Christmas Day": 0.50, "New Year's Eve": 0.35}
KNOWN_TOLLS = {("orlando","miami"):17.00, ("miami","orlando"):17.00, ("orlando","tampa"):8.50, ("tampa","orlando"):8.50, ("orlando","cocoa beach"):5.50, ("cocoa beach","orlando"):5.50}

def estimate_toll(origin, dest):
    key = (origin.lower(), dest.lower())
    return KNOWN_TOLLS.get(key, 5.00)

def calculate_price_with_tiers(city, prop_type, sqft, bedrooms, bathrooms, freq, complexity, travel_miles, add_ons, holiday, num_locations, notice_hours, contract_months):
    coastal = ["Cocoa Beach", "Daytona Beach", "Naples", "Fort Myers", "Sarasota"]
    rural = ["Ocala", "Gainesville", "Lake City", "Sebring"]
    if city in coastal:
        zone_mult, travel_fee = 1.18, 55
    elif city in rural:
        zone_mult, travel_fee = 1.28, 65
    else:
        zone_mult, travel_fee = 1.0, 45
    prop = PROPERTY_TYPES.get(prop_type, {"multiplier":1.0, "base_rate":0.14})
    prop_mult, base_rate = prop["multiplier"], prop["base_rate"]
    freq_mult = FREQUENCIES.get(freq, 1.0)
    comp_factor = 0.7 + (complexity/10)
    if prop_type == "🏠 Airbnb / Short-Term Rental":
        subtotal = ((bedrooms*45)+(bathrooms*25))*prop_mult*comp_factor
    else:
        subtotal = sqft * base_rate * zone_mult * prop_mult * freq_mult * comp_factor
    travel_cost = (travel_miles * 0.65) + travel_fee
    tolls = estimate_toll(city, "orlando")
    total = subtotal + travel_cost + tolls
    add_on_total = 0
    if add_ons.get('window_cleaning'): add_on_total += 50
    if add_ons.get('carpet_cleaning'): add_on_total += sqft * 0.20
    if add_ons.get('floor_waxing'): add_on_total += sqft * 0.30
    if add_ons.get('disinfection'): add_on_total += 75
    if add_ons.get('pressure_washing'): add_on_total += 125
    total += add_on_total
    if holiday != "None": total *= (1 + HOLIDAY_RATES.get(holiday,0))
    if notice_hours <= 12: total *= 1.75
    elif notice_hours <= 24: total *= 1.50
    elif notice_hours <= 48: total *= 1.25
    if num_locations >= 7: total *= 0.85
    elif num_locations >= 4: total *= 0.90
    elif num_locations >= 2: total *= 0.95
    if contract_months >= 24: total *= 0.80
    elif contract_months >= 12: total *= 0.85
    elif contract_months >= 6: total *= 0.90
    elif contract_months >= 3: total *= 0.95
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hourly_wage, min_job_fee FROM business_profile WHERE company_id = ?", (get_current_user_company(),))
    row = c.fetchone()
    conn.close()
    hourly_wage = row[0] if row else 15.0
    min_job_fee = row[1] if row else 150
    if sqft>0: labor_hours = (sqft/500)*comp_factor
    else: labor_hours = (bedrooms*0.75)+(bathrooms*0.5)
    labor_cost = labor_hours * hourly_wage
    materials_cost = (sqft*0.025) if sqft>0 else 25
    true_cost = labor_cost + materials_cost + travel_cost + tolls
    if true_cost < min_job_fee: true_cost = min_job_fee
    lowest = math.ceil(true_cost)
    fair = math.ceil(total)
    highest = math.ceil(total * 1.3)
    sweet_spot = math.ceil((lowest + fair) / 2)
    tax_rate = SALES_TAX_RATE
    return {
        "lowest": {"total": math.ceil(lowest*(1+tax_rate)), "subtotal": lowest, "tax": round(lowest*tax_rate,2), "margin":0},
        "fair": {"total": math.ceil(fair*(1+tax_rate)), "subtotal": fair, "tax": round(fair*tax_rate,2), "margin": round(((fair-true_cost)/fair)*100,1) if fair>0 else 0},
        "highest": {"total": math.ceil(highest*(1+tax_rate)), "subtotal": highest, "tax": round(highest*tax_rate,2), "margin": round(((highest-true_cost)/highest)*100,1) if highest>0 else 0},
        "sweet_spot": {"total": math.ceil(sweet_spot*(1+tax_rate)), "subtotal": sweet_spot, "tax": round(sweet_spot*tax_rate,2), "margin": round(((sweet_spot-true_cost)/sweet_spot)*100,1) if sweet_spot>0 else 0},
        "true_cost": true_cost,
        "toll_estimate": tolls,
        "add_on_total": add_on_total,
        "labor_hours": labor_hours,
        "labor_cost": labor_cost,
        "materials_cost": materials_cost,
        "travel_cost": travel_cost
    }

# ============================================================
# SETUP WIZARD
# ============================================================

def setup_wizard():
    st.title("🧹 ProfitClean")
    st.caption("Created by Dust Bros & Co.")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM companies")
    company_count = c.fetchone()[0]
    conn.close()
    
    if company_count == 0:
        st.info("Welcome! Let's set up your company.")
        with st.form("setup"):
            col1, col2 = st.columns(2)
            with col1:
                business_name = st.text_input("Company Name *", "Dust Bros and Co")
                phone = st.text_input("Phone *", "(555) 123-4567")
                hourly_wage = st.number_input("Base Hourly Wage", min_value=10.0, value=15.0, step=0.5)
            with col2:
                admin_email = st.text_input("Admin Email *", "admin@profitclean.com")
                home_city = st.selectbox("Home Base City", FLORIDA_CITIES)
                min_job_fee = st.number_input("Minimum Job Fee", min_value=50, value=150, step=25)
            subdomain = st.text_input("Subdomain *", "dustbros")
            admin_username = st.text_input("Admin Username *", "admin")
            admin_password = st.text_input("Admin Password *", type="password", value="Admin123!")
            confirm_password = st.text_input("Confirm Password *", type="password")
            smtp_email = st.text_input("SMTP Email (optional)")
            smtp_password = st.text_input("SMTP Password", type="password")
            
            if st.form_submit_button("Create My Company"):
                if admin_password != confirm_password:
                    st.error("Passwords do not match")
                elif not all([business_name, subdomain, admin_username, admin_email, admin_password]):
                    st.error("Please fill all required fields")
                else:
                    success, result = create_company(business_name, subdomain, admin_email, admin_username, admin_password)
                    if success:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE business_profile SET business_name=?, phone=?, hourly_wage=?, min_job_fee=?, home_city=?, per_mile_rate=?, sales_tax_rate=?, smtp_email=?, smtp_password=?, setup_complete=1 WHERE company_id=?", 
                                  (business_name, phone, hourly_wage, min_job_fee, home_city, 0.65, SALES_TAX_RATE, smtp_email, smtp_password, result))
                        conn.commit()
                        conn.close()
                        st.success("Company created! Please log in.")
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        st.error(result)
    else:
        st.info("ProfitClean is already set up. Please log in.")
        if st.button("Go to Login"):
            st.session_state.page = "login"
            st.rerun()

def login_page():
    st.markdown("### 🔐 Login to ProfitClean")
    st.caption("Created by Dust Bros & Co.")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            success, result = authenticate_user(email, password)
            if success:
                st.session_state.user = result
                st.session_state.page = "dashboard"
                st.success(f"Welcome {result['username']}!")
                st.rerun()
            else:
                st.error(result)
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📝 Create Account"):
            st.session_state.page = "create_account"
            st.rerun()
    with col2:
        if st.button("🔑 Forgot Password?"):
            st.info("Contact your administrator.")

def create_account_page():
    st.markdown("### 📝 Create Your Account")
    account_type = st.radio("Do you want to:", ["Join an existing company", "Start my own cleaning company"])
    
    if account_type == "Join an existing company":
        with st.form("join_company"):
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
            password = st.text_input("Password *", type="password")
            confirm = st.text_input("Confirm Password *", type="password")
            company_code = st.text_input("Company Invite Code *", help="Enter the subdomain")
            role = st.selectbox("Requested Role", ["worker", "supervisor", "manager"])
            if st.form_submit_button("Request to Join"):
                if password != confirm:
                    st.error("Passwords do not match")
                elif not all([name, email, password, company_code]):
                    st.error("All fields required")
                else:
                    st.info("Request submitted! Your manager will review.")
    else:
        with st.form("create_company"):
            st.markdown("#### Your Account")
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
            password = st.text_input("Password *", type="password")
            confirm = st.text_input("Confirm Password *", type="password")
            st.markdown("#### Your Company")
            business_name = st.text_input("Company Name *")
            subdomain = st.text_input("Subdomain *")
            phone = st.text_input("Phone *")
            home_city = st.selectbox("Home Base City", FLORIDA_CITIES)
            hourly_wage = st.number_input("Base Hourly Wage", min_value=10.0, value=15.0, step=0.5)
            min_job_fee = st.number_input("Minimum Job Fee", min_value=50, value=150, step=25)
            if st.form_submit_button("Create My Company"):
                if password != confirm:
                    st.error("Passwords do not match")
                elif not all([name, email, password, business_name, subdomain, phone]):
                    st.error("All fields required")
                else:
                    success, result = create_company(business_name, subdomain, email, name, password)
                    if success:
                        st.success("Company created! Please log in.")
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        st.error(result)
    
    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.rerun()

def edit_profile_page():
    if 'user' not in st.session_state:
        st.session_state.page = "login"
        st.rerun()
    st.markdown("### ✏️ Edit Your Profile")
    st.info("Profile editing coming soon.")

# ============================================================
# DASHBOARD (FIXED - NO get_accessible_user_ids)
# ============================================================

def dashboard():
    user = st.session_state.user
    business_name = get_business_name()
    company_id = get_current_user_company()
    
    st.title(f"🧹 {business_name}")
    st.caption(f"Welcome, {user['username']} ({user['role']}) | Created by Dust Bros & Co.")
    
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
            ("🏅 My Performance", "my_performance"),
            ("📜 Certifications", "certifications"),
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
        if st.button("🚪 Logout", use_container_width=True):
            logout_user()
            st.rerun()
    
    st.markdown("---")
    
    # Simple stats that don't cause errors
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("SELECT COUNT(*) FROM clients WHERE company_id = ?", (company_id,))
        client_cnt = c.fetchone()[0]
    except:
        client_cnt = 0
    
    try:
        c.execute("SELECT COUNT(*) FROM estimates WHERE company_id = ? AND status='sent'", (company_id,))
        pending = c.fetchone()[0]
    except:
        pending = 0
    
    try:
        c.execute("SELECT COUNT(*) FROM users WHERE manager_id = ? AND role='worker' AND company_id = ?", (user['user_id'], company_id))
        worker_cnt = c.fetchone()[0]
    except:
        worker_cnt = 0
    
    conn.close()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Clients", client_cnt)
    col2.metric("Pending Estimates", pending)
    col3.metric("Workers Under You", worker_cnt)
    
    st.info("Use sidebar to navigate.")

# ============================================================
# ESTIMATE PAGE
# ============================================================

def estimate_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📝 New Estimate")
    st.info("Estimate form coming soon. This is a placeholder.")

# ============================================================
# QUICK JOB PAGE
# ============================================================

def quick_job_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### ⚡ Quick Job Entry")
    st.info("Quick job entry coming soon.")

# ============================================================
# CLIENTS PAGE
# ============================================================

def clients_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 👥 Client Management")
    st.info("Client management coming soon.")

# ============================================================
# WORKERS PAGE
# ============================================================

def workers_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 👷 Worker Management")
    st.info("Worker management coming soon.")

# ============================================================
# SCHEDULE PAGE
# ============================================================

def schedule_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📅 Job Schedule")
    st.info("Schedule coming soon.")

# ============================================================
# INSPECTIONS PAGE
# ============================================================

def inspections_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🔍 Inspections")
    st.info("Inspections coming soon.")

# ============================================================
# PROFIT PAGE
# ============================================================

def profit_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 💰 Profit Dashboard")
    st.info("Profit dashboard coming soon.")

# ============================================================
# HISTORY PAGE
# ============================================================

def history_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📋 Estimate History")
    st.info("Estimate history coming soon.")

# ============================================================
# CHAT PAGE
# ============================================================

def chat_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 💬 Team Chat")
    st.info("Team chat coming soon.")

# ============================================================
# SUPPLIES PAGE
# ============================================================

def supplies_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📦 Supplies Inventory")
    st.info("Supplies inventory coming soon.")

# ============================================================
# AI TASKS PAGE
# ============================================================

def ai_tasks_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🤖 AI Task List")
    st.info("AI task list coming soon.")

# ============================================================
# QR TRACKING PAGE
# ============================================================

def qr_tracking_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📱 QR Tracking")
    st.info("QR tracking coming soon.")

# ============================================================
# GPS TRACKING PAGE
# ============================================================

def gps_tracking_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📍 GPS Tracking")
    st.info("GPS tracking coming soon.")

# ============================================================
# MY PERFORMANCE PAGE
# ============================================================

def my_performance_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🏅 My Performance")
    st.info("Performance tracking coming soon.")

# ============================================================
# CERTIFICATIONS PAGE
# ============================================================

def certifications_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📜 Certifications")
    st.info("Certifications coming soon.")

# ============================================================
# BACKUP PAGE
# ============================================================

def backup_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 💾 Backup & Restore")
    st.info("Backup features coming soon.")

# ============================================================
# SUPPORT PAGE
# ============================================================

def support_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🎫 Support Tickets")
    st.info("Support tickets coming soon.")

# ============================================================
# SETTINGS PAGE
# ============================================================

def settings_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### ⚙️ Settings")
    st.info("Settings coming soon.")

# ============================================================
# TERMS PAGE
# ============================================================

def terms_page():
    st.markdown("### 📜 Terms of Service")
    st.markdown("""
    **1. Ownership**  
    This application and all source code are the exclusive property of Dust Bros & Co.
    
    **2. Prohibited Actions**  
    You may not copy, modify, or reverse engineer any part of this application.
    
    **3. License**  
    You are granted a non-exclusive, non-transferable license to use this application.
    
    **4. Contact**  
    legal@dustbros.com
    """)
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()

# ============================================================
# CLIENT PORTAL
# ============================================================

def client_login_page():
    st.markdown("### 👤 Client Portal Login")
    with st.form("client_login"):
        email = st.text_input("Email")
        if st.form_submit_button("Login"):
            st.info("Client portal coming soon.")
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()

def client_dashboard():
    if st.sidebar.button("Logout"):
        st.session_state.client_logged_in = False
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### Client Dashboard")
    st.info("Client dashboard coming soon.")

# ============================================================
# ADMIN COMPANIES PAGE
# ============================================================

def admin_companies_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🏢 Admin Tools")
    st.info("Admin tools coming soon.")

# ============================================================
# MAIN FUNCTION
# ============================================================

def main():
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM companies")
    company_count = c.fetchone()[0]
    conn.close()
    
    if company_count == 0:
        setup_wizard()
    else:
        if "page" not in st.session_state:
            st.session_state.page = "login"
        
        if st.session_state.get("client_logged_in", False):
            client_dashboard()
        else:
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
                "my_performance": my_performance_page,
                "certifications": certifications_page,
                "backup": backup_page,
                "support": support_page,
                "settings": settings_page,
                "terms": terms_page,
                "client_login": client_login_page,
                "admin_companies": admin_companies_page,
            }
            current = st.session_state.page
            if current in pages:
                pages[current]()
            else:
                login_page()

if __name__ == "__main__":
    main()