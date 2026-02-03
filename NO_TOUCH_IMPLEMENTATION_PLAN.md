# NO-TOUCH PRODUCTION SYSTEM — IMPLEMENTATION PLAN

**Generated:** February 2, 2026  
**Spec Source:** BeatVegas Final Locked Dev Brief (19 pages)  
**Status:** Master plan + gap analysis

---

## 📊 Gap Analysis: What Exists vs What's Needed

### ✅ Already Built (From Previous Work)

**Grading Architecture v2.0:**
- ✅ `backend/services/unified_grading_service_v2.py` (750 lines)
  - Rules versioning (settlement_rules_version, clv_rules_version)
  - Idempotency key generation
  - Score payload reference
  - Provider drift detection
  - Ops alerts (PROVIDER_ID_MISSING, CLOSE_SNAPSHOT_MISSING, MAPPING_DRIFT)

**Integrity Hard-Lock Patch:**
- ✅ `backend/services/pick_integrity_validator.py` (750 lines)
  - Selection ID validation
  - Snapshot identity validation
  - Probability consistency checks
  - Canonical action payload structure
  - Opposite selection resolver
- ✅ `backend/services/parlay_eligibility_gate.py` (200 lines)
- ✅ `backend/services/writer_matrix_enforcement.py` (400 lines)

**Database:**
- ✅ `backend/db/indexes.py` — Index management
- ✅ `backend/db/mongo.py` — MongoDB connection
- ✅ Grading collection with idempotency
- ✅ Events collection with provider_event_map.oddsapi.event_id

**Existing Services:**
- ✅ OddsAPI integration (`backend/integrations/odds_api.py`)
- ✅ Result service (score fetching)
- ✅ Pick creation logic (needs refactor to match new schema)

---

### ❌ Missing Components (Must Build)

**Core Platform (Tier 1 - Critical Path):**

1. **Multi-Tenant Foundation** ❌
   - `tenant` table (tenant_id, type, status)
   - `user` table (user_id, tenant_id, email, telegram_user_id)
   - Tenant isolation in ALL services
   - Tenant-scoped queries by default

2. **Entitlements + Billing** ❌
   - `entitlement` table (FINAL schema with PAY_PER_USE tiers)
   - `rate_limit_policy` table
   - `billing_ledger` table (source of truth for charges)
   - Billing engine (idempotent ledger writes)
   - Entitlement gating service
   - Rate limiting middleware

3. **Canonical Mapping Service** ❌
   - `team` table (team_id, source_team_map)
   - `selection` table (selection_id, side, label_template)
   - Normalize vendor events → canonical IDs
   - Deterministic selection creation
   - MAPPING_DRIFT detection

4. **Immutable Snapshots** ❌
   - `market_snapshot` table (immutable)
   - `raw_payload_blob` table (for replay)
   - Snapshot creation service (never update existing)
   - Staleness monitoring

5. **Pick Lifecycle State Machine** ❌
   - `pick` table (FINAL schema with all fields)
   - State transition enforcement (PROPOSED → PUBLISHED → GRADED)
   - `pick_line_tracking` table (CLV tracking)
   - Idempotency enforcement (unique constraint)

6. **Configuration Management** ❌
   - `league_config` table (all thresholds config-driven)
   - `config_version` table (version league configs)
   - Attach config_version_id to every pick
   - Config change tracking

7. **Governance Layer** ❌
   - `audit_log` table (append-only)
   - State hash tracking (before/after)
   - Role-based access control
   - Admin vs OPS vs SYSTEM separation

**Engine Pipeline (Tier 2 - Core Flows):**

8. **Provider Interface Abstraction** ❌
   - `MarketDataProvider` interface
   - `InjuryProvider` interface (placeholder OK for Phase 0)
   - `ResultsProvider` interface (placeholder OK for Phase 0)
   - OddsAPI adapter (refactor existing to interface)
   - Healthcheck + staleness monitoring

9. **Validity Engine** ❌
   - Line movement monitoring
   - validity_state transitions (VALID → MOVED_BUT_OK → INVALIDATED)
   - REFRESH_RECOMMENDED detection
   - CLV tracking (open/best/close snapshots)

