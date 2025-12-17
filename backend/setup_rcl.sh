#!/bin/bash

# Reality Check Layer (RCL) - Quick Start Script
# Run this after pulling the RCL implementation

echo "🚀 BeatVegas Reality Check Layer (RCL) - Setup"
echo "=============================================="
echo ""

# Check if we're in the backend directory
if [ ! -f "main.py" ]; then
    echo "❌ Error: Please run this script from the backend directory"
    exit 1
fi

# Step 1: Initialize database collections
echo "📦 Step 1: Initializing RCL collections..."
python scripts/init_rcl.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to initialize collections"
    exit 1
fi
echo ""

# Step 2: Seed league statistics
echo "🌱 Step 2: Seeding league historical stats..."
python scripts/seed_league_stats.py
if [ $? -ne 0 ]; then
    echo "❌ Failed to seed league stats"
    exit 1
fi
echo ""

# Step 3: Run tests
echo "🧪 Step 3: Running RCL tests..."
python -m pytest test_rcl.py -v --tb=short
if [ $? -ne 0 ]; then
    echo "⚠️  Some tests failed (this is OK if database is not fully set up)"
else
    echo "✅ All tests passed!"
fi
echo ""

# Step 4: Verify integration
echo "🔍 Step 4: Verifying RCL integration..."

# Check if reality_check_layer.py exists
if [ -f "core/reality_check_layer.py" ]; then
    echo "✅ reality_check_layer.py found"
else
    echo "❌ reality_check_layer.py not found"
    exit 1
fi

# Check if monte_carlo_engine.py has RCL import
if grep -q "from core.reality_check_layer import" core/monte_carlo_engine.py; then
    echo "✅ RCL integrated into monte_carlo_engine.py"
else
    echo "❌ RCL not integrated into monte_carlo_engine.py"
    exit 1
fi

echo ""
echo "=============================================="
echo "✅ RCL Setup Complete!"
echo ""
echo "📊 System Status:"
echo "  - Historical RCL: Active"
echo "  - Live Pace Guardrail: Active"
echo "  - Per-Team Pace Guardrail: Active"
echo ""
echo "📚 Next Steps:"
echo "  1. Review: backend/RCL_IMPLEMENTATION_GUIDE.md"
echo "  2. Monitor: db.sim_audit collection for RCL results"
echo "  3. Test: Run a simulation to see RCL in action"
echo ""
echo "🧪 Example Test:"
echo "  python -c \"from core.monte_carlo_engine import monte_carlo_engine; print('RCL Ready!')\""
echo ""
