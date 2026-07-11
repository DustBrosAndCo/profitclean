"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
ENHANCED VERSION - Part 1 of 5
Includes: multi-tenant, super admin, support staff, troubleshooting tools, enhanced features
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
import urllib.request
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from io import BytesIO
import base64
import hashlib
import hmac
from datetime import datetime, date, timedelta
from encryption_manager import encryption
from functools import wraps
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import plotly.express as px
import plotly.graph_objects as go
import time
import shutil
import traceback
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from integrations.calendly import CalendlyIntegration
from constants import (
    DB_PATH, MIN_PASSWORD_LENGTH, MAX_LOGIN_ATTEMPTS, ACCOUNT_LOCKOUT_MINUTES,
    SESSION_EXPIRY_DAYS, SALES_TAX_RATE, BACKUP_DIR, UPLOAD_DIR,
    AVAILABLE_INTEGRATIONS, FLORIDA_CITIES, PROPERTY_TYPES, FREQUENCIES,
    HOLIDAY_RATES, KNOWN_TOLLS, MAX_RESET_CODE_ATTEMPTS,
)
from enums import UserRole, TicketStatus, TicketPriority, EstimateStatus, JobStatus, EmailContext
from i18n import TRANSLATIONS, get_user_language, t, language_selector
from database import init_db, migrate_database
from auth import (
    get_current_user_company, normalize_email, hash_password, verify_password,
    check_user_password_hash, validate_password_strength, log_audit, log_auth_event,
    get_current_user_data, generate_session_token, hash_session_token,
    create_user_session, validate_session_token, clear_expired_sessions,
    authenticate_user, logout_user, get_effective_user, require_auth, require_role,
    generate_totp_secret, get_totp_uri, verify_totp, generate_backup_codes,
    verify_backup_code,
)

LAST_EMAIL_ERROR = None

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
/* ---------- Design tokens ---------- */
:root {
    --pc-navy: #0F172A;
    --pc-navy-light: #1E3A5F;
    --pc-teal: #2DD4BF;
    --pc-teal-dark: #0F766E;
    --pc-green: #10b981;
    --pc-green-dark: #059669;
    --pc-amber: #f59e0b;
    --pc-amber-light: #fef3c7;
    --pc-purple: #8b5cf6;
    --pc-red: #ef4444;
    --pc-border: #e2e8f0;
    --pc-bg-soft: #f8fafc;
    --pc-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
    --pc-shadow-hover: 0 8px 24px rgba(15, 23, 42, 0.12);
    --pc-radius: 16px;
    --pc-radius-sm: 10px;
}

/* ---------- Global typography ---------- */
html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

h1, h2, h3 {
    font-weight: 700 !important;
    color: var(--pc-navy) !important;
    letter-spacing: -0.02em;
}

/* Main app background */
.stApp {
    background: linear-gradient(180deg, #fafbfc 0%, #f4f6f8 100%);
}

/* ---------- Sidebar ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--pc-navy) 0%, var(--pc-navy-light) 100%);
}
section[data-testid="stSidebar"] * {
    color: #f1f5f9 !important;
}
section[data-testid="stSidebar"] .stButton button {
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.10) !important;
    color: #f1f5f9 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    border-radius: var(--pc-radius-sm) !important;
    margin: 3px 0 !important;
    transition: all 0.18s ease;
}
section[data-testid="stSidebar"] .stButton button:hover {
    background: rgba(45, 212, 191, 0.18) !important;
    border-color: var(--pc-teal) !important;
    transform: translateX(3px);
}
section[data-testid="stSidebar"] .stButton button:active {
    background: rgba(45, 212, 191, 0.32) !important;
    transform: translateX(3px) scale(0.97);
    transition: all 0.05s ease !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.12);
}

/* ---------- Cards & metrics ---------- */
.metric-card {
    background: linear-gradient(135deg, var(--pc-navy-light) 0%, var(--pc-navy) 100%);
    border-radius: var(--pc-radius);
    padding: 1.4rem;
    color: white;
    text-align: center;
    box-shadow: var(--pc-shadow);
}
.metric-value { font-size: 2.1rem; font-weight: 800; }

.price-card {
    background: linear-gradient(135deg, var(--pc-teal) 0%, var(--pc-teal-dark) 100%);
    border-radius: 20px;
    padding: 2rem;
    color: white;
    text-align: center;
    box-shadow: var(--pc-shadow-hover);
}
.price-value { font-size: 3rem; font-weight: 800; }

.card {
    background: white;
    border-radius: var(--pc-radius);
    padding: 1.25rem;
    margin-bottom: 1rem;
    border: 1px solid var(--pc-border);
    box-shadow: var(--pc-shadow);
    transition: box-shadow 0.2s ease;
}
.card:hover { box-shadow: var(--pc-shadow-hover); }

.internal-card {
    background: var(--pc-amber-light);
    border-radius: var(--pc-radius);
    padding: 1.1rem;
    border-left: 4px solid var(--pc-amber);
}
.worker-card {
    background: #f0fdf4;
    border-radius: var(--pc-radius);
    padding: 1.1rem;
    border: 1px solid #bbf7d0;
}

/* Pricing tiers — unified look */
.pricing-tier-low, .pricing-tier-fair, .pricing-tier-high {
    border-radius: var(--pc-radius);
    padding: 1.25rem;
    text-align: center;
    box-shadow: var(--pc-shadow);
    transition: transform 0.18s ease;
}
.pricing-tier-low:hover, .pricing-tier-fair:hover, .pricing-tier-high:hover {
    transform: translateY(-3px);
}
.pricing-tier-low { background: var(--pc-amber-light); }
.pricing-tier-fair { background: #d1fae5; }
.pricing-tier-high { background: #ede9fe; }

/* ---------- Buttons ---------- */
.stButton button {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font-weight: 600;
    border-radius: var(--pc-radius-sm);
    transition: all 0.18s ease;
    border: 1px solid transparent;
}
.stButton button:hover {
    transform: translateY(-1px);
    box-shadow: var(--pc-shadow-hover);
}
/* Instant press feedback on every button -- a quick scale-down + inset shadow
   so clicking feels acknowledged immediately, before the rerun even starts. */
.stButton button:active {
    transform: scale(0.96) !important;
    box-shadow: inset 0 2px 5px rgba(0,0,0,0.15) !important;
    transition: all 0.05s ease !important;
}
/* Primary (form submit / type="primary") buttons get the brand gradient */
button[kind="primary"], .stFormSubmitButton button[kind="primary"] {
    background: linear-gradient(135deg, var(--pc-green) 0%, var(--pc-green-dark) 100%) !important;
    color: white !important;
    border: none !important;
}
button[kind="primary"]:active, .stFormSubmitButton button[kind="primary"]:active {
    background: linear-gradient(135deg, var(--pc-green-dark) 0%, #065f46 100%) !important;
}

/* ---------- Inputs ---------- */
.stTextInput input, .stNumberInput input, .stTextArea textarea, .stSelectbox > div {
    border-radius: var(--pc-radius-sm) !important;
    border: 1px solid var(--pc-border) !important;
}
.stTextInput input:focus, .stNumberInput input:focus, .stTextArea textarea:focus {
    border-color: var(--pc-teal) !important;
    box-shadow: 0 0 0 3px rgba(45, 212, 191, 0.15) !important;
}

/* ---------- Tabs ---------- */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    border-bottom: 2px solid var(--pc-border);
}
.stTabs [data-baseweb="tab"] {
    border-radius: var(--pc-radius-sm) var(--pc-radius-sm) 0 0;
    padding: 10px 18px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] {
    background: var(--pc-bg-soft);
    color: var(--pc-teal-dark) !important;
}

/* ---------- Metrics (st.metric) ---------- */
[data-testid="stMetric"] {
    background: white;
    border: 1px solid var(--pc-border);
    border-radius: var(--pc-radius);
    padding: 0.9rem 1rem;
    box-shadow: var(--pc-shadow);
}
[data-testid="stMetricLabel"] { font-weight: 600; color: #64748b; }
[data-testid="stMetricValue"] { color: var(--pc-navy); font-weight: 800; }

/* ---------- Expanders ---------- */
.streamlit-expanderHeader {
    border-radius: var(--pc-radius-sm) !important;
    font-weight: 600 !important;
    background: var(--pc-bg-soft) !important;
}

/* ---------- Dataframes ---------- */
[data-testid="stDataFrame"] {
    border-radius: var(--pc-radius-sm);
    overflow: hidden;
    border: 1px solid var(--pc-border);
}

/* ---------- Notification badge ---------- */
.notification-badge {
    background-color: var(--pc-red);
    color: white;
    border-radius: 50%;
    padding: 2px 6px;
    font-size: 10px;
    margin-left: 5px;
}

/* ---------- Timeline ---------- */
.timeline-item {
    border-left: 3px solid var(--pc-green);
    padding-left: 15px;
    margin-bottom: 15px;
}

.status-approved { color: var(--pc-green); font-weight: 700; }
.status-pending { color: var(--pc-amber); font-weight: 700; }
.status-rejected { color: var(--pc-red); font-weight: 700; }

/* ---------- Login page polish ---------- */
.stForm {
    background: white;
    border-radius: var(--pc-radius);
    padding: 1.5rem;
    border: 1px solid var(--pc-border);
    box-shadow: var(--pc-shadow);
}
</style>
""", unsafe_allow_html=True)

# ============================================================
# DATABASE SETUP (ENHANCED)
# ============================================================

# ============================================================
# PERMISSION SYSTEM
# ============================================================

def has_permission(user_role: str, action: str, target_type: str = None) -> bool:
    """Check if user has permission for an action"""
    
    # Super admin can do everything
    if user_role == UserRole.SUPER_ADMIN.value:
        return True
    
    # Permission matrix
    permissions = {
        'view_events': [UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.SUPERVISOR.value, UserRole.WORKER.value],
        'add_event': [UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.SUPERVISOR.value, UserRole.WORKER.value],
        'add_client': [UserRole.ADMIN.value, UserRole.MANAGER.value, UserRole.SUPERVISOR.value, UserRole.WORKER.value],
        'edit_event': [UserRole.ADMIN.value, UserRole.MANAGER.value],
        'edit_own_event': [UserRole.SUPERVISOR.value, UserRole.WORKER.value],
        'delete_event': [UserRole.ADMIN.value],
        'move_event': [UserRole.ADMIN.value],
        'request_delete': [UserRole.MANAGER.value, UserRole.SUPERVISOR.value, UserRole.WORKER.value],
        'request_move': [UserRole.MANAGER.value, UserRole.SUPERVISOR.value, UserRole.WORKER.value],
        'approve_requests': [UserRole.ADMIN.value, UserRole.MANAGER.value],
        'manage_workers': [UserRole.ADMIN.value, UserRole.MANAGER.value]
    }
    
    allowed_roles = permissions.get(action, [])
    return user_role in allowed_roles


def can_delete_directly(user_role: str) -> bool:
    """Check if user can delete without approval"""
    return user_role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]


def can_move_directly(user_role: str) -> bool:
    """Check if user can move without approval"""
    return user_role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]


def requires_approval(user_role: str, action: str) -> bool:
    """Check if action requires admin approval"""
    if user_role in [UserRole.ADMIN.value, UserRole.SUPER_ADMIN.value]:
        return False
    if action in ['delete', 'move']:
        return True
    return False


# ============================================================
# APPROVAL REQUEST SYSTEM
# ============================================================

def create_approval_request(company_id: int, requester_id: int, request_type: str, target_type: str,
                            target_id: int, requested_value: str = None, reason: str = "") -> int:
    """Create an approval request for admin"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get current value if applicable
    current_value = None
    if target_type == 'scheduled_job':
        c.execute("SELECT * FROM scheduled_jobs WHERE id = ? AND company_id = ?",
                  (target_id, company_id))
        row = c.fetchone()
        if row:
            current_value = f"Job: {row[5]} on {row[9]} at {row[10]}"
    
    c.execute("""
        INSERT INTO approval_requests
        (company_id, requester_id, request_type, target_type, target_id,
         current_value, requested_value, reason, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
    """, (company_id, requester_id, request_type, target_type, target_id,
          current_value, requested_value, reason, datetime.now().isoformat()))
    
    request_id = c.lastrowid
    conn.commit()
    conn.close()
    
    # Create notification for admins
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE company_id = ? AND role IN ('admin', 'manager')",
              (company_id,))
    admins = c.fetchall()
    for admin in admins:
        create_notification(admin[0], company_id,
                           f"New {request_type} request",
                           f"User requested to {request_type} {target_type} #{target_id}",
                           "approval_needed", request_id)
    conn.close()
    
    return request_id


def get_pending_approval_requests(company_id: int) -> pd.DataFrame:
    """Get pending approval requests for admin"""
    
    conn = sqlite3.connect(DB_PATH)
    query = """
        SELECT ar.*, u.username as requester_name
        FROM approval_requests ar
        JOIN users u ON ar.requester_id = u.id
        WHERE ar.company_id = ? AND ar.status = 'pending'
        ORDER BY ar.created_at DESC
    """
    df = pd.read_sql_query(query, conn, params=(company_id,))
    conn.close()
    return df


def approve_request(request_id: int, admin_id: int, admin_notes: str = "") -> tuple:
    """Approve a request and execute the action"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get request details
    c.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,))
    request = c.fetchone()
    
    if not request:
        conn.close()
        return False, "Request not found"
    
    request_type = request[3]
    target_type = request[4]
    target_id = request[5]
    requested_value = request[7]
    company_id = request[1]
    requester_id = request[2]

    # The acting admin must belong to the same company as the request --
    # otherwise an admin could approve (and execute) a request that targets
    # another company's scheduled_jobs by passing in a foreign request_id.
    c.execute("SELECT company_id FROM users WHERE id = ?", (admin_id,))
    admin_row = c.fetchone()
    if not admin_row or admin_row[0] != company_id:
        conn.close()
        return False, "Not authorized to approve this request"

    # Execute the approved action
    success = False
    if request_type == 'delete_event' and target_type == 'scheduled_job':
        c.execute("DELETE FROM scheduled_jobs WHERE id = ? AND company_id = ?", (target_id, company_id))
        success = True
    elif request_type == 'move_event' and target_type == 'scheduled_job':
        # Parse requested_value (e.g., "2024-01-15|10:00 AM")
        if requested_value:
            try:
                new_date, new_time = requested_value.split('|')
                c.execute("UPDATE scheduled_jobs SET scheduled_date = ?, scheduled_time = ? WHERE id = ? AND company_id = ?",
                          (new_date, new_time, target_id, company_id))
                success = True
            except ValueError:
                success = False
    elif request_type == 'edit_event' and target_type == 'scheduled_job':
        if requested_value:
            c.execute("UPDATE scheduled_jobs SET notes = ? WHERE id = ? AND company_id = ?",
                      (requested_value, target_id, company_id))
            success = True

    # Update request status
    c.execute("""
        UPDATE approval_requests
        SET status = 'approved', reviewed_at = ?, reviewed_by = ?, admin_notes = ?
        WHERE id = ? AND company_id = ?
    """, (datetime.now().isoformat(), admin_id, admin_notes, request_id, company_id))
    
    conn.commit()
    conn.close()
    
    # Notify requester
    if success:
        create_notification(requester_id, company_id,
                           f"Your {request_type} request was approved",
                           f"Admin approved your request to {request_type} {target_type} #{target_id}",
                           "request_approved", request_id)
    
    return success, "Request approved and executed" if success else "Request approved but action failed"


def reject_request(request_id: int, admin_id: int, reason: str) -> bool:
    """Reject a request"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Get requester info for notification
    c.execute("SELECT requester_id, company_id FROM approval_requests WHERE id = ?", (request_id,))
    request = c.fetchone()

    c.execute("SELECT company_id FROM users WHERE id = ?", (admin_id,))
    admin_row = c.fetchone()
    if not request or not admin_row or admin_row[0] != request[1]:
        conn.close()
        return False

    c.execute("""
        UPDATE approval_requests
        SET status = 'rejected', reviewed_at = ?, reviewed_by = ?, admin_notes = ?
        WHERE id = ? AND company_id = ?
    """, (datetime.now().isoformat(), admin_id, reason, request_id, request[1]))
    
    conn.commit()
    conn.close()
    
    if request:
        create_notification(request[0], request[1],
                           f"Your request was rejected",
                           f"Reason: {reason}",
                           "request_rejected", request_id)
    
    return True


# ============================================================
# ACTIVITY LOGGING
# ============================================================

def log_activity(company_id: int, user_id: int, action: str, target_type: str = None,
                target_id: int = None, details: str = None):
    """Log user activity for audit trail"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO activity_log (company_id, user_id, action, target_type, target_id, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, user_id, action, target_type, target_id, details, datetime.now().isoformat()))
    conn.commit()
    conn.close()


def log_error_event(error_type: str, error_message: str, page_url: str = None, stack_trace: str = None):
    """Log an unhandled error so the 'Errors (24h)' metric on the Super Admin
    dashboard reflects something real instead of always reading 0."""
    user = st.session_state.get('user') if hasattr(st, 'session_state') else None
    company_id = user.get('company_id') if user else None
    user_id = user.get('user_id') if user else None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO error_logs (company_id, user_id, error_type, error_message, page_url, stack_trace, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (company_id, user_id, error_type, error_message, page_url, stack_trace, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    except Exception:
        pass


# ============================================================
# NOTIFICATION SYSTEM
# ============================================================

def create_notification(user_id: int, company_id: int, title: str, message: str, 
                        notification_type: str, related_id: int = None) -> int:
    """Create a new notification for a user"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO notifications (user_id, company_id, title, message, notification_type, related_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, company_id, title, message, notification_type, related_id, datetime.now().isoformat()))
    notification_id = c.lastrowid
    conn.commit()
    conn.close()
    return notification_id

def get_user_notifications(user_id: int, limit: int = 20) -> pd.DataFrame:
    """Get notifications for a user"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, title, message, notification_type, related_id, read_status, created_at
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
    """, conn, params=(user_id, limit))
    conn.close()
    return df

def mark_notification_read(notification_id: int, user_id: int):
    """Mark a notification as read"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE notifications SET read_status = 1 WHERE id = ? AND user_id = ?", (notification_id, user_id))
    conn.commit()
    conn.close()

def get_unread_notification_count(user_id: int) -> int:
    """Get count of unread notifications"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Safe: user_id is unique per user, and users are scoped to companies
    c.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_status = 0", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count


# ============================================================
# EMAIL SYSTEM
# ============================================================

def get_smtp_settings(company_id: int):
    ensure_business_profile_schema(company_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT smtp_email, smtp_password, smtp_server, smtp_port FROM business_profile WHERE company_id = ?", (company_id,))
    row = c.fetchone()
    conn.close()

    if not row:
        return {
            "smtp_email": "",
            "smtp_password": "",
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
        }

    # Decrypt SMTP password
    encrypted_password = row[1] or ""
    decrypted_password = ""
    if encrypted_password:
        try:
            from encryption_manager import encryption
            decrypted_password = encryption.decrypt(encrypted_password)
        except Exception:
            # If decryption fails, assume it's plain text (for migration)
            decrypted_password = encrypted_password

    return {
        "smtp_email": row[0] or "",
        "smtp_password": decrypted_password,
        "smtp_server": row[2] or "smtp.gmail.com",
        "smtp_port": int(row[3]) if row[3] else 587,
    }


def get_last_email_error() -> Optional[str]:
    return LAST_EMAIL_ERROR


def send_email(company_id: int, to_email: str, subject: str, body: str, html_body: str = None) -> bool:
    """Send email using company's SMTP settings"""
    global LAST_EMAIL_ERROR
    LAST_EMAIL_ERROR = None

    smtp_settings = get_smtp_settings(company_id)
    smtp_email = smtp_settings["smtp_email"]
    smtp_password = smtp_settings["smtp_password"]
    smtp_server = smtp_settings["smtp_server"]
    smtp_port = smtp_settings["smtp_port"]

    if not smtp_email or not smtp_password:
        LAST_EMAIL_ERROR = (
            "SMTP is not fully configured. Enter SMTP Email and SMTP Password in Business Settings, "
            "then save and retry."
        )
        print(LAST_EMAIL_ERROR)
        return False

    try:
        # Removed debug logging for security
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_email
        msg['To'] = to_email
        msg['Subject'] = subject

        msg.attach(MIMEText(body, 'plain'))

        if html_body:
            msg.attach(MIMEText(html_body, 'html'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            # Disabled debug mode for security
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()
        LAST_EMAIL_ERROR = None
        return True
    except Exception as e:
        LAST_EMAIL_ERROR = (
            f"SMTP send failed using {smtp_server}:{smtp_port} from {smtp_email}. "
            f"Error: {e}"
        )
        print(LAST_EMAIL_ERROR)
        return False

def test_smtp_connection(company_id: int, test_email: str) -> tuple[bool, str]:
    smtp_settings = get_smtp_settings(company_id)
    smtp_email = smtp_settings["smtp_email"]
    smtp_password = smtp_settings["smtp_password"]
    smtp_server = smtp_settings["smtp_server"]
    smtp_port = smtp_settings["smtp_port"]

    if not smtp_email or not smtp_password:
        return False, "SMTP credentials not configured. Please enter your SMTP Email and Password in Business Settings."

    try:
        msg = MIMEMultipart('alternative')
        msg['From'] = smtp_email
        msg['To'] = test_email
        msg['Subject'] = "ProfitClean SMTP Test - Successful!"

        body = f"""
Hello!

This is a test email from your ProfitClean application.

SMTP Configuration:
- Server: {smtp_server}:{smtp_port}
- From: {smtp_email}
- To: {test_email}

✅ Your email settings are working correctly!

You can now send estimates, approvals, and reminders to your clients.

- ProfitClean System
"""
        html_body = f"""
<html>
<body>
    <h2>✅ SMTP Test Successful!</h2>
    <p>This is a test email from your ProfitClean application.</p>
    <hr>
    <p><strong>SMTP Configuration:</strong><br>
    - Server: {smtp_server}:{smtp_port}<br>
    - From: {smtp_email}<br>
    - To: {test_email}</p>
    <p>Your email settings are working correctly!</p>
    <hr>
    <p style="color: green;">- ProfitClean System</p>
</body>
</html>
"""

        msg.attach(MIMEText(body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))

        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            server.ehlo()
            server.starttls()
            server.ehlo()

        server.login(smtp_email, smtp_password)
        server.send_message(msg)
        server.quit()
        return True, f"Test email sent successfully to {test_email}!"
    except Exception as e:
        return False, f"Failed: {e}"


def send_estimate_email(company_id: int, estimate_id: int, client_email: str, client_name: str, 
                        amount: float, approval_link: str) -> bool:
    """Send estimate approval email using template"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT subject, body FROM email_templates WHERE company_id = ? AND name = 'estimate_sent' AND is_active = 1", (company_id,))
    template = c.fetchone()
    c.execute("SELECT business_name FROM business_profile WHERE company_id = ?", (company_id,))
    business = c.fetchone()
    conn.close()
    
    business_name = business[0] if business else "ProfitClean"
    
    context = EmailContext(
        business_name=business_name,
        client_name=client_name,
        client_email=client_email,
        estimate_id=str(estimate_id),
        amount=amount,
        approval_link=approval_link
    )
    
    if template:
        subject = context.format_template(template[0])
        body = context.format_template(template[1])
    else:
        subject = f"Estimate from {business_name}"
        body = f"Dear {client_name},\n\nYour estimate is ${amount:,.2f}.\n\nApprove here: {approval_link}"
    
    html_body = f"""
    <html>
    <body>
        <h2>Estimate from {business_name}</h2>
        <p>Dear {client_name},</p>
        <p>Your estimate #{estimate_id} is ready for review.</p>
        <p style="font-size: 24px; font-weight: bold;">Amount: ${amount:,.2f}</p>
        <p><a href="{approval_link}" style="background-color: #10b981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Approve Estimate</a></p>
        <p>Thank you for your business!</p>
    </body>
    </html>
    """
    
    return send_email(company_id, client_email, subject, body, html_body)

def send_estimate_approved_email(company_id: int, estimate_id: int, client_email: str, client_name: str, amount: float) -> bool:
    """Send estimate approval confirmation email"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT subject, body FROM email_templates WHERE company_id = ? AND name = 'estimate_approved' AND is_active = 1", (company_id,))
    template = c.fetchone()
    c.execute("SELECT business_name FROM business_profile WHERE company_id = ?", (company_id,))
    business = c.fetchone()
    conn.close()
    
    business_name = business[0] if business else "ProfitClean"
    
    context = EmailContext(
        business_name=business_name,
        client_name=client_name,
        estimate_id=str(estimate_id),
        amount=amount
    )
    
    if template:
        subject = context.format_template(template[0])
        body = context.format_template(template[1])
    else:
        subject = f"Estimate Approved - {business_name}"
        body = f"Dear {client_name},\n\nYour estimate #{estimate_id} for ${amount:,.2f} has been approved.\n\nWe will contact you to schedule the service."
    
    return send_email(company_id, client_email, subject, body)

def send_job_reminder_email(company_id: int, job_id: int, client_email: str, client_name: str, 
                            job_date: str, job_time: str) -> bool:
    """Send job reminder email"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT subject, body FROM email_templates WHERE company_id = ? AND name = 'job_reminder' AND is_active = 1", (company_id,))
    template = c.fetchone()
    c.execute("SELECT business_name FROM business_profile WHERE company_id = ?", (company_id,))
    business = c.fetchone()
    conn.close()
    
    business_name = business[0] if business else "ProfitClean"
    
    context = EmailContext(
        business_name=business_name,
        client_name=client_name,
        date=job_date,
        time=job_time
    )
    
    if template:
        subject = context.format_template(template[0])
        body = context.format_template(template[1])
    else:
        subject = f"Upcoming Cleaning Appointment - {business_name}"
        body = f"Dear {client_name},\n\nThis is a reminder of your cleaning appointment on {job_date} at {job_time}.\n\nThank you!"
    
    return send_email(company_id, client_email, subject, body)


def send_password_reset_email(email: str, reset_link: str) -> bool:
    """Send password reset email"""
    subject = "Reset Your ProfitClean Password"
    body = f"""
Dear User,

You requested to reset your password. Click the link below to set a new password:

{reset_link}

This link will expire in 1 hour.

If you did not request this, please ignore this email.

- ProfitClean Team
"""
    # Use company_id 1 for system emails
    return send_email(1, email, subject, body)


def send_2fa_code_email(email: str, code: str) -> bool:
    """Send 2FA verification code email"""
    subject = "Your 2FA Verification Code"
    body = f"""
Dear User,

Your 2FA verification code is: {code}

This code will expire in 10 minutes.

If you did not request this, please ignore this email.

- ProfitClean Team
"""
    # Use company_id 1 for system emails
    return send_email(1, email, subject, body)


# ============================================================
# MULTI-TENANT & SUPPORT HELPERS
# ============================================================



def get_company_integration(company_id: int, integration_type: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT id, enabled, access_token, refresh_token, token_expires, settings, last_sync FROM company_integrations WHERE company_id = ? AND integration_type = ?",
        (company_id, integration_type)
    )
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    settings = json.loads(row[5]) if row[5] else {}
    # Decrypt any stored client_secret
    if settings.get("client_secret"):
        try:
            settings["client_secret"] = encryption.decrypt(settings["client_secret"])
        except Exception:
            # leave as-is if decryption fails
            pass
    return {
        "id": row[0],
        "enabled": bool(row[1]),
        "access_token": row[2],
        "refresh_token": row[3],
        "token_expires": row[4],
        "settings": settings,
        "last_sync": row[6]
    }


def list_company_integrations(company_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT integration_type, enabled, settings, last_sync FROM company_integrations WHERE company_id = ?",
        (company_id,)
    )
    rows = c.fetchall()
    conn.close()
    result = {}
    for row in rows:
        settings = json.loads(row[2]) if row[2] else {}
        if settings.get("client_secret"):
            try:
                settings["client_secret"] = encryption.decrypt(settings["client_secret"])
            except Exception:
                pass
        result[row[0]] = {
            "enabled": bool(row[1]),
            "settings": settings,
            "last_sync": row[3]
        }
    return result


def save_company_integration(company_id: int, integration_type: str, enabled: bool = False, access_token: str = None, refresh_token: str = None, token_expires: str = None, settings: dict = None, last_sync: str = None):
    existing = get_company_integration(company_id, integration_type)
    now = datetime.now().isoformat()
    # Encrypt sensitive settings (client_secret) before persisting
    settings_to_save = dict(settings or {})
    if settings_to_save.get("client_secret"):
        try:
            settings_to_save["client_secret"] = encryption.encrypt(settings_to_save["client_secret"])
        except Exception:
            pass
    settings_json = json.dumps(settings_to_save)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if existing:
        c.execute(
            "UPDATE company_integrations SET enabled = ?, access_token = ?, refresh_token = ?, token_expires = ?, settings = ?, last_sync = ?, updated_at = ? WHERE company_id = ? AND integration_type = ?",
            (1 if enabled else 0, access_token, refresh_token, token_expires, settings_json, last_sync, now, company_id, integration_type)
        )
    else:
        c.execute(
            "INSERT INTO company_integrations (company_id, integration_type, enabled, access_token, refresh_token, token_expires, settings, last_sync, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (company_id, integration_type, 1 if enabled else 0, access_token, refresh_token, token_expires, settings_json, last_sync, now, now)
        )
    conn.commit()
    conn.close()


def disable_company_integration(company_id: int, integration_type: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM company_integrations WHERE company_id = ? AND integration_type = ?", (company_id, integration_type))
    c.execute("DELETE FROM external_bookings WHERE company_id = ? AND integration_type = ?", (company_id, integration_type))
    conn.commit()
    conn.close()


def sync_integration(company_id: int, integration_type: str) -> int:
    if integration_type == "calendly":
        integration = CalendlyIntegration(company_id)
        return integration.sync()
    return 0


def integrations_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()

    # Role check: Only admins can access integrations
    user_role = st.session_state.get('user', {}).get('role')
    if user_role not in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
        st.error("❌ Access denied. Only company administrators can access integration settings.")
        st.info("Please contact your company administrator to connect Calendly or other integrations.")
        return

    st.markdown("### 🔌 Integration Hub")
    st.caption("Connect optional apps for your company. Tokens are stored per company and can be disconnected at any time.")

    company_id = get_current_user_company()
    if not company_id:
        st.warning("Unable to determine your company. Please refresh and try again.")
        return

    company_integrations = list_company_integrations(company_id)
    cols = st.columns(3)
    for idx, (key, integration) in enumerate(AVAILABLE_INTEGRATIONS.items()):
        with cols[idx % 3]:
            status = company_integrations.get(key, {}).get("enabled", False)
            last_sync = company_integrations.get(key, {}).get("last_sync")
            st.markdown(f"### {integration['icon']} {integration['name']}")
            st.write(integration['description'])
            st.write(f"**Status:** {'✅ Connected' if status else 'Not connected'}")
            if last_sync:
                st.caption(f"Last sync: {last_sync[:16]}")

            if status:
                if st.button(f"🔄 Sync", key=f"sync_{key}"):
                    with st.spinner(f"Syncing {integration['name']}..."):
                        result = sync_integration(company_id, key)
                        if result > 0:
                            st.success(f"Synced {result} new bookings!")
                        else:
                            st.info("No new bookings found.")
                        st.rerun()
                if st.button(f"❌ Disconnect", key=f"disconnect_{key}"):
                    disable_company_integration(company_id, key)
                    st.success(f"{integration['name']} disconnected.")
                    st.rerun()
            else:
                if integration['requires_oauth']:
                    if key == "calendly":
                        # Allow company admins to provide their own Calendly OAuth app credentials
                        company_int = get_company_integration(company_id, 'calendly') or {}
                        settings = company_int.get('settings', {})
                        user_role = st.session_state.get('user', {}).get('role')
                        if user_role in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
                            with st.expander("Admin: Configure Calendly OAuth app", expanded=False):
                                cid = st.text_input("Client ID", value=settings.get('client_id', ''), key=f"cal_cid_{company_id}")
                                csecret = st.text_input("Client Secret", value=settings.get('client_secret', ''), key=f"cal_csecret_{company_id}")
                                ruri = st.text_input("Redirect URI", value=settings.get('redirect_uri', ''), key=f"cal_ruri_{company_id}")
                                if st.button("Save OAuth credentials", key=f"save_cal_{company_id}"):
                                    save_company_integration(company_id, 'calendly', settings={'client_id': cid, 'client_secret': csecret, 'redirect_uri': ruri})
                                    st.success("Saved Calendly app credentials for this company.")
                                    st.rerun()

                        # Show connect button to initiate OAuth using company credentials if present
                        if st.button(f"🔌 Connect {integration['name']}", key=f"connect_{key}"):
                            st.session_state.page = "integrations_calendly_auth"
                            st.rerun()
                    else:
                        st.info("This integration will be available soon.")
                else:
                    st.info("This integration is not available yet.")


def calendly_oauth_page():
    # Role check: Only admins can access Calendly OAuth
    user_role = st.session_state.get('user', {}).get('role')
    if user_role not in (UserRole.SUPER_ADMIN.value, UserRole.ADMIN.value):
        st.error("❌ Access denied. Only company administrators can connect Calendly.")
        st.info("Please contact your company administrator to connect Calendly.")
        if st.button("← Back to Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
        return

    st.markdown("### 🔗 Connect Calendly")
    st.caption("Authorize Calendly for your company. You will be redirected back after granting access.")

    company_id = get_current_user_company()
    if not company_id:
        st.warning("Unable to determine your company. Please refresh and try again.")
        return

    integration = CalendlyIntegration(company_id)
    
    # Check if credentials are configured
    if not integration.has_required_credentials():
        st.error("🔧 Calendly OAuth is not configured")
        st.info("""
        **Setup required to enable Calendly integration:**
        
        1. **Create a Calendly OAuth Application**
           - Go to https://calendly.com/integrations/applications
           - Click "Create New Application"
           - Fill in app details
           - Set Redirect URI based on your environment:
             - Local: `http://localhost:8501`
             - Production: Your Streamlit Cloud app URL
           - Copy the Client ID and Secret
        
        2. **Add credentials to your environment**
           - **For local development:** Create `.streamlit/secrets.toml` with:
             ```
             CALENDLY_CLIENT_ID = "your_client_id"
             CALENDLY_CLIENT_SECRET = "your_client_secret"
             CALENDLY_REDIRECT_URI = "http://localhost:8501"
             ```
           - **For Streamlit Cloud:** Add these in Settings → Secrets
        
        3. **Restart the app** after adding credentials
        
        📖 See `CALENDLY_SETUP.md` for detailed instructions.
        """)
        if st.button("← Back to Integration Hub"):
            st.session_state.page = "integrations"
            st.rerun()
        return

    params = get_query_params_safely()
    code = parse_query_param(params, "code")
    state = parse_query_param(params, "state")

    if code and state:
        # Validate OAuth state for CSRF protection
        stored_state = st.session_state.get('oauth_state')
        if not stored_state or state != stored_state:
            st.error("❌ Invalid OAuth state. Possible CSRF attack detected.")
            st.session_state.page = "integrations"
            st.rerun()
            return
        
        with st.spinner("Connecting to Calendly..."):
            try:
                integration.exchange_code_for_token(code)
                st.success("✅ Successfully connected to Calendly!")
                st.balloons()
                set_query_params_safely()
                st.session_state.page = "integrations"
                st.rerun()
            except Exception as e:
                st.error(f"Failed to connect: {e}")
                if st.button("← Back to Integration Hub"):
                    st.session_state.page = "integrations"
                    st.rerun()
    else:
        # Generate and store random state for CSRF protection
        oauth_state = secrets.token_urlsafe(32)
        st.session_state['oauth_state'] = oauth_state
        
        try:
            auth_url = integration.get_oauth_url(state=oauth_state)
            st.code(f"Auth URL being sent: {auth_url}", language="text")
            st.markdown(
                f"<a href=\"{auth_url}\" target=\"_self\" style=\"display:inline-block;padding:10px 18px;border-radius:8px;background:#1f6feb;color:#fff;text-decoration:none;font-weight:600;\">Continue to Calendly</a>",
                unsafe_allow_html=True,
            )
            st.caption("After authorizing, Calendly will redirect you back automatically.")
        except Exception as e:
            st.error(f"Unable to start OAuth flow: {e}")

        if st.button("← Back to Integration Hub"):
            st.session_state.page = "integrations"
            st.rerun()


def calendly_callback_page():
    """Handle Calendly OAuth callback - redirects to calendly_oauth_page"""
    calendly_oauth_page()


def create_company(company_name, subdomain, owner_email, owner_username, owner_password, bypass_duplicate_email=False, make_super_admin=False):
    owner_email = normalize_email(owner_email)
    owner_username = owner_username.strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM companies WHERE subdomain = ?", (subdomain,))
    if c.fetchone():
        conn.close()
        return False, "Subdomain already taken"

    duplicate_email = False
    c.execute("SELECT id FROM users WHERE lower(email) = ?", (owner_email,))
    if c.fetchone():
        duplicate_email = True
        if not bypass_duplicate_email:
            conn.close()
            return False, "Email already registered"

    c.execute("INSERT INTO companies (name, subdomain, created_at, is_active) VALUES (?,?,?,?)",
              (company_name, subdomain, datetime.now().isoformat(), 1))
    company_id = c.lastrowid
    hashed, salt = hash_password(owner_password)
    invite_code = secrets.token_hex(4).upper()
    # super_admin can only be granted by the caller explicitly (the true
    # first-run bootstrap in setup_wizard, gated on company_count == 0) --
    # never derived from the email the caller typed, which any public
    # signup visitor controls.
    owner_role = "super_admin" if make_super_admin else "admin"

    fallback_email = f"{owner_email.split('@')[0]}+{company_id}@{owner_email.split('@', 1)[1]}" if duplicate_email else owner_email
    c.execute("""
        INSERT INTO users (username, email, password_hash, salt, role, company_id, can_manage_workers, is_active, approval_status, created_at, hire_date, invite_code)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (owner_username, fallback_email, hashed, salt, owner_role, company_id, 1, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat(), invite_code))
    owner_id = c.lastrowid
    c.execute("UPDATE companies SET owner_id = ? WHERE id = ?", (owner_id, company_id))
    c.execute("INSERT INTO business_profile (company_id, business_name, phone, email, hourly_wage, profit_target, min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (company_id, company_name, "(555) 000-0000", owner_email, 15.0, 0.30, 150, "Orlando", 0.65, SALES_TAX_RATE, 1))
    conn.commit()
    conn.close()
    return True, company_id

def create_support_staff(email, username, password):
    email = normalize_email(email)
    username = username.strip()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Support staff are global, so check globally for email uniqueness
    c.execute("SELECT id FROM users WHERE lower(email) = ?", (email,))
    if c.fetchone():
        conn.close()
        return False, "Email already exists"
    hashed, salt = hash_password(password)
    invite_code = secrets.token_hex(4).upper()
    c.execute("INSERT INTO users (username, email, password_hash, salt, role, company_id, can_manage_workers, is_active, approval_status, created_at, hire_date, invite_code) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
              (username, email, hashed, salt, "support_staff", 1, 0, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat(), invite_code))
    user_id = c.lastrowid
    conn.commit()
    conn.close()
    return True, user_id


# ============================================================
# HIERARCHICAL ACCESS HELPERS
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
        # NOTE: SQL's AND binds tighter than OR, so without parentheses this
        # parsed as "supervisor_id = ? OR (id = ? AND company_id = ?)" --
        # the supervisor_id branch wasn't scoped by company_id at all,
        # which could leak cross-tenant users if a supervisor_id value ever
        # collided across companies. Both branches are now scoped.
        c.execute(
            "SELECT id FROM users WHERE (supervisor_id = ? OR id = ?) AND company_id = ?",
            (current_user_id, current_user_id, current_user_company),
        )
        ids = [row[0] for row in c.fetchall()]
        conn.close()
        return ids
    else:
        return [current_user_id]

def user_belongs_to_hierarchy(current_user_id, target_user_id):
    return target_user_id in get_descendant_user_ids(current_user_id)




def request_password_reset(email):
    """Request password reset with 2FA verification"""
    import random
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Find user
    c.execute("SELECT id, username, email, totp_secret, totp_enabled FROM users WHERE email = ?", (email,))
    user = c.fetchone()

    if not user:
        conn.close()
        log_auth_event(None, email, "password_reset_request", "failure", error_message="No account with this email")
        return False, "If an account exists with this email, you will receive reset instructions."

    user_id, username, user_email, totp_secret, totp_enabled = user

    # Rate limit: at most 3 reset requests per hour per account
    one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
    c.execute("""
        SELECT COUNT(*) FROM password_reset_tokens
        WHERE user_id = ? AND created_at > ?
    """, (user_id, one_hour_ago))
    recent_requests = c.fetchone()[0]
    if recent_requests >= 3:
        conn.close()
        log_auth_event(user_id, email, "password_reset_request", "failure", error_message="Rate limit exceeded")
        return False, "Too many reset requests. Please try again later."

    # Generate reset token (expires in 1 hour)
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=1)
    
    # Store token
    c.execute("""
        INSERT INTO password_reset_tokens (user_id, token, expires_at, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, reset_token, expires_at.isoformat(), datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    # Generate reset link
    reset_link = f"https://profitclean-c4s6mqoafikfejkdfuwgvx.streamlit.app/reset_password?token={reset_token}"
    
    # If 2FA is enabled, send code via email
    if totp_enabled:
        # Generate and send 2FA code
        twofa_code = str(random.randint(100000, 999999))
        
        # Store 2FA code temporarily
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            UPDATE password_reset_tokens 
            SET verification_code = ? 
            WHERE token = ?
        """, (twofa_code, reset_token))
        conn.commit()
        conn.close()
        
        # Send 2FA code and the reset token/link via email. The "Set New
        # Password" form requires both the token and the code, so the token
        # must reach the user here too, not just the code.
        send_2fa_code_email(user_email, twofa_code)
        send_password_reset_email(user_email, reset_link)

        log_auth_event(user_id, email, "password_reset_request", "success", error_message="2FA code and reset link sent")
        return True, "A reset link and 2FA verification code have been sent to your email."
    else:
        # Send reset link directly
        send_password_reset_email(user_email, reset_link)

        log_auth_event(user_id, email, "password_reset_request", "success", error_message="Reset link sent")
        return True, "Password reset link has been sent to your email."


def reset_password_with_2fa(token, twofa_code, new_password):
    """Reset password with 2FA verification"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Verify token
    c.execute("""
        SELECT user_id, expires_at, verification_code, used, attempts
        FROM password_reset_tokens
        WHERE token = ? AND used = 0
    """, (token,))
    token_data = c.fetchone()

    if not token_data:
        conn.close()
        return False, "Invalid or expired reset token."

    user_id, expires_at, stored_code, used, attempts = token_data

    # Check expiration
    if datetime.fromisoformat(expires_at) < datetime.now():
        conn.close()
        return False, "Reset link has expired. Please request a new one."

    # Throttle verification attempts so a stolen/guessed token can't be
    # brute-forced against all 1,000,000 possible 6-digit codes.
    if (attempts or 0) >= MAX_RESET_CODE_ATTEMPTS:
        c.execute("UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        log_auth_event(user_id, None, "password_reset", "failure", error_message="Too many verification attempts")
        return False, "Too many attempts. Please request a new reset link."

    # Verify 2FA code (constant-time compare to avoid a timing side-channel)
    if stored_code and not hmac.compare_digest(stored_code, twofa_code or ""):
        c.execute("UPDATE password_reset_tokens SET attempts = attempts + 1 WHERE token = ?", (token,))
        conn.commit()
        conn.close()
        log_auth_event(user_id, None, "password_reset", "failure", error_message="Invalid 2FA verification code")
        return False, "Invalid 2FA verification code."
    
    # Validate new password
    valid, msg = validate_password_strength(new_password)
    if not valid:
        conn.close()
        return False, msg
    
    # Hash new password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(new_password.encode('utf-8'), salt)
    
    # Update password
    c.execute("""
        UPDATE users 
        SET password_hash = ?, salt = ?, login_attempts = 0, locked_until = NULL 
        WHERE id = ?
    """, (hashed.decode('utf-8'), salt.decode('utf-8'), user_id))
    
    # Mark token as used
    c.execute("UPDATE password_reset_tokens SET used = 1 WHERE token = ?", (token,))
    
    conn.commit()
    conn.close()

    # Invalidate any existing sessions (e.g. a stolen/leaked token) now that
    # the password has changed.
    force_logout_sessions(user_id)

    log_auth_event(user_id, None, "password_reset", "success", None, None, "Password reset via 2FA")

    return True, "Password reset successfully. Please log in with your new password."


def generate_approval_token(estimate_id: int, company_id: int, expires_hours: int = 24) -> str:
    """Generate and store a secure approval token for an estimate"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=expires_hours)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO estimate_approval_tokens (estimate_id, company_id, token, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (estimate_id, company_id, token, expires_at.isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    
    return token


def validate_approval_token(token: str):
    """Validate an approval token and return estimate data"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT eat.estimate_id, eat.company_id, eat.expires_at, eat.used, e.status
        FROM estimate_approval_tokens eat
        JOIN estimates e ON eat.estimate_id = e.id
        WHERE eat.token = ?
    """, (token,))
    token_data = c.fetchone()
    conn.close()
    
    if not token_data:
        return None, "Invalid approval token"
    
    estimate_id, company_id, expires_at, used, status = token_data
    
    # Check if already used
    if used:
        return None, "This approval link has already been used"
    
    # Check expiration
    if datetime.fromisoformat(expires_at) < datetime.now():
        return None, "Approval link has expired"
    
    # Check if estimate is already approved
    if status == 'approved':
        return None, "This estimate has already been approved"
    
    return {
        "estimate_id": estimate_id,
        "company_id": company_id
    }, None


def approve_estimate_with_token(token: str):
    """Approve an estimate using a valid token"""
    estimate_data, error = validate_approval_token(token)
    if error:
        return False, error
    
    estimate_id = estimate_data["estimate_id"]
    company_id = estimate_data["company_id"]
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Update estimate status
    c.execute("UPDATE estimates SET status = 'approved', approved_at = ? WHERE id = ?", 
              (datetime.now().isoformat(), estimate_id))
    
    # Mark token as used
    c.execute("UPDATE estimate_approval_tokens SET used = 1 WHERE token = ?", (token,))
    
    conn.commit()
    conn.close()
    
    log_audit(None, "estimate_approved", f"Estimate {estimate_id} approved via token")

    return True, "Estimate approved successfully"


# ============================================================
# CLIENT PORTAL AUTHENTICATION
# ============================================================

def generate_client_portal_token(client_id: int, expires_hours: int = 24) -> str:
    """Generate and store a token for a client to set up or reset their portal password"""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(hours=expires_hours)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO client_portal_tokens (client_id, token, expires_at, created_at)
        VALUES (?, ?, ?, ?)
    """, (client_id, token, expires_at.isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return token


def validate_client_portal_token(token: str):
    """Validate a client portal token and return the client_id"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT client_id, expires_at, used FROM client_portal_tokens WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()

    if not row:
        return None, "Invalid portal access link"

    client_id, expires_at, used = row
    if used:
        return None, "This link has already been used"
    if datetime.fromisoformat(expires_at) < datetime.now():
        return None, "This link has expired. Please request a new one."

    return client_id, None


def set_client_password(client_id: int, new_password: str, token: str = None):
    """Set or reset a client's portal password"""
    valid, msg = validate_password_strength(new_password)
    if not valid:
        return False, msg

    hashed, salt = hash_password(new_password)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE clients SET password_hash = ?, salt = ?, portal_enabled = 1 WHERE id = ?",
              (hashed, salt, client_id))
    if token:
        c.execute("UPDATE client_portal_tokens SET used = 1 WHERE token = ?", (token,))
    conn.commit()
    conn.close()
    return True, "Password set successfully"


def send_client_portal_setup_email(company_id: int, client_email: str, client_name: str, setup_link: str) -> bool:
    """Send a client a link to set up or reset their portal password"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT business_name FROM business_profile WHERE company_id = ?", (company_id,))
    business = c.fetchone()
    conn.close()
    business_name = business[0] if business else "ProfitClean"

    subject = f"Set up your client portal access - {business_name}"
    body = f"""Dear {client_name},

Click the link below to set up (or reset) your password for the {business_name} client portal:

{setup_link}

This link will expire in 24 hours. If you did not request this, please ignore this email.
"""
    html_body = f"""
    <html><body>
        <h2>Set Up Your Client Portal Access</h2>
        <p>Dear {client_name},</p>
        <p>Click the button below to set up (or reset) your password for the {business_name} client portal:</p>
        <p><a href="{setup_link}" style="background-color: #10b981; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">Set Password</a></p>
        <p>This link will expire in 24 hours. If you did not request this, please ignore this email.</p>
    </body></html>
    """
    return send_email(company_id, client_email, subject, body, html_body)


def authenticate_client(email: str, password: str):
    """Authenticate a client for the client portal. Returns (success, client_dict_or_error_message).

    Email is not unique across companies, so a single email may match multiple
    client rows (different companies). The password is used to disambiguate:
    each candidate row is checked, and the first one whose password matches wins.
    This avoids silently logging the client into the wrong company's record.
    """
    email = normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, business_name, company_id, password_hash, portal_enabled FROM clients WHERE email = ?", (email,))
    candidates = c.fetchall()
    conn.close()

    if not candidates:
        return False, "Invalid email or password"

    any_portal_set_up = False
    for client_id, business_name, company_id, password_hash, portal_enabled in candidates:
        if not portal_enabled or not password_hash:
            continue
        any_portal_set_up = True
        if verify_password(password, password_hash):
            return True, {
                "client_id": client_id,
                "business_name": business_name,
                "company_id": company_id,
                "email": email,
            }

    if not any_portal_set_up:
        return False, "PORTAL_NOT_SET_UP"

    return False, "Invalid email or password"


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
# EXPORT / IMPORT HELPERS
# ============================================================

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

def create_full_system_backup():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(BACKUP_DIR, f"full_system_backup_{timestamp}.json")
    
    conn = sqlite3.connect(DB_PATH)
    
    backup_data = {
        "version": "2.0",
        "backup_date": datetime.now().isoformat(),
        "data": {}
    }
    
    tables = ["companies", "users", "clients", "estimates", "scheduled_jobs", 
              "inspections", "quick_jobs", "monthly_expenses", "supplies", 
              "team_messages", "support_tickets", "worker_certifications", 
              "worker_badges", "worker_transfers", "audit_log", "business_profile",
              "notifications", "estimate_history", "client_communications"]
    
    for table in tables:
        try:
            df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
            backup_data["data"][table] = df.to_dict('records')
        except:
            backup_data["data"][table] = []
    
    conn.close()
    
    with open(backup_file, 'w') as f:
        json.dump(backup_data, f, indent=2, default=str)
    
    return backup_file


# ============================================================
# ESTIMATE HISTORY TRACKING
# ============================================================

def add_estimate_history_entry(estimate_id: int, status_from: str, status_to: str, changed_by: int, notes: str = ""):
    """Add an entry to estimate history timeline"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO estimate_history (estimate_id, status_from, status_to, changed_by, notes, changed_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (estimate_id, status_from, status_to, changed_by, notes, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def get_estimate_history(estimate_id: int) -> pd.DataFrame:
    """Get estimate history timeline"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT eh.*, u.username as changed_by_name
        FROM estimate_history eh
        LEFT JOIN users u ON eh.changed_by = u.id
        WHERE eh.estimate_id = ?
        ORDER BY eh.changed_at
    """, conn, params=(estimate_id,))
    conn.close()
    return df


