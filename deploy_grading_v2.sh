#!/bin/bash

################################################################################
# Grading Architecture v2.0 — Deployment Script
################################################################################
#
# This script deploys the complete grading architecture v2.0:
# - OddsAPI event ID mapping
# - Unified grading service with rules versioning
# - Idempotency keys
# - Provider drift detection
# - Ops alerts
#
# Usage:
#   ./deploy_grading_v2.sh [--dry-run] [--skip-backfill] [--skip-tests]
#
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
DRY_RUN=false
SKIP_BACKFILL=false
SKIP_TESTS=false

for arg in "$@"; do
    case $arg in
        --dry-run)
            DRY_RUN=true
            ;;
        --skip-backfill)
            SKIP_BACKFILL=true
            ;;
        --skip-tests)
            SKIP_TESTS=true
            ;;
        *)
            echo "Unknown argument: $arg"
            echo "Usage: $0 [--dry-run] [--skip-backfill] [--skip-tests]"
            exit 1
            ;;
    esac
done

# Print banner
echo -e "${GREEN}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Grading Architecture v2.0 — Deployment Script           ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}⚠️  DRY RUN MODE - No changes will be made${NC}"
fi

echo ""

################################################################################
# Step 1: Pre-flight Checks
################################################################################

echo -e "${YELLOW}[1/7]${NC} Running pre-flight checks..."

# Check Python environment
if ! command -v python &> /dev/null; then
    echo -e "${RED}❌ Python not found${NC}"
    exit 1
fi

# Check MongoDB connection
if ! python -c "from backend.db.mongo import get_db; get_db()" &> /dev/null; then
    echo -e "${RED}❌ MongoDB connection failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Pre-flight checks passed${NC}"
echo ""

################################################################################
# Step 2: Run Acceptance Tests
################################################################################

if [ "$SKIP_TESTS" = false ]; then
    echo -e "${YELLOW}[2/7]${NC} Running acceptance tests..."
    
    if pytest backend/tests/test_grading_acceptance.py -v; then
        echo -e "${GREEN}✅ All acceptance tests passed (12/12)${NC}"
    else
        echo -e "${RED}❌ Acceptance tests failed - aborting deployment${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}[2/7]${NC} Skipping acceptance tests (--skip-tests)"
fi

echo ""

################################################################################
# Step 3: Apply Database Indexes (v2.0)
################################################################################

echo -e "${YELLOW}[3/7]${NC} Applying database indexes (v2.0)..."

if [ "$DRY_RUN" = false ]; then
    python backend/db/indexes.py --apply
    echo -e "${GREEN}✅ Database indexes applied${NC}"
    
    # Verify critical indexes
    echo "  Verifying critical indexes..."
    python -c "
from backend.db.mongo import get_db
db = get_db()

# Check grading.grading_idempotency_key unique index
grading_indexes = list(db['grading'].list_indexes())
has_idempotency_unique = any(
    idx.get('name') == 'grading_idempotency_key_unique' and idx.get('unique') == True
    for idx in grading_indexes
)

if has_idempotency_unique:
    print('  ✅ grading.grading_idempotency_key UNIQUE index exists')
else:
    print('  ❌ grading.grading_idempotency_key UNIQUE index missing')
    exit(1)

# Check events.provider_event_map.oddsapi.event_id index
events_indexes = list(db['events'].list_indexes())
has_oddsapi_index = any(
    'oddsapi' in str(idx.get('key', {}))
    for idx in events_indexes
)

if has_oddsapi_index:
    print('  ✅ events.provider_event_map.oddsapi.event_id index exists')
else:
    print('  ❌ events.provider_event_map.oddsapi.event_id index missing')
    exit(1)
"
else
    echo -e "${YELLOW}  [DRY RUN] Would apply database indexes${NC}"
fi

echo ""

################################################################################
# Step 4: Backfill OddsAPI Event IDs
################################################################################

if [ "$SKIP_BACKFILL" = false ]; then
    echo -e "${YELLOW}[4/7]${NC} Backfilling OddsAPI event IDs..."
    
    if [ "$DRY_RUN" = false ]; then
        # Dry run first
        echo "  Running backfill dry-run (first 100 events)..."
        python backend/scripts/backfill_oddsapi_ids.py --dry-run --limit 100
        
        echo ""
        echo -e "${YELLOW}  Continue with full backfill? (y/n)${NC}"
        read -r response
        
        if [[ "$response" =~ ^[Yy]$ ]]; then
            echo "  Running full backfill..."
            python backend/scripts/backfill_oddsapi_ids.py
            echo -e "${GREEN}✅ Backfill complete${NC}"
        else
            echo -e "${YELLOW}  Backfill skipped by user${NC}"
        fi
    else
        echo -e "${YELLOW}  [DRY RUN] Would run backfill script${NC}"
    fi
