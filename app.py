"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
FINAL VERSION - Part 1 of 3
Includes: multi-tenant, super admin, support staff, troubleshooting tools
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
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import plotly.express as px
import plotly.graph_objects as go
import time
import shutil

# ============================================================
# SECURITY CONFIGURATION
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
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="ProfitClean",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ============================================================
# PWA META TAGS
# ============================================================

st.markdown("""
<link rel="manifest" href="static/manifest.json">
<meta name="theme-color" content="#1E3A5F">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ProfitClean">
""", unsafe_allow_html=True)

# ============================================================
# CUSTOM CSS
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
.internal-card {
    background: #fef3c7;
    border-radius: 16px;
    padding: 1rem;
    border-left: 4px solid #f59e0b;
}
.worker-card {
    background: #f0fdf4;
    border-radius: 16px;
    padding: 1rem;
    border: 1px solid #bbf7d0;
}
.pricing-tier-low { background: #fef3c7; border-radius: 16px; padding: 1rem; text-align: center; }
.pricing-tier-fair { background: #d1fae5; border-radius: 16px; padding: 1rem; text-align: center; }
.pricing-tier-high { background: #ede9fe; border-radius: 16px; padding: 1rem; text-align: center; }

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
""", unsafe_allow_html=True)

# ============================================================
# DATABASE SETUP (MULTI-TENANT + SUPPORT STAFF + JOB_ASSIGNMENTS)
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
        is_active BOOLEAN DEFAULT 1,
        settings_json TEXT
    )''')

    # Users table (with company_id and support_staff flag)
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
        last_raise_date DATETIME,
        raise_recommended_by INTEGER,
        raise_recommended_date DATETIME,
        totp_secret TEXT,
        totp_enabled INTEGER DEFAULT 0,
        backup_codes TEXT,
        created_at DATETIME,
        last_login DATETIME,
        created_ip TEXT,
        approval_status TEXT DEFAULT 'approved',
        approved_by INTEGER,
        approval_date DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (manager_id) REFERENCES users(id),
        FOREIGN KEY (supervisor_id) REFERENCES users(id),
        FOREIGN KEY (approved_by) REFERENCES users(id)
    )''')

    # Pending worker requests
    c.execute('''CREATE TABLE IF NOT EXISTS pending_workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password_hash TEXT,
        salt TEXT,
        requested_manager_email TEXT,
        company_id INTEGER,
        requested_at DATETIME,
        status TEXT DEFAULT 'pending',
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Sessions
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        session_token TEXT UNIQUE NOT NULL,
        expires_at DATETIME,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Audit log (enhanced for troubleshooting)
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        action TEXT,
        details TEXT,
        ip_address TEXT,
        created_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Business profile (per company)
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
        sweet_spot_price REAL,
        created_at DATETIME,
        status TEXT DEFAULT 'draft',
        approved_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (client_id) REFERENCES clients(id)
    )''')

    # Estimate approvals (sweet-spot)
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

    # ============================================================
    # JOB ASSIGNMENTS TABLE (ADDED FOR WORKER PERFORMANCE)
    # ============================================================
    c.execute('''CREATE TABLE IF NOT EXISTS job_assignments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        worker_id INTEGER,
        assigned_by INTEGER,
        assigned_at DATETIME,
        status TEXT DEFAULT 'assigned',
        travel_distance REAL,
        completed_at DATETIME,
        FOREIGN KEY (worker_id) REFERENCES users(id),
        FOREIGN KEY (assigned_by) REFERENCES users(id)
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

    c.execute('''CREATE TABLE IF NOT EXISTS supply_usage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        supply_id INTEGER,
        job_id INTEGER,
        quantity_used REAL,
        used_by INTEGER,
        used_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (supply_id) REFERENCES supplies(id),
        FOREIGN KEY (used_by) REFERENCES users(id)
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

    # Support tickets (for users to report issues)
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

    c.execute('''CREATE TABLE IF NOT EXISTS support_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        ticket_id INTEGER,
        user_id INTEGER,
        message TEXT,
        is_staff BOOLEAN DEFAULT 0,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (ticket_id) REFERENCES support_tickets(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Email templates (per company)
    c.execute('''CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        name TEXT,
        subject TEXT,
        body TEXT,
        FOREIGN KEY (company_id) REFERENCES companies(id)
    )''')

    # Error logs
    c.execute('''CREATE TABLE IF NOT EXISTS error_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_id INTEGER,
        user_id INTEGER,
        error_type TEXT,
        error_message TEXT,
        page_url TEXT,
        stack_trace TEXT,
        created_at DATETIME,
        FOREIGN KEY (company_id) REFERENCES companies(id),
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # ---------- Default Data ----------
    # Create default "Dust Bros & Co." company
    c.execute("SELECT COUNT(*) FROM companies WHERE name = 'Dust Bros & Co.'")
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

    # Create default business profile for Dust Bros & Co.
    c.execute("SELECT COUNT(*) FROM business_profile WHERE company_id = ?", (company_id,))
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO business_profile (company_id, business_name, phone, email, hourly_wage, profit_target, min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                  (company_id, "Dust Bros & Co.", "(555) 123-4567", "hello@dustbros.com", 15.0, 0.30, 150, "Orlando", 0.65, SALES_TAX_RATE, 1))

    # Default supplies for Dust Bros & Co.
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

    # Default email templates for Dust Bros & Co.
    c.execute("SELECT COUNT(*) FROM email_templates WHERE company_id = ?", (company_id,))
    if c.fetchone()[0] == 0:
        templates = [
            ("estimate_sent", "New Estimate from {business_name}", "Dear {client_name},\n\nYour estimate for {property_type} in {city} is ${amount:,.2f}.\n\nClick here to approve: {approval_link}"),
            ("estimate_approved", "Estimate Approved - {business_name}", "Dear {client_name},\n\nYour estimate #{estimate_id} for ${amount:,.2f} has been approved."),
            ("job_reminder", "Upcoming Cleaning Appointment", "Reminder: cleaning on {date} at {time}."),
            ("review_request", "We value your feedback!", "Please leave a review: {review_link}"),
            ("worker_approval", "Your account has been approved", "You can now log in."),
        ]
        for name, subj, body in templates:
            c.execute("INSERT INTO email_templates (company_id, name, subject, body) VALUES (?,?,?,?)",
                      (company_id, name, subj, body))

    conn.commit()
    conn.close()

# ============================================================
# MULTI-TENANT & SUPPORT HELPERS
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
    c.execute("""
        INSERT INTO users (username, email, password_hash, salt, role, company_id, can_manage_workers, is_active, approval_status, created_at, hire_date)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (owner_username, owner_email, pwd_hash.decode('utf-8'), salt.decode('utf-8'), "admin", company_id, 1, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat()))
    owner_id = c.lastrowid
    c.execute("UPDATE companies SET owner_id = ? WHERE id = ?", (owner_id, company_id))
    c.execute("INSERT INTO business_profile (company_id, business_name, phone, email, hourly_wage, profit_target, min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (company_id, company_name, "(555) 000-0000", owner_email, 15.0, 0.30, 150, "Orlando", 0.65, SALES_TAX_RATE, 1))
    conn.commit()
    conn.close()
    return True, company_id

def create_support_staff(email, username, password):
    """Only super admin can call this."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE email = ?", (email,))
    if c.fetchone():
        conn.close()
        return False, "Email already exists"
    salt = bcrypt.gensalt()
    pwd_hash = bcrypt.hashpw(password.encode('utf-8'), salt)
    # Support staff can be attached to the main company (company_id=1) – they will switch using the switcher
    c.execute("INSERT INTO users (username, email, password_hash, salt, role, company_id, can_manage_workers, is_active, approval_status, created_at, hire_date) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (username, email, pwd_hash.decode('utf-8'), salt.decode('utf-8'), "support_staff", 1, 0, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat()))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return True, user_id

# ============================================================
# HIERARCHICAL ACCESS HELPERS (UPDATED FOR SUPPORT STAFF)
# ============================================================

def get_descendant_user_ids(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        WITH RECURSIVE user_tree AS (
            SELECT id, manager_id FROM users WHERE id = ?
            UNION ALL
            SELECT u.id, u.manager_id FROM users u
            INNER JOIN user_tree ut ON u.manager_id = ut.id
        )
        SELECT id FROM user_tree
    """, (user_id,))
    ids = [row[0] for row in c.fetchall()]
    conn.close()
    return ids

def get_accessible_user_ids(current_user_id, current_user_role, current_user_company):
    if current_user_role == 'super_admin':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM users")
        ids = [row[0] for row in c.fetchall()]
        conn.close()
        return ids
    elif current_user_role == 'support_staff':
        # Support staff can see all users (for troubleshooting), but actions are logged.
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM users")
        ids = [row[0] for row in c.fetchall()]
        conn.close()
        return ids
    elif current_user_role == 'admin':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE company_id = ?", (current_user_company,))
        ids = [row[0] for row in c.fetchall()]
        conn.close()
        return ids
    elif current_user_role == 'manager':
        return get_descendant_user_ids(current_user_id)
    elif current_user_role == 'supervisor':
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM users WHERE supervisor_id = ? OR id = ? AND company_id = ?", (current_user_id, current_user_id, current_user_company))
        ids = [row[0] for row in c.fetchall()]
        conn.close()
        return ids
    else:
        return [current_user_id]

def user_belongs_to_hierarchy(current_user_id, target_user_id):
    return target_user_id in get_descendant_user_ids(current_user_id)

# ============================================================
# SECURITY FUNCTIONS
# ============================================================

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

def get_current_user_data():
    if 'user' not in st.session_state:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, role, company_id, manager_id, supervisor_id, hire_date, totp_enabled FROM users WHERE id = ?", (st.session_state.user['user_id'],))
    row = c.fetchone()
    conn.close()
    return row

def get_company_settings():
    company_id = get_current_user_company()
    if not company_id:
        return None
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM business_profile WHERE company_id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    return row

# ============================================================
# EXPORT / IMPORT HELPERS (FOR SUPER ADMIN & SUPPORT STAFF)
# ============================================================

def export_company_data(company_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tables = ["users", "clients", "estimates", "scheduled_jobs", "inspections", "quick_jobs", "monthly_expenses", "supplies", "team_messages", "support_tickets", "worker_certifications", "worker_badges"]
    data = {"company_id": company_id, "export_date": datetime.now().isoformat(), "tables": {}}
    for table in tables:
        try:
            c.execute(f"SELECT * FROM {table} WHERE company_id = ?", (company_id,))
            rows = c.fetchall()
            c.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in c.fetchall()]
            table_data = []
            for row in rows:
                table_data.append(dict(zip(columns, row)))
            data["tables"][table] = table_data
        except:
            data["tables"][table] = []
    conn.close()
    return json.dumps(data, indent=2, default=str)

def import_company_data(dest_company_id, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        for table in data["tables"].keys():
            c.execute(f"DELETE FROM {table} WHERE company_id = ?", (dest_company_id,))
        for table, rows in data["tables"].items():
            if not rows:
                continue
            columns = [col for col in rows[0].keys() if col not in ('id', 'company_id')]
            placeholders = ','.join(['?' for _ in columns])
            for row in rows:
                values = [row[col] for col in columns]
                c.execute(f"INSERT INTO {table} (company_id, {','.join(columns)}) VALUES (?, {placeholders})", [dest_company_id] + values)
        conn.commit()
        return True
    except Exception as e:
        print(f"Import error: {e}")
        return False
    finally:
        conn.close()

# ============================================================
# PART 2: AUTHENTICATION, PRICING, CORE PAGE FUNCTIONS
# (CORRECTED get_worker_performance)
# ============================================================

def create_user(username, email, password, role, company_id, manager_id=None, supervisor_id=None, ip_address=None):
    valid, msg = validate_password_strength(password)
    if not valid:
        return False, msg
    hashed, salt = hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, company_id, manager_id, supervisor_id, can_manage_workers, is_active, approval_status, created_at, hire_date, created_ip)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (username, email, hashed, salt, role, company_id, manager_id, supervisor_id, 1 if role in ['admin','manager','super_admin','support_staff'] else 0, 1, 'approved', datetime.now().isoformat(), datetime.now().isoformat(), ip_address))
        user_id = c.lastrowid
        conn.commit()
        log_audit(user_id, "user_created", f"Created {role} {username} in company {company_id}")
        return True, user_id
    except sqlite3.IntegrityError:
        return False, "Username or email already exists"
    finally:
        conn.close()

def request_worker_account(name, email, password, manager_email, company_id):
    valid, msg = validate_password_strength(password)
    if not valid:
        return False, msg
    hashed, salt = hash_password(password)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO pending_workers (name, email, password_hash, salt, requested_manager_email, company_id, requested_at, status)
            VALUES (?,?,?,?,?,?,?,?)
        """, (name, email, hashed, salt, manager_email, company_id, datetime.now().isoformat(), 'pending'))
        conn.commit()
        log_audit(None, "worker_request", f"Worker {name} requested approval under {manager_email} for company {company_id}")
        return True, "Request submitted. Your manager will review."
    except sqlite3.IntegrityError:
        return False, "Email already in pending queue"
    finally:
        conn.close()

def get_pending_workers_for_manager(manager_email, company_id):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, name, email, requested_at FROM pending_workers WHERE requested_manager_email = ? AND company_id = ? AND status = 'pending'", conn, params=(manager_email, company_id))
    conn.close()
    return df

def approve_worker_request(request_id, manager_id, company_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, email, password_hash, salt FROM pending_workers WHERE id = ? AND company_id = ?", (request_id, company_id))
    row = c.fetchone()
    if row:
        name, email, pwd_hash, salt = row
        c.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, company_id, manager_id, can_manage_workers, is_active, approval_status, created_at, hire_date, approved_by, approval_date)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (name, email, pwd_hash, salt, "worker", company_id, manager_id, 0, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat(), manager_id, datetime.now().isoformat()))
        user_id = c.lastrowid
        c.execute("DELETE FROM pending_workers WHERE id = ?", (request_id,))
        conn.commit()
        log_audit(manager_id, "worker_approved", f"Approved worker {name} (ID {user_id}) for company {company_id}")
        return True, user_id
    conn.close()
    return False, None

def deny_worker_request(request_id, company_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM pending_workers WHERE id = ? AND company_id = ?", (request_id, company_id))
    conn.commit()
    conn.close()
    return True

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

# ----------------------------- 2FA (TOTP) -----------------------------
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

# ----------------------------- FLORIDA PRICING -----------------------------
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

# ----------------------------- WORKER / CLIENT / JOB HELPERS -----------------------------
def get_all_workers_for_manager(manager_id, company_id):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, username, email, hire_date, is_active FROM users WHERE manager_id = ? AND company_id = ? AND role = 'worker'", conn, params=(manager_id, company_id))
    conn.close()
    return df

def get_all_workers_for_supervisor(supervisor_id, company_id):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, username, email, hire_date, is_active FROM users WHERE supervisor_id = ? AND company_id = ? AND role = 'worker'", conn, params=(supervisor_id, company_id))
    conn.close()
    return df

def get_all_clients():
    company_id = get_current_user_company()
    uid = st.session_state.user['user_id']
    role = st.session_state.user['role']
    accessible = get_accessible_user_ids(uid, role, company_id)
    placeholders = ','.join(['?' for _ in accessible])
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM clients WHERE company_id = ? AND user_id IN ({placeholders}) ORDER BY business_name", conn, params=[company_id] + accessible)
    conn.close()
    return df

def add_client(business, contact, phone, email, address, city, state, zipc, lat, lon, notes):
    company_id = get_current_user_company()
    uid = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO clients (company_id, user_id, business_name, contact_name, phone, email, address, city, state, zip, lat, lon, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (company_id, uid, business, contact, phone, email, address, city, state, zipc, lat, lon, notes, datetime.now().isoformat(), datetime.now().isoformat()))
    cid = c.lastrowid
    conn.commit()
    conn.close()
    return cid

def update_client(cid, business, contact, phone, email, address, city, state, zipc, lat, lon, notes):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE clients SET business_name=?, contact_name=?, phone=?, email=?, address=?, city=?, state=?, zip=?, lat=?, lon=?, notes=?, updated_at=? WHERE id=?",
              (business, contact, phone, email, address, city, state, zipc, lat, lon, notes, datetime.now().isoformat(), cid))
    conn.commit()
    conn.close()

def delete_client(cid):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM clients WHERE id = ?", (cid,))
    conn.commit()
    conn.close()

def schedule_job(client_id, client_name, client_email, estimate_id, worker_id, date, time_slot, notes=""):
    company_id = get_current_user_company()
    uid = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO scheduled_jobs (company_id, user_id, client_id, client_name, client_email, estimate_id, assigned_worker_id, scheduled_date, scheduled_time, notes, status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (company_id, uid, client_id, client_name, client_email, estimate_id, worker_id, date.isoformat(), time_slot, notes, "scheduled"))
    job_id = c.lastrowid
    conn.commit()
    conn.close()
    return job_id

def update_job_status(job_id, status):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if status == "completed":
        c.execute("UPDATE scheduled_jobs SET status = ?, completed_at = ? WHERE id = ?", (status, datetime.now().isoformat(), job_id))
    else:
        c.execute("UPDATE scheduled_jobs SET status = ? WHERE id = ?", (status, job_id))
    conn.commit()
    conn.close()

def get_scheduled_jobs(date_filter=None, status_filter=None):
    company_id = get_current_user_company()
    uid = st.session_state.user['user_id']
    role = st.session_state.user['role']
    accessible = get_accessible_user_ids(uid, role, company_id)
    placeholders = ','.join(['?' for _ in accessible])
    conn = sqlite3.connect(DB_PATH)
    query = f"SELECT * FROM scheduled_jobs WHERE company_id = ? AND user_id IN ({placeholders})"
    params = [company_id] + accessible
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

def get_upcoming_jobs(days=7):
    company_id = get_current_user_company()
    uid = st.session_state.user['user_id']
    role = st.session_state.user['role']
    accessible = get_accessible_user_ids(uid, role, company_id)
    placeholders = ','.join(['?' for _ in accessible])
    today = datetime.now().date().isoformat()
    future = (datetime.now().date() + timedelta(days=days)).isoformat()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT * FROM scheduled_jobs WHERE company_id = ? AND user_id IN ({placeholders}) AND scheduled_date BETWEEN ? AND ? AND status = 'scheduled' ORDER BY scheduled_date", conn, params=[company_id] + accessible + [today, future])
    conn.close()
    return df

# ----------------------------- PERFORMANCE & BADGES (CORRECTED) -----------------------------
def get_worker_performance(worker_id):
    """Get worker's performance metrics from scheduled_jobs and quick_jobs"""
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Count completed scheduled jobs for this worker
    c.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE assigned_worker_id = ? AND company_id = ? AND status = 'completed'", (worker_id, company_id))
    jobs = c.fetchone()[0]
    # Get profit from quick_jobs
    c.execute("SELECT SUM(profit) FROM quick_jobs WHERE user_id = ? AND company_id = ?", (worker_id, company_id))
    profit = c.fetchone()[0] or 0
    # Get hours from quick_jobs
    c.execute("SELECT SUM(hours) FROM quick_jobs WHERE user_id = ? AND company_id = ?", (worker_id, company_id))
    hours = c.fetchone()[0] or 0
    conn.close()
    return jobs, profit, hours

def award_badge(worker_id, badge_name):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM worker_badges WHERE worker_id = ? AND badge_name = ? AND company_id = ?", (worker_id, badge_name, company_id))
    if not c.fetchone():
        c.execute("INSERT INTO worker_badges (company_id, worker_id, badge_name, earned_at) VALUES (?,?,?,?)", (company_id, worker_id, badge_name, datetime.now().isoformat()))
        conn.commit()
    conn.close()

def update_worker_badges(worker_id):
    jobs, profit, hours = get_worker_performance(worker_id)
    if jobs >= 1: award_badge(worker_id, "Rookie")
    if jobs >= 10: award_badge(worker_id, "10 Jobs")
    if jobs >= 50: award_badge(worker_id, "50 Jobs")
    if jobs >= 100: award_badge(worker_id, "100 Jobs")
    if hours >= 100: award_badge(worker_id, "100 Hours")
    if hours >= 500: award_badge(worker_id, "500 Hours")
    if profit >= 1000: award_badge(worker_id, "$1k Profit")
    if profit >= 5000: award_badge(worker_id, "$5k Profit")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hire_date FROM users WHERE id = ?", (worker_id,))
    row = c.fetchone()
    if row:
        hire = datetime.fromisoformat(row[0])
        years = (datetime.now() - hire).days / 365.25
        if years >= 1: award_badge(worker_id, "1 Year")
        if years >= 2: award_badge(worker_id, "2 Years")
    conn.close()

def get_worker_badges(worker_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT badge_name, earned_at FROM worker_badges WHERE worker_id = ? AND company_id = ? ORDER BY earned_at", conn, params=(worker_id, company_id))
    conn.close()
    return df

# ----------------------------- SWEET SPOT APPROVAL -----------------------------
def request_sweet_spot_approval(estimate_id, worker_id, requested_price, manager_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO estimate_approvals (company_id, estimate_id, worker_id, requested_price, requested_at, status, manager_id) VALUES (?,?,?,?,?,?,?)",
              (company_id, estimate_id, worker_id, requested_price, datetime.now().isoformat(), 'pending', manager_id))
    conn.commit()
    conn.close()
    log_audit(worker_id, "sweet_spot_request", f"Requested approval for estimate {estimate_id} in company {company_id}")

def get_pending_sweet_spot_requests(manager_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT ea.id, ea.estimate_id, u.username as worker_name, ea.requested_price, ea.requested_at, e.client_name, e.city
        FROM estimate_approvals ea
        JOIN users u ON ea.worker_id = u.id
        JOIN estimates e ON ea.estimate_id = e.id
        WHERE ea.status = 'pending' AND ea.manager_id = ? AND ea.company_id = ?
        ORDER BY ea.requested_at
    """, conn, params=(manager_id, company_id))
    conn.close()
    return df

def approve_sweet_spot(request_id, manager_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT estimate_id, requested_price FROM estimate_approvals WHERE id = ? AND company_id = ?", (request_id, company_id))
    row = c.fetchone()
    if row:
        est_id, price = row
        c.execute("UPDATE estimates SET estimated_price = ?, status = 'sent' WHERE id = ? AND company_id = ?", (price, est_id, company_id))
        c.execute("UPDATE estimate_approvals SET status = 'approved', approved_at = ? WHERE id = ?", (datetime.now().isoformat(), request_id))
        conn.commit()
        log_audit(manager_id, "sweet_spot_approved", f"Approved sweet spot for estimate {est_id} in company {company_id}")
        conn.close()
        return True
    conn.close()
    return False

def reject_sweet_spot(request_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE estimate_approvals SET status = 'rejected' WHERE id = ? AND company_id = ?", (request_id, company_id))
    conn.commit()
    conn.close()
    return True

# ----------------------------- CERTIFICATION FUNCTIONS -----------------------------
def add_certification(worker_id, name, issuer, date_earned, expiration, file, notes):
    company_id = get_current_user_company()
    file_path = None
    if file:
        ext = file.name.split('.')[-1]
        filename = f"cert_{worker_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, filename)
        with open(file_path, 'wb') as f:
            f.write(file.getbuffer())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO worker_certifications (company_id, worker_id, certification_name, issuing_body, date_earned, expiration_date, certificate_file_path, notes, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (company_id, worker_id, name, issuer, date_earned, expiration, file_path, notes, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_certifications_for_worker(worker_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM worker_certifications WHERE worker_id = ? AND company_id = ? ORDER BY date_earned DESC", conn, params=(worker_id, company_id))
    conn.close()
    return df

def verify_certification(cert_id, verifier_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE worker_certifications SET verified_by = ?, verified_at = ? WHERE id = ? AND company_id = ?", (verifier_id, datetime.now().isoformat(), cert_id, company_id))
    conn.commit()
    conn.close()

# ============================================================
# PAGE FUNCTIONS (SETUP, LOGIN, DASHBOARD, ESTIMATE, QUICK, CLIENTS, WORKERS, SCHEDULE)
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
            subdomain = st.text_input("Subdomain *", "dustbros", help="Will be used for your company URL")
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
                if result.get('totp_enabled'):
                    st.session_state.pending_2fa_user = result
                    st.session_state.page = "two_factor"
                    st.rerun()
                else:
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
            st.info("Contact your company administrator.")

def two_factor_page():
    st.markdown("### 🔐 Two‑Factor Authentication")
    st.caption("Enter the code from your authenticator app")
    user = st.session_state.pending_2fa_user
    if not user:
        st.session_state.page = "login"
        st.rerun()
    with st.form("2fa"):
        code = st.text_input("Authentication Code")
        if st.form_submit_button("Verify"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT totp_secret FROM users WHERE id = ?", (user['user_id'],))
            row = c.fetchone()
            conn.close()
            if row and verify_totp(row[0], code):
                st.session_state.user = user
                del st.session_state.pending_2fa_user
                st.session_state.page = "dashboard"
                st.success("2FA verified!")
                st.rerun()
            else:
                st.error("Invalid code. Try again.")

def create_account_page():
    st.markdown("### 📝 Create Your Account")
    st.caption("Join an existing company or start your own")
    account_type = st.radio("Do you want to:", ["Join an existing company", "Start my own cleaning company"])
    if account_type == "Join an existing company":
        with st.form("join_company"):
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
            password = st.text_input("Password *", type="password")
            confirm = st.text_input("Confirm Password *", type="password")
            company_code = st.text_input("Company Invite Code *", help="Enter the subdomain or invite code provided by your manager")
            role = st.selectbox("Requested Role", ["worker", "supervisor", "manager"])
            if st.form_submit_button("Request to Join"):
                if password != confirm:
                    st.error("Passwords do not match")
                elif not all([name, email, password, company_code]):
                    st.error("All fields required")
                else:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("SELECT id FROM companies WHERE subdomain = ? AND is_active = 1", (company_code,))
                    company = c.fetchone()
                    conn.close()
                    if company:
                        company_id = company[0]
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("SELECT email FROM users WHERE company_id = ? AND role = 'manager' LIMIT 1", (company_id,))
                        manager_row = c.fetchone()
                        conn.close()
                        manager_email = manager_row[0] if manager_row else None
                        if manager_email:
                            success, msg = request_worker_account(name, email, password, manager_email, company_id)
                            if success:
                                st.success(msg)
                                st.info("Your manager will review and approve your account.")
                                st.session_state.page = "login"
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.error("No manager found for this company. Please contact the company directly.")
                    else:
                        st.error("Invalid company invite code")
    else:
        with st.form("create_company"):
            st.markdown("#### Your Account")
            name = st.text_input("Full Name *")
            email = st.text_input("Email *")
            password = st.text_input("Password *", type="password")
            confirm = st.text_input("Confirm Password *", type="password")
            st.markdown("#### Your Company")
            business_name = st.text_input("Company Name *")
            subdomain = st.text_input("Subdomain *", help="This will be your unique URL: yourcompany.profitclean.com")
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
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE business_profile SET business_name=?, phone=?, hourly_wage=?, min_job_fee=?, home_city=?, per_mile_rate=?, sales_tax_rate=?, setup_complete=1 WHERE company_id=?", 
                                  (business_name, phone, hourly_wage, min_job_fee, home_city, 0.65, SALES_TAX_RATE, result))
                        conn.commit()
                        conn.close()
                        st.success("Company created successfully! Please log in.")
                        st.session_state.page = "login"
                        st.rerun()
                    else:
                        st.error(result)
    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.rerun()

def setup_2fa_page():
    st.markdown("### 🔐 Set Up Two‑Factor Authentication")
    secret = st.session_state.get("totp_secret")
    email = st.session_state.get("totp_email")
    if not secret:
        st.error("Session expired. Try again.")
        st.session_state.page = "edit_profile"
        st.rerun()
    uri = get_totp_uri(secret, email)
    qr = qrcode.make(uri)
    buffered = BytesIO()
    qr.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    st.image(f"data:image/png;base64,{img_str}", width=200)
    st.code(secret)
    st.markdown("Scan the QR code with Google Authenticator or Authy.")
    code = st.text_input("Enter the 6‑digit code from the app")
    if st.button("Verify and Enable"):
        if verify_totp(secret, code):
            backup_codes, hashed_codes = generate_backup_codes(8)
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET totp_secret = ?, totp_enabled = 1, backup_codes = ? WHERE id = ?", (secret, json.dumps(hashed_codes), st.session_state.user['user_id']))
            conn.commit()
            conn.close()
            st.success("2FA enabled! Save your backup codes:")
            st.code("\n".join(backup_codes))
            st.warning("Store these codes safely. They will not be shown again.")
            st.session_state.page = "edit_profile"
            st.rerun()
        else:
            st.error("Invalid code")

def edit_profile_page():
    if 'user' not in st.session_state:
        st.session_state.page = "login"
        st.rerun()
    st.markdown("### ✏️ Edit Your Profile")
    user_data = get_current_user_data()
    if not user_data:
        st.error("User not found")
        return
    uid, username, email, role, company_id, mgr_id, sup_id, hire_date, totp_enabled = user_data
    with st.form("edit_profile_form"):
        new_username = st.text_input("Username", username)
        new_email = st.text_input("Email", email)
        st.text_input("Role", role, disabled=True)
        st.text_input("Company ID", str(company_id) if company_id else "N/A", disabled=True)
        st.text_input("Hire Date", hire_date[:10] if hire_date else "N/A", disabled=True)
        st.markdown("#### Change Password")
        cur_pwd = st.text_input("Current Password", type="password")
        new_pwd = st.text_input("New Password", type="password")
        confirm_pwd = st.text_input("Confirm New Password", type="password")
        if st.form_submit_button("Save Profile Changes"):
            updates = []
            params = []
            if new_username != username:
                updates.append("username = ?")
                params.append(new_username)
            if new_email != email:
                updates.append("email = ?")
                params.append(new_email)
            if new_pwd:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT password_hash FROM users WHERE id = ?", (uid,))
                row = c.fetchone()
                conn.close()
                if not row or not verify_password(cur_pwd, row[0]):
                    st.error("Current password is incorrect")
                elif new_pwd != confirm_pwd:
                    st.error("New passwords do not match")
                else:
                    valid, msg = validate_password_strength(new_pwd)
                    if not valid:
                        st.error(msg)
                    else:
                        hashed, salt = hash_password(new_pwd)
                        updates.append("password_hash = ?")
                        updates.append("salt = ?")
                        params.extend([hashed, salt])
            if updates:
                params.append(uid)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
                conn.commit()
                conn.close()
                st.success("Profile updated")
                st.rerun()
    st.markdown("---")
    st.markdown("#### Two‑Factor Authentication")
    if totp_enabled:
        st.success("2FA is ENABLED")
        if st.button("Disable 2FA"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE users SET totp_enabled = 0, totp_secret = NULL WHERE id = ?", (uid,))
            conn.commit()
            conn.close()
            st.success("2FA disabled")
            st.rerun()
    else:
        st.info("2FA is disabled. You can enable it.")
        if st.button("Enable 2FA"):
            secret = generate_totp_secret()
            uri = get_totp_uri(secret, email)
            st.session_state.totp_secret = secret
            st.session_state.totp_email = email
            st.session_state.page = "setup_2fa"
            st.rerun()
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

def dashboard():
    user = st.session_state.user
    business_name = get_business_name()
    company_id = get_current_user_company()
    st.title(f"🧹 {business_name}")
    st.caption(f"Welcome, {user['username']} ({user['role']}) | Company ID: {company_id} | Created by Dust Bros & Co.")
    if st.session_state.user.get('role_override'):
        st.warning(f"You are currently viewing data for company ID: {st.session_state.user['company_id']} (override active).")
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
        if user['role'] in ['super_admin', 'support_staff']:
            menu_items.append(("🔧 Admin Tools", "admin_companies"))
        for label, page in menu_items:
            if st.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        st.markdown("---")
        with st.expander("💬 Need Help?"):
            if st.button("📝 Report Issue"):
                st.session_state.page = "support"
                st.rerun()
        st.markdown("---")
        if st.button("🚪 Logout"):
            logout_user()
            st.rerun()
    st.markdown("---")
    accessible = get_accessible_user_ids(user['user_id'], user['role'], company_id)
    placeholders = ','.join(['?' for _ in accessible])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM clients WHERE company_id = ? AND user_id IN ({placeholders})", [company_id] + accessible)
    client_cnt = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM estimates WHERE company_id = ? AND user_id IN ({placeholders}) AND status='sent'", [company_id] + accessible)
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE manager_id = ? AND role='worker' AND company_id = ?", (user['user_id'], company_id))
    worker_cnt = c.fetchone()[0]
    conn.close()
    col1, col2, col3 = st.columns(3)
    col1.metric("Clients", client_cnt)
    col2.metric("Pending Estimates", pending)
    col3.metric("Workers Under You", worker_cnt)
    st.info("Use sidebar to navigate.")

def estimate_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📝 New Estimate")
    company_id = get_current_user_company()
    city = st.selectbox("City", FLORIDA_CITIES)
    prop = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()))
    freq = st.selectbox("Frequency", list(FREQUENCIES.keys()))
    complexity = st.slider("Complexity (1-10)", 1, 10, 3)
    is_airbnb = prop == "🏠 Airbnb / Short-Term Rental"
    if is_airbnb:
        bedrooms = st.number_input("Bedrooms", 0, 10, 2)
        bathrooms = st.number_input("Bathrooms", 0, 8, 1)
        sqft = 0
    else:
        sqft = st.number_input("Square Feet", 100, 100000, 2000)
        bedrooms = bathrooms = 0
    travel_miles = st.number_input("Travel Miles", 0, 200, 25)
    client_name = st.text_input("Client Name")
    client_email = st.text_input("Client Email")
    with st.expander("Internal Costs (Staff Only)"):
        hours_est = st.number_input("Est. Hours", 0.5, 20.0, 3.0)
        materials_est = st.number_input("Materials $", 0, 500, 35)
    st.markdown("### Add‑Ons")
    col1, col2, col3 = st.columns(3)
    add_window = col1.checkbox("Window Cleaning (+$50)")
    add_carpet = col2.checkbox("Carpet Cleaning (+$0.20/sq ft)")
    add_floor = col3.checkbox("Floor Waxing (+$0.30/sq ft)")
    add_disinfection = col1.checkbox("Disinfection (+$75)")
    add_pressure = col2.checkbox("Pressure Washing (+$125)")
    add_ons = {'window_cleaning':add_window, 'carpet_cleaning':add_carpet, 'floor_waxing':add_floor, 'disinfection':add_disinfection, 'pressure_washing':add_pressure}
    st.markdown("### Modifiers")
    col1, col2 = st.columns(2)
    holiday = col1.selectbox("Holiday", ["None"]+list(HOLIDAY_RATES.keys()))
    emergency = col1.selectbox("Emergency", ["Standard (3+ days)","2 days (+25%)","Next day (+50%)","Same day (+75%)"])
    emap = {"Standard (3+ days)":72, "2 days (+25%)":48, "Next day (+50%)":24, "Same day (+75%)":12}
    notice = emap[emergency]
    num_locations = col2.number_input("Number of Locations", 1, 20, 1)
    contract = col2.selectbox("Contract", ["No contract","3 months (-5%)","6 months (-10%)","12 months (-15%)","24+ months (-20%)"])
    cmap = {"No contract":0,"3 months (-5%)":3,"6 months (-10%)":6,"12 months (-15%)":12,"24+ months (-20%)":24}
    contract_months = cmap[contract]
    result = calculate_price_with_tiers(city, prop, sqft, bedrooms, bathrooms, freq, complexity, travel_miles, add_ons, holiday, num_locations, notice, contract_months)
    st.markdown("### 💰 Pricing Options")
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f'<div class="pricing-tier-low">🔥 LOWEST<br>${result["lowest"]["total"]}<br>0% margin</div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="pricing-tier-fair">💰 FAIR<br>${result["fair"]["total"]}<br>{result["fair"]["margin"]}% margin</div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="pricing-tier-high">⭐ HIGHEST<br>${result["highest"]["total"]}<br>{result["highest"]["margin"]}% margin</div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="pricing-tier-fair">🎯 SWEET SPOT<br>${result["sweet_spot"]["total"]}<br>{result["sweet_spot"]["margin"]}% margin</div>', unsafe_allow_html=True)
    with st.expander("Internal Cost Breakdown"):
        st.write(f"True cost: ${result['true_cost']:.2f}")
    if st.button("Save as Draft (Fair Market)"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""INSERT INTO estimates (company_id, user_id, client_name, client_email, city, property_type, square_feet, bedrooms, bathrooms, frequency, complexity, travel_miles, toll_cost, add_on_window, add_on_carpet, add_on_floor, add_on_disinfection, add_on_pressure, subtotal, tax, estimated_price, lowest_price, fair_price, highest_price, sweet_spot_price, created_at, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (company_id, st.session_state.user['user_id'], client_name, client_email, city, prop, sqft, bedrooms, bathrooms, freq, complexity, travel_miles, result['toll_estimate'], 1 if add_window else 0, 1 if add_carpet else 0, 1 if add_floor else 0, 1 if add_disinfection else 0, 1 if add_pressure else 0, result['fair']['subtotal'], result['fair']['tax'], result['fair']['total'], result['lowest']['total'], result['fair']['total'], result['highest']['total'], result['sweet_spot']['total'], datetime.now().isoformat(), "draft"))
        conn.commit()
        conn.close()
        st.success("Estimate saved as draft.")
    if st.session_state.user['role'] == 'worker':
        manager_id = st.session_state.user.get('manager_id')
        if manager_id:
            if st.button("📨 Request Sweet‑Spot Approval"):
                st.warning("Please save the estimate first, then request approval from the Workers page.")
        else:
            st.info("You don't have a manager assigned.")

def quick_job_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### ⚡ Quick Job Entry")
    company_id = get_current_user_company()
    with st.form("quick"):
        date = st.date_input("Date", datetime.now())
        desc = st.text_input("Description")
        hours = st.number_input("Hours", 0.5, 24.0, 2.0)
        amount = st.number_input("Amount Invoiced", 0.0, 10000.0, 350.0)
        expenses = st.number_input("Expenses", 0.0, 500.0, 25.0)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT hourly_wage FROM business_profile WHERE company_id = ?", (company_id,))
        row = c.fetchone()
        conn.close()
        hourly = row[0] if row else 15.0
        profit = amount - expenses - (hours * hourly)
        st.metric("Estimated Profit", f"${profit:.2f}")
        if st.form_submit_button("Save"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO quick_jobs (company_id, user_id, job_date, description, hours, amount_invoiced, job_expenses, profit, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (company_id, st.session_state.user['user_id'], date.isoformat(), desc, hours, amount, expenses, profit, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            update_worker_badges(st.session_state.user['user_id'])
            st.success("Quick job saved!")
            st.rerun()

def clients_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 👥 Client Management")
    if st.button("📥 Export CSV"):
        df = get_all_clients()
        if not df.empty:
            csv = df.to_csv(index=False)
            st.download_button("Download", csv, "clients.csv", "text/csv")
    with st.expander("➕ Add Client"):
        with st.form("add_client"):
            business = st.text_input("Business Name *")
            contact = st.text_input("Contact Name")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            address = st.text_input("Address")
            city = st.text_input("City")
            state = st.text_input("State", "FL")
            zipc = st.text_input("Zip")
            lat = st.number_input("Latitude", 0.0, format="%.6f")
            lon = st.number_input("Longitude", 0.0, format="%.6f")
            notes = st.text_area("Notes")
            if st.form_submit_button("Save"):
                if business:
                    add_client(business, contact, phone, email, address, city, state, zipc, lat, lon, notes)
                    st.success("Client added")
                    st.rerun()
                else:
                    st.error("Business name required")
    df = get_all_clients()
    if df.empty:
        st.info("No clients")
    else:
        for _, row in df.iterrows():
            with st.expander(f"🏢 {row['business_name']}"):
                st.write(f"Contact: {row['contact_name'] or 'N/A'}, Phone: {row['phone'] or 'N/A'}, Email: {row['email'] or 'N/A'}")
                st.write(f"Address: {row['address'] or 'N/A'}, {row['city'] or 'N/A'}, {row['state']} {row['zip']}")
                if st.button(f"Delete", key=f"del_{row['id']}"):
                    delete_client(row['id'])
                    st.rerun()

def workers_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 👷 Worker Management")
    user = st.session_state.user
    company_id = get_current_user_company()
    if user['role'] == 'super_admin':
        conn = sqlite3.connect(DB_PATH)
        workers = pd.read_sql_query("SELECT id, username, email, company_id, manager_id, supervisor_id, role, is_active, hire_date FROM users WHERE role IN ('worker','supervisor','manager')", conn)
        conn.close()
        st.subheader("All Workers (All Companies)")
        st.dataframe(workers)
    elif user['role'] == 'support_staff':
        conn = sqlite3.connect(DB_PATH)
        workers = pd.read_sql_query("SELECT id, username, email, company_id, manager_id, supervisor_id, role, is_active, hire_date FROM users", conn)
        conn.close()
        st.subheader("All Workers (Troubleshooting View)")
        st.dataframe(workers)
        st.info("Support staff can view all users but cannot modify them here. Use Admin Tools to switch company.")
    elif user['role'] == 'admin':
        conn = sqlite3.connect(DB_PATH)
        workers = pd.read_sql_query("SELECT id, username, email, manager_id, supervisor_id, role, is_active, hire_date FROM users WHERE company_id = ?", conn, params=(company_id,))
        conn.close()
        st.subheader("All Users in Your Company")
        st.dataframe(workers)
        with st.expander("➕ Create New Manager"):
            with st.form("create_manager"):
                name = st.text_input("Name")
                email = st.text_input("Email")
                temp_password = st.text_input("Temporary Password", type="password")
                if st.form_submit_button("Create Manager"):
                    if name and email and temp_password:
                        success, msg = create_user(name, email, temp_password, "manager", company_id, manager_id=user['user_id'])
                        if success:
                            st.success(f"Manager {name} created")
                            st.rerun()
                        else:
                            st.error(msg)
                    else:
                        st.error("All fields required")
    else:  # manager
        st.subheader("Your Workers")
        workers = get_all_workers_for_manager(user['user_id'], company_id)
        st.dataframe(workers)
        st.subheader("Invite New Worker")
        with st.form("invite"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            temp_password = st.text_input("Temporary Password", type="password")
            if st.form_submit_button("Invite"):
                if name and email and temp_password:
                    success, msg = create_user(name, email, temp_password, "worker", company_id, manager_id=user['user_id'])
                    if success:
                        st.success(f"Worker {name} created")
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    st.error("All fields required")
        st.subheader("Pending Worker Requests")
        pending = get_pending_workers_for_manager(st.session_state.user.get('email', ''), company_id)
        if not pending.empty:
            for _, req in pending.iterrows():
                st.write(f"{req['name']} ({req['email']}) requested on {req['requested_at']}")
                col1, col2 = st.columns(2)
                if col1.button(f"Approve", key=f"app_{req['id']}"):
                    approve_worker_request(req['id'], user['user_id'], company_id)
                    st.success("Approved")
                    st.rerun()
                if col2.button(f"Deny", key=f"den_{req['id']}"):
                    deny_worker_request(req['id'], company_id)
                    st.success("Denied")
                    st.rerun()
        else:
            st.info("No pending requests")
        st.subheader("Sweet‑Spot Approval Requests")
        sweet_requests = get_pending_sweet_spot_requests(user['user_id'])
        if not sweet_requests.empty:
            for _, req in sweet_requests.iterrows():
                st.write(f"Estimate #{req['estimate_id']} – {req['client_name']} ({req['city']}) requested by {req['worker_name']} at ${req['requested_price']:.2f}")
                col1, col2 = st.columns(2)
                if col1.button(f"Approve", key=f"sapp_{req['id']}"):
                    approve_sweet_spot(req['id'], user['user_id'])
                    st.success("Approved")
                    st.rerun()
                if col2.button(f"Reject", key=f"srej_{req['id']}"):
                    reject_sweet_spot(req['id'])
                    st.success("Rejected")
                    st.rerun()
        else:
            st.info("No sweet‑spot requests pending")

def schedule_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📅 Job Schedule")
    company_id = get_current_user_company()
    view_date = st.date_input("Date", datetime.now())
    status_filter = st.selectbox("Status", ["All","scheduled","completed","cancelled"])
    df = get_scheduled_jobs(date_filter=view_date, status_filter=status_filter)
    if df.empty:
        st.info("No jobs")
    else:
        st.dataframe(df)
    with st.expander("➕ Add Job"):
        clients_df = get_all_clients()
        client_options = ["Select..."] + clients_df['business_name'].tolist()
        client = st.selectbox("Client", client_options)
        accessible_workers = get_accessible_user_ids(st.session_state.user['user_id'], st.session_state.user['role'], company_id)
        placeholders = ','.join(['?' for _ in accessible_workers])
        conn = sqlite3.connect(DB_PATH)
        workers_df = pd.read_sql_query(f"SELECT id, username FROM users WHERE role='worker' AND company_id = ? AND id IN ({placeholders})", conn, params=[company_id] + accessible_workers)
        conn.close()
        worker_options = ["Unassigned"] + workers_df['username'].tolist()
        worker = st.selectbox("Worker", worker_options)
        time_slot = st.selectbox("Time", ["8:00 AM","9:00 AM","10:00 AM","11:00 AM","12:00 PM","1:00 PM","2:00 PM","3:00 PM","4:00 PM"])
        if st.button("Schedule"):
            if client != "Select...":
                client_id = clients_df[clients_df['business_name']==client]['id'].values[0]
                worker_id = None if worker=="Unassigned" else workers_df[workers_df['username']==worker]['id'].values[0]
                schedule_job(client_id, client, "", None, worker_id, view_date, time_slot)
                st.success("Scheduled")
                st.rerun()

# ============================================================
# PART 3: REMAINING PAGE FUNCTIONS & MAIN ROUTING
# INSPECTIONS, PROFIT, HISTORY, CHAT, SUPPLIES, AI, QR, GPS,
# BACKUP, SUPPORT, SETTINGS, PERFORMANCE, CERTIFICATIONS,
# CLIENT PORTAL, ADMIN COMPANIES, TERMS, MAIN
# ============================================================

def inspections_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🔍 Pre‑Inspection Checklist")
    st.info("Dynamic inspection system: add rooms, take notes, save versions.")
    if 'inspection_areas' not in st.session_state:
        st.session_state.inspection_areas = []
    new_area = st.text_input("Add area (e.g., Restroom, Office, Kitchen)")
    if st.button("➕ Add Area"):
        if new_area:
            st.session_state.inspection_areas.append({"name": new_area, "status": "pending", "notes": ""})
            st.rerun()
    for idx, area in enumerate(st.session_state.inspection_areas):
        with st.expander(f"{area['name']} – {area['status']}"):
            status = st.selectbox("Status", ["pending","in_progress","completed"], index=["pending","in_progress","completed"].index(area['status']), key=f"stat_{idx}")
            notes = st.text_area("Notes", value=area.get('notes', ''), key=f"notes_{idx}")
            area['status'] = status
            area['notes'] = notes
    if st.button("Save Inspection"):
        company_id = get_current_user_company()
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO inspections (company_id, user_id, client_name, areas_json, status, started_at) VALUES (?,?,?,?,?,?)",
                  (company_id, st.session_state.user['user_id'], "Sample Client", json.dumps(st.session_state.inspection_areas), "completed", datetime.now().isoformat()))
        conn.commit()
        conn.close()
        st.success("Inspection saved")
        st.session_state.inspection_areas = []
        st.rerun()

def profit_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 💰 Profit Dashboard")
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM quick_jobs WHERE user_id = ? AND company_id = ? ORDER BY job_date DESC", conn, params=(st.session_state.user['user_id'], company_id))
    c = conn.cursor()
    c.execute("SELECT insurance, vehicle, software, advertising, other FROM monthly_expenses WHERE user_id = ? AND company_id = ? AND month_year = ?", 
              (st.session_state.user['user_id'], company_id, datetime.now().strftime("%Y-%m")))
    exp_row = c.fetchone()
    conn.close()
    expenses = {"insurance":0.0,"vehicle":0.0,"software":0.0,"advertising":0.0,"other":0.0}
    if exp_row:
        expenses = dict(zip(["insurance","vehicle","software","advertising","other"], [float(x) if x is not None else 0.0 for x in exp_row]))
    total_exp = sum(expenses.values())
    st.markdown("#### Monthly Fixed Expenses")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        new_ins = st.number_input("Insurance", value=float(expenses["insurance"]), step=50.0)
    with col2:
        new_veh = st.number_input("Vehicle", value=float(expenses["vehicle"]), step=50.0)
    with col3:
        new_sw = st.number_input("Software", value=float(expenses["software"]), step=25.0)
    with col4:
        new_adv = st.number_input("Advertising", value=float(expenses["advertising"]), step=50.0)
    with col5:
        new_other = st.number_input("Other", value=float(expenses["other"]), step=50.0)
    if st.button("Save Expenses"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO monthly_expenses (user_id, company_id, month_year, insurance, vehicle, software, advertising, other) VALUES (?,?,?,?,?,?,?,?)",
                  (st.session_state.user['user_id'], company_id, datetime.now().strftime("%Y-%m"), new_ins, new_veh, new_sw, new_adv, new_other))
        conn.commit()
        conn.close()
        st.success("Saved")
        st.rerun()
    if df.empty:
        st.info("No quick jobs yet")
    else:
        total_rev = float(df["amount_invoiced"].sum())
        total_profit = float(df["profit"].sum())
        margin = (total_profit/total_rev*100) if total_rev>0 else 0
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Revenue", f"${total_rev:,.2f}")
        col2.metric("Total Profit", f"${total_profit:,.2f}")
        col3.metric("Margin", f"{margin:.1f}%")
        net = total_profit - total_exp
        st.metric("Net Profit (after overhead)", f"${net:,.2f}")
        st.dataframe(df[["job_date","description","hours","amount_invoiced","profit"]])
        df['month'] = pd.to_datetime(df['job_date']).dt.strftime("%Y-%m")
        monthly = df.groupby('month')['profit'].sum().reset_index()
        if not monthly.empty:
            fig = px.bar(monthly, x='month', y='profit', title="Monthly Profit")
            st.plotly_chart(fig, use_container_width=True)

def history_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📋 Estimate History")
    company_id = get_current_user_company()
    accessible = get_accessible_user_ids(st.session_state.user['user_id'], st.session_state.user['role'], company_id)
    placeholders = ','.join(['?' for _ in accessible])
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f"SELECT id, client_name, city, property_type, estimated_price, created_at, status FROM estimates WHERE company_id = ? AND user_id IN ({placeholders}) ORDER BY created_at DESC", conn, params=[company_id] + accessible)
    conn.close()
    if df.empty:
        st.info("No estimates")
    else:
        st.dataframe(df)
        csv = df.to_csv(index=False)
        st.download_button("Export CSV", csv, "estimates.csv", "text/csv")

def send_message(message, channel='general', recipient_id=None):
    user = st.session_state.user
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO team_messages (company_id, user_id, username, user_role, message, channel, is_private, recipient_id, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
              (company_id, user['user_id'], user['username'], user['role'], message, channel, 1 if recipient_id else 0, recipient_id, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_messages(channel='general', user_id=None, limit=50):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    if user_id:
        df = pd.read_sql_query("SELECT id, username, user_role, message, created_at FROM team_messages WHERE company_id = ? AND ((is_private=0 AND channel=?) OR (is_private=1 AND (user_id=? OR recipient_id=?))) ORDER BY created_at DESC LIMIT ?", conn, params=(company_id, channel, user_id, user_id, limit))
    else:
        df = pd.read_sql_query("SELECT id, username, user_role, message, created_at FROM team_messages WHERE company_id = ? AND is_private=0 AND channel=? ORDER BY created_at DESC LIMIT ?", conn, params=(company_id, channel, limit))
    conn.close()
    return df

def chat_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 💬 Team Chat")
    with st.form("chat"):
        msg = st.text_input("Message")
        if st.form_submit_button("Send"):
            if msg:
                send_message(msg)
                st.rerun()
    messages = get_messages(channel='general', limit=50)
    for _, m in messages[::-1].iterrows():
        st.write(f"**{m['username']}**: {m['message']} ({m['created_at'][11:16]})")

def get_all_supplies():
    company_id = get_current_user_company()
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM supplies WHERE company_id = ? AND user_id = ? ORDER BY category, name", conn, params=(company_id, user_id))
    conn.close()
    return df

def get_low_stock_supplies():
    company_id = get_current_user_company()
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM supplies WHERE company_id = ? AND user_id = ? AND current_stock <= reorder_level", conn, params=(company_id, user_id))
    conn.close()
    return df

def add_supply(name, category, unit, stock, reorder, cost):
    company_id = get_current_user_company()
    user_id = st.session_state.user['user_id']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO supplies (company_id, user_id, name, category, unit, current_stock, reorder_level, unit_cost, last_updated) VALUES (?,?,?,?,?,?,?,?,?)",
              (company_id, user_id, name, category, unit, stock, reorder, cost, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def supplies_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📦 Supplies Inventory")
    supplies = get_all_supplies()
    if supplies.empty:
        st.info("No supplies")
    else:
        st.dataframe(supplies)
    low = get_low_stock_supplies()
    if not low.empty:
        st.warning("Low stock: " + ", ".join(low['name'].tolist()))
    with st.expander("Add Supply"):
        with st.form("add_supply"):
            name = st.text_input("Name")
            cat = st.selectbox("Category", ["Chemicals","Consumables","Equipment","PPE","Other"])
            unit = st.selectbox("Unit", ["gallons","bottles","rolls","boxes","packs","each"])
            stock = st.number_input("Current Stock", 0.0)
            reorder = st.number_input("Reorder Level", 0.0)
            cost = st.number_input("Unit Cost", 0.0)
            if st.form_submit_button("Add"):
                if name:
                    add_supply(name, cat, unit, stock, reorder, cost)
                    st.rerun()

def ai_tasks_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🤖 AI Task List")
    prop = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()))
    sqft = st.number_input("Square Feet", 100, 100000, 2000)
    complexity = st.slider("Complexity",1,10,3)
    if st.button("Generate"):
        tasks = [
            "Vacuum floors",
            "Dust surfaces",
            "Clean restrooms",
            "Empty trash",
            "Sanitize high-touch areas"
        ]
        if complexity >= 8:
            tasks.append("Deep clean required")
        if sqft > 5000:
            tasks.append("Large area – allocate extra time")
        for t in tasks:
            st.checkbox(t)

def generate_worker_qr(worker_id, worker_name):
    data = f"profitclean://worker/{worker_id}/{datetime.now().strftime('%Y%m%d')}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/png;base64,{img_str}"

def qr_tracking_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📱 QR Tracking")
    company_id = get_current_user_company()
    accessible = get_accessible_user_ids(st.session_state.user['user_id'], st.session_state.user['role'], company_id)
    placeholders = ','.join(['?' for _ in accessible])
    conn = sqlite3.connect(DB_PATH)
    workers_df = pd.read_sql_query(f"SELECT id, username FROM users WHERE role='worker' AND company_id = ? AND id IN ({placeholders})", conn, params=[company_id] + accessible)
    conn.close()
    if workers_df.empty:
        st.info("No workers")
    else:
        selected = st.selectbox("Worker", workers_df['username'].tolist())
        wid = workers_df[workers_df['username']==selected]['id'].values[0]
        if st.button("Generate QR"):
            qr = generate_worker_qr(wid, selected)
            st.image(qr, width=200)

def gps_tracking_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📍 GPS Tracking")
    st.warning("Opt‑in location sharing. Enable only during work hours.")
    if st.button("Share Location (Test)"):
        st.success("Location shared (mock). In production, browser geolocation would be used.")

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def create_backup():
    ensure_backup_dir()
    user_id = st.session_state.user['user_id']
    company_id = get_current_user_company()
    accessible = get_accessible_user_ids(user_id, st.session_state.user['role'], company_id)
    backup_data = {"version": "3.0", "backup_date": datetime.now().isoformat(), "user_id": user_id, "company_id": company_id, "accessible_users": accessible, "data": {}}
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    tables = ["clients", "estimates", "quick_jobs", "monthly_expenses", "scheduled_jobs", "inspections", "supplies", "team_messages", "support_tickets"]
    for table in tables:
        try:
            placeholders = ','.join(['?' for _ in accessible])
            c.execute(f"SELECT * FROM {table} WHERE company_id = ? AND user_id IN ({placeholders})", [company_id] + accessible)
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
    for old in backups[:-30]:
        os.remove(os.path.join(BACKUP_DIR, old))
    return backup_file

def restore_from_backup(backup_file):
    with open(backup_file, 'r') as f:
        backup = json.load(f)
    user_id = st.session_state.user['user_id']
    company_id = get_current_user_company()
    data = backup.get("data", {})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for table, rows in data.items():
        if not rows:
            continue
        c.execute(f"DELETE FROM {table} WHERE company_id = ? AND user_id = ?", (company_id, user_id))
        for row in rows:
            columns = [col for col in row.keys() if col != 'id']
            placeholders = ','.join(['?' for _ in columns])
            values = [row[col] for col in columns]
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
            path = os.path.join(BACKUP_DIR, f)
            backups.append({"file": f, "path": path, "date": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S"), "size": f"{os.path.getsize(path)/1024:.1f} KB"})
    return sorted(backups, key=lambda x: x["date"], reverse=True)

def backup_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 💾 Backup & Restore")
    if st.button("Create Backup"):
        f = create_backup()
        with open(f, 'rb') as fp:
            st.download_button("Download Backup", fp, os.path.basename(f))
    backups = get_backup_list()
    if backups:
        st.dataframe(backups)
        sel = st.selectbox("Select backup", [b['file'] for b in backups])
        if st.button("Restore"):
            path = os.path.join(BACKUP_DIR, sel)
            if restore_from_backup(path):
                st.success("Restored! Refresh page.")

def create_support_ticket(issue_type, description, steps, screenshot=None):
    user_id = st.session_state.user['user_id']
    user_email = st.session_state.user.get('email', '')
    company_id = get_current_user_company()
    ticket_id = f"TKT-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO support_tickets (company_id, ticket_id, user_id, user_email, issue_type, description, steps_to_reproduce, screenshot, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (company_id, ticket_id, user_id, user_email, issue_type, description, steps, screenshot, datetime.now().isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return ticket_id

def get_user_tickets():
    user_id = st.session_state.user['user_id']
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT ticket_id, issue_type, description, status, created_at FROM support_tickets WHERE user_id = ? AND company_id = ? ORDER BY created_at DESC", conn, params=(user_id, company_id))
    conn.close()
    return df

def support_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🎫 Support Tickets")
    with st.form("ticket"):
        issue = st.selectbox("Type", ["Bug","Feature request","Data issue","Other"])
        desc = st.text_area("Description")
        if st.form_submit_button("Submit"):
            if desc:
                tid = create_support_ticket(issue, desc, "")
                st.success(f"Ticket {tid} submitted")
                st.rerun()
    tickets = get_user_tickets()
    if not tickets.empty:
        st.dataframe(tickets)

def settings_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### ⚙️ Business Settings")
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT business_name, phone, email, hourly_wage, min_job_fee, home_city, smtp_email, smtp_password FROM business_profile WHERE company_id = ?", (company_id,))
    row = c.fetchone()
    conn.close()
    if row:
        with st.form("settings"):
            bname = st.text_input("Business Name", row[0])
            phone = st.text_input("Phone", row[1])
            email = st.text_input("Email", row[2])
            wage = st.number_input("Hourly Wage", value=row[3])
            min_fee = st.number_input("Min Job Fee", value=row[4])
            home = st.selectbox("Home City", FLORIDA_CITIES, index=FLORIDA_CITIES.index(row[5]) if row[5] in FLORIDA_CITIES else 0)
            smtp_email = st.text_input("SMTP Email", value=row[6] if row[6] else "")
            smtp_password = st.text_input("SMTP Password", type="password", value=row[7] if row[7] else "")
            if st.form_submit_button("Save"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE business_profile SET business_name=?, phone=?, email=?, hourly_wage=?, min_job_fee=?, home_city=?, smtp_email=?, smtp_password=? WHERE company_id=?",
                          (bname, phone, email, wage, min_fee, home, smtp_email, smtp_password, company_id))
                conn.commit()
                conn.close()
                st.success("Saved")
                st.rerun()
    else:
        st.warning("Business profile not found")

def my_performance_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🏅 My Performance")
    uid = st.session_state.user['user_id']
    jobs, profit, hours = get_worker_performance(uid)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hire_date FROM users WHERE id = ?", (uid,))
    row = c.fetchone()
    hire = datetime.fromisoformat(row[0]) if row else datetime.now()
    years = (datetime.now() - hire).days / 365.25
    conn.close()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Jobs Completed", jobs)
    col2.metric("Total Profit", f"${profit:,.2f}")
    col3.metric("Total Hours", f"{hours:.1f}")
    col4.metric("Years of Service", f"{years:.1f}")
    if years >= 1.0:
        st.success(f"🎉 Congratulations on your {int(years)}‑year anniversary!")
    badges = get_worker_badges(uid)
    if not badges.empty:
        st.subheader("Earned Badges")
        st.dataframe(badges)
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT strftime('%Y-%m', job_date) as month, SUM(profit) as profit FROM quick_jobs WHERE user_id = ? GROUP BY month ORDER BY month", conn, params=(uid,))
    conn.close()
    if not df.empty:
        fig = px.line(df, x='month', y='profit', title="Your Monthly Profit")
        st.plotly_chart(fig, use_container_width=True)

def certifications_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📜 Certifications")
    user_role = st.session_state.user['role']
    uid = st.session_state.user['user_id']
    if user_role == 'worker':
        certs = get_certifications_for_worker(uid)
        if certs.empty:
            st.info("No certifications yet.")
        else:
            st.dataframe(certs)
        with st.expander("➕ Add New Certification"):
            with st.form("add_cert"):
                name = st.text_input("Certification Name")
                issuer = st.text_input("Issuing Body")
                date_earned = st.date_input("Date Earned")
                expiration = st.date_input("Expiration Date (optional)", value=None)
                file = st.file_uploader("Upload Certificate (PDF/Image)", type=['pdf','png','jpg'])
                notes = st.text_area("Notes")
                if st.form_submit_button("Submit"):
                    if name:
                        add_certification(uid, name, issuer, date_earned.isoformat(), expiration.isoformat() if expiration else None, file, notes)
                        st.success("Certification added")
                        st.rerun()
    elif user_role in ['supervisor','admin','super_admin','support_staff']:
        company_id = get_current_user_company()
        accessible = get_accessible_user_ids(uid, user_role, company_id)
        placeholders = ','.join(['?' for _ in accessible])
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(f"""
            SELECT u.username, c.certification_name, c.issuing_body, c.date_earned, c.expiration_date, c.verified_by, c.id
            FROM worker_certifications c
            JOIN users u ON c.worker_id = u.id
            WHERE u.company_id = ? AND u.id IN ({placeholders})
        """, conn, params=[company_id] + accessible)
        conn.close()
        if df.empty:
            st.info("No certifications from your team.")
        else:
            st.dataframe(df)
            cert_id = st.number_input("Certification ID to verify", min_value=1, step=1)
            if st.button("Verify Certification"):
                verify_certification(cert_id, uid)
                st.success("Verified")
                st.rerun()

def client_login_page():
    st.markdown("### 👤 Client Portal Login")
    with st.form("client_login"):
        email = st.text_input("Email")
        if st.form_submit_button("Login"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id, business_name, company_id FROM clients WHERE email = ?", (email,))
            client = c.fetchone()
            conn.close()
            if client:
                st.session_state.client_logged_in = True
                st.session_state.client_id = client[0]
                st.session_state.client_name = client[1]
                st.session_state.client_company_id = client[2]
                st.session_state.page = "client_dashboard"
                st.rerun()
            else:
                st.error("Client not found")
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()

def client_dashboard():
    if st.sidebar.button("Logout"):
        st.session_state.client_logged_in = False
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown(f"### 👋 Welcome, {st.session_state.client_name}")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, city, property_type, estimated_price, created_at, status FROM estimates WHERE client_id = ? AND company_id = ? ORDER BY created_at DESC", 
                           conn, params=(st.session_state.client_id, st.session_state.client_company_id))
    conn.close()
    if df.empty:
        st.info("No estimates")
    else:
        st.dataframe(df)
        for _, row in df.iterrows():
            if row['status'] == 'sent':
                if st.button(f"Approve Estimate #{row['id']}"):
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("UPDATE estimates SET status = 'approved', approved_at = ? WHERE id = ? AND client_id = ?", 
                              (datetime.now().isoformat(), row['id'], st.session_state.client_id))
                    conn.commit()
                    conn.close()
                    st.success("Approved! We'll contact you.")
                    st.rerun()

# ----------------------------- TERMS OF SERVICE PAGE -----------------------------
def terms_page():
    st.markdown("### 📜 Terms of Service")
    st.caption("Last Updated: 2025")
    st.markdown("""
    **1. Ownership**  
    This application and all source code, design, algorithms, and business logic are the exclusive property of Dust Bros & Co.
    
    **2. Prohibited Actions**  
    You may not:
    - Copy, modify, or reverse engineer any part of this application
    - Use the application to create a competing product
    - Share, distribute, or sublicense the application or its source code
    
    **3. License**  
    You are granted a non-exclusive, non-transferable license to use this application for your internal business purposes only.
    
    **4. Termination**  
    Any violation of these terms will result in immediate termination of your access.
    
    **5. Contact**  
    legal@dustbros.com
    """)
    
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

# ----------------------------- ADMIN COMPANIES PAGE (TROUBLESHOOTING) -----------------------------
@require_role(['super_admin', 'support_staff'])
def admin_companies_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 🏢 Admin Tools")
    st.caption("Super Admin & Support Staff Dashboard")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT c.id, c.name, c.subdomain, u.username as owner, 
               c.created_at, c.is_active,
               (SELECT COUNT(*) FROM users WHERE company_id = c.id) as user_count,
               (SELECT COUNT(*) FROM clients WHERE company_id = c.id) as client_count
        FROM companies c
        LEFT JOIN users u ON c.owner_id = u.id
        ORDER BY c.created_at DESC
    """, conn)
    conn.close()
    st.dataframe(df, use_container_width=True)

    # Company Switcher (Super Admin & Support Staff)
    with st.expander("🔧 Switch to Company (Troubleshooting)"):
        st.warning("⚠️ Switching will change your session to act as a user of the selected company. All actions are logged.")
        company_id_switch = st.selectbox("Select company to switch to", df['id'].tolist(), format_func=lambda x: f"{df[df['id']==x]['name'].iloc[0]} (ID: {x})")
        if st.button("Switch to this company"):
            if st.session_state.user.get('role') in ['super_admin', 'support_staff']:
                st.session_state.original_company_id = st.session_state.user.get('company_id')
                st.session_state.user['company_id'] = company_id_switch
                st.session_state.user['role_override'] = True
                log_audit(st.session_state.user['user_id'], "company_switch", f"Switched to company ID {company_id_switch}")
                st.success(f"Switched to company ID {company_id_switch}. You are now viewing that company's data.")
                st.rerun()
            else:
                st.error("Only super admin or support staff can switch companies.")
        if st.button("Reset to my original company"):
            if 'original_company_id' in st.session_state:
                st.session_state.user['company_id'] = st.session_state.original_company_id
                del st.session_state.original_company_id
                st.session_state.user.pop('role_override', None)
                log_audit(st.session_state.user['user_id'], "company_switch_reset", "Reset to original company")
                st.success("Reset to your original company.")
                st.rerun()
            else:
                st.info("No override active.")

    # Export Company Data (both roles)
    with st.expander("📤 Export Company Data (Troubleshooting)"):
        export_company_id = st.selectbox("Select company to export", df['id'].tolist(), format_func=lambda x: f"{df[df['id']==x]['name'].iloc[0]} (ID: {x})", key="export_company")
        if st.button("Export this company to JSON"):
            export_data = export_company_data(export_company_id)
            if export_data:
                st.download_button("Download JSON", export_data, f"company_{export_company_id}_backup.json", "application/json")
            else:
                st.error("Export failed.")

    # Import Company Data (only super admin)
    if st.session_state.user['role'] == 'super_admin':
        with st.expander("📥 Import Company Data (Migration)"):
            st.warning("⚠️ This will REPLACE data in the destination company! Use with caution.")
            import_file = st.file_uploader("Upload JSON backup file", type=['json'])
            dest_company_id = st.selectbox("Destination company ID", df['id'].tolist(), format_func=lambda x: f"{df[df['id']==x]['name'].iloc[0]} (ID: {x})", key="import_dest")
            if import_file and st.button("Import into destination company"):
                try:
                    data = json.load(import_file)
                    success = import_company_data(dest_company_id, data)
                    if success:
                        st.success(f"Data imported into company ID {dest_company_id}. Refresh to see changes.")
                    else:
                        st.error("Import failed. Check log.")
                except Exception as e:
                    st.error(f"Invalid file: {e}")

    # Create New Company (super admin only)
    if st.session_state.user['role'] == 'super_admin':
        with st.expander("➕ Create New Company"):
            with st.form("create_company_admin"):
                company_name = st.text_input("Company Name")
                subdomain = st.text_input("Subdomain")
                admin_email = st.text_input("Admin Email")
                admin_username = st.text_input("Admin Username")
                admin_password = st.text_input("Admin Password", type="password")
                if st.form_submit_button("Create Company"):
                    if all([company_name, subdomain, admin_email, admin_username, admin_password]):
                        success, result = create_company(company_name, subdomain, admin_email, admin_username, admin_password)
                        if success:
                            st.success(f"Company '{company_name}' created successfully!")
                            st.rerun()
                        else:
                            st.error(result)
                    else:
                        st.error("All fields required")

    # Create Support Staff Account (super admin only)
    if st.session_state.user['role'] == 'super_admin':
        with st.expander("👥 Create Support Staff Account"):
            with st.form("create_support"):
                support_email = st.text_input("Email")
                support_username = st.text_input("Username")
                support_password = st.text_input("Temporary Password", type="password")
                if st.form_submit_button("Create Support Staff"):
                    if all([support_email, support_username, support_password]):
                        success, msg = create_support_staff(support_email, support_username, support_password)
                        if success:
                            st.success(f"Support staff {support_username} created. They can log in and use troubleshooting tools.")
                        else:
                            st.error(msg)
                    else:
                        st.error("All fields required")

    # Company Activation/Deactivation (super admin only)
    if st.session_state.user['role'] == 'super_admin':
        with st.expander("⚙️ Company Actions (Activate/Deactivate)"):
            company_id = st.number_input("Company ID", min_value=1, step=1)
            new_status = st.selectbox("Set Active Status", [1, 0], format_func=lambda x: "Active" if x else "Inactive")
            if st.button("Update Company Status"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE companies SET is_active = ? WHERE id = ?", (new_status, company_id))
                conn.commit()
                conn.close()
                st.success(f"Company {company_id} status updated")
                st.rerun()

# ----------------------------- DASHBOARD (CORRECTED) -----------------------------
def dashboard():
    user = st.session_state.user
    business_name = get_business_name()
    company_id = get_current_user_company()
    st.title(f"🧹 {business_name}")
    st.caption(f"Welcome, {user['username']} ({user['role']}) | Company ID: {company_id} | Created by Dust Bros & Co.")
    if st.session_state.user.get('role_override'):
        st.warning(f"You are currently viewing data for company ID: {st.session_state.user['company_id']} (override active).")
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
            ("📜 Terms of Service", "terms"),
        ]
        if user['role'] in ['super_admin', 'support_staff']:
            menu_items.append(("🔧 Admin Tools", "admin_companies"))
        for label, page in menu_items:
            if st.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        st.markdown("---")
        with st.expander("💬 Need Help?"):
            if st.button("📝 Report Issue"):
                st.session_state.page = "support"
                st.rerun()
        st.markdown("---")
        if st.button("🚪 Logout"):
            logout_user()
            st.rerun()
    st.markdown("---")
    # FIXED: Added user['role'] as second argument
    accessible = get_accessible_user_ids(user['user_id'], user['role'], company_id)
    placeholders = ','.join(['?' for _ in accessible])
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(f"SELECT COUNT(*) FROM clients WHERE company_id = ? AND user_id IN ({placeholders})", [company_id] + accessible)
    client_cnt = c.fetchone()[0]
    c.execute(f"SELECT COUNT(*) FROM estimates WHERE company_id = ? AND user_id IN ({placeholders}) AND status='sent'", [company_id] + accessible)
    pending = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM users WHERE manager_id = ? AND role='worker' AND company_id = ?", (user['user_id'], company_id))
    worker_cnt = c.fetchone()[0]
    conn.close()
    col1, col2, col3 = st.columns(3)
    col1.metric("Clients", client_cnt)
    col2.metric("Pending Estimates", pending)
    col3.metric("Workers Under You", worker_cnt)
    st.info("Use sidebar to navigate.")

# ============================================================
# MAIN ROUTING
# ============================================================

def main():
    init_db()

    # Check if any companies exist (if not, show setup wizard)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM companies")
    company_count = c.fetchone()[0]
    conn.close()

    if company_count == 0:
        setup_wizard()
    else:
        # Initialize session state page if not present
        if "page" not in st.session_state:
            st.session_state.page = "login"

        # Client portal mode
        if st.session_state.get("client_logged_in", False):
            if st.session_state.page == "client_dashboard":
                client_dashboard()
            else:
                st.session_state.page = "client_dashboard"
                client_dashboard()
        else:
            # Page routing for authenticated users
            pages = {
                "login": login_page,
                "two_factor": two_factor_page,
                "create_account": create_account_page,
                "edit_profile": edit_profile_page,
                "setup_2fa": setup_2fa_page,
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
                "admin_companies": admin_companies_page,
            }
            current = st.session_state.page
            if current in pages:
                pages[current]()
            else:
                login_page()

if __name__ == "__main__":
    main()    