# ============================================================
# JOB TEMPLATE FUNCTIONS
# ============================================================

def create_job_template(company_id: int, name: str, description: str, property_type: str, 
                        estimated_hours: float, task_list: List[str]) -> int:
    """Create a job template for recurring jobs"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO job_templates (company_id, name, description, property_type, estimated_hours, task_list, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (company_id, name, description, property_type, estimated_hours, json.dumps(task_list), datetime.now().isoformat()))
    template_id = c.lastrowid
    conn.commit()
    conn.close()
    return template_id

def get_job_templates(company_id: int) -> pd.DataFrame:
    """Get all job templates for a company"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM job_templates WHERE company_id = ? ORDER BY name", conn, params=(company_id,))
    conn.close()
    return df
def estimate_toll(origin, dest):
    key = (origin.lower(), dest.lower())
    return KNOWN_TOLLS.get(key, 5.00)


def estimate_toll_cost(origin, dest):
    """Alias for tests and backward compatibility."""
    return estimate_toll(origin, dest)


# ============================================================
# ENHANCED PRICING CALCULATION WITH 4 TIERS
# ============================================================

# ============================================================
# INTERNAL CALCULATOR #1: COST-BASED (Location + Square Footage)
# ============================================================

def calculator_cost_based(city, prop_type, sqft, bedrooms, bathrooms, freq, complexity, travel_miles):
    """INTERNAL: Based on location, square footage, and industry standards"""
    
    coastal = ["Cocoa Beach", "Daytona Beach", "Naples", "Fort Myers", "Sarasota", "Miami Beach", "Palm Beach"]
    rural = ["Ocala", "Gainesville", "Lake City", "Sebring", "Palatka", "Arcadia"]
    major_metros = ["Miami", "Orlando", "Tampa", "Jacksonville", "St. Petersburg"]
    
    if city in major_metros:
        zone_mult, travel_fee, zone_name = 1.25, 65, "Major Metro"
    elif city in coastal:
        zone_mult, travel_fee, zone_name = 1.18, 55, "Coastal"
    elif city in rural:
        zone_mult, travel_fee, zone_name = 1.10, 45, "Rural"
    else:
        zone_mult, travel_fee, zone_name = 1.0, 45, "Standard"
    
    prop = PROPERTY_TYPES.get(prop_type, {"multiplier": 1.0, "base_rate": 0.14})
    prop_mult = prop["multiplier"]
    base_rate = prop["base_rate"]
    freq_mult = FREQUENCIES.get(freq, 1.0)
    comp_factor = 0.6 + (complexity / 10)
    
    if prop_type == "🏠 Airbnb / Short-Term Rental":
        room_price = 45 if city in major_metros else 35
        bathroom_price = 25 if city in major_metros else 20
        base_price = ((bedrooms * room_price) + (bathrooms * bathroom_price)) * prop_mult * comp_factor
        pricing_model = "Per Room"
    else:
        adjusted_rate = base_rate * zone_mult * prop_mult * freq_mult * comp_factor
        base_price = sqft * adjusted_rate
        pricing_model = "Per Square Foot"
    
    travel_cost = (travel_miles * 0.65) + travel_fee
    tolls = 5.00
    
    total = base_price + travel_cost + tolls
    
    return {
        "total": math.ceil(total),
        "breakdown": {
            "base_price": round(base_price, 2),
            "zone_multiplier": zone_mult,
            "zone_name": zone_name,
            "prop_multiplier": prop_mult,
            "frequency_multiplier": freq_mult,
            "complexity_factor": round(comp_factor, 2),
            "travel_cost": round(travel_cost, 2),
            "tolls": tolls,
            "pricing_model": pricing_model
        }
    }


# ============================================================
# INTERNAL CALCULATOR #2: MARKET-BASED (Real-time Fair Value)
# ============================================================

# Fair market rates for line-item services
FAIR_MARKET_RATES = {
    "vacuum_carpet": {"rate": 0.05, "unit": "sqft", "min_charge": 25},
    "mop_tile": {"rate": 0.08, "unit": "sqft", "min_charge": 35},
    "clean_hardwood": {"rate": 0.12, "unit": "sqft", "min_charge": 50},
    "toilet": {"rate": 3.50, "unit": "each", "min_charge": 10},
    "sink_counter": {"rate": 4.00, "unit": "each", "min_charge": 15},
    "mirror": {"rate": 2.00, "unit": "each", "min_charge": 10},
    "interior_window": {"rate": 3.00, "unit": "each", "min_charge": 50},
    "high_dust": {"rate": 25.00, "unit": "per_1000_sqft", "min_charge": 50},
    "desk_clean": {"rate": 2.00, "unit": "each", "min_charge": 25},
    "empty_trash": {"rate": 1.50, "unit": "each", "min_charge": 15},
    "disinfection": {"rate": 0.03, "unit": "sqft", "min_charge": 50},
}

def calculator_market_based(city, prop_type, sqft, bedrooms, bathrooms, selected_services=None):
    """INTERNAL: Based on real-time fair market rates"""
    
    major_metros = ["Miami", "Orlando", "Tampa", "Jacksonville", "St. Petersburg"]
    coastal = ["Cocoa Beach", "Daytona Beach", "Naples", "Fort Myers", "Sarasota"]
    rural = ["Ocala", "Gainesville", "Lake City", "Sebring"]
    
    market_rates = {
        "major_metro": {"min": 0.16, "avg": 0.22, "max": 0.30, "confidence": "High"},
        "coastal": {"min": 0.14, "avg": 0.19, "max": 0.26, "confidence": "High"},
        "standard": {"min": 0.12, "avg": 0.16, "max": 0.22, "confidence": "Medium"},
        "rural": {"min": 0.10, "avg": 0.14, "max": 0.18, "confidence": "Medium"}
    }
    
    if city in major_metros:
        zone = "major_metro"
    elif city in coastal:
        zone = "coastal"
    elif city in rural:
        zone = "rural"
    else:
        zone = "standard"
    
    zone_rates, service_rates = load_global_market_rate_overrides()
    rates = zone_rates.get(zone, market_rates[zone])
    prop_mult = PROPERTY_TYPES.get(prop_type, {"multiplier": 1.0})["multiplier"]
    
    if sqft > 0:
        market_min = sqft * rates["min"] * prop_mult
        market_avg = sqft * rates["avg"] * prop_mult
        market_max = sqft * rates["max"] * prop_mult
    else:
        market_min = bedrooms * 35 * prop_mult
        market_avg = bedrooms * 45 * prop_mult
        market_max = bedrooms * 60 * prop_mult
    
    line_item_total = 0
    if selected_services:
        for service in selected_services:
            item = service.get('item')
            quantity = service.get('quantity', 1)
            if item in service_rates:
                rate_data = service_rates[item]
                line_item_total += rate_data['rate'] * quantity
        
        if len(selected_services) >= 5:
            bundle_discount = line_item_total * 0.05
            line_item_total -= bundle_discount
        
        market_avg = max(market_avg, line_item_total)
    
    return {
        "min": math.ceil(market_min),
        "avg": math.ceil(market_avg),
        "max": math.ceil(market_max),
        "zone": zone,
        "confidence": rates["confidence"],
        "line_item_total": round(line_item_total, 2) if selected_services else 0
    }


# ============================================================
# INTERNAL CALCULATOR #3: EXPENSE-BASED (Business Health)
# ============================================================

