"""Smoke tests for ProfitClean core logic (no Streamlit UI)."""
import os
import sys
import tempfile
import shutil
from unittest.mock import MagicMock

# Mock streamlit before importing app (session_state needs attr access like Streamlit)
class SessionState(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            raise AttributeError(key)

    def __setattr__(self, key, value):
        self[key] = value

st_mock = MagicMock()
st_mock.session_state = SessionState()
sys.modules["streamlit"] = st_mock

# Use isolated test database
TEST_DB = os.path.join(tempfile.gettempdir(), "profitclean_test_smoke.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

import app  # noqa: E402

app.DB_PATH = TEST_DB
app.init_db()

passed = 0
failed = 0
errors = []


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  PASS  {name}")
    else:
        failed += 1
        msg = f"  FAIL  {name}" + (f": {detail}" if detail else "")
        print(msg)
        errors.append(msg)


print("\n=== ProfitClean Smoke Tests ===\n")

# Password security
ok, msg = app.validate_password_strength("weak")
check("weak password rejected", not ok)

ok, msg = app.validate_password_strength("Strong1!")
check("strong password accepted", ok)

h, _ = app.hash_password("TestPass1!")
check("password hash verifies", app.verify_password("TestPass1!", h))
check("wrong password fails", not app.verify_password("WrongPass1!", h))

# Toll estimation
check("Orlando-Miami toll", app.estimate_toll_cost("Orlando", "Miami") == 17.0)
check("unknown route default", app.estimate_toll_cost("Unknown", "City") == 5.0)

# Test company for pricing and user tests
conn = __import__("sqlite3").connect(TEST_DB)
c = conn.cursor()
c.execute("INSERT INTO companies (name, subdomain, created_at, is_active) VALUES (?,?,?,?)",
          ("Test Co", "testco", app.datetime.now().isoformat(), 1))
company_id = c.lastrowid
conn.commit()
conn.close()

# Pricing tiers
result = app.calculate_price_with_tiers(
    "Orlando",
    "Office Standard",
    2000,
    0,
    0,
    "Weekly",
    5,
    10,
    {},
    "None",
    1,
    72,
    0,
    company_id=company_id,
)
check("pricing returns tiers", all(k in result for k in ("lowest", "fair", "highest")))
check("fair >= lowest", result["fair"]["subtotal"] >= result["lowest"]["subtotal"])
check("highest >= fair", result["highest"]["subtotal"] >= result["fair"]["subtotal"])
check("fair total has tax", result["fair"]["total"] > result["fair"]["subtotal"])

# Pre-inspection ballpark estimate
insp = app.calculate_inspection_estimate({
    "property_type": "Office",
    "square_feet": 2000,
    "num_floors": 1,
    "has_elevator": True,
    "num_buildings": 1,
    "frequency": "Weekly",
    "access_time": "Normal business hours",
    "areas": {"reception": True, "private_offices": 0, "open_workstations": 0, "conference_rooms": 0,
              "breakroom": False, "hallways": False, "stairwells": 0, "storage_rooms": 0,
              "loading_dock": False, "exterior_entry": False, "trash": False},
    "windows": {"interior": 0, "exterior": 0, "high": 0, "glass_doors": 0, "partitions": 0,
                "mirrors": 0, "tracks": False, "screens": False},
    "restrooms": {"toilets": 0, "urinals": 0, "sinks": 0, "mirrors": 0, "showers": 0,
                  "count": 0, "deep_clean": False, "restock": False},
    "floors": {"carpet_sqft": 0, "tile_sqft": 0, "vinyl_sqft": 0, "hardwood_sqft": 0,
               "concrete_sqft": 0, "condition": "Good", "carpet_extract": False, "strip_wax": False, "buff": False},
    "furniture": {"desks": 0, "computers": 0, "phones": 0, "chairs": 0, "tables": 0,
                  "whiteboards": 0, "appliances": 0, "equipment": 0, "move_light": 0, "move_heavy": 0, "clean_under": False},
    "special": {"high_dusting": False, "blinds": 0, "disinfection": False, "odor_control": False,
                "post_construction": False, "emergency": False, "holiday": "No", "supply_provided": False, "complexity": 3},
})
check("inspection estimate minimum", insp["final_price"] >= 150)

ok, uid = app.create_user("testuser", "test_smoke@example.com", "TestPass1!", role="admin", company_id=company_id)
check("create_user succeeds", ok and uid is not None)

ok2, data = app.authenticate_user("test_smoke@example.com", "TestPass1!")
check("authenticate succeeds", ok2 and data.get("username") == "testuser")

ok3, _ = app.authenticate_user("test_smoke@example.com", "WrongPass1!")
check("bad password rejected", not ok3)

st_mock.session_state.user = {"user_id": uid, "username": "testuser", "role": "admin"}

# Client CRUD
cid = app.add_client(
    "Acme Corp", "Jane Doe", "555-0100", "jane@acme.com",
    "123 Main St", "Orlando", "FL", "32801", 28.5, -81.3, "notes"
)
check("add_client returns id", cid is not None and cid > 0)

clients = app.get_all_clients()
check("client in list", not clients.empty)

# Cleanup
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
if failed:
    for e in errors:
        print(e)
    sys.exit(1)
sys.exit(0)
