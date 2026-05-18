"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
Complete Version - Commercial + Airbnb/STR + Tax + Rounding + Internal Breakdown
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
from datetime import datetime, date, timedelta
import os

# Page config
st.set_page_config(
    page_title="ProfitClean",
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
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
.price-tax {
    font-size: 1rem;
    opacity: 0.9;
    margin-top: 0.5rem;
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
</style>
""", unsafe_allow_html=True)

# Database path
DB_PATH = os.path.join(os.path.dirname(__file__), "profitclean.db")

# Sales tax rate (Florida)
SALES_TAX_RATE = 0.06  # 6% Florida sales tax

def round_up_price(price):
    """Round price up to nearest dollar"""
    return math.ceil(price)

def calculate_with_tax(price):
    """Calculate price plus tax and round up"""
    subtotal = price
    tax = subtotal * SALES_TAX_RATE
    total = subtotal + tax
    rounded_total = round_up_price(total)
    return {
        "subtotal": round(subtotal, 2),
        "tax": round(tax, 2),
        "total": rounded_total,
        "total_display": rounded_total
    }

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
        zip TEXT,
        notes TEXT,
        created_at DATETIME
    )''')
    
    # Estimates
    c.execute('''CREATE TABLE IF NOT EXISTS estimates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        city TEXT,
        property_type TEXT,
        square_feet REAL,
        bedrooms INTEGER,
        bathrooms INTEGER,
        frequency TEXT,
        complexity INTEGER,
        travel_miles REAL,
        toll_cost REAL,
        subtotal REAL,
        tax REAL,
        estimated_price REAL,
        internal_labor_cost REAL,
        internal_materials_cost REAL,
        internal_travel_cost REAL,
        internal_profit REAL,
        internal_margin REAL,
        created_at DATETIME,
        status TEXT DEFAULT 'draft'
    )''')
    
    # Scheduled jobs
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        estimate_id INTEGER,
        scheduled_date DATE,
        scheduled_time TEXT,
        status TEXT DEFAULT 'scheduled'
    )''')
    
    # Inspections
    c.execute('''CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        property_type TEXT,
        inspection_date DATETIME,
        walls_condition TEXT,
        floors_condition TEXT,
        equipment_condition TEXT,
        windows_condition TEXT,
        linens_changed TEXT,
        towels_replaced TEXT,
        supplies_restocked TEXT,
        damage_found TEXT,
        damage_notes TEXT,
        notes TEXT,
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
    
    conn.commit()
    conn.close()

# Florida data
FLORIDA_CITIES = ["Orlando", "Miami", "Tampa", "Jacksonville", "Cocoa Beach", "Daytona Beach", "Naples", "Ocala", "Gainesville", "Tallahassee", "St. Petersburg", "Fort Myers", "Sarasota"]

PROPERTY_TYPES = {
    "Office Standard": {"multiplier": 1.0, "pricing_model": "sqft", "base_rate": 0.14},
    "Gym / Fitness": {"multiplier": 1.6, "pricing_model": "sqft", "base_rate": 0.14},
    "Restaurant": {"multiplier": 2.2, "pricing_model": "sqft", "base_rate": 0.14},
    "Medical / Dental": {"multiplier": 1.6, "pricing_model": "sqft", "base_rate": 0.14},
    "Retail Store": {"multiplier": 1.2, "pricing_model": "sqft", "base_rate": 0.14},
    "Warehouse": {"multiplier": 0.8, "pricing_model": "sqft", "base_rate": 0.12},
    "School / Classroom": {"multiplier": 1.4, "pricing_model": "sqft", "base_rate": 0.13},
    "Post-Construction": {"multiplier": 2.5, "pricing_model": "sqft", "base_rate": 0.18},
    "🏠 Airbnb / Short-Term Rental": {"multiplier": 1.0, "pricing_model": "bedroom", "base_rate": 45},
}

FREQUENCIES = {
    "Daily": 0.85,
    "Weekly": 1.0,
    "Bi-Weekly": 1.35,
    "Monthly": 1.75,
    "One-Time": 2.0,
    "🏠 Per Checkout / Turnover": 1.0,
}

def calculate_internal_breakdown(price_total, hours_estimated, hourly_wage, materials_cost, travel_miles, tolls, travel_fee, per_mile_rate=0.65):
    """
    Calculate internal cost breakdown (NOT shown to customers)
    Shows true profit margin after all expenses
    """
    
    # Labor cost
    labor_cost = hours_estimated * hourly_wage
    
    # Travel cost (gas + vehicle wear)
    travel_cost = (travel_miles * per_mile_rate) + travel_fee
    
    # Total costs
    total_costs = labor_cost + materials_cost + travel_cost + tolls
    
    # Profit
    profit = price_total - total_costs
    profit_margin = (profit / price_total * 100) if price_total > 0 else 0
    
    return {
        "labor_cost": round(labor_cost, 2),
        "materials_cost": round(materials_cost, 2),
        "travel_cost": round(travel_cost, 2),
        "tolls": round(tolls, 2),
        "total_costs": round(total_costs, 2),
        "profit": round(profit, 2),
        "profit_margin": round(profit_margin, 1),
        "effective_hourly_rate": round(profit / hours_estimated, 2) if hours_estimated > 0 else 0
    }

def calculate_commercial_price(city, property_type, sqft, frequency, complexity=3, travel_miles=0, tolls=0, hours_estimated=None, materials_cost=None):
    """Calculate commercial cleaning price with tax and rounding"""
    
    # Zone multiplier
    coastal_cities = ["Cocoa Beach", "Daytona Beach", "Naples"]
    rural_cities = ["Ocala", "Gainesville"]
    
    if city in coastal_cities:
        zone_mult = 1.18
        travel_fee = 55
    elif city in rural_cities:
        zone_mult = 1.28
        travel_fee = 65
    else:
        zone_mult = 1.0
        travel_fee = 45
    
    prop_data = PROPERTY_TYPES.get(property_type, {"multiplier": 1.0, "base_rate": 0.14})
    prop_mult = prop_data["multiplier"]
    base_rate = prop_data["base_rate"]
    freq_mult = FREQUENCIES.get(frequency, 1.0)
    complexity_factor = 0.7 + (complexity / 10)
    
    price_per_sqft = base_rate * zone_mult * prop_mult * freq_mult * complexity_factor
    subtotal = sqft * price_per_sqft
    travel_cost = (travel_miles * 0.65) + travel_fee
    total_before_tax = subtotal + travel_cost + tolls
    
    # Apply minimum job fee
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT min_job_fee, hourly_wage FROM business_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    min_job_fee = row[0] if row else 150
    hourly_wage = row[1] if row else 15.0
    
    if total_before_tax < min_job_fee:
        total_before_tax = min_job_fee
    
    # Calculate tax and round up
    tax = total_before_tax * SALES_TAX_RATE
    total_with_tax = total_before_tax + tax
    rounded_total = math.ceil(total_with_tax)
    
    # Internal breakdown (if estimates provided)
    internal = None
    if hours_estimated is not None and materials_cost is not None:
        internal = calculate_internal_breakdown(
            rounded_total, hours_estimated, hourly_wage, materials_cost, 
            travel_miles, tolls, travel_fee, 0.65
        )
    
    return {
        "subtotal": round(total_before_tax, 2),
        "tax": round(tax, 2),
        "total": rounded_total,
        "price_per_sqft": round(price_per_sqft, 4),
        "travel_fee": travel_fee,
        "internal": internal,
        "breakdown": {
            "zone_mult": zone_mult,
            "prop_mult": prop_mult,
            "freq_mult": freq_mult,
            "complexity_factor": round(complexity_factor, 2)
        }
    }

def calculate_airbnb_price(bedrooms, bathrooms, city, complexity=3, add_ons=None, hours_estimated=None, materials_cost=None):
    """Calculate Airbnb/STR cleaning price with tax and rounding"""
    if add_ons is None:
        add_ons = []
    
    # Zone travel fee
    coastal_cities = ["Cocoa Beach", "Daytona Beach", "Naples"]
    rural_cities = ["Ocala", "Gainesville"]
    
    if city in coastal_cities:
        travel_fee = 55
    elif city in rural_cities:
        travel_fee = 65
    else:
        travel_fee = 45
    
    # Base calculation
    base_price = (bedrooms * 45) + (bathrooms * 25)
    
    # Add-on prices
    add_on_prices = {
        "linens": 15 * bedrooms,
        "towels": 10,
        "dishes": 15,
        "trash": 10,
        "supplies": 20,
        "patio": 25,
        "hottub": 30,
        "lockbox": 10,
        "welcome": 15,
    }
    
    add_on_total = sum([add_on_prices.get(item, 0) for item in add_ons])
    
    # Complexity factor
    complexity_factor = 0.7 + (complexity / 10)
    
    total_before_tax = (base_price + add_on_total) * complexity_factor + travel_fee
    
    # Apply minimum job fee
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT min_job_fee, hourly_wage FROM business_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    min_job_fee = row[0] if row else 150
    hourly_wage = row[1] if row else 15.0
    
    if total_before_tax < min_job_fee:
        total_before_tax = min_job_fee
    
    # Calculate tax and round up
    tax = total_before_tax * SALES_TAX_RATE
    total_with_tax = total_before_tax + tax
    rounded_total = math.ceil(total_with_tax)
    
    # Internal breakdown (if estimates provided)
    internal = None
    if hours_estimated is not None and materials_cost is not None:
        internal = calculate_internal_breakdown(
            rounded_total, hours_estimated, hourly_wage, materials_cost, 
            0, 0, travel_fee, 0.65
        )
    
    return {
        "subtotal": round(total_before_tax, 2),
        "tax": round(tax, 2),
        "total": rounded_total,
        "base_price": base_price,
        "add_on_total": add_on_total,
        "travel_fee": travel_fee,
        "internal": internal,
        "breakdown": {
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "add_ons": add_ons,
            "complexity_factor": round(complexity_factor, 2)
        }
    }

def setup_wizard():
    """One-time setup"""
    st.title("🧹 ProfitClean")
    st.caption("Created by Dust Bros & Co.")
    st.markdown("---")
    
    with st.form("setup"):
        col1, col2 = st.columns(2)
        with col1:
            business_name = st.text_input("Business name", "Dust Bros and Co")
            phone = st.text_input("Phone", "(555) 123-4567")
        with col2:
            email = st.text_input("Email", "hello@dustbros.com")
            home_city = st.selectbox("Home base", FLORIDA_CITIES)
        
        st.markdown("#### Your Costs")
        col1, col2 = st.columns(2)
        with col1:
            hourly_wage = st.number_input("Hourly wage", value=15.0)
        with col2:
            profit_target = st.selectbox("Target profit %", [20, 30, 40], index=1)
        
        st.markdown("#### Travel & Tax")
        col1, col2 = st.columns(2)
        with col1:
            per_mile_rate = st.number_input("Per-mile rate", value=0.65)
        with col2:
            min_job_fee = st.number_input("Minimum job fee", value=150)
        
        st.info(f"Florida sales tax will be added at {SALES_TAX_RATE * 100}% and prices will be rounded up to the nearest dollar.")
        
        submitted = st.form_submit_button("Start Using ProfitClean")
        
        if submitted:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM business_profile")
            c.execute('''INSERT INTO business_profile 
                (id, business_name, phone, email, hourly_wage, labor_burden, profit_target, 
                 min_job_fee, home_city, per_mile_rate, sales_tax_rate, setup_complete)
                VALUES (1,?,?,?,?,?,?,?,?,?,?,1)''',
                (business_name, phone, email, hourly_wage, 0.25, profit_target/100,
                 min_job_fee, home_city, per_mile_rate, SALES_TAX_RATE))
            conn.commit()
            conn.close()
            st.success("Setup complete!")
            st.rerun()

def dashboard():
    """Main dashboard with all features"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT business_name FROM business_profile WHERE id=1")
    row = c.fetchone()
    
    c.execute("SELECT SUM(amount_invoiced), SUM(profit) FROM quick_jobs")
    job_data = c.fetchone()
    conn.close()
    
    business_name = row[0] if row else "ProfitClean"
    total_revenue = job_data[0] if job_data and job_data[0] else 0
    total_profit = job_data[1] if job_data and job_data[1] else 0
    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    st.title(f"🧹 {business_name}")
    st.caption("Created by Dust Bros & Co.")
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${total_revenue:,.0f}</div>
            <div class="metric-label">Total Revenue</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${total_profit:,.0f}</div>
            <div class="metric-label">Total Profit</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{margin:.0f}%</div>
            <div class="metric-label">Profit Margin</div>
        </div>
        """, unsafe_allow_html=True)
    
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
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 📝 Recent Estimates")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, client_name, city, property_type, estimated_price, created_at FROM estimates ORDER BY created_at DESC LIMIT 5", conn)
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Click 'New Estimate' to create your first one.")
    else:
        for _, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <strong>{row['client_name'] or 'Unnamed Client'}</strong> - {row['city']}<br>
                <small>{row['property_type']} • ${row['estimated_price']:,.2f}</small>
            </div>
            """, unsafe_allow_html=True)

