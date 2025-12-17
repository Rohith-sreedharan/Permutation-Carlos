#!/bin/bash
"""
Setup Daily Calibration Cron Job
Adds cron entry to run calibration analysis every night at 2 AM EST

Usage:
    bash scripts/setup_calibration_cron.sh
"""

# Get absolute path to backend directory
BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SCRIPT_PATH="$BACKEND_DIR/scripts/daily_calibration_job.py"
VENV_PATH="$BACKEND_DIR/.venv/bin/activate"
LOG_PATH="$BACKEND_DIR/logs/calibration.log"

# Cron schedule: 2 AM EST daily (0 2 * * *)
# Adjust if needed based on timezone
CRON_TIME="0 2 * * *"

# Build cron command
CRON_CMD="cd $BACKEND_DIR && source $VENV_PATH && PYTHONPATH=$BACKEND_DIR python3 $SCRIPT_PATH >> $LOG_PATH 2>&1"

echo "=================================================="
echo "🎯 Setting Up Daily Calibration Cron Job"
echo "=================================================="
echo ""
echo "Backend Directory: $BACKEND_DIR"
echo "Script Path: $SCRIPT_PATH"
echo "Virtual Env: $VENV_PATH"
echo "Log Path: $LOG_PATH"
echo "Schedule: $CRON_TIME (2 AM EST daily)"
echo ""

# Check if script exists
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "❌ Error: Script not found at $SCRIPT_PATH"
    exit 1
fi

# Check if virtual environment exists
if [ ! -f "$VENV_PATH" ]; then
    echo "❌ Error: Virtual environment not found at $VENV_PATH"
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p "$BACKEND_DIR/logs"

# Get current crontab
CURRENT_CRON=$(crontab -l 2>/dev/null || echo "")

# Check if job already exists
if echo "$CURRENT_CRON" | grep -q "daily_calibration_job.py"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    CURRENT_CRON=$(echo "$CURRENT_CRON" | grep -v "daily_calibration_job.py")
fi

# Add new cron job
NEW_CRON="$CURRENT_CRON"$'\n'"$CRON_TIME $CRON_CMD"

# Install new crontab
echo "$NEW_CRON" | crontab -

# Verify installation
if crontab -l | grep -q "daily_calibration_job.py"; then
    echo ""
    echo "✅ Cron job successfully installed!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep "daily_calibration_job.py"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Monitor logs at: $LOG_PATH"
    echo "2. Check MongoDB calibration_daily collection"
    echo "3. First run will be at 2 AM EST tonight"
    echo ""
    echo "To test manually, run:"
    echo "  cd $BACKEND_DIR && source $VENV_PATH && PYTHONPATH=$BACKEND_DIR python3 $SCRIPT_PATH"
    echo ""
else
    echo ""
    echo "❌ Failed to install cron job"
    exit 1
fi
