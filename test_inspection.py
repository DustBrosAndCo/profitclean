"""Tests for pre-inspection estimate calculator and backup restore helpers."""
import os
import sys
import json
import tempfile
import sqlite3
from unittest.mock import MagicMock


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

TEST_DB = os.path.join(tempfile.gettempdir(), "profitclean_test_inspection.db")
if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

import app  # noqa: E402

app.DB_PATH = TEST_DB
app.init_db()
app.migrate_database()

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


def sample_inspection_data(**overrides):
    data = {
        "property_type": "Office",
        "square_feet": 2000,
        "num_floors": 1,
        "has_elevator": True,
        "num_buildings": 1,
        "frequency": "Weekly",
        "access_time": "Normal business hours",
        "areas": {
            "reception": True,
            "private_offices": 5,
            "open_workstations": 0,
            "conference_rooms": 2,
            "breakroom": True,
            "hallways": True,
            "stairwells": 0,
            "storage_rooms": 0,
            "loading_dock": False,
            "exterior_entry": False,
            "trash": True,
        },
        "windows": {
            "interior": 10,
            "exterior": 0,
            "high": 0,
            "glass_doors": 2,
            "partitions": 0,
            "mirrors": 0,
            "tracks": False,
            "screens": False,
        },
        "restrooms": {
            "toilets": 4,
            "urinals": 0,
            "sinks": 4,
            "mirrors": 4,
            "showers": 0,
            "count": 2,
            "deep_clean": False,
            "restock": False,
        },
        "floors": {
            "carpet_sqft": 500,
            "tile_sqft": 300,
            "vinyl_sqft": 0,
            "hardwood_sqft": 0,
            "concrete_sqft": 0,
            "condition": "Good",
            "carpet_extract": False,
            "strip_wax": False,
            "buff": False,
        },
        "furniture": {
            "desks": 10,
            "computers": 10,
            "phones": 5,
            "chairs": 10,
            "tables": 2,
            "whiteboards": 1,
            "appliances": 1,
            "equipment": 0,
            "move_light": 0,
            "move_heavy": 0,
            "clean_under": False,
        },
        "special": {
            "high_dusting": False,
            "blinds": 0,
            "disinfection": False,
            "odor_control": False,
            "post_construction": False,
            "emergency": False,
            "holiday": "No",
            "supply_provided": False,
            "complexity": 3,
        },
    }
    data.update(overrides)
    return data


print("\n=== Pre-Inspection & Backup Tests ===\n")

result = app.calculate_inspection_estimate(sample_inspection_data())
check("estimate returns required keys", all(k in result for k in ("final_price", "base_price", "adjustments", "confidence")))
check("final price >= minimum", result["final_price"] >= 150, f"got {result['final_price']}")
check("final price rounded to $25", result["final_price"] % 25 == 0, f"got {result['final_price']}")

emergency = app.calculate_inspection_estimate(
    sample_inspection_data(special={**sample_inspection_data()["special"], "emergency": True})
)
base = app.calculate_inspection_estimate(sample_inspection_data())
check("emergency increases price", emergency["final_price"] > base["final_price"])

# Company + user for backup restore
ok, uid = app.create_user("inspuser", "insp@test.com", "TestPass1!", role="admin", company_id=1)
st_mock.session_state.user = {"user_id": uid, "username": "inspuser", "role": "admin", "company_id": 1}

cid = app.add_client("Test Co", "Bob", "555", "bob@test.com", "1 St", "Orlando", "FL", "32801", 0, 0, "")
check("client created for backup test", cid is not None)

backup = {
    "version": "3.0",
    "user_id": uid,
    "company_id": 1,
    "data": {
        "clients": [],
        "estimates": [],
        "quick_jobs": [],
        "monthly_expenses": [],
        "scheduled_jobs": [],
        "inspections": [],
        "supplies": [],
        "team_messages": [],
        "support_tickets": [],
    },
}
app.restore_personal_backup_data(backup)
conn = sqlite3.connect(TEST_DB)
c = conn.cursor()
c.execute("SELECT COUNT(*) FROM clients WHERE company_id = 1 AND user_id = ?", (uid,))
client_count = c.fetchone()[0]
conn.close()
check("personal restore clears scoped clients", client_count == 0, f"count={client_count}")

# Save inspection row
conn = sqlite3.connect(TEST_DB)
c = conn.cursor()
c.execute(
    """INSERT INTO inspections (company_id, user_id, client_name, areas_json, inspection_data, status, started_at, completed_at)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
    (1, uid, "Walk-in", json.dumps(sample_inspection_data()), json.dumps(result), "completed", "2025-01-01", "2025-01-01"),
)
conn.commit()
c.execute("SELECT COUNT(*) FROM inspections WHERE user_id = ?", (uid,))
insp_count = c.fetchone()[0]
conn.close()
check("inspection row inserts", insp_count == 1, f"count={insp_count}")

if os.path.exists(TEST_DB):
    os.remove(TEST_DB)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
if failed:
    for e in errors:
        print(e)
    sys.exit(1)
sys.exit(0)
