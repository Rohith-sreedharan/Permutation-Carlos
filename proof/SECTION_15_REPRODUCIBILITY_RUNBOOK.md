# Section 15: Reproducibility & Cold-Start Verification Runbook

**ENGINE LOCK Specification v2.0.0 - Section 15 Compliance**

This runbook provides exact commands to verify Section 15 implementation from a clean checkout, ensuring no local state dependencies.

---

## Prerequisites

- Python 3.13+
- MongoDB 7.0+ (local or remote instance)
- Git
- pytest installed globally or in virtual environment

---

## Test 1: Clean Checkout Reproducibility

**Objective:** Verify all Section 15 tests pass from a fresh clone with no local state.

### Step 1: Clone Repository

```bash
# Fresh clone (or delete existing and re-clone)
git clone <repository-url> permutation-test
cd permutation-test
```

### Step 2: Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
cd backend
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Start MongoDB (if local)

```bash
# Option 1: Local MongoDB
mongod --dbpath /path/to/data/db

# Option 2: Docker
docker run -d -p 27017:27017 --name mongodb mongo:7.0

# Option 3: Use existing remote MongoDB
export MONGO_URI="mongodb://your-mongo-host:27017/"
```

### Step 4: Run Section 15 Tests

```bash
# From backend/ directory
python -m pytest tests/test_section_15_version_control.py -v --tb=short

# Expected output:
# ============================= test session starts ==============================
# tests/test_section_15_version_control.py::TestVersionManager::test_version_format_validation PASSED
# tests/test_section_15_version_control.py::TestVersionManager::test_get_current_version_returns_semver PASSED
# tests/test_section_15_version_control.py::TestVersionManager::test_version_metadata_includes_git_sha PASSED
# tests/test_section_15_version_control.py::TestVersionManager::test_version_bump_major PASSED
# tests/test_section_15_version_control.py::TestVersionManager::test_version_bump_minor PASSED
# tests/test_section_15_version_control.py::TestVersionManager::test_version_bump_patch PASSED
# tests/test_section_15_version_control.py::TestVersionManager::test_version_bump_invalid_type PASSED
# tests/test_section_15_version_control.py::TestDeterministicReplayCache::test_cache_miss_returns_none PASSED
# tests/test_section_15_version_control.py::TestDeterministicReplayCache::test_cache_hit_returns_decision PASSED
# tests/test_section_15_version_control.py::TestDeterministicReplayCache::test_identical_inputs_return_identical_outputs PASSED
# tests/test_section_15_version_control.py::TestDeterministicReplayCache::test_different_version_cache_miss PASSED
# tests/test_section_15_version_control.py::TestDeterministicReplayCache::test_verify_determinism_success PASSED
# tests/test_section_15_version_control.py::TestDeterministicReplayCache::test_verify_determinism_failure PASSED
# tests/test_section_15_version_control.py::TestDeterministicReplayCache::test_cache_statistics PASSED
# ============================== 14 passed in X.XXs ===============================
```

### Step 5: Verify version.json Created

```bash
# Check that version.json is auto-created on first run
ls -la backend/core/version.json

# Expected content:
# {
#   "major": 2,
#   "minor": 0,
#   "patch": 0,
#   "version": "2.0.0",
#   "updated_at": "2026-02-19T00:00:00Z",
#   "updated_by": "system",
#   "change_description": "Initial ENGINE LOCK version after Section 14 completion"
# }
```

### Step 6: Verify Deterministic Replay Cache

```bash
# Test deterministic replay cache independently
python -c "
from core.deterministic_replay_cache import get_replay_cache

cache = get_replay_cache('mongodb://localhost:27017/')

# Test 1: Cache miss
result = cache.get_cached_decision('test_event', 'hash123', 'spread', '2.0.0')
assert result is None, 'Cache miss should return None'
print('✅ Cache miss: PASSED')

# Test 2: Cache decision
decision = {'classification': 'EDGE', 'edge_points': 2.5}
success = cache.cache_decision('test_event', 'hash123', 'spread', '2.0.0', decision)
assert success, 'Cache write should succeed'
print('✅ Cache write: PASSED')

# Test 3: Cache hit
cached = cache.get_cached_decision('test_event', 'hash123', 'spread', '2.0.0')
assert cached is not None, 'Cache hit should return decision'
assert cached['classification'] == 'EDGE', 'Cached decision should match'
print('✅ Cache hit: PASSED')

print('✅ Deterministic replay cache verification: PASSED')
"
```

