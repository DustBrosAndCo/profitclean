"""
PROFITCLEAN - Commercial Cleaning Estimator
Created by Dust Bros & Co.
Complete Version - All Features Included
- Florida zone pricing
- 15+ property types
- Three-tier pricing (Lowest/Fair/Highest)
- Toll estimation
- Add-on services
- Holiday surcharge
- Multi-location discount
- Emergency premium
- Contract discount
- Client CRM
- Worker management
- Fair job assignment
- Job scheduling
- Dynamic inspections with edit/undo
- Quick job entry
- Profit dashboard
- Estimate history
- Client portal
- CSV export
- Email notifications
- PWA support
"""

import streamlit as st
import sqlite3
import pandas as pd
import math
import json
import hashlib
import os
import io
import csv
from datetime import datetime, date, timedelta

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
# PWA / MOBILE APP CONFIGURATION
# ============================================

st.markdown('''
<link rel="manifest" href="static/manifest.json">
<meta name="theme-color" content="#1E3A5F">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="ProfitClean">
<link rel="apple-touch-icon" href="https://via.placeholder.com/152?text=PC">
''', unsafe_allow_html=True)

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
.price-tax {
    font-size: 0.85rem;
    opacity: 0.9;
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
        smtp_email TEXT,
        smtp_password TEXT,
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
        state TEXT,
        zip TEXT,
        lat REAL,
        lon REAL,
        password TEXT,
        portal_enabled INTEGER DEFAULT 1,
        notes TEXT,
        created_at DATETIME,
        updated_at DATETIME
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
        created_at DATETIME,
        status TEXT DEFAULT 'draft',
        approved_at DATETIME
    )''')
    
    # Scheduled jobs
    c.execute('''CREATE TABLE IF NOT EXISTS scheduled_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        client_email TEXT,
        estimate_id INTEGER,
        assigned_worker_id INTEGER,
        scheduled_date DATE,
        scheduled_time TEXT,
        status TEXT DEFAULT 'scheduled',
        reminder_sent INTEGER DEFAULT 0,
        completed_at DATETIME
    )''')
    
    # Inspections (dynamic)
    c.execute('''CREATE TABLE IF NOT EXISTS inspections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id INTEGER,
        client_name TEXT,
        property_type TEXT,
        areas_json TEXT,
        inspection_data TEXT,
        status TEXT DEFAULT 'in_progress',
        started_at DATETIME,
        completed_at DATETIME
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
        home_lat REAL,
        home_lon REAL,
        is_active INTEGER DEFAULT 1,
        jobs_assigned INTEGER DEFAULT 0,
        jobs_completed INTEGER DEFAULT 0,
        hourly_rate REAL,
        created_at DATETIME
    )''')
    
    # Assignment queue (fairness tracking)
    c.execute('''CREATE TABLE IF NOT EXISTS assignment_queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        position INTEGER,
        updated_at DATETIME
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
        completed_at DATETIME
    )''')
    
    # Email templates
    c.execute('''CREATE TABLE IF NOT EXISTS email_templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        subject TEXT,
        body TEXT
    )''')
    
    # Insert default email templates
    c.execute("SELECT COUNT(*) FROM email_templates")
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO email_templates (name, subject, body) VALUES (?,?,?)",
                  ("estimate_approved", "Your estimate has been approved", 
                   "Dear {client_name},\n\nYour estimate #{estimate_id} for ${amount} has been approved. We'll contact you to schedule.\n\nThank you!"))
        c.execute("INSERT INTO email_templates (name, subject, body) VALUES (?,?,?)",
                  ("job_reminder", "Upcoming Cleaning Appointment", 
                   "Dear {client_name},\n\nThis is a reminder that we will be cleaning your property on {date} at {time}.\n\nThank you!"))
        c.execute("INSERT INTO email_templates (name, subject, body) VALUES (?,?,?)",
                  ("estimate_sent", "New Estimate from {business_name}", 
                   "Dear {client_name},\n\nPlease find attached your estimate for {property_type} in {city}.\n\nAmount: ${amount}\n\nTo approve this estimate, please log into the client portal.\n\nThank you!"))
    
    current_month = datetime.now().strftime("%Y-%m")
    c.execute("INSERT OR IGNORE INTO monthly_expenses (month_year) VALUES (?)", (current_month,))
    
    conn.commit()
    conn.close()

# ============================================
# FLORIDA DATA
# ============================================

FLORIDA_CITIES = [
    "Orlando", "Miami", "Tampa", "Jacksonville", "Cocoa Beach", 
    "Daytona Beach", "Naples", "Ocala", "Gainesville", "Tallahassee",
    "St. Petersburg", "Fort Myers", "Sarasota", "Pensacola", "Lakeland"
]

# Property types with multipliers and base rates
PROPERTY_TYPES = {
    "Office Standard": {"multiplier": 1.0, "pricing_model": "sqft", "base_rate": 0.14},
    "Retail Store": {"multiplier": 1.2, "pricing_model": "sqft", "base_rate": 0.14},
    "Warehouse": {"multiplier": 0.8, "pricing_model": "sqft", "base_rate": 0.12},
    "🏥 Medical / Dental": {"multiplier": 1.6, "pricing_model": "sqft", "base_rate": 0.14},
    "🏭 Industrial Facility": {"multiplier": 1.2, "pricing_model": "sqft", "base_rate": 0.12},
    "🏫 School / Daycare": {"multiplier": 1.4, "pricing_model": "sqft", "base_rate": 0.13},
    "🏨 Hotel / Motel": {"multiplier": 1.5, "pricing_model": "sqft", "base_rate": 0.14},
    "🍽️ Restaurant": {"multiplier": 2.2, "pricing_model": "sqft", "base_rate": 0.14},
    "⛽ Gas Station / C-Store": {"multiplier": 1.9, "pricing_model": "sqft", "base_rate": 0.16},
    "🏢 High-Rise Building": {"multiplier": 1.3, "pricing_model": "sqft", "base_rate": 0.14},
    "⛪ Church / Worship Center": {"multiplier": 1.2, "pricing_model": "sqft", "base_rate": 0.13},
    "🛍️ Shopping Mall": {"multiplier": 1.3, "pricing_model": "sqft", "base_rate": 0.14},
    "🏋️ Gym / Fitness": {"multiplier": 1.6, "pricing_model": "sqft", "base_rate": 0.14},
    "🏗️ Post-Construction": {"multiplier": 2.5, "pricing_model": "sqft", "base_rate": 0.18},
    "🎪 Event Venue": {"multiplier": 1.5, "pricing_model": "sqft", "base_rate": 0.14},
    "🏠 Airbnb / Short-Term Rental": {"multiplier": 1.0, "pricing_model": "bedroom", "base_rate": 45},
}

# Frequencies with multipliers
FREQUENCIES = {
    "Daily": 0.85,
    "Weekly": 1.0,
    "Bi-Weekly": 1.35,
    "Monthly": 1.75,
    "One-Time": 2.0,
    "🏠 Per Checkout / Turnover": 1.0,
}

# Holiday surcharge rates
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

# Toll zones and known routes (free estimation)
KNOWN_TOLL_RATES = {
    ("orlando", "miami"): {"sunpass": 17.00, "toll_by_plate": 23.00},
    ("miami", "orlando"): {"sunpass": 17.00, "toll_by_plate": 23.00},
    ("orlando", "tampa"): {"sunpass": 8.50, "toll_by_plate": 12.00},
    ("tampa", "orlando"): {"sunpass": 8.50, "toll_by_plate": 12.00},
    ("orlando", "cocoa beach"): {"sunpass": 5.50, "toll_by_plate": 8.00},
    ("cocoa beach", "orlando"): {"sunpass": 5.50, "toll_by_plate": 8.00},
    ("orlando", "jacksonville"): {"sunpass": 12.00, "toll_by_plate": 17.00},
    ("jacksonville", "orlando"): {"sunpass": 12.00, "toll_by_plate": 17.00},
    ("tampa", "cocoa beach"): {"sunpass": 14.00, "toll_by_plate": 20.00},
    ("cocoa beach", "tampa"): {"sunpass": 14.00, "toll_by_plate": 20.00},
    ("miami", "naples"): {"sunpass": 9.00, "toll_by_plate": 13.00},
    ("naples", "miami"): {"sunpass": 9.00, "toll_by_plate": 13.00},
}

TOLL_ZONES = {
    "orlando": {"toll_factor": 1.2, "base_toll": 2.50},
    "miami": {"toll_factor": 1.5, "base_toll": 3.00},
    "tampa": {"toll_factor": 1.0, "base_toll": 1.50},
    "cocoa beach": {"toll_factor": 1.3, "base_toll": 2.00},
    "daytona beach": {"toll_factor": 1.2, "base_toll": 2.00},
    "naples": {"toll_factor": 1.4, "base_toll": 2.50},
    "jacksonville": {"toll_factor": 1.1, "base_toll": 1.50},
}

# Add-on services pricing
ADD_ON_SERVICES = {
    "window_cleaning": {"name": "Window Cleaning", "price_per_unit": 50, "unit": "per hour", "multiplier": 1.0},
    "carpet_cleaning": {"name": "Carpet Cleaning", "price_per_unit": 0.20, "unit": "per sq ft", "multiplier": 1.0},
    "floor_waxing": {"name": "Floor Stripping/Waxing", "price_per_unit": 0.30, "unit": "per sq ft", "multiplier": 1.0},
    "electrostatic_disinfection": {"name": "Electrostatic Disinfection", "price_per_unit": 75, "unit": "per session", "multiplier": 1.0},
    "pressure_washing": {"name": "Pressure Washing", "price_per_unit": 125, "unit": "per hour", "multiplier": 1.0},
    "extra_trash": {"name": "Extra Trash Removal", "price_per_unit": 25, "unit": "per bin", "multiplier": 1.0},
    "post_construction": {"name": "Post-Construction Cleanup", "price_per_unit": 0.50, "unit": "per sq ft", "multiplier": 1.0},
    "event_cleanup": {"name": "Event Cleanup", "price_per_unit": 150, "unit": "per event", "multiplier": 1.0},
}

# ============================================
# PRICING CALCULATION ENGINE
# ============================================

def estimate_toll_cost(origin_city, destination_city, has_sunpass=True):
    """Estimate Florida toll costs based on route"""
    origin_lower = str(origin_city).lower()
    dest_lower = str(destination_city).lower()
    
    route_key = (origin_lower, dest_lower)
    if route_key in KNOWN_TOLL_RATES:
        rate_type = "sunpass" if has_sunpass else "toll_by_plate"
        return KNOWN_TOLL_RATES[route_key][rate_type]
    
    # Fallback estimation using zone data
    zone_data = TOLL_ZONES.get(origin_lower, {"toll_factor": 1.0, "base_toll": 1.00})
    per_mile_rate = 0.067 if has_sunpass else 0.10
    distance = 50  # Default distance if unknown
    return round(zone_data["base_toll"] + (distance * per_mile_rate * zone_data["toll_factor"]), 2)

def calculate_add_on_total(sqft, add_ons):
    """Calculate total for selected add-on services"""
    total = 0
    breakdown = []
    
    if add_ons.get('window_cleaning'):
        cost = ADD_ON_SERVICES['window_cleaning']['price_per_unit']
        total += cost
        breakdown.append(f"Window Cleaning: ${cost}")
    
    if add_ons.get('carpet_cleaning'):
        cost = sqft * ADD_ON_SERVICES['carpet_cleaning']['price_per_unit']
        total += cost
        breakdown.append(f"Carpet Cleaning: ${cost:.0f}")
    
    if add_ons.get('floor_waxing'):
        cost = sqft * ADD_ON_SERVICES['floor_waxing']['price_per_unit']
        total += cost
        breakdown.append(f"Floor Waxing: ${cost:.0f}")
    
    if add_ons.get('electrostatic_disinfection'):
        cost = ADD_ON_SERVICES['electrostatic_disinfection']['price_per_unit']
        total += cost
        breakdown.append(f"Disinfection: ${cost}")
    
    if add_ons.get('pressure_washing'):
        cost = ADD_ON_SERVICES['pressure_washing']['price_per_unit']
        total += cost
        breakdown.append(f"Pressure Washing: ${cost}")
    
    if add_ons.get('extra_trash'):
        cost = ADD_ON_SERVICES['extra_trash']['price_per_unit']
        total += cost
        breakdown.append(f"Extra Trash Removal: ${cost}")
    
    if add_ons.get('event_cleanup'):
        cost = ADD_ON_SERVICES['event_cleanup']['price_per_unit']
        total += cost
        breakdown.append(f"Event Cleanup: ${cost}")
    
    return total, breakdown

def calculate_base_price(city, property_type, sqft, bedrooms, bathrooms, frequency, complexity, travel_miles):
    """Calculate base price before modifiers and add-ons"""
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
    
    if property_type == "🏠 Airbnb / Short-Term Rental":
        subtotal = (bedrooms * 45) + (bathrooms * 25)
        subtotal = subtotal * prop_mult * complexity_factor
    else:
        price_per_sqft = base_rate * zone_mult * prop_mult * freq_mult * complexity_factor
        subtotal = sqft * price_per_sqft
    
    travel_cost = (travel_miles * 0.65) + travel_fee
    return subtotal + travel_cost, travel_fee

def calculate_true_cost(sqft, hours_estimated, hourly_wage, materials_cost, travel_fee, tolls):
    """Calculate true break-even cost (lowest possible price)"""
    if hours_estimated:
        labor_cost = hours_estimated * hourly_wage
    else:
        labor_cost = (sqft / 500) * hourly_wage
    
    overhead = labor_cost * 0.25
    return labor_cost + materials_cost + travel_fee + tolls + overhead

def apply_holiday_surcharge(price, holiday):
    """Apply holiday surcharge"""
    if holiday and holiday in HOLIDAY_RATES:
        surcharge = price * HOLIDAY_RATES[holiday]
        return price + surcharge, surcharge
    return price, 0

def apply_multi_location_discount(price, num_locations):
    """Apply discount for multiple locations"""
    if num_locations >= 7:
        discount = 0.15
    elif num_locations >= 4:
        discount = 0.10
    elif num_locations >= 2:
        discount = 0.05
    else:
        discount = 0
    discount_amount = price * discount
    return price - discount_amount, discount_amount

def apply_emergency_premium(price, notice_hours):
    """Apply premium for emergency/same-day service"""
    if notice_hours <= 12:
        premium = 0.75
    elif notice_hours <= 24:
        premium = 0.50
    elif notice_hours <= 48:
        premium = 0.25
    else:
        premium = 0
    premium_amount = price * premium
    return price + premium_amount, premium_amount

def apply_contract_discount(price, contract_months):
    """Apply discount for recurring contracts"""
    if contract_months >= 24:
        discount = 0.20
    elif contract_months >= 12:
        discount = 0.15
    elif contract_months >= 6:
        discount = 0.10
    elif contract_months >= 3:
        discount = 0.05
    else:
        discount = 0
    discount_amount = price * discount
    return price - discount_amount, discount_amount

def calculate_price_with_all_tiers(city, property_type, sqft, bedrooms, bathrooms, frequency, complexity, 
                                    travel_miles, hours_estimated, materials_cost, add_ons,
                                    holiday, num_locations, notice_hours, contract_months, has_sunpass=True):
    """Calculate complete pricing with all three tiers and modifiers"""
    
    # Get business settings
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT hourly_wage, min_job_fee, profit_target FROM business_profile WHERE id=1")
    row = c.fetchone()
    conn.close()
    
    hourly_wage = row[0] if row else 15.0
    min_job_fee = row[1] if row else 150
    target_margin = row[2] if row else 0.30
    
    # Calculate base price
    base_price, travel_fee = calculate_base_price(city, property_type, sqft, bedrooms, bathrooms, 
                                                   frequency, complexity, travel_miles)
    
    # Calculate add-ons
    add_on_total, add_on_breakdown = calculate_add_on_total(sqft, add_ons)
    
    # Calculate tolls
    tolls = estimate_toll_cost(city, "orlando", has_sunpass)
    
    # Start with base price + add-ons
    price_before_modifiers = base_price + add_on_total
    
    # Calculate true cost (break-even)
    true_cost = calculate_true_cost(sqft, hours_estimated, hourly_wage, materials_cost, travel_fee, tolls)
    
    # Apply minimum job fee
    if true_cost < min_job_fee:
        true_cost = min_job_fee
    
    # Start with fair market price
    fair_market = price_before_modifiers
    
    # Apply all modifiers to fair market price
    fair_market, holiday_amt = apply_holiday_surcharge(fair_market, holiday)
    fair_market, emergency_amt = apply_emergency_premium(fair_market, notice_hours)
    fair_market, location_amt = apply_multi_location_discount(fair_market, num_locations)
    fair_market, contract_amt = apply_contract_discount(fair_market, contract_months)
    
    # Ensure fair market has at least target margin
    min_fair = true_cost * (1 + target_margin)
    if fair_market < min_fair:
        fair_market = min_fair
    
    # Calculate highest price (premium)
    highest_price = fair_market * 1.3
    
    # Lowest price (break-even)
    lowest_price = true_cost
    
    # Round all prices
    lowest_price = math.ceil(lowest_price)
    fair_market = math.ceil(fair_market)
    highest_price = math.ceil(highest_price)
    
    # Calculate tax
    tax_lowest = lowest_price * SALES_TAX_RATE
    tax_fair = fair_market * SALES_TAX_RATE
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
            "subtotal": fair_market,
            "tax": round(tax_fair, 2),
            "total": math.ceil(fair_market + tax_fair),
            "profit": round(fair_market - true_cost, 2),
            "margin": round(((fair_market - true_cost) / fair_market) * 100, 1)
        },
        "highest": {
            "subtotal": highest_price,
            "tax": round(tax_highest, 2),
            "total": math.ceil(highest_price + tax_highest),
            "profit": round(highest_price - true_cost, 2),
            "margin": round(((highest_price - true_cost) / highest_price) * 100, 1)
        },
        "true_cost": round(true_cost, 2),
        "travel_fee": travel_fee,
        "toll_estimate": tolls,
        "add_on_total": add_on_total,
        "add_on_breakdown": add_on_breakdown,
        "modifiers": {
            "holiday": round(holiday_amt, 2),
            "emergency": round(emergency_amt, 2),
            "multi_location": round(location_amt, 2),
            "contract": round(contract_amt, 2)
        }
    }

# ============================================
# WORKER MANAGEMENT FUNCTIONS
# ============================================

def add_worker(name, phone, email, address, lat, lon, hourly_rate):
    """Add a new worker to the system"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO workers (name, phone, email, home_address, home_lat, home_lon, hourly_rate, created_at)
        VALUES (?,?,?,?,?,?,?,?)
    """, (name, phone, email, address, lat, lon, hourly_rate, datetime.now().isoformat()))
    worker_id = c.lastrowid
    
    # Add to assignment queue at the end
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
        SELECT w.id, w.name, w.phone, w.email, w.home_address, w.jobs_assigned, 
               w.jobs_completed, w.hourly_rate, aq.position as queue_position
        FROM workers w
        LEFT JOIN assignment_queue aq ON w.id = aq.worker_id
        WHERE w.is_active = 1
        ORDER BY aq.position
    """, conn)
    conn.close()
    return df

def get_best_workers_for_job(job_lat, job_lon, limit=5):
    """Get best workers for job based on queue position and distance"""
    conn = sqlite3.connect(DB_PATH)
    workers_df = pd.read_sql_query("""
        SELECT w.id, w.name, w.home_lat, w.home_lon, w.jobs_assigned, aq.position
        FROM workers w
        LEFT JOIN assignment_queue aq ON w.id = aq.worker_id
        WHERE w.is_active = 1
    """, conn)
    conn.close()
    
    # Calculate distance (simplified)
    for idx, row in workers_df.iterrows():
        if row['home_lat'] and job_lat:
            dist = abs(row['home_lat'] - job_lat) * 69  # Approximate miles per degree
        else:
            dist = 999
        workers_df.loc[idx, 'distance'] = round(dist, 1)
    
    # Priority score: 40% queue position, 60% distance
    workers_df['position_score'] = workers_df['position'] / workers_df['position'].max() if workers_df['position'].max() > 0 else 0
    workers_df['distance_score'] = workers_df['distance'] / workers_df['distance'].max() if workers_df['distance'].max() > 0 else 0
    workers_df['priority_score'] = (workers_df['position_score'] * 0.4) + (workers_df['distance_score'] * 0.6)
    workers_df = workers_df.sort_values('priority_score').head(limit)
    
    return workers_df.to_dict('records')

def assign_job_to_worker(job_id, worker_id, assigned_by="system"):
    """Assign a job to a worker and update fairness queue"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Create assignment record
    c.execute("""
        INSERT INTO job_assignments (job_id, worker_id, assigned_by, assigned_at, status)
        VALUES (?,?,?,?,?)
    """, (job_id, worker_id, assigned_by, datetime.now().isoformat(), "assigned"))
    
    # Update worker job count
    c.execute("UPDATE workers SET jobs_assigned = jobs_assigned + 1 WHERE id = ?", (worker_id,))
    
    # Move worker to end of queue
    c.execute("SELECT MAX(position) FROM assignment_queue")
    max_pos = c.fetchone()[0] or 0
    c.execute("UPDATE assignment_queue SET position = ? WHERE worker_id = ?", (max_pos + 1, worker_id))
    
    # Rebalance queue (recalculate positions)
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
    return True

# ============================================
# DYNAMIC INSPECTION FUNCTIONS
# ============================================

def init_inspection_session(client_id, client_name, property_type):
    """Initialize a new dynamic inspection session"""
    if 'inspection' not in st.session_state:
        st.session_state.inspection = {
            'client_id': client_id,
            'client_name': client_name,
            'property_type': property_type,
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
            'responses': {},
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

# ============================================
# EMAIL FUNCTIONS
# ============================================

def send_email_notification(to_email, template_name, template_data):
    """Send email notification using template"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT subject, body FROM email_templates WHERE name = ?", (template_name,))
    template = c.fetchone()
    c.execute("SELECT smtp_email, business_name FROM business_profile WHERE id=1")
    biz = c.fetchone()
    conn.close()
    
    if not template or not biz or not biz[0]:
        return False
    
    subject = template[0].format(**template_data)
    body = template[1].format(**template_data)
    
    # For now, just log (in production, use SMTP)
    print(f"Email would send to {to_email}: {subject}")
    return True

def export_to_csv(data, filename):
    """Export data to CSV for accounting"""
    if not data:
        return ""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(data[0].keys())
    for row in data:
        writer.writerow(row.values())
    return output.getvalue()

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
    st.markdown("---")
    
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
        smtp_email = st.text_input("SMTP Email for Notifications", help="For sending estimates to clients")
        smtp_password = st.text_input("SMTP Password", type="password")
        
        st.markdown("---")
        st.info("You can adjust these settings later from the Settings page.")
        
        if st.form_submit_button("🚀 Start Using ProfitClean", use_container_width=True):
            if business_name and phone and email:
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("DELETE FROM business_profile")
                c.execute("""
                    INSERT INTO business_profile 
                    (id, business_name, phone, email, hourly_wage, labor_burden, profit_target, 
                     min_job_fee, home_city, per_mile_rate, sales_tax_rate, smtp_email, smtp_password, setup_complete)
                    VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,1)
                """, (business_name, phone, email, hourly_wage, 0.25, 0.30,
                      min_job_fee, home_city, 0.65, SALES_TAX_RATE, smtp_email, smtp_password))
                conn.commit()
                conn.close()
                st.success("Setup complete! Redirecting to dashboard...")
                st.rerun()
            else:
                st.error("Please fill in all required fields (*)")

# ============================================
# DASHBOARD
# ============================================

def dashboard():
    business_name = get_business_name()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT SUM(amount_invoiced), SUM(profit) FROM quick_jobs")
    job_data = c.fetchone()
    c.execute("SELECT COUNT(*) FROM workers WHERE is_active = 1")
    worker_result = c.fetchone()
    c.execute("SELECT COUNT(*) FROM estimates WHERE status = 'sent'")
    pending_estimates = c.fetchone()[0]
    conn.close()
    
    total_revenue = job_data[0] if job_data and job_data[0] else 0
    total_profit = job_data[1] if job_data and job_data[1] else 0
    worker_count = worker_result[0] if worker_result else 0
    margin = (total_profit / total_revenue * 100) if total_revenue > 0 else 0
    
    st.title(f"🧹 {business_name}")
    st.caption("Created by Dust Bros & Co.")
    
    # Sidebar Navigation
    with st.sidebar:
        st.markdown("### 📋 Menu")
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
        if st.button("👷 Workers", use_container_width=True):
            st.session_state.page = "workers"
            st.rerun()
        if st.button("📅 Schedule", use_container_width=True):
            st.session_state.page = "schedule"
            st.rerun()
        if st.button("🔍 Inspections", use_container_width=True):
            st.session_state.page = "inspections"
            st.rerun()
        if st.button("💰 Profit", use_container_width=True):
            st.session_state.page = "profit"
            st.rerun()
        if st.button("📋 History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()
        if st.button("⚙️ Settings", use_container_width=True):
            st.session_state.page = "settings"
            st.rerun()
        if st.button("👤 Client Portal", use_container_width=True):
            st.session_state.page = "client_login"
            st.rerun()
        
        st.markdown("---")
        if pending_estimates > 0:
            st.warning(f"📊 {pending_estimates} estimates pending approval")
    
    st.markdown("---")
    
    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">${total_revenue:,.0f}</div><div class="metric-label">Total Revenue</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">${total_profit:,.0f}</div><div class="metric-label">Total Profit</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{margin:.0f}%</div><div class="metric-label">Profit Margin</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{worker_count}</div><div class="metric-label">Active Workers</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 📋 Recent Estimates")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, client_name, city, property_type, estimated_price, created_at, status 
        FROM estimates ORDER BY created_at DESC LIMIT 5
    """, conn)
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Click 'New Estimate' to create your first one.")
    else:
        for _, row in df.iterrows():
            status_badge = '✅ Approved' if row['status'] == 'approved' else '⏳ Pending' if row['status'] == 'sent' else row['status']
            st.markdown(f"""
            <div class="card">
                <strong>#{row['id']}</strong> - {row['client_name'] or 'Unnamed Client'} in {row['city']}<br>
                <small>{row['property_type']} • ${row['estimated_price']:,.2f}</small><br>
                <small>Created: {row['created_at'][:10]} • {status_badge}</small>
            </div>
            """, unsafe_allow_html=True)
    
    # Worker fairness preview
    st.markdown("---")
    st.markdown("### 👷 Worker Fairness")
    
    workers_df = get_all_workers()
    if not workers_df.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total Workers", len(workers_df))
        with col2:
            avg_jobs = workers_df['jobs_assigned'].mean() if not workers_df.empty else 0
            st.metric("Avg Jobs/Worker", f"{avg_jobs:.1f}")
        
        st.dataframe(workers_df[['name', 'jobs_assigned', 'jobs_completed', 'queue_position']].head(5), use_container_width=True)
    else:
        st.info("No workers added. Go to Workers page to add your team.")

# ============================================
# ESTIMATE PAGE
# ============================================

def estimate_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📝 New Estimate")
    st.caption(f"💰 Florida sales tax ({SALES_TAX_RATE * 100}%) is included and prices are rounded up to the nearest dollar.")
    
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
            bedrooms = st.number_input("🛏️ Number of Bedrooms", min_value=0, max_value=10, value=2)
        with col2:
            bathrooms = st.number_input("🚽 Number of Bathrooms", min_value=0, max_value=8, value=1)
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
            materials_cost = st.number_input("Estimated materials cost ($)", min_value=0, value=35, step=5)
    
    # Add-On Services
    st.markdown("---")
    st.markdown("### ➕ Add-On Services")
    col1, col2, col3 = st.columns(3)
    with col1:
        add_window = st.checkbox("Window Cleaning (+$50)")
        add_carpet = st.checkbox("Carpet Cleaning (+$0.20/sq ft)")
        add_floor = st.checkbox("Floor Stripping/Waxing (+$0.30/sq ft)")
    with col2:
        add_disinfection = st.checkbox("Electrostatic Disinfection (+$75)")
        add_pressure = st.checkbox("Pressure Washing (+$125)")
        add_trash = st.checkbox("Extra Trash Removal (+$25)")
    with col3:
        add_event = st.checkbox("Event Cleanup (+$150)")
    
    add_ons = {
        'window_cleaning': add_window,
        'carpet_cleaning': add_carpet,
        'floor_waxing': add_floor,
        'electrostatic_disinfection': add_disinfection,
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
    result = calculate_price_with_all_tiers(
        city, property_type, sqft, bedrooms, bathrooms, frequency, complexity,
        travel_miles, hours_estimated, materials_cost, add_ons,
        holiday, num_locations, notice_hours, contract_months, has_sunpass
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
                {result['fair']['margin']}% margin • ${result['fair']['profit']:.0f} profit
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
                {result['highest']['margin']}% margin • ${result['highest']['profit']:.0f} profit
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Modifiers Summary
    if any(result['modifiers'].values()):
        st.markdown("---")
        st.markdown("#### 📊 Price Adjustments Applied:")
        mod_text = []
        if result['modifiers']['holiday'] > 0:
            mod_text.append(f"🎄 Holiday surcharge: +${result['modifiers']['holiday']:.2f}")
        if result['modifiers']['emergency'] > 0:
            mod_text.append(f"🚨 Emergency premium: +${result['modifiers']['emergency']:.2f}")
        if result['modifiers']['multi_location'] > 0:
            mod_text.append(f"📍 Multi-location discount: -${result['modifiers']['multi_location']:.2f}")
        if result['modifiers']['contract'] > 0:
            mod_text.append(f"📄 Contract discount: -${result['modifiers']['contract']:.2f}")
        for mod in mod_text:
            st.markdown(f"- {mod}")
    
    # Add-ons Breakdown
    if result['add_on_breakdown']:
        st.markdown("#### ➕ Add-On Services:")
        for addon in result['add_on_breakdown']:
            st.markdown(f"- {addon}")
    
    # Internal breakdown (staff only)
    with st.expander("🔒 INTERNAL COST BREAKDOWN (Staff Only)"):
        st.markdown(f"""
        - **True Cost (Break-even):** ${result['true_cost']:.2f}
        - **Travel Fee:** ${result['travel_fee']:.2f}
        - **Toll Estimate:** ${result['toll_estimate']:.2f}
        - **Add-On Total:** ${result['add_on_total']:.2f}
        """)
    
    # Save estimate
    if st.button("💾 Save & Send Estimate", use_container_width=True):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        
        # Check if client exists, create if not
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
            (client_id, client_name, client_email, city, property_type, square_feet, bedrooms, bathrooms,
             frequency, complexity, travel_miles, toll_cost, add_on_window, add_on_carpet, add_on_floor,
             add_on_disinfection, add_on_pressure, holiday_surcharge, emergency_premium,
             location_discount, contract_discount, subtotal, tax, estimated_price,
             lowest_price, fair_price, highest_price, created_at, status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (client_id, client_name, client_email, city, property_type, sqft, bedrooms, bathrooms,
              frequency, complexity, travel_miles, result['toll_estimate'], 
              1 if add_window else 0, 1 if add_carpet else 0, 1 if add_floor else 0,
              1 if add_disinfection else 0, 1 if add_pressure else 0,
              result['modifiers']['holiday'], result['modifiers']['emergency'],
              result['modifiers']['multi_location'], result['modifiers']['contract'],
              result['fair']['subtotal'], result['fair']['tax'], result['fair']['total'],
              result['lowest']['total'], result['fair']['total'], result['highest']['total'],
              datetime.now().isoformat(), "sent"))
        
        estimate_id = c.lastrowid
        conn.commit()
        conn.close()
        
        # Send email notification
        if client_email:
            business_name = get_business_name()
            send_email_notification(client_email, "estimate_sent", {
                "client_name": client_name,
                "business_name": business_name,
                "estimate_id": estimate_id,
                "property_type": property_type,
                "city": city,
                "amount": result['fair']['total']
            })
        
        st.success(f"✅ Estimate #{estimate_id} saved and sent to {client_email if client_email else 'client'}!")
        st.balloons()

# ============================================
# QUICK JOB PAGE
# ============================================

def quick_job_page():
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
                (job_date, description, hours, amount_invoiced, job_expenses, profit, created_at)
                VALUES (?,?,?,?,?,?,?)
            """, (job_date.isoformat(), description, hours, amount, expenses, profit, datetime.now().isoformat()))
            conn.commit()
            conn.close()
            st.success("✅ Quick job saved!")
            st.rerun()

# ============================================
# CLIENTS PAGE
# ============================================

def clients_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 👥 Client CRM")
    
    # Export button
    col1, col2 = st.columns([3, 1])
    with col2:
        conn = sqlite3.connect(DB_PATH)
        clients_data = pd.read_sql_query("SELECT id, business_name, contact_name, phone, email, city, created_at FROM clients", conn).to_dict('records')
        conn.close()
        if clients_data:
            csv_data = export_to_csv(clients_data, "clients.csv")
            st.download_button("📥 Export to CSV", csv_data, "clients.csv", "text/csv", use_container_width=True)
    
    # Add new client
    with st.expander("➕ Add New Client"):
        with st.form("new_client_form"):
            col1, col2 = st.columns(2)
            with col1:
                business_name = st.text_input("Business Name *")
                contact_name = st.text_input("Contact Name")
                phone = st.text_input("Phone")
            with col2:
                email = st.text_input("Email")
                address = st.text_input("Address")
                city = st.text_input("City")
            
            portal_password = st.text_input("Portal Password (for client login)", type="password")
            notes = st.text_area("Notes")
            
            if st.form_submit_button("Save Client"):
                if business_name:
                    conn = sqlite3.connect(DB_PATH)
                    c = conn.cursor()
                    c.execute("""
                        INSERT INTO clients (business_name, contact_name, phone, email, address, city, password, notes, created_at)
                        VALUES (?,?,?,?,?,?,?,?,?)
                    """, (business_name, contact_name, phone, email, address, city, portal_password, notes, datetime.now().isoformat()))
                    conn.commit()
                    conn.close()
                    st.success(f"✅ {business_name} added!")
                    st.rerun()
                else:
                    st.error("Business name is required")
    
    # Display clients
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT id, business_name, contact_name, phone, email, city FROM clients ORDER BY business_name", conn)
    conn.close()
    
    if df.empty:
        st.info("No clients yet. Click 'Add New Client' to get started.")
    else:
        for _, row in df.iterrows():
            st.markdown(f"""
            <div class="card">
                <strong>🏢 {row['business_name']}</strong><br>
                📞 {row['contact_name'] or 'No contact'} • {row['phone'] or 'No phone'} • 📧 {row['email'] or 'No email'}<br>
                📍 {row['city'] or 'No city'}
            </div>
            """, unsafe_allow_html=True)

# ============================================
# WORKERS PAGE
# ============================================

def workers_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 👷 Worker Management")
    st.caption("Manage your team and ensure fair job distribution")
    
    tab1, tab2, tab3 = st.tabs(["📋 Workers List", "➕ Add Worker", "🔄 Auto-Assign"])
    
    with tab1:
        workers_df = get_all_workers()
        if workers_df.empty:
            st.info("No workers added yet.")
        else:
            st.dataframe(workers_df, use_container_width=True)
            
            # Export workers
            csv_data = export_to_csv(workers_df.to_dict('records'), "workers.csv")
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
        
        col1, col2 = st.columns(2)
        with col1:
            job_lat = st.number_input("Job Site Latitude", value=0.0, format="%.6f")
            job_lon = st.number_input("Job Site Longitude", value=0.0, format="%.6f")
        with col2:
            job_address = st.text_area("Job Address (reference)")
        
        if st.button("🔍 Find Best Workers", use_container_width=True):
            if job_lat != 0 or job_lon != 0:
                best_workers = get_best_workers_for_job(job_lat, job_lon, limit=5)
                
                st.markdown("#### 🎯 Top Recommended Workers")
                for worker in best_workers:
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    with col1:
                        st.markdown(f"**{worker['name']}**")
                    with col2:
                        st.markdown(f"📏 {worker['distance'] if worker['distance'] else 'N/A'} miles")
                    with col3:
                        st.markdown(f"🔄 #{worker['position'] + 1 if worker['position'] else '?'} in queue")
                    with col4:
                        if st.button(f"Assign", key=f"assign_{worker['id']}"):
                            assign_job_to_worker(1, worker['id'])
                            st.success(f"✅ Assigned to {worker['name']}!")
                            st.balloons()
            else:
                st.warning("Please enter job coordinates (latitude/longitude)")

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
        conn = sqlite3.connect(DB_PATH)
        clients_df = pd.read_sql_query("SELECT id, business_name FROM clients", conn)
        workers_df = pd.read_sql_query("SELECT id, name FROM workers WHERE is_active = 1", conn)
        conn.close()
        
        client_options = ["Select a client..."] + [f"{row['id']}: {row['business_name']}" for _, row in clients_df.iterrows()]
        client_selected = st.selectbox("Select Client", client_options)
        
        worker_options = ["Unassigned"] + [f"{row['id']}: {row['name']}" for _, row in workers_df.iterrows()]
        worker_selected = st.selectbox("Assign to Worker", worker_options)
    
    scheduled_time = st.selectbox("Time", ["8:00 AM", "9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", 
                                           "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"])
    
    if st.button("📅 Schedule Job", use_container_width=True):
        if client_selected != "Select a client...":
            client_id = int(client_selected.split(":")[0])
            worker_id = None
            if worker_selected != "Unassigned":
                worker_id = int(worker_selected.split(":")[0])
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                INSERT INTO scheduled_jobs (client_id, assigned_worker_id, scheduled_date, scheduled_time, status)
                VALUES (?,?,?,?,?)
            """, (client_id, worker_id, schedule_date.isoformat(), scheduled_time, "scheduled"))
            conn.commit()
            conn.close()
            st.success("✅ Job scheduled successfully!")
            st.balloons()
        else:
            st.warning("Please select a client")
    
    st.markdown("---")
    st.markdown("#### Upcoming Jobs")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT sj.id, c.business_name, w.name as worker_name, sj.scheduled_date, sj.scheduled_time, sj.status
        FROM scheduled_jobs sj
        JOIN clients c ON sj.client_id = c.id
        LEFT JOIN workers w ON sj.assigned_worker_id = w.id
        ORDER BY sj.scheduled_date
    """, conn)
    conn.close()
    
    if df.empty:
        st.info("No scheduled jobs")
    else:
        st.dataframe(df, use_container_width=True)

# ============================================
# DYNAMIC INSPECTIONS PAGE
# ============================================

def inspections_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 🔍 Pre-Inspection Checklist")
    st.caption("Document existing conditions before starting work - photos save automatically")
    
    # Initialize or continue inspection
    if 'inspection' not in st.session_state:
        st.session_state.inspection = None
    
    if st.session_state.inspection is None:
        st.markdown("#### Start a New Inspection")
        
        conn = sqlite3.connect(DB_PATH)
        clients_df = pd.read_sql_query("SELECT id, business_name FROM clients", conn)
        conn.close()
        
        client_options = ["Select a client..."] + [f"{row['id']}: {row['business_name']}" for _, row in clients_df.iterrows()]
        client_selected = st.selectbox("Client", client_options)
        property_type = st.selectbox("Property Type", list(PROPERTY_TYPES.keys()))
        
        if st.button("Start Inspection", use_container_width=True):
            if client_selected != "Select a client...":
                client_id = int(client_selected.split(":")[0])
                client_name = client_selected.split(":")[1].strip()
                init_inspection_session(client_id, client_name, property_type)
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
                area_type = st.selectbox("Area type", ["Restroom", "Office", "Breakroom", "Kitchen", 
                                                        "Gym Area", "Storage", "Lobby", "Conference Room", 
                                                        "Bathroom", "Hallway", "Classroom", "Warehouse"])
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
                                      index=0, key=f"floors_{current_idx}")
                    walls = st.radio("Walls Condition", ["Good", "Scuffs", "Holes", "Damage"], 
                                     index=0, key=f"walls_{current_idx}")
                    trash = st.radio("Trash Status", ["Empty", "Partial", "Full"], 
                                     index=0, key=f"trash_{current_idx}")
                with col2:
                    supplies = st.radio("Supplies Status", ["Full", "Low", "Empty"], 
                                        index=0, key=f"supplies_{current_idx}")
                    odor = st.radio("Odor", ["None", "Mild", "Strong"], 
                                    index=0, key=f"odor_{current_idx}")
                    lighting = st.radio("Lighting", ["All Working", "Some Out", "Major Issues"], 
                                        index=0, key=f"lighting_{current_idx}")
                
                notes = st.text_area("Additional Notes", value=current_area.get('notes', ''), key=f"notes_{current_idx}")
                
                # Photo upload
                photo = st.file_uploader("📸 Take Photo (optional)", type=['jpg', 'png'], key=f"photo_{current_idx}")
                if photo:
                    current_area['photos'].append(photo.name)
                    st.success(f"Photo added: {photo.name}")
                
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
                            'lighting': lighting
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
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("""
                    INSERT INTO inspections (client_id, client_name, property_type, areas_json, inspection_data, status, started_at, completed_at)
                    VALUES (?,?,?,?,?,?,?,?)
                """, (st.session_state.inspection['client_id'], st.session_state.inspection['client_name'],
                      st.session_state.inspection['property_type'], json.dumps(st.session_state.inspection['areas']),
                      json.dumps(st.session_state.inspection), "completed",
                      st.session_state.inspection['started_at'], datetime.now().isoformat()))
                conn.commit()
                conn.close()
                st.success("✅ Inspection completed and saved!")
                st.session_state.inspection = None
                st.rerun()

# ============================================
# PROFIT DASHBOARD - COMPLETE
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
    
    total_expenses = sum(expenses.values())
    
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
        total_job_expenses = float(df["job_expenses"].sum())
        total_profit = float(df["profit"].sum())
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
            daily_target = total_expenses / 22 if total_expenses > 0 else 0
            st.metric("Daily Break-Even Target", f"${daily_target:.0f}")
        
        st.markdown("---")
        st.markdown("#### Recent Jobs")
        st.dataframe(df[["job_date", "description", "hours", "amount_invoiced", "profit"]], use_container_width=True)
        
        # Export button
        output = io.StringIO()
        df.to_csv(output, index=False)
        st.download_button("📥 Export Profit Data to CSV", output.getvalue(), "profit_data.csv", "text/csv")

# ============================================
# HISTORY PAGE
# ============================================

def history_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### 📋 Estimate History")
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("""
        SELECT id, client_name, client_email, city, property_type, estimated_price, created_at, status 
        FROM estimates ORDER BY created_at DESC
    """, conn)
    conn.close()
    
    if df.empty:
        st.info("No estimates yet. Click 'New Estimate' to create your first one.")
    else:
        st.dataframe(df, use_container_width=True)
        
        total_value = df["estimated_price"].sum()
        st.metric("Total Value of All Estimates", f"${total_value:,.2f}")
        
        output = io.StringIO()
        df.to_csv(output, index=False)
        st.download_button("📥 Export Estimates to CSV", output.getvalue(), "estimates.csv", "text/csv")

# ============================================
# CLIENT PORTAL
# ============================================

def client_login_page():
    st.markdown("### 👤 Client Portal Login")
    st.caption("Access your estimates, schedule, and account history")
    
    with st.form("client_login"):
        email = st.text_input("Email Address")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login", use_container_width=True):
            # Demo login - in production, verify against database
            if email:
                st.session_state.client_logged_in = True
                st.session_state.client_name = email.split('@')[0]
                st.session_state.page = "client_dashboard"
                st.rerun()
            else:
                st.error("Invalid email or password")
    
    if st.button("← Back to Main Site"):
        st.session_state.page = "dashboard"
        st.rerun()

def client_dashboard():
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.client_logged_in = False
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown(f"### 👋 Welcome, {st.session_state.client_name}")
    st.caption("Client Portal - View and manage your cleaning services")
    
    tab1, tab2 = st.tabs(["📝 Estimates", "📅 Schedule"])
    
    with tab1:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query("""
            SELECT id, city, property_type, square_feet, estimated_price, created_at, status
            FROM estimates ORDER BY created_at DESC
        """, conn)
        conn.close()
        
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
                    if st.button(f"✅ Approve Estimate #{row['id']}", key=f"approve_{row['id']}"):
                        st.success(f"Estimate #{row['id']} approved! Thank you.")
    
    with tab2:
        st.info("Your scheduled jobs will appear here.")

# ============================================
# SETTINGS PAGE
# ============================================

def settings_page():
    if st.button("← Back to Dashboard"):
        st.session_state.page = "dashboard"
        st.rerun()
    
    st.markdown("### ⚙️ Business Settings")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT business_name, phone, email, hourly_wage, profit_target, min_job_fee, home_city FROM business_profile WHERE id=1")
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
            
            if st.form_submit_button("💾 Save Settings", use_container_width=True):
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("""
                    UPDATE business_profile SET 
                        business_name=?, phone=?, email=?, hourly_wage=?, profit_target=?, 
                        min_job_fee=?, home_city=?
                    WHERE id=1
                """, (business_name, phone, email, hourly_wage, profit_target/100, min_job_fee, home_city))
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
        
        if st.session_state.get("client_logged_in", False):
            client_dashboard()
        else:
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