def estimate_page():
    """New estimate page - with internal cost breakdown (staff only)"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📝 New Estimate")
    st.caption(f"💰 Florida sales tax ({SALES_TAX_RATE * 100}%) is included and prices are rounded up to the nearest dollar.")
    
    property_type = st.selectbox("🏢 Property Type", list(PROPERTY_TYPES.keys()))
    is_airbnb = property_type == "🏠 Airbnb / Short-Term Rental"
    
    if is_airbnb:
        st.markdown("---")
        st.markdown("#### 🏠 Airbnb / Short-Term Rental Details")
        
        col1, col2 = st.columns(2)
        with col1:
            bedrooms = st.number_input("🛏️ Number of Bedrooms", min_value=0, max_value=10, value=2, step=1)
        with col2:
            bathrooms = st.number_input("🚽 Number of Bathrooms", min_value=0, max_value=8, value=1, step=1)
        
        st.markdown("#### ➕ Add-On Services")
        col1, col2, col3 = st.columns(3)
        with col1:
            linen_change = st.checkbox("Linen change ($15 per bed)")
            towel_refresh = st.checkbox("Towel set refresh ($10)")
            dishes = st.checkbox("Dishes put away ($15)")
        with col2:
            trash = st.checkbox("Trash removal to bin ($10)")
            supplies = st.checkbox("Supply restocking ($20)")
            patio = st.checkbox("Patio / Balcony sweep ($25)")
        with col3:
            hot_tub = st.checkbox("Hot tub check ($30)")
            lockbox = st.checkbox("Lockbox / key return ($10)")
            welcome = st.checkbox("Guest welcome setup ($15)")
        
        city = st.selectbox("📍 City", FLORIDA_CITIES)
        complexity = st.slider("⚙️ Complexity (1-10)", 1, 10, 3, 
                               help="1 = Clean and tidy, 10 = Heavy party cleanup")
        client_name = st.text_input("👤 Guest/Host Name", placeholder="Enter name")
        
        # Internal cost inputs (STAFF ONLY - not shown to customer)
        st.markdown("---")
        with st.expander("🔒 INTERNAL ONLY - Cost Estimates (not shown to customer)"):
            st.caption("These are for your internal profit calculation only.")
            col1, col2 = st.columns(2)
            with col1:
                hours_estimated = st.number_input("Estimated hours for this job", min_value=0.5, value=2.5, step=0.5, key="airbnb_hours")
            with col2:
                materials_cost = st.number_input("Estimated materials cost ($)", min_value=0, value=25, step=5, key="airbnb_materials")
        
        add_ons = []
        if linen_change: add_ons.append("linens")
        if towel_refresh: add_ons.append("towels")
        if dishes: add_ons.append("dishes")
        if trash: add_ons.append("trash")
        if supplies: add_ons.append("supplies")
        if patio: add_ons.append("patio")
        if hot_tub: add_ons.append("hottub")
        if lockbox: add_ons.append("lockbox")
        if welcome: add_ons.append("welcome")
        
        result = calculate_airbnb_price(bedrooms, bathrooms, city, complexity, add_ons, hours_estimated, materials_cost)
        
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(f"""
            <div class="price-card">
                <div class="price-value">${result['total']:,.0f}</div>
                <div class="price-label">total with tax (rounded up)</div>
                <div class="price-tax">Subtotal: ${result['subtotal']:.2f} + Tax: ${result['tax']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Internal breakdown (STAFF ONLY)
        if result.get('internal'):
            st.markdown("---")
            st.markdown("🔒 **INTERNAL COST BREAKDOWN (Staff Only - Not for Customers)**")
            internal = result['internal']
            st.markdown(f"""
            <div class="internal-card">
                <strong>💰 Your True Costs & Profit:</strong><br>
                • Labor Cost: ${internal['labor_cost']:.2f}<br>
                • Materials Cost: ${internal['materials_cost']:.2f}<br>
                • Travel Cost: ${internal['travel_cost']:.2f}<br>
                • Tolls: ${internal['tolls']:.2f}<br>
                • <strong>Total Costs: ${internal['total_costs']:.2f}</strong><br>
                • <strong>Your Profit: ${internal['profit']:.2f}</strong><br>
                • <strong>Profit Margin: {internal['profit_margin']:.1f}%</strong><br>
                • Effective Hourly Rate: ${internal['effective_hourly_rate']:.2f}/hr
            </div>
            """, unsafe_allow_html=True)
            
            # Profit warning
            if internal['profit_margin'] < 20:
                st.warning("⚠️ Profit margin is below 20%. Consider adjusting your pricing or reducing costs.")
            elif internal['profit_margin'] > 40:
                st.success("✅ Excellent profit margin! Your pricing is well optimized.")
        
        with st.expander("🔍 View Calculation Breakdown"):
            st.markdown(f"""
            - **Bedrooms:** {bedrooms} × $45 = ${bedrooms * 45}
            - **Bathrooms:** {bathrooms} × $25 = ${bathrooms * 25}
            - **Add-on services:** ${result['add_on_total']}
            - **Complexity factor:** {result['breakdown']['complexity_factor']:.2f}x
            - **Travel fee:** ${result['travel_fee']}
            - **Subtotal:** ${result['subtotal']:.2f}
            - **Tax ({SALES_TAX_RATE * 100}%):** ${result['tax']:.2f}
            - **Total (rounded up):** ${result['total']:.0f}
            """)
        
        if st.button("💾 Save Estimate", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO estimates 
                (client_name, city, property_type, bedrooms, bathrooms, frequency, complexity, 
                 subtotal, tax, estimated_price, internal_labor_cost, internal_materials_cost,
                 internal_travel_cost, internal_profit, internal_margin, created_at, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (client_name, city, property_type, bedrooms, bathrooms, "Per Checkout", complexity,
                 result['subtotal'], result['tax'], result['total'],
                 result['internal']['labor_cost'] if result['internal'] else 0,
                 result['internal']['materials_cost'] if result['internal'] else 0,
                 result['internal']['travel_cost'] if result['internal'] else 0,
                 result['internal']['profit'] if result['internal'] else 0,
                 result['internal']['profit_margin'] if result['internal'] else 0,
                 datetime.now().isoformat(), "sent"))
            conn.commit()
            conn.close()
            st.success(f"✅ Airbnb estimate saved: ${result['total']:.0f} (includes tax)")
            st.balloons()
    
    else:
        col1, col2 = st.columns(2)
        with col1:
            city = st.selectbox("📍 City", FLORIDA_CITIES)
            sqft = st.number_input("📐 Square Feet", min_value=100, max_value=100000, value=2000, step=100)
        with col2:
            frequency = st.selectbox("📅 Frequency", list(FREQUENCIES.keys()))
            complexity = st.slider("⚙️ Complexity (1-10)", 1, 10, 3)
            travel_miles = st.number_input("🚗 Travel Miles (round trip)", min_value=0, value=25, step=5)
            tolls = st.number_input("🛣️ Estimated Tolls", min_value=0, value=5, step=5)
        
        client_name = st.text_input("👤 Client Name", placeholder="Enter client name")
        
        # Internal cost inputs (STAFF ONLY - not shown to customer)
        st.markdown("---")
        with st.expander("🔒 INTERNAL ONLY - Cost Estimates (not shown to customer)"):
            st.caption("These are for your internal profit calculation only.")
            col1, col2 = st.columns(2)
            with col1:
                hours_estimated = st.number_input("Estimated hours for this job", min_value=0.5, value=3.0, step=0.5, key="commercial_hours")
            with col2:
                materials_cost = st.number_input("Estimated materials cost ($)", min_value=0, value=35, step=5, key="commercial_materials")
        
        result = calculate_commercial_price(city, property_type, sqft, frequency, complexity, travel_miles, tolls, hours_estimated, materials_cost)
        
        st.markdown("---")
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown(f"""
            <div class="price-card">
                <div class="price-value">${result['total']:,.0f}</div>
                <div class="price-label">total with tax (rounded up)</div>
                <div class="price-tax">Subtotal: ${result['subtotal']:.2f} + Tax: ${result['tax']:.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Internal breakdown (STAFF ONLY)
        if result.get('internal'):
            st.markdown("---")
            st.markdown("🔒 **INTERNAL COST BREAKDOWN (Staff Only - Not for Customers)**")
            internal = result['internal']
            st.markdown(f"""
            <div class="internal-card">
                <strong>💰 Your True Costs & Profit:</strong><br>
                • Labor Cost: ${internal['labor_cost']:.2f}<br>
                • Materials Cost: ${internal['materials_cost']:.2f}<br>
                • Travel Cost: ${internal['travel_cost']:.2f}<br>
                • Tolls: ${internal['tolls']:.2f}<br>
                • <strong>Total Costs: ${internal['total_costs']:.2f}</strong><br>
                • <strong>Your Profit: ${internal['profit']:.2f}</strong><br>
                • <strong>Profit Margin: {internal['profit_margin']:.1f}%</strong><br>
                • Effective Hourly Rate: ${internal['effective_hourly_rate']:.2f}/hr
            </div>
            """, unsafe_allow_html=True)
            
            # Profit warning
            if internal['profit_margin'] < 20:
                st.warning("⚠️ Profit margin is below 20%. Consider adjusting your pricing or reducing costs.")
            elif internal['profit_margin'] > 40:
                st.success("✅ Excellent profit margin! Your pricing is well optimized.")
        
        if st.button("💾 Save Estimate", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO estimates 
                (client_name, city, property_type, square_feet, frequency, complexity,
                 travel_miles, toll_cost, subtotal, tax, estimated_price,
                 internal_labor_cost, internal_materials_cost, internal_travel_cost,
                 internal_profit, internal_margin, created_at, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (client_name, city, property_type, sqft, frequency, complexity,
                 travel_miles, tolls, result['subtotal'], result['tax'], result['total'],
                 result['internal']['labor_cost'] if result['internal'] else 0,
                 result['internal']['materials_cost'] if result['internal'] else 0,
                 result['internal']['travel_cost'] if result['internal'] else 0,
                 result['internal']['profit'] if result['internal'] else 0,
                 result['internal']['profit_margin'] if result['internal'] else 0,
                 datetime.now().isoformat(), "sent"))
            conn.commit()
            conn.close()
            st.success(f"✅ Estimate saved: ${result['total']:.0f} (includes tax)")
            st.balloons()
        
        with st.expander("🔍 View Calculation Breakdown"):
            zone_type = "Coastal" if city in ["Cocoa Beach", "Daytona Beach", "Naples"] else "Rural" if city in ["Ocala", "Gainesville"] else "Urban"
            st.markdown(f"""
            - **Zone:** {zone_type}
            - **Price per sq ft:** ${result['price_per_sqft']:.4f}
            - **Subtotal:** ${result['subtotal']:.2f}
            - **Tax ({SALES_TAX_RATE * 100}%):** ${result['tax']:.2f}
            - **Total (rounded up):** ${result['total']:.0f}
            """)

def quick_job_page():
    """Quick job entry"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### ⚡ Quick Job Entry")
    st.caption("Log a completed job to track your profit")
    
    with st.form("quick_form"):
        col1, col2 = st.columns(2)
        with col1:
            job_date = st.date_input("Date", datetime.now())
            description = st.text_input("Job Description", "Commercial cleaning")
        with col2:
            hours = st.number_input("Hours Worked", min_value=0.5, value=2.0, step=0.5)
            amount = st.number_input("Amount Invoiced (after tax)", min_value=0.0, value=350.0)
        
        expenses = st.number_input("Job Expenses (materials, tolls, etc.)", min_value=0.0, value=25.0)
        
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
            st.metric("Estimated Profit", f"${profit:.2f}")
        with col3:
            st.metric("Profit Margin", f"{margin:.0f}%")
        
        if st.form_submit_button("💾 Save Quick Job", use_container_width=True):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO quick_jobs 
                (job_date, description, hours, amount_invoiced, job_expenses, profit, created_at)
                VALUES (?,?,?,?,?,?,?)''',
                (job_date.isoformat(), description, hours, amount, expenses, profit, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            st.success("✅ Quick job saved!")
            st.rerun()

def clients_page():
    """Client management"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 👥 Client CRM")
    
    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("➕ Add Client", use_container_width=True):
            st.session_state.show_client_form = True
    
    if st.session_state.get("show_client_form", False):
        with st.form("new_client_form"):
            st.markdown("#### New Client")
            col1, col2 = st.columns(2)
            with col1:
                business_name = st.text_input("Business Name")
                contact_name = st.text_input("Contact Name")
                phone = st.text_input("Phone")
            with col2:
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
                        c.execute('''INSERT INTO clients 
                            (business_name, contact_name, phone, email, address, city, notes, created_at)
                            VALUES (?,?,?,?,?,?,?,?)''',
                            (business_name, contact_name, phone, email, address, city, notes, datetime.now().isoformat()))
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
    df = pd.read_sql_query("SELECT id, business_name, contact_name, phone, city FROM clients ORDER BY business_name", conn)
    conn.close()
    
    if df.empty:
        st.info("No clients yet. Click 'Add Client' to get started.")
    else:
        for _, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <strong>🏢 {row['business_name']}</strong><br>
                📞 {row['contact_name'] or 'No contact'} • {row['phone'] or 'No phone'} • 📍 {row['city'] or 'No city'}
            </div>
            """, unsafe_allow_html=True)

def schedule_page():
    """Job scheduling"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📅 Job Schedule")
    
    col1, col2 = st.columns(2)
    with col1:
        schedule_date = st.date_input("Date", datetime.now())
    with col2:
        conn = sqlite3.connect(DB_PATH)
        clients_df = pd.read_sql_query("SELECT business_name FROM clients", conn)
        conn.close()
        client_options = ["Select a client..."] + clients_df["business_name"].tolist() if not clients_df.empty else ["No clients yet"]
        client_name = st.selectbox("Select Client", client_options)
    
    scheduled_time = st.selectbox("Time", ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"])
    
    if st.button("📅 Schedule Job", use_container_width=True):
        if client_name not in ["Select a client...", "No clients yet"]:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('''INSERT INTO scheduled_jobs 
                (client_name, scheduled_date, scheduled_time, status)
                VALUES (?,?,?,?)''',
                (client_name, schedule_date.isoformat(), scheduled_time, "scheduled"))
            conn.commit()
            conn.close()
            st.success(f"✅ Job scheduled for {client_name} on {schedule_date} at {scheduled_time}")
        else:
            st.warning("Please add a client first")
    
    st.markdown("---")
    st.markdown("#### Upcoming Jobs")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT client_name, scheduled_date, scheduled_time, status FROM scheduled_jobs ORDER BY scheduled_date", conn)
    conn.close()
    
    if df.empty:
        st.info("No scheduled jobs")
    else:
        for _, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <strong>{row['client_name']}</strong><br>
                📅 {row['scheduled_date']} at {row['scheduled_time']} • {row['status']}
            </div>
            """, unsafe_allow_html=True)

def inspections_page():
    """Pre-inspection checklists"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 🔍 Pre-Inspection Checklist")
    st.caption("Document existing conditions before starting work")
    
    conn = sqlite3.connect(DB_PATH)
    clients_df = pd.read_sql_query("SELECT business_name FROM clients", conn)
    conn.close()
    client_options = ["Select a client..."] + clients_df["business_name"].tolist() if not clients_df.empty else ["No clients yet"]
    client_name = st.selectbox("Client", client_options)
    
    property_type = st.selectbox("Property Type", ["Commercial", "🏠 Airbnb / STR"])
    
    st.markdown("---")
    
    if property_type == "🏠 Airbnb / STR":
        st.markdown("### 🏠 Airbnb / STR Specific Checklist")
        
        col1, col2 = st.columns(2)
        with col1:
            linens = st.radio("Linens changed on all beds?", ["Yes", "No"], key="linens")
            towels = st.radio("Fresh towels placed?", ["Yes", "No"], key="towels")
            dishes = st.radio("Dishes clean and put away?", ["Yes", "No"], key="dishes")
            trash = st.radio("All trash removed to outside bin?", ["Yes", "No"], key="trash_str")
        with col2:
            supplies = st.radio("Supplies restocked (TP, soap, coffee)?", ["Yes", "No"], key="supplies")
            fridge = st.radio("Refrigerator cleared of old food?", ["Yes", "No"], key="fridge_str")
            amenities = st.radio("Amenities (WiFi, TV, AC) working?", ["Yes", "No"], key="amenities")
            lockbox = st.radio("Lockbox/key returned to correct spot?", ["Yes", "No"], key="lockbox")
        
        st.markdown("#### 🚨 Damage Check")
        damage = st.radio("Any damage found beyond normal wear?", ["Yes", "No"], key="damage")
        damage_notes = ""
        if damage == "Yes":
            damage_notes = st.text_area("Describe damage found (photos recommended):")
        
        notes = st.text_area("Additional Notes")
        
        if st.button("✓ Save Inspection", use_container_width=True):
            if client_name not in ["Select a client...", "No clients yet"]:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('''INSERT INTO inspections 
                    (client_name, property_type, inspection_date, linens_changed, towels_replaced,
                     supplies_restocked, damage_found, damage_notes, notes, status)
                    VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (client_name, property_type, datetime.now().isoformat(), linens, towels,
                     supplies, damage, damage_notes, notes, "completed"))
                conn.commit()
                conn.close()
                st.success("✅ Airbnb inspection saved!")
                st.balloons()
            else:
                st.warning("Please select a client first")
    
    else:
        st.markdown("### 🧼 Commercial Cleaning Checklist")
        
        col1, col2 = st.columns(2)
        with col1:
            walls = st.radio("Walls", ["No damage", "Scuffs", "Holes", "Missing"], index=0)
            equipment = st.radio("Equipment", ["Good", "Broken", "Missing", "N/A"], index=0)
        with col2:
            floors = st.radio("Floors", ["Good", "Normal wear", "Stains", "Damage"], index=0)
            windows = st.radio("Windows", ["Clean", "Streaks", "Cracked", "Foggy"], index=0)
        
        notes = st.text_area("Additional Notes")
        
        if st.button("✓ Save Inspection", use_container_width=True):
            if client_name not in ["Select a client...", "No clients yet"]:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('''INSERT INTO inspections 
                    (client_name, property_type, inspection_date, walls_condition, floors_condition,
                     equipment_condition, windows_condition, notes, status)
                    VALUES (?,?,?,?,?,?,?,?,?)''',
                    (client_name, property_type, datetime.now().isoformat(), walls, floors, equipment, windows, notes, "completed"))
                conn.commit()
                conn.close()
                st.success("✅ Inspection saved!")
                st.balloons()
            else:
                st.warning("Please select a client first")

def profit_page():
    """Profit dashboard"""
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
            "insurance": expenses_row[0] or 0,
            "vehicle": expenses_row[1] or 0,
            "software": expenses_row[2] or 0,
            "advertising": expenses_row[3] or 0,
            "other": expenses_row[4] or 0
        }
    else:
        expenses = {"insurance": 0, "vehicle": 0, "software": 0, "advertising": 0, "other": 0}
    
    total_expenses = sum(expenses.values())
    
    st.markdown("#### Monthly Expenses")
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        new_insurance = st.number_input("Insurance", value=expenses["insurance"], step=50)
    with col2:
        new_vehicle = st.number_input("Vehicle", value=expenses["vehicle"], step=50)
    with col3:
        new_software = st.number_input("Software", value=expenses["software"], step=25)
    with col4:
        new_advertising = st.number_input("Advertising", value=expenses["advertising"], step=50)
    with col5:
        new_other = st.number_input("Other", value=expenses["other"], step=50)
    
    if st.button("Save Expenses"):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO monthly_expenses 
            (month_year, insurance, vehicle, software, advertising, other)
            VALUES (?,?,?,?,?,?)''',
            (datetime.now().strftime("%Y-%m"), new_insurance, new_vehicle, new_software, new_advertising, new_other))
        conn.commit()
        conn.close()
        st.success("Expenses saved!")
        st.rerun()
    
    st.markdown("---")
    
    if df.empty:
        st.info("No jobs logged yet. Add some Quick Jobs to see your profit data.")
    else:
        total_revenue = df["amount_invoiced"].sum()
        total_job_expenses = df["job_expenses"].sum()
        total_profit = df["profit"].sum()
        margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
        
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
            st.metric("Overall Margin", f"{margin:.0f}%")
        
        st.markdown("---")
        st.markdown("#### Recent Jobs")
        st.dataframe(df[["job_date", "description", "hours", "amount_invoiced", "profit"]], use_container_width=True)
        
        if total_expenses > 0:
            daily_target = total_expenses / 22
            st.info(f"📊 To break even on monthly expenses (${total_expenses:,.0f}), you need ${daily_target:.0f} per day (22 working days).")

def history_page():
    """Estimate history"""
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📋 Estimate History")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, client_name, city, property_type, estimated_price, created_at, status FROM estimates ORDER BY created_at DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Create your first estimate!")
    else:
        st.dataframe(df, use_container_width=True)
        
        total_value = df["estimated_price"].sum()
        st.metric("Total Value of All Estimates", f"${total_value:,.2f}")

def settings_page():
    """Settings"""
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
                per_mile_rate = st.number_input("Per-Mile Rate", value=row[5])
                min_job_fee = st.number_input("Minimum Job Fee", value=row[6])
                home_city = st.selectbox("Home Base City", FLORIDA_CITIES, index=FLORIDA_CITIES.index(row[7]) if row[7] in FLORIDA_CITIES else 0)
            
            if st.form_submit_button("Save Settings"):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute('''UPDATE business_profile SET 
                    business_name=?, phone=?, email=?, hourly_wage=?, profit_target=?, 
                    per_mile_rate=?, min_job_fee=?, home_city=?
                    WHERE id=1''',
                    (business_name, phone, email, hourly_wage, profit_target/100, per_mile_rate, min_job_fee, home_city))
                conn.commit()
                conn.close()
                st.success("Settings saved!")
                st.rerun()
    else:
        st.warning("Please complete setup first")

def main():
    """Main app"""
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
        
        if st.session_state.page == "dashboard":
            dashboard()
        elif st.session_state.page == "estimate":
            estimate_page()
        elif st.session_state.page == "quick":
            quick_job_page()
        elif st.session_state.page == "clients":
            clients_page()
        elif st.session_state.page == "schedule":
            schedule_page()
        elif st.session_state.page == "inspections":
            inspections_page()
        elif st.session_state.page == "profit":
            profit_page()
        elif st.session_state.page == "history":
            history_page()
        elif st.session_state.page == "settings":
            settings_page()

if __name__ == "__main__":
    main()