### Step 7: Verify Version Manager

```bash
# Test version manager independently
python -c "
from core.version_manager import get_version_manager

vm = get_version_manager()

# Test 1: Get current version (SEMVER format)
version = vm.get_current_version()
assert len(version.split('.')) == 3, 'Version must be MAJOR.MINOR.PATCH format'
print(f'✅ Current version: {version}')

# Test 2: Get version metadata
metadata = vm.get_version_metadata()
assert 'decision_version' in metadata, 'Metadata must include decision_version'
assert 'git_commit_sha' in metadata, 'Metadata must include git_commit_sha'
print(f'✅ Version metadata: {metadata}')

# Test 3: Validate version format
assert vm.validate_version_format('2.0.0'), 'Valid SEMVER should pass'
assert not vm.validate_version_format('2.0'), 'Invalid SEMVER should fail'
print('✅ SEMVER validation: PASSED')

print('✅ Version manager verification: PASSED')
"
```

### ✅ Test 1 Success Criteria

- All 14 unit tests PASSED
- version.json auto-created with version 2.0.0
- Deterministic replay cache functional
- Version manager returns valid SEMVER

---

## Test 2: Cold-Start Determinism Verification

**Objective:** Verify determinism holds after API process restart (cleared memory).

### Step 1: Start API Server (First Run)

```bash
# From backend/ directory
cd backend
export MONGO_URI="mongodb://localhost:27017/"
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Wait for server to start
# Expected log: "Application startup complete."
```

### Step 2: Make Test Decision Request (Call 1)

```bash
# In a new terminal
curl -X POST http://localhost:8000/api/decisions/compute \
  -H "Content-Type: application/json" \
  -d '{
    "league": "NBA",
    "game_id": "cold_start_test_game",
    "home_team": "Lakers",
    "away_team": "Celtics"
  }' > decision_call_1.json

# Extract key fields
cat decision_call_1.json | jq '{
  classification: .spread.classification,
  release_status: .spread.release_status,
  edge_points: .spread.edge.edge_points,
  decision_version: .spread.debug.decision_version,
  git_commit_sha: .spread.debug.git_commit_sha,
  inputs_hash: .spread.debug.inputs_hash
}'
```

### Step 3: Make Second Request (Same Inputs - Should Be Cached)

```bash
curl -X POST http://localhost:8000/api/decisions/compute \
  -H "Content-Type: application/json" \
  -d '{
    "league": "NBA",
    "game_id": "cold_start_test_game",
    "home_team": "Lakers",
    "away_team": "Celtics"
  }' > decision_call_2.json

# Compare with first call (excluding timestamp/trace_id)
diff <(cat decision_call_1.json | jq 'del(.spread.debug.timestamp, .spread.debug.trace_id, .computed_at)') \
     <(cat decision_call_2.json | jq 'del(.spread.debug.timestamp, .spread.debug.trace_id, .computed_at)')

# Expected: No differences (exit code 0)
echo "Difference check exit code: $?"
```

### Step 4: Stop API Server

```bash
# In server terminal, press Ctrl+C
# Or from another terminal:
pkill -f "uvicorn main:app"

# Wait for graceful shutdown
sleep 2
```

### Step 5: Restart API Server (Cold Start)

```bash
# Clear Python cache to ensure true cold start
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete

# Restart server
export MONGO_URI="mongodb://localhost:27017/"
python -m uvicorn main:app --host 0.0.0.0 --port 8000

# Wait for server to start
# Expected log: "Application startup complete."
```

### Step 6: Make Third Request (After Restart)

```bash
curl -X POST http://localhost:8000/api/decisions/compute \
  -H "Content-Type: application/json" \
  -d '{
    "league": "NBA",
    "game_id": "cold_start_test_game",
    "home_team": "Lakers",
    "away_team": "Celtics"
  }' > decision_call_3.json

# Compare with first call (excluding timestamp/trace_id)
diff <(cat decision_call_1.json | jq 'del(.spread.debug.timestamp, .spread.debug.trace_id, .computed_at)') \
     <(cat decision_call_3.json | jq 'del(.spread.debug.timestamp, .spread.debug.trace_id, .computed_at)')

# Expected: No differences (exit code 0)
echo "Cold-start difference check exit code: $?"
```

