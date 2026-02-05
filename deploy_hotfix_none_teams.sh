#!/bin/bash
# Hotfix: Defensive None checks for team_a/team_b
set -e

echo "🔧 HOTFIX: Team data None safety checks"
echo "=================================="

# Deploy to production server
ssh root@ubuntu-s-2vcpu-2gb-amd-nyc3-01 << 'ENDSSH'
cd /root/permu/backend

# Backup current files
cp core/monte_carlo_engine.py core/monte_carlo_engine.py.backup.$(date +%s)
cp routes/simulation_routes.py routes/simulation_routes.py.backup.$(date +%s)

# Pull latest changes
git pull origin main

# Restart backend
pm2 restart permu-backend
sleep 3
pm2 logs permu-backend --lines 20 --nostream

echo ""
echo "✅ Hotfix deployed successfully"
ENDSSH

echo ""
echo "🚀 Deployment complete. Testing..."
sleep 2
curl -s https://beta.beatvegas.app/api/health | jq .
