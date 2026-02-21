#!/bin/bash

# Section 14 HTTP 500 Failure Test
# Simulates audit write failure by temporarily breaking MongoDB connection

echo "========================================================================"
echo "Section 14 Audit Logging - HTTP 500 Failure Test"
echo "========================================================================"
echo ""

# Test with invalid MongoDB URI to simulate connection failure
echo "TEST: Simulating audit write failure..."
echo ""

# Test decision endpoint with broken audit logger
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" \
  -X POST "https://beta.beatvegas.app/api/decisions/game" \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "test_http_500_failure",
    "game_data": {
      "home_team": "Lakers",
      "away_team": "Celtics",
      "spread": -5.5,
      "total": 220.5,
      "league": "NBA"
    }
  }')

HTTP_CODE=$(echo "$RESPONSE" | grep "HTTP_CODE" | cut -d':' -f2)
BODY=$(echo "$RESPONSE" | grep -v "HTTP_CODE")

echo "Response:"
echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
echo ""
echo "HTTP Status Code: $HTTP_CODE"
echo ""

if [ "$HTTP_CODE" = "500" ]; then
    echo "✅ PASS: API returned HTTP 500 on audit failure"
    echo ""
    echo "Expected error message should mention:"
    echo "  - 'Decision audit log write failed'"
    echo "  - 'institutional compliance violation'"
    echo ""
    exit 0
else
    echo "❌ FAIL: Expected HTTP 500, got HTTP $HTTP_CODE"
    echo ""
    exit 1
fi
