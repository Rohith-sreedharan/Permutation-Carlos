#!/bin/bash
# Setup script to install all dependencies and verify codebase

echo "🚀 BeatVegas Backend Setup Script"
echo "=================================="
echo ""

# Check Python version
echo "📋 Checking Python version..."
python3 --version
echo ""

# Install dependencies
echo "📦 Installing Python dependencies..."
pip3 install -r requirements.txt
echo ""

# Verify MongoDB connection (if running)
echo "🔍 Verifying imports..."
python3 -c "
import sys
sys.path.insert(0, '.')

print('Testing critical imports...')
try:
    from db.mongo import db
    print('  ✅ db.mongo')
except Exception as e:
    print(f'  ❌ db.mongo: {e}')

try:
    from services.mlb_edge_evaluator import MLBEdgeEvaluator
    print('  ✅ MLBEdgeEvaluator')
except Exception as e:
    print(f'  ❌ MLBEdgeEvaluator: {e}')

try:
    from services.ncaab_edge_evaluator import NCAABThresholds
    print('  ✅ NCAABThresholds')
except Exception as e:
    print(f'  ❌ NCAABThresholds: {e}')

try:
    from services.ai_analyzer_schemas import AnalyzerOutput
    print('  ✅ AnalyzerOutput')
except Exception as e:
    print(f'  ❌ AnalyzerOutput: {e}')

try:
    from pymongo.database import Database
    print('  ✅ pymongo.Database')
except Exception as e:
    print(f'  ❌ pymongo.Database: {e}')

try:
    from motor.motor_asyncio import AsyncIOMotorDatabase
    print('  ✅ motor.AsyncIOMotorDatabase')
except Exception as e:
    print(f'  ❌ motor.AsyncIOMotorDatabase: {e}')

print('')
print('✅ Import verification complete!')
"

echo ""
echo "=================================="
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Configure environment variables in .env file"
echo "  2. Ensure MongoDB is running"
echo "  3. Run: python3 tools/system_validation.py"
echo ""