def calculator_expense_based(company_id, labor_hours):
    """INTERNAL: Based on business expenses and what's needed to stay afloat"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("PRAGMA table_info(business_profile)")
    existing_cols = [col[1] for col in c.fetchall()]
    
    expense_cols = ['monthly_rent', 'monthly_insurance', 'monthly_vehicles', 'monthly_marketing', 'monthly_software', 'monthly_admin_salary', 'desired_profit_margin']
    for col in expense_cols:
        if col not in existing_cols:
            try:
                c.execute(f"ALTER TABLE business_profile ADD COLUMN {col} REAL DEFAULT 0")
            except:
                pass
    
    c.execute("""
        SELECT monthly_rent, monthly_insurance, monthly_vehicles, 
               monthly_marketing, monthly_software, monthly_admin_salary,
               desired_profit_margin, hourly_wage, min_job_fee
        FROM business_profile WHERE company_id = ?
    """, (company_id,))
    row = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM users WHERE company_id = ? AND role = 'worker' AND is_active = 1", (company_id,))
    worker_count = c.fetchone()[0]
    conn.close()
    
    if not row:
        return {"error": "Expense data not configured", "min_viable": 150, "healthy_price": 200}
    
    monthly_fixed_costs = sum(row[:6]) if row[:6] else 0
    desired_profit_margin = row[6] if row[6] else 0.20
    # Guard against a margin of 100% or more (e.g. a user entering "100" as
    # a whole-number percent instead of "1.00" as a fraction, or just a bad
    # value getting saved). Without this, "true_cost / (1 - margin)" below
    # divides by zero or goes negative, crashing or showing a nonsensical
    # "healthy price" on this profit-tracking app's core dashboard.
    if desired_profit_margin >= 1:
        desired_profit_margin = 0.95
    elif desired_profit_margin < 0:
        desired_profit_margin = 0
    hourly_wage = row[7] if row[7] else 15.0
    min_job_fee = row[8] if row[8] else 150
    
    if worker_count == 0:
        worker_count = 1
    
    billable_hours_per_month = worker_count * 160
    required_hourly_break_even = monthly_fixed_costs / billable_hours_per_month if billable_hours_per_month > 0 else 0
    total_monthly_target = monthly_fixed_costs * (1 + desired_profit_margin)
    required_hourly_profit = total_monthly_target / billable_hours_per_month if billable_hours_per_month > 0 else 0
    
    labor_cost = labor_hours * required_hourly_profit
    materials_cost = labor_hours * 5
    overhead_cost = labor_hours * (required_hourly_break_even * 0.15)
    
    true_cost = labor_cost + materials_cost + overhead_cost
    if true_cost < min_job_fee:
        true_cost = min_job_fee
    
    min_viable = math.ceil(true_cost)
    healthy_price = math.ceil(true_cost / (1 - desired_profit_margin))
    
    return {
        "min_viable": min_viable,
        "healthy_price": healthy_price,
        "breakdown": {
            "monthly_fixed_costs": monthly_fixed_costs,
            "worker_count": worker_count,
            "billable_hours_per_month": billable_hours_per_month,
            "required_hourly_break_even": round(required_hourly_break_even, 2),
            "required_hourly_profit": round(required_hourly_profit, 2),
            "desired_profit_margin": f"{desired_profit_margin * 100}%",
            "labor_cost": round(labor_cost, 2),
            "materials_cost": round(materials_cost, 2),
            "overhead_cost": round(overhead_cost, 2)
        },
        "business_health": {
            # Was backwards: prices in (250, 350] evaluated to "Struggling"
            # while prices > 350 evaluated to "At Risk", so a $300 price
            # read as worse than a $400 price. Bands now escalate in order.
            "status": "Healthy" if healthy_price <= 250 else "At Risk" if healthy_price <= 350 else "Struggling",
            "recommendation": "Increase efficiency or raise prices" if healthy_price > 300 else "On track"
        }
    }


# ============================================================
# MASTER PRICING ENGINE (Combines All Three)
# ============================================================

def calculate_complete_price(city, prop_type, sqft, bedrooms, bathrooms, freq, complexity, 
                              travel_miles, selected_services, company_id, labor_hours):
    """MASTER: Combines cost-based, market-based, and expense-based calculators"""
    
    cost_based = calculator_cost_based(city, prop_type, sqft, bedrooms, bathrooms, freq, complexity, travel_miles)
    market_based = calculator_market_based(city, prop_type, sqft, bedrooms, bathrooms, selected_services)
    expense_based = calculator_expense_based(company_id, labor_hours)
    
    if "error" in expense_based:
        expense_based = {"min_viable": 150, "healthy_price": 200, "breakdown": {}, "business_health": {"status": "Unknown", "recommendation": "Configure expenses in settings"}}
    
    weighted_price = (market_based['avg'] * 0.40) + (cost_based['total'] * 0.35) + (expense_based['healthy_price'] * 0.25)
    sweet_spot = math.ceil(weighted_price)
    
    pricing_tiers = {
        "low": math.ceil(sweet_spot * 0.85),
        "sweet_spot": sweet_spot,
        "medium": math.ceil(sweet_spot * 1.10),
        "high": math.ceil(sweet_spot * 1.25)
    }
    
    if pricing_tiers["low"] < expense_based['min_viable']:
        pricing_tiers["low"] = expense_based['min_viable']
        pricing_tiers["sweet_spot"] = max(sweet_spot, expense_based['min_viable'] * 1.1)
    
    confidence = 70
    if market_based['confidence'] == "High":
        confidence += 10
    if expense_based['business_health']['status'] == "Healthy":
        confidence += 10
    expense_ratio = expense_based['healthy_price'] / market_based['avg'] if market_based['avg'] > 0 else 1
    if 0.85 <= expense_ratio <= 1.15:
        confidence += 10
    elif expense_ratio > 1.3:
        confidence -= 20
    
    tax_rate = get_global_setting("global.tax_rate", SALES_TAX_RATE)
    
    return {
        "customer_tiers": {
            "low": {
                "total": math.ceil(pricing_tiers["low"] * (1 + tax_rate)),
                "subtotal": pricing_tiers["low"],
                "margin": 12,
                "tax": math.ceil(pricing_tiers["low"] * (1 + tax_rate)) - pricing_tiers["low"]
            },
            "sweet_spot": {
                "total": math.ceil(pricing_tiers["sweet_spot"] * (1 + tax_rate)),
                "subtotal": pricing_tiers["sweet_spot"],
                "margin": 22,
                "tax": math.ceil(pricing_tiers["sweet_spot"] * (1 + tax_rate)) - pricing_tiers["sweet_spot"]
            },
            "medium": {
                "total": math.ceil(pricing_tiers["medium"] * (1 + tax_rate)),
                "subtotal": pricing_tiers["medium"],
                "margin": 32,
                "tax": math.ceil(pricing_tiers["medium"] * (1 + tax_rate)) - pricing_tiers["medium"]
            },
            "high": {
                "total": math.ceil(pricing_tiers["high"] * (1 + tax_rate)),
                "subtotal": pricing_tiers["high"],
                "margin": 45,
                "tax": math.ceil(pricing_tiers["high"] * (1 + tax_rate)) - pricing_tiers["high"]
            }
        },
        "internal": {
            "cost_based": cost_based,
            "market_based": market_based,
            "expense_based": expense_based,
            "weighted_price": weighted_price,
            "confidence_score": confidence,
            "true_cost": expense_based.get('min_viable', 150)
        }
    }


# ============================================================
# LEGACY FUNCTION (kept for compatibility - calls new system)
# ============================================================

def calculate_price_with_tiers(city, prop_type, sqft, bedrooms, bathrooms, freq, complexity, travel_miles, add_ons, holiday, num_locations, notice_hours, contract_months, company_id=None):
    """Legacy wrapper - calls the new comprehensive pricing system"""
    if company_id is None:
        company_id = get_current_user_company()
    
    if sqft > 0:
        labor_hours = (sqft / 500) * (0.6 + complexity/10)
    else:
        labor_hours = (bedrooms * 0.75) + (bathrooms * 0.5)
    
    if complexity >= 8:
        labor_hours *= 1.5
    elif complexity >= 6:
        labor_hours *= 1.25
    
    result = calculate_complete_price(
        city, prop_type, sqft, bedrooms, bathrooms, freq, complexity,
        travel_miles, [], company_id, labor_hours
    )
    
    return {
        "lowest": result["customer_tiers"]["low"],
        "fair": result["customer_tiers"]["medium"],
        "highest": result["customer_tiers"]["high"],
        "sweet_spot": result["customer_tiers"]["sweet_spot"],
        "true_cost": result["internal"]["true_cost"],
        "toll_estimate": 5.00,
        "add_on_total": 0,
        "labor_hours": labor_hours,
        "labor_cost": labor_hours * 15,
        "materials_cost": labor_hours * 5,
        "travel_cost": travel_miles * 0.65,
        "break_even": result["customer_tiers"]["low"],
        "fair_market": result["customer_tiers"]["medium"],
        "premium": result["customer_tiers"]["high"],
        "summary": {
            "total_cost": result["internal"]["true_cost"],
            "recommended_total": result["customer_tiers"]["sweet_spot"]["total"],
            "house_profit": result["customer_tiers"]["sweet_spot"]["subtotal"] - result["internal"]["true_cost"],
            "house_margin": result["customer_tiers"]["sweet_spot"]["margin"],
            "premium_vs_break_even": 50
        }
    }
# ============================================================

# ============================================================
# USER MANAGEMENT FUNCTIONS
# ============================================================

def create_user(username, email, password, role, company_id, manager_id=None, supervisor_id=None, ip_address=None):
    email = normalize_email(email)
    username = username.strip()
    valid, msg = validate_password_strength(password)
    if not valid:
        return False, msg
    hashed, salt = hash_password(password)
    invite_code = secrets.token_hex(4).upper()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, company_id, manager_id, supervisor_id, can_manage_workers, is_active, approval_status, created_at, hire_date, created_ip, invite_code)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (username, email, hashed, salt, role, company_id, manager_id, supervisor_id, 1 if role in ['admin','manager','super_admin','support_staff'] else 0, 1, 'approved', datetime.now().isoformat(), datetime.now().isoformat(), ip_address, invite_code))
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
        invite_code = secrets.token_hex(4).upper()
        c.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, company_id, manager_id, can_manage_workers, is_active, approval_status, created_at, hire_date, approved_by, approval_date, invite_code)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (name, email, pwd_hash, salt, "worker", company_id, manager_id, 0, 1, "approved", datetime.now().isoformat(), datetime.now().isoformat(), manager_id, datetime.now().isoformat(), invite_code))
        user_id = c.lastrowid
        c.execute("DELETE FROM pending_workers WHERE id = ?", (request_id,))
        conn.commit()
        log_audit(manager_id, "worker_approved", f"Approved worker {name} (ID {user_id}) for company {company_id}")
        create_notification(user_id, company_id, "Welcome aboard!", "Your account has been approved. You can now log in and access the system.", "account_approved")
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




def set_global_setting(name, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO global_settings (name, value, updated_at) VALUES (?,?,?)",
              (name, json.dumps(value), datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_global_settings():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name, value FROM global_settings")
    rows = c.fetchall()
    conn.close()
    settings = {}
    for name, value in rows:
        try:
            settings[name] = json.loads(value)
        except Exception:
            settings[name] = value
    return settings


def get_global_setting(name, default=None):
    settings = get_global_settings()
    return settings.get(name, default)


def ensure_business_profile_schema(company_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(business_profile)")
    existing_columns = [col[1] for col in c.fetchall()]

    required_columns = [
        ("smtp_email", "TEXT"),
        ("smtp_password", "TEXT"),
        ("smtp_server", "TEXT"),
        ("smtp_port", "INTEGER DEFAULT 587"),
        ("monthly_rent", "REAL DEFAULT 0"),
        ("monthly_insurance", "REAL DEFAULT 0"),
        ("monthly_vehicles", "REAL DEFAULT 0"),
        ("monthly_marketing", "REAL DEFAULT 0"),
        ("monthly_software", "REAL DEFAULT 0"),
        ("monthly_admin_salary", "REAL DEFAULT 0"),
        ("desired_profit_margin", "REAL DEFAULT 0.20"),
    ]

    for col_name, col_def in required_columns:
        if col_name not in existing_columns:
            try:
                c.execute(f"ALTER TABLE business_profile ADD COLUMN {col_name} {col_def}")
            except sqlite3.OperationalError:
                pass

    if company_id:
        c.execute("SELECT COUNT(*) FROM business_profile WHERE company_id = ?", (company_id,))
        if c.fetchone()[0] == 0:
            c.execute("SELECT name FROM companies WHERE id = ?", (company_id,))
            company_row = c.fetchone()
            company_name = company_row[0] if company_row else f"Company {company_id}"
            c.execute(
                "INSERT INTO business_profile (company_id, business_name, phone, email, hourly_wage, profit_target, min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (company_id, company_name, "(555) 000-0000", "", 15.0, 0.30, 150, "Orlando", 0.65, SALES_TAX_RATE, 0)
            )

    conn.commit()
    conn.close()


def send_test_email(smtp_server, smtp_port, smtp_email, smtp_password, to_email):
    """Send a simple test email using provided SMTP settings. Returns (success, error_message)."""
    try:
        smtp_port = int(smtp_port) if smtp_port is not None else 587
        server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
        server.ehlo()
        try:
            server.starttls()
            server.ehlo()
        except Exception:
            # Some SMTP servers don't support STARTTLS; continue
            pass
        if smtp_email and smtp_password:
            try:
                server.login(smtp_email, smtp_password)
            except Exception as e:
                server.quit()
                return False, f"SMTP login failed: {e}"

        msg = f"Subject: Test Email from ProfitClean\n\nThis is a test email sent at {datetime.now().isoformat()}"
        server.sendmail(smtp_email or f"no-reply@{smtp_server}", [to_email], msg)
        server.quit()
        return True, None
    except Exception as e:
        return False, str(e)


def load_global_market_rate_overrides():
    settings = get_global_settings()
    zone_rates = {
        "major_metro": {"min": 0.16, "avg": 0.22, "max": 0.30, "confidence": "High"},
        "coastal": {"min": 0.14, "avg": 0.19, "max": 0.26, "confidence": "High"},
        "standard": {"min": 0.12, "avg": 0.16, "max": 0.22, "confidence": "Medium"},
        "rural": {"min": 0.10, "avg": 0.14, "max": 0.18, "confidence": "Medium"}
    }
    for zone in zone_rates:
        for metric in ["min", "avg", "max"]:
            key = f"zone.{zone}.{metric}"
            if key in settings:
                zone_rates[zone][metric] = float(settings[key])

    service_rates = {k: v.copy() for k, v in FAIR_MARKET_RATES.items()}
    for setting_key, setting_value in settings.items():
        if setting_key.startswith("service."):
            _, service_name, field_name = setting_key.split(".")
            if service_name in service_rates:
                service_rates[service_name][field_name] = float(setting_value)

    return zone_rates, service_rates


def ensure_default_global_settings():
    defaults = {
        "global.tax_rate": 0.06,
        "global.default_hourly_wage": 15.0,
        "global.default_min_job_fee": 150,
        "zone.major_metro.min": 0.16,
        "zone.major_metro.avg": 0.22,
        "zone.major_metro.max": 0.30,
        "zone.coastal.min": 0.14,
        "zone.coastal.avg": 0.19,
        "zone.coastal.max": 0.26,
        "zone.standard.min": 0.12,
        "zone.standard.avg": 0.16,
        "zone.standard.max": 0.22,
        "zone.rural.min": 0.10,
        "zone.rural.avg": 0.14,
        "zone.rural.max": 0.18,
    }

    for name, value in defaults.items():
        if get_global_setting(name) is None:
            set_global_setting(name, value)


def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, email, role, company_id, manager_id, supervisor_id, is_active, approval_status FROM users WHERE id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {
        "user_id": row[0],
        "username": row[1],
        "email": row[2],
        "role": row[3],
        "company_id": row[4],
        "manager_id": row[5],
        "supervisor_id": row[6],
        "is_active": row[7],
        "approval_status": row[8]
    }


def force_logout_sessions(target_user_id=None):
    """Force-logout a specific user, or everyone if no target is given.

    Previously the "everyone" branch deleted WHERE expires_at > now(),
    i.e. only currently-active sessions -- the inverse comparator of
    clear_expired_sessions() (which correctly uses '<'). That happened to
    still force-logout everyone (since deleting the active sessions is
    exactly what logs people out), but it left already-expired session
    rows behind uncleaned, and read as a copy-paste inversion bug. Now it
    just deletes every session row for clarity: "force logout everyone"
    means everyone, expired rows included.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if target_user_id:
        c.execute("DELETE FROM sessions WHERE user_id = ?", (target_user_id,))
    else:
        c.execute("DELETE FROM sessions")
    conn.commit()
    deleted = c.rowcount
    conn.close()
    return deleted


def impersonate_user(target_user_id):
    target = get_user_by_id(target_user_id)
    if not target:
        return False, "User not found"
    if not target['is_active']:
        return False, "Cannot impersonate an inactive user"
    st.session_state.original_user = st.session_state.user
    target['role_override'] = True
    st.session_state.user = target
    return True, "Impersonation started"


def stop_impersonation():
    if st.session_state.get('original_user'):
        st.session_state.user = st.session_state.original_user
        st.session_state.original_user = None
        return True
    return False


