"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
Complete Version - All Features Included
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
import json
from datetime import datetime, date, timedelta
import os

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
# CUSTOM CSS
# ============================================

st.markdown("""
<style>
.metric-card {
    background: linear-gradient(135deg, #1E3A5F 0%, #0F172A 100%);
    border-radius: 16px;
    padding: 1.25rem;
    color: white;
    text-align: center;
}
.metric-value {
    font-size: 2rem;
    font-weight: 700;
}
.price-card {
    background: linear-gradient(135deg, #2DD4BF 0%, #0F766E 100%);
    border-radius: 20px;
    padding: 2rem;
    color: white;
    text-align: center;
}
.price-value {
    font-size: 3rem;
    font-weight: 800;
}
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
</style>
""", unsafe_allow_html=True)

# ============================================
# DATABASE SETUP
# ============================================

DB_PATH = os.path.join(os.path.dirname(__file__), "profitclean.db")
SALES_TAX_RATE = 0.06

def init_db():
    """Initialize all database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Business profile
    c.execute('''CREATE TABLE IF NOT EXISTS business_profile (
        id INTEGER PRIMARY KEY,
        business_name TEXT,
        phone TEXT,
        email TEXT,
        hourly_wage REAL,
        labor_burden REAL,
        profit_target REAL,
        min_job_fee REAL,
        home_city TEXT,
        per_mile_rate REAL,
        sales_tax_rate REAL DEFAULT 0.06,
        setup_complete INTEGER DEFAULT 0
    )''')
    
    # Clients
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        business_name TEXT,
        contact_name TEXT,
        phone TEXT,
        email TEXT,
        address TEXT,
        city TEXT,
        password TEXT,
        portal_enabled INTEGER DEFAULT 1,
        notes TEXT,
        created_at DATETIME
    )''')
    
    # Estimates
    c.execute('''CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        city TEXT,
        property_type TEXT,
        square_feet REAL,
        frequency TEXT,
        complexity INTEGER,
        travel_miles REAL,
        estimated_price REAL,
        created_at DATETIME,
        status TEXT DEFAULT 'draft'
    )''')
    
    # Scheduled jobs
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        scheduled_date DATE,
        scheduled_time TEXT,
        status TEXT DEFAULT 'scheduled'
    )''')
    
    # Quick jobs
    c.execute('''CREATE TABLE IF NOT EXISTS quick_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_date DATE,
        description TEXT,
        hours REAL,
        amount_invoiced REAL,
        job_expenses REAL,
        profit REAL,
        created_at DATETIME
    )''')
    
    # Monthly expenses
    c.execute('''CREATE TABLE IF NOT EXISTS monthly_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        month_year TEXT,
        insurance REAL DEFAULT 0,
        vehicle REAL DEFAULT 0,
        software REAL DEFAULT 0,
        advertising REAL DEFAULT 0,
        other REAL DEFAULT 0
    )''')
    
    # Workers
    c.execute('''CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        home_address TEXT,
        is_active INTEGER DEFAULT 1,
        jobs_assigned INTEGER DEFAULT 0,
        created_at DATETIME
    )''')
    
    current_month = datetime.now().strftime("%Y-%m")
    c.execute("INSERT OR IGNORE INTO monthly_expenses (month_year) VALUES (?)", (current_month,))
    
    conn.commit()
    conn.close()

# ============================================
# FLORIDA DATA
# ============================================

FLORIDA_CITIES = [
    "Orlando", "Miami", "Tampa", "Jacksonville", "Cocoa Beach", 
    "Daytona Beach", "Naples", "Ocala", "Gainesville"
]

PROPERTY_TYPES = {
    "Office Standard": 1.0,
    "Gym / Fitness": 1.6,
    "Restaurant": 2.2,
    "Medical / Dental": 1.6,
    "Retail Store": 1.2,
    "Warehouse": 0.8,
    "Gas Station / C-Store": 1.9,
    "Airbnb / Short-Term Rental": 1.0,
}

FREQUENCIES = {
    "Weekly": 1.0,
    "Bi-Weekly": 1.35,
    "Monthly": 1.75,
    "One-Time": 2.0,
}

HOLIDAY_RATES = {
    "Thanksgiving": 0.35,
    "Christmas": 0.50,
    "New Year's": 0.35,
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_base_price(city, property_type, sqft, frequency, complexity, travel_miles):
    """Calculate base price"""
    coastal = ["Cocoa Beach", "Daytona Beach", "Naples"]
    
    if city in coastal:
        zone_mult = 1.18
        travel_fee = 55
    else:
        zone_mult = 1.0
        travel_fee = 45
    
    prop_mult = PROPERTY_TYPES.get(property_type, 1.0)
    freq_mult = FREQUENCIES.get(frequency, 1.0)
    comp_factor = 0.7 + (complexity / 10)
    
    price_per_sqft = 0.14 * zone_mult * prop_mult * freq_mult * comp_factor
    subtotal = sqft * price_per_sqft
    travel_cost = (travel_miles * 0.65) + travel_fee
    
    return subtotal + travel_cost

def get_business_name():
    """Get business name from database"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT business_name FROM business_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else "ProfitClean"

