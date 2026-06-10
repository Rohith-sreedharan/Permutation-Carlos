#!/usr/bin/env python3
import requests

BASE = "http://localhost:8000"
resp = requests.get(f"{BASE}/api/odds/list?upcoming_only=true&limit=10", timeout=20)
print("status", resp.status_code)
if resp.status_code != 200:
    print(resp.text[:400])
    raise SystemExit(1)
obj = resp.json()
events = obj.get("events", []) if isinstance(obj, dict) else obj
print("count", len(events))
for i, ev in enumerate(events[:8]):
    print(i, {
        "id": ev.get("id"),
        "event_id": ev.get("event_id"),
        "away": ev.get("away_team"),
        "home": ev.get("home_team"),
    })
