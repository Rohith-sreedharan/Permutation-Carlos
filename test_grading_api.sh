#!/bin/bash

# Test Grading API - Complete Setup and Test Script

echo "🚀 Starting automated grading API test..."
echo ""

# Step 1: Ensure MongoDB is running
echo "1️⃣  Checking MongoDB..."
if ! pgrep -x "mongod" > /dev/null; then
    echo "   Starting MongoDB..."
    mongod --dbpath ~/data/db --fork --logpath ~/data/mongodb.log --setParameter diagnosticDataCollectionEnabled=false
    sleep 2
else
    echo "   ✅ MongoDB already running"
fi

# Step 2: Start backend server (kill existing if needed)
echo ""
echo "2️⃣  Starting backend server..."
cd /Users/rohithaditya/Downloads/Permutation-Carlos

# Kill any existing server on port 8000
lsof -ti:8000 | xargs kill -9 2>/dev/null

# Start server in background
source .venv/bin/activate
cd backend
nohup uvicorn main:app --port 8000 > /tmp/beatvegas.log 2>&1 &
SERVER_PID=$!
echo "   Server starting with PID: $SERVER_PID"

# Step 3: Wait for server to be ready
echo ""
echo "3️⃣  Waiting for server to initialize..."
MAX_WAIT=30
COUNTER=0

while [ $COUNTER -lt $MAX_WAIT ]; do
    if curl -s "http://localhost:8000/api/simulations/grading/stats?days_back=7" > /dev/null 2>&1; then
        echo "   ✅ Server is ready!"
        break
    fi
    echo "   ⏳ Waiting... ($COUNTER/$MAX_WAIT)"
    sleep 2
    COUNTER=$((COUNTER + 2))
done

if [ $COUNTER -ge $MAX_WAIT ]; then
    echo "   ❌ Server failed to start within $MAX_WAIT seconds"
    echo ""
    echo "Check logs:"
    echo "  tail -50 /tmp/beatvegas.log"
    exit 1
fi

# Step 4: Test grading stats endpoint
echo ""
echo "4️⃣  Testing grading stats API..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
curl -s "http://localhost:8000/api/simulations/grading/stats?days_back=7" | python3 -m json.tool
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Step 5: Test manual grading trigger
echo ""
echo "5️⃣  Testing manual grading trigger..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
curl -s -X POST "http://localhost:8000/api/simulations/grading/run?hours_back=48" | python3 -m json.tool
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "✅ Tests complete!"
echo ""
echo "📝 Server logs: tail -f /tmp/beatvegas.log"
echo "🛑 Stop server: kill $SERVER_PID"
echo ""
echo "🎯 API Endpoints:"
echo "  GET  http://localhost:8000/api/simulations/grading/stats?days_back=7"
echo "  POST http://localhost:8000/api/simulations/grading/run?hours_back=48"
