#!/usr/bin/env bash
set -euo pipefail

ROOT=/home/ubuntu/Permutation-Carlos
OUT=$ROOT/proof_batch_screenshots/phase13/oracle_evidence
mkdir -p "$OUT"

echo "[1/12] Service status + health" | tee "$OUT/00_progress.log"
systemctl status beatvegas > "$OUT/01_systemctl_status.txt" 2>&1 || true
curl -sS https://beta.beatvegas.app/api/health > "$OUT/02_beta_health.json"

echo "[2/12] Rate limit discovery" | tee -a "$OUT/00_progress.log"
grep -r "rate_limit\|RateLimit\|slowapi\|limiter\|Limiter\|429\|throttle" \
  "$ROOT/backend/middleware/" \
  "$ROOT/backend/main.py" \
  "$ROOT/backend/routes/" \
  --include="*.py" -l > "$OUT/03_rate_limit_files.txt"
cp "$ROOT/backend/config/agent_config.py" "$OUT/04_agent_config_snapshot.py"
cp "$ROOT/backend/middleware/rate_limiter.py" "$OUT/05_rate_limiter_snapshot.py"

echo "[3/12] Directive Step 4A dashboard triage commands" | tee -a "$OUT/00_progress.log"
cd "$ROOT/backend"
source .venv/bin/activate
python3 -c "
from db.mongo import db
count = db.decision_records.count_documents({})
recent = list(db.decision_records.find({}, {\"game_id\":1,\"classification\":1,\"release_status\":1,\"created_at\":1}).sort(\"created_at\",-1).limit(3))
print(f\"Total: {count}\")
for d in recent: print(d)
" > "$OUT/06_dashboard_cmd1_decisions_shape.txt" 2>&1

if [[ -n "${PHASE13_JWT:-}" ]]; then
  curl https://beta.beatvegas.app/api/v1/decisions -H "Authorization: Bearer ${PHASE13_JWT}" -v 2>&1 | tail -40 > "$OUT/07_dashboard_cmd2_decisions_api_tail40.txt"
else
  echo "PHASE13_JWT not set" > "$OUT/07_dashboard_cmd2_decisions_api_tail40.txt"
fi

grep -r "decisions\|getDecisions\|fetchDecisions" \
  "$ROOT/services/" \
  --include="*.ts" --include="*.tsx" | head -10 > "$OUT/08_dashboard_cmd3_frontend_url_refs.txt"

echo "[4/12] Subscription none shape test" | tee -a "$OUT/00_progress.log"
python3 - <<'PY' > "$OUT/09_subscription_none_shape_test.txt" 2>&1
import time, requests
base = "https://beta.beatvegas.app"
email = f"phase13_none_{int(time.time())}@example.com"
pwd = "Phase13Temp!123"
r = requests.post(f"{base}/api/v1/auth/register", json={"email": email, "password": pwd, "username": "phase13none"}, timeout=30)
print("register", r.status_code, r.text)
t = requests.post(f"{base}/api/v1/token", data={"username": email, "password": pwd}, timeout=30)
print("token", t.status_code)
tok = t.json().get("access_token", "")
s = requests.get(f"{base}/api/v1/subscription/status", headers={"Authorization": f"Bearer {tok}"}, timeout=30)
print("status", s.status_code, s.text)
PY

echo "[5/12] Prohibited-language grep exact command" | tee -a "$OUT/00_progress.log"
grep -r -i "\bbet\b\|\bwager\b\|\bgambl\|\bodds\b\|\bpick\b\|\bhandicap\b\|\bsportsbook\b" \
  "$ROOT/components/" \
  "$ROOT/src/" \
  "$ROOT/uiCopy/" \
  --include="*.tsx" --include="*.ts" --include="*.js" --include="*.json" \
  | grep -v "node_modules\|\.git\|test\|spec\|BeatVegas\|beatvegas\|NotASportsbook\|not.*sportsbook\|no.*bet\|no_bet\|no-bet" \
  > "$OUT/10_prohibited_language_raw.txt" || true

echo "[6/12] Sentinel non-canonical entries" | tee -a "$OUT/00_progress.log"
python3 -c "
from db.mongo import db
import re
pattern = re.compile(r'^agent\\.[a-z]+\\.v[0-9]+$')
all_entries = list(db.sentinel_event_log.find({\"agent_id\": {\"$exists\": True}}, {\"agent_id\":1, \"event_type\":1, \"created_at\":1, \"severity\":1}))
non_canonical = [e for e in all_entries if not pattern.match(str(e.get(\"agent_id\", \"\")))]
print(f\"Non-canonical entries: {len(non_canonical)}\")
for e in non_canonical:
    print(e)
" > "$OUT/11_non_canonical_sentinel.txt" 2>&1

echo "[7/12] Section 13.7 evidence" | tee -a "$OUT/00_progress.log"
python3 - <<'PY' > "$OUT/12_section_13_7_core_logs.txt" 2>&1
from db.mongo import db
stages = [
  "DECISION_COMPUTED","PUBLISHED","GRADE_PENDING","GRADED","CALIBRATED",
  "DISTRIBUTED","SETTLED","AUDITED","ARCHIVED"
]
print("prediction_lifecycle_log total", db.prediction_lifecycle_log.count_documents({}))
for s in stages:
  c = db.prediction_lifecycle_log.count_documents({"stage": s})
  print(s, c)
print("assertion_failure_log total", db.assertion_failure_log.count_documents({}))
PY

grep -R "datetime\.now\(" "$ROOT/backend" --include="*.py" > "$OUT/13_datetime_now_grep.txt" || true

echo "[8/12] Section 13.8/13.9/13.10/13.11/13.12/13.13 mapped test suite" | tee -a "$OUT/00_progress.log"
pytest -q "$ROOT/backend/tests/test_phase13_entitlement_billing.py" -q > "$OUT/14_tests_13_8_syndicate.txt" 2>&1 || true
pytest -q "$ROOT/backend/tests/test_phase13_parlay_extended.py" -q > "$OUT/15_tests_13_9_parlay.txt" 2>&1 || true
pytest -q "$ROOT/backend/tests/test_phase13_affiliate_system.py" -q > "$OUT/16_tests_13_10_affiliate.txt" 2>&1 || true
pytest -q "$ROOT/backend/tests/test_phase13_security.py" -q > "$OUT/17_tests_13_11_compliance.txt" 2>&1 || true
pytest -q "$ROOT/backend/tests/test_phase13_billing_extended.py" -q > "$OUT/18_tests_13_12_billing_edges.txt" 2>&1 || true
pytest -q "$ROOT/backend/tests/test_distribution_governance_service.py" -q > "$OUT/19_tests_13_13_agent_coordination.txt" 2>&1 || true

echo "[9/12] Load test evidence pointers" | tee -a "$OUT/00_progress.log"
ls -lah "$ROOT/proof_batch_screenshots/phase13"/*load* > "$OUT/20_existing_load_artifacts.txt" 2>&1 || true

echo "[10/12] Sidebar developer-tab source proof" | tee -a "$OUT/00_progress.log"
grep -n "For Developers\|VITE_SIMSPORTS_LIVE" "$ROOT/components/Sidebar.tsx" > "$OUT/21_for_developers_source.txt" 2>&1 || true

echo "[11/12] Package manifest" | tee -a "$OUT/00_progress.log"
find "$OUT" -maxdepth 1 -type f | sort > "$OUT/22_manifest.txt"

echo "[12/12] DONE" | tee -a "$OUT/00_progress.log"
