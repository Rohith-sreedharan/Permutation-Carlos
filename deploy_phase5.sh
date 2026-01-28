#!/bin/bash
#
# BeatVegas vFinal.1 - Phase 5 Deployment Script
# Executes complete deployment workflow per specification Section 7
#
# Usage:
#   ./deploy_phase5.sh staging   # Deploy to staging
#   ./deploy_phase5.sh production # Deploy to production
#

set -e  # Exit on error

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-staging}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Auto-detect backend directory
if [ -d "$SCRIPT_DIR/backend" ]; then
    BACKEND_DIR="$SCRIPT_DIR/backend"
else
    # Running from root or backend dir
    BACKEND_DIR="$SCRIPT_DIR"
fi

echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}BeatVegas vFinal.1 - Phase 5 Deployment${NC}"
echo -e "${BLUE}=========================================${NC}"
echo -e "${BLUE}Environment: ${ENVIRONMENT}${NC}"
echo -e "${BLUE}Time: $(date)${NC}"
echo -e "${BLUE}=========================================${NC}\n"

# =============================================================================
# STEP 1: PRE-FLIGHT CHECKS
# =============================================================================
echo -e "${YELLOW}[1/7] Pre-flight checks...${NC}"

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Python 3 available${NC}"

# Check MongoDB connection
if ! pgrep -x "mongod" > /dev/null; then
    echo -e "${RED}✗ MongoDB is not running${NC}"
    echo "Please start MongoDB:"
    echo "  macOS: brew services start mongodb-community"
    echo "  Linux: sudo systemctl start mongod"
    exit 1
fi
echo -e "${GREEN}✓ MongoDB is running${NC}"

# Check virtual environment (either activated or exists in backend dir)
if [ -z "$VIRTUAL_ENV" ] && [ ! -d "$BACKEND_DIR/.venv" ] && [ ! -d ".venv" ]; then
    echo -e "${RED}✗ Virtual environment not found${NC}"
    echo "Please activate virtual environment or create one in backend/"
    exit 1
fi
echo -e "${GREEN}✓ Virtual environment available${NC}"

# Check .env file
if [ ! -f "$BACKEND_DIR/.env" ]; then
    echo -e "${RED}✗ .env file not found${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Configuration file exists${NC}"

echo ""

# =============================================================================
# STEP 2: RUN TIER A INTEGRITY TESTS
# =============================================================================
echo -e "${YELLOW}[2/7] Running Tier A integrity tests (33 tests)...${NC}"

cd "$BACKEND_DIR"

# Activate venv only if not already activated
if [ -z "$VIRTUAL_ENV" ]; then
    if [ -d ".venv" ]; then
        source .venv/bin/activate
    elif [ -d "$BACKEND_DIR/.venv" ]; then
        source "$BACKEND_DIR/.venv/bin/activate"
    fi
fi

if ! python tests/tier_a_integrity.py; then
    echo -e "${RED}✗ Tier A tests failed${NC}"
    echo -e "${RED}DEPLOYMENT BLOCKED${NC}"
    exit 1
fi
echo -e "${GREEN}✓ All 33 Tier A tests passed${NC}"
echo ""

# =============================================================================
# STEP 3: RUN MULTI-SPORT SMOKE TESTS
# =============================================================================
echo -e "${YELLOW}[3/7] Running multi-sport smoke tests (36 test cases)...${NC}"

if ! python scripts/smoke_test_multisport.py; then
    echo -e "${RED}✗ Smoke tests failed${NC}"
    echo -e "${RED}DEPLOYMENT BLOCKED${NC}"
    exit 1
fi
echo -e "${GREEN}✓ All 36 smoke tests passed${NC}"
echo ""

# =============================================================================
# STEP 4: EXECUTE DATABASE MIGRATION
# =============================================================================
echo -e "${YELLOW}[4/7] Executing database migration...${NC}"

# Dry-run first
echo "Running dry-run migration..."
if ! python scripts/migrate_market_fields.py; then
    echo -e "${RED}✗ Dry-run migration failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Dry-run migration successful${NC}"

# Prompt for live migration
if [ "$ENVIRONMENT" = "production" ]; then
    echo -e "${YELLOW}⚠️  About to run LIVE MIGRATION in PRODUCTION${NC}"
    read -p "Are you sure? (type 'yes' to continue): " confirm
    if [ "$confirm" != "yes" ]; then
        echo -e "${RED}Deployment cancelled${NC}"
        exit 1
    fi
fi

# Run live migration
echo "Running live migration..."
if ! python scripts/migrate_market_fields.py --live; then
    echo -e "${RED}✗ Live migration failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Live migration successful${NC}"

