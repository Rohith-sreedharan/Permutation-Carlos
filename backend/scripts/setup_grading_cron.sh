#!/bin/bash

# Automated Post-Game Grading Cron Setup
# This script sets up the cron job for automated grading

# Get absolute path to backend directory
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Create cron job entry
CRON_COMMAND="*/30 * * * * cd $BACKEND_DIR && python scripts/grade_finished_games.py >> /var/log/beatvegas/grading.log 2>&1"

echo "🎯 Setting up automated grading cron job..."
echo ""
echo "Cron command to add:"
echo "$CRON_COMMAND"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "grade_finished_games.py"; then
    echo "⚠️  Cron job already exists!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep "grade_finished_games.py"
    echo ""
    read -p "Do you want to update it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "❌ Setup cancelled"
        exit 0
    fi
    
    # Remove old entry
    crontab -l | grep -v "grade_finished_games.py" | crontab -
    echo "✅ Removed old cron job"
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_COMMAND") | crontab -

echo "✅ Cron job added successfully!"
echo ""
echo "Grading will run every 30 minutes and log to:"
echo "/var/log/beatvegas/grading.log"
echo ""

# Create log directory if it doesn't exist
if [ ! -d "/var/log/beatvegas" ]; then
    echo "📁 Creating log directory..."
    sudo mkdir -p /var/log/beatvegas
    sudo chown $USER:$USER /var/log/beatvegas
    echo "✅ Log directory created"
fi

# Test the grading script
echo ""
echo "🧪 Testing grading script..."
cd "$BACKEND_DIR"
python scripts/grade_finished_games.py

echo ""
echo "✅ Setup complete!"
echo ""
echo "To view logs:"
echo "  tail -f /var/log/beatvegas/grading.log"
echo ""
echo "To remove cron job:"
echo "  crontab -e"
echo "  (Delete the line with 'grade_finished_games.py')"
