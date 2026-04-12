# FIX-06 Submission

## Status
Ready for review.

## 1. Root Cause Confirmed
Root cause is divergent presentation logic (not independent fetch timing):
- Grid and list both render from the same Dashboard `filteredEvents` array.
- Grid previously used `TOP PROP MISPRICING` and structured-prop-first display.
- List previously used `MODEL MISPRICING (NOT A BETTING PICK)` and `top_prop_bet` display.

This allowed same-game mismatches in visible label and headline/value string.

## 2. Files Changed
- components/EventCard.tsx
- components/EventListItem.tsx
- utils/propDisplay.ts (new)
- backend/scripts/fix06_submission_proof_pack.py (new)

## 3. Logic Implemented
Introduced one canonical prop presentation source:
- `CANONICAL_PROP_LABEL = MODEL MISPRICING (NOT A BETTING PICK)`
- `getCanonicalPropHeadline(event)`

Canonical headline precedence (both surfaces):
1. `top_prop_bet` when present
2. formatted first structured prop (`player - market @ line`)
3. fallback message

Both `EventCard` and `EventListItem` now import and render the same canonical label and same headline derivation function.

## 4. Before / After (2 Examples)
Example A (both fields present):
- Before grid: structured prop text
- Before list: `top_prop_bet` text
- After both: same canonical headline

Example B (`top_prop_bet` absent):
- Before grid: structured prop text
- Before list: fallback text
- After both: same canonical structured-prop headline

## 5. Validation (3-Game Side-by-Side)
Validated with three representative game payloads in proof script output:
- each row prints `before_grid`, `before_list`, `after_grid`, `after_list`
- all three rows report `identical_after: True`

Proof script:
- backend/scripts/fix06_submission_proof_pack.py

## 6. Proof
Script verifies all required consistency assertions:
- canonical util exports exist
- both surfaces import canonical util
- both surfaces render same label constant
- both surfaces derive headline with same function
- legacy grid-only label removed
- 3-game side-by-side `identical_after` all true

## 7. Regression
Confirmed unchanged:
- Dashboard event mapping flow (`filteredEvents`) remains intact
- FIX-04 team-order normalization untouched
- FIX-05 timezone label correction untouched
- confidence rendering and event navigation untouched