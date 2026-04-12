# FIX-04 Submission

## Status
Ready for review.

## 1. Root Cause Confirmed
Card surfaces were displaying team order as HOME vs AWAY, while detail view used AWAY @ HOME. This created inconsistent game identity presentation for the same event.

Root cause locations:
- components/EventCard.tsx (title rendering path)
- components/EventListItem.tsx (title rendering path)

## 2. Files Changed
- components/EventCard.tsx
- components/EventListItem.tsx
- components/GameDetail.tsx
- utils/matchupLabel.ts (new)

## 3. Logic Implemented
Implemented a shared canonical formatter:
- formatAwayAtHome({ away_team, home_team }) => Away @ Home

Applied this same formatter path to:
- card surface: EventCard
- card surface: EventListItem
- detail surface: GameDetail header and share text

This enforces one source and one order for every game.

## 4. Before / After (2 surfaces)
Surface 1: EventCard
- Before: HOME vs. AWAY
- After: AWAY @ HOME

Surface 2: EventListItem
- Before: HOME vs. AWAY
- After: AWAY @ HOME

Detail surface now references the same canonical label source.

## 5. Validation
Validated in code:
- EventCard no longer renders HOME vs AWAY literal ordering
- EventListItem no longer renders HOME vs AWAY literal ordering
- GameDetail PageHeader uses shared matchupLabel
- GameDetail share payload uses shared matchupLabel

Assertion scope note:
- FIX-03 blocked-state behavior untouched
- FIX-04 only normalizes team-order presentation

## 6. Proof
Proof script:
- backend/scripts/fix04_submission_proof_pack.py

The script verifies:
- shared formatter exists
- all three surfaces consume same formatter path
- old HOME vs AWAY literals removed from card surfaces
- detail header/share consume canonical label

## 7. Regression
Confirmed unchanged:
- event click/navigation flow
- sport badge rendering
- game time rendering
- analytical sections and state gates

Only matchup ordering presentation was changed.
