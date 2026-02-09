#!/bin/bash
# Production Deployment Script
# Execute this on production server after SSH

set -e

echo "=========================================="
echo "PRODUCTION DEPLOYMENT - Atomic MarketDecision"
echo "=========================================="
echo ""

# Navigate to backend
cd ~/permu/backend

# Pull latest commits (includes debug overlay, MongoDB wiring, atomic version)
echo "📦 Pulling latest commits from GitHub..."
git pull origin main

# Show what changed
echo ""
echo "📊 Changes deployed:"
git log --oneline -5

# Restart backend service
echo ""
echo "🔄 Restarting backend service..."
if command -v pm2 &> /dev/null; then
    pm2 restart backend
    pm2 logs backend --lines 50
elif command -v systemctl &> /dev/null; then
    sudo systemctl restart beatvegas-backend
    sudo systemctl status beatvegas-backend
else
    echo "⚠️  Could not find pm2 or systemctl. Please restart manually."
fi

echo ""
echo "=========================================="
echo "VERIFICATION COMMANDS"
echo "=========================================="
echo ""
echo "1. Test decisions endpoint:"
echo "   curl https://beta.beatvegas.app/api/games/NCAAB/4b884b7909ec80756fc09db4223867b4/decisions | jq '.'"
echo ""
echo "2. Verify atomic consistency:"
echo "   curl https://beta.beatvegas.app/api/games/NCAAB/4b884b7909ec80756fc09db4223867b4/decisions | jq '{spread_version: .spread.debug.decision_version, total_version: .total.debug.decision_version, spread_trace: .spread.debug.trace_id, total_trace: .total.debug.trace_id}'"
echo ""
echo "3. Check MongoDB data:"
echo "   mongosh beatvegas --eval 'db.events.findOne({id: \"4b884b7909ec80756fc09db4223867b4\"}, {id: 1, home_team: 1, away_team: 1})'"
echo ""
