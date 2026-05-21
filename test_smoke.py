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

# Distance calculation
d = app.calculate_distance(28.5383, -81.3792, 25.7617, -80.1918)
check("Orlando-Miami distance ~235mi", 200 < d < 270, f"got {d:.1f}")

# Pricing tiers
result = app.calculate_price_with_tiers(
    city="Orlando",
    property_type="Office Standard",
    sqft=2000,
    bedrooms=0,
    bathrooms=0,
    frequency="Weekly",
    complexity=5,
    travel_miles=10,
    add_ons={},
    holiday="None",
    num_locations=1,
    notice_hours=72,
    contract_months=0,
)
check("pricing returns tiers", all(k in result for k in ("lowest", "fair", "highest")))
check("fair >= lowest", result["fair"]["subtotal"] >= result["lowest"]["subtotal"])
check("highest >= fair", result["highest"]["subtotal"] >= result["fair"]["subtotal"])
check("fair total has tax", result["fair"]["total"] > result["fair"]["subtotal"])

# Smart task list
tasks = app.generate_smart_task_list("Office Standard", 1500, 5)
check("task list non-empty", len(tasks) > 0)

duration = app.generate_cleaning_duration(1500, "Office Standard", 5)
check("duration positive", duration > 0)

# QR code generation
qr = app.generate_qr_code("test-data-123")
check("QR returns data URI", isinstance(qr, str) and qr.startswith("data:image/png;base64,"))

# Database init + user creation
ok, uid = app.create_user("testuser", "test_smoke@example.com", "TestPass1!", role="admin")
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