def export_company_data(company_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM users WHERE company_id = ?", (company_id,))
    user_ids = [row[0] for row in c.fetchall()]
    user_placeholders = ','.join(['?' for _ in user_ids]) if user_ids else 'NULL'
    backup = {"company_id": company_id, "exported_at": datetime.now().isoformat(), "data": {}}

    def query_table(table, where_clause, params):
        c.execute(f"SELECT * FROM {table} {where_clause}", params)
        cols = [d[0] for d in c.description]
        return [dict(zip(cols, row)) for row in c.fetchall()]

    backup["data"]["companies"] = query_table("companies", "WHERE id = ?", (company_id,))
    backup["data"]["business_profile"] = query_table("business_profile", "WHERE company_id = ?", (company_id,))
    backup["data"]["users"] = query_table("users", "WHERE company_id = ?", (company_id,))
    backup["data"]["clients"] = query_table("clients", "WHERE company_id = ?", (company_id,))
    backup["data"]["estimates"] = query_table("estimates", "WHERE company_id = ?", (company_id,))
    backup["data"]["scheduled_jobs"] = query_table("scheduled_jobs", "WHERE company_id = ?", (company_id,))
    backup["data"]["quick_jobs"] = query_table("quick_jobs", "WHERE company_id = ?", (company_id,))
    backup["data"]["monthly_expenses"] = query_table("monthly_expenses", "WHERE company_id = ?", (company_id,))
    backup["data"]["job_templates"] = query_table("job_templates", "WHERE company_id = ?", (company_id,))
    backup["data"]["email_templates"] = query_table("email_templates", "WHERE company_id = ?", (company_id,))
    backup["data"]["notifications"] = query_table("notifications", "WHERE company_id = ?", (company_id,))
    if user_ids:
        backup["data"]["sessions"] = query_table("sessions", f"WHERE user_id IN ({user_placeholders})", tuple(user_ids))
        backup["data"]["audit_log"] = query_table("audit_log", f"WHERE user_id IN ({user_placeholders})", tuple(user_ids))
    else:
        backup["data"]["sessions"] = []
        backup["data"]["audit_log"] = []

    conn.close()
    return json.dumps(backup, default=str, indent=2)


def delete_user_profile(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM notifications WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM audit_log WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()




# ============================================================
# WORKER / CLIENT / JOB HELPERS
# ============================================================

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


def render_worker_transfer_ui(key_prefix):
    """Super-admin-only UI to move a worker/supervisor/manager to a different company.
    Shared between workers_page() and admin_companies_page() so the transfer logic lives in one place."""
    conn = sqlite3.connect(DB_PATH)
    workers_df = pd.read_sql_query("""
        SELECT u.id, u.username, u.email, u.role, u.company_id,
               c.name as current_company
        FROM users u
        LEFT JOIN companies c ON u.company_id = c.id
        WHERE u.role IN ('worker', 'supervisor', 'manager')
        ORDER BY u.username
    """, conn)
    companies_df = pd.read_sql_query("SELECT id, name FROM companies WHERE is_active = 1 ORDER BY name", conn)
    conn.close()

    if workers_df.empty:
        st.info("No workers found to transfer.")
        return
    if companies_df.empty:
        st.info("No active companies found.")
        return

    col1, col2 = st.columns(2)
    with col1:
        selected_worker = st.selectbox(
            "Select worker", workers_df['id'].tolist(),
            format_func=lambda x: f"{workers_df[workers_df['id']==x]['username'].iloc[0]} ({workers_df[workers_df['id']==x]['current_company'].iloc[0]})",
            key=f"{key_prefix}_worker_select",
        )
    with col2:
        dest_company = st.selectbox(
            "Destination company", companies_df['id'].tolist(),
            format_func=lambda x: companies_df[companies_df['id']==x]['name'].iloc[0],
            key=f"{key_prefix}_dest_select",
        )

    if st.button("Transfer Worker", key=f"{key_prefix}_btn"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT company_id FROM users WHERE id = ?", (selected_worker,))
            row = c.fetchone()
            from_company = row[0] if row else None
            c.execute("UPDATE users SET company_id = ? WHERE id = ?", (dest_company, selected_worker))
            c.execute("INSERT INTO worker_transfers (worker_id, from_company_id, to_company_id, transferred_by, transferred_at) VALUES (?,?,?,?,?)",
                      (selected_worker, from_company, dest_company, st.session_state.user['user_id'], datetime.now().isoformat()))
            c.execute("INSERT INTO audit_log (user_id, action, details, created_at) VALUES (?,?,?,?)",
                      (st.session_state.user['user_id'], 'transfer_worker', f'Worker {selected_worker} transferred from {from_company} to {dest_company}', datetime.now().isoformat()))
            conn.commit()
            conn.close()
            st.success("Worker transferred successfully")
            st.rerun()
        except Exception as e:
            conn.rollback()
            conn.close()
            st.error(f"Transfer failed: {e}")

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
    email = normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO clients (company_id, user_id, business_name, contact_name, phone, email, address, city, state, zip, lat, lon, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
              (company_id, uid, business, contact, phone, email, address, city, state, zipc, lat, lon, notes, datetime.now().isoformat(), datetime.now().isoformat()))
    cid = c.lastrowid
    conn.commit()
    conn.close()
    return cid

def update_client(cid, business, contact, phone, email, address, city, state, zipc, lat, lon, notes):
    company_id = get_current_user_company()
    email = normalize_email(email)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE clients SET business_name=?, contact_name=?, phone=?, email=?, address=?, city=?, state=?, zip=?, lat=?, lon=?, notes=?, updated_at=? WHERE id=? AND company_id=?",
              (business, contact, phone, email, address, city, state, zipc, lat, lon, notes, datetime.now().isoformat(), cid, company_id))
    conn.commit()
    conn.close()

def delete_client(cid):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM clients WHERE id = ? AND company_id = ?", (cid, company_id))
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
    
    if worker_id:
        create_notification(worker_id, company_id, "New Job Assigned", f"You have been assigned a job for {client_name} on {date.isoformat()} at {time_slot}", "job_assigned", job_id)
    
    return job_id

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


# ============================================================
# PERFORMANCE & BADGES FUNCTIONS
# ============================================================

def get_worker_performance(worker_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM scheduled_jobs WHERE assigned_worker_id = ? AND company_id = ? AND status = 'completed'", (worker_id, company_id))
    jobs = c.fetchone()[0]
    c.execute("SELECT SUM(profit) FROM quick_jobs WHERE user_id = ? AND company_id = ?", (worker_id, company_id))
    profit = c.fetchone()[0] or 0
    c.execute("SELECT SUM(hours) FROM quick_jobs WHERE user_id = ? AND company_id = ?", (worker_id, company_id))
    hours = c.fetchone()[0] or 0
    conn.close()
    return jobs, profit, hours

def award_badge(worker_id, badge_name, badge_icon="🏅"):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM worker_badges WHERE worker_id = ? AND badge_name = ? AND company_id = ?", (worker_id, badge_name, company_id))
    if not c.fetchone():
        c.execute("INSERT INTO worker_badges (company_id, worker_id, badge_name, badge_icon, earned_at) VALUES (?,?,?,?,?)", 
                  (company_id, worker_id, badge_name, badge_icon, datetime.now().isoformat()))
        conn.commit()
        create_notification(worker_id, company_id, "New Badge Earned!", f"Congratulations! You've earned the '{badge_name}' badge.", "badge_earned")
    conn.close()

def update_worker_badges(worker_id):
    jobs, profit, hours = get_worker_performance(worker_id)
    if jobs >= 1: award_badge(worker_id, "Rookie", "🌟")
    if jobs >= 10: award_badge(worker_id, "10 Jobs", "📊")
    if jobs >= 50: award_badge(worker_id, "50 Jobs", "🏆")
    if jobs >= 100: award_badge(worker_id, "100 Jobs", "💎")
    if hours >= 100: award_badge(worker_id, "100 Hours", "⏰")
    if hours >= 500: award_badge(worker_id, "500 Hours", "⚡")
    if profit >= 1000: award_badge(worker_id, "$1k Profit", "💰")
    if profit >= 5000: award_badge(worker_id, "$5k Profit", "💵")
    if profit >= 10000: award_badge(worker_id, "$10k Profit", "💎")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hire_date FROM users WHERE id = ?", (worker_id,))
    row = c.fetchone()
    if row:
        hire = datetime.fromisoformat(row[0])
        years = (datetime.now() - hire).days / 365.25
        if years >= 1: award_badge(worker_id, "1 Year", "🎂")
        if years >= 2: award_badge(worker_id, "2 Years", "🎈")
        if years >= 5: award_badge(worker_id, "5 Years", "🎉")
        if years >= 10: award_badge(worker_id, "10 Years", "👑")
    conn.close()

def get_worker_badges(worker_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT badge_name, badge_icon, earned_at FROM worker_badges WHERE worker_id = ? AND company_id = ? ORDER BY earned_at", conn, params=(worker_id, company_id))
    conn.close()
    return df


# ============================================================
# SWEET SPOT APPROVAL FUNCTIONS
# ============================================================

def request_sweet_spot_approval(estimate_id, worker_id, requested_price, manager_id):
    company_id = get_current_user_company()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO estimate_approvals (company_id, estimate_id, worker_id, requested_price, requested_at, status, manager_id) VALUES (?,?,?,?,?,?,?)",
              (company_id, estimate_id, worker_id, requested_price, datetime.now().isoformat(), 'pending', manager_id))
    conn.commit()
    conn.close()
    log_audit(worker_id, "sweet_spot_request", f"Requested approval for estimate {estimate_id} in company {company_id}")
    create_notification(manager_id, company_id, "Sweet Spot Approval Request", f"Worker requested approval for estimate #{estimate_id} at ${requested_price:,.2f}", "approval_request", estimate_id)

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
        c.execute("UPDATE estimate_approvals SET status = 'approved', approved_at = ? WHERE id = ? AND company_id = ?", (datetime.now().isoformat(), request_id, company_id))
        add_estimate_history_entry(est_id, "draft", "sent", manager_id, f"Sweet spot approved at ${price:,.2f}")
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


# ============================================================
# CERTIFICATION FUNCTIONS
# ============================================================

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
# PAGE FUNCTIONS
# ============================================================

def setup_wizard():
    st.title("🧹 ProfitClean")
    st.caption("Created by Dust Bros & Co.")

    # Temporary diagnostic for the one-time platform-admin setup -- see
    # _run_platform_admin_setup_if_requested() for details. Remove alongside
    # that function.
    _platform_admin_marker_path, _ = _platform_admin_marker_paths()
    if os.path.exists(_platform_admin_marker_path):
        with st.expander("Platform admin setup diagnostic (remove after use)"):
            try:
                with open(_platform_admin_marker_path) as f:
                    st.code(f.read())
            except OSError as e:
                st.write(f"Could not read marker file: {e}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM companies")
    company_count = c.fetchone()[0]
    conn.close()
    if company_count == 0:
        st.info("Welcome! Let's set up your company.")
        if st.button("Sign in instead"):
            st.session_state.page = "login"
            st.rerun()
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
            smtp_server = st.text_input("SMTP Server (optional)", placeholder="smtp.gmail.com")
            smtp_port = st.number_input("SMTP Port", value=587)
            if st.form_submit_button("Create My Company"):
                if admin_password != confirm_password:
                    st.error("Passwords do not match")
                elif not all([business_name, subdomain, admin_username, admin_email, admin_password]):
                    st.error("Please fill all required fields")
                else:
                    success, result = create_company(
                        business_name,
                        subdomain,
                        admin_email,
                        admin_username,
                        admin_password,
                        make_super_admin=(company_count == 0),
                    )
                    if success:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        # Encrypt SMTP password before storing
                        encrypted_password = ""
                        if smtp_password:
                            try:
                                from encryption_manager import encryption
                                encrypted_password = encryption.encrypt(smtp_password)
                            except Exception as e:
                                print(f"SMTP password encryption failed, not storing: {e}")
                                st.warning("Could not securely save the SMTP password. Please re-enter it later from Settings.")
                        c.execute("UPDATE business_profile SET business_name=?, phone=?, hourly_wage=?, min_job_fee=?, home_city=?, per_mile_rate=?, sales_tax_rate=?, smtp_email=?, smtp_password=?, smtp_server=?, smtp_port=?, setup_complete=1 WHERE company_id=?",
                                  (business_name, phone, hourly_wage, min_job_fee, home_city, 0.65, SALES_TAX_RATE, smtp_email, encrypted_password, smtp_server, smtp_port, result))
                        conn.commit()
                        
                        create_job_template(result, "Standard Office Clean", "Standard office cleaning including vacuum, dust, and restrooms", 
                                           "Office Standard", 2.0, ["Vacuum floors", "Dust surfaces", "Clean restrooms", "Empty trash", "Sanitize touchpoints"])
                        create_job_template(result, "Deep Clean", "Deep cleaning for move-in/move-out or seasonal", 
                                           "Office Standard", 4.0, ["All standard tasks", "Baseboard cleaning", "Window cleaning", "Cabinet wiping", "Appliance cleaning"])
                        
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

    if st.button("Skip setup and go to login"):
        st.session_state.page = "login"
        st.rerun()

def login_page():
    lang_choice = language_selector(key_suffix="login")
    st.session_state['lang'] = lang_choice

    st.markdown(f"# {t('login_title')}")

    # Temporary diagnostic for the one-time platform-admin setup -- shows
    # exactly what _run_platform_admin_setup_if_requested() did (including
    # the generated password), since there's no server/log access available
    # otherwise. Remove alongside that function.
    _platform_admin_marker_path, _ = _platform_admin_marker_paths()
    if os.path.exists(_platform_admin_marker_path):
        with st.expander("Platform admin setup diagnostic (remove after use)"):
            try:
                with open(_platform_admin_marker_path) as f:
                    st.code(f.read())
            except OSError as e:
                st.write(f"Could not read marker file: {e}")

    # If already logged in via session_state
    if st.session_state.get("user"):
        user = validate_session_token(st.session_state.get("session_token"))
        if user:
            st.session_state.user = user
            st.session_state.page = "dashboard"
            st.rerun()

    col1, col2 = st.columns([2, 1])

    with col1:
        with st.form("login_form"):
            email = st.text_input(t("login_email"), placeholder="you@company.com")
            password = st.text_input(t("login_password"), type="password")

            remember_me = st.checkbox(t("login_remember_me"), value=True)

            if st.form_submit_button(t("login_button"), use_container_width=True):
                if not email or not password:
                    st.error(t("login_missing_fields"))
                else:
                    with st.spinner(t("login_authenticating")):
                        success, result = authenticate_user(
                            email, password,
                            ip_address=st.context.headers.get("X-Forwarded-For") if hasattr(st, 'context') else None
                        )

                        if success:
                            # Carry the pre-login language choice through as the user's
                            # saved preference, so picking "Español" here doesn't get
                            # silently overridden by the DB default once they're past login.
                            if result.get('language') != lang_choice:
                                conn = sqlite3.connect(DB_PATH)
                                c = conn.cursor()
                                c.execute("UPDATE users SET language = ? WHERE id = ?", (lang_choice, result['user_id']))
                                conn.commit()
                                conn.close()
                                result['language'] = lang_choice

                            if result.get('totp_enabled'):
                                # Password is correct, but 2FA is enabled -- hold off on
                                # granting access until the second factor is verified.
                                st.session_state.pending_2fa_user = result
                                st.session_state.page = "two_factor"
                                st.rerun()
                            else:
                                st.session_state.user = result
                                st.session_state.session_token = result["session_token"]
                                st.success(t("login_success"))
                                st.session_state.page = "dashboard"
                                st.rerun()
                        else:
                            st.error(result)

    with col2:
        st.markdown(t("login_new_here"))
        if st.button(t("login_create_account"), use_container_width=True):
            st.session_state.page = "create_account"
            st.rerun()

        if st.button(t("login_forgot_password"), use_container_width=True):
            st.session_state.page = "forgot_password"
            st.rerun()

        st.caption(t("login_need_help"))

    # Footer
    st.markdown("---")
    if st.button(t("login_client_portal")):
        st.session_state.page = "client_login"
        st.rerun()


def two_factor_page():
    st.markdown("### 🔐 Two‑Factor Authentication")
    st.caption("Enter the 6-digit code from your authenticator app, or one of your backup codes")
    user = st.session_state.get('pending_2fa_user')
    if not user:
        st.session_state.page = "login"
        st.rerun()
        return
    with st.form("2fa"):
        code = st.text_input("Authentication Code")
        if st.form_submit_button("Verify"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT totp_secret FROM users WHERE id = ?", (user['user_id'],))
            row = c.fetchone()
            conn.close()
            verified = bool(row and row[0] and verify_totp(row[0], code))
            if not verified:
                verified = verify_backup_code(user['user_id'], code)
            if verified:
                st.session_state.user = user
                st.session_state.session_token = user.get('session_token')
                del st.session_state.pending_2fa_user
                st.session_state.page = "dashboard"
                st.success("2FA verified!")
                st.rerun()
            else:
                st.error("Invalid code. Try again.")
    if st.button("← Back to Login"):
        st.session_state.pop('pending_2fa_user', None)
        st.session_state.page = "login"
        st.rerun()

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
            invite_code = st.text_input("Invite Code *", help="Enter the invite code provided by your manager")
            role = st.selectbox("Requested Role", ["worker", "supervisor", "manager"])
            if st.form_submit_button("Request to Join"):
                if password != confirm:
                    st.error("Passwords do not match")
                elif not all([name, email, password, invite_code]):
                    st.error("All fields required")
                else:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("SELECT company_id FROM users WHERE invite_code = ? AND role IN ('admin', 'manager')", (invite_code,))
                    user_row = c.fetchone()
                    conn.close()
                    if user_row:
                        company_id = user_row[0]
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
                        st.error("Invalid invite code")
    else:
        render_start_company_wizard()

    if st.button("← Back to Login"):
        st.session_state.pop("signup_wizard_step", None)
        st.session_state.pop("signup_wizard_data", None)
        st.session_state.page = "login"
        st.rerun()


def render_start_company_wizard():
    """Guided, multi-step version of "Start my own cleaning company",
    replacing what used to be a single dense form. Each step asks one
    focused question so a first-time user isn't confronted with ten
    fields at once, and can go back to fix something without losing the
    rest of what they've entered.
    """
    step = st.session_state.get("signup_wizard_step", 1)
    data = st.session_state.setdefault("signup_wizard_data", {})
    total_steps = 4

    st.progress((step - 1) / total_steps)
    st.caption(f"Step {step} of {total_steps}")

    if step == 1:
        st.subheader("👋 Let's create your login")
        st.caption("This is what you'll use to sign in to ProfitClean.")
        name = st.text_input("Full Name *", data.get("name", ""), key="wiz_name")
        email = st.text_input("Email *", data.get("email", ""), key="wiz_email")
        password = st.text_input("Password *", type="password", key="wiz_password")
        confirm = st.text_input("Confirm Password *", type="password", key="wiz_confirm")
        st.caption("At least 8 characters, with an uppercase letter, a number, and a special character.")
        if st.button("Next →", use_container_width=True, key="wiz_next_1"):
            if not all([name, email, password, confirm]):
                st.error("Please fill in all fields")
            elif password != confirm:
                st.error("Passwords do not match")
            else:
                valid, msg = validate_password_strength(password)
                if not valid:
                    st.error(msg)
                else:
                    data.update(name=name, email=email, password=password)
                    st.session_state.signup_wizard_step = 2
                    st.rerun()

    elif step == 2:
        st.subheader("🏢 Tell us about your business")
        business_name = st.text_input("Company Name *", data.get("business_name", ""), key="wiz_business_name")
        subdomain = st.text_input(
            "Subdomain *", data.get("subdomain", ""), key="wiz_subdomain",
            help="This will be your unique URL: yourcompany.profitclean.com",
        )
        phone = st.text_input("Phone *", data.get("phone", ""), key="wiz_phone")
        default_city_index = FLORIDA_CITIES.index(data["home_city"]) if data.get("home_city") in FLORIDA_CITIES else 0
        home_city = st.selectbox("Home Base City", FLORIDA_CITIES, index=default_city_index, key="wiz_home_city")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back", use_container_width=True, key="wiz_back_2"):
                st.session_state.signup_wizard_step = 1
                st.rerun()
        with col2:
            if st.button("Next →", use_container_width=True, key="wiz_next_2"):
                if not all([business_name, subdomain, phone]):
                    st.error("Please fill in all fields")
                else:
                    data.update(business_name=business_name, subdomain=subdomain, phone=phone, home_city=home_city)
                    st.session_state.signup_wizard_step = 3
                    st.rerun()

    elif step == 3:
        st.subheader("💰 Set your starting prices")
        st.caption("Just a starting point -- you can change these anytime in Settings.")
        hourly_wage = st.number_input(
            "Base Hourly Wage", min_value=10.0, value=float(data.get("hourly_wage", 15.0)), step=0.5, key="wiz_hourly_wage",
            help="What you pay your team per hour, before overhead and profit.",
        )
        min_job_fee = st.number_input(
            "Minimum Job Fee", min_value=50, value=int(data.get("min_job_fee", 150)), step=25, key="wiz_min_job_fee",
            help="The lowest price you'll charge for any single job, no matter how small.",
        )
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back", use_container_width=True, key="wiz_back_3"):
                st.session_state.signup_wizard_step = 2
                st.rerun()
        with col2:
            if st.button("Next →", use_container_width=True, key="wiz_next_3"):
                data.update(hourly_wage=hourly_wage, min_job_fee=min_job_fee)
                st.session_state.signup_wizard_step = 4
                st.rerun()

    elif step == 4:
        st.subheader("✅ Review & create your account")
        st.markdown(f"""
- **Name:** {data.get('name')}
- **Email:** {data.get('email')}
- **Company:** {data.get('business_name')}
- **Subdomain:** {data.get('subdomain')}.profitclean.com
- **Phone:** {data.get('phone')}
- **Home City:** {data.get('home_city')}
- **Base Hourly Wage:** ${data.get('hourly_wage', 0):.2f}
- **Minimum Job Fee:** ${data.get('min_job_fee', 0):.2f}
""")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back", use_container_width=True, key="wiz_back_4"):
                st.session_state.signup_wizard_step = 3
                st.rerun()
        with col2:
            if st.button("Create My Account", use_container_width=True, key="wiz_create"):
                success, result = create_company(
                    data["business_name"],
                    data["subdomain"],
                    data["email"],
                    data["name"],
                    data["password"],
                )
                if success:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute(
                        "UPDATE business_profile SET business_name=?, phone=?, hourly_wage=?, min_job_fee=?, home_city=?, per_mile_rate=?, sales_tax_rate=?, setup_complete=1 WHERE company_id=?",
                        (data["business_name"], data["phone"], data["hourly_wage"], data["min_job_fee"], data["home_city"], 0.65, SALES_TAX_RATE, result),
                    )
                    conn.commit()
                    conn.close()
                    st.session_state.pop("signup_wizard_step", None)
                    st.session_state.pop("signup_wizard_data", None)
                    st.success("Account created! Please log in.")
                    st.session_state.page = "login"
                    st.rerun()
                else:
                    st.error(result)

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
    st.markdown(t("profile_title"))
    user_data = get_current_user_data()
    if not user_data:
        st.error(t("profile_user_not_found"))
        return

    unread_count = get_unread_notification_count(st.session_state.user['user_id'])
    if unread_count > 0:
        st.info(t("profile_unread", count=unread_count))

    if len(user_data) == 10:
        uid, username, email, role, company_id, mgr_id, sup_id, hire_date, totp_enabled, invite_code = user_data
    else:
        uid, username, email, role, company_id, mgr_id, sup_id, hire_date, totp_enabled = user_data
        invite_code = t("profile_not_set")

    with st.form("edit_profile_form"):
        new_username = st.text_input(t("profile_username"), username)
        new_email = st.text_input(t("profile_email"), email)
        st.text_input(t("profile_role"), role, disabled=True)
        st.text_input(t("profile_company_id"), str(company_id) if company_id else "N/A", disabled=True)
        st.text_input(t("profile_hire_date"), hire_date[:10] if hire_date else "N/A", disabled=True)
        st.text_input(t("profile_invite_code"), invite_code if invite_code else t("profile_not_set"), disabled=True)
        st.markdown(t("profile_change_password"))
        cur_pwd = st.text_input(t("profile_current_password"), type="password")
        new_pwd = st.text_input(t("profile_new_password"), type="password")
        confirm_pwd = st.text_input(t("profile_confirm_password"), type="password")
        if st.form_submit_button(t("profile_save_changes")):
            updates = []
            params = []
            if new_username != username:
                updates.append("username = ?")
                params.append(new_username)
            if new_email != email:
                updates.append("email = ?")
                params.append(new_email)
            password_changed = False
            if new_pwd:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT password_hash FROM users WHERE id = ?", (uid,))
                row = c.fetchone()
                conn.close()
                if not row or not verify_password(cur_pwd, row[0]):
                    st.error(t("profile_current_password_wrong"))
                elif new_pwd != confirm_pwd:
                    st.error(t("profile_passwords_no_match"))
                else:
                    valid, msg = validate_password_strength(new_pwd)
                    if not valid:
                        st.error(msg)
                    else:
                        hashed, salt = hash_password(new_pwd)
                        updates.append("password_hash = ?")
                        updates.append("salt = ?")
                        params.extend([hashed, salt])
                        password_changed = True
            if updates:
                params.append(uid)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                try:
                    c.execute(f"UPDATE users SET {', '.join(updates)} WHERE id = ?", params)
                    conn.commit()
                    if password_changed:
                        # A changed password should invalidate any other active
                        # sessions (e.g. a stolen/leaked token) -- including this
                        # one, so the user logs back in with the new password.
                        force_logout_sessions(uid)
                        for key in list(st.session_state.keys()):
                            if key not in ["page"]:
                                del st.session_state[key]
                        st.session_state.page = "login"
                        st.success("Password changed. Please log in again with your new password.")
                        st.rerun()
                    else:
                        st.success(t("profile_saved"))
                        st.rerun()
                except sqlite3.IntegrityError:
                    conn.rollback()
                    st.error("That username or email is already in use. Please choose another.")
                finally:
                    conn.close()

    st.markdown("---")
    st.markdown(t("profile_language"))
    st.caption(t("profile_language_help"))
    new_lang = language_selector(key_suffix="profile")
    if new_lang != st.session_state.user.get('language', 'en'):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("UPDATE users SET language = ? WHERE id = ?", (new_lang, uid))
        conn.commit()
        conn.close()
        st.session_state.user['language'] = new_lang
        st.success(t("profile_language_saved"))
        st.rerun()

    st.markdown("---")
    st.markdown(t("profile_2fa_title"))
    if totp_enabled:
        st.success(t("profile_2fa_enabled"))
        disable_pwd = st.text_input(t("profile_2fa_disable_confirm_password"), type="password", key="disable_2fa_password")
        if st.button(t("profile_2fa_disable")):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT password_hash FROM users WHERE id = ?", (uid,))
            row = c.fetchone()
            if not row or not verify_password(disable_pwd, row[0]):
                conn.close()
                st.error(t("profile_2fa_disable_wrong_password"))
            else:
                c.execute("UPDATE users SET totp_enabled = 0, totp_secret = NULL WHERE id = ?", (uid,))
                conn.commit()
                conn.close()
                log_audit(uid, "disable_2fa", "User disabled two-factor authentication")
                st.success(t("profile_2fa_disabled_msg"))
                st.rerun()
    else:
        st.info(t("profile_2fa_disabled_info"))
        if st.button(t("profile_2fa_enable")):
            secret = generate_totp_secret()
            uri = get_totp_uri(secret, email)
            st.session_state.totp_secret = secret
            st.session_state.totp_email = email
            st.session_state.page = "setup_2fa"
            st.rerun()

    st.markdown("---")
    st.markdown(t("profile_notifications"))
    notifications = get_user_notifications(uid, 10)
    if not notifications.empty:
        for _, notif in notifications.iterrows():
            with st.container():
                col1, col2 = st.columns([4, 1])
                with col1:
                    if notif['read_status'] == 0:
                        st.markdown(f"🔔 **{notif['title']}**")
                        st.caption(notif['message'])
                    else:
                        st.markdown(f"📌 {notif['title']}")
                        st.caption(notif['message'])
                with col2:
                    if notif['read_status'] == 0:
                        if st.button(t("profile_mark_read"), key=f"mark_{notif['id']}"):
                            mark_notification_read(notif['id'], st.session_state.user['user_id'])
                            st.rerun()
                st.markdown("---")
    else:
        st.info(t("profile_no_notifications"))

    if st.button(t("profile_back_dashboard")):
        st.session_state.page = "dashboard"
        st.rerun()

def dashboard():
    # Check authentication
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("🔒 Please log in")
        st.session_state.page = "login"
        st.rerun()
        return
    
    # Validate session token if available
    if st.session_state.get('session_token'):
        user = validate_session_token(st.session_state.session_token)
        if not user:
            st.warning("Session expired. Please log in again.")
            st.session_state.page = "login"
            st.rerun()
            return
        st.session_state.user = user
    
    user = st.session_state.user
    business_name = get_business_name()
    company_id = get_current_user_company()
    st.title(f"🧹 {business_name}")
    st.caption(t("dashboard_welcome", username=user['username'], role=user['role'], company_id=company_id))

    unread_count = get_unread_notification_count(user['user_id'])
    if unread_count > 0:
        st.info(t("dashboard_new_notifications", count=unread_count))

    if st.session_state.user.get('role_override'):
        st.warning(t("dashboard_role_override", company_id=st.session_state.user['company_id']))

    with st.sidebar:
        st.markdown(t("menu_title"))
        menu_items = [
            (t("menu_dashboard"), "dashboard"),
            (t("menu_new_estimate"), "estimate"),
            (t("menu_proposal"), "proposal"),
            (t("menu_quick_job"), "quick"),
            (t("menu_clients"), "clients"),
            (t("menu_workers"), "workers"),
            (t("menu_schedule"), "schedule"),
            (t("menu_pre_inspection"), "inspections"),
            (t("menu_profit"), "profit"),
            (t("menu_history"), "history"),
            (t("menu_team_chat"), "chat"),
            (t("menu_supplies"), "supplies"),
            (t("menu_ai_tasks"), "ai_tasks"),
            (t("menu_qr_tracking"), "qr_tracking"),
            (t("menu_gps_tracking"), "gps_tracking"),
            (t("menu_my_performance"), "my_performance"),
            (t("menu_certifications"), "certifications"),
            (t("menu_job_templates"), "job_templates"),
            (t("menu_backup"), "backup"),
            (t("menu_support"), "support"),
            (t("menu_integrations"), "integrations"),
            (t("menu_settings"), "settings"),
            (t("menu_edit_profile"), "edit_profile"),
            (t("menu_terms"), "terms"),

        ]
        effective_role = get_effective_user()['role'] if get_effective_user() else user['role']
        if effective_role in ['super_admin', 'admin', 'manager']:
            menu_items.append(("📋 Approval Requests", "approvals"))
        if effective_role in ['super_admin', 'admin']:
            menu_items.append(("🔍 Auth Logs", "debug_logs"))
        if effective_role in ['super_admin', 'support_staff']:
            menu_items.append(("🔧 Admin Tools", "admin_companies"))
        if effective_role in ['super_admin', 'admin']:
            menu_items.append(("📊 Internal Pricing", "internal_pricing"))
        for label, page in menu_items:
            if st.button(label, use_container_width=True, key=f"nav_{page}"):
                st.session_state.page = page
                st.rerun()
        st.markdown("---")
        with st.expander(t("menu_need_help")):
            if st.button(t("menu_report_issue")):
                st.session_state.page = "support"
                st.rerun()
        st.markdown("---")
        if st.button(t("menu_logout")):
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
    c.execute(f"SELECT COUNT(*) FROM scheduled_jobs WHERE company_id = ? AND user_id IN ({placeholders}) AND scheduled_date >= date('now') AND status='scheduled'", [company_id] + accessible)
    upcoming = c.fetchone()[0]
    conn.close()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric(t("dashboard_metric_clients"), client_cnt)
    col2.metric(t("dashboard_metric_pending"), pending)
    col3.metric(t("dashboard_metric_workers"), worker_cnt)
    col4.metric(t("dashboard_metric_upcoming"), upcoming)

    st.markdown(t("dashboard_upcoming_jobs"))
    upcoming_jobs = get_upcoming_jobs(14)
    if not upcoming_jobs.empty:
        st.dataframe(upcoming_jobs[['scheduled_date', 'scheduled_time', 'client_name', 'assigned_worker_id', 'status']])
    else:
        st.info(t("dashboard_no_upcoming"))
    
    st.info("Use sidebar to navigate.")


def approve_estimate_page():
    """Handle estimate approval via secure token"""
    params = get_query_params_safely()
    token = parse_query_param(params, "token")
    
    if not token:
        st.error("❌ Invalid approval link")
        st.markdown("This approval link is missing the required token.")
        if st.button("Return to Home"):
            st.session_state.page = "login"
            st.rerun()
        return
    
    # Validate token
    estimate_data, error = validate_approval_token(token)
    
    if error:
        st.error(f"❌ {error}")
        st.markdown("This approval link is invalid, expired, or has already been used.")
        if st.button("Return to Home"):
            st.session_state.page = "login"
            st.rerun()
        return
    
    # Show approval confirmation
    st.markdown("### ✅ Approve Estimate")
    st.caption(f"Estimate #{estimate_data['estimate_id']}")
    
    st.info("You are about to approve this estimate. This action cannot be undone.")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Confirm Approval", type="primary"):
            success, message = approve_estimate_with_token(token)
            if success:
                st.success("✅ Estimate approved successfully!")
                st.balloons()
            else:
                st.error(f"❌ {message}")
    
    with col2:
        if st.button("Cancel"):
            st.session_state.page = "login"
            st.rerun()

def forgot_password_page():
    """Page for users to request password reset"""
    
    st.markdown("### 🔑 Reset Your Password")
    st.caption("Enter your email to receive reset instructions")
    
    tab1, tab2 = st.tabs(["📧 Request Reset", "🔐 Set New Password"])
    
    with tab1:
        with st.form("request_reset"):
            email = st.text_input("Email Address")
            
            if st.form_submit_button("Send Reset Instructions"):
                if email:
                    success, message = request_password_reset(email)
                    if success:
                        st.success(message)
                        if "2FA" in message:
                            st.info("Please check your email for the verification code.")
                        st.session_state.reset_requested = True
                    else:
                        st.warning(message)
                else:
                    st.error("Please enter your email address")
    
    with tab2:
        st.markdown("#### Already have a reset token?")
        
        token = st.text_input("Reset Token (from email)")
        twofa_code = st.text_input("2FA Verification Code (if required)")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        
        if st.button("Reset Password"):
            if new_password != confirm_password:
                st.error("Passwords do not match")
            elif not token:
                st.error("Please enter your reset token")
            else:
                success, message = reset_password_with_2fa(token, twofa_code, new_password)
                if success:
                    st.success(message)
                    st.info("Please log in with your new password")
                    if st.button("Go to Login"):
                        st.session_state.page = "login"
                        st.rerun()
                else:
                    st.error(message)
    
    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.rerun()


def debug_logs_page():
    """Admin page to view authentication logs"""
    
    if st.session_state.user.get('role') not in ['super_admin', 'admin']:
        st.error("Access denied")
        return
    
    st.markdown("### 🔍 Authentication Logs")
    st.caption("Troubleshoot login issues")

    conn = sqlite3.connect(DB_PATH)

    # Get logs. Non-super_admins only see logs for their own company's users --
    # otherwise a tenant admin could see every other tenant's emails/login activity.
    if st.session_state.user.get('role') == 'super_admin':
        logs_df = pd.read_sql_query("""
            SELECT id, user_id, email, event_type, status, error_message, created_at
            FROM auth_logs
            ORDER BY created_at DESC
            LIMIT 100
        """, conn)
    else:
        company_id = get_current_user_company()
        logs_df = pd.read_sql_query("""
            SELECT a.id, a.user_id, a.email, a.event_type, a.status, a.error_message, a.created_at
            FROM auth_logs a
            JOIN users u ON a.user_id = u.id
            WHERE u.company_id = ?
            ORDER BY a.created_at DESC
            LIMIT 100
        """, conn, params=(company_id,))
    conn.close()
    
    if logs_df.empty:
        st.info("No authentication logs found")
    else:
        # Filters
        col1, col2 = st.columns(2)
        with col1:
            event_filter = st.multiselect("Filter by event", logs_df['event_type'].unique())
        with col2:
            status_filter = st.multiselect("Filter by status", logs_df['status'].unique())
        
        # Apply filters
        if event_filter:
            logs_df = logs_df[logs_df['event_type'].isin(event_filter)]
        if status_filter:
            logs_df = logs_df[logs_df['status'].isin(status_filter)]
        
        st.dataframe(logs_df, use_container_width=True)
        
        # Check for problematic accounts
        st.markdown("---")
        st.markdown("### 🚨 Problem Accounts")
        
        problem_df = logs_df[logs_df['event_type'] == 'login_failed'].groupby('email').size().reset_index(name='failed_attempts')
        problem_df = problem_df[problem_df['failed_attempts'] > 3]
        
        if not problem_df.empty:
            st.warning("Accounts with multiple failed logins:")
            st.dataframe(problem_df)
        else:
            st.success("No problematic accounts detected")
    
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()


def estimate_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.markdown("### 📝 New Estimate")
    company_id = get_current_user_company()
    business_name = get_business_name()

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

    client_name = st.text_input("Client Name *")
    client_email = st.text_input("Client Email *")

    if not client_name or not client_email:
        st.warning("⚠️ Please enter client name and email before saving")

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
    add_ons = {
        'window_cleaning': add_window,
        'carpet_cleaning': add_carpet,
        'floor_waxing': add_floor,
        'disinfection': add_disinfection,
        'pressure_washing': add_pressure,
    }

    st.markdown("### Modifiers")
    col1, col2 = st.columns(2)
    holiday = col1.selectbox("Holiday", ["None"] + list(HOLIDAY_RATES.keys()))
    emergency = col1.selectbox("Emergency", ["Standard (3+ days)", "2 days (+25%)", "Next day (+50%)", "Same day (+75%)"])
    emap = {
        "Standard (3+ days)": 72,
        "2 days (+25%)": 48,
        "Next day (+50%)": 24,
        "Same day (+75%)": 12,
    }
    notice = emap[emergency]
    num_locations = col2.number_input("Number of Locations", 1, 20, 1)
    contract = col2.selectbox(
        "Contract",
        ["No contract", "3 months (-5%)", "6 months (-10%)", "12 months (-15%)", "24+ months (-20%)"],
    )
    cmap = {
        "No contract": 0,
        "3 months (-5%)": 3,
        "6 months (-10%)": 6,
        "12 months (-15%)": 12,
        "24+ months (-20%)": 24,
    }
    contract_months = cmap[contract]

    result = calculate_price_with_tiers(
        city,
        prop,
        sqft,
        bedrooms,
        bathrooms,
        freq,
        complexity,
        travel_miles,
        add_ons,
        holiday,
        num_locations,
        notice,
        contract_months,
        company_id,
    )

    st.markdown("### 💰 Four Pricing Tiers")

    with st.expander("📊 Market Intelligence & Competitor Analysis", expanded=False):
        cost_calc = calculator_cost_based(city, prop, sqft, bedrooms, bathrooms, freq, complexity, travel_miles)
        st.markdown(f"""
        **Location Analysis:** {cost_calc['breakdown']['zone_name']} area (Multiplier: {cost_calc['breakdown']['zone_multiplier']}x)
        **Complexity Level:** {complexity}/10
        **Pricing Model:** {cost_calc['breakdown']['pricing_model']}

        **Recommended Price:** ${result['sweet_spot']['total']:,}
        """)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; border-radius: 12px; background: #fef3c7; border: 2px solid #f59e0b;">
            <h4>📉 BREAK EVEN</h4>
            <h2 style="color: #d97706;">${result['break_even']['total']:,}</h2>
            <p><strong>{result['break_even']['margin']}% margin</strong></p>
            <p style="font-size: 12px; margin-top: 10px;">⚠️ No profit - just covering costs</p>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; border-radius: 12px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; border: 2px solid #10b981;">
            <h4>🎯 SWEET SPOT</h4>
            <h2 style="color: white;">${result['sweet_spot']['total']:,}</h2>
            <p><strong>{result['sweet_spot']['margin']}% margin</strong></p>
            <p style="font-size: 12px; margin-top: 10px;">✅ RECOMMENDED - Best value</p>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; border-radius: 12px; background: #d1fae5; border: 2px solid #10b981;">
            <h4>💰 FAIR MARKET</h4>
            <h2 style="color: #059669;">${result['fair_market']['total']:,}</h2>
            <p><strong>{result['fair_market']['margin']}% margin</strong></p>
            <p style="font-size: 12px; margin-top: 10px;">📊 Competitive with local market</p>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div style="text-align: center; padding: 15px; border-radius: 12px; background: linear-gradient(135deg, #8b5cf6 0%, #6d28d9 100%); color: white; border: 2px solid #8b5cf6;">
            <h4>⭐ PREMIUM</h4>
            <h2 style="color: white;">${result['premium']['total']:,}</h2>
            <p><strong>{result['premium']['margin']}% margin</strong></p>
            <p style="font-size: 12px; margin-top: 10px;">⚡ Rush/Emergency/Premium</p>
        </div>
        """, unsafe_allow_html=True)

    with st.expander("🔍 Detailed Cost Breakdown", expanded=False):
        st.markdown(f"""
        **True Cost Calculation:**
        - Labor ({result['labor_hours']:.1f} hrs): ${result['labor_cost']:,.2f}
        - Materials: ${result['materials_cost']:,.2f}
        - Travel: ${result['travel_cost']:,.2f}
        - Tolls: ${result['toll_estimate']:,.2f}
        - **Total Cost: ${result['true_cost']:,.2f}**
        """)

    st.info(f"""
    💡 **Pricing Summary:**
    - Total Cost: ${result['true_cost']:,.2f}
    - 🎯 Recommended Price: ${result['sweet_spot']['total']:,}
    - 🏠 House Profit: ${result['sweet_spot']['subtotal'] - result['true_cost']:,.2f} ({result['sweet_spot']['margin']}% margin)
    """)

    col_btn1, col_btn2 = st.columns(2)
    save_only = col_btn1.button("💾 Save as Draft Only", key="save_only_estimate")
    save_and_send = col_btn2.button("💾 Save & Send Email to Client", key="save_and_send_estimate")

    if save_only or save_and_send:
        if not client_name or not client_email:
            st.error("❌ Please enter both client name and client email before saving")
            return

        estimate_id = save_estimate_to_database(
            company_id,
            client_name,
            client_email,
            city,
            prop,
            sqft,
            bedrooms,
            bathrooms,
            freq,
            complexity,
            travel_miles,
            add_window,
            add_carpet,
            add_floor,
            add_disinfection,
            add_pressure,
            result,
        )

        if not estimate_id:
            st.error("❌ Unable to save estimate. Please try again.")
            return

        st.success(f"✅ Estimate #{estimate_id} saved as draft!")

        if save_and_send:
            # Generate secure approval token
            approval_token = generate_approval_token(estimate_id, company_id)
            # Use configurable base URL instead of hardcoded
            base_url = os.getenv('APP_BASE_URL', 'https://profitclean-c4s6mqoafikfejkdfuwgvx.streamlit.app')
            approval_link = f"{base_url}?page=approve_estimate&token={approval_token}"
            email_sent = send_estimate_email(
                company_id,
                estimate_id,
                client_email,
                client_name,
                result['sweet_spot']['total'],
                approval_link,
            )

            if email_sent:
                st.success(f"📧 Estimate sent to {client_email}")
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("UPDATE estimates SET status = 'sent' WHERE id = ?", (estimate_id,))
                conn.commit()
                conn.close()
            else:
                error_message = get_last_email_error() or "Please configure SMTP settings in Business Settings."
                st.warning(f"⚠️ Estimate saved but email failed. {error_message}")
                st.info("If you’re using Gmail, make sure you are using an App Password and that SMTP settings are saved.")


def save_estimate_to_database(
    company_id,
    client_name,
    client_email,
    city,
    prop,
    sqft,
    bedrooms,
    bathrooms,
    freq,
    complexity,
    travel_miles,
    add_window,
    add_carpet,
    add_floor,
    add_disinfection,
    add_pressure,
    result,
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("PRAGMA table_info(estimates)")
    existing_columns = [col[1] for col in c.fetchall()]

    base_columns = [
        'company_id',
        'user_id',
        'client_name',
        'client_email',
        'city',
        'property_type',
        'square_feet',
        'bedrooms',
        'bathrooms',
        'frequency',
        'complexity',
        'travel_miles',
        'toll_cost',
        'add_on_window',
        'add_on_carpet',
        'add_on_floor',
        'add_on_disinfection',
        'add_on_pressure',
        'subtotal',
        'tax',
        'estimated_price',
        'lowest_price',
        'fair_price',
        'highest_price',
        'sweet_spot_price',
        'created_at',
        'status',
    ]

    use_expires = False
    if 'expires_at' in existing_columns:
        base_columns.append('expires_at')
        use_expires = True

    columns_str = ', '.join(base_columns)
    placeholders = ', '.join(['?' for _ in base_columns])

    base_values = [
        company_id,
        st.session_state.user['user_id'],
        client_name,
        client_email,
        city,
        prop,
        sqft,
        bedrooms,
        bathrooms,
        freq,
        complexity,
        travel_miles,
        result.get('toll_estimate', 0.0),
        1 if add_window else 0,
        1 if add_carpet else 0,
        1 if add_floor else 0,
        1 if add_disinfection else 0,
        1 if add_pressure else 0,
        result['sweet_spot']['subtotal'],
        result['sweet_spot'].get('tax', 0.0),
        result['sweet_spot']['total'],
        result['break_even']['total'],
        result['fair_market']['total'],
        result['premium']['total'],
        result['sweet_spot']['total'],
        datetime.now().isoformat(),
        'draft',
    ]

    if use_expires:
        base_values.append((datetime.now() + timedelta(days=30)).isoformat())

    query = f"INSERT INTO estimates ({columns_str}) VALUES ({placeholders})"
    c.execute(query, base_values)
    estimate_id = c.lastrowid
    conn.commit()
    conn.close()

    add_estimate_history_entry(
        estimate_id,
        None,
        'draft',
        st.session_state.user['user_id'],
        'Initial draft created',
    )

    return estimate_id


PROPOSAL_PROPERTY_TYPES = ["Grocery Store", "Retail Store", "Gym", "School", "Office", "Restaurant", "Medical Office", "Dental Office", "Warehouse", "Airbnb / Short-Term Rental", "Other"]

PROPERTY_SCOPE_TEMPLATES = {
    "Grocery Store": [
        "Remove all items from shelves, wipe down and sanitize shelving, reorganize and restock neatly",
        "Wipe down AC vents",
        "Clean multiple stains in the ceiling",
        "Full floor cleaning and detailing",
        "Restroom deep cleaning and sanitation",
        "Interior window cleaning",
        "Surface wipe-downs and high dusting",
        "Debris removal",
        "Sanitize soda machine nozzles",
        "Clean refrigerator glass",
        "Steam clean stains if needed",
        "Clean checkout lanes",
    ],
    "Retail Store": [
        "Remove items from shelves, wipe down and sanitize, reorganize and restock neatly",
        "Wipe down AC vents",
        "Full floor cleaning and detailing",
        "Restroom deep cleaning and sanitation",
        "Interior window cleaning",
        "Surface wipe-downs and high dusting",
        "Debris removal",
        "Clean fitting room mirrors and surfaces",
        "Clean checkout/register counters",
    ],
    "Gym": [
        "Sanitize all gym equipment (cardio machines, weights, benches)",
        "Clean and disinfect locker rooms and showers",
        "Mop and disinfect floors and workout mats",
        "Clean mirrors throughout the facility",
        "Sanitize water fountains and hydration stations",
        "Restroom deep cleaning and sanitation",
        "Wipe down AC vents",
        "Trash removal and liner replacement",
        "Interior window cleaning",
        "Surface wipe-downs and high dusting",
    ],
    "Office": [
        "Empty trash and replace liners in all offices and common areas",
        "Wipe down desks, conference tables, and workstations",
        "Vacuum carpets and mop hard floors",
        "Clean breakroom counters, sink, and appliances",
        "Restroom deep cleaning and sanitation",
        "Interior window cleaning",
        "Wipe down AC vents",
        "Surface wipe-downs and high dusting",
        "Sanitize doorknobs and high-touch surfaces",
    ],
    "Restaurant": [
        "Deep clean kitchen surfaces and degrease equipment",
        "Clean and sanitize dining area tables and chairs",
        "Mop and degrease kitchen floors",
        "Restroom deep cleaning and sanitation",
        "Clean walk-in cooler/freezer surfaces",
        "Wipe down AC vents and exhaust hoods",
        "Interior window cleaning",
        "Trash and grease trap area cleanup",
        "Surface wipe-downs and high dusting",
    ],
    "Medical Office": [
        "Disinfect exam rooms and treatment areas (hospital-grade cleaner)",
        "Sanitize waiting room furniture and high-touch surfaces",
        "Restroom deep cleaning and sanitation",
        "Biohazard-compliant trash removal",
        "Mop and disinfect floors",
        "Wipe down AC vents",
        "Interior window cleaning",
        "Surface wipe-downs and high dusting",
        "Sanitize medical equipment exteriors",
    ],
    "Dental Office": [
        "Disinfect treatment rooms and dental chairs (hospital-grade cleaner)",
        "Sanitize suction lines and instrument trays",
        "Sanitize waiting room furniture and high-touch surfaces",
        "Restroom deep cleaning and sanitation",
        "Biohazard-compliant trash and sharps disposal",
        "Mop and disinfect floors",
        "Wipe down AC vents",
        "Interior window cleaning",
        "Surface wipe-downs and high dusting",
    ],
    "Warehouse": [
        "Sweep and scrub warehouse floors",
        "Clean loading dock area",
        "Dust high shelving and racking",
        "Restroom deep cleaning and sanitation",
        "Trash and debris removal",
        "Wipe down AC vents",
        "Office area cleaning (if applicable)",
        "Surface wipe-downs and high dusting",
    ],
    "School": [
        "Clean and sanitize classroom desks and chairs",
        "Disinfect high-touch surfaces (door handles, light switches, railings)",
        "Clean and sanitize cafeteria tables and serving areas",
        "Restroom deep cleaning and sanitation",
        "Sweep, mop, and/or vacuum hallways and classrooms",
        "Wipe down whiteboards and surfaces",
        "Trash removal and liner replacement",
        "Wipe down AC vents",
        "Interior window cleaning",
        "Surface wipe-downs and high dusting",
    ],
    "Airbnb / Short-Term Rental": [
        "Strip and remake beds with fresh linens",
        "Launder and restock towels and linens",
        "Full kitchen cleaning (counters, appliances, sink, dishes)",
        "Full bathroom cleaning and sanitation",
        "Vacuum and mop all floors",
        "Restock guest supplies (toiletries, paper towels, coffee, etc.)",
        "Trash removal and liner replacement",
        "Dust and wipe down all surfaces",
        "Check for damage or missing items and report to host",
        "Interior window cleaning",
    ],
    "Other": [
        "Full floor cleaning and detailing",
        "Restroom deep cleaning and sanitation",
        "Interior window cleaning",
        "Surface wipe-downs and high dusting",
        "Debris removal",
        "Wipe down AC vents",
    ],
}


def generate_customer_proposal():
    """Generate a professional customer proposal with pick-and-choose options and profit calculator"""
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📄 Customer Proposal Generator")
    st.caption("Create a professional proposal for your client with pick-and-choose service tiers")
    
    if 'proposal_data' not in st.session_state:
        st.session_state.proposal_data = {
            "client_name": "",
            "client_email": "",
            "property_address": "",
            "property_type": "Grocery Store",
            "square_feet": 2320,
            "num_checkout_lanes": 3,
            "has_soda_machine": True,
            "crew_size": 3,
            "estimated_hours": 6,
            "shift_type": "Night Shift",
            "total_price": 500,
            "travel_miles": 90,
            "supplies_cost": 100,
            "hourly_wage": 25,
            "key_pickup": "We will pick up the keys 45 minutes before closing and drop them off in the U-Haul drop box when cleaning is complete.",
            "commitment_statement": "We aim to provide you with a comprehensive understanding of our services, ensuring you feel confident in the value you receive for the price. Our goal is to deliver a variety of services that meet your needs and expectations.",
            "additional_notes": "This is a break-even rate covering direct costs, labor, supplies, and long-distance travel.",
            "is_deep_clean": True,
            "scope_items": [
                "Remove all items from shelves, wipe down and sanitize shelving, reorganize and restock neatly",
                "Wipe down AC vents",
                "Clean multiple stains in the ceiling",
                "Full floor cleaning and detailing",
                "Restroom deep cleaning and sanitation",
                "Interior window cleaning",
                "Surface wipe-downs and high dusting",
                "Debris removal",
                "Sanitize soda machine nozzles",
                "Clean refrigerator glass",
                "Steam clean stains if needed",
                "Clean checkout lanes"
            ]
        }
    
    # ============================================================
    # SECTION 1: CLIENT INFORMATION
    # ============================================================
    with st.expander("📋 Client Information", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            client_name = st.text_input("Client Name", value=st.session_state.proposal_data.get("client_name", ""))
            client_email = st.text_input("Client Email", value=st.session_state.proposal_data.get("client_email", ""))
            property_address = st.text_area("Property Address", value=st.session_state.proposal_data.get("property_address", ""), height=68)
        with col2:
            property_type = st.selectbox("Property Type", PROPOSAL_PROPERTY_TYPES,
                                        index=PROPOSAL_PROPERTY_TYPES.index(
                                            st.session_state.proposal_data.get("property_type", "Grocery Store")))
            square_feet = st.number_input("Square Footage", min_value=100, value=st.session_state.proposal_data.get("square_feet", 2320), step=100)
            if property_type == "Grocery Store":
                num_checkout_lanes = st.number_input("Number of Checkout Lanes", min_value=0, value=st.session_state.proposal_data.get("num_checkout_lanes", 3))
                has_soda_machine = st.checkbox("Has Soda Machine", value=st.session_state.proposal_data.get("has_soda_machine", True))
            else:
                num_checkout_lanes = 0
                has_soda_machine = False

        st.session_state.proposal_data["client_name"] = client_name
        st.session_state.proposal_data["client_email"] = client_email
        st.session_state.proposal_data["property_address"] = property_address
        st.session_state.proposal_data["property_type"] = property_type
        st.session_state.proposal_data["square_feet"] = square_feet
        st.session_state.proposal_data["num_checkout_lanes"] = num_checkout_lanes
        st.session_state.proposal_data["has_soda_machine"] = has_soda_machine
    
    # ============================================================
    # SECTION 2: PRICE & COSTS (With Profit Calculator)
    # ============================================================
    st.markdown("---")
    st.markdown("### 💰 Pricing & Profit Calculator")
    st.caption("Adjust the numbers below to see your estimated profit margin in real-time")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 📊 Revenue")
        total_price = st.number_input("Proposed Price ($)", min_value=0, value=st.session_state.proposal_data.get("total_price", 500), step=25, help="What you will charge the client")
        
        st.markdown("#### 👥 Labor Costs")
        crew_size = st.number_input("Number of Cleaners", min_value=1, max_value=10, value=st.session_state.proposal_data.get("crew_size", 3))
        estimated_hours = st.number_input("Estimated Hours", min_value=1, max_value=24, value=st.session_state.proposal_data.get("estimated_hours", 6), step=1)
        hourly_wage = st.number_input("Hourly Wage per Cleaner ($)", min_value=10, max_value=50, value=st.session_state.proposal_data.get("hourly_wage", 25), step=1)
    
    with col2:
        st.markdown("#### 🧴 Supply & Equipment Costs")
        supplies_cost = st.number_input("Supplies & Equipment ($)", min_value=0, value=st.session_state.proposal_data.get("supplies_cost", 100), step=25, 
                                        help="Cleaning products, tools, equipment rental")
        
        st.markdown("#### 🚗 Travel Costs")
        travel_miles = st.number_input("Round Trip Miles", min_value=0, value=st.session_state.proposal_data.get("travel_miles", 90), step=10)
        mileage_rate = st.number_input("Mileage Rate ($/mile)", min_value=0.40, max_value=1.00, value=0.65, step=0.05)
        
        is_deep_clean = st.checkbox("Deep Clean (First-time / Heavy soil)", value=st.session_state.proposal_data.get("is_deep_clean", True),
                                    help="Deep cleaning takes 50-100% longer than regular maintenance")
    
    st.markdown("#### 🔧 Additional Costs")
    col1, col2, col3 = st.columns(3)
    with col1:
        equipment_rental = st.number_input("Equipment Rental ($)", min_value=0, value=0, step=50, help="Steam cleaner, floor scrubber, etc.")
    with col2:
        waste_disposal = st.number_input("Waste Disposal ($)", min_value=0, value=0, step=25, help="Special waste removal fees")
    with col3:
        parking_tolls = st.number_input("Parking/Tolls ($)", min_value=0, value=0, step=10)
    
    st.session_state.proposal_data["total_price"] = total_price
    st.session_state.proposal_data["crew_size"] = crew_size
    st.session_state.proposal_data["estimated_hours"] = estimated_hours
    st.session_state.proposal_data["hourly_wage"] = hourly_wage
    st.session_state.proposal_data["supplies_cost"] = supplies_cost
    st.session_state.proposal_data["travel_miles"] = travel_miles
    st.session_state.proposal_data["is_deep_clean"] = is_deep_clean
    
    labor_hours = crew_size * estimated_hours
    if is_deep_clean:
        labor_hours = labor_hours * 1.5  # Deep clean takes 50% longer
    labor_cost = labor_hours * hourly_wage
    
    travel_cost = travel_miles * mileage_rate
    
    total_costs = labor_cost + supplies_cost + travel_cost + equipment_rental + waste_disposal + parking_tolls
    
    overhead_rate = 0.15  # 15%
    overhead_cost = total_costs * overhead_rate
    total_costs_with_overhead = total_costs + overhead_cost
    
    profit = total_price - total_costs_with_overhead
    profit_margin = (profit / total_price * 100) if total_price > 0 else 0
    
    if profit_margin <= 0:
        margin_status = "🔴 LOSING MONEY"
        margin_color = "red"
        recommendation = "Increase price or reduce costs immediately"
    elif profit_margin < 15:
        margin_status = "🟡 LOW PROFIT"
        margin_color = "orange"
        recommendation = "Consider raising price by 10-20%"
    elif profit_margin < 30:
        margin_status = "🟢 GOOD PROFIT"
        margin_color = "green"
        recommendation = "Healthy margin - competitive pricing"
    elif profit_margin < 45:
        margin_status = "⭐ GREAT PROFIT"
        margin_color = "blue"
        recommendation = "Excellent margin - premium positioning"
    else:
        margin_status = "💰 EXCELLENT PROFIT"
        margin_color = "gold"
        recommendation = "Very profitable - consider if client will accept"
    
    st.markdown("---")
    st.markdown("### 📊 Profit Analysis")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("💰 Proposed Price", f"${total_price:,.2f}")
    with col2:
        st.metric("💸 Total Costs", f"${total_costs_with_overhead:,.2f}", delta=f"-${total_costs_with_overhead:,.2f}")
    with col3:
        st.metric("📈 Profit", f"${profit:,.2f}", delta=f"{profit_margin:.1f}% margin")
    with col4:
        st.markdown(f"""
        <div style="text-align: center; padding: 10px; border-radius: 10px; background: {margin_color}20;">
            <strong>Status</strong><br>
            <span style="color: {margin_color}; font-weight: bold;">{margin_status}</span>
        </div>
        """, unsafe_allow_html=True)
    
    with st.expander("🔍 Detailed Cost Breakdown", expanded=False):
        st.markdown(f"""
        **Labor Costs:**
        - Base hours: {crew_size} cleaners × {estimated_hours} hours = {crew_size * estimated_hours} hours
        - Deep clean multiplier: {'1.5x' if is_deep_clean else '1.0x'}
        - Adjusted hours: {labor_hours:.1f} hours
        - Hourly wage: ${hourly_wage}/hr
        - **Labor subtotal: ${labor_cost:,.2f}**
        
        **Supply & Equipment:**
        - Cleaning supplies: ${supplies_cost:,.2f}
        - Equipment rental: ${equipment_rental:,.2f}
        - Waste disposal: ${waste_disposal:,.2f}
        - **Supplies subtotal: ${supplies_cost + equipment_rental + waste_disposal:,.2f}**
        
        **Travel & Logistics:**
        - Round trip miles: {travel_miles} miles × ${mileage_rate}/mile = ${travel_cost:,.2f}
        - Parking/Tolls: ${parking_tolls:,.2f}
        - **Travel subtotal: ${travel_cost + parking_tolls:,.2f}**
        
        **Overhead (15%):** ${overhead_cost:,.2f}
        
        ---
        **TOTAL COSTS: ${total_costs_with_overhead:,.2f}**
        **PROPOSED PRICE: ${total_price:,.2f}**
        **PROFIT: ${profit:,.2f} ({profit_margin:.1f}%)**
        """)
    
    if profit_margin < 20 and total_price > 0:
        st.warning(f"⚠️ **{recommendation}**")
        fair_price = total_costs_with_overhead / 0.70  # 30% margin
        sweet_spot_price = total_costs_with_overhead / 0.60  # 40% margin
        premium_price = total_costs_with_overhead / 0.50  # 50% margin
        
        st.markdown(f"""
        **Suggested Pricing Options:**
        - 🟢 **Fair Market** (30% margin): **${math.ceil(fair_price):,}**
        - ⭐ **Sweet Spot** (40% margin): **${math.ceil(sweet_spot_price):,}** (Recommended)
        - 💎 **Premium** (50% margin): **${math.ceil(premium_price):,}**
        """)
    
    shift_type = st.selectbox("Shift Type", ["Night Shift", "Day Shift", "Weekend", "After Hours"],
                             index=["Night Shift", "Day Shift", "Weekend", "After Hours"].index(
                                 st.session_state.proposal_data.get("shift_type", "Night Shift")))
    st.session_state.proposal_data["shift_type"] = shift_type
    
    # ============================================================
    # SECTION 3: SCOPE OF WORK (Checkboxes)
    # ============================================================
    with st.expander("📋 Scope of Work (Select all that apply)", expanded=True):
        st.markdown(f"#### Select tasks to include ({property_type}):")

        template_items = PROPERTY_SCOPE_TEMPLATES.get(property_type, PROPERTY_SCOPE_TEMPLATES["Other"])

        # When the property type changes, default all of its template items to checked
        if st.session_state.proposal_data.get("scope_property_type") != property_type:
            current_scope = list(template_items)
            st.session_state.proposal_data["scope_property_type"] = property_type
        else:
            current_scope = st.session_state.proposal_data.get("scope_items", [])

        col1, col2 = st.columns(2)
        midpoint = (len(template_items) + 1) // 2

        scope_items = []
        with col1:
            for item in template_items[:midpoint]:
                if st.checkbox(item, value=item in current_scope, key=f"scope_{property_type}_{item}"):
                    scope_items.append(item)

        with col2:
            for item in template_items[midpoint:]:
                if st.checkbox(item, value=item in current_scope, key=f"scope_{property_type}_{item}"):
                    scope_items.append(item)

        additional_scope = st.text_area(
            "Additional scope items (one per line)",
            placeholder="Clean exterior windows\nPressure wash entryway\nRemove gum from floors",
            height=100)

        if additional_scope:
            for line in additional_scope.split('\n'):
                if line.strip():
                    scope_items.append(line.strip())

        st.session_state.proposal_data["scope_items"] = scope_items
    
    # ============================================================
    # SECTION 4: LOGISTICS & COMMITMENT
    # ============================================================
    with st.expander("🔑 Logistics & Commitment Statement", expanded=True):
        key_pickup = st.text_area("Key Pickup Instructions", 
                                   value=st.session_state.proposal_data.get("key_pickup", ""),
                                   height=68)
        
        commitment_statement = st.text_area("Our Commitment Statement", 
                                            value=st.session_state.proposal_data.get("commitment_statement", ""),
                                            height=100)
        
        additional_notes = st.text_area("Additional Notes (optional)", 
                                        value=st.session_state.proposal_data.get("additional_notes", ""),
                                        height=68)
        
        st.session_state.proposal_data["key_pickup"] = key_pickup
        st.session_state.proposal_data["commitment_statement"] = commitment_statement
        st.session_state.proposal_data["additional_notes"] = additional_notes
    
    # ============================================================
    # SECTION 5: Generate Professional Email
    # ============================================================
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        generate_btn = st.button("📧 Generate Professional Email", use_container_width=True, type="primary")
    
    if generate_btn:
        if not client_name:
            st.error("❌ Please enter client name")
        elif not property_address:
            st.error("❌ Please enter property address")
        else:
            current_date = datetime.now().strftime("%B %d, %Y")
            scope_text = "\n".join([f"- {item}" for item in scope_items])
            effective_hours = estimated_hours * (1.5 if is_deep_clean else 1)
            per_person_rate = total_price / crew_size / effective_hours if crew_size > 0 and effective_hours > 0 else 0

            cleaning_type_label = "first-time deep cleaning" if is_deep_clean else "regular maintenance cleaning"
            if property_type == "Grocery Store":
                walkthrough_line = f"I completed a walkthrough today and took detailed photos. The store has {num_checkout_lanes} checkout lane(s){' and a soda machine' if has_soda_machine else ''}."
            else:
                walkthrough_line = "I completed a walkthrough today and took detailed photos of the property."
            
            email_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <title>Cleaning Proposal for {client_name}</title>
                <style>
                    body {{ font-family: Arial, Helvetica, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ text-align: center; padding-bottom: 20px; border-bottom: 2px solid #10b981; margin-bottom: 20px; }}
                    .business-name {{ font-size: 24px; font-weight: bold; color: #1e3a5f; }}
                    .price-box {{ text-align: center; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 25px; border-radius: 16px; margin: 20px 0; }}
                    .price {{ font-size: 42px; font-weight: bold; margin: 10px 0; }}
                    .section {{ margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 8px; }}
                    .section-title {{ font-size: 18px; font-weight: bold; color: #1e3a5f; margin-bottom: 10px; border-left: 4px solid #10b981; padding-left: 10px; }}
                    .checklist {{ list-style: none; padding: 0; }}
                    .checklist li {{ padding: 5px 0; padding-left: 25px; position: relative; }}
                    .checklist li:before {{ content: "✓"; color: #10b981; font-weight: bold; position: absolute; left: 0; }}
                    .commitment {{ background: #e8f5e9; border-left: 4px solid #10b981; padding: 15px; margin: 20px 0; border-radius: 8px; }}
                    .footer {{ margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; text-align: center; }}
                    .signature {{ margin-top: 20px; padding-top: 10px; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <div class="business-name">Dust Bros and Co.</div>
                    <div>Professional Commercial Cleaning | Orlando, FL 32829</div>
                </div>
                
                <p><strong>Date:</strong> {current_date}</p>
                <p><strong>Dear {client_name},</strong></p>
                
                <p>Thank you for the opportunity to quote on the {cleaning_type_label} of your <strong>{property_type.lower()}</strong> at <strong>{property_address}</strong>.</p>

                <p>{walkthrough_line}</p>
                
                <div class="price-box">
                    <div class="price">${total_price:,.2f}</div>
                    <div>all-inclusive with tax • no hidden fees</div>
                    <div style="font-size: 12px; opacity: 0.9;">💵 ${per_person_rate:.2f} per person per hour</div>
                </div>
                
                <div class="section">
                    <div class="section-title">📋 Scope of Work:</div>
                    <ul class="checklist">
                        {''.join([f"<li>{item}</li>" for item in scope_items])}
                    </ul>
                </div>
                
                <div class="section">
                    <div class="section-title">👥 Crew & Schedule:</div>
                    <p><strong>Team:</strong> {crew_size} trained professional(s)</p>
                    <p><strong>Shift:</strong> {shift_type} ({estimated_hours} hours estimated)</p>
                </div>
                
                <div class="section">
                    <div class="section-title">🔑 Logistics:</div>
                    <p>{key_pickup}</p>
                </div>
                
                <div class="commitment">
                    <strong>🤝 Our Commitment to You</strong><br>
                    {commitment_statement}
                </div>
                
                <div class="section">
                    <div class="section-title">💰 Payment Options:</div>
                    <p>Venmo, Zelle, cash, wire, credit card, or pay-by-link. No checks.</p>
                </div>
                
                <div class="signature">
                    <p>Best regards,<br><strong>Elvis</strong><br>Dust Bros and Co.<br>📧 dustbrosco@gmail.com</p>
                </div>
                
                <div class="footer">
                    <p><em>{additional_notes}</em></p>
                    <p>This proposal is valid for 30 days from {current_date}.</p>
                </div>
            </body>
            </html>
            """
            
            email_text = f"""
Dust Bros and Co.
Professional Commercial Cleaning
Orlando, FL 32829

Date: {current_date}

Dear {client_name},

Thank you for the opportunity to quote on the {cleaning_type_label} of your {property_type.lower()} at {property_address}.

{walkthrough_line}

Total Price: ${total_price:,.2f} (all-inclusive with tax)

Scope of Work:
{scope_text}

Crew & Schedule:
Team of {crew_size} cleaner(s) during {shift_type.lower()} ({estimated_hours} hours estimated).

Logistics:
{key_pickup}

🤝 Our Commitment to You:
{commitment_statement}

Payment Options:
Venmo, Zelle, cash, wire, credit card, or pay-by-link. No checks.

{additional_notes}

Best regards,
Elvis
Dust Bros and Co.
dustbrosco@gmail.com

---
This proposal is valid for 30 days from {current_date}.
"""
            
            st.session_state.generated_email_html = email_html
            st.session_state.generated_email_text = email_text
            st.session_state.generated_email_price = total_price
            st.session_state.generated_email_client = client_name
            st.session_state.generated_email_address = property_address
    
    if 'generated_email_html' in st.session_state:
        st.markdown("---")
        st.markdown("### 📧 Your Professional Email is Ready")
        
        st.info(f"""
        **📊 Final Profit Summary:**
        - 💰 Proposed Price: **${total_price:,.2f}**
        - 💸 Total Costs: **${total_costs_with_overhead:,.2f}**
        - 📈 Profit: **${profit:,.2f}** ({profit_margin:.1f}% margin)
        - 🎯 Status: **{margin_status}**
        """)
        
        tab1, tab2, tab3 = st.tabs(["📧 Email Preview", "📋 Plain Text Version", "💾 Save/Send"])
        
        with tab1:
            st.components.v1.html(st.session_state.generated_email_html, height=600, scrolling=True)
            
            col1, col2 = st.columns(2)
            with col1:
                st.download_button("📥 Download HTML", st.session_state.generated_email_html, 
                                   f"Proposal_{st.session_state.generated_email_client.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.html", 
                                   "text/html", use_container_width=True)
            with col2:
                st.download_button("📥 Download Text", st.session_state.generated_email_text,
                                   f"Proposal_{st.session_state.generated_email_client.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                                   "text/plain", use_container_width=True)
        
        with tab2:
            st.text_area("Plain Text Version", st.session_state.generated_email_text, height=400)
        
        with tab3:
            email_to = st.text_input("Recipient Email", value=st.session_state.proposal_data.get("client_email", ""))
            email_subject = st.text_input("Subject", value=f"Cleaning Proposal for {st.session_state.generated_email_client}")
            cc_me = st.checkbox("Send a copy to myself", value=True)
            
            if st.button("📧 Send Email to Client", use_container_width=True, type="primary"):
                if email_to:
                    company_id = get_current_user_company()
                    success = send_email(company_id, email_to, email_subject, 
                                        st.session_state.generated_email_text,
                                        st.session_state.generated_email_html)
                    
                    if success and cc_me:
                        user_email = st.session_state.user.get('email', '')
                        if user_email:
                            send_email(company_id, user_email, f"COPY: {email_subject}", 
                                      st.session_state.generated_email_text,
                                      st.session_state.generated_email_html)
                    
                    if success:
                        st.success(f"✅ Proposal sent to {email_to}")
                        st.balloons()
                    else:
                        st.error("❌ Failed to send. Check SMTP settings.")
                else:
                    st.warning("Please enter recipient email address")
def quick_job_page():
    if st.button(t("back")):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown(t("quick_title"))
    company_id = get_current_user_company()
    with st.form("quick"):
        date = st.date_input(t("quick_date"), datetime.now())
        desc = st.text_input(t("quick_description"))
        hours = st.number_input(t("quick_hours"), 0.5, 24.0, 2.0)
        amount = st.number_input(t("quick_amount"), 0.0, 10000.0, 350.0)
        expenses = st.number_input(t("quick_expenses"), 0.0, 500.0, 25.0)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT hourly_wage FROM business_profile WHERE company_id = ?", (company_id,))
        row = c.fetchone()
        conn.close()
        hourly = row[0] if row else 15.0
        profit = amount - expenses - (hours * hourly)
        st.metric(t("quick_estimated_profit"), f"${profit:.2f}")
        if st.form_submit_button(t("quick_save")):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("INSERT INTO quick_jobs (company_id, user_id, job_date, description, hours, amount_invoiced, job_expenses, profit, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (company_id, st.session_state.user['user_id'], date.isoformat(), desc, hours, amount, expenses, profit, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            update_worker_badges(st.session_state.user['user_id'])
            st.success(t("quick_saved"))
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
                if st.session_state.get('edit_client_id') == row['id']:
                    with st.form(f"edit_client_form_{row['id']}"):
                        e_business = st.text_input("Business Name *", row['business_name'])
                        e_contact = st.text_input("Contact Name", row['contact_name'] or "")
                        e_phone = st.text_input("Phone", row['phone'] or "")
                        e_email = st.text_input("Email", row['email'] or "")
                        e_address = st.text_input("Address", row['address'] or "")
                        e_city = st.text_input("City", row['city'] or "")
                        e_state = st.text_input("State", row['state'] or "FL")
                        e_zip = st.text_input("Zip", row['zip'] or "")
                        e_lat = st.number_input("Latitude", value=float(row['lat'] or 0.0), format="%.6f")
                        e_lon = st.number_input("Longitude", value=float(row['lon'] or 0.0), format="%.6f")
                        e_notes = st.text_area("Notes", row['notes'] or "")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.form_submit_button("💾 Save Changes"):
                                if e_business:
                                    update_client(row['id'], e_business, e_contact, e_phone, e_email, e_address, e_city, e_state, e_zip, e_lat, e_lon, e_notes)
                                    st.session_state.edit_client_id = None
                                    st.success("Client updated")
                                    st.rerun()
                                else:
                                    st.error("Business name required")
                        with col_b:
                            if st.form_submit_button("Cancel"):
                                st.session_state.edit_client_id = None
                                st.rerun()
                else:
                    st.write(f"Contact: {row['contact_name'] or 'N/A'}, Phone: {row['phone'] or 'N/A'}, Email: {row['email'] or 'N/A'}")
                    st.write(f"Address: {row['address'] or 'N/A'}, {row['city'] or 'N/A'}, {row['state']} {row['zip']}")
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"✏️ Edit", key=f"edit_{row['id']}"):
                            st.session_state.edit_client_id = row['id']
                            st.rerun()
                    with col2:
                        if st.button(f"🗑️ Delete", key=f"del_{row['id']}"):
                            delete_client(row['id'])
                            st.rerun()

def workers_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 👷 Worker Management")
    user = st.session_state.user
    company_id = get_current_user_company()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    has_invite_code = 'invite_code' in columns
    conn.close()
    
    if user['role'] == 'super_admin':
        conn = sqlite3.connect(DB_PATH)
        if has_invite_code:
            workers = pd.read_sql_query("SELECT id, username, email, company_id, manager_id, supervisor_id, role, is_active, hire_date, invite_code FROM users WHERE role IN ('worker','supervisor','manager')", conn)
        else:
            workers = pd.read_sql_query("SELECT id, username, email, company_id, manager_id, supervisor_id, role, is_active, hire_date FROM users WHERE role IN ('worker','supervisor','manager')", conn)
        conn.close()
        st.subheader("All Workers (All Companies)")
        st.dataframe(workers)

        st.markdown("#### Transfer Worker Between Companies")
        st.caption("Moving a worker between companies is a platform-level action restricted to super admins.")
        render_worker_transfer_ui("super_admin_workers_page")
    elif user['role'] == 'support_staff':
        conn = sqlite3.connect(DB_PATH)
        if has_invite_code:
            workers = pd.read_sql_query("SELECT id, username, email, company_id, manager_id, supervisor_id, role, is_active, hire_date, invite_code FROM users", conn)
        else:
            workers = pd.read_sql_query("SELECT id, username, email, company_id, manager_id, supervisor_id, role, is_active, hire_date FROM users", conn)
        conn.close()
        st.subheader("All Workers (Troubleshooting View)")
        st.dataframe(workers)
        st.info("Support staff can view all users but cannot modify them here. Use Admin Tools to switch company.")
    elif user['role'] == 'admin':
        conn = sqlite3.connect(DB_PATH)
        if has_invite_code:
            workers = pd.read_sql_query("SELECT id, username, email, manager_id, supervisor_id, role, is_active, hire_date, invite_code FROM users WHERE company_id = ?", conn, params=(company_id,))
        else:
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
        st.markdown("#### Manage Worker")
        if not workers.empty:
            sel_worker = st.selectbox("Select worker to manage", workers['id'].tolist(), format_func=lambda x: f"{workers[workers['id']==x]['username'].iloc[0]} ({x})")
            # NOTE: "Transfer Worker" used to live here, letting a single
            # company's admin move a worker into ANY active company (the
            # destination list was every company in the system, not just
            # this admin's own tenant) -- a cross-tenant authorization bug.
            # Moving a worker between companies is a platform-level action,
            # so it has been moved to the super_admin view below.
            col1, col2 = st.columns([2,1])
            with col1:
                if st.button("Deactivate Worker"):
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    try:
                        c.execute("UPDATE users SET is_active = 0 WHERE id = ?", (sel_worker,))
                        c.execute("INSERT INTO audit_log (user_id, action, details, created_at) VALUES (?,?,?,?)",
                                  (st.session_state.user['user_id'], 'deactivate_worker', f'Worker {sel_worker} deactivated', datetime.now().isoformat()))
                        conn.commit()
                        conn.close()
                        st.success("Worker deactivated")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        conn.close()
                        st.error(f"Failed to deactivate: {e}")
            with col2:
                if st.button("Refresh List"):
                    st.rerun()
    elif user['role'] in ('manager', 'supervisor'):
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
    else:
        st.info("This page is for managers and supervisors. Contact your manager if you need to invite a worker.")

def schedule_page():
    if st.button(t("back")):
        st.session_state.page = "dashboard"
        st.rerun()

    st.markdown(t("schedule_title"))

    user_role = st.session_state.user['role']
    company_id = get_current_user_company()
    user_id = st.session_state.user['user_id']

    # View is allowed for all roles
    view_date = st.date_input(t("schedule_date"), datetime.now())
    status_filter = st.selectbox(t("schedule_status"), ["All","scheduled","completed","cancelled"])
    df = get_scheduled_jobs(date_filter=view_date, status_filter=status_filter)

    if df.empty:
        st.info(t("schedule_no_jobs"))
    else:
        # Display jobs with action buttons based on permissions
        for _, job in df.iterrows():
            with st.container():
                if st.session_state.get('edit_job_id') == job['id']:
                    with st.form(f"edit_job_form_{job['id']}"):
                        e_date = st.date_input("Date", datetime.fromisoformat(job['scheduled_date']))
                        e_time = st.selectbox("Time", ["8:00 AM","9:00 AM","10:00 AM","11:00 AM","12:00 PM","1:00 PM","2:00 PM","3:00 PM","4:00 PM"],
                                               index=["8:00 AM","9:00 AM","10:00 AM","11:00 AM","12:00 PM","1:00 PM","2:00 PM","3:00 PM","4:00 PM"].index(job['scheduled_time']) if job['scheduled_time'] in ["8:00 AM","9:00 AM","10:00 AM","11:00 AM","12:00 PM","1:00 PM","2:00 PM","3:00 PM","4:00 PM"] else 0)
                        e_status = st.selectbox("Status", ["scheduled","completed","cancelled"],
                                                 index=["scheduled","completed","cancelled"].index(job['status']) if job['status'] in ["scheduled","completed","cancelled"] else 0)
                        e_notes = st.text_area("Notes", job['notes'] or "")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            if st.form_submit_button("💾 Save Changes"):
                                conn = sqlite3.connect(DB_PATH)
                                c = conn.cursor()
                                c.execute("UPDATE scheduled_jobs SET scheduled_date = ?, scheduled_time = ?, status = ?, notes = ? WHERE id = ? AND company_id = ?",
                                          (e_date.isoformat(), e_time, e_status, e_notes, job['id'], company_id))
                                conn.commit()
                                conn.close()
                                log_activity(company_id, user_id, 'edit_job', 'scheduled_job', job['id'], f"Edited job for {job['client_name']}")
                                st.session_state.edit_job_id = None
                                st.success("Job updated")
                                st.rerun()
                        with col_b:
                            if st.form_submit_button("Cancel"):
                                st.session_state.edit_job_id = None
                                st.rerun()
                    st.markdown("---")
                    continue

                col1, col2, col3, col4 = st.columns([3, 2, 2, 2])

                with col1:
                    st.markdown(f"**{job['client_name']}**")
                    st.caption(f"{job['scheduled_time']} | {t('schedule_worker_label')}: {job['assigned_worker_id'] or t('schedule_worker_unassigned')}")

                with col2:
                    st.markdown(f"{t('schedule_status')}: {job['status']}")

                with col3:
                    # Edit button - only for admin/manager
                    if has_permission(user_role, 'edit_event'):
                        if st.button(t("schedule_edit"), key=f"edit_{job['id']}"):
                            st.session_state.edit_job_id = job['id']
                            st.rerun()

                with col4:
                    # Delete/Move buttons with approval logic
                    if can_delete_directly(user_role):
                        if st.button(t("schedule_delete"), key=f"del_{job['id']}"):
                            if st.confirm(f"Delete job for {job['client_name']}?"):
                                conn = sqlite3.connect(DB_PATH)
                                c = conn.cursor()
                                c.execute("DELETE FROM scheduled_jobs WHERE id = ? AND company_id = ?", (job['id'], company_id))
                                conn.commit()
                                conn.close()
                                log_activity(company_id, user_id, 'delete_job', 'scheduled_job', job['id'], f"Deleted job for {job['client_name']}")
                                st.success(t("schedule_job_deleted"))
                                st.rerun()
                    else:
                        if st.button(t("schedule_request_delete"), key=f"req_del_{job['id']}"):
                            with st.expander(f"Request deletion for {job['client_name']}", key=f"exp_del_{job['id']}"):
                                reason = st.text_input(t("schedule_delete_reason"), key=f"reason_{job['id']}")
                                if st.button(t("schedule_submit_request"), key=f"submit_del_{job['id']}"):
                                    create_approval_request(
                                        company_id, user_id, 'delete_event', 'scheduled_job',
                                        job['id'], None, reason
                                    )
                                    log_activity(company_id, user_id, 'request_delete', 'scheduled_job', job['id'], f"Requested deletion: {reason}")
                                    st.success(t("schedule_deletion_sent"))
                                    st.rerun()

                st.markdown("---")

    # Add job - allowed for most roles
    if has_permission(user_role, 'add_event'):
        with st.expander(t("schedule_add_job")):
            clients_df = get_all_clients()
            client_options = [t("schedule_select")] + clients_df['business_name'].tolist()
            client = st.selectbox(t("schedule_client"), client_options)
            accessible_workers = get_accessible_user_ids(st.session_state.user['user_id'], st.session_state.user['role'], company_id)
            placeholders = ','.join(['?' for _ in accessible_workers])
            conn = sqlite3.connect(DB_PATH)
            workers_df = pd.read_sql_query(f"SELECT id, username FROM users WHERE role='worker' AND company_id = ? AND id IN ({placeholders})", conn, params=[company_id] + accessible_workers)
            conn.close()
            worker_options = [t("schedule_worker_unassigned")] + workers_df['username'].tolist()
            worker = st.selectbox(t("schedule_worker_label"), worker_options)
            time_slot = st.selectbox(t("schedule_time"), ["8:00 AM","9:00 AM","10:00 AM","11:00 AM","12:00 PM","1:00 PM","2:00 PM","3:00 PM","4:00 PM"])
            if st.button(t("schedule_schedule_btn")):
                if client != t("schedule_select"):
                    client_id = clients_df[clients_df['business_name']==client]['id'].values[0]
                    worker_id = None if worker==t("schedule_worker_unassigned") else workers_df[workers_df['username']==worker]['id'].values[0]
                    schedule_job(client_id, client, "", None, worker_id, view_date, time_slot)
                    log_activity(company_id, user_id, 'add_job', 'scheduled_job', None, f"Added job for {client}")
                    st.success(t("schedule_scheduled"))
                    st.rerun()


def admin_approval_dashboard():
    """Admin dashboard to manage approval requests"""
    
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📋 Approval Requests Dashboard")
    st.caption("Review and manage requests from workers")
    
    user_role = st.session_state.user['role']
    
    if not has_permission(user_role, 'approve_requests'):
        st.error("❌ You don't have permission to view this page")
        return
    
    company_id = get_current_user_company()
    user_id = st.session_state.user['user_id']
    
    # Get pending requests
    pending_requests = get_pending_approval_requests(company_id)
    
    if pending_requests.empty:
        st.info("No pending approval requests")
    else:
        for _, req in pending_requests.iterrows():
            with st.container():
                col1, col2, col3 = st.columns([2, 1, 2])
                
                with col1:
                    st.markdown(f"**{req['request_type'].upper()} Request**")
                    st.caption(f"From: {req['requester_name']}")
                    st.caption(f"Target: {req['target_type']} #{req['target_id']}")
                    if req['reason']:
                        st.caption(f"Reason: {req['reason']}")
                
                with col2:
                    st.markdown(f"**Current:** {req['current_value']}")
                    if req['requested_value']:
                        st.markdown(f"**Requested:** {req['requested_value']}")
                
                with col3:
                    col_a, col_b = st.columns(2)
                    with col_a:
                        admin_notes = st.text_input("Notes", key=f"notes_{req['id']}")
                        if st.button(f"✅ Approve", key=f"approve_{req['id']}"):
                            success, msg = approve_request(req['id'], user_id, admin_notes)
                            if success:
                                log_activity(company_id, user_id, 'approve_request', 'approval_request', req['id'], f"Approved {req['request_type']} request from {req['requester_name']}")
                                st.success(msg)
                            else:
                                st.error(msg)
                            st.rerun()
                    with col_b:
                        if st.button(f"❌ Reject", key=f"reject_{req['id']}"):
                            if admin_notes:
                                reject_request(req['id'], user_id, admin_notes)
                                log_activity(company_id, user_id, 'reject_request', 'approval_request', req['id'], f"Rejected {req['request_type']} request from {req['requester_name']}")
                                st.success("Request rejected")
                                st.rerun()
                            else:
                                st.warning("Please provide a reason for rejection")
                
                st.markdown("---")


def job_templates_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### 📋 Job Templates")
    company_id = get_current_user_company()
    
    templates = get_job_templates(company_id)
    if templates.empty:
        st.info("No job templates yet. Create one below.")
    else:
        st.dataframe(templates)
    
    with st.expander("➕ Create New Template"):
        with st.form("create_template"):
            name = st.text_input("Template Name *")
            description = st.text_area("Description")
            property_type = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()))
            estimated_hours = st.number_input("Estimated Hours", 0.5, 20.0, 2.0)
            task_list_text = st.text_area("Task List (one per line)", "Vacuum floors\nDust surfaces\nClean restrooms\nEmpty trash")
            if st.form_submit_button("Create Template"):
                if name:
                    tasks = [t.strip() for t in task_list_text.split('\n') if t.strip()]
                    create_job_template(company_id, name, description, property_type, estimated_hours, tasks)
                    st.success("Template created")
                    st.rerun()
                else:
                    st.error("Template name required")

def calculate_inspection_estimate(data):
    """Calculate ballpark estimate from inspection data (Medium to High range, excludes travel/tolls)"""
    
    base_price = 0
    adjustments = 0
    adjustment_details = []
    
    # ============================================================
    # BASE PRICE FROM SQUARE FOOTAGE
    # ============================================================
    sqft = data['square_feet']
    
    # Base rate per sq ft (Medium to High range)
    base_rate_per_sqft = 0.18  # Florida average for commercial
    
    # Adjust for property type
    property_multipliers = {
        "Office": 1.0,
        "Retail": 1.1,
        "Warehouse": 0.85,
        "Medical/Dental": 1.5,
        "Restaurant": 2.0,
        "School/Daycare": 1.3,
        "Hotel": 1.2,
        "Gym/Fitness": 1.3,
        "Church": 1.0,
        "Other": 1.0
    }
    
    prop_mult = property_multipliers.get(data['property_type'], 1.0)
    
    # Adjust for frequency
    freq_multipliers = {
        "One-time": 1.0,
        "Daily": 0.7,
        "Weekly": 0.85,
        "Bi-weekly": 1.0,
        "Monthly": 1.2
    }
    
    freq_mult = freq_multipliers.get(data['frequency'], 1.0)
    
    # Adjust for floors
    floor_penalty = 1 + ((data['num_floors'] - 1) * 0.10) if data['num_floors'] > 1 else 1
    if not data['has_elevator'] and data['num_floors'] > 1:
        floor_penalty += 0.05 * (data['num_floors'] - 1)
    
    # Adjust for multiple buildings
    building_penalty = 1 + ((data['num_buildings'] - 1) * 0.15) if data['num_buildings'] > 1 else 1
    
    # Complexity factor
    complexity_factor = 1 + ((data['special']['complexity'] - 3) * 0.05)
    
    base_price = sqft * base_rate_per_sqft * prop_mult * freq_mult * floor_penalty * building_penalty * complexity_factor
    
    # ============================================================
    # ADD-ONS (Based on inspection findings)
    # ============================================================
    
    # Restrooms
    restroom_fixtures = (
        data['restrooms']['toilets'] * 3.50 +
        data['restrooms']['urinals'] * 2.50 +
        data['restrooms']['sinks'] * 4.00 +
        data['restrooms']['mirrors'] * 2.00
    )
    if restroom_fixtures > 0:
        adjustments += restroom_fixtures
        adjustment_details.append(f"Restroom fixtures: ${restroom_fixtures:.0f}")
    
    if data['restrooms']['showers'] > 0:
        shower_cost = data['restrooms']['showers'] * 8.00
        adjustments += shower_cost
        adjustment_details.append(f"Showers: ${shower_cost:.0f}")
    
    if data['restrooms']['deep_clean']:
        deep_clean_cost = 75
        adjustments += deep_clean_cost
        adjustment_details.append(f"Restroom deep clean: ${deep_clean_cost}")
    
    # Windows
    window_cost = (
        data['windows']['interior'] * 3.00 +
        data['windows']['exterior'] * 5.00 +
        data['windows']['high'] * 12.00 +
        data['windows']['glass_doors'] * 4.00 +
        data['windows']['partitions'] * 2.00 +
        data['windows']['mirrors'] * 2.00
    )
    if window_cost > 0:
        adjustments += window_cost
        adjustment_details.append(f"Windows/glass: ${window_cost:.0f}")
    
    if data['windows']['tracks']:
        track_cost = data['windows']['interior'] * 2.00 if data['windows']['interior'] > 0 else 25
        adjustments += track_cost
        adjustment_details.append(f"Window tracks: ${track_cost:.0f}")
    
    # Floors
    floor_cleaning = (
        data['floors']['carpet_sqft'] * 0.05 +
        data['floors']['tile_sqft'] * 0.08 +
        data['floors']['vinyl_sqft'] * 0.07 +
        data['floors']['hardwood_sqft'] * 0.12 +
        data['floors']['concrete_sqft'] * 0.04
    )
    if floor_cleaning > 0:
        adjustments += floor_cleaning
        adjustment_details.append(f"Floor cleaning: ${floor_cleaning:.0f}")
    
    if data['floors']['carpet_extract']:
        extract_cost = data['floors'].get('carpet_sqft', 0) * 0.20
        adjustments += extract_cost
        adjustment_details.append(f"Carpet extraction: ${extract_cost:.0f}")
    
    if data['floors']['strip_wax']:
        strip_cost = (data['floors']['tile_sqft'] + data['floors']['vinyl_sqft']) * 0.35
        adjustments += strip_cost
        adjustment_details.append(f"Strip & wax: ${strip_cost:.0f}")
    
    # Furniture & Equipment
    furniture_cost = (
        data['furniture']['desks'] * 2.00 +
        data['furniture']['computers'] * 1.50 +
        data['furniture']['phones'] * 1.00 +
        data['furniture']['chairs'] * 1.00 +
        data['furniture']['tables'] * 3.00 +
        data['furniture']['whiteboards'] * 2.00
    )
    if furniture_cost > 0:
        adjustments += furniture_cost
        adjustment_details.append(f"Furniture/equipment: ${furniture_cost:.0f}")
    
    # Moving furniture
    moving_cost = data['furniture']['move_light'] * 2.00 + data['furniture']['move_heavy'] * 15.00
    if moving_cost > 0:
        adjustments += moving_cost
        adjustment_details.append(f"Moving furniture: ${moving_cost:.0f}")
    
    if data['furniture']['clean_under'] and moving_cost > 0:
        under_cost = data['furniture']['move_heavy'] * 10.00 if data['furniture']['move_heavy'] > 0 else 25
        adjustments += under_cost
        adjustment_details.append(f"Clean under items: ${under_cost:.0f}")
    
    # Special conditions
    if data['special']['high_dusting']:
        dust_cost = sqft * 0.015
        adjustments += dust_cost
        adjustment_details.append(f"High dusting: ${dust_cost:.0f}")
    
    if data['special']['blinds'] > 0:
        blind_cost = data['special']['blinds'] * 4.00
        adjustments += blind_cost
        adjustment_details.append(f"Blinds: ${blind_cost:.0f}")
    
    if data['special']['disinfection']:
        disinfection_cost = sqft * 0.03
        adjustments += disinfection_cost
        adjustment_details.append(f"Disinfection: ${disinfection_cost:.0f}")
    
    if data['special']['odor_control']:
        adjustments += 45
        adjustment_details.append("Odor control: $45")
    
    if data['special']['post_construction']:
        post_cost = sqft * 0.15
        adjustments += post_cost
        adjustment_details.append(f"Post-construction: ${post_cost:.0f}")
    
    subtotal = base_price + adjustments
    if data['special']['emergency']:
        emergency_surcharge = subtotal * 0.25
        adjustments += emergency_surcharge
        adjustment_details.append(f"Emergency/Rush: +25% (${emergency_surcharge:.0f})")
        subtotal = base_price + adjustments
    
    if data['special']['holiday'] == "Yes - Holiday":
        holiday_surcharge = subtotal * 0.35
        adjustments += holiday_surcharge
        adjustment_details.append(f"Holiday surcharge: +35% (${holiday_surcharge:.0f})")
        subtotal = base_price + adjustments
    elif data['special']['holiday'] == "Yes - Weekend":
        weekend_surcharge = subtotal * 0.25
        adjustments += weekend_surcharge
        adjustment_details.append(f"Weekend surcharge: +25% (${weekend_surcharge:.0f})")
        subtotal = base_price + adjustments
    
    if data['special']['supply_provided']:
        supply_discount = subtotal * 0.10
        adjustments -= supply_discount
        adjustment_details.append(f"Client provides supplies: -10% (${supply_discount:.0f})")
    
    # Access time adjustment
    if data['access_time'] == "After hours (6PM-6AM)":
        adjustments += base_price * 0.20
        adjustment_details.append("After-hours access: +20%")
    elif data['access_time'] == "Weekend only":
        adjustments += base_price * 0.25
        adjustment_details.append("Weekend only: +25%")
    elif data['access_time'] == "Very restricted window":
        adjustments += base_price * 0.35
        adjustment_details.append("Restricted access: +35%")
    
    # Areas multiplier
    area_count = sum([
        1 if data['areas']['reception'] else 0,
        1 if data['areas']['breakroom'] else 0,
        1 if data['areas']['hallways'] else 0,
        1 if data['areas']['loading_dock'] else 0,
        data['areas']['private_offices'] / 5 if data['areas']['private_offices'] > 0 else 0,
        data['areas']['conference_rooms'] / 2 if data['areas']['conference_rooms'] > 0 else 0
    ])
    
    if area_count > 3:
        area_multiplier = 1 + (area_count * 0.05)
        base_price *= area_multiplier
        adjustment_details.append(f"Multiple areas ({int(area_count)}): +{int((area_multiplier-1)*100)}%")
    
    # Minimum job fee
    final_price = base_price + adjustments
    if final_price < 150:
        final_price = 150
        adjustment_details.append("Minimum job fee applied: $150")
    
    # Round to nearest $25 for ballpark
    final_price = round(final_price / 25) * 25
    
    # Generate included summary
    included_summary = f"- {sqft:,} sq ft {data['property_type']} cleaning\n"
    included_summary += f"- {data['frequency']} frequency\n"
    if data['num_floors'] > 1:
        included_summary += f"- {data['num_floors']} floors\n"
    if data['restrooms']['toilets'] > 0:
        included_summary += f"- {data['restrooms']['toilets']} toilet(s), {data['restrooms']['sinks']} sink(s)\n"
    if data['windows']['interior'] > 0:
        included_summary += f"- {data['windows']['interior']} interior windows\n"
    
    adjustment_summary = "\n".join([f"- {detail}" for detail in adjustment_details[:10]])
    if len(adjustment_details) > 10:
        adjustment_summary += f"\n- ... and {len(adjustment_details) - 10} more adjustments"
    
    # Calculate confidence score
    confidence = 70
    if data['special']['complexity'] >= 5:
        confidence -= 10
    if sqft > 0:
        confidence += 10
    if len(adjustment_details) > 5:
        confidence += 10
    confidence = min(95, max(40, confidence))
    
    return {
        "base_price": round(base_price),
        "adjustments": round(adjustments),
        "final_price": final_price,
        "included_summary": included_summary,
        "adjustment_summary": adjustment_summary,
        "confidence": confidence
    }


def pre_inspection_page():
    """Quick pre-inspection checklist for ballpark estimates (Medium to High range)"""
    if st.button(t("insp_back_dashboard")):
        st.session_state.page = "dashboard"
        st.rerun()

    if 'user' not in st.session_state or not st.session_state.user:
        st.warning(t("insp_login_required"))
        st.session_state.page = "login"
        st.rerun()
        return

    st.markdown(t("insp_title"))
    st.caption(t("insp_caption"))

    # Create tabs for different inspection categories
    tabs = st.tabs([
        t("insp_tab_basics"),
        t("insp_tab_areas"),
        t("insp_tab_windows"),
        t("insp_tab_restrooms"),
        t("insp_tab_floors"),
        t("insp_tab_equipment"),
        t("insp_tab_special"),
    ])

    # ============================================================
    # TAB 1: PROPERTY BASICS
    # ============================================================
    with tabs[0]:
        st.markdown(t("insp_property_info"))

        col1, col2 = st.columns(2)
        with col1:
            prop_type_values = ["Office", "Retail", "Warehouse", "Medical/Dental", "Restaurant",
                                 "School/Daycare", "Hotel", "Gym/Fitness", "Church", "Other"]
            property_type = st.selectbox(
                t("insp_property_type"),
                prop_type_values,
                format_func=lambda v: t(f"insp_prop_{v}"),
                key="insp_prop_type"
            )

            if property_type == "Other":
                property_type_other = st.text_input(t("insp_please_specify"), key="insp_prop_other")
                property_type = property_type_other if property_type_other else "Other"

            square_feet = st.number_input(t("insp_sqft"), min_value=100, max_value=500000, value=2000, step=500, key="insp_sqft")

        with col2:
            num_floors = st.number_input(t("insp_num_floors"), min_value=1, max_value=20, value=1, key="insp_floors")
            has_elevator = st.checkbox(t("insp_has_elevator"), key="insp_elevator")
            multi_building = st.checkbox(t("insp_multi_building"), key="insp_multi_building")

            if multi_building:
                num_buildings = st.number_input(t("insp_num_buildings"), min_value=2, max_value=10, value=2, key="insp_buildings")
            else:
                num_buildings = 1

        st.markdown("---")
        st.markdown(t("insp_job_timing"))

        col1, col2 = st.columns(2)
        with col1:
            freq_values = ["One-time", "Daily", "Weekly", "Bi-weekly", "Monthly"]
            frequency = st.selectbox(
                t("insp_frequency"),
                freq_values,
                format_func=lambda v: t(f"insp_freq_{v}"),
                key="insp_freq"
            )

        with col2:
            access_values = ["Normal business hours", "After hours (6PM-6AM)", "Weekend only", "Very restricted window"]
            access_time = st.selectbox(
                t("insp_access_time"),
                access_values,
                format_func=lambda v: t(f"insp_access_{v}"),
                key="insp_access"
            )

    # ============================================================
    # TAB 2: AREAS TO CLEAN
    # ============================================================
    with tabs[1]:
        st.markdown(t("insp_select_areas"))
        st.caption(t("insp_check_all"))

        col1, col2, col3 = st.columns(3)

        with col1:
            reception_area = st.checkbox(t("insp_reception"), key="insp_reception")
            private_offices = st.number_input(t("insp_private_offices"), min_value=0, value=0, key="insp_offices")
            open_workstations = st.number_input(t("insp_workstations"), min_value=0, value=0, key="insp_workstations")
            conference_rooms = st.number_input(t("insp_conference_rooms"), min_value=0, value=0, key="insp_conference")
            breakroom_kitchen = st.checkbox(t("insp_breakroom"), key="insp_breakroom")

        with col2:
            hallways = st.checkbox(t("insp_hallways"), key="insp_hallways")
            stairwells = st.number_input(t("insp_stairwells"), min_value=0, value=0, key="insp_stairs")
            storage_rooms = st.number_input(t("insp_storage_rooms"), min_value=0, value=0, key="insp_storage")
            st.checkbox(t("insp_janitor_closet"), key="insp_janitor")
            loading_dock = st.checkbox(t("insp_loading_dock"), key="insp_dock")

        with col3:
            exterior_entry = st.checkbox(t("insp_exterior_entry"), key="insp_exterior")
            st.checkbox(t("insp_sidewalk"), key="insp_sidewalk")
            st.checkbox(t("insp_parking_garage"), key="insp_parking")
            trash_recycling = st.checkbox(t("insp_trash"), key="insp_trash")

    # ============================================================
    # TAB 3: WINDOWS & GLASS
    # ============================================================
    with tabs[2]:
        st.markdown(t("insp_window_title"))

        col1, col2 = st.columns(2)

        with col1:
            interior_windows = st.number_input(t("insp_interior_windows"), min_value=0, value=0, key="insp_int_windows", help="Count individual window panes")
            exterior_windows = st.number_input(t("insp_exterior_windows"), min_value=0, value=0, key="insp_ext_windows")
            high_windows = st.number_input(t("insp_high_windows"), min_value=0, value=0, key="insp_high_windows")

        with col2:
            glass_doors = st.number_input(t("insp_glass_doors"), min_value=0, value=0, key="insp_glass_doors")
            glass_partitions = st.number_input(t("insp_glass_partitions"), min_value=0, value=0, key="insp_partitions")
            mirrors = st.number_input(t("insp_mirrors"), min_value=0, value=0, key="insp_mirrors")

        window_tracks = st.checkbox(t("insp_window_tracks"), key="insp_tracks")
        st.checkbox(t("insp_window_screens"), key="insp_screens")

    # ============================================================
    # TAB 4: RESTROOMS
    # ============================================================
    with tabs[3]:
        st.markdown(t("insp_restroom_title"))

        col1, col2, col3 = st.columns(3)

        with col1:
            num_toilets = st.number_input(t("insp_toilets"), min_value=0, value=0, key="insp_toilets")
            num_urinals = st.number_input(t("insp_urinals"), min_value=0, value=0, key="insp_urinals")

        with col2:
            num_sinks = st.number_input(t("insp_sinks"), min_value=0, value=0, key="insp_sinks")
            num_mirrors_rest = st.number_input(t("insp_rest_mirrors"), min_value=0, value=0, key="insp_rest_mirrors")

        with col3:
            num_showers = st.number_input(t("insp_showers"), min_value=0, value=0, key="insp_showers")
            restroom_count = st.number_input(t("insp_restroom_count"), min_value=0, value=0, key="insp_restroom_count")

        deep_clean = st.checkbox(t("insp_deep_clean"), key="insp_deep_clean")
        restock_supplies = st.checkbox(t("insp_restock"), key="insp_restock")
    
    # ============================================================
    # TAB 5: FLOORS
    # ============================================================
    with tabs[4]:
        st.markdown(t("insp_floor_title"))

        col1, col2 = st.columns(2)

        with col1:
            carpet_sqft = st.number_input(t("insp_carpet"), min_value=0, value=0, key="insp_carpet")
            tile_sqft = st.number_input(t("insp_tile"), min_value=0, value=0, key="insp_tile")
            vinyl_sqft = st.number_input(t("insp_vinyl"), min_value=0, value=0, key="insp_vinyl")

        with col2:
            hardwood_sqft = st.number_input(t("insp_hardwood"), min_value=0, value=0, key="insp_hardwood")
            concrete_sqft = st.number_input(t("insp_concrete"), min_value=0, value=0, key="insp_concrete")

            floor_condition = st.select_slider(
                t("insp_floor_condition"),
                options=["Excellent", "Good", "Fair", "Poor", "Very Poor"],
                value="Good",
                format_func=lambda v: t(f"insp_floorcond_{v}"),
                key="insp_floor_condition"
            )

        st.markdown(t("insp_additional_floor"))
        col1, col2, col3 = st.columns(3)

        with col1:
            carpet_extract = st.checkbox(t("insp_carpet_extract"), key="insp_extract")
        with col2:
            strip_wax = st.checkbox(t("insp_strip_wax"), key="insp_wax")
        with col3:
            floor_buff = st.checkbox(t("insp_floor_buff"), key="insp_buff")

        if carpet_extract:
            st.number_input(t("insp_extract_sqft"), min_value=0, value=carpet_sqft, key="insp_extract_sqft")

        # Area rugs
        st.markdown(t("insp_area_rugs"))
        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input(t("insp_rug_small"), min_value=0, value=0, key="insp_small_rugs")
        with col2:
            st.number_input(t("insp_rug_medium"), min_value=0, value=0, key="insp_medium_rugs")
        with col3:
            st.number_input(t("insp_rug_large"), min_value=0, value=0, key="insp_large_rugs")

    # ============================================================
    # TAB 6: EQUIPMENT & FURNITURE
    # ============================================================
    with tabs[5]:
        st.markdown(t("insp_equipment_title"))

        col1, col2 = st.columns(2)

        with col1:
            desks = st.number_input(t("insp_desks"), min_value=0, value=0, key="insp_desks")
            computers = st.number_input(t("insp_computers"), min_value=0, value=0, key="insp_computers")
            phones = st.number_input(t("insp_phones"), min_value=0, value=0, key="insp_phones")
            chairs = st.number_input(t("insp_chairs"), min_value=0, value=0, key="insp_chairs")

        with col2:
            tables = st.number_input(t("insp_tables"), min_value=0, value=0, key="insp_tables")
            whiteboards = st.number_input(t("insp_whiteboards"), min_value=0, value=0, key="insp_whiteboards")
            appliances = st.number_input(t("insp_appliances"), min_value=0, value=0, key="insp_appliances")
            equipment = st.number_input(t("insp_equipment"), min_value=0, value=0, key="insp_equipment")

        st.markdown(t("insp_furniture_moving"))
        move_light = st.number_input(t("insp_move_light"), min_value=0, value=0, key="insp_move_light")
        move_heavy = st.number_input(t("insp_move_heavy"), min_value=0, value=0, key="insp_move_heavy")
        clean_under = st.checkbox(t("insp_clean_under"), key="insp_clean_under")

    # ============================================================
    # TAB 7: SPECIAL CONDITIONS
    # ============================================================
    with tabs[6]:
        st.markdown(t("insp_special_title"))

        col1, col2 = st.columns(2)

        with col1:
            high_dusting = st.checkbox(t("insp_high_dusting"), key="insp_high_dust")
            if high_dusting:
                st.number_input(t("insp_high_dust_sqft"), min_value=0, value=square_feet, key="insp_high_dust_sqft")

            blind_cleaning = st.number_input(t("insp_blinds"), min_value=0, value=0, key="insp_blinds")
            disinfection = st.checkbox(t("insp_disinfection"), key="insp_disinfection")
            odor_control = st.checkbox(t("insp_odor"), key="insp_odor")

        with col2:
            post_construction = st.checkbox(t("insp_post_construction"), key="insp_post_construction")
            emergency = st.checkbox(t("insp_emergency"), key="insp_emergency")
            holiday_values = ["No", "Yes - Holiday", "Yes - Weekend"]
            holiday_clean = st.selectbox(t("insp_holiday"), holiday_values,
                                          format_func=lambda v: t(f"insp_holiday_{v}"), key="insp_holiday")

            st.checkbox(t("insp_supplies_provided"), key="insp_supplies")

            complexity_rating = st.select_slider(
                t("insp_complexity"),
                options=[1,2,3,4,5,6,7,8,9,10],
                value=3,
                key="insp_complexity"
            )
    
    # ============================================================
    # CALCULATE BALLPARK ESTIMATE
    # ============================================================
    
    inspection_data = {
        "property_type": property_type,
        "square_feet": square_feet,
        "num_floors": num_floors,
        "has_elevator": has_elevator,
        "num_buildings": num_buildings,
        "frequency": frequency,
        "access_time": access_time,
        "areas": {
            "reception": reception_area,
            "private_offices": private_offices,
            "open_workstations": open_workstations,
            "conference_rooms": conference_rooms,
            "breakroom": breakroom_kitchen,
            "hallways": hallways,
            "stairwells": stairwells,
            "storage_rooms": storage_rooms,
            "loading_dock": loading_dock,
            "exterior_entry": exterior_entry,
            "trash": trash_recycling
        },
        "windows": {
            "interior": interior_windows,
            "exterior": exterior_windows,
            "high": high_windows,
            "glass_doors": glass_doors,
            "partitions": glass_partitions,
            "mirrors": mirrors,
            "tracks": window_tracks,
            "screens": st.session_state.get("insp_screens", False)
        },
        "restrooms": {
            "toilets": num_toilets,
            "urinals": num_urinals,
            "sinks": num_sinks,
            "mirrors": num_mirrors_rest,
            "showers": num_showers,
            "count": restroom_count,
            "deep_clean": deep_clean,
            "restock": restock_supplies
        },
        "floors": {
            "carpet_sqft": carpet_sqft,
            "tile_sqft": tile_sqft,
            "vinyl_sqft": vinyl_sqft,
            "hardwood_sqft": hardwood_sqft,
            "concrete_sqft": concrete_sqft,
            "condition": floor_condition,
            "carpet_extract": carpet_extract,
            "strip_wax": strip_wax,
            "buff": floor_buff
        },
        "furniture": {
            "desks": desks,
            "computers": computers,
            "phones": phones,
            "chairs": chairs,
            "tables": tables,
            "whiteboards": whiteboards,
            "appliances": appliances,
            "equipment": equipment,
            "move_light": move_light,
            "move_heavy": move_heavy,
            "clean_under": clean_under
        },
        "special": {
            "high_dusting": high_dusting,
            "blinds": blind_cleaning,
            "disinfection": disinfection,
            "odor_control": odor_control,
            "post_construction": post_construction,
            "emergency": emergency,
            "holiday": holiday_clean,
            "supply_provided": st.session_state.get("insp_supplies", False),
            "complexity": complexity_rating
        }
    }
    
    if st.button(t("insp_generate_btn"), type="primary", use_container_width=True, key="insp_generate_btn"):
        st.session_state.insp_payload = inspection_data
        st.session_state.insp_estimate = calculate_inspection_estimate(inspection_data)
        st.session_state.pop("insp_saved", None)

    if st.session_state.get("insp_estimate") and st.session_state.get("insp_payload"):
        estimate = st.session_state.insp_estimate
        saved_payload = st.session_state.insp_payload

        st.markdown("---")
        st.markdown(t("insp_results_title"))
        st.caption(t("insp_results_caption"))

        col1, col2, col3 = st.columns(3)

        with col2:
            st.markdown(f"""
            <div style="text-align: center; padding: 20px; border-radius: 16px; background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white;">
                <h3>{t("insp_ballpark")}</h3>
                <h1 style="font-size: 48px;">${estimate['final_price']:,}</h1>
                <p>{t("insp_medium_high")}</p>
                <small>{t("insp_excludes")}</small>
            </div>
            """, unsafe_allow_html=True)

        with st.expander(t("insp_breakdown"), expanded=True):
            st.markdown(f"""
            **Base Price:** ${estimate['base_price']:,}
            **Adjustments:** +${estimate['adjustments']:,}
            **Total:** ${estimate['final_price']:,}

            ---
            **What's Included:**
            {estimate['included_summary']}

            **Adjustments Applied:**
            {estimate['adjustment_summary']}
            """)

        if estimate['confidence'] >= 80:
            st.success(t("insp_confidence_high", confidence=estimate['confidence']))
        elif estimate['confidence'] >= 60:
            st.warning(t("insp_confidence_med", confidence=estimate['confidence']))
        else:
            st.error(t("insp_confidence_low", confidence=estimate['confidence']))

        if st.button(t("insp_save_btn"), key="save_inspection_btn"):
            company_id = get_current_user_company()
            if not company_id:
                st.error(t("insp_company_error"))
            else:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO inspections (company_id, user_id, client_name, areas_json, inspection_data, status, started_at, completed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    company_id,
                    st.session_state.user['user_id'],
                    "Walk-in Inspection",
                    json.dumps(saved_payload),
                    json.dumps(estimate),
                    "completed",
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                conn.commit()
                conn.close()
                st.session_state.insp_saved = True
                st.success(t("insp_saved"))


def inspections_page():
    pre_inspection_page()

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
    if st.button(t("back")):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown(t("chat_title"))
    with st.form("chat"):
        msg = st.text_input(t("chat_message"))
        if st.form_submit_button(t("chat_send")):
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

    st.markdown("### 🤖 Smart Task Generator")
    st.caption("Generate a customized cleaning task list based on your property details")

    col1, col2 = st.columns(2)

    with col1:
        property_type = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()), key="ai_prop_type")
        square_feet = st.number_input("Total Square Feet", min_value=100, max_value=500000, value=2000, step=100, key="ai_sqft")
        num_rooms = st.number_input("Number of Rooms/Areas", min_value=1, max_value=200, value=5, key="ai_num_rooms")
        has_restrooms = st.checkbox("Has restrooms on site", value=True, key="ai_has_restrooms")
        num_restrooms = 0
        if has_restrooms:
            num_restrooms = st.number_input("Number of Restrooms", min_value=1, max_value=50, value=2, key="ai_num_restrooms")

    with col2:
        complexity = st.select_slider("Complexity Level", options=[1,2,3,4,5,6,7,8,9,10], value=3, key="ai_complexity")
        frequency = st.selectbox("Cleaning Frequency", ["Daily", "Weekly", "Bi-weekly", "Monthly", "One-time"], key="ai_frequency")
        special_considerations = st.multiselect("Special Considerations", [
            "High-traffic area",
            "Pets on premises",
            "Sensitive equipment",
            "Green cleaning required",
            "After-hours only access",
            "Security clearance needed"
        ], key="ai_special_considerations")
        include_estimate = st.checkbox("Include time & labor estimates", value=True, key="ai_include_estimate")

    if st.button("🚀 Generate Smart Task List", type="primary", use_container_width=True, key="ai_generate"):
        tasks = generate_intelligent_tasks(
            property_type,
            int(square_feet),
            int(num_rooms),
            bool(has_restrooms),
            int(num_restrooms) if has_restrooms else 0,
            int(complexity),
            frequency,
            special_considerations,
        )

        labor_estimate = None
        if include_estimate:
            labor_estimate = calculate_labor_estimate(int(square_feet), int(complexity), int(num_restrooms) if has_restrooms else 0)

        st.markdown("---")
        st.markdown("### 📋 Your Custom Task List")

        for i, task in enumerate(tasks, 1):
            left, right = st.columns([4,1])
            with left:
                st.checkbox(f"{i}. {task['name']}", key=f"ai_task_{i}")
                if task.get('tip'):
                    st.caption(f"💡 Tip: {task['tip']}")
            with right:
                if include_estimate:
                    st.metric("Est. Time", f"{task.get('minutes', 0)} min")
            st.markdown("---")

        if include_estimate and labor_estimate:
            st.markdown("### ⏱️ Labor & Time Summary")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.metric("Total Time", f"{labor_estimate['total_hours']:.1f} hours")
            with c2:
                st.metric("Crew Size", f"{labor_estimate['crew_size']} people")
            with c3:
                st.metric("Estimated Labor Cost", f"${labor_estimate['labor_cost']:.2f}")
            with c4:
                st.metric("Productivity Rate", f"{labor_estimate['sqft_per_hour']:.0f} sqft/hr")

        st.markdown("### 🛠️ Recommended Equipment & Supplies")
        equipment = generate_equipment_list(property_type, int(square_feet))
        ec1, ec2 = st.columns(2)
        with ec1:
            st.markdown("**Equipment Needed:**")
            for item in equipment['equipment']:
                st.markdown(f"- {item}")
        with ec2:
            st.markdown("**Supplies Needed:**")
            for item in equipment['supplies']:
                st.markdown(f"- {item}")

        st.markdown("### ✅ Quality Assurance Checklist")
        quality_items = generate_quality_checklist(property_type)
        for j, qi in enumerate(quality_items, 1):
            st.checkbox(qi, key=f"ai_quality_{j}")

        st.markdown("---")
        ex1, ex2, ex3 = st.columns(3)
        with ex1:
            if st.button("📋 Copy to Clipboard", use_container_width=True, key="ai_copy"):
                st.success("Task list copied to clipboard (browser action simulated)")
        with ex2:
            if st.button("📧 Email to Team", use_container_width=True, key="ai_email_team"):
                st.info("Email feature is available; it would send this list to assigned workers")
        with ex3:
            if st.button("💾 Save as Template", use_container_width=True, key="ai_save_template"):
                st.success("Template saved for future use")


def generate_intelligent_tasks(property_type, sqft, num_rooms, has_restrooms, num_restrooms, complexity, frequency, special_considerations):
    """Generate intelligent task list based on property characteristics"""
    base_tasks = [
        {"name": "Empty all trash and recycling bins", "minutes": 15, "tip": "Replace liners in all bins"},
        {"name": "Dust all horizontal surfaces", "minutes": 20, "tip": "Work top to bottom"},
        {"name": "Vacuum all carpeted areas", "minutes": max(5, int(sqft / 200)), "tip": "Use HEPA filter for allergies"},
        {"name": "Mop all hard floor surfaces", "minutes": max(5, int(sqft / 250)), "tip": "Use color-coded mop heads"},
        {"name": "Clean and sanitize all door handles and light switches", "minutes": 10, "tip": "High-touch areas need daily attention"},
        {"name": "Final visual inspection", "minutes": 10, "tip": "Walk through all areas"},
    ]

    # NOTE: keys must exactly match PROPERTY_TYPES (the dict the selectbox in
    # ai_tasks_page() is built from) -- it uses emoji-prefixed labels like
    # "🍽️ Restaurant", not plain "Restaurant". Previously these keys didn't
    # match anything except "Warehouse", so the specialized lists below
    # silently never triggered for any other property type.
    property_tasks = {
        "🍽️ Restaurant": [
            {"name": "Clean kitchen hood and exhaust", "minutes": 30, "tip": "Focus on grease buildup"},
            {"name": "Degrease all cooking surfaces", "minutes": 25, "tip": "Use food-safe degreaser"},
            {"name": "Sanitize food preparation areas", "minutes": 15, "tip": "Use NSF-certified sanitizer"},
            {"name": "Clean dining tables and chairs", "minutes": 20, "tip": "Wipe down all surfaces"},
            {"name": "Clean and sanitize menus", "minutes": 10, "tip": "Use food-safe wipes"}
        ],
        "🏥 Medical / Dental": [
            {"name": "Disinfect all exam room surfaces", "minutes": 30, "tip": "Use hospital-grade disinfectant"},
            {"name": "Clean medical equipment (exterior)", "minutes": 20, "tip": "Follow equipment manufacturer guidelines"},
            {"name": "Sanitize waiting area chairs and tables", "minutes": 15, "tip": "Focus on armrests"},
            {"name": "Biohazard waste handling", "minutes": 15, "tip": "Use proper PPE and red bags"},
            {"name": "Restock medical supplies (paper, gloves)", "minutes": 10, "tip": "Check inventory levels"}
        ],
        "🏫 School / Daycare": [
            {"name": "Sanitize all toys and play areas", "minutes": 25, "tip": "Use child-safe disinfectant"},
            {"name": "Clean cubbies and storage areas", "minutes": 20, "tip": "Remove all items and wipe down"},
            {"name": "Disinfect changing tables", "minutes": 10, "tip": "Use appropriate sanitizer"},
            {"name": "Clean cafeteria tables", "minutes": 15, "tip": "Focus on high-touch areas"},
            {"name": "Sanitize door handles at child height", "minutes": 10, "tip": "Children touch lower handles"}
        ],
        "Warehouse": [
            {"name": "Sweep all aisles and open areas", "minutes": max(5, int(sqft / 1000)), "tip": "Use industrial sweeper for large areas"},
            {"name": "Clean loading dock area", "minutes": 30, "tip": "Remove debris and sweep"},
            {"name": "Dust racking and shelving", "minutes": 40, "tip": "Use extension duster for high racks"},
            {"name": "Empty large industrial trash bins", "minutes": 20, "tip": "Check dumpster placement"},
            {"name": "Clean breakroom and office areas", "minutes": 20, "tip": "Focus on employee areas"}
        ],
        "🏋️ Gym / Fitness": [
            {"name": "Sanitize all exercise equipment", "minutes": 30, "tip": "Use equipment-safe disinfectant"},
            {"name": "Clean locker rooms and showers", "minutes": 35, "tip": "Check for mold in corners"},
            {"name": "Mop studio and class floors", "minutes": 20, "tip": "Use appropriate floor cleaner"},
            {"name": "Clean all mirrors (gym and lockers)", "minutes": 15, "tip": "Streak-free glass cleaner"},
            {"name": "Restock towels and amenities", "minutes": 15, "tip": "Check supply levels"}
        ]
    }

    tasks = base_tasks.copy()
    if property_type in property_tasks:
        tasks.extend(property_tasks[property_type])

    if has_restrooms:
        for i in range(num_restrooms):
            tasks.append({"name": f"Clean restroom #{i+1} (toilets, sinks, mirrors, floors)", "minutes": 25, "tip": "Use restroom-specific color-coded tools"})

    if complexity >= 7:
        tasks.append({"name": "DEEP CLEAN: Baseboards and corners", "minutes": 30, "tip": "Focus on neglected areas"})
        tasks.append({"name": "DEEP CLEAN: Window tracks and blinds", "minutes": 25, "tip": "Detailed attention"})
    if complexity >= 9:
        tasks.append({"name": "DEEP CLEAN: Behind and under furniture", "minutes": 40, "tip": "Move light furniture"})

    if frequency == "Daily":
        for task in tasks:
            task['minutes'] = max(1, int(task['minutes'] * 0.7))
    elif frequency == "Monthly":
        for task in tasks:
            task['minutes'] = int(task['minutes'] * 1.5)

    if "Pets on premises" in special_considerations:
        tasks.append({"name": "Vacuum pet hair from all surfaces", "minutes": 20, "tip": "Use rubber brush attachment"})
    if "Green cleaning required" in special_considerations:
        tasks.append({"name": "Use eco-friendly certified products only", "minutes": 5, "tip": "Verify product certifications"})
    if "After-hours only access" in special_considerations:
        tasks.append({"name": "Security check-in/out procedures", "minutes": 10, "tip": "Log entry and exit times"})

    return tasks


def calculate_labor_estimate(sqft, complexity, num_restrooms):
    """Calculate labor hours and crew size"""
    base_hours = sqft / 2000.0
    complexity_factor = 1 + ((complexity - 3) * 0.1)
    adjusted_hours = base_hours * complexity_factor
    restroom_hours = num_restrooms * 0.25
    total_hours = adjusted_hours + restroom_hours

    if total_hours <= 2:
        crew_size = 1
    elif total_hours <= 4:
        crew_size = 2
    elif total_hours <= 8:
        crew_size = 3
    else:
        crew_size = 4

    return {
        "total_hours": round(total_hours, 1),
        "crew_size": crew_size,
        "labor_cost": round(total_hours * 25, 2),
        "sqft_per_hour": round(sqft / total_hours, 0) if total_hours > 0 else 0,
    }


def generate_equipment_list(property_type, sqft):
    base_equipment = [
        "Vacuum cleaner (HEPA filter recommended)",
        "Microfiber mop with bucket and wringer",
        "Microfiber cloths (color-coded set)",
        "Extension duster for high areas",
        "Step ladder or small platform",
    ]

    base_supplies = [
        "All-purpose cleaner (2 bottles)",
        "Glass cleaner (1 bottle)",
        "Disinfectant spray (3 bottles)",
        "Trash bags (various sizes)",
        "Paper towels (4 rolls)",
    ]

    if property_type == "🍽️ Restaurant":
        base_equipment.extend(["Degreaser sprayer", "Commercial kitchen cleaner", "Floor scrubber for kitchen"])
        base_supplies.extend(["Food-safe sanitizer", "Grease remover concentrate", "Stainless steel polish"])

    if property_type == "🏥 Medical / Dental":
        base_equipment.extend(["Hospital-grade disinfectant sprayer", "PPE kit (gloves, mask, gown)"])
        base_supplies.extend(["Medical-grade disinfectant wipes", "Biohazard waste bags", "Hand sanitizer refills"])

    if property_type == "Warehouse":
        base_equipment.extend(["Industrial floor sweeper", "High-reach duster (15+ feet)", "Pallet jack for moving items"])
        base_supplies.extend(["Industrial trash bags (55+ gallon)", "Shop towels (heavy-duty)", "Floor sweep compound"])

    if sqft > 10000:
        base_equipment.append("Ride-on floor scrubber (recommended for efficiency)")

    return {"equipment": base_equipment, "supplies": base_supplies}


def generate_quality_checklist(property_type):
    base_checklist = [
        "All floors are clean and dry",
        "No visible dust on any surface",
        "All trash cans emptied and relined",
        "Restrooms are sanitized and fully stocked",
        "All high-touch areas disinfected",
        "Windows and mirrors are streak-free",
        "Supplies are organized in janitor closet",
        "No unpleasant odors remain",
    ]

    property_specific = {
        "🍽️ Restaurant": [
            "Kitchen hood and exhaust clean",
            "Food prep surfaces sanitized",
            "No grease buildup on equipment",
            "Dining area tables and chairs clean",
        ],
        "🏥 Medical / Dental": [
            "Exam room surfaces disinfected",
            "Biohazard waste properly disposed",
            "Waiting area sanitized",
            "Medical equipment exteriors clean",
        ],
        "🏫 School / Daycare": [
            "Toys and play areas sanitized",
            "Child-height surfaces disinfected",
            "Cubbies and storage clean",
            "Cafeteria tables sanitized",
        ],
    }

    checklist = base_checklist.copy()
    if property_type in property_specific:
        checklist.extend(property_specific[property_type])

    return checklist

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
    return restore_personal_backup_data(backup)


PERSONAL_BACKUP_TABLES = [
    "clients", "estimates", "quick_jobs", "monthly_expenses", "scheduled_jobs",
    "inspections", "supplies", "team_messages", "support_tickets",
]


def restore_personal_backup_data(backup_data):
    """Restore a user-scoped backup (create_backup format).

    Deliberately ignores any user_id/company_id/table names claimed inside
    the uploaded file -- always restores into the *current session's* own
    company and accessible-user scope. Trusting file-supplied identifiers
    here would let any logged-in user (any role) upload a crafted backup
    naming a different company_id/user_id and overwrite another tenant's
    data.
    """
    user_id = st.session_state.user['user_id']
    role = st.session_state.user['role']
    company_id = get_current_user_company()
    if not company_id:
        return False
    accessible = get_accessible_user_ids(user_id, role, company_id)

    data = backup_data.get("data", {})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for table, rows in data.items():
        if table not in PERSONAL_BACKUP_TABLES:
            continue
        try:
            placeholders = ','.join(['?' for _ in accessible])
            c.execute(f"DELETE FROM {table} WHERE company_id = ? AND user_id IN ({placeholders})", [company_id] + accessible)
            for row in rows or []:
                row = dict(row)
                row['company_id'] = company_id
                if row.get('user_id') not in accessible:
                    row['user_id'] = user_id
                columns = [col for col in row.keys() if col != 'id']
                col_placeholders = ','.join(['?' for _ in columns])
                values = [row[col] for col in columns]
                c.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({col_placeholders})", values)
        except Exception as e:
            print(f"Personal restore error on {table}: {e}")
    conn.commit()
    conn.close()
    return True


def restore_full_system_backup_data(backup_data):
    """Restore a full system backup (create_full_system_backup format)."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = OFF")
    c = conn.cursor()
    for table, rows in backup_data.get('data', {}).items():
        try:
            c.execute(f"DELETE FROM {table}")
            if rows:
                columns = list(rows[0].keys())
                placeholders = ','.join(['?' for _ in columns])
                for row in rows:
                    values = [row[col] for col in columns]
                    c.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({placeholders})", values)
        except Exception as e:
            print(f"Full restore error on {table}: {e}")
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")
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

def upload_backup():
    """Upload and restore a backup file"""
    st.markdown("### 📤 Upload Backup to Restore")
    uploaded_file = st.file_uploader("Choose backup JSON file", type=['json'], key="upload_backup_file")
    
    if uploaded_file is not None:
        try:
            backup_data = json.load(uploaded_file)
            
            is_personal = (
                backup_data.get('data')
                and backup_data.get('user_id') is not None
                and backup_data.get('company_id') is not None
            )
            is_full_system = backup_data.get('data') and not is_personal
            
            if not is_personal and not is_full_system:
                st.error("Invalid backup file format. Expected a personal or full system backup JSON.")
                return
            
            if is_personal:
                st.warning(
                    "⚠️ This will replace your personal data (clients, estimates, jobs, etc.) "
                    "for the company in this backup. Other users are not affected."
                )
            else:
                role = st.session_state.user.get('role')
                if role != 'super_admin':
                    st.error("Only a super admin can restore full system backups.")
                    return
                st.warning(
                    "⚠️ This will REPLACE ALL data in the database with this backup. "
                    "This cannot be undone!"
                )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Confirm Restore", use_container_width=True, key="upload_confirm_restore"):
                    if is_personal:
                        ok = restore_personal_backup_data(backup_data)
                    else:
                        ok = restore_full_system_backup_data(backup_data)
                    if ok:
                        st.success("✅ Backup restored successfully! Refresh the page.")
                        st.rerun()
                    else:
                        st.error("Restore failed. Check the console for details.")
            with col2:
                if st.button("❌ Cancel", use_container_width=True, key="upload_cancel_restore"):
                    st.rerun()
        except Exception as e:
            st.error(f"Error reading backup file: {e}")

def list_all_backups():
    """List all available backups across all users"""
    ensure_backup_dir()
    all_backups = []
    for f in os.listdir(BACKUP_DIR):
        if f.endswith(".json"):
            path = os.path.join(BACKUP_DIR, f)
            all_backups.append({
                "file": f, 
                "path": path, 
                "date": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S"), 
                "size": f"{os.path.getsize(path)/1024:.1f} KB"
            })
    return sorted(all_backups, key=lambda x: x["date"], reverse=True)

def backup_page():
    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("Please log in to use backup and restore.")
        st.session_state.page = "login"
        st.rerun()
        return
    
    st.markdown("### 💾 Backup & Restore")
    
    tab1, tab2, tab3 = st.tabs(["📦 My Backups", "📤 Upload & Restore", "🏢 System Backups"])
    
    with tab1:
        if st.session_state.get("restore_file"):
            path = os.path.join(BACKUP_DIR, st.session_state.restore_file)
            if restore_from_backup(path):
                st.success("✅ Restored successfully!")
            del st.session_state.restore_file
        
        st.markdown("#### Your Personal Backups")
        if st.button("Create New Backup", use_container_width=True, key="create_personal_backup"):
            st.session_state.last_personal_backup_file = create_backup()
        
        if st.session_state.get("last_personal_backup_file") and os.path.exists(st.session_state.last_personal_backup_file):
            with open(st.session_state.last_personal_backup_file, 'rb') as fp:
                st.download_button(
                    "Download Latest Backup",
                    fp,
                    os.path.basename(st.session_state.last_personal_backup_file),
                    "application/json",
                    key="download_personal_backup",
                )
        
        backups = get_backup_list()
        if backups:
            st.dataframe(backups)
            sel = st.selectbox("Select backup to restore", [b['file'] for b in backups])
            if st.button("Restore Selected", use_container_width=True):
                st.session_state.restore_file = sel
                st.rerun()
        else:
            st.info("No backups found. Create your first backup above.")
    
    with tab2:
        upload_backup()
    
    with tab3:
        st.markdown("#### Full System Backups (All Companies)")
        role = st.session_state.user.get('role')
        if role not in ('super_admin', 'admin'):
            st.info("Only administrators can create full system backups.")
        elif st.button("Create Full System Backup", use_container_width=True, key="create_system_backup"):
            st.session_state.last_system_backup_file = create_full_system_backup()
        
        if st.session_state.get("last_system_backup_file") and os.path.exists(st.session_state.last_system_backup_file):
            with open(st.session_state.last_system_backup_file, 'rb') as f:
                st.download_button(
                    "Download System Backup",
                    f,
                    os.path.basename(st.session_state.last_system_backup_file),
                    "application/json",
                    key="download_system_backup",
                )
        
        all_backups = list_all_backups()
        if all_backups:
            st.dataframe(all_backups[:20])
        else:
            st.info("No system backups found.")

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
    if st.button(t("back")):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown(t("support_title"))
    issue_type_map = {"Bug": "support_bug", "Feature request": "support_feature",
                       "Data issue": "support_data_issue", "Other": "support_other"}
    with st.form("ticket"):
        issue = st.selectbox(t("support_type"), list(issue_type_map.keys()),
                              format_func=lambda v: t(issue_type_map[v]))
        desc = st.text_area(t("support_description"))
        steps = st.text_area(t("support_steps"))
        if st.form_submit_button(t("support_submit")):
            if desc:
                tid = create_support_ticket(issue, desc, steps)
                st.success(t("support_submitted", ticket_id=tid))
                st.rerun()
    tickets = get_user_tickets()
    if not tickets.empty:
        st.dataframe(tickets)

def settings_page():
    if st.session_state.user.get('role') not in ['super_admin', 'admin']:
        st.error("Access denied. Business settings (including SMTP credentials and financials) are admin-only.")
        return

    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown("### ⚙️ Business Settings")
    company_id = get_current_user_company()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    ensure_business_profile_schema(company_id)
    c.execute("PRAGMA table_info(business_profile)")
    existing_columns = [col[1] for col in c.fetchall()]
    
    select_columns = [
        "business_name", "phone", "email", "hourly_wage", "min_job_fee", "home_city",
        "monthly_rent", "monthly_insurance", "monthly_vehicles", "monthly_marketing",
        "monthly_software", "monthly_admin_salary", "desired_profit_margin",
        "smtp_email", "smtp_password"
    ]
    
    if 'smtp_server' in existing_columns:
        select_columns.append("smtp_server")
    else:
        select_columns.append("'' as smtp_server")
    
    if 'smtp_port' in existing_columns:
        select_columns.append("smtp_port")
    else:
        select_columns.append("587 as smtp_port")
    
    query = f"SELECT {', '.join(select_columns)} FROM business_profile WHERE company_id = ?"
    
    try:
        c.execute(query, (company_id,))
        row = c.fetchone()
    except Exception as e:
        st.error(f"Error loading settings: {e}")
        row = None
    finally:
        conn.close()
    
    if row:
        row_dict = {}
        for i, col in enumerate(select_columns):
            col_name = col.split(' as ')[0] if ' as ' in col else col
            row_dict[col_name] = row[i]

        # The stored value is encrypted; decrypt it for display so the form
        # doesn't re-encrypt an already-encrypted blob when saved unchanged.
        if row_dict.get('smtp_password'):
            try:
                from encryption_manager import encryption
                row_dict['smtp_password'] = encryption.decrypt(row_dict['smtp_password'])
            except Exception:
                pass

        with st.form("settings"):
            bname = st.text_input("Business Name", row_dict.get('business_name', ''))
            phone = st.text_input("Phone", row_dict.get('phone', ''))
            email = st.text_input("Email", row_dict.get('email', ''))
            wage = st.number_input("Hourly Wage", value=float(row_dict.get('hourly_wage', 15.0)))
            min_fee = st.number_input("Min Job Fee", value=float(row_dict.get('min_job_fee', 150)))
            
            current_city = row_dict.get('home_city', 'Orlando')
            home_index = FLORIDA_CITIES.index(current_city) if current_city in FLORIDA_CITIES else 0
            home = st.selectbox("Home City", FLORIDA_CITIES, index=home_index)
            
            smtp_email = st.text_input("SMTP Email", value=row_dict.get('smtp_email', '') if row_dict.get('smtp_email') else "")
            smtp_password = st.text_input("SMTP Password", type="password", value=row_dict.get('smtp_password', '') if row_dict.get('smtp_password') else "")
            smtp_server = st.text_input("SMTP Server", value=row_dict.get('smtp_server', 'smtp.gmail.com'))
            smtp_port = st.number_input("SMTP Port", value=int(row_dict.get('smtp_port', 587)))

            if not smtp_email or not smtp_password:
                st.warning("SMTP is not not fully configured. Estimate emails will not send until both SMTP Email and SMTP Password are entered.")
            else:
                st.success("SMTP settings appear configured. Save and send a test email to verify delivery.")

            with st.expander("SMTP Setup Help"):
                st.markdown("""
                - Gmail: `smtp.gmail.com`, port `587` (STARTTLS) or `465` (SSL). Use an App Password, not your Google login password.
                - Outlook/Office 365: `smtp.office365.com`, port `587`.
                - Yahoo: `smtp.mail.yahoo.com`, port `465`.
                - Enter the SMTP provider credentials you normally use for email clients.
                - Save the settings and then click **Send Test Email** to verify that the account is working.
                - For Gmail, follow these steps:
                  1. Enable 2-Step Verification
                  2. Create an App Password at https://myaccount.google.com/apppasswords
                  3. Paste the 16-character App Password into SMTP Password
                """)

            st.markdown("**Current SMTP configuration loaded from your account:**")
            st.write(f"- From: {smtp_email or 'Not configured'}")
            st.write(f"- Server: {smtp_server or 'smtp.gmail.com'}")
            st.write(f"- Port: {smtp_port}")
            if smtp_password:
                st.write("- Password: configured")
            else:
                st.write("- Password: not configured")

            st.markdown("#### 📧 Test Your SMTP Configuration")
            test_recipient = st.text_input("Enter email address to send test", value=row_dict.get('smtp_email', '') if row_dict.get('smtp_email') else "", key="test_email_input")
            if st.form_submit_button("Send Test Email", key="send_test_email"):
                to_addr = test_recipient.strip()
                if not to_addr:
                    st.error("Please enter a valid recipient email to send a test message.")
                else:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("PRAGMA table_info(business_profile)")
                    existing_columns = [col[1] for col in c.fetchall()]
                    if 'smtp_server' not in existing_columns:
                        c.execute("ALTER TABLE business_profile ADD COLUMN smtp_server TEXT")
                    if 'smtp_port' not in existing_columns:
                        c.execute("ALTER TABLE business_profile ADD COLUMN smtp_port INTEGER DEFAULT 587")
                    # Encrypt SMTP password before storing
                    encrypted_password = ""
                    if smtp_password:
                        try:
                            from encryption_manager import encryption
                            encrypted_password = encryption.encrypt(smtp_password)
                        except Exception as e:
                            print(f"SMTP password encryption failed, not storing: {e}")
                            st.warning("Could not securely save the SMTP password. Please re-enter it later from Settings.")
                    c.execute("UPDATE business_profile SET smtp_email=?, smtp_password=?, smtp_server=?, smtp_port=? WHERE company_id=?",
                              (smtp_email, encrypted_password, smtp_server, smtp_port, company_id))
                    conn.commit()
                    conn.close()

                    with st.spinner("Sending test email using configured SMTP settings..."):
                        success, err = test_smtp_connection(company_id, to_addr)
                        if success:
                            st.success(f"Test email sent to {to_addr}. Check the inbox (or spam).")
                            st.balloons()
                        else:
                            st.error(f"Failed to send test email: {err}")
                            st.info("If you’re using Gmail, make sure you are using an App Password. See SMTP Setup Help above.")

            st.markdown("---")
            st.markdown("### 💰 Business Expenses (For Internal Pricing)")
            st.caption("These help calculate what you need to charge to stay profitable")
            
            col1, col2 = st.columns(2)
            with col1:
                monthly_rent = st.number_input("Monthly Rent/Lease", min_value=0, value=int(row_dict.get('monthly_rent', 0)), step=100)
                monthly_insurance = st.number_input("Monthly Insurance", min_value=0, value=int(row_dict.get('monthly_insurance', 0)), step=100)
                monthly_vehicles = st.number_input("Monthly Vehicle Expenses", min_value=0, value=int(row_dict.get('monthly_vehicles', 0)), step=100)
            with col2:
                monthly_marketing = st.number_input("Monthly Marketing", min_value=0, value=int(row_dict.get('monthly_marketing', 0)), step=50)
                monthly_software = st.number_input("Monthly Software/Subscriptions", min_value=0, value=int(row_dict.get('monthly_software', 0)), step=50)
                monthly_admin_salary = st.number_input("Monthly Admin Salary", min_value=0, value=int(row_dict.get('monthly_admin_salary', 0)), step=500)
            
            # Streamlit's slider `format` just printf-formats the raw value -- it
            # doesn't multiply by 100. With min/max as fractions (0.05-0.50), this
            # rendered as "0%" for every position. Slide in whole percent instead
            # and convert to the fraction the rest of the app expects.
            desired_profit_margin_pct = st.slider("Desired Profit Margin", min_value=5, max_value=50,
                                                   value=int(round(float(row_dict.get('desired_profit_margin', 0.20)) * 100)),
                                                   step=5, format="%d%%")
            desired_profit_margin = desired_profit_margin_pct / 100.0
            
            if st.form_submit_button("Save"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                
                c.execute("PRAGMA table_info(business_profile)")
                current_columns = [col[1] for col in c.fetchall()]
                
                if 'smtp_server' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN smtp_server TEXT")
                        print("Added smtp_server column")
                    except:
                        pass
                
                if 'smtp_port' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN smtp_port INTEGER DEFAULT 587")
                        print("Added smtp_port column")
                    except:
                        pass
                if 'monthly_rent' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN monthly_rent REAL DEFAULT 0")
                    except:
                        pass
                if 'monthly_insurance' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN monthly_insurance REAL DEFAULT 0")
                    except:
                        pass
                if 'monthly_vehicles' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN monthly_vehicles REAL DEFAULT 0")
                    except:
                        pass
                if 'monthly_marketing' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN monthly_marketing REAL DEFAULT 0")
                    except:
                        pass
                if 'monthly_software' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN monthly_software REAL DEFAULT 0")
                    except:
                        pass
                if 'monthly_admin_salary' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN monthly_admin_salary REAL DEFAULT 0")
                    except:
                        pass
                if 'desired_profit_margin' not in current_columns:
                    try:
                        c.execute("ALTER TABLE business_profile ADD COLUMN desired_profit_margin REAL DEFAULT 0.20")
                    except:
                        pass
                
                # Encrypt SMTP password before storing
                encrypted_password = ""
                if smtp_password:
                    try:
                        from encryption_manager import encryption
                        encrypted_password = encryption.encrypt(smtp_password)
                    except Exception as e:
                        print(f"SMTP password encryption failed, not storing: {e}")
                        st.warning("Could not securely save the SMTP password. Please re-enter it later from Settings.")

                c.execute("""
                    UPDATE business_profile 
                    SET business_name=?, phone=?, email=?, hourly_wage=?, min_job_fee=?, home_city=?, 
                        smtp_email=?, smtp_password=?, smtp_server=?, smtp_port=?,
                        monthly_rent=?, monthly_insurance=?, monthly_vehicles=?, monthly_marketing=?,
                        monthly_software=?, monthly_admin_salary=?, desired_profit_margin=?
                    WHERE company_id=?
                """, (bname, phone, email, wage, min_fee, home, smtp_email, encrypted_password, smtp_server, smtp_port,
                      monthly_rent, monthly_insurance, monthly_vehicles, monthly_marketing, monthly_software, monthly_admin_salary, desired_profit_margin, company_id))
                
                conn.commit()
                conn.close()
                st.success("Settings saved successfully!")
                st.rerun()
    else:
        st.warning("Business profile not found. Please contact support.")


def internal_pricing_dashboard():
    """Internal dashboard showing all three calculators"""
    if st.session_state.user.get('role') not in ['super_admin', 'admin']:
        st.error("Access denied")
        return

    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    st.markdown("### 📊 Internal Pricing Intelligence Dashboard")
    st.caption("Confidential - Internal use only. View all three pricing calculators.")
    
    company_id = get_current_user_company()
    
    # Demo inputs for testing the calculators
    st.markdown("#### Test Calculator Inputs")
    col1, col2 = st.columns(2)
    with col1:
        test_city = st.selectbox("Test City", FLORIDA_CITIES, key="test_city")
        test_prop = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()), key="test_prop")
        test_sqft = st.number_input("Square Feet", min_value=500, value=5000, key="test_sqft")
    with col2:
        test_complexity = st.slider("Complexity (1-10)", 1, 10, 3, key="test_complexity")
        test_travel = st.number_input("Travel Miles", min_value=0, value=10, key="test_travel")
        labor_hours = (test_sqft / 500) * (0.6 + test_complexity/10)
    
    if st.button("Run All Calculators", key="run_calculators"):
        # Run all three internal calculators
        cost_result = calculator_cost_based(test_city, test_prop, test_sqft, 2, 1, "Weekly", test_complexity, test_travel)
        market_result = calculator_market_based(test_city, test_prop, test_sqft, 2, 1, None)
        expense_result = calculator_expense_based(company_id, labor_hours)
        
        # Display results in three columns
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("#### 🏢 Cost-Based Calculator")
            st.markdown(f"**Recommended Price:** ${cost_result['total']}")
            with st.expander("Breakdown"):
                for k, v in cost_result['breakdown'].items():
                    st.markdown(f"- {k.replace('_', ' ').title()}: {v}")
        
        with col2:
            st.markdown("#### 📊 Market-Based Calculator")
            st.markdown(f"**Min:** ${market_result['min']} | **Avg:** ${market_result['avg']} | **Max:** ${market_result['max']}")
            st.markdown(f"**Zone:** {market_result['zone']} (Confidence: {market_result['confidence']})")
        
        with col3:
            st.markdown("#### 💰 Expense-Based Calculator")
            if "error" in expense_result:
                st.warning(expense_result['error'])
            else:
                st.markdown(f"**Min Viable:** ${expense_result['min_viable']}")
                st.markdown(f"**Healthy Price:** ${expense_result['healthy_price']}")
                st.markdown(f"**Business Health:** {expense_result['business_health']['status']}")
                if expense_result['business_health']['recommendation'] != "On track":
                    st.warning(expense_result['business_health']['recommendation'])
        
        # Combined result
        st.markdown("---")
        st.markdown("#### 🎯 Combined Recommendation")
        
        weighted = (market_result['avg'] * 0.40) + (cost_result['total'] * 0.35) + (expense_result['healthy_price'] * 0.25)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Low", f"${math.ceil(weighted * 0.85)}")
        col2.metric("Sweet Spot", f"${math.ceil(weighted)}", delta="RECOMMENDED")
        col3.metric("Medium", f"${math.ceil(weighted * 1.10)}")
        col4.metric("High", f"${math.ceil(weighted * 1.25)}")
    
    # Business expense summary
    st.markdown("---")
    st.markdown("#### 💼 Business Expense Summary")
    
    ensure_business_profile_schema(company_id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT monthly_rent, monthly_insurance, monthly_vehicles, monthly_marketing, 
               monthly_software, monthly_admin_salary, desired_profit_margin, hourly_wage
        FROM business_profile WHERE company_id = ?
    """, (company_id,))
    expenses = c.fetchone()
    conn.close()
    
    if expenses:
        total_monthly = sum(expenses[:6])
        st.metric("Total Monthly Fixed Costs", f"${total_monthly:,.2f}")
        st.metric("Desired Profit Margin", f"{expenses[6]*100:.0f}%")
        st.metric("Hourly Wage Base", f"${expenses[7]:.2f}/hr")
        
        # Annual projection
        annual_cost = total_monthly * 12
        annual_profit_target = annual_cost * expenses[6]
        st.info(f"**Annual Revenue Target:** ${(annual_cost + annual_profit_target):,.2f} to achieve {expenses[6]*100:.0f}% profit")
    else:
        st.warning("No expense data configured. Go to Settings > Business Expenses to add.")

def my_performance_page():
    if st.button(t("back")):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown(t("perf_title"))
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
    col1.metric(t("perf_jobs_completed"), jobs)
    col2.metric(t("perf_total_profit"), f"${profit:,.2f}")
    col3.metric(t("perf_total_hours"), f"{hours:.1f}")
    col4.metric(t("perf_years_service"), f"{years:.1f}")
    if years >= 1.0:
        st.success(t("perf_anniversary", years=int(years)))
    badges = get_worker_badges(uid)
    if not badges.empty:
        st.subheader(t("perf_badges"))
        st.dataframe(badges)
    conn = sqlite3.connect(DB_PATH)
    company_id = get_current_user_company()
    df = pd.read_sql_query("SELECT strftime('%Y-%m', job_date) as month, SUM(profit) as profit FROM quick_jobs WHERE user_id = ? AND company_id = ? GROUP BY month ORDER BY month", conn, params=(uid, company_id))
    conn.close()
    if not df.empty:
        fig = px.line(df, x='month', y='profit', title=t("perf_monthly_profit_chart"))
        st.plotly_chart(fig, use_container_width=True)

def certifications_page():
    if st.button(t("back")):
        st.session_state.page = "dashboard"
        st.rerun()
    st.markdown(t("cert_title"))
    user_role = st.session_state.user['role']
    uid = st.session_state.user['user_id']
    if user_role == 'worker':
        certs = get_certifications_for_worker(uid)
        if certs.empty:
            st.info(t("cert_none_yet"))
        else:
            st.dataframe(certs)
        with st.expander(t("cert_add_new")):
            with st.form("add_cert"):
                name = st.text_input(t("cert_name"))
                issuer = st.text_input(t("cert_issuer"))
                date_earned = st.date_input(t("cert_date_earned"))
                expiration = st.date_input(t("cert_expiration"), value=None)
                file = st.file_uploader(t("cert_upload"), type=['pdf','png','jpg'])
                notes = st.text_area(t("cert_notes"))
                if st.form_submit_button(t("cert_submit")):
                    if name:
                        add_certification(uid, name, issuer, date_earned.isoformat(), expiration.isoformat() if expiration else None, file, notes)
                        st.success(t("cert_added"))
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
            st.info(t("cert_none_from_team"))
        else:
            st.dataframe(df)
            cert_id = st.number_input(t("cert_verify_id"), min_value=1, step=1)
            if st.button(t("cert_verify_btn")):
                verify_certification(cert_id, uid)
                st.success(t("cert_verified"))
                st.rerun()

def client_login_page():
    st.markdown("### 👤 Client Portal Login")
    with st.form("client_login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            if not email or not password:
                st.error("Please enter your email and password")
            else:
                success, result = authenticate_client(email, password)
                if success:
                    st.session_state.client_logged_in = True
                    st.session_state.client_id = result["client_id"]
                    st.session_state.client_name = result["business_name"]
                    st.session_state.client_company_id = result["company_id"]
                    st.session_state.client_email = result["email"]
                    st.session_state.page = "client_dashboard"
                    st.rerun()
                elif result == "PORTAL_NOT_SET_UP":
                    st.warning("Portal access has not been set up for this email yet. Use the option below to set a password.")
                else:
                    st.error(result)

    with st.expander("🔑 Set up or reset your portal password"):
        setup_email = st.text_input("Email Address", key="client_portal_setup_email")
        if st.button("Send Setup Link", key="client_portal_send_setup"):
            if not setup_email:
                st.error("Please enter your email address")
            else:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT id, business_name, company_id FROM clients WHERE email = ?", (normalize_email(setup_email),))
                matching_clients = c.fetchall()
                conn.close()
                # Always show the same message whether or not the email matches, so this
                # form can't be used to enumerate which emails exist as clients.
                # The same email can belong to clients of different companies, so send a
                # separate, correctly-labeled setup link for each match rather than only
                # the first one found.
                for client_id, business_name, company_id in matching_clients:
                    setup_token = generate_client_portal_token(client_id)
                    base_url = os.getenv('APP_BASE_URL', 'https://profitclean-c4s6mqoafikfejkdfuwgvx.streamlit.app')
                    setup_link = f"{base_url}?page=client_set_password&token={setup_token}"
                    send_client_portal_setup_email(company_id, setup_email, business_name, setup_link)
                st.success("If an account exists with this email, a setup link has been sent.")

    if st.button("← Back"):
        st.session_state.page = "dashboard"
        st.rerun()


def client_set_password_page():
    st.markdown("### 🔑 Set Your Client Portal Password")
    params = get_query_params_safely()
    token = parse_query_param(params, "token")

    if not token:
        st.error("❌ Invalid or missing setup link")
        if st.button("← Back to Login"):
            st.session_state.page = "client_login"
            st.rerun()
        return

    client_id, error = validate_client_portal_token(token)
    if error:
        st.error(f"❌ {error}")
        if st.button("← Back to Login"):
            st.session_state.page = "client_login"
            st.rerun()
        return

    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")
    if st.button("Set Password"):
        if new_password != confirm_password:
            st.error("Passwords do not match")
        else:
            success, msg = set_client_password(client_id, new_password, token)
            if success:
                st.success("✅ Password set! You can now log in.")
                if st.button("Go to Login"):
                    st.session_state.page = "client_login"
                    st.rerun()
            else:
                st.error(msg)

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
                    
                    add_estimate_history_entry(row['id'], "sent", "approved", None, "Client approved via portal")
                    
                    company_id = st.session_state.client_company_id
                    send_estimate_approved_email(company_id, row['id'], 
                                                 st.session_state.get('client_email', ''),
                                                 st.session_state.client_name, 
                                                 row['estimated_price'])
                    
                    conn.commit()
                    conn.close()
                    st.success("Estimate approved! We'll contact you to schedule the service.")
                    st.rerun()
    
    st.markdown("### 📅 Upcoming Services")
    conn = sqlite3.connect(DB_PATH)
    jobs_df = pd.read_sql_query("SELECT scheduled_date, scheduled_time, status FROM scheduled_jobs WHERE client_id = ? AND company_id = ? AND scheduled_date >= date('now') ORDER BY scheduled_date", 
                                conn, params=(st.session_state.client_id, st.session_state.client_company_id))
    conn.close()
    if not jobs_df.empty:
        st.dataframe(jobs_df)
    else:
        st.info("No upcoming services scheduled")

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


# ============================================================
# ENHANCED ADMIN COMPANIES PAGE
# ============================================================

@require_role(['super_admin', 'support_staff'])
def admin_companies_page():
    if 'user' not in st.session_state or not st.session_state.user:
        st.warning("🔒 Please log in")
        st.session_state.page = "login"
        st.rerun()
        return
    if st.session_state.user.get('role') not in ['super_admin', 'support_staff']:
        st.error("Access denied")
        return

    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()

    current_user = get_effective_user()
    st.markdown("### 🏢 Super Admin Dashboard")
    if st.session_state.get('original_user'):
        st.warning(f"👀 Impersonating {st.session_state.user['username']} ({st.session_state.user['role']}). Logged in as {st.session_state.original_user['username']}.")
        if st.button("Stop Impersonation", use_container_width=True):
            stop_impersonation()
            st.rerun()
    st.caption("Complete control over all companies, users, and system settings")
    
    # System Health Dashboard
    with st.expander("📊 System Health Dashboard", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        c.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
        db_size = c.fetchone()
        db_size_mb = round(db_size[0] / (1024 * 1024), 2) if db_size else 0
        
        c.execute("SELECT COUNT(*) FROM users")
        total_users = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM sessions WHERE expires_at > datetime('now')")
        active_sessions = c.fetchone()[0]
        
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        c.execute("SELECT COUNT(*) FROM error_logs WHERE created_at > ?", (yesterday,))
        error_count = c.fetchone()[0]
        
        conn.close()
        
        with col1:
            st.metric("💾 Database Size", f"{db_size_mb} MB")
        with col2:
            st.metric("👥 Total Users", total_users)
        with col3:
            st.metric("🟢 Active Sessions", active_sessions)
        with col4:
            st.metric("⚠️ Errors (24h)", error_count, delta="Critical" if error_count > 10 else "Normal")
    
    # Main Tabs
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "🏢 Companies", 
        "👥 Users & Workers", 
        "🔄 Worker Transfer",
        "📜 Audit Log", 
        "📧 Email Templates",
        "💾 System Actions",
        "⚙️ Settings"
    ])
    
    # TAB 1: COMPANIES
    with tab1:
        st.markdown("### Company Management")
        
        conn = sqlite3.connect(DB_PATH)
        total_companies = pd.read_sql_query("SELECT COUNT(*) as count FROM companies", conn)['count'][0]
        active_companies = pd.read_sql_query("SELECT COUNT(*) as count FROM companies WHERE is_active = 1", conn)['count'][0]
        conn.close()
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.info(f"📊 Total Companies: **{total_companies}**")
        with col2:
            st.success(f"🟢 Active: **{active_companies}**")
        with col3:
            st.warning(f"🔴 Inactive: **{total_companies - active_companies}**")
        
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        with col1:
            search_term = st.text_input("🔍 Search companies", placeholder="Search by name or subdomain...", key="company_search_main")
        with col2:
            status_filter = st.selectbox("Status", ["All", "Active", "Inactive"], key="company_status_main")
        with col3:
            sort_by = st.selectbox("Sort by", ["Newest First", "Oldest First", "Most Users", "Most Clients"], key="company_sort")
        with col4:
            if st.button("🔄 Refresh", use_container_width=True):
                st.rerun()
        
        conn = sqlite3.connect(DB_PATH)
        query = """
            SELECT c.id, c.name, c.subdomain, u.username as owner, u.email as owner_email,
                   c.created_at, c.is_active,
                   (SELECT COUNT(*) FROM users WHERE company_id = c.id) as user_count,
                   (SELECT COUNT(*) FROM clients WHERE company_id = c.id) as client_count,
                   (SELECT COUNT(*) FROM estimates WHERE company_id = c.id) as estimate_count
            FROM companies c
            LEFT JOIN users u ON c.owner_id = u.id
            WHERE 1=1
        """
        params = []
        
        if search_term:
            query += " AND (c.name LIKE ? OR c.subdomain LIKE ?)"
            params.extend([f"%{search_term}%", f"%{search_term}%"])
        
        if status_filter == "Active":
            query += " AND c.is_active = 1"
        elif status_filter == "Inactive":
            query += " AND c.is_active = 0"
        
        if sort_by == "Newest First":
            query += " ORDER BY c.created_at DESC"
        elif sort_by == "Oldest First":
            query += " ORDER BY c.created_at ASC"
        elif sort_by == "Most Users":
            query += " ORDER BY user_count DESC"
        elif sort_by == "Most Clients":
            query += " ORDER BY client_count DESC"
        else:
            query += " ORDER BY c.id"
        
        df = pd.read_sql_query(query, conn, params=params)
        conn.close()
        
        if df.empty:
            st.info("No companies found.")
        else:
            for _, row in df.iterrows():
                with st.container():
                    col1, col2, col3, col4, col5, col6 = st.columns([1, 3, 2, 2, 1, 2])
                    
                    with col1:
                        st.markdown(f"**#{row['id']}**")
                    
                    with col2:
                        st.markdown(f"**{row['name']}**")
                        st.caption(f"Subdomain: {row['subdomain']} | Owner: {row['owner'] or 'N/A'}")
                        st.caption(f"Created: {row['created_at'][:10] if row['created_at'] else 'N/A'}")
                    
                    with col3:
                        st.metric("👥 Users", row['user_count'])
                        st.caption(f"📝 Estimates: {row['estimate_count']}")
                    
                    with col4:
                        st.metric("🏢 Clients", row['client_count'])
                    
                    with col5:
                        if row['is_active'] == 1:
                            st.markdown("🟢 **ACTIVE**")
                        else:
                            st.markdown("🔴 **INACTIVE**")
                    
                    with col6:
                        if row['id'] == 1:
                            st.info("🔒 System")
                        else:
                            col_a, col_b, col_c, col_d = st.columns(4)
                            with col_a:
                                if row['is_active'] == 1:
                                    if st.button(f"🔴 Off", key=f"deact_{row['id']}"):
                                        st.session_state.pending_action = {
                                            "type": "deactivate_company",
                                            "company_id": row['id'],
                                            "company_name": row['name']
                                        }
                                        st.rerun()
                                else:
                                    if st.button(f"🟢 On", key=f"act_{row['id']}"):
                                        st.session_state.pending_action = {
                                            "type": "activate_company",
                                            "company_id": row['id'],
                                            "company_name": row['name']
                                        }
                                        st.rerun()
                            with col_b:
                                if st.button(f"📧 Email", key=f"email_{row['id']}"):
                                    st.session_state.email_company_id = row['id']
                                    st.session_state.email_company_name = row['name']
                                    st.rerun()
                            with col_c:
                                if st.button(f"👁️ View", key=f"view_{row['id']}"):
                                    st.session_state.view_company_id = row['id']
                                    st.rerun()
                            with col_d:
                                if st.button(f"🗑️", key=f"del_comp_{row['id']}"):
                                    st.session_state.pending_action = {
                                        "type": "delete_company",
                                        "company_id": row['id'],
                                        "company_name": row['name'],
                                        "user_count": row['user_count'],
                                        "client_count": row['client_count']
                                    }
                                    st.rerun()
                    
                    st.markdown("---")
            st.markdown("### Data Export")
            export_company_id = st.number_input("Company ID to export", min_value=1, value=1, step=1, key="admin_export_company_id")
            if st.button("Export Company Data", use_container_width=True):
                try:
                    export_json = export_company_data(export_company_id)
                    st.download_button("Download Company Export", export_json, f"company_{export_company_id}_export.json", "application/json")
                except Exception as e:
                    st.error(f"Failed to export company data: {e}")
    
    # Confirmation dialogs (outside the for loop)
    if 'pending_action' in st.session_state:
        action = st.session_state.pending_action
        
        if action['type'] in ['deactivate_company', 'activate_company']:
            st.warning(f"⚠️ Are you sure you want to {action['type'].replace('_', ' ')} **{action['company_name']}**?")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Yes", key="confirm_action"):
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    is_active = 1 if action['type'] == 'activate_company' else 0
                    c.execute("UPDATE companies SET is_active = ? WHERE id = ?", (is_active, action['company_id']))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ {action['company_name']} has been updated.")
                    del st.session_state.pending_action
                    time.sleep(1)
                    st.rerun()
            with col2:
                if st.button("❌ Cancel", key="cancel_action"):
                    del st.session_state.pending_action
                    st.rerun()
        
        elif action['type'] == 'delete_company':
            st.error(f"🗑️ **PERMANENTLY DELETE** Company: **{action['company_name']}**?")
            st.warning(f"⚠️ This will delete:\n- {action['user_count']} user(s)\n- {action['client_count']} client(s)\n- All associated data\n\n**This action CANNOT be undone.**")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🗑️ YES, PERMANENTLY DELETE", key="confirm_delete_company_final"):
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        conn.execute("PRAGMA foreign_keys = OFF")
                        c = conn.cursor()
                        company_id = action['company_id']
                        
                        c.execute("SELECT id FROM users WHERE company_id = ?", (company_id,))
                        user_ids = [row[0] for row in c.fetchall()]
                        
                        if user_ids:
                            placeholders = ','.join(['?' for _ in user_ids])
                            tables_to_clear = [
                                "sessions", "notifications", "audit_log", "team_messages",
                                "support_messages", "worker_certifications", "worker_badges",
                                "estimate_history", "estimate_approvals", "job_assignments"
                            ]
                            for table in tables_to_clear:
                                try:
                                    c.execute(f"DELETE FROM {table} WHERE user_id IN ({placeholders})", user_ids)
                                except:
                                    pass
                        
                        delete_queries = [
                            "DELETE FROM support_tickets WHERE company_id = ?",
                            "DELETE FROM supply_usage WHERE company_id = ?",
                            "DELETE FROM supplies WHERE company_id = ?",
                            "DELETE FROM inspections WHERE company_id = ?",
                            "DELETE FROM scheduled_jobs WHERE company_id = ?",
                            "DELETE FROM estimates WHERE company_id = ?",
                            "DELETE FROM client_communications WHERE company_id = ?",
                            "DELETE FROM clients WHERE company_id = ?",
                            "DELETE FROM quick_jobs WHERE company_id = ?",
                            "DELETE FROM monthly_expenses WHERE company_id = ?",
                            "DELETE FROM job_templates WHERE company_id = ?",
                            "DELETE FROM email_templates WHERE company_id = ?",
                            "DELETE FROM worker_transfers WHERE from_company_id = ? OR to_company_id = ?",
                            "DELETE FROM users WHERE company_id = ?",
                            "DELETE FROM business_profile WHERE company_id = ?",
                            "DELETE FROM companies WHERE id = ?"
                        ]
                        
                        for query in delete_queries:
                            try:
                                c.execute(query, (company_id,))
                            except Exception as e:
                                print(f"Query failed: {query}, Error: {e}")
                        
                        conn.commit()
                        conn.execute("PRAGMA foreign_keys = ON")
                        conn.close()
                        
                        st.success(f"✅ **{action['company_name']}** and all its data have been permanently deleted.")
                        st.balloons()
                        del st.session_state.pending_action
                        time.sleep(2)
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Error deleting company: {str(e)}")
                        if 'conn' in locals():
                            conn.rollback()
                            conn.execute("PRAGMA foreign_keys = ON")
                            conn.close()
                        del st.session_state.pending_action
                        st.rerun()
            
            with col2:
                if st.button("❌ Cancel", key="cancel_delete_company_final"):
                    del st.session_state.pending_action
                    st.rerun()
    
    # TAB 2: USERS & WORKERS
    with tab2:
        st.markdown("### User Management")
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("PRAGMA table_info(users)")
        existing_columns = [col[1] for col in c.fetchall()]
        
        if 'invite_code' in existing_columns:
            query = """
                SELECT u.id, u.username, u.email, u.role, u.company_id, u.is_active, u.created_at, u.invite_code,
                       c.name as company_name, c.subdomain
                FROM users u
                LEFT JOIN companies c ON u.company_id = c.id
                WHERE u.role != 'super_admin'
                ORDER BY c.name, u.role, u.username
            """
        else:
            query = """
                SELECT u.id, u.username, u.email, u.role, u.company_id, u.is_active, u.created_at,
                       '' as invite_code, c.name as company_name, c.subdomain
                FROM users u
                LEFT JOIN companies c ON u.company_id = c.id
                WHERE u.role != 'super_admin'
                ORDER BY c.name, u.role, u.username
            """
        
        try:
            users_df = pd.read_sql_query(query, conn)
        except Exception as e:
            st.error(f"Error loading users: {e}")
            users_df = pd.DataFrame()
        finally:
            conn.close()
        
        if users_df.empty:
            st.info("No users found.")
        else:
            st.dataframe(users_df, use_container_width=True)
            st.markdown("### Manage Users")
            selected_user = st.selectbox(
                "Select a user to manage",
                users_df['id'].tolist(),
                format_func=lambda x: f"{users_df[users_df['id']==x]['username'].iloc[0]} ({users_df[users_df['id']==x]['company_name'].iloc[0] or 'No Company'})",
                key="admin_selected_user"
            )
            if selected_user:
                target_user = get_user_by_id(selected_user)
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT name FROM companies WHERE id = ?", (target_user['company_id'],))
                company_name_row = c.fetchone()
                company_name = company_name_row[0] if company_name_row else "Unknown"
                conn.close()

                st.markdown(f"**Manage {target_user['username']} ({target_user['email']}) | {target_user['role']} | {company_name}**")
                col1, col2 = st.columns(2)
                with col1:
                    if current_user['role'] != 'super_admin':
                        st.caption("Only a super admin can change a user's role.")
                    else:
                        new_role = st.selectbox(
                            "Change Role",
                            ["worker", "supervisor", "manager", "admin", "support_staff", "super_admin"],
                            index=["worker", "supervisor", "manager", "admin", "support_staff", "super_admin"].index(target_user['role']) if target_user['role'] in ["worker", "supervisor", "manager", "admin", "support_staff", "super_admin"] else 0,
                            key="admin_change_role"
                        )
                        if st.button("Update Role", key="admin_update_role"):
                            if new_role != target_user['role']:
                                conn = sqlite3.connect(DB_PATH)
                                c = conn.cursor()
                                c.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, selected_user))
                                conn.commit()
                                conn.close()
                                log_audit(current_user['user_id'], "change_role", f"Changed role for user {selected_user} to {new_role}")
                                st.success("User role updated")
                                st.rerun()
                            else:
                                st.info("Role is already set to that value")
                with col2:
                    if current_user['role'] != 'super_admin':
                        st.caption("Only a super admin can reset another user's password.")
                    else:
                        password_reset = st.text_input("New Password", type="password", key="admin_new_password")
                        if st.button("Reset Password", key="admin_reset_password"):
                            if password_reset:
                                valid, msg = validate_password_strength(password_reset)
                                if not valid:
                                    st.error(msg)
                                else:
                                    hashed, salt = hash_password(password_reset)
                                    conn = sqlite3.connect(DB_PATH)
                                    c = conn.cursor()
                                    c.execute("UPDATE users SET password_hash = ?, salt = ?, login_attempts = 0, locked_until = NULL WHERE id = ?", (hashed, salt, selected_user))
                                    conn.commit()
                                    conn.close()
                                    force_logout_sessions(selected_user)
                                    log_audit(current_user['user_id'], "reset_password", f"Reset password for user {selected_user}")
                                    st.success("Password reset successfully")
                            else:
                                st.error("Enter a new password")

                st.markdown("#### Activation")
                if target_user['is_active']:
                    if st.button("Deactivate User", key="admin_deactivate_user"):
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE users SET is_active = 0 WHERE id = ?", (selected_user,))
                        conn.commit()
                        conn.close()
                        log_audit(current_user['user_id'], "deactivate_user", f"Deactivated user {selected_user}")
                        st.success("User deactivated")
                        st.rerun()
                else:
                    if st.button("Activate User", key="admin_activate_user"):
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("UPDATE users SET is_active = 1 WHERE id = ?", (selected_user,))
                        conn.commit()
                        conn.close()
                        log_audit(current_user['user_id'], "activate_user", f"Activated user {selected_user}")
                        st.success("User activated")
                        st.rerun()

                if current_user['role'] == 'super_admin':
                    if st.button("Impersonate User", key="admin_impersonate_user"):
                        ok, msg = impersonate_user(selected_user)
                        if ok:
                            log_audit(current_user['user_id'], "impersonation_start", f"Started impersonating user {selected_user}")
                            st.success("Now impersonating user")
                            st.rerun()
                        else:
                            st.error(msg)
                    if st.button("Delete User Permanently", key="admin_delete_user"):
                        if delete_user_profile(selected_user):
                            log_audit(current_user['user_id'], "delete_user", f"Deleted user {selected_user}")
                            st.success("User permanently deleted")
                            st.rerun()
                        else:
                            st.error("Failed to delete user")

            if current_user['role'] == 'super_admin':
                with st.expander("➕ Create Support Staff Account"):
                    support_company = st.number_input("Company ID", min_value=1, value=1, step=1, key="support_company_id")
                    support_username = st.text_input("Username", key="support_username")
                    support_email = st.text_input("Email", key="support_email")
                    support_password = st.text_input("Password", type="password", key="support_password")
                    if st.button("Create Support Staff", key="create_support_staff_btn"):
                        if support_username and support_email and support_password:
                            ok, result = create_user(support_username, support_email, support_password, "support_staff", support_company)
                            if ok:
                                log_audit(current_user['user_id'], "create_support_staff", f"Created support staff {support_username} for company {support_company}")
                                st.success("Support staff account created")
                                st.rerun()
                            else:
                                st.error(result)
                        else:
                            st.error("All fields are required")

            with st.expander("✅ Approve or Reject Worker Requests"):
                conn = sqlite3.connect(DB_PATH)
                pending = pd.read_sql_query("SELECT id, name, email, company_id, requested_manager_email, requested_at FROM pending_workers WHERE status = 'pending' ORDER BY requested_at DESC", conn)
                conn.close()
                if pending.empty:
                    st.info("No pending worker requests.")
                else:
                    for _, req in pending.iterrows():
                        st.write(f"{req['name']} ({req['email']}) requested for company {req['company_id']} on {req['requested_at']}")
                        col1, col2 = st.columns(2)
                        if col1.button(f"Approve {req['id']}", key=f"approve_req_{req['id']}"):
                            approve_worker_request(req['id'], current_user['user_id'], req['company_id'])
                            log_audit(current_user['user_id'], "approve_worker_request", f"Approved pending worker request {req['id']}")
                            st.success("Worker request approved")
                            st.rerun()
                        if col2.button(f"Reject {req['id']}", key=f"reject_req_{req['id']}"):
                            deny_worker_request(req['id'], req['company_id'])
                            log_audit(current_user['user_id'], "deny_worker_request", f"Rejected pending worker request {req['id']}")
                            st.success("Worker request denied")
                            st.rerun()

    # TAB 3: WORKER TRANSFER
    with tab3:
        st.markdown("### 🔄 Transfer Workers Between Companies")
        
        if current_user['role'] == 'super_admin':
            render_worker_transfer_ui("admin_companies_tab3")
        else:
            st.error("❌ Access Denied: Only Super Admin can transfer workers between companies.")
            st.info("If you need to transfer a worker, please contact your system administrator.")
    
    # TAB 4: AUDIT LOG
    with tab4:
        st.markdown("### 📜 Audit Log")
        conn = sqlite3.connect(DB_PATH)
        audit_df = pd.read_sql_query("""
            SELECT al.id, u.username, al.action, al.details, al.created_at
            FROM audit_log al
            LEFT JOIN users u ON al.user_id = u.id
            ORDER BY al.created_at DESC
            LIMIT 200
        """, conn)
        conn.close()
        st.dataframe(audit_df, use_container_width=True)
    
    # TAB 5: EMAIL TEMPLATES
    with tab5:
        st.markdown("### 📧 Email Templates")

        conn = sqlite3.connect(DB_PATH)
        companies_df = pd.read_sql_query("SELECT id, name FROM companies WHERE is_active = 1 ORDER BY name", conn)
        conn.close()

        if companies_df.empty:
            st.warning("No active companies available for email templates.")
        else:
            company_names = {row['id']: row['name'] for _, row in companies_df.iterrows()}
            company_options = companies_df['id'].tolist()
            selected_company = st.selectbox(
                "Company",
                company_options,
                format_func=lambda cid: company_names.get(cid, str(cid)),
                index=company_options.index(1) if 1 in company_options else 0,
            )

            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_templates'")
            table_exists = c.fetchone()

            if table_exists:
                templates_df = pd.read_sql_query(
                    "SELECT id, name, subject, is_active FROM email_templates WHERE company_id = ? ORDER BY name",
                    conn,
                    params=(selected_company,),
                )
                if not templates_df.empty:
                    st.dataframe(templates_df)
                else:
                    st.info("No email templates found for this company. Create one below.")
            else:
                st.info("Email templates will be available after you create your first template.")
                templates_df = pd.DataFrame()

            conn.close()

            with st.expander("➕ Add/Edit Template"):
                with st.form("email_template"):
                    template_name = st.selectbox(
                        "Template Type",
                        ["estimate_sent", "estimate_approved", "job_reminder", "review_request", "worker_approval"],
                    )
                    subject = st.text_input("Subject", placeholder="Your estimate from {business_name}")
                    body = st.text_area(
                        "Body",
                        height=200,
                        placeholder="Dear {client_name},\n\nYour estimate is ${amount:,.2f}.\n\nClick here to approve: {approval_link}",
                    )
                    is_active = st.checkbox("Active", value=True)
                    if st.form_submit_button("Save Template"):
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()

                        existing = c.execute(
                            "SELECT id FROM email_templates WHERE company_id = ? AND name = ?",
                            (selected_company, template_name),
                        ).fetchone()

                        if existing:
                            c.execute(
                                "UPDATE email_templates SET subject = ?, body = ?, is_active = ?, created_at = ? WHERE id = ?",
                                (subject, body, 1 if is_active else 0, datetime.now().isoformat(), existing[0]),
                            )
                        else:
                            c.execute(
                                "INSERT INTO email_templates (company_id, name, subject, body, is_active, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                                (selected_company, template_name, subject, body, 1 if is_active else 0, datetime.now().isoformat()),
                            )

                        conn.commit()
                        conn.close()
                        st.success("Template saved successfully!")
                        st.rerun()
    
    # TAB 6: SYSTEM ACTIONS
    with tab6:
        st.markdown("### 💾 System Actions")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Create Full System Backup", use_container_width=True):
                backup_file = create_full_system_backup()
                with open(backup_file, 'rb') as f:
                    st.download_button("Download Backup", f, os.path.basename(backup_file), "application/json")
            if st.button("Force Logout All Active Sessions", use_container_width=True):
                deleted = force_logout_sessions()
                st.success(f"✅ Forced logout for {deleted} active sessions")

            st.markdown("---")
            st.markdown("#### Restore Backup")
            if current_user['role'] != 'super_admin':
                st.info("Only a super admin can restore a full system backup.")
            else:
                uploaded = st.file_uploader("Upload full system backup JSON", type=['json'], key="admin_restore_backup")
                if uploaded:
                    try:
                        backup_data = json.load(uploaded)
                        if backup_data.get('data') and backup_data.get('backup_date'):
                            if st.button("Restore Backup", use_container_width=True, key="admin_restore_confirm"):
                                ok = restore_full_system_backup_data(backup_data)
                                if ok:
                                    st.success("✅ System backup restored. Refresh the app.")
                                    log_audit(current_user['user_id'], "restore_system_backup", "Restored full system backup")
                                else:
                                    st.error("Failed to restore backup.")
                        else:
                            st.error("Uploaded file is not a valid full system backup.")
                    except Exception as e:
                        st.error(f"Failed to read backup file: {e}")
        
        with col2:
            if st.button("Clean Up Old Sessions", use_container_width=True):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")
                conn.commit()
                deleted = c.rowcount
                conn.close()
                st.success(f"✅ Removed {deleted} expired sessions")
            
            if st.button("Vacuum Database", use_container_width=True):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("VACUUM")
                conn.commit()
                conn.close()
                st.success("✅ Database vacuumed successfully")
    
    # TAB 7: SETTINGS
    with tab7:
        st.markdown("### ⚙️ System Settings")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("#### Global Settings")
            default_hourly_wage = st.number_input("Default Hourly Wage", min_value=10.0, value=float(get_global_setting('global.default_hourly_wage', 15.0)), step=0.5)
            default_min_job_fee = st.number_input("Default Minimum Job Fee", min_value=50, value=int(float(get_global_setting('global.default_min_job_fee', 150))), step=25)
            default_tax_rate = st.number_input("Default Tax Rate (%)", min_value=0.0, value=float(get_global_setting('global.tax_rate', 0.06))*100, step=0.5)
            
            st.markdown("#### Market Zone Rate Overrides")
            major_min = st.number_input("Major Metro Min Rate", min_value=0.0, value=float(get_global_setting('zone.major_metro.min', 0.16)), step=0.01)
            major_avg = st.number_input("Major Metro Avg Rate", min_value=0.0, value=float(get_global_setting('zone.major_metro.avg', 0.22)), step=0.01)
            major_max = st.number_input("Major Metro Max Rate", min_value=0.0, value=float(get_global_setting('zone.major_metro.max', 0.30)), step=0.01)
            coastal_min = st.number_input("Coastal Min Rate", min_value=0.0, value=float(get_global_setting('zone.coastal.min', 0.14)), step=0.01)
            coastal_avg = st.number_input("Coastal Avg Rate", min_value=0.0, value=float(get_global_setting('zone.coastal.avg', 0.19)), step=0.01)
            coastal_max = st.number_input("Coastal Max Rate", min_value=0.0, value=float(get_global_setting('zone.coastal.max', 0.26)), step=0.01)
            standard_min = st.number_input("Standard Min Rate", min_value=0.0, value=float(get_global_setting('zone.standard.min', 0.12)), step=0.01)
            standard_avg = st.number_input("Standard Avg Rate", min_value=0.0, value=float(get_global_setting('zone.standard.avg', 0.16)), step=0.01)
            standard_max = st.number_input("Standard Max Rate", min_value=0.0, value=float(get_global_setting('zone.standard.max', 0.22)), step=0.01)
            rural_min = st.number_input("Rural Min Rate", min_value=0.0, value=float(get_global_setting('zone.rural.min', 0.10)), step=0.01)
            rural_avg = st.number_input("Rural Avg Rate", min_value=0.0, value=float(get_global_setting('zone.rural.avg', 0.14)), step=0.01)
            rural_max = st.number_input("Rural Max Rate", min_value=0.0, value=float(get_global_setting('zone.rural.max', 0.18)), step=0.01)
            
            if st.button("Save Global Settings", use_container_width=True):
                set_global_setting('global.default_hourly_wage', default_hourly_wage)
                set_global_setting('global.default_min_job_fee', default_min_job_fee)
                set_global_setting('global.tax_rate', default_tax_rate / 100.0)
                set_global_setting('zone.major_metro.min', major_min)
                set_global_setting('zone.major_metro.avg', major_avg)
                set_global_setting('zone.major_metro.max', major_max)
                set_global_setting('zone.coastal.min', coastal_min)
                set_global_setting('zone.coastal.avg', coastal_avg)
                set_global_setting('zone.coastal.max', coastal_max)
                set_global_setting('zone.standard.min', standard_min)
                set_global_setting('zone.standard.avg', standard_avg)
                set_global_setting('zone.standard.max', standard_max)
                set_global_setting('zone.rural.min', rural_min)
                set_global_setting('zone.rural.avg', rural_avg)
                set_global_setting('zone.rural.max', rural_max)
                st.success("Global settings saved!")
        
        with col2:
            st.markdown("#### System Information")
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            total_users = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM companies")
            total_companies = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM estimates")
            total_estimates = c.fetchone()[0]
            conn.close()
            
            st.metric("Total Users", total_users)
            st.metric("Total Companies", total_companies)
            st.metric("Total Estimates", total_estimates)


