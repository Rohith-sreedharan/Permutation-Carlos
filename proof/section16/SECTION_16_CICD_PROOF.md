# SECTION 16 — CI/CD GOVERNANCE: EVIDENCE PACKAGE

**Status:** LOCKED  
**Lock Date:** 2026-03-07  
**Final Commit:** `e77feec8d519bba1667cc265035aecdf25b661c1`  

---

## 1. Test Suite Results

**File:** `test_suite_output.txt`

### Summary:
- **23 tests passed** in 0.82 seconds
- **0 failures**

### Tests Executed:
| Test File | Tests | Result |
|-----------|-------|--------|
| test_odds_alignment_gate.py | 9 | ✅ ALL PASSED |
| test_section_15_version_control.py | 14 | ✅ ALL PASSED |

### Key Tests:
1. `test_line_delta_exact_match_approved` - PASSED
2. `test_line_delta_within_tolerance_approved` - PASSED
3. `test_line_delta_exceeds_tolerance_blocked` - PASSED
4. `test_pickem_symmetry_pass` - PASSED
5. `test_pickem_symmetry_block` - PASSED
6. `test_boundary_0_25_exactly_passes` - PASSED
7. `test_boundary_0_25001_blocks` - PASSED
8. `test_boundary_prob_delta_0_0200_passes` - PASSED
9. `test_lifecycle_order_odds_before_classification` - PASSED
10. `test_version_format_validation` - PASSED
11. `test_cache_hit_returns_decision` - PASSED
12. `test_verify_determinism_success` - PASSED
13. `test_cache_statistics` - PASSED

---

## 2. CI Pipeline Status

**File:** `ci_pipeline_status.json`

### Last Known GREEN Build (commit ab0118e):
| Workflow | Status | Run ID |
|----------|--------|--------|
| Engine Tests + Schema Validation | ✅ SUCCESS | 22469926967 |
| UI Tests (Build + Playwright) | ✅ SUCCESS | 22469926971 |
| Security Scan | ✅ SUCCESS | 22469926972 |

### CI Run Links:
- [Engine Tests](https://github.com/Rohith-sreedharan/Permutation-Carlos/actions/runs/22469926967) - ✅ SUCCESS
- [UI Tests](https://github.com/Rohith-sreedharan/Permutation-Carlos/actions/runs/22469926971) - ✅ SUCCESS
- [Security Scan](https://github.com/Rohith-sreedharan/Permutation-Carlos/actions/runs/22469926972) - ✅ SUCCESS

**Note:** Commit e77feec CI failed due to GitHub account billing lock (not code issue). Local tests pass 23/23.

---

## 3. Live API Sanity Check

**Files:** 
- `live_sanity_ad1dc68e.json` (MIN vs ORL)
- `live_sanity_d2465617.json` (ATL vs PHI)
- `live_sanity_d504db90.json` (DET vs BKN)

### Results:
| Game | Spread | Total | Status |
|------|--------|-------|--------|
| Minnesota Timberwolves vs Orlando Magic | EDGE | EDGE | ✅ APPROVED |
| Atlanta Hawks vs Philadelphia 76ers | EDGE | EDGE | ✅ APPROVED |
| Detroit Pistons vs Brooklyn Nets | EDGE | EDGE | ✅ APPROVED |

**Verification:**
- 0 contradictions
- 0 BLOCKED_BY_INTEGRITY
- 0 selection_id mismatches
- Decision version: 6.1.1 (consistent across all)

---

## 4. Commit History (Section 16 Fixes)

| Commit | Description |
|--------|-------------|
| `e77feec` | FIX: Correct decision_version type in GameDecisions (str not int) + Fix audit.py import |
| `ab0118e` | FIX: Remove invalid +00:00Z double timezone suffix (ROOT CAUSE FIX #6) |
| `ff2b8c7` | FIX: Remove workflow path filters + fix timezone-aware datetime (INSTITUTIONAL FIX #5) |
| `e1d5b04` | FIX: Make datetime comparison timezone-naive in freshness validation |
| `2ade658` | FIX: Replace ALL remaining datetime.UTC with timezone.utc |
| `b984dca` | FIX: Correct timezone import - use timezone.utc not datetime.UTC |
| `6792708` | FIX: Make summary jobs non-skippable - add if:always and explicit result checking |
| `f7feaf7` | FIX: Remove workflow path filters to prevent required check bypass |
| `7e0ef33` | FIX: Make all-gates-passed non-skippable + replace deprecated datetime.utcnow() |
| `175f868` | FIX: Allow pick'em markets (line=0) in validator (INSTITUTIONAL FIX #4) |
| `bcb405b` | FIX: Correct pick'em test data and MongoDB connection handling |

---

## 5. Architecture Verification

### 5.1 compute_market_decision is ONLY compute path
- **Evidence:** Single import at `backend/routes/decisions.py:17`
- No alternative compute paths exist

### 5.2 validate_market_decision runs on every decision
- **Evidence:** Called at lines 239 (spread) and 342 (total) in `compute_market_decision.py`
- Blocks with `BLOCKED_BY_INTEGRITY` if validation fails

### 5.3 baseline/sharp_analysis deleted
- **Evidence:** Commit `81ec91e` deleted `sharp_analysis.py` (608 lines)
- Architecturally replaced with `compute_market_decision.py`

### 5.4 No bypass logic
- Searched for: `SKIP_VALIDATION`, `BYPASS_GATE`, `relaxed_threshold`
- **Result:** None found
- Only legitimate patterns: `DISABLE_TELEGRAM` (safety feature), `skip_fatigue` (1H adjustment)

---

## 6. CI/CD Infrastructure

### Workflows:
1. **Engine Tests + Schema Validation** (`.github/workflows/engine-tests.yml`)
   - Backend Unit Tests
   - Backend Integration Tests (Smoke)
   - Section 15 Determinism Verification
   - API Response Contract Validation
   - Schema Validation Gate
   - All Gates Passed ✅ (non-skippable)

2. **UI Tests** (`.github/workflows/ui-tests.yml`)
   - Build
   - Playwright E2E Tests
   - Accessibility Audit
   - UI All-Gates-Passed ✅ (non-skippable)

3. **Security Scan** (`.github/workflows/security.yml`)
   - Credential detection
   - Dependency audit
   - Security All-Gates-Passed ✅ (non-skippable)

### Branch Protection:
- All 3 "All Gates Passed" jobs are non-skippable (`if: always()`)
- Explicit result checking prevents false positives

---

## CERTIFICATION

This evidence package certifies that Section 16 CI/CD Governance requirements are met:

- ✅ All 23 unit tests pass locally
- ✅ CI pipeline architecture verified (14 gates)
- ✅ All summary jobs non-skippable
- ✅ Live API sanity check passed (3 games, 0 errors)
- ✅ No bypass logic or temporary flags
- ✅ Root causes fixed, not patched

**SECTION 16 — CI/CD GOVERNANCE: LOCKED**

---

*Generated: 2026-03-07*  
*Lock Commit: e77feec8d519bba1667cc265035aecdf25b661c1*
