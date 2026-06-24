# Canary Server Evidence Package

Date: 2026-06-13
Source: Production host root@67.207.93.88 at /root/Permutation-Carlos

## Evidence Item 1 — NCPG footer coverage
Command run:
grep -rn "_email_footer_html\|1-800-522-4700\|ncpgambling" backend/services/transactional_email_service.py

Output:
435:        f"Problem gambling help: 1-800-522-4700 | ncpgambling.org"
469:  Problem gambling help: 1-800-522-4700 |
470:  <a href="https://www.ncpgambling.org" style="color:rgba(242,243,236,0.4)">ncpgambling.org</a>
533:        f"Problem gambling help: 1-800-522-4700 | ncpgambling.org"
566:  Problem gambling help: 1-800-522-4700 |
567:  <a href="https://www.ncpgambling.org" style="color:rgba(242,243,236,0.4)">ncpgambling.org</a>

## Evidence Item 2 — Language audit
Commands run:
python3 backend/scripts/phase9_ac3_language_audit.py --ci
cat backend/logs/phase9_ac3_language_audit.json

Output:
=== PHASE 9 AC-3 LANGUAGE AUDIT ===
files_scanned: 294
violations_count: 0
report_path: /root/Permutation-Carlos/backend/logs/phase9_ac3_language_audit.json
STATUS: PASS
{
  "scanner": "phase9_ac3_language_audit",
  "surfaces": [
    "backend/routes",
    "backend/services",
    "backend/middleware",
    "backend/tools",
    "components",
    "src",
    "docs",
    "public",
    "uiCopy",
    "tests"
  ],
  "files_scanned": 294,
  "violations_count": 0,
  "violations_by_phrase": {},
  "violations": []
}

## Evidence Item 3 — Load time diagnosis
Commands run:
cat > /root/curl-format.txt << 'EOF'
time_namelookup:    %{time_namelookup}\n
time_connect:       %{time_connect}\n
time_appconnect:    %{time_appconnect}\n
time_pretransfer:   %{time_pretransfer}\n
time_starttransfer: %{time_starttransfer}\n
time_total:         %{time_total}\n
EOF
curl -w "@/root/curl-format.txt" -s -o /dev/null https://beta.beatvegas.app/api/v1/games

Output:
time_namelookup:    0.013740
time_connect:       0.016237
time_appconnect:    0.085364
time_pretransfer:   0.085687
time_starttransfer: 0.108290
time_total:         0.108367

## Evidence Item 4 — Routing confirmation
Command run:
grep -n "trust-loop\|leaderboard\|parlay" App.tsx components/MainLayout.tsx 2>/dev/null | head -30

Output:
components/MainLayout.tsx:173:      case 'leaderboard':
components/MainLayout.tsx:198:      case 'trust-loop':
components/MainLayout.tsx:235:      case 'war-room-leaderboard':

## Evidence Item 5 — Build confirmation
Command run:
npm run build 2>&1 | tail -5

Output:
npm notice
npm notice New major version of npm available! 10.8.2 -> 11.17.0
npm notice Changelog: https://github.com/npm/cli/releases/tag/v11.17.0
npm notice To update run: npm install -g npm@11.17.0
npm notice

Supplemental build success check:
npm run build 2>&1 | grep -E "built in|✓ built|error" | tail -10

Output:
✓ built in 17.34s

## Production deployment state check (game-state labels)
Command run:
grep -n "IN PROGRESS\|Pre-game analysis archived\|FINAL" components/EventCard.tsx components/EventListItem.tsx 2>/dev/null || true

Output:
(no matches)

Interpretation:
Staged game-state fix has not been deployed to production yet, consistent with canary no-deploy rule.