### Step 7: Verify Determinism Across All Three Calls

```bash
# Extract critical fields from all three calls
for i in 1 2 3; do
  echo "=== Call $i ==="
  cat decision_call_$i.json | jq '{
    classification: .spread.classification,
    edge_points: .spread.edge.edge_points,
    decision_version: .spread.debug.decision_version,
    inputs_hash: .spread.debug.inputs_hash
  }'
done

# All three outputs should be identical
```

### ✅ Test 2 Success Criteria

- Calls 1, 2, and 3 have identical classification, edge_points, decision_version, inputs_hash
- Cold-start (call 3) produces same output as pre-restart calls (1, 2)
- Deterministic replay cache persists across process restarts
- No memory-dependent state affecting determinism

---

## Test 3: Multi-Environment Verification

**Objective:** Verify reproducibility on a second machine/environment.

### Option A: Different Developer Machine

1. Send repository URL to another developer
2. Have them follow Test 1 (Clean Checkout Reproducibility)
3. Compare test results - all 14 tests should PASS
4. Compare version.json content - should match exactly

### Option B: CI/CD Environment (GitHub Actions)

1. Push code to repository
2. GitHub Actions will run `engine-tests.yml`
3. Workflow includes Section 15 determinism tests
4. Verify all tests PASS in CI environment
5. Compare local test results with CI results

### Option C: Docker Container

```bash
# Build container
docker build -t permutation-test -f - . << 'EOF'
FROM python:3.13-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .
CMD ["pytest", "tests/test_section_15_version_control.py", "-v"]
EOF

# Run tests in container
docker run --rm permutation-test

# Expected: 14 passed
```

### ✅ Test 3 Success Criteria

- Tests pass on at least 2 different machines/environments
- version.json content identical across environments
- No environment-specific dependencies

---

## Verification Checklist

Use this checklist to confirm Section 15 reproducibility:

- [ ] **Test 1 passed** - Clean checkout reproducibility (14/14 tests)
- [ ] **Test 2 passed** - Cold-start determinism verified (identical outputs)
- [ ] **Test 3 passed** - Multi-environment verification (2+ environments)
- [ ] **version.json** auto-created with version 2.0.0
- [ ] **Git commit SHA** present in all decisions
- [ ] **Deterministic cache** persists across restarts
- [ ] **No local state** dependencies detected
- [ ] **No hardcoded paths** or environment-specific values

---

## Troubleshooting

### Issue: Tests fail with MongoDB connection error

**Solution:**
```bash
# Check MongoDB is running
mongosh mongodb://localhost:27017/ --eval "db.adminCommand('ping')"

# Or set custom MongoDB URI
export MONGO_URI="mongodb://your-host:27017/"
```

### Issue: version.json not created

**Solution:**
```bash
# Manually create version.json
mkdir -p backend/core
cat > backend/core/version.json << 'EOF'
{
  "major": 2,
  "minor": 0,
  "patch": 0,
  "version": "2.0.0",
  "updated_at": "2026-02-19T00:00:00Z",
  "updated_by": "system",
  "change_description": "Initial ENGINE LOCK version"
}
EOF
```

### Issue: Different git_commit_sha across environments

**Expected behavior:** This is normal if environments are at different commits.
- Verify that within the same commit, git_commit_sha is identical
- In clean checkout, git_commit_sha should match current HEAD

### Issue: Cold-start determinism fails

**Investigation:**
1. Check if simulation data changed between calls
2. Verify cache is using MongoDB (not in-memory)
3. Check logs for cache hit/miss messages
4. Verify inputs_hash is identical across calls

---

## Certification

Once all three tests pass, Section 15 reproducibility is **VERIFIED ✅**

**Verified by:** _________________  
**Date:** _________________  
**Environment 1:** _________________  
**Environment 2:** _________________  
**Cold-start test:** ✅ PASSED / ❌ FAILED  

---

## Next Steps

After Section 15 verification:
1. Proceed to Section 16 - CI/CD Gates
2. Implement GitHub Actions workflows
3. Configure branch protection rules
4. Generate Section 16 proof pack