10. **Unified Pick Publisher** ❌
    - Generate App + Telegram from SAME pick_id
    - Store telegram_message_id in pick
    - Feature flag enforcement (PUBLISH_ENABLED_*)
    - Supersede mechanism (pick_version)

11. **Grading Integration** ❌
    - Use existing UnifiedGradingService
    - Ensure oddsapi_event_id used for score lookup
    - Reconciliation job for missing finals
    - Transition pick → GRADED

**Monitoring + Ops (Tier 3 - Operational Excellence):**

12. **Ops Alerts (Enhanced)** ❌
    - All required alert types (FEED_STALE, SIM_FAIL, DIRECTION_MISMATCH, etc.)
    - Auto-disable publishing on critical alerts
    - Degrade modes (FULL → EDGE_ONLY → NONE)

13. **Feature Flags** ❌
    - `feature_flag` table (scope: GLOBAL, TENANT, LEAGUE, MARKET)
    - Required flags (PUBLISH_ENABLED_*, LEAGUE_ENABLED_*, MARKET_ENABLED_*)
    - Runtime flag checking

14. **Kill Switches** ❌
    - Auto-disable on provider healthcheck failure
    - Auto-disable on staleness threshold breach
    - Manual kill switch for emergency

15. **Replay + Backfill** ❌
    - Reconstruct picks from raw_payload_blob
    - Re-grade historical picks with version tags
    - Re-run calibration for time windows

**Analytics + Data Moat (Tier 4 - Value Unlock):**

16. **Analytics Layer** ❌
    - `analytics_event_fact` table (daily rollups)
    - ROI by tier, calibration metrics, CLV hit rate
    - Drift monitoring (nightly job)
    - `data_products_catalog` table

17. **Data Export Layer** ❌
    - Tenant-scoped data products
    - Aggregated datasets (CLV curves, efficiency metrics)
    - Read-only export service

---

## 🎯 Implementation Priority

### Phase 0: Foundation (Week 1-2)

**Goal:** Multi-tenant platform with entitlements, canonical mapping, immutable snapshots

1. **Database schema updates** (all tables)
2. **Tenant isolation** (tenant_id everywhere)
3. **Canonical mapping service** (team, selection, event normalization)
4. **Immutable snapshot service** (market_snapshot, raw_payload_blob)
5. **Entitlement + billing engine** (billing_ledger with idempotency)
6. **Configuration management** (league_config, config_version)

**Acceptance:**
- ✅ All tables exist with proper indexes
- ✅ Tenant-scoped queries work
- ✅ Canonical event/team/selection IDs generated
- ✅ Snapshots are immutable (create-only)
- ✅ Billing ledger writes are idempotent
- ✅ Config changes are versioned

---

### Phase 1: Pick Lifecycle (Week 3-4)

**Goal:** End-to-end pick flow with state machine, validity tracking, CLV

1. **Pick table (FINAL schema)** with all fields
2. **Pick lifecycle state machine** enforcement
3. **Provider interface abstraction** (MarketDataProvider, etc.)
4. **Validity engine** (line movement, validity_state transitions)
5. **CLV tracking** (pick_line_tracking with open/best/close)
6. **Unified pick publisher** (App + Telegram from pick_id)

**Acceptance:**
- ✅ Pick lifecycle transitions enforced
- ✅ Idempotency prevents duplicate picks
- ✅ Validity state tracks line movement
- ✅ CLV captured deterministically
- ✅ Single publisher generates App + Telegram

---

### Phase 2: Governance + Ops (Week 5)

**Goal:** Monitoring, alerts, kill switches, audit trail

1. **Audit log** (append-only, state hashing)
2. **Ops alerts** (all required types)
3. **Feature flags** (runtime enforcement)
4. **Kill switches** (auto-disable publishing)
5. **Monitoring dashboards** (provider health, staleness, grading lag)
6. **Replay + backfill** (reconstruct from raw payloads)

