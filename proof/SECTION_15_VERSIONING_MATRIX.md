# Section 15: Version Control - Versioning Matrix

**ENGINE LOCK Specification v2.0.0 - Section 15 Compliance**

## SEMVER Format: MAJOR.MINOR.PATCH

### Version Bump Rules (Operator-Controlled)

| Bump Type | When to Use | Effect | Example Scenario |
|-----------|-------------|--------|-----------------|
| **MAJOR** | Breaking changes to thresholds, formulas, or schema | Increment MAJOR, reset MINOR and PATCH to 0 | Change edge classification thresholds from [0-1.5, 1.5-3.0, 3.0+] to [0-2.0, 2.0-4.0, 4.0+] |
| **MINOR** | Additive rule changes or new features (non-breaking) | Increment MINOR, reset PATCH to 0 | Add new validation gate without changing existing logic |
| **PATCH** | Bug fixes only (no logic changes) | Increment PATCH only | Fix rounding error in edge calculation |

---

## Version History

### v2.0.0 (Initial ENGINE LOCK Version)
**Date:** 2026-02-19  
**Type:** MAJOR (Initial Release)  
**Updated By:** system  
**Description:** Initial ENGINE LOCK version after Section 14 completion - Section 15 Version Control implementation  

**Changes:**
- ✅ Section 14: Audit Logging (100% LOCKED)
- ✅ MongoDB append-only enforcement with role-based access control
- ✅ 7-year retention policy implementation
- ✅ HTTP 500 on audit write failure
- ✅ Section 15: Version Control implementation
- ✅ SEMVER format (MAJOR.MINOR.PATCH)
- ✅ Deterministic replay cache
- ✅ Git commit SHA traceability

**Rationale:**
- Baseline version for ENGINE LOCK specification compliance
- Establishes semantic versioning foundation for all future changes
- Deterministic replay ensures identical inputs → identical outputs
- Version traceability enables forensic analysis and debugging

---

## Version Bump Examples

### Example 1: MAJOR Bump (Breaking Change)
**Scenario:** Changing edge classification thresholds

**Before (v2.0.0):**
```python
def _classify_spread(edge_points: float) -> Classification:
    if edge_points >= 3.0:
        return Classification.EDGE
    elif edge_points >= 1.5:
        return Classification.LEAN
    else:
        return Classification.MARKET_ALIGNED
```

**After (v3.0.0):**
```python
def _classify_spread(edge_points: float) -> Classification:
    if edge_points >= 4.0:  # Changed threshold
        return Classification.EDGE
    elif edge_points >= 2.0:  # Changed threshold
        return Classification.LEAN
    else:
        return Classification.MARKET_ALIGNED
```

**Version Bump Command:**
```python
get_version_manager().bump_version(
    bump_type="major",
    updated_by="ops_team@beatvegas.com",
    change_description="Breaking change: Updated edge classification thresholds (EDGE: 3.0→4.0, LEAN: 1.5→2.0)"
)
# Result: 2.0.0 → 3.0.0
```

**Impact:**
- Same inputs will produce different classifications
- Historical comparisons must account for threshold change
- Audit logs will show version change for forensic analysis

---

### Example 2: MINOR Bump (Additive Change)
**Scenario:** Adding new validation gate without changing existing logic

**Before (v2.0.0):**
```python
# Validation gates:
# 1. Directional Integrity
# 2. Odds Alignment
# 3. Freshness
```

**After (v2.1.0):**
```python
# Validation gates:
# 1. Directional Integrity
# 2. Odds Alignment
# 3. Freshness
# 4. Liquidity Check (NEW - additive only)
if market_liquidity < MIN_LIQUIDITY_THRESHOLD:
    return BLOCKED_BY_LOW_LIQUIDITY
```

**Version Bump Command:**
```python
get_version_manager().bump_version(
    bump_type="minor",
    updated_by="ops_team@beatvegas.com",
    change_description="Additive change: Added liquidity validation gate (non-breaking)"
)
# Result: 2.0.0 → 2.1.0
```

**Impact:**
- Some decisions may now be BLOCKED that were previously APPROVED
- Existing approved decisions remain valid
- Additive rule does not change existing classification logic

---

### Example 3: PATCH Bump (Bug Fix)
**Scenario:** Fixing rounding error in edge calculation

