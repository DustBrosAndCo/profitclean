"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
Complete Version - All Features Included
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
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
}
</style>
""", unsafe_allow_html=True)

# ============================================
# DATABASE SETUP
# ============================================

DB_PATH = os.path.join(os.path.dirname(__file__), "profitclean.db")
SALES_TAX_RATE = 0.06

def init_db():
    """Initialize database tables"""
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
        lat REAL,
        lon REAL,
        notes TEXT,
        created_at DATETIME
    )''')
    
    # Estimates
    c.execute('''CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT,
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
    
    # Workers table
    c.execute('''CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        phone TEXT,
        email TEXT,
        home_address TEXT,
        home_lat REAL,
        home_lon REAL,
        is_active BOOLEAN DEFAULT 1,
        jobs_assigned INTEGER DEFAULT 0,
        jobs_completed INTEGER DEFAULT 0,
        created_at DATETIME
    )''')
    
    # Assignment queue
    c.execute('''CREATE TABLE IF NOT EXISTS assignment_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        position INTEGER,
        updated_at DATETIME
    )''')
    
    # Scheduled jobs
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT,
        worker_id INTEGER,
        scheduled_date DATE,
        scheduled_time TEXT,
        status TEXT DEFAULT 'scheduled'
    )''')
    
    # Inspections
    c.execute('''CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_name TEXT,
        inspection_date DATETIME,
        notes TEXT,
        status TEXT DEFAULT 'draft'
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
    "Daytona Beach", "Naples", "Ocala", "Gainesville", "Tallahassee"
]

PROPERTY_TYPES = {
    "Office Standard": 1.0,
    "Gym / Fitness": 1.6,
    "Restaurant": 2.2,
    "Medical / Dental": 1.6,
    "Retail Store": 1.2,
    "Warehouse": 0.8,
    "Gas Station / C-Store": 1.9,
    "Hotel / Motel": 1.5,
    "School / Daycare": 1.4,
    "Airbnb / Short-Term Rental": 1.0
}

FREQUENCIES = {
    "Weekly": 1.0,
    "Bi-Weekly": 1.35,
    "Monthly": 1.75,
    "One-Time": 2.0
}

HOLIDAY_RATES = {
    "Thanksgiving": 0.35,
    "Christmas": 0.50,
    "New Year's": 0.35,
    "Memorial Day": 0.25,
    "Independence Day": 0.25,
    "Labor Day": 0.25
}

# ============================================
# HELPER FUNCTIONS
# ============================================

def calculate_base_price(city, property_type, sqft, frequency, complexity, travel_miles):
    """Calculate base price"""
    coastal = ["Cocoa Beach", "Daytona Beach", "Naples"]
    rural = ["Ocala", "Gainesville"]
    
    if city in coastal:
        zone_mult = 1.18
        travel_fee = 55
    elif city in rural:
        zone_mult = 1.28
        travel_fee = 65
    else:
        zone_mult = 1.0
        travel_fee = 45
    
    prop_mult = PROPERTY_TYPES.get(property_type, 1.0)
    freq_mult = FREQUENCIES.get(frequency, 1.0)
    comp_factor = 0.7 + (complexity / 10)
    
    price_per_sqft = 0.14 * zone_mult * prop_mult * freq_mult * comp_factor
    subtotal = sqft * price_per_sqft
    travel_cost = (travel_miles * 0.65) + travel_fee
    
    return subtotal + travel_cost, travel_fee

def estimate_toll_cost(origin, destination):
    """Simple toll estimation"""
    return 5.00

def apply_holiday_surcharge(price, holiday):
    """Apply holiday surcharge"""
    if holiday and holiday in HOLIDAY_RATES:
        return price * (1 + HOLIDAY_RATES[holiday])
    return price

def apply_multi_location_discount(price, num_locations):
    """Apply multi-location discount"""
    if num_locations >= 5:
        return price * 0.85
    elif num_locations >= 3:
        return price * 0.90
    elif num_locations >= 2:
        return price * 0.95
    return price

def apply_emergency_premium(price, notice_hours):
    """Apply emergency premium"""
    if notice_hours <= 12:
        return price * 1.75
    elif notice_hours <= 24:
        return price * 1.50
    elif notice_hours <= 48:
        return price * 1.25
    return price

def apply_contract_discount(price, contract_months):
    """Apply contract discount"""
    if contract_months >= 12:
        return price * 0.85
    elif contract_months >= 6:
        return price * 0.90
    elif contract_months >= 3:
        return price * 0.95
    return price

def calculate_price_with_range(city, property_type, sqft, frequency, complexity, travel_miles, 
                                hours_estimated, materials_cost, holiday, num_locations, 
                                notice_hours, contract_months):
    """Calculate all price tiers"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hourly_wage, min_job_fee FROM business_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    
    hourly_wage = row[0] if row else 15.0
    min_job_fee = row[1] if row else 150
    
    base_price, travel_fee = calculate_base_price(city, property_type, sqft, frequency, complexity, travel_miles)
    
    # Calculate true cost
    labor_cost = hours_estimated * hourly_wage if hours_estimated else (sqft / 500) * hourly_wage
    true_cost = labor_cost + materials_cost + travel_fee
    if true_cost < min_job_fee:
        true_cost = min_job_fee
    
    # Fair market price
    fair_price = base_price
    
    # Apply modifiers
    fair_price = apply_holiday_surcharge(fair_price, holiday)
    fair_price = apply_emergency_premium(fair_price, notice_hours)
    fair_price = apply_multi_location_discount(fair_price, num_locations)
    fair_price = apply_contract_discount(fair_price, contract_months)
    
    # Highest price
    highest_price = fair_price * 1.3
    
    # Lowest price (break-even)
    lowest_price = true_cost
    
    # Round up
    lowest_price = math.ceil(lowest_price)
    fair_price = math.ceil(fair_price)
    highest_price = math.ceil(highest_price)
    
    # Calculate tax
    tax_lowest = lowest_price * SALES_TAX_RATE
    tax_fair = fair_price * SALES_TAX_RATE
    tax_highest = highest_price * SALES_TAX_RATE
    
    return {
        "lowest": {
            "subtotal": lowest_price,
            "tax": round(tax_lowest, 2),
            "total": math.ceil(lowest_price + tax_lowest),
            "profit": 0,
            "margin": 0
        },
        "fair": {
            "subtotal": fair_price,
            "tax": round(tax_fair, 2),
            "total": math.ceil(fair_price + tax_fair),
            "profit": round(fair_price - true_cost, 2),
            "margin": round(((fair_price - true_cost) / fair_price) * 100, 1)
        },
        "highest": {
            "subtotal": highest_price,
            "tax": round(tax_highest, 2),
            "total": math.ceil(highest_price + tax_highest),
            "profit": round(highest_price - true_cost, 2),
            "margin": round(((highest_price - true_cost) / highest_price) * 100, 1)
        },
        "true_cost": round(true_cost, 2),
        "toll_estimate": 5.00
    }