**Acceptance:**
- ✅ All state changes logged in audit_log
- ✅ Ops alerts trigger auto-disable
- ✅ Feature flags control publishing/grading
- ✅ Kill switches work instantly
- ✅ Backfill reconstructs last 7 days

---

### Phase 3: Analytics + Data Moat (Week 6-7)

**Goal:** Data products, drift monitoring, B2B readiness

1. **Analytics rollups** (analytics_event_fact daily)
2. **Drift monitoring** (ROI anomaly, calibration drift)
3. **Data export layer** (tenant-scoped products)
4. **Data products catalog** (materialized queries)
5. **B2B tenant configs** (custom thresholds, SLA-backed)

**Acceptance:**
- ✅ Daily analytics rollups running
- ✅ Drift monitoring alerts on anomalies
- ✅ Data products available for export
- ✅ B2B tenants isolated with custom configs

---

## 📐 Database Schema Implementation Order

### Round 1: Core Entities

```sql
-- Priority 1
CREATE TABLE tenant (...)
CREATE TABLE user (...)
CREATE TABLE entitlement (...)
CREATE TABLE rate_limit_policy (...)
CREATE TABLE billing_ledger (...)

-- Priority 2
CREATE TABLE team (...)
CREATE TABLE event (...)
CREATE TABLE selection (...)

-- Priority 3
CREATE TABLE market_snapshot (...)
CREATE TABLE raw_payload_blob (...)
```

### Round 2: Picks + Tracking

```sql
CREATE TABLE pick (...)
CREATE TABLE pick_line_tracking (...)
CREATE TABLE simulation_run (...)
CREATE TABLE market_evaluation (...)
```

### Round 3: Governance + Config

```sql
CREATE TABLE config_version (...)
CREATE TABLE league_config (...)
CREATE TABLE audit_log (...)
CREATE TABLE ops_alert (...)
CREATE TABLE feature_flag (...)
```

### Round 4: Analytics

```sql
CREATE TABLE analytics_event_fact (...)
CREATE TABLE data_products_catalog (...)
```

---

## 🔄 Integration with Existing Work

### Grading Architecture v2.0 → New Schema

**Existing:**
- `grading` collection with `grading_idempotency_key`, `settlement_rules_version`, `clv_rules_version`

**Integration:**
- ✅ Keep existing grading collection
- ✅ Add `pick_id` FK to grading (link to new pick table)
- ✅ UnifiedGradingService transitions pick → GRADED
- ✅ Use oddsapi_event_id for exact score lookup

### Integrity Validator → Pick Creation

**Existing:**
- `PickIntegrityValidator` validates selection IDs, snapshot identity, probability consistency

**Integration:**
- ✅ Call validator before pick creation (PROPOSED state)
- ✅ Block pick creation if violations detected
- ✅ Emit ops_alert for INTEGRITY_BLOCKED picks

### Provider Event Map → Canonical Mapping

**Existing:**
- `provider_event_map.oddsapi.event_id` stored in events collection

**Integration:**
- ✅ Migrate to `event.oddsapi_event_id` field (required)
- ✅ Add `event.source_event_map` JSON for future providers
- ✅ Canonical Mapping Service creates event with both fields

---

## 🚀 Quick Start: Phase 0 Implementation

### Step 1: Database Schema (Day 1-2)

Create all core tables:
- `backend/db/schema_v2.py` (new file with all table definitions)
- `backend/db/migrations/001_no_touch_schema.py` (migration script)

### Step 2: Tenant Isolation (Day 3-4)

- Add `tenant_id` to all relevant tables
- Implement tenant-scoped query helpers
- Add tenant validation to service layer

### Step 3: Canonical Mapping (Day 5-7)

- Implement `CanonicalMappingService`
- Normalize events/teams → canonical IDs
- Create selections deterministically

### Step 4: Entitlements + Billing (Day 8-10)

- Implement `EntitlementService`
- Implement `BillingEngine` with idempotent ledger writes
- Add rate limiting middleware

### Step 5: Immutable Snapshots (Day 11-12)