# ============================================================
# MAIN ROUTING
# ============================================================

def get_query_params_safely():
    if hasattr(st, "experimental_get_query_params"):
        try:
            return st.experimental_get_query_params()
        except Exception:
            return {}
    if hasattr(st, "get_query_params"):
        try:
            return st.get_query_params()
        except Exception:
            return {}
    return {}


def set_query_params_safely(**kwargs):
    """Safely set query params in Streamlit."""
    if hasattr(st, "experimental_set_query_params"):
        try:
            st.experimental_set_query_params(**kwargs)
        except Exception:
            pass
    elif hasattr(st, "set_query_params"):
        try:
            st.set_query_params(**kwargs)
        except Exception:
            pass


def parse_query_param(params, key):
    """Safely parse query param that may be a string or list."""
    val = params.get(key)
    if isinstance(val, list):
        return val[0] if val else None
    return val


def _platform_admin_marker_paths():
    base = os.path.dirname(os.path.abspath(DB_PATH))
    return os.path.join(base, ".platform_admin_marker"), os.path.join(base, ".platform_admin_lock")


def _run_platform_admin_setup_if_requested():
    """One-time production migration, explicitly triggered by an owner-set
    Streamlit secret (CONFIRM_PLATFORM_ADMIN_SETUP) that is never
    committed to git.

    Removes the temporary bootstrap account/company
    (dustbrosco@gmail.com / "Dust Bros and Co") created during initial
    recovery, freeing that email and subdomain so the owner can
    re-register it normally as a regular tenant admin through the
    public signup wizard. Creates a dedicated platform-only super_admin
    account (admin@profitclean.com) under its own "ProfitClean
    Platform" company, with a freshly generated password that is never
    hardcoded -- it's written only to the diagnostic marker file that
    login_page() surfaces, never to git.

    Guarded by an atomic lock file (O_CREAT|O_EXCL) against concurrent
    Streamlit reruns, and self-disables via a result marker file so it
    can't repeat even if the secret is left set.

    REMOVE THIS FUNCTION, ITS CALL BELOW, AND THE DIAGNOSTIC EXPANDER IN
    login_page() once the new super_admin login is confirmed working.
    """
    marker_path, lock_path = _platform_admin_marker_paths()
    if os.path.exists(marker_path):
        return

    try:
        confirm = st.secrets.get("CONFIRM_PLATFORM_ADMIN_SETUP")
    except Exception:
        confirm = None
    if confirm != "SETUP-PLATFORM-ADMIN":
        return

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        return  # another concurrent rerun is already handling this

    lines = [f"Started at {datetime.now().isoformat()}"]
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id, company_id FROM users WHERE lower(email) = 'dustbrosco@gmail.com'")
        old_user = c.fetchone()
        if old_user:
            old_user_id, old_company_id = old_user
            c.execute("DELETE FROM users WHERE id = ?", (old_user_id,))
            c.execute("DELETE FROM business_profile WHERE company_id = ?", (old_company_id,))
            c.execute("DELETE FROM companies WHERE id = ?", (old_company_id,))
            conn.commit()
            lines.append(f"Removed bootstrap user id={old_user_id} and company id={old_company_id} (frees dustbrosco@gmail.com and its subdomain for reuse).")
        else:
            lines.append("No existing dustbrosco@gmail.com account found (nothing to remove).")
        conn.close()

        new_password = secrets.token_urlsafe(12) + "A1!"
        success, result = create_company(
            "ProfitClean Platform", "platform-admin", "admin@profitclean.com",
            "Platform Admin", new_password,
            make_super_admin=True,
        )
        lines.append(f"create_company() -> success={success}, result={result}")

        if success:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT password_hash, role FROM users WHERE company_id = ?", (result,))
            row = c.fetchone()
            conn.close()
            if row:
                verified = verify_password(new_password, row[0])
                lines.append(f"Created user role={row[1]}, self-check verify_password = {verified}")
                lines.append(f"NEW SUPER ADMIN LOGIN -- email: admin@profitclean.com | password: {new_password}")
            else:
                lines.append("WARNING: no user row found for the new company_id.")
    except Exception as e:
        lines.append(f"ERROR: {type(e).__name__}: {e}")
    finally:
        try:
            with open(marker_path, "w") as f:
                f.write("\n".join(lines))
        except OSError:
            pass
        try:
            os.remove(lock_path)
        except OSError:
            pass