# ============================================
# WORKER FUNCTIONS
# ============================================

def add_worker(name, phone, email, address, lat, lon):
    """Add a new worker"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO workers (name, phone, email, home_address, home_lat, home_lon, created_at)
        VALUES (?,?,?,?,?,?,?)
    """, (name, phone, email, address, lat, lon, datetime.now().isoformat()))
    worker_id = c.lastrowid
    
    c.execute("SELECT COUNT(*) FROM assignment_queue")
    queue_size = c.fetchone()[0]
    c.execute("INSERT INTO assignment_queue (worker_id, position, updated_at) VALUES (?,?,?)",
              (worker_id, queue_size, datetime.now().isoformat()))
    conn.commit()
    conn.close()
    return worker_id

def get_all_workers():
    """Get all active workers"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, name, phone, email, home_address, jobs_assigned, jobs_completed
        FROM workers WHERE is_active = 1 ORDER BY name
    """, conn)
    conn.close()
    return df

def get_best_workers_for_job(lat, lon, limit=5):
    """Get best workers (simplified - no geopy)"""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, name, home_lat, home_lon, jobs_assigned
        FROM workers WHERE is_active = 1
    """, conn)
    conn.close()
    
    # Simplified distance calculation (no geopy)
    for idx, row in df.iterrows():
        if row['home_lat'] and lat:
            dist = abs(row['home_lat'] - lat) * 69
        else:
            dist = 999
        df.loc[idx, 'distance'] = round(dist, 1)
    
    df['score'] = df['jobs_assigned'] * 0.4 + df['distance'] * 0.6
    df = df.sort_values('score').head(limit)
    
    return df.to_dict('records')

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
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT business_name FROM business_profile WHERE id=1")
    row = c.fetchone()
    
    c.execute("SELECT SUM(amount_invoiced), SUM(profit) FROM quick_jobs")
    job_data = c.fetchone()
    
    c.execute("SELECT COUNT(*) FROM workers WHERE is_active = 1")
    worker_result = c.fetchone()
    worker_count = worker_result[0] if worker_result else 0
    
    conn.close()
    
    business_name = row[0] if row else "ProfitClean"
    total_revenue = job_data[0] if job_data and job_data[0] else 0
    total_profit = job_data[1] if job_data and job_data[1] else 0
    
    if total_revenue > 0:
        margin = (total_profit / total_revenue) * 100
    else:
        margin = 0
    
    st.title(f"🧹 {business_name}")
    st.caption("Created by Dust Bros & Co.")
    st.markdown("---")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">${total_revenue:,.0f}</div>'
            f'<div class="metric-label">Total Revenue</div></div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">${total_profit:,.0f}</div>'
            f'<div class="metric-label">Total Profit</div></div>',
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{margin:.0f}%</div>'
            f'<div class="metric-label">Profit Margin</div></div>',
            unsafe_allow_html=True
        )
    
    with col4:
        st.markdown(
            f'<div class="metric-card"><div class="metric-value">{worker_count}</div>'
            f'<div class="metric-label">Active Workers</div></div>',
            unsafe_allow_html=True
        )
    
    st.markdown("---")
    st.markdown("### Quick Actions")
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("📝 New Estimate", use_container_width=True):
            st.session_state.page = "estimate"
            st.rerun()
    with col2:
        if st.button("⚡ Quick Job", use_container_width=True):
            st.session_state.page = "quick"
            st.rerun()
    with col3:
        if st.button("👥 Clients", use_container_width=True):
            st.session_state.page = "clients"
            st.rerun()
    with col4:
        if st.button("📅 Schedule", use_container_width=True):
            st.session_state.page = "schedule"
            st.rerun()
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("🔍 Inspections", use_container_width=True):
            st.session_state.page = "inspections"
            st.rerun()
    with col2:
        if st.button("💰 Profit", use_container_width=True):
            st.session_state.page = "profit"
            st.rerun()
    with col3:
        if st.button("📋 History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()
    with col4:
        if st.button("👥 Workers", use_container_width=True):
            st.session_state.page = "workers"
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 📝 Recent Estimates")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT client_name, city, property_type, estimated_price FROM estimates ORDER BY created_at DESC LIMIT 5",
        conn
    )
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Click 'New Estimate' to create your first one.")
    else:
        for _, row in df.iterrows():
            client = row['client_name'] if row['client_name'] else 'Unnamed'
            st.markdown(
                f'<div class="card">'
                f'<strong>{client}</strong> - {row["city"]}<br>'
                f'<small>{row["property_type"]} • ${row["estimated_price"]:,.2f}</small>'
                f'</div>',
                unsafe_allow_html=True
            )

# ============================================
# ESTIMATE PAGE
# ============================================

def estimate_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📝 New Estimate")
    
    col1, col2 = st.columns(2)
    with col1:
        city = st.selectbox("📍 City", FLORIDA_CITIES)
        property_type = st.selectbox("🏢 Property Type", list(PROPERTY_TYPES.keys()))
        sqft = st.number_input("📐 Square Feet", min_value=100, value=2000, step=100)
    with col2:
        frequency = st.selectbox("📅 Frequency", list(FREQUENCIES.keys()))
        complexity = st.slider("⚙️ Complexity (1-10)", 1, 10, 3)
        travel_miles = st.number_input("🚗 Travel Miles", min_value=0, value=25, step=5)
    
    client_name = st.text_input("👤 Client Name", placeholder="Enter client name")
    
    with st.expander("🔒 INTERNAL ONLY - Cost Estimates"):
        col1, col2 = st.columns(2)
        with col1:
            hours_estimated = st.number_input("Estimated hours", min_value=0.5, value=3.0, step=0.5)
        with col2:
            materials_cost = st.number_input("Materials cost ($)", min_value=0, value=35, step=5)
    
    st.markdown("### 🎯 Pricing Modifiers")
    
    col1, col2 = st.columns(2)
    with col1:
        holidays = ["None"] + list(HOLIDAY_RATES.keys())
        holiday = st.selectbox("🎄 Holiday", holidays)
        notice_options = ["Standard (3+ days)", "2 days", "Next day", "Same day"]
        notice_map = {"Standard (3+ days)": 72, "2 days": 48, "Next day": 24, "Same day": 12}
        notice = st.selectbox("🚨 Emergency", notice_options)
        notice_hours = notice_map[notice]
    with col2:
        num_locations = st.number_input("📍 Number of locations", min_value=1, value=1)
        contract_options = ["No contract", "3 months", "6 months", "12 months", "24 months"]
        contract_map = {"No contract": 0, "3 months": 3, "6 months": 6, "12 months": 12, "24 months": 24}
        contract = st.selectbox("📄 Contract", contract_options)
        contract_months = contract_map[contract]
    
    result = calculate_price_with_range(
        city, property_type, sqft, frequency, complexity, travel_miles,
        hours_estimated, materials_cost, holiday, num_locations, notice_hours, contract_months
    )
    
    st.markdown("---")
    st.markdown("### 💰 Pricing Options")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(
            f'<div style="background:#fef3c7;border-radius:16px;padding:1rem;text-align:center;">'
            f'<div style="color:#92400e;">🔥 LOWEST</div>'
            f'<div style="font-size:2rem;font-weight:800;color:#92400e;">${result["lowest"]["total"]}</div>'
            f'<div>0% margin</div></div>',
            unsafe_allow_html=True
        )
    
    with col2:
        st.markdown(
            f'<div style="background:#d1fae5;border-radius:16px;padding:1rem;text-align:center;">'
            f'<div style="color:#065f46;">💰 FAIR MARKET</div>'
            f'<div style="font-size:2rem;font-weight:800;color:#065f46;">${result["fair"]["total"]}</div>'
            f'<div>{result["fair"]["margin"]}% margin</div></div>',
            unsafe_allow_html=True
        )
    
    with col3:
        st.markdown(
            f'<div style="background:#ede9fe;border-radius:16px;padding:1rem;text-align:center;">'
            f'<div style="color:#5b21b6;">⭐ HIGHEST</div>'
            f'<div style="font-size:2rem;font-weight:800;color:#5b21b6;">${result["highest"]["total"]}</div>'
            f'<div>{result["highest"]["margin"]}% margin</div></div>',
            unsafe_allow_html=True
        )
    
    if st.button("💾 Save Estimate", use_container_width=True):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""
            INSERT INTO estimates 
            (client_name, city, property_type, square_feet, frequency, complexity,
             travel_miles, estimated_price, created_at, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (client_name, city, property_type, sqft, frequency, complexity,
              travel_miles, result["fair"]["total"], datetime.now().isoformat(), "sent"))
        conn.commit()
        conn.close()
        st.success(f"✅ Estimate saved: ${result['fair']['total']}")
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
        
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT hourly_wage FROM business_profile WHERE id=1")
        row = c.fetchone()
        conn.close()
        hourly_wage = row[0] if row else 15.0
        
        profit = amount - expenses - (hours * hourly_wage)
        st.metric("Estimated Profit", f"${profit:.2f}")
        
        if st.form_submit_button("Save"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT INTO quick_jobs 
                (job_date, description, hours, amount_invoiced, job_expenses, profit, created_at)
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
    
    if st.button("➕ Add Client"):
        st.session_state.show_client_form = True
    
    if st.session_state.get("show_client_form", False):
        with st.form("new_client_form"):
            business_name = st.text_input("Business Name")
            contact_name = st.text_input("Contact Name")
            phone = st.text_input("Phone")
            email = st.text_input("Email")
            address = st.text_input("Address")
            city = st.text_input("City")
            notes = st.text_area("Notes")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.form_submit_button("Save"):
                    if business_name:
                        conn = sqlite3.connect(DB_PATH)
                        c = conn.cursor()
                        c.execute("""
                            INSERT INTO clients (business_name, contact_name, phone, email, address, city, notes, created_at)
                            VALUES (?,?,?,?,?,?,?,?)
                        """, (business_name, contact_name, phone, email, address, city, notes, datetime.now().isoformat()))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ {business_name} added!")
                        st.session_state.show_client_form = False
                        st.rerun()
            with col2:
                if st.form_submit_button("Cancel"):
                    st.session_state.show_client_form = False
                    st.rerun()
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT business_name, contact_name, phone, city FROM clients ORDER BY business_name", conn)
    conn.close()
    
    if df.empty:
        st.info("No clients yet.")
    else:
        for _, row in df.iterrows():
            st.markdown(
                f'<div class="card">'
                f'<strong>🏢 {row["business_name"]}</strong><br>'
                f'📞 {row["contact_name"] or "No contact"} • {row["phone"] or "No phone"} • 📍 {row["city"] or "No city"}'
                f'</div>',
                unsafe_allow_html=True
            )

# ============================================
# WORKERS PAGE
# ============================================

def workers_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 👥 Worker Management")
    
    tab1, tab2 = st.tabs(["📋 Workers", "➕ Add Worker"])
    
    with tab1:
        workers_df = get_all_workers()
        if workers_df.empty:
            st.info("No workers added yet.")
        else:
            st.dataframe(workers_df, use_container_width=True)
    
    with tab2:
        with st.form("add_worker_form"):
            col1, col2 = st.columns(2)
            with col1:
                name = st.text_input("Full Name")
                phone = st.text_input("Phone")
                email = st.text_input("Email")
            with col2:
                address = st.text_input("Home Address")
                lat = st.number_input("Latitude", value=0.0, format="%.6f")
                lon = st.number_input("Longitude", value=0.0, format="%.6f")
            
            if st.form_submit_button("Add Worker"):
                if name:
                    add_worker(name, phone, email, address, lat, lon)
                    st.success(f"✅ {name} added!")
                    st.rerun()
                else:
                    st.error("Please enter worker name")

# ============================================
# SCHEDULE PAGE
# ============================================

def schedule_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📅 Job Schedule")
    
    col1, col2 = st.columns(2)
    with col1:
        schedule_date = st.date_input("Date", datetime.now())
    with col2:
        client_name = st.text_input("Client Name")
    
    scheduled_time = st.selectbox("Time", ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"])
    
    if st.button("📅 Schedule Job"):
        if client_name:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT INTO scheduled_jobs (client_name, scheduled_date, scheduled_time, status)
                VALUES (?,?,?,?)
            """, (client_name, schedule_date.isoformat(), scheduled_time, "scheduled"))
            conn.commit()
            conn.close()
            st.success(f"✅ Job scheduled for {client_name}")
        else:
            st.warning("Please enter client name")

