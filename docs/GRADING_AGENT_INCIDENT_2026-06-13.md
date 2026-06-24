# Grading Agent Incident - 2026-06-13

Production host: root@67.207.93.88
Path: /root/Permutation-Carlos

## Requested diagnostics (verbatim outputs)

### 1) agent.grading.v1 existence check
find backend/ -name "*.py" | xargs grep -l "agent.grading.v1\|grading_agent\|GradingAgent" 2>/dev/null

Output:
backend/scripts/generate_phase4_evidence.py
backend/services/phase4_grading_engine.py
backend/services/phase4_grading_agent.py
backend/services/phase8_observability_metrics.py
backend/routes/phase8_routes.py
backend/routes/phase4_grading_agent_routes.py
backend/main.py
backend/config/agent_config.py
backend/tests/phase4_ci_gates.py

### 2) Is decision_settlement_metrics populated?
Output:
graded: 1

### 3) Are DecisionRecords being created?
Output:
decisions: 1912

### 4) Is the OddsAPI results endpoint configured?
Command used:
grep -rn "results\|ResultsProvider\|game_result\|final_score" backend/ --include="*.py" | grep -v ".venv|test" | head -20

Output:
backend/core/tier_classification_adapter.py:7:the universal classifier, and returns classification results.
backend/core/tier_classification_adapter.py:188:    results = {}
backend/core/tier_classification_adapter.py:191:        results[market_type] = classify_simulation(
backend/core/tier_classification_adapter.py:198:    return results
backend/core/tier_classification_adapter.py:221:    all_results = []
backend/core/tier_classification_adapter.py:226:        game_results = classify_all_markets(sim, market, now_unix)
backend/core/tier_classification_adapter.py:228:        # Add valid results
backend/core/tier_classification_adapter.py:229:        for market_type, result in game_results.items():
backend/core/tier_classification_adapter.py:231:                all_results.append(result)
backend/core/tier_classification_adapter.py:234:    return choose_top(all_results, max_posts=max_picks)
backend/core/tier_classification_adapter.py:382:    all_results = classify_all_markets(simulation, market_data)
backend/core/tier_classification_adapter.py:383:    for market_type, result in all_results.items():
backend/core/deterministic_replay_cache.py:48:        # with an explicit error — never silently returning stale cached results.
backend/core/deterministic_replay_cache.py:160:                # Production: fail closed — never return stale in-memory results.
backend/core/simulation_engine.py:83:            results = []
backend/core/simulation_engine.py:86:                batch_results = simulation_fn(rng, batch_size)
backend/core/simulation_engine.py:87:                results.extend(batch_results)
backend/core/simulation_engine.py:90:                ci = self._calculate_confidence_interval(np.array(results))
backend/core/simulation_engine.py:92:                    n_run = len(results)
backend/core/simulation_engine.py:97:            results = np.array(results)

### 5) Is CLV closing line capture running?
Output:
clv_records: 0

### 6) Is drift detection running?
Output:
drift_log: 0

### 7) evidence_exports count (Section 3, diagnostic #7)
Output:
evidence_exports: 0

## Additional required behavior checks

Manual override block check (no X-Agent-Id header):
HTTP/1.1 403 Forbidden
{"detail":"BLOCKED: Manual grade override attempt for decision_id=(header check) from source=http_route_guard. Only agent.grading.v1 may grade. Sentinel event MANUAL_GRADE_OVERRIDE_BLOCKED logged."}

Latest manual override sentinel document:
{'event_type': 'MANUAL_GRADE_OVERRIDE_BLOCKED', 'severity': 'CRITICAL', 'decision_id': '(header check)', 'blocked_source': 'http_route_guard', 'requester': 'anonymous', 'agent_id': 'agent.grading.v1', 'timestamp': '2026-06-13T10:06:44.616807+00:00'}

Sample settlement record:
{'decision_id': 'ev_edge_fddeb0d6', 'event_id': 'ev_34b8819c', 'result_code': 'WIN', 'graded_by': 'agent.grading.v1', 'graded_at': '2026-05-24T10:19:55.732635+00:00'}

## Root causes found and fixes applied live

1) Recursion bug in grading engine DB resolver
- Symptom: authenticated grading route returned 500 with RecursionError.
- Fix applied in production file backend/services/phase4_grading_engine.py:
  - _get_db() now imports db.mongo.db once and caches module db handle.
  - Replaced incorrect collection access that used module db variable instead of local _db in batch/reconcile/CLV functions.

2) Batch route shadowed by dynamic route
- Symptom: POST /api/phase4/grade/batch matched /{decision_id}, produced Decision not found: batch.
- Fix applied in production file backend/routes/phase4_grading_agent_routes.py:
  - Registered /batch route before /{decision_id}.

## Post-fix endpoint result
POST /api/phase4/grade/batch with header X-Agent-Id: agent.grading.v1

Output:
{"status":"complete","counts":{"graded":0,"pending":5,"failed":0},"agent_id":"agent.grading.v1"}
HTTP_STATUS:200

## Current status snapshot

graded: 1
decisions: 1912
phase4_records: 3590
ungraded_phase4_edge_lean: 0
clv_records: 0
drift_log: 0
evidence_exports: 0

Conclusion:
- agent.grading.v1 exists and route invocation now works.
- Settlement/CLV/drift/evidence data pipelines remain largely empty and still require full Section 3-11 implementation alignment to satisfy Trust Loop requirements.
