#!/bin/bash

# Test Blocked Parlay State with Best Single Fallback
# This script tests the new Truth Mode blocked state response

echo "🧪 Testing BEATVEGAS Parlay Architect - Blocked State with Best Single"
echo "======================================================================="
echo ""

# Get auth token first (adjust credentials as needed)
echo "1️⃣ Authenticating..."
AUTH_RESPONSE=$(curl -s -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "rohith@springreen.in",
    "password": "your_password_here"
  }')

TOKEN=$(echo $AUTH_RESPONSE | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo "❌ Authentication failed. Check credentials."
  exit 1
fi

echo "✅ Authenticated successfully"
echo ""

# Test 1: Generate NFL parlay (likely to be blocked due to model_validity_fail)
echo "2️⃣ Attempting to generate 3-leg NFL parlay..."
echo ""

PARLAY_RESPONSE=$(curl -s -X POST http://localhost:8000/api/architect/generate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "sport_key": "americanfootball_nfl",
    "leg_count": 3,
    "risk_profile": "balanced",
    "multi_sport": false
  }')

echo "📊 Response:"
echo "$PARLAY_RESPONSE" | python3 -m json.tool
echo ""

# Check if blocked
if echo "$PARLAY_RESPONSE" | grep -q '"status": "BLOCKED"'; then
  echo "✅ Blocked state detected"
  echo ""
  
  # Extract key info
  echo "📋 Summary:"
  echo "$PARLAY_RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"   • Status: {data.get('status')}\" )
print(f\"   • Passed legs: {data.get('passed_count', 0)}\")
print(f\"   • Failed legs: {data.get('failed_count', 0)}\")
print(f\"   • Best Single available: {'Yes' if data.get('best_single') else 'No'}\")
if data.get('best_single'):
    single = data['best_single']
    print(f\"   • Best Single: {single.get('pick')} ({single.get('confidence')}% confidence, {single.get('expected_value'):+.1f}% EV)\")
print(f\"   • Next refresh: {data.get('next_refresh_seconds')} seconds\")
"
else
  echo "✅ Parlay generated successfully (no block)"
fi

echo ""
echo "======================================================================="
echo "Test complete! Check response above for blocked state details."
