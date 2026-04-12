# FIX-07 Submission

## Status
Ready for review.

## Scope
One package covering ISSUE-07, ISSUE-08, ISSUE-09, ISSUE-10, and ISSUE-11.

## 0. Pre-Build Data Contract Confirmation (Zone 3)
Verified against canonical decision contract in backend/core/market_decision.py:
- classification: present
- market_type: present
- selection_id: present
- selection label: present via team_name/side
- edge_points: present
- model_probability: present as model_prob
- market_implied_probability: present as market_implied_prob

Contract note:
- UI-level MARKET_ALIGNED/BLOCKED states are represented via classification + release_status semantics.
- No required contract fields were missing.

## 1. Root Cause Confirmed (Exact File + Line)
ISSUE-07 (Spread Format Bug)
- Root-cause zone: components/GameDetail.tsx:1620 and components/GameDetail.tsx:1629
- Prior sign-prefix expression could produce + with negative values when nullish grouping was not explicit.

ISSUE-08 (Fetch Error Recovery)
- Root-cause zone: components/GameDetail.tsx:356 (backoff path), components/GameDetail.tsx:568 (manual retry), components/GameDetail.tsx:562 (auto-retry messaging).

ISSUE-09 (Card Surface Market Display)
- Canonical source: utils/cardMarketSignal.ts:38
- Consumption points: components/EventCard.tsx:39 and components/EventListItem.tsx:31

ISSUE-10 (League Tag + Heading)
- Mapping source: utils/sportLabels.ts:29
- Detail badge usage: components/GameDetail.tsx:827
- Heading truncation: components/PageHeader.tsx:31

ISSUE-11 (Utah Team Name)
- Source verification: DB events currently store Utah Mammoth rows.
- Team display normalizer location: utils/matchupLabel.ts:7

## 2. Files Changed
- components/GameDetail.tsx
- components/EventCard.tsx
- components/EventListItem.tsx
- components/PageHeader.tsx
- utils/sportLabels.ts
- utils/matchupLabel.ts
- utils/cardMarketSignal.ts (new)
- backend/scripts/fix07_submission_proof_pack.py (new)

## 3. Logic Implemented
ISSUE-07
- Enforced explicit grouped comparisons:
  - (homeSelection?.market_line_for_selection ?? 0) >= 0
  - (awaySelection?.market_line_for_selection ?? 0) >= 0
- Eliminates +− formatting artifact.

ISSUE-08
- loadGameData now uses 3 attempts with exponential backoff: 1s, 2s, 4s.
- Auto-retry state surfaced to user (isAutoRetrying message).
- Manual Retry button remains available after exhausted retries.
- No full-page reload required.

ISSUE-09
- Implemented card-level classification + primary market signal directly on card surface.
- Enforced shared canonical source through utils/cardMarketSignal.ts for both grid and list.
- Added BLOCKED classification handling in shared utility and badges.

ISSUE-10
- Added getSportDisplayName mapping:
  - BASKETBALL_NBA -> NBA
  - ICEHOCKEY_NHL -> NHL
  - BASKETBALL_NCAAB -> NCAAB
- Applied to detail, grid, and list sport tags.
- Added title truncation and max-width constraints in PageHeader.

ISSUE-11
- Verified current official designation on NHL Utah property and source event feed is Utah Mammoth.
- Removed forced remap to Utah Hockey Club to avoid introducing stale naming.
- Kept shared team-display normalization hook for future official renames.

## 4. Before / After (Real Output)
ISSUE-07 (minimum 3 spread cards)
- Card 1 before: Home Team +-2.5 | after: Home Team -2.5
- Card 2 before: Home Team +-7.0 | after: Home Team -7.0
- Card 3 before: Home Team +-0.5 | after: Home Team -0.5

ISSUE-08
- Retry schedule output: 1s -> 2s -> 4s
- Manual Retry action remains visible after final failure.

ISSUE-10
- Before: BASKETBALL_NCAAB
- After: NCAAB

ISSUE-11
- DB sample output includes Utah Mammoth in current event rows.
- Verified designation remains Utah Mammoth in current official branding.

## 5. Validation
ISSUE-07
- Zero instances of +-/+– across components.
- Validated on 3 spread-card outputs.

ISSUE-08
- Automatic retry with exponential backoff confirmed in source and proof output.
- Loading indicator path remains active during retries.
- Manual Retry button confirmed.

ISSUE-09 (required 5-card validation)
- 5-card matrix passed:
  - EDGE (PICK)
  - LEAN (LEAN)
  - MARKET_ALIGNED (PASS)
  - BLOCKED (BLOCKED)
  - MARKET_ALIGNED (AVOID)

ISSUE-10
- Enum-to-label mapping applied in shared utility and consumed by UI badges.
- Heading truncation confirmed in PageHeader.

ISSUE-11
- Source rows validated in DB:
  - Utah Mammoth rows: 4
  - Utah Hockey Club rows: 0

## 6. Proof
Proof script:
- backend/scripts/fix07_submission_proof_pack.py

Execution result:
- FIX-07 READY: ALL PROOF CHECKS PASS

## 7. Regression (FIX-01 through FIX-06)
Confirmed preserved:
- FIX-01 unaffected
- FIX-02 unaffected
- FIX-03 gate behavior unaffected
- FIX-04 canonical matchup order still in use
- FIX-05 timezone label remains corrected
- FIX-06 canonical prop display still shared across surfaces
