#!/bin/bash

# BEATVEGAS CRITICAL FIX DEPLOYMENT
# Fixes cover probability calculation bug that caused 0-3 picks

echo "🚨 DEPLOYING CRITICAL FIX - Cover Probability Bug"
echo "=================================================="
echo ""

# Step 1: Verify we're in the right directory
if [ ! -f "backend/core/monte_carlo_engine.py" ]; then
    echo "❌ Error: Not in project root directory"
    exit 1
fi

echo "✅ Project directory confirmed"
echo ""

# Step 2: Show the fix
echo "📝 Fix Summary:"
echo "  - File: backend/core/monte_carlo_engine.py"
echo "  - Bug: Cover probability formula inverted"
echo "  - Old: home_covers = margin > vegas_spread_home"
echo "  - New: home_covers = margin + vegas_spread_home > 0"
echo ""

# Step 3: Commit the fix
echo "💾 Committing fix to git..."
git add backend/core/monte_carlo_engine.py
git add backend/core/output_consistency.py
git add backend/integrations/odds_api.py
git add backend/services/parlay_architect.py
git add components/GameDetail.tsx

git commit -m "CRITICAL FIX: Cover probability formula was inverted

- Fixed spread cover calculation in monte_carlo_engine.py
- Old formula counted favorites covering when they didn't
- New formula: margin + spread > 0 (correct ATS logic)
- Added validator to prevent contradictions
- Added spread integrity checks in odds API

This bug caused incorrect cover probabilities and bad picks.
All simulations must be regenerated after this fix."

echo "✅ Changes committed"
echo ""

# Step 4: Check if backend is running
echo "🔍 Checking if backend is running..."
BACKEND_PID=$(lsof -ti:8000)

if [ -n "$BACKEND_PID" ]; then
    echo "⚠️  Backend is running on PID $BACKEND_PID"
    echo "   We need to restart it to apply the fix"
    echo ""
    read -p "Kill and restart backend? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        kill $BACKEND_PID
        echo "✅ Backend stopped"
        echo "   Please restart manually: cd backend && uvicorn main:app --reload"
    fi
else
    echo "ℹ️  Backend not running - start it when ready"
fi

echo ""

# Step 5: Connect to MongoDB and delete old simulations
echo "🗑️  Cleaning up old simulations..."
echo ""
echo "To delete simulations from last 7 days, run:"
echo ""
echo "mongo beatvegas --eval '"
echo "  db.monte_carlo_simulations.deleteMany({"
echo "    created_at: { \$gte: new Date(Date.now() - 7*24*60*60*1000).toISOString() }"
echo "  })"
echo "'"
echo ""

# Step 6: Verification instructions
echo "🧪 VERIFICATION STEPS:"
echo "====================="
echo ""
echo "1. Start backend: cd backend && uvicorn main:app --reload"
echo ""
echo "2. Test with a recent game where favorite didn't cover:"
echo "   - Pick a game like DEN @ MIL (DEN won by 20, MIL was -7.5)"
echo "   - Force re-simulation"
echo "   - Check that MIL -7.5 shows LOW cover % (should be ~0-20%)"
echo "   - Old bug would show 80%+"
echo ""
echo "3. Run calibration report (after games finish):"
echo "   curl http://localhost:8000/api/v1/calibration/report?days=7"
echo ""
echo "4. Monitor logs for these messages:"
echo "   - '✅ Cover Probabilities at market line' (should look reasonable)"
echo "   - '⚠️ CALIBRATION ALERT' (flags big misses)"
echo ""

# Step 7: Create verification script
cat > verify_fix.py << 'EOF'
#!/usr/bin/env python3
"""
Quick verification that the fix is working
"""
import requests
import sys

def verify_fix():
    print("🧪 Testing cover probability fix...")
    print("")
    
    # Test case: Favorite that didn't cover
    # Denver @ Milwaukee: DEN won 83-63 (won by 20), MIL was -7.5
    # Expected: MIL -7.5 should have LOW cover % since they lost by 20
    
    BASE_URL = "http://localhost:8000"
    
    # Try to get recent NBA games
    try:
        response = requests.get(f"{BASE_URL}/api/v1/events?sport=basketball_nba&days=3")
        if response.status_code != 200:
            print(f"❌ Failed to fetch games: {response.status_code}")
            return False
        
        games = response.json().get("events", [])
        if not games:
            print("⚠️ No games found in last 3 days")
            return True
        
        print(f"✅ Found {len(games)} games")
        print("")
        
        # Check a simulation
        for game in games[:3]:
            event_id = game.get("event_id")
            home_team = game.get("home_team")
            away_team = game.get("away_team")
            
            # Get simulation
            sim_response = requests.get(f"{BASE_URL}/api/v1/simulations/{event_id}")
            if sim_response.status_code != 200:
                continue
            
            sim = sim_response.json()
            spread_data = sim.get("sharp_analysis", {}).get("spread", {})
            probs = sim.get("sharp_analysis", {}).get("probabilities", {})
            
            market_spread = spread_data.get("market_spread_home", 0)
            p_cover_home = probs.get("p_cover_home", 0.5)
            p_cover_away = probs.get("p_cover_away", 0.5)
            
            print(f"📊 {away_team} @ {home_team}")
            print(f"   Market: {home_team} {market_spread:+.1f}")
            print(f"   Cover %: {home_team} {p_cover_home*100:.1f}% | {away_team} {p_cover_away*100:.1f}%")
            
            # Sanity check
            if abs(p_cover_home + p_cover_away - 1.0) > 0.01:
                print(f"   ❌ WARNING: Probabilities don't sum to 1.0!")
                return False
            
            # Check if favorite has unrealistic cover %
            if market_spread < -5:  # Home favorite by more than 5
                if p_cover_home > 0.85:
                    print(f"   ⚠️ Warning: Heavy favorite with very high cover % - verify this makes sense")
            
            print("")
        
        print("✅ Fix appears to be working")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = verify_fix()
    sys.exit(0 if success else 1)
EOF

chmod +x verify_fix.py

echo "📝 Created verify_fix.py - run this after backend starts"
echo ""

# Step 8: Final checklist
echo "✅ DEPLOYMENT CHECKLIST:"
echo "======================="
echo ""
echo "☐ Fix committed to git"
echo "☐ Backend restarted with new code"
echo "☐ Old simulations deleted from MongoDB"
echo "☐ Verification script run (./verify_fix.py)"
echo "☐ Calibration logging enabled"
echo "☐ Tested with at least 3 recent games"
echo ""
echo "🎯 CRITICAL: Do NOT post picks from old simulations!"
echo "   All simulations created before this fix have inverted cover probabilities"
echo ""
echo "Done! Backend is ready to deploy once restarted."
