#!/bin/bash
# vFinal.1 Phase 2 Migration - Quick Start Guide
# Run this to test the migration on your database

set -e

echo "=================================================="
echo "vFinal.1 Phase 2: Schema Migration"
echo "=================================================="
echo ""

cd "$(dirname "$0")/backend"

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "📦 Activating virtual environment..."
    source .venv/bin/activate
fi

# Step 1: Dry Run
echo "Step 1: Running DRY RUN migration..."
echo "This will show what would happen without making changes."
echo ""
python scripts/migrate_market_fields.py

echo ""
echo "=================================================="
echo "Review the dry run output above."
echo ""
read -p "Continue with LIVE migration? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "❌ Migration cancelled."
    exit 0
fi

# Step 2: Live Migration
echo ""
echo "Step 2: Running LIVE migration..."
python scripts/migrate_market_fields.py --live

# Step 3: Verification
echo ""
echo "Step 3: Verifying migration results..."
python scripts/migrate_market_fields.py --verify

echo ""
echo "=================================================="
echo "✅ Migration Complete!"
echo "=================================================="
echo ""
echo "Next Steps:"
echo "1. Check the output above for any errors"
echo "2. Restart your backend server to load new indexes"
echo "3. Test API with new market_type parameter"
echo "4. Proceed to Phase 3 (Tier A test updates)"
echo ""
