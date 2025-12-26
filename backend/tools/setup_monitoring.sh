#!/bin/bash
# 🚦 SYSTEM MONITORING AUTOMATION SETUP
# Sets up all monitoring cron jobs for the Edge Detection System

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PATH="$(dirname "$SCRIPT_DIR")"
TOOLS_PATH="$BACKEND_PATH/tools"

echo "🚦 Edge Detection System - Monitoring Setup"
echo "============================================"
echo ""
echo "Backend Path: $BACKEND_PATH"
echo "Tools Path: $TOOLS_PATH"
echo ""

# Verify tools exist
echo "Verifying monitoring tools..."
REQUIRED_TOOLS=(
    "system_validation.py"
    "daily_monitoring.py"
    "telegram_safety_audit.py"
    "performance_review.py"
    "drift_detection.py"
    "health_dashboard.py"
)

MISSING_TOOLS=0
for tool in "${REQUIRED_TOOLS[@]}"; do
    if [ -f "$TOOLS_PATH/$tool" ]; then
        echo "  ✅ $tool"
    else
        echo "  ❌ $tool - NOT FOUND"
        MISSING_TOOLS=$((MISSING_TOOLS + 1))
    fi
done

if [ $MISSING_TOOLS -gt 0 ]; then
    echo ""
    echo "❌ Missing $MISSING_TOOLS required tools. Please ensure all tools are created."
    exit 1
fi

echo ""
echo "✅ All monitoring tools found"
echo ""

# Create cron entries
CRON_FILE="/tmp/edge_monitoring_cron_$$.txt"

echo "Creating cron schedule..."

cat > "$CRON_FILE" << EOF
# ========================================
# Edge Detection System - Monitoring Jobs
# Generated: $(date)
# ========================================

# Daily monitoring at 9 AM (after previous day's games)
0 9 * * * cd $TOOLS_PATH && python daily_monitoring.py >> $BACKEND_PATH/logs/monitoring/daily.log 2>&1

# Health dashboard at noon
0 12 * * * cd $TOOLS_PATH && python health_dashboard.py >> $BACKEND_PATH/logs/monitoring/health.log 2>&1

# Telegram safety audit twice daily (9 AM and 9 PM)
0 9,21 * * * cd $TOOLS_PATH && python telegram_safety_audit.py 24 >> $BACKEND_PATH/logs/monitoring/telegram_safety.log 2>&1

# Weekly review every Monday at 10 AM
0 10 * * 1 cd $TOOLS_PATH && python performance_review.py weekly >> $BACKEND_PATH/logs/monitoring/weekly.log 2>&1

# Drift detection every other Monday at 11 AM
0 11 * * 1 [ \$(expr \$(date +\\%V) \\% 2) -eq 0 ] && cd $TOOLS_PATH && python drift_detection.py 4 >> $BACKEND_PATH/logs/monitoring/drift.log 2>&1

# Monthly review on 1st of month at 2 PM
0 14 1 * * cd $TOOLS_PATH && python performance_review.py monthly >> $BACKEND_PATH/logs/monitoring/monthly.log 2>&1

# ========================================
EOF

echo ""
echo "Cron schedule created:"
echo "----------------------------------------"
cat "$CRON_FILE"
echo "----------------------------------------"
echo ""

# Create log directory
echo "Creating log directories..."
mkdir -p "$BACKEND_PATH/logs/monitoring"
mkdir -p "$BACKEND_PATH/logs/daily_reports"
echo "✅ Log directories created"
echo ""

# Prompt for installation
read -p "Install these cron jobs? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Backup existing crontab
    echo "Backing up existing crontab..."
    crontab -l > "/tmp/crontab_backup_$(date +%Y%m%d_%H%M%S).txt" 2>/dev/null || echo "No existing crontab"
    
    # Install new cron jobs
    echo "Installing cron jobs..."
    (crontab -l 2>/dev/null || true; cat "$CRON_FILE") | crontab -
    
    echo ""
    echo "✅ Cron jobs installed successfully!"
    echo ""
    echo "Current crontab:"
    echo "----------------------------------------"
    crontab -l | grep -A 20 "Edge Detection System" || crontab -l
    echo "----------------------------------------"
else
    echo ""
    echo "Installation cancelled."
    echo "To install manually, run:"
    echo "  cat $CRON_FILE | crontab -"
fi

# Cleanup
rm -f "$CRON_FILE"

echo ""
echo "=========================================="
echo "SETUP COMPLETE"
echo "=========================================="
echo ""
echo "📋 Next Steps:"
echo ""
echo "1. Run pre-production validation:"
echo "   cd $TOOLS_PATH && python system_validation.py"
echo ""
echo "2. Review logs at:"
echo "   $BACKEND_PATH/logs/monitoring/"
echo ""
echo "3. Monitor daily reports at:"
echo "   $BACKEND_PATH/logs/daily_reports/"
echo ""
echo "4. To view scheduled jobs:"
echo "   crontab -l"
echo ""
echo "5. To remove monitoring jobs:"
echo "   crontab -e  # then delete the Edge Detection System section"
echo ""
echo "🚦 System monitoring is now automated!"
echo ""
