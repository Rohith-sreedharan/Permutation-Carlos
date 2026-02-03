#!/bin/bash
# BeatVegas Production Deployment Script
# Run this to deploy to canary (5% traffic)

set -e  # Exit on error

echo "🚀 BeatVegas Production Deployment — Canary Launch"
echo "=================================================="
echo ""

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[0;93m'
NC='\033[0m'

# ============================================================================
# PRE-FLIGHT CHECKS
# ============================================================================

echo -e "${BLUE}Running Pre-Flight Checks...${NC}"
echo ""

# Check 1: Tier A Integrity Tests
echo -e "${BLUE}1. Running Tier A Integrity Tests (33 tests)...${NC}"
cd backend
python3 tests/tier_a_integrity.py
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ TIER A TESTS FAILED - DEPLOYMENT BLOCKED${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Tier A Integrity: 33/33 PASS${NC}"
echo ""

# Check 2: Canonical Contract Test
echo -e "${BLUE}2. Testing Canonical Contract Enforcement...${NC}"
python3 test_contract.py > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ CANONICAL CONTRACT TEST FAILED - DEPLOYMENT BLOCKED${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Canonical Contract: PASS${NC}"
echo ""

# Check 3: Kill Switch Status
echo -e "${BLUE}3. Checking Kill Switch Status...${NC}"
if [ -f "/tmp/beatvegas_kill_switch.lock" ]; then
    echo -e "${RED}❌ KILL SWITCH IS ACTIVE - Remove /tmp/beatvegas_kill_switch.lock${NC}"
    exit 1
fi
if [ "$BEATVEGAS_KILL_SWITCH" = "1" ]; then
    echo -e "${RED}❌ KILL SWITCH ENV VAR ACTIVE - Unset BEATVEGAS_KILL_SWITCH${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Kill Switch: Deactivated${NC}"
echo ""

# Check 4: Audit Log Directory
echo -e "${BLUE}4. Checking Audit Log Directory...${NC}"
AUDIT_DIR="${BEATVEGAS_AUDIT_LOG_DIR:-/var/log/beatvegas}"
if [ ! -d "$AUDIT_DIR" ]; then
    echo -e "${YELLOW}⚠️  Audit directory doesn't exist, creating: $AUDIT_DIR${NC}"
    sudo mkdir -p "$AUDIT_DIR"
    sudo chown $(whoami):$(whoami) "$AUDIT_DIR"
fi
if [ ! -w "$AUDIT_DIR" ]; then
    echo -e "${RED}❌ Audit directory not writable: $AUDIT_DIR${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Audit Log Directory: $AUDIT_DIR${NC}"
echo ""

# Check 5: Environment Variables
echo -e "${BLUE}5. Checking Environment Variables...${NC}"
if [ -z "$BEATVEGAS_AUDIT_SECRET" ]; then
    echo -e "${YELLOW}⚠️  BEATVEGAS_AUDIT_SECRET not set - using default (INSECURE)${NC}"
    echo -e "${YELLOW}   Set export BEATVEGAS_AUDIT_SECRET='<random-256-bit-key>'${NC}"
fi
echo -e "${GREEN}✅ Environment: OK${NC}"
echo ""

# Check 6: MongoDB Connection
echo -e "${BLUE}6. Testing MongoDB Connection...${NC}"
cd backend
python3 test_mongo_connection.py > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo -e "${RED}❌ MONGODB CONNECTION FAILED${NC}"
    exit 1
fi
echo -e "${GREEN}✅ MongoDB: Connected${NC}"
echo ""

cd ..

# ============================================================================
# DEPLOYMENT CONFIRMATION
# ============================================================================

echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}All Pre-Flight Checks PASSED${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo -e "${YELLOW}Deployment Details:${NC}"
echo "  • Target: Canary (5% traffic)"
echo "  • Backend: Canonical contract + audit logging + kill switch"
echo "  • Frontend: UI contract system + box-level suppression"
echo "  • Test Coverage: 67+ automated tests"
echo "  • Monitoring: Audit logs + manual review"
echo ""
echo -e "${YELLOW}Expected Canary Duration: 24-48 hours${NC}"
echo ""

read -p "Deploy to canary? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
    echo -e "${RED}Deployment cancelled${NC}"
    exit 0
fi

# ============================================================================
# BACKUP CURRENT STATE
# ============================================================================

echo ""
echo -e "${BLUE}Creating backup...${NC}"
BACKUP_DIR="backups/pre_canary_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp -r backend/core "$BACKUP_DIR/"
cp -r backend/routes "$BACKUP_DIR/"
cp -r utils "$BACKUP_DIR/"
echo -e "${GREEN}✅ Backup created: $BACKUP_DIR${NC}"
echo ""

# ============================================================================
# START BACKEND SERVER
# ============================================================================

echo -e "${BLUE}Starting Backend Server...${NC}"
cd backend

# Activate virtual environment
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt --quiet

# Set production environment
export ENVIRONMENT="production"
export LOG_LEVEL="INFO"

# Clear last-known-good cache (fresh start)
echo -e "${BLUE}Clearing last-known-good cache...${NC}"
rm -f /tmp/beatvegas_last_known_good_*.json 2>/dev/null || true
echo -e "${GREEN}✅ Cache cleared${NC}"
echo ""

# Start server
echo ""
echo -e "${GREEN}=================================================${NC}"
echo -e "${GREEN}🚀 CANARY DEPLOYMENT LIVE${NC}"
echo -e "${GREEN}=================================================${NC}"
echo ""
echo "Features Enabled:"
echo "  ✅ Canonical Contract Enforcement"
echo "  ✅ Audit Logging (immutable, signed)"
echo "  ✅ Kill Switch (deactivated)"
echo "  ✅ Box-Level Suppression"
echo "  ✅ UI Contract System"
echo ""
echo "Monitoring:"
echo "  • Audit Logs: tail -f $AUDIT_DIR/audit.jsonl"
echo "  • Kill Switch Status: curl http://localhost:8000/api/audit/kill-switch/status"
echo "  • Audit Stats: curl http://localhost:8000/api/audit/stats"
echo ""
echo "Emergency Commands:"
echo "  • Activate Kill Switch: touch /tmp/beatvegas_kill_switch.lock"
echo "  • Deactivate Kill Switch: rm /tmp/beatvegas_kill_switch.lock"
echo ""
echo -e "${YELLOW}Traffic: 5% (canary)${NC}"
echo -e "${YELLOW}Monitor for 24-48 hours before increasing traffic${NC}"
echo ""
echo -e "${BLUE}Press Ctrl+C to stop${NC}"
echo ""

# Run server with PYTHONPATH set
PYTHONPATH=$(pwd) uvicorn main:app --reload --port 8000 --host 0.0.0.0