- Implement `SnapshotService` (create-only)
- Store raw payloads in `raw_payload_blob`
- Enforce immutability constraints

### Step 6: Configuration (Day 13-14)

- Implement `ConfigurationService`
- Version league configs
- Attach config_version_id to picks

---

## ✅ Definition of Done (Full System)

### Core Platform

- [ ] All database tables created with indexes
- [ ] Tenant isolation enforced (queries, services)
- [ ] Entitlements + billing working (idempotent ledger)
- [ ] Rate limiting enforced per tenant
- [ ] Canonical mapping creates deterministic IDs
- [ ] Snapshots are immutable (create-only)
- [ ] Configuration is versioned

### Engine Pipeline

- [ ] Provider interfaces abstracted
- [ ] Pick lifecycle state machine enforced
- [ ] Validity engine tracks line movement
- [ ] CLV captured deterministically
- [ ] Unified publisher (App + Telegram from pick_id)
- [ ] Grading transitions pick → GRADED

### Governance + Ops

- [ ] Audit log tracks all state changes
- [ ] Ops alerts emit on all required events
- [ ] Feature flags control runtime behavior
- [ ] Kill switches auto-disable publishing
- [ ] Replay/backfill works for last 7 days

### Analytics + Data Moat

- [ ] Daily analytics rollups running
- [ ] Drift monitoring alerts on anomalies
- [ ] Data products available for B2B
- [ ] Tenant-scoped exports working

### Acceptance Tests

- [ ] No contradictory team display (selection lock)
- [ ] Idempotency prevents duplicate picks
- [ ] Lifecycle transitions enforced
- [ ] Grading ≥99% within SLA
- [ ] Kill switches work instantly
- [ ] Tenant isolation verified

---

## 📋 File Structure (New)

```
backend/
  db/
    schema_v2.py                      ← All table definitions
    migrations/
      001_no_touch_schema.py          ← Migration script
  
  services/
    tenant_service.py                 ← Tenant management
    entitlement_service.py            ← Entitlement checking
    billing_engine.py                 ← Billing ledger (idempotent)
    canonical_mapping_service.py      ← Event/team/selection normalization
    snapshot_service.py               ← Immutable snapshot creation
    configuration_service.py          ← Config versioning
    validity_engine.py                ← Line movement + CLV
    pick_publisher.py                 ← Unified App + Telegram
    audit_service.py                  ← Audit log writes
    feature_flag_service.py           ← Feature flag runtime
    
  providers/
    base.py                           ← Provider interfaces
    oddsapi_adapter.py                ← OddsAPI implementation
    sportradar_adapter.py             ← Placeholder for Phase 1
    
  jobs/
    ingest_job.py                     ← Odds ingest every 60s
    validity_check_job.py             ← Every 2 minutes
    publish_job.py                    ← Every 5 minutes
    grading_job.py                    ← After games end
    drift_monitoring_job.py           ← Nightly
    
  tests/
    test_tenant_isolation.py
    test_entitlement_gating.py
    test_canonical_mapping.py
    test_pick_lifecycle.py
    test_clv_tracking.py
```

---

## 🎯 Success Metrics

### Week 2 (Phase 0 Complete)

- ✅ All core tables exist
- ✅ Tenant-scoped queries work
- ✅ Billing ledger idempotent
- ✅ Canonical IDs generated

### Week 4 (Phase 1 Complete)

- ✅ Pick lifecycle working end-to-end
- ✅ Validity tracking functional
- ✅ CLV captured deterministically
- ✅ Unified publisher live

### Week 5 (Phase 2 Complete)

- ✅ Audit trail complete
- ✅ Ops alerts auto-disable publishing
- ✅ Kill switches functional

### Week 7 (Phase 3 Complete)

- ✅ Analytics rollups daily
- ✅ Data products exportable
- ✅ B2B tenants isolated

---

**Total Implementation:** 7 weeks (aggressive timeline)  
**Files to Create:** 30+ new files  
**Lines of Code:** 10,000+ lines  
**Database Tables:** 20+ tables

**Status:** Plan complete, ready to start Phase 0 implementation ✅
