import os

DB_PATH = os.path.join(os.path.dirname(__file__), "profitclean.db")

# ============================================================
# SECURITY CONFIGURATION
# ============================================================

MIN_PASSWORD_LENGTH = 8
MAX_LOGIN_ATTEMPTS = 5
ACCOUNT_LOCKOUT_MINUTES = 30
SESSION_EXPIRY_DAYS = 7
SALES_TAX_RATE = 0.06
MAX_RESET_CODE_ATTEMPTS = 5

BACKUP_DIR = os.path.join(os.path.expanduser("~"), "ProfitClean_Backups")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(BACKUP_DIR, exist_ok=True)

AVAILABLE_INTEGRATIONS = {
    "calendly": {
        "name": "Calendly",
        "icon": "📅",
        "description": "Auto-import booking details from Calendly",
        "free": True,
        "requires_oauth": True
    },
    "acuity": {
        "name": "Acuity Scheduling",
        "icon": "📆",
        "description": "Sync appointments from Acuity",
        "free": True,
        "requires_oauth": True
    },
    "google_calendar": {
        "name": "Google Calendar",
        "icon": "📅",
        "description": "Two-way calendar sync",
        "free": True,
        "requires_oauth": True
    },
    "stripe": {
        "name": "Stripe",
        "icon": "💳",
        "description": "Process payments & invoices",
        "free": False,
        "requires_oauth": True
    }
}

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
