# Canary Pre-Close Evidence Package

Date: 2026-06-13
Scope: Document 2 canary directives + deployment sequence readiness

## Evidence 1 - API Timing (Directive 2)
time_namelookup: 0.005253
time_connect: 0.329475
time_appconnect: 0.622827
time_pretransfer: 0.623375
time_starttransfer: 0.938758
time_total: 0.939041

Diagnosis: API first byte and total are ~1.2s from this test path, so the reported 14s UX delay is likely frontend render/auth/data-path specific rather than raw network/API latency.

## Evidence 2 - Language Audit Pass (Directive 1 C12)
=== PHASE 9 AC-3 LANGUAGE AUDIT ===
files_scanned: 296
violations_count: 0
report_path: /Users/rohithaditya/Downloads/Permutation-Carlos/backend/logs/phase9_ac3_language_audit.json
STATUS: PASS

## Evidence 3 - NCPG Footer Presence in Transactional Email Service (Directive 1 C11)
55:        'Call <strong>1-800-522-4700</strong> or visit '
56:        '<a href="https://ncpgambling.org">ncpgambling.org</a>'
466:        f"Problem gambling help: 1-800-522-4700 | ncpgambling.org"
501:  Problem gambling help: 1-800-522-4700 |
502:  <a href="https://www.ncpgambling.org" style="color:rgba(242,243,236,0.4)">ncpgambling.org</a>
566:        f"Problem gambling help: 1-800-522-4700 | ncpgambling.org"
600:  Problem gambling help: 1-800-522-4700 |
601:  <a href="https://www.ncpgambling.org" style="color:rgba(242,243,236,0.4)">ncpgambling.org</a>

## Evidence 4 - Routing Map Proof (Directive 4)
123:const resolvePageFromLocation = (pathname: string, hash: string): Page => {
131:  const PATH_TO_PAGE: Record<string, Page> = {
136:    '/trust-loop': 'trust-loop',
137:    '/parlay': 'architect',
139:    '/leaderboard': 'leaderboard',
152:  return PATH_TO_PAGE[normalizedPath] || 'dashboard';
158:  'trust-loop': '/trust-loop',
159:  architect: '/parlay',
160:  leaderboard: '/leaderboard',
183:      const pageFromPath = resolvePageFromLocation(window.location.pathname, window.location.hash);

## Evidence 5 - Game State + Sentinel Odds Proof (Live Audit cross-reference)
173:            {card.odds && card.odds !== 0 && Math.abs(card.odds) !== 999900 && (
178:            {card.odds && Math.abs(card.odds) === 999900 && (
291:                  {card.parlay_odds && Math.abs(card.parlay_odds) !== 999900
components/EventCard.tsx:26:  const isFinal = rawGameStatus === 'FINAL' || rawGameStatus === 'COMPLETED' || rawGameStatus === 'CLOSED' || Boolean((event as any)?.completed);
components/EventCard.tsx:28:  const gameStateLabel = isFinal ? 'FINAL' : (isInProgress ? 'IN PROGRESS' : null);
components/EventListItem.tsx:21:  const isFinal = rawGameStatus === 'FINAL' || rawGameStatus === 'COMPLETED' || rawGameStatus === 'CLOSED' || Boolean((event as any)?.completed);
components/EventListItem.tsx:23:  const gameStateLabel = isFinal ? 'FINAL' : (isInProgress ? 'IN PROGRESS' : null);

## Screenshot Status for T+1 Dashboard Check (Directive 2)
Captured T+1 screenshot artifact at proof_batch_screenshots/canary_t1_dashboard_check.png.
Observed state at T+1: authentication gate is displayed for unauthenticated session; authenticated dashboard-only skeleton/blank validation still requires a valid subscriber session.

## Deployment Order Acknowledged (post-canary)
1) Submit 72h canary health package
2) Deploy game state fix first
3) Deploy Section A staged package
4) Deploy Canary Directives in sequence
5) Deploy Live Audit Directive P1 items
6) Begin Phase 14.5 full directive