def main():
    _run_platform_admin_setup_if_requested()
    # First, initialize database and run migrations
    init_db()
    ensure_default_global_settings()
    migrate_database()
    clear_expired_sessions()   # Clean old sessions on startup
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM companies")
    company_count = c.fetchone()[0]
    conn.close()

    if company_count == 0:
        if st.session_state.get("page") == "login":
            login_page()
        else:
            setup_wizard()
    else:
        if "page" not in st.session_state:
            st.session_state.page = "login"

        params = get_query_params_safely()
        code = parse_query_param(params, "code")
        state = parse_query_param(params, "state")
        if code and state:
            st.session_state.page = "integrations_calendly_auth"
        elif not st.session_state.get("_page_param_consumed"):
            # Honor a deep-link ?page=... param (used by emailed links like the
            # estimate-approval and client-portal-setup emails) on first load only.
            # Without the "consumed" guard, clicking any in-app nav button would
            # just bounce back to this page on the next rerun since the query
            # param is still in the URL.
            deep_link_page = parse_query_param(params, "page")
            if deep_link_page:
                st.session_state.page = deep_link_page
            st.session_state["_page_param_consumed"] = True

        if st.session_state.get("client_logged_in", False):
            if st.session_state.page == "client_dashboard":
                client_dashboard()
            else:
                st.session_state.page = "client_dashboard"
                client_dashboard()
        else:
            pages = {
                "login": login_page,
                "forgot_password": forgot_password_page,
                "two_factor": two_factor_page,
                "create_account": create_account_page,
                "edit_profile": edit_profile_page,
                "setup_2fa": setup_2fa_page,
                "dashboard": dashboard,
                "estimate": estimate_page,
                "proposal": generate_customer_proposal,
                "quick": quick_job_page,
                "clients": clients_page,
                "workers": workers_page,
                "schedule": schedule_page,
                "job_templates": job_templates_page,
                "inspections": inspections_page,
                "pre_inspection": pre_inspection_page,
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
                "integrations": integrations_page,
                "integrations_calendly_auth": calendly_oauth_page,
                "calendly_callback": calendly_callback_page,
                "approvals": admin_approval_dashboard,
                "debug_logs": debug_logs_page,
                "settings": settings_page,
                "terms": terms_page,
                "approve_estimate": approve_estimate_page,
                "internal_pricing": internal_pricing_dashboard,
                "admin_companies": admin_companies_page,
                "client_login": client_login_page,
                "client_set_password": client_set_password_page,
            }
            current = st.session_state.page
            if current in pages:
                try:
                    pages[current]()
                except Exception as e:
                    log_error_event(type(e).__name__, str(e), page_url=current, stack_trace=traceback.format_exc())
                    st.error("⚠️ Something went wrong loading this page. The issue has been logged.")
                    if st.button("← Return to Dashboard"):
                        st.session_state.page = "dashboard"
                        st.rerun()
            else:
                login_page()

if __name__ == "__main__":
    main()