# ============================================
# INSPECTIONS PAGE
# ============================================

def inspections_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 🔍 Pre-Inspection Checklist")
    
    client_name = st.text_input("Client Name")
    notes = st.text_area("Inspection Notes", placeholder="Document any existing damage or special instructions...")
    
    if st.button("✓ Save Inspection"):
        if client_name:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT INTO inspections (client_name, inspection_date, notes, status)
                VALUES (?,?,?,?)
            """, (client_name, datetime.now().isoformat(), notes, "completed"))
            conn.commit()
            conn.close()
            st.success("✅ Inspection saved!")
            st.balloons()
        else:
            st.warning("Please enter client name")

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
    c.execute("SELECT insurance, vehicle, software, advertising, other FROM monthly_expenses WHERE month_year = ?", 
              (datetime.now().strftime("%Y-%m"),))
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
        st.info("No jobs logged yet. Add some Quick Jobs to see your profit data.")
    else:
        total_revenue = float(df["amount_invoiced"].sum())
        total_profit = float(df["profit"].sum())
        margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total Revenue", f"${total_revenue:,.2f}")
        col2.metric("Total Profit", f"${total_profit:,.2f}")
        col3.metric("Profit Margin", f"{margin:.0f}%")
        
        net_profit = total_profit - total_expenses
        st.metric("Net Profit (after overhead)", f"${net_profit:,.2f}")
        
        st.markdown("---")
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
        st.metric("Total Value", f"${df['estimated_price'].sum():,.2f}")

# ============================================
# SETTINGS PAGE
# ============================================

def settings_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### ⚙️ Settings")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT business_name, phone, email, hourly_wage, profit_target, per_mile_rate, min_job_fee, home_city FROM business_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    
    if row:
        with st.form("settings_form"):
            col1, col2 = st.columns(2)
            with col1:
                business_name = st.text_input("Business Name", row[0])
                phone = st.text_input("Phone", row[1])
                email = st.text_input("Email", row[2])
            with col2:
                hourly_wage = st.number_input("Hourly Wage", value=row[3])
                profit_target = st.number_input("Target Profit %", value=row[4]*100)
                min_job_fee = st.number_input("Minimum Job Fee", value=row[6])
                home_city = st.selectbox("Home Base", FLORIDA_CITIES, index=FLORIDA_CITIES.index(row[7]) if row[7] in FLORIDA_CITIES else 0)
            
            if st.form_submit_button("Save Settings"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("""
                    UPDATE business_profile SET 
                        business_name=?, phone=?, email=?, hourly_wage=?, profit_target=?, 
                        per_mile_rate=?, min_job_fee=?, home_city=?
                    WHERE id=1
                """, (business_name, phone, email, hourly_wage, profit_target/100, 0.65, min_job_fee, home_city))
                conn.commit()
                conn.close()
                st.success("Settings saved!")
                st.rerun()
    else:
        st.warning("Please complete setup first")

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
        
        pages = {
            "dashboard": dashboard,
            "estimate": estimate_page,
            "quick": quick_job_page,
            "clients": clients_page,
            "workers": workers_page,
            "schedule": schedule_page,
            "inspections": inspections_page,
            "profit": profit_page,
            "history": history_page,
            "settings": settings_page
        }
        
        current_page = st.session_state.page
        if current_page in pages:
            pages[current_page]()
        else:
            dashboard()

if __name__ == "__main__":
    main()