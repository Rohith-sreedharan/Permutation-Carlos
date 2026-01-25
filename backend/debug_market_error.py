#!/usr/bin/env python3
"""Debug the market data structural error"""
import sys
sys.path.insert(0, '.')

from db.mongo import db
import json

game_id = "8ce953bbc0069883f9f0d53118a22bdc"

print(f"🔍 Investigating market data for game: {game_id}\n")

# Check if event exists
event = db.events.find_one({"game_id": game_id})
if not event:
    print(f"❌ Event not found in database: {game_id}")
    sys.exit(1)

print("✅ Event found:")
print(f"  Sport: {event.get('sport_key')}")
print(f"  Home: {event.get('home_team')}")
print(f"  Away: {event.get('away_team')}")
print(f"  Start time: {event.get('start_time')}")

# Check market_context
market_context = event.get("market_context", {})
print(f"\n📊 Market Context:")
print(f"  Keys: {list(market_context.keys())}")

# Check for structural issues
issues = []

# Check total_line
total_line = market_context.get("total_line")
if total_line is None:
    issues.append("❌ MISSING: total_line")
elif total_line == 0:
    issues.append("❌ INVALID: total_line is zero")
else:
    print(f"  ✅ total_line: {total_line}")

# Check bookmaker_source
bookmaker = market_context.get("bookmaker_source")
if not bookmaker:
    issues.append("❌ MISSING: bookmaker_source")
else:
    print(f"  ✅ bookmaker_source: {bookmaker}")

# Check market_type
market_type = market_context.get("market_type", "full_game")
print(f"  ✅ market_type: {market_type}")

# Check odds_timestamp
odds_timestamp = market_context.get("odds_timestamp")
if not odds_timestamp:
    issues.append("⚠️  MISSING: odds_timestamp")
else:
    print(f"  ✅ odds_timestamp: {odds_timestamp}")

# Check spread
spread = market_context.get("current_spread")
if spread is None:
    issues.append("⚠️  MISSING: current_spread")
else:
    print(f"  ✅ current_spread: {spread}")

# Check event_id consistency
event_id_in_context = market_context.get("event_id")
if event_id_in_context and event_id_in_context != game_id:
    issues.append(f"❌ MISMATCH: event_id in context ({event_id_in_context}) != game_id ({game_id})")

if issues:
    print(f"\n🚨 Found {len(issues)} issue(s):")
    for issue in issues:
        print(f"  {issue}")
else:
    print(f"\n✅ No obvious structural issues found")

# Show full market_context
print(f"\n📋 Full market_context:")
print(json.dumps(market_context, indent=2, default=str))
