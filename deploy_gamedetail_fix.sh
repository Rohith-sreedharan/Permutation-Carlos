#!/bin/bash
# Deploy latest changes to production

echo "🚀 Deploying GameDetail.tsx fix to production..."
echo ""

# Check if we're on the right server
if [ ! -d "/root/permu" ]; then
    echo "❌ Error: /root/permu directory not found"
    echo "   This script should be run on the production server"
    exit 1
fi

cd /root/permu || exit 1

echo "📥 Pulling latest changes from main branch..."
git fetch origin
git pull origin main

echo ""
echo "✅ Latest changes pulled"
echo ""
echo "Current commit:"
git log -1 --oneline

echo ""
echo "🔄 Frontend will auto-reload (Vite HMR)"
echo "   If needed, restart manually: pm2 restart permu-frontend"
echo ""
echo "✅ Deployment complete!"
