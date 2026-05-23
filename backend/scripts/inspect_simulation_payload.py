import os
#!/usr/bin/env python3
import random
import requests

BASE = "http://localhost:8000"
EVENT_ID = "107fec52e1d9d6f2f6e74f47eb1d520b"

email = f"siminspect_{random.randint(1000,9999)}@example.com"
password = os.getenv("PROOF_PASS", "")
requests.post(
    f"{BASE}/api/auth/register",
    json={"email": email, "username": email.split("@")[0], "password": password},
    timeout=10,
)
login = requests.post(
    f"{BASE}/api/token",
    headers={"Content-Type": "application/x-www-form-urlencoded"},
    data={"username": email, "password": password},
    timeout=10,
)
token = login.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

resp = requests.get(f"{BASE}/api/simulations/{EVENT_ID}", headers=headers, timeout=20)
print("status", resp.status_code)
data = resp.json()
print("keys", sorted(data.keys())[:40])
print("has_event", "event" in data and isinstance(data.get("event"), dict))
print("home", data.get("home_team"), "away", data.get("away_team"))
print("teams", data.get("team_a"), data.get("team_b"))
print("metadata_keys", sorted((data.get("metadata") or {}).keys()))
