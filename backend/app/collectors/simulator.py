"""
Metadata Collector (simulated / historical demo mode).

Generates 30 days of realistic, privacy-preserving behavioural metadata
for a set of employees — login times, device info, USB activity, file
copy counts/sizes, upload destinations, process usage, network volume,
geo-location, and privilege-escalation events — with 3 employees
secretly seeded with real insider-threat patterns so the detection
pipeline has genuine ground truth to catch.

Never generates or touches actual file contents — only metadata.
"""
import random
from datetime import datetime, timedelta

random.seed(42)

DEPARTMENTS = ["Engineering", "Finance", "Sales", "HR", "Legal"]
DESTINATIONS_NORMAL = ["corp-sharepoint", "corp-drive", "internal-wiki", "team-s3-bucket"]
DESTINATIONS_RISKY = ["personal-gdrive", "personal-dropbox", "unknown-cloud", "personal-email"]
GEOS_HOME = ["Nagpur", "Mumbai", "Pune"]
GEOS_UNUSUAL = ["Lagos", "Bucharest", "Manila", "unknown-vpn-exit"]

NUM_EMPLOYEES = 20
NUM_DAYS = 30
START_DATE = datetime(2026, 8, 1)

# Employees secretly given an insider-threat behavioural pattern, used
# purely to sanity-check the detection pipeline's recall in pipeline.py
SEEDED_SCENARIOS = {
    "EMP003": "slow_drip",         # gradually escalating small exfiltration
    "EMP008": "resignation_dump",  # short burst of mass USB copying before departure
    "EMP014": "offhours_bulk",     # single large off-hours bulk upload to a personal account
}


def _make_employees():
    return [
        {"id": f"EMP{str(i).zfill(3)}", "name": f"Employee {i}", "department": random.choice(DEPARTMENTS)}
        for i in range(1, NUM_EMPLOYEES + 1)
    ]


def _normal_day_events(emp_id: str, day: datetime) -> list[dict]:
    events = []
    login_hour = random.gauss(9, 0.6)
    login_time = day.replace(hour=max(6, min(11, int(login_hour))), minute=random.randint(0, 59))
    events.append({
        "employee_id": emp_id, "event_type": "login", "timestamp": login_time,
        "payload": {"device_known": True, "geo_city": random.choice(GEOS_HOME)},
    })
    events.append({
        "employee_id": emp_id, "event_type": "usb", "timestamp": login_time + timedelta(hours=2),
        "payload": {"usb_events": random.choice([0, 0, 0, 1])},
    })
    n_uploads = random.randint(0, 3)
    for _ in range(n_uploads):
        events.append({
            "employee_id": emp_id, "event_type": "upload",
            "timestamp": day.replace(hour=random.randint(9, 17), minute=random.randint(0, 59)),
            "payload": {
                "size_mb": round(random.uniform(0.5, 15), 2),
                "destination": random.choice(DESTINATIONS_NORMAL),
                "file_count": random.randint(1, 3),
            },
        })
    events.append({
        "employee_id": emp_id, "event_type": "process", "timestamp": day.replace(hour=10),
        "payload": {"process_count": random.randint(15, 40), "new_process_count": random.randint(0, 5)},
    })
    events.append({
        "employee_id": emp_id, "event_type": "network", "timestamp": day.replace(hour=14),
        "payload": {"network_mb": round(random.uniform(20, 200), 1), "session_minutes": random.randint(300, 540)},
    })
    if random.random() < 0.02:
        events.append({
            "employee_id": emp_id, "event_type": "privilege", "timestamp": day.replace(hour=11),
            "payload": {"escalation": True},
        })
    return events


def _scenario_day_events(emp_id: str, day: datetime, day_index: int, scenario: str) -> list[dict]:
    events = _normal_day_events(emp_id, day)

    if scenario == "slow_drip" and day_index >= 15:
        # Gradually escalating small exfiltration to a personal account,
        # split into several small transfers to stay under naive thresholds.
        ramp = (day_index - 15) / 14.0
        for _ in range(random.randint(2, 4)):
            events.append({
                "employee_id": emp_id, "event_type": "upload",
                "timestamp": day.replace(hour=random.choice([12, 13, 20, 21]), minute=random.randint(0, 59)),
                "payload": {
                    "size_mb": round(5 + ramp * 40 + random.uniform(-2, 2), 2),
                    "destination": random.choice(DESTINATIONS_RISKY),
                    "file_count": random.randint(3, 8),
                },
            })

    elif scenario == "resignation_dump" and day_index in (26, 27, 28):
        events.append({
            "employee_id": emp_id, "event_type": "usb", "timestamp": day.replace(hour=19),
            "payload": {"usb_events": random.randint(6, 12)},
        })
        events.append({
            "employee_id": emp_id, "event_type": "upload", "timestamp": day.replace(hour=19, minute=30),
            "payload": {"size_mb": round(random.uniform(300, 900), 1), "destination": "usb-mass-storage",
                        "file_count": random.randint(50, 200)},
        })

    elif scenario == "offhours_bulk" and day_index == 20:
        events.append({
            "employee_id": emp_id, "event_type": "login", "timestamp": day.replace(hour=23, minute=40),
            "payload": {"device_known": True, "geo_city": random.choice(GEOS_UNUSUAL)},
        })
        events.append({
            "employee_id": emp_id, "event_type": "upload", "timestamp": day.replace(hour=23, minute=55),
            "payload": {"size_mb": round(random.uniform(500, 1200), 1), "destination": "personal-gdrive",
                        "file_count": random.randint(100, 400)},
        })
        events.append({
            "employee_id": emp_id, "event_type": "network", "timestamp": day.replace(hour=23, minute=50),
            "payload": {"network_mb": round(random.uniform(500, 1200), 1), "session_minutes": 45},
        })

    return events


def generate_dataset() -> tuple[list[dict], list[dict]]:
    """Returns (employees, events) for the full 30-day / 20-employee
    simulated organisation."""
    employees = _make_employees()
    events = []
    for emp in employees:
        scenario = SEEDED_SCENARIOS.get(emp["id"])
        for d in range(NUM_DAYS):
            day = START_DATE + timedelta(days=d)
            if scenario:
                events.extend(_scenario_day_events(emp["id"], day, d, scenario))
            else:
                events.extend(_normal_day_events(emp["id"], day))
    return employees, events