**Before (v2.0.0):**
```python
edge_points = abs(market_line - model_fair_line)  # Missing rounding
```

**After (v2.0.1):**
```python
edge_points = round(abs(market_line - model_fair_line), 2)  # Fixed precision
```

**Version Bump Command:**
```python
get_version_manager().bump_version(
    bump_type="patch",
    updated_by="ops_team@beatvegas.com",
    change_description="Bug fix: Added rounding to edge_points calculation (2 decimal precision)"
)
# Result: 2.0.0 → 2.0.1
```

**Impact:**
- Minimal behavioral change (precision only)
- No logic changes to classification or validation
- Identical inputs may produce slightly different edge_points due to rounding

---

## Determinism Guarantee

### Requirement A: decision_version = SEMVER
✅ **COMPLIANCE:** decision_version field returns SEMVER format (e.g., "2.0.0")  
✅ **VERIFICATION:** See [backend/core/market_decision.py](../backend/core/market_decision.py) Debug model

### Requirement B: Identical inputs → Identical outputs + Identical decision_version
✅ **COMPLIANCE:** Deterministic replay cache ensures byte-identical outputs  
✅ **VERIFICATION:** See test `test_identical_inputs_return_identical_outputs` in [test_section_15_version_control.py](../backend/tests/test_section_15_version_control.py)

### Requirement C: Operator-controlled version increments
✅ **COMPLIANCE:** Version bumps require explicit operator call to `bump_version()`  
✅ **VERIFICATION:** No automatic version changes on deployment

### Requirement D: Deterministic replay proof
✅ **COMPLIANCE:** See [SECTION_15_DETERMINISM_PASS.json](./SECTION_15_DETERMINISM_PASS.json)  
✅ **VERIFICATION:** Multiple calls with identical inputs produce identical outputs

### Requirement E: Version history traceability
✅ **COMPLIANCE:** engine_version + decision_version + git_commit_sha in audit logs  
✅ **VERIFICATION:** See [decision_audit_logger.py](../backend/db/decision_audit_logger.py) log_decision()

---

## Excluded Fields from Determinism Comparison

The following fields are **allowed to differ** between identical input calls:

| Field | Reason | Example |
|-------|--------|---------|
| `timestamp` | Reflects actual computation time | "2026-02-19T12:00:00Z" vs "2026-02-19T12:05:00Z" |
| `trace_id` | Unique per request for audit trail | "abc-123" vs "def-456" |
| `cached_at` | Cache metadata | "2026-02-19T10:00:00Z" vs "2026-02-19T11:00:00Z" |

All other fields MUST be byte-identical for determinism compliance.

---

## Version Traceability Chain

Every decision includes complete version metadata:

```json
{
  "debug": {
    "decision_version": "2.0.0",
    "git_commit_sha": "a3f7c92",
    "engine_version": "2.0.0",
    "trace_id": "uuid-for-request",
    "computed_at": "2026-02-19T12:00:00Z"
  }
}
```

**Audit Log Entry:**
```json
{
  "event_id": "nba_game_12345",
  "decision_version": "2.0.0",
  "git_commit_sha": "a3f7c92",
  "engine_version": "2.0.0",
  "trace_id": "uuid-for-request",
  "timestamp": "2026-02-19T12:00:00Z"
}
```

This enables:
- Forensic analysis: What version produced this decision?
- Reproducibility: Checkout git commit + replay inputs
- Debugging: Trace decision through audit logs
- Compliance: 7-year retention with full version history

---

## Section 15 Certification

✅ **REQUIREMENT A:** decision_version = SEMVER (MAJOR.MINOR.PATCH)  
✅ **REQUIREMENT B:** Identical inputs → Identical outputs + Identical decision_version  
✅ **REQUIREMENT C:** Operator-controlled version increments (no auto-bumps)  
✅ **REQUIREMENT D:** Deterministic replay proof artifacts generated  
✅ **REQUIREMENT E:** Version history traceable (engine_version + decision_version + git_commit_sha)  

✅ **UNIT TESTS:** 14/14 passed (version validation, bump rules, deterministic cache)  
✅ **PROOF ARTIFACTS:** [SECTION_15_DETERMINISM_PASS.json](./SECTION_15_DETERMINISM_PASS.json)  

**STATUS:** Section 15 - Version Control - **100% COMPLETE - READY FOR LOCK**