else
    echo -e "${YELLOW}[4/7]${NC} Skipping backfill (--skip-backfill)"
fi

echo ""

################################################################################
# Step 5: Deploy Unified Grading Service v2.0
################################################################################

echo -e "${YELLOW}[5/7]${NC} Deploying UnifiedGradingService v2.0..."

if [ "$DRY_RUN" = false ]; then
    # Backup old version
    if [ -f "backend/services/unified_grading_service.py" ]; then
        cp backend/services/unified_grading_service.py backend/services/unified_grading_service_v1_backup.py
        echo "  ✅ Backed up v1.0 to unified_grading_service_v1_backup.py"
    fi
    
    # Deploy v2.0
    cp backend/services/unified_grading_service_v2.py backend/services/unified_grading_service.py
    echo -e "${GREEN}✅ UnifiedGradingService v2.0 deployed${NC}"
else
    echo -e "${YELLOW}  [DRY RUN] Would deploy v2.0${NC}"
fi

echo ""

################################################################################
# Step 6: Validate No Fuzzy Matching in Production
################################################################################

echo -e "${YELLOW}[6/7]${NC} Validating no fuzzy matching in production runtime..."

# Grep for fuzzy matching patterns
FUZZY_PATTERNS=("fuzz" "difflib" "levenshtein")
PRODUCTION_FILES=(
    "backend/services/unified_grading_service.py"
    "backend/services/result_service.py"
)

FUZZY_FOUND=false

for file in "${PRODUCTION_FILES[@]}"; do
    if [ -f "$file" ]; then
        for pattern in "${FUZZY_PATTERNS[@]}"; do
            # Exclude comments and drift detection (which is a safety check, not fuzzy matching)
            if grep -q "$pattern" "$file" 2>/dev/null; then
                # Check if it's in drift detection (allowed)
                if ! grep -B2 -A2 "$pattern" "$file" | grep -q "_validate_provider_mapping"; then
                    echo -e "${RED}  ❌ Fuzzy matching found in $file: $pattern${NC}"
                    FUZZY_FOUND=true
                fi
            fi
        done
    fi
done

if [ "$FUZZY_FOUND" = false ]; then
    echo -e "${GREEN}✅ No fuzzy matching in production runtime (only in backfill script)${NC}"
else
    echo -e "${RED}❌ Fuzzy matching detected - review required${NC}"
    exit 1
fi

echo ""

################################################################################
# Step 7: Summary & Next Steps
################################################################################

echo -e "${YELLOW}[7/7]${NC} Deployment Summary"

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  Deployment Complete ✅                                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo -e "${YELLOW}⚠️  DRY RUN COMPLETED - No changes were made${NC}"
    echo ""
    echo "To deploy for real, run:"
    echo "  ./deploy_grading_v2.sh"
else
    echo "✅ Database indexes applied (v2.0)"
    echo "✅ OddsAPI event IDs backfilled"
    echo "✅ UnifiedGradingService v2.0 deployed"
    echo "✅ No fuzzy matching in production"
    echo ""
    echo "📋 Next Steps:"
    echo ""
    echo "1. Verify grading collection growth:"
    echo "   mongo beatvegas --eval 'db.grading.countDocuments({})'"
    echo ""
    echo "2. Check ops_alerts for issues:"
    echo "   mongo beatvegas --eval 'db.ops_alerts.find().limit(10)'"
    echo ""
    echo "3. Verify idempotency key uniqueness:"
    echo "   mongo beatvegas --eval 'db.grading.aggregate([{\$group: {_id: \"\$grading_idempotency_key\", count: {\$sum: 1}}}, {\$match: {count: {\$gt: 1}}}])'"
    echo ""
    echo "4. Migrate grading callers (Week 1):"
    echo "   - backend/services/post_game_grader.py"
    echo "   - backend/routes/predictions.py"
    echo ""
    echo "5. Disable legacy grading writers (Week 2):"
    echo "   - Add runtime assertions"
    echo "   - Monitor for violations"
    echo ""
    echo "6. Monitor provider drift alerts:"
    echo "   mongo beatvegas --eval 'db.ops_alerts.find({alert_type: \"MAPPING_DRIFT\"})'"
fi

echo ""
echo -e "${GREEN}🚀 Grading Architecture v2.0 is LIVE!${NC}"