# ============================================
# SETUP WIZARD
# ============================================

def setup_wizard():
    st.title("🧹 ProfitClean")
    st.caption("Created by Dust Bros & Co.")
    
    with st.form("setup"):
        col1, col2 = st.columns(2)
        with col1:
            business_name = st.text_input("Business name", "Dust Bros and Co")
            phone = st.text_input("Phone", "(555) 123-4567")
            hourly_wage = st.number_input("Hourly wage", value=15.0)
        with col2:
            email = st.text_input("Email", "hello@dustbros.com")
            home_city = st.selectbox("Home base", FLORIDA_CITIES)
            min_job_fee = st.number_input("Minimum job fee", value=150)
        
        if st.form_submit_button("Start Using ProfitClean"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM business_profile")
            c.execute("""
                INSERT INTO business_profile 
                (id, business_name, phone, email, hourly_wage, labor_burden, profit_target, 
                 min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete)
                VALUES (1,?,?,?,?,?,?,?,?,?,?,1)
            """, (business_name, phone, email, hourly_wage, 0.25, 0.30,
                  min_job_fee, home_city, 0.65, SALES_TAX_RATE))
            conn.commit()
            conn.close()
            st.success("Setup complete!")
            st.rerun()

# ============================================
# DASHBOARD
# ============================================

def dashboard():
    business_name = get_business_name()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT SUM(amount_invoiced), SUM(profit) FROM quick_jobs")
    job_data = c.fetchone()
    conn.close()
    
    total_revenue = job_data[0] if job_data and job_data[0] else 0
    total_profit = job_data[1] if job_data and job_data[1] else 0
    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    st.title(f"🧹 {business_name}")
    st.caption("Created by Dust Bros & Co.")
    
    # Sidebar navigation
    with st.sidebar:
        st.markdown("### Navigation")
        if st.button("🏠 Dashboard", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()
        if st.button("📝 New Estimate", use_container_width=True):
            st.session_state.page = "estimate"
            st.rerun()
        if st.button("⚡ Quick Job", use_container_width=True):
            st.session_state.page = "quick"
            st.rerun()
        if st.button("👥 Clients", use_container_width=True):
            st.session_state.page = "clients"
            st.rerun()
        if st.button("👤 Client Portal", use_container_width=True):
            st.session_state.page = "client_login"
            st.rerun()
        st.markdown("---")
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">${total_revenue:,.0f}</div><div class="metric-label">Total Revenue</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">${total_profit:,.0f}</div><div class="metric-label">Total Profit</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{margin:.0f}%</div><div class="metric-label">Profit Margin</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📝 Recent Estimates")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, client_name, city, property_type, estimated_price, created_at FROM estimates ORDER BY created_at DESC LIMIT 5", conn)
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Click 'New Estimate' to get started.")
    else:
        for _, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <strong>{row['client_name'] or 'Unnamed Client'}</strong> - {row['city']}<br>
                <small>{row['property_type']} • ${row['estimated_price']:,.2f}</small>
            </div>
            """, unsafe_allow_html=True)

# ============================================
# ESTIMATE PAGE
# ============================================

def estimate_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📝 New Estimate")
    st.caption(f"💰 Florida sales tax ({SALES_TAX_RATE * 100}%) included, prices rounded up.")
    
    col1, col2 = st.columns(2)
    with col1:
        city = st.selectbox("📍 City", FLORIDA_CITIES)
        property_type = st.selectbox("🏢 Property Type", list(PROPERTY_TYPES.keys()))
        sqft = st.number_input("📐 Square Feet", min_value=100, value=2000, step=100)
    with col2:
        frequency = st.selectbox("📅 Frequency", list(FREQUENCIES.keys()))
        complexity = st.slider("⚙️ Complexity (1-10)", 1, 10, 3)
        travel_miles = st.number_input("🚗 Travel Miles (round trip)", min_value=0, value=25, step=5)
    
    client_name = st.text_input("👤 Client Name")
    client_email = st.text_input("📧 Client Email", help="For sending estimate notifications")
    
    # Internal cost estimates
    with st.expander("🔒 INTERNAL ONLY - Cost Estimates"):
        col1, col2 = st.columns(2)
        with col1:
            hours_estimated = st.number_input("Estimated hours", min_value=0.5, value=3.0, step=0.5)
        with col2:
            materials_cost = st.number_input("Materials cost ($)", min_value=0, value=35, step=5)
    
    # Pricing modifiers
    st.markdown("### 🎯 Pricing Modifiers")
    col1, col2 = st.columns(2)
    with col1:
        holidays = ["None"] + list(HOLIDAY_RATES.keys())
        holiday = st.selectbox("🎄 Holiday Service", holidays)
    with col2:
        num_locations = st.number_input("📍 Number of locations", min_value=1, value=1)
    
    # Calculate price
    base_price = calculate_base_price(city, property_type, sqft, frequency, complexity, travel_miles)
    
    # Apply holiday surcharge
    final_price = base_price
    if holiday != "None":
        final_price = final_price * (1 + HOLIDAY_RATES.get(holiday, 0))
    
    # Calculate true cost (break-even)
    hourly_wage = 15.0  # Default, can be fetched from DB
    true_cost = (hours_estimated * hourly_wage) + materials_cost + (travel_miles * 0.65)
    
    # Calculate tiers
    lowest_price = math.ceil(true_cost)
    fair_price = math.ceil(final_price)
    highest_price = math.ceil(final_price * 1.3)
    
    # Calculate tax
    tax_lowest = lowest_price * SALES_TAX_RATE
    tax_fair = fair_price * SALES_TAX_RATE
    tax_highest = highest_price * SALES_TAX_RATE
    
    st.markdown("---")
    st.markdown("### 💰 Pricing Options")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div style="background:#fef3c7;border-radius:16px;padding:1rem;text-align:center;">
            <div style="color:#92400e;">🔥 LOWEST (Break-even)</div>
            <div style="font-size:2rem;font-weight:800;color:#92400e;">${math.ceil(lowest_price + tax_lowest)}</div>
            <div>0% margin</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div style="background:#d1fae5;border-radius:16px;padding:1rem;text-align:center;">
            <div style="color:#065f46;">💰 FAIR MARKET</div>
            <div style="font-size:2rem;font-weight:800;color:#065f46;">${math.ceil(fair_price + tax_fair)}</div>
            <div>Recommended</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div style="background:#ede9fe;border-radius:16px;padding:1rem;text-align:center;">
            <div style="color:#5b21b6;">⭐ HIGHEST (Premium)</div>
            <div style="font-size:2rem;font-weight:800;color:#5b21b6;">${math.ceil(highest_price + tax_highest)}</div>
            <div>Premium service</div>
        </div>
        """, unsafe_allow_html=True)
    
    if st.button("💾 Save Estimate", use_container_width=True):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if client exists
        c.execute("SELECT id FROM clients WHERE email = ?", (client_email,))
        existing = c.fetchone()
        if existing:
            client_id = existing[0]
        else:
            c.execute("INSERT INTO clients (business_name, email, created_at) VALUES (?,?,?)",
                      (client_name, client_email, datetime.now().isoformat()))
            client_id = c.lastrowid
        
        c.execute("""
            INSERT INTO estimates 
            (client_id, client_name, client_email, city, property_type, square_feet,
             frequency, complexity, travel_miles, estimated_price, created_at, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (client_id, client_name, client_email, city, property_type, sqft,
              frequency, complexity, travel_miles, fair_price, datetime.now().isoformat(), "sent"))
        
        estimate_id = c.lastrowid
        conn.commit()
        conn.close()
        
        st.success(f"✅ Estimate #{estimate_id} saved! ${fair_price:.2f}")
        st.balloons()

# ============================================
# QUICK JOB PAGE
# ============================================

def quick_job_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### ⚡ Quick Job Entry")
    
    with st.form("quick_form"):
        col1, col2 = st.columns(2)
        with col1:
            job_date = st.date_input("Date", datetime.now())
            description = st.text_input("Description")
        with col2:
            hours = st.number_input("Hours Worked", value=2.0)
            amount = st.number_input("Amount Invoiced", value=350.0)
        
        expenses = st.number_input("Job Expenses", value=25.0)
        hourly_wage = 15.0
        profit = amount - expenses - (hours * hourly_wage)
        st.metric("Estimated Profit", f"${profit:.2f}")
        
        if st.form_submit_button("Save"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT INTO quick_jobs (job_date, description, hours, amount_invoiced, job_expenses, profit, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (job_date.isoformat(), description, hours, amount, expenses, profit, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            st.success("Quick job saved!")
            st.rerun()

# ============================================
# CLIENTS PAGE
# ============================================

def clients_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 👥 Client CRM")
    
    with st.expander("➕ Add New Client"):
        with st.form("new_client_form"):
            col1, col2 = st.columns(2)
            with col1:
                business_name = st.text_input("Business Name")
                contact_name = st.text_input("Contact Name")
                phone = st.text_input("Phone")
            with col2:
                email = st.text_input("Email")
                address = st.text_input("Address")
                city = st.text_input("City")
            
            if st.form_submit_button("Save Client"):
                if business_name:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO clients (business_name, contact_name, phone, email, address, city, created_at)
                        VALUES (?,?,?,?,?,?,?)
                    """, (business_name, contact_name, phone, email, address, city, datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ {business_name} added!")
                    st.rerun()
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, business_name, contact_name, phone, email, city FROM clients ORDER BY business_name", conn)
    conn.close()
    
    if df.empty:
        st.info("No clients yet.")
    else:
        for _, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <strong>🏢 {row['business_name']}</strong><br>
                📞 {row['contact_name'] or 'No contact'} • {row['phone'] or 'No phone'} • 📍 {row['city'] or 'No city'}
            </div>
            """, unsafe_allow_html=True)

# ============================================
# CLIENT PORTAL
# ============================================

def client_login_page():
    st.markdown("### 👤 Client Portal Login")
    
    with st.form("client_login"):
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login", use_container_width=True):
            # Simple demo login - in production, verify password properly
            if email:
                st.session_state.client_logged_in = True
                st.session_state.client_name = email.split('@')[0]
                st.session_state.page = "client_dashboard"
                st.rerun()
            else:
                st.error("Invalid email")
    
    if st.button("← Back to Main Site"):
        st.session_state.page = "dashboard"
        st.rerun()

def client_dashboard():
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.client_logged_in = False
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown(f"### 👋 Welcome, {st.session_state.client_name}")
    
    tab1, tab2 = st.tabs(["📝 Estimates", "📅 Schedule"])
    
    with tab1:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("SELECT id, city, property_type, estimated_price, created_at, status FROM estimates ORDER BY created_at DESC", conn)
        conn.close()
        
        if df.empty:
            st.info("No estimates yet.")
        else:
            for _, row in df.iterrows():
                st.markdown(f"""
                <div class="card">
                    <strong>Estimate #{row['id']}</strong> - {row['property_type']} in {row['city']}<br>
                    <strong>${row['estimated_price']:,.2f}</strong><br>
                    <small>Status: {row['status']}</small>
                </div>
                """, unsafe_allow_html=True)
    
    with tab2:
        st.info("Your scheduled jobs will appear here.")

# ============================================
# PROFIT PAGE
# ============================================

def profit_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 💰 Profit Dashboard")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM quick_jobs ORDER BY job_date DESC", conn)
    
    c = conn.cursor()
    c.execute("SELECT insurance, vehicle, software, advertising, other FROM monthly_expenses WHERE month_year = ?", (datetime.now().strftime("%Y-%m"),))
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
    
    st.markdown("#### Monthly Expenses")
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
    
    if st.button("Save Expenses"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO monthly_expenses 
            (month_year, insurance, vehicle, software, advertising, other)
            VALUES (?,?,?,?,?,?)
        """, (datetime.now().strftime("%Y-%m"), new_insurance, new_vehicle, new_software, new_advertising, new_other))
        conn.commit()
        conn.close()
        st.success("Expenses saved!")
        st.rerun()
    
    st.markdown("---")
    
    if df.empty:
        st.info("No jobs logged yet.")
    else:
        total_revenue = float(df["amount_invoiced"].sum())
        total_profit = float(df["profit"].sum())
        margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Revenue", f"${total_revenue:,.2f}")
        col2.metric("Total Profit", f"${total_profit:,.2f}")
        col3.metric("Profit Margin", f"{margin:.0f}%")
        
        st.dataframe(df[["job_date", "description", "hours", "amount_invoiced", "profit"]], use_container_width=True)

# ============================================
# HISTORY PAGE
# ============================================

def history_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📋 Estimate History")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, client_name, city, property_type, estimated_price, created_at, status FROM estimates ORDER BY created_at DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("No estimates yet.")
    else:
        st.dataframe(df, use_container_width=True)

# ============================================
# SETTINGS PAGE
# ============================================

def settings_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### ⚙️ Settings")
    st.info("Settings page - configure your business preferences here.")

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    init_db()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT setup_complete FROM business_profile WHERE id=1")
    setup = c.fetchone()
    conn.close()
    
    if not setup or setup[0] == 0:
        setup_wizard()
    else:
        if "page" not in st.session_state:
            st.session_state.page = "dashboard"
        
        if st.session_state.get("client_logged_in", False):
            if st.session_state.page == "client_dashboard":
                client_dashboard()
            else:
                client_dashboard()
        else:
            pages = {
                "dashboard": dashboard,
                "estimate": estimate_page,
                "quick": quick_job_page,
                "clients": clients_page,
                "profit": profit_page,
                "history": history_page,
                "settings": settings_page,
                "client_login": client_login_page
            }
            
            current_page = st.session_state.page
            if current_page in pages:
                pages[current_page]()
            else:
                dashboard()

if __name__ == "__main__":
    main()