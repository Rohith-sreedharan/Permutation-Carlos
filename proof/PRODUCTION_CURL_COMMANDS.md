# Production Artifact Curl Commands

## MARKET_ALIGNED Spread (NCAAB - UIC Flames vs Northern Iowa Panthers)

```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '.spread'
```

**Key Metrics:**
- Classification: MARKET_ALIGNED
- Edge Points: 0.999 (< 1.0 threshold)
- Model Prob: 57.82%
- Validator Failures: [] ✅
- Release Status: INFO_ONLY

**Artifact:** `proof/MARKET_ALIGNED_SPREAD.json`

---

## EDGE Total (NCAAB - UIC Flames vs Northern Iowa Panthers)

```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '.total'
```

**Key Metrics:**
- Classification: EDGE
- Edge Points: 2.75 (≥ 2.0 threshold)
- Model Prob: 60.0% (≥ 0.55 threshold)
- Edge Grade: B
- Validator Failures: [] ✅
- Release Status: OFFICIAL

**Artifact:** `proof/EDGE_TOTAL.json`

---

## Verification

Full decision object (both spread + total):

```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions'
```

Validate both artifacts are clean:

```bash
curl -s 'https://beta.beatvegas.app/api/games/NCAAB/3fdae7883c7eb0b4fe00927d043d69ba/decisions' | jq '{
  spread_classification: .spread.classification,
  spread_validators: .spread.validator_failures,
  total_classification: .total.classification,
  total_validators: .total.validator_failures
}'
```

Expected output:
```json
{
  "spread_classification": "MARKET_ALIGNED",
  "spread_validators": [],
  "total_classification": "EDGE",
  "total_validators": []
}
```