# Verify migration
echo "Verifying migration..."
if ! python scripts/migrate_market_fields.py --verify; then
    echo -e "${RED}✗ Migration verification failed${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Migration verification successful${NC}"
echo ""

# =============================================================================
# STEP 5: VERIFY NO REGRESSIONS
# =============================================================================
echo -e "${YELLOW}[5/7] Verifying no regressions in existing behavior...${NC}"

# Test NBA behavior (existing)
echo "Testing NBA FULL_GAME behavior..."
python -c "
from core.sport_config import MarketType, MarketSettlement, validate_market_contract
validate_market_contract('NBA', MarketType.SPREAD, MarketSettlement.FULL_GAME)
validate_market_contract('NBA', MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME)
print('✓ NBA FULL_GAME validation working')
"

# Test NFL behavior (existing)
echo "Testing NFL FULL_GAME behavior..."
python -c "
from core.sport_config import MarketType, MarketSettlement, validate_market_contract
validate_market_contract('NFL', MarketType.SPREAD, MarketSettlement.FULL_GAME)
validate_market_contract('NFL', MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME)
print('✓ NFL FULL_GAME validation working')
"

# Test NHL behavior (existing)
echo "Testing NHL FULL_GAME behavior..."
python -c "
from core.sport_config import MarketType, MarketSettlement, validate_market_contract
validate_market_contract('NHL', MarketType.SPREAD, MarketSettlement.FULL_GAME)
validate_market_contract('NHL', MarketType.MONEYLINE_2WAY, MarketSettlement.FULL_GAME)
print('✓ NHL FULL_GAME validation working')
"

echo -e "${GREEN}✓ No regressions detected${NC}"
echo ""

# =============================================================================
# STEP 6: START/RESTART BACKEND SERVER
# =============================================================================
echo -e "${YELLOW}[6/7] Starting backend server...${NC}"

# Kill existing process if running
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "Stopping existing server..."
    kill $(lsof -ti:8000) || true
    sleep 2
fi

# Start server in background
echo "Starting server on port 8000..."
PYTHONPATH=$BACKEND_DIR nohup uvicorn main:app --reload --port 8000 --host 0.0.0.0 > "$BACKEND_DIR/backend.log" 2>&1 &
SERVER_PID=$!

# Wait for server to start
echo "Waiting for server to start..."
sleep 5

# Check if server is running
if ! lsof -ti:8000 > /dev/null 2>&1; then
    echo -e "${RED}✗ Server failed to start${NC}"
    echo "Check $BACKEND_DIR/backend.log for errors"
    exit 1
fi

echo -e "${GREEN}✓ Server started (PID: $SERVER_PID)${NC}"
echo ""

# =============================================================================
# STEP 7: HEALTH CHECK & VALIDATION
# =============================================================================
echo -e "${YELLOW}[7/7] Running health checks...${NC}"

# Wait for server warmup
sleep 2

# Test health endpoint
if curl -s http://localhost:8000/health > /dev/null; then
    echo -e "${GREEN}✓ Health endpoint responding${NC}"
else
    echo -e "${RED}✗ Health endpoint not responding${NC}"
    exit 1
fi

# Test API docs
if curl -s http://localhost:8000/docs > /dev/null; then
    echo -e "${GREEN}✓ API documentation available${NC}"
else
    echo -e "${RED}✗ API documentation not available${NC}"
fi

echo ""

# =============================================================================
# DEPLOYMENT SUCCESS
# =============================================================================
echo -e "${GREEN}=========================================${NC}"
echo -e "${GREEN}✓ PHASE 5 DEPLOYMENT SUCCESSFUL${NC}"
echo -e "${GREEN}=========================================${NC}"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Backend Server: http://localhost:8000"
echo "API Docs: http://localhost:8000/docs"
echo "Server PID: $SERVER_PID"
echo "Log File: $BACKEND_DIR/backend.log"
echo ""
echo -e "${BLUE}Next Steps:${NC}"
echo "1. Monitor server logs: tail -f $BACKEND_DIR/backend.log"
echo "2. Watch for MARKET_CONTRACT_MISMATCH errors"
echo "3. Test API endpoints manually"
echo "4. Monitor MongoDB for query performance"
echo ""
echo -e "${YELLOW}To view deployment status:${NC}"
echo "  curl http://localhost:8000/api/system/status"
echo ""
echo -e "${YELLOW}To stop the server:${NC}"
echo "  kill $SERVER_PID"
echo ""
echo -e "${GREEN}Deployment complete at $(date)${NC}"
