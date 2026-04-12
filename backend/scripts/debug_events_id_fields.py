#!/usr/bin/env python3
import random
import requests

BASE = "http://localhost:8000"

email = f"idcheck_{random.randint(1000,9999)}@example.com"
password = "ProofPass123!"
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
token = login.json().get("access_token")
headers = {"Authorization": f"Bearer {token}"}

resp = requests.get(f"{BASE}/api/events?limit=20", headers=headers, timeout=20)
print("status", resp.status_code)
if resp.status_code != 200:
    print(resp.text[:400])
    raise SystemExit(1)

data = resp.json()
print("count", len(data))
for i, ev in enumerate(data[:8]):
    print(i, {
        "id": ev.get("id"),
        "event_id": ev.get("event_id"),
        "away": ev.get("away_team"),
        "home": ev.get("home_team"),
        "sport_key": ev.get("sport_key"),
    })
