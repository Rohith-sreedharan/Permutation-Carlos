import json
import subprocess
from collections import Counter

token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiI2OWZhYTIyNjZlZThmZDMyYWUxNTJiMzEiLCJlbWFpbCI6ImJlYXR2ZWdhc2FwcEBnbWFpbC5jb20iLCJ0aWVyIjoicGxhdGZvcm0iLCJpYXQiOjE3ODIwMzI2MzUsImV4cCI6MTc4MjExOTAzNX0.GmBaojugKYdd8RPwaZ0TQ5202AMYLPUWr2_T80I-5Ng"

proc = subprocess.run([
    "curl", "-sS", "http://localhost:8000/api/odds/list?date=2026-06-21&upcoming_only=false&limit=200"
], capture_output=True, text=True, check=True)
raw = json.loads(proc.stdout)
events = raw if isinstance(raw, list) else raw.get("events", [])

counts = Counter()
rows = []

for ev in events:
    event_id = ev.get("event_id")
    sport = ev.get("sport_key", "")
    league = "MLB" if "mlb" in sport.lower() else "NBA"
    if not event_id:
        continue

    dproc = subprocess.run([
        "curl", "-sS", f"http://localhost:8000/api/games/{league}/{event_id}/decisions",
        "-H", "Authorization: Bearer " + token
    ], capture_output=True, text=True)

    if dproc.returncode != 0 or not dproc.stdout.strip():
        continue

    try:
        dec = json.loads(dproc.stdout)
    except Exception:
        continue

    cls_values = []
    for m in ("spread", "total", "moneyline"):
        dm = dec.get(m) or {}
        c = str(dm.get("classification") or "").upper()
        if c:
            cls_values.append(c)

    teaser = "MARKET_ALIGNED"
    if "EDGE" in cls_values:
        teaser = "EDGE"
    elif "LEAN" in cls_values:
        teaser = "LEAN"
    elif "NO_ACTION" in cls_values:
        teaser = "NO_ACTION"
    elif "BLOCKED" in cls_values:
        teaser = "BLOCKED"

    counts[teaser] += 1
    rows.append((event_id, teaser, cls_values))

print("TOTAL_VISIBLE", len(rows))
print("EDGE", counts["EDGE"])
print("LEAN", counts["LEAN"])
print("MARKET_ALIGNED", counts["MARKET_ALIGNED"])
print("NO_ACTION", counts["NO_ACTION"])
print("BLOCKED", counts["BLOCKED"])
print("\nSAMPLE:")
for r in rows[:12]:
    print(r[0], "|", r[1], "|", r[2])
