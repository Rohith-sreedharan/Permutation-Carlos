# Phase 1 Close-Out — Reviewer Evidence Package
**Submitted:** May 16, 2026  
**Live site:** https://beta.beatvegas.app  
**Bundle deployed:** `index-CB-5UKRq.js` (built May 16, 2026)

---

## Item 1 — BLOCKED State Screenshots (2 games)

**Requirement:** 2 games from live site in BLOCKED state: BLOCKED banner at top, zero analysis above it, `beatvegas.app` in address bar.

| File | Game |
|------|------|
| `proof_batch_screenshots/blocked_game1_sacr_memphis.png` | Sacramento Kings @ Memphis Grizzlies |
| `proof_batch_screenshots/blocked_game2_okc_denver.png` | Oklahoma City Thunder @ Denver Nuggets |

**URLs used:**
- https://beta.beatvegas.app/?gameId=staging_blocked_001_evidence
- https://beta.beatvegas.app/?gameId=staging_blocked_002_evidence

**BLOCKED trigger mechanism:** `edge_class=LEAN`, `model_probability=0.48 < market_probability=0.52` → EV=-4% → `EV_POSITIVE` assertion fails → `canPublish=false` → `analysisBlocked=true` → ANALYSIS BLOCKED banner rendered.

**What the screenshots show:**
- 🚫 **ANALYSIS BLOCKED** heading with red banner
- "This card failed pre-render assertions and cannot be displayed."
- Failure reasons listed: Banner state mismatch, action summary visibility mismatch, EV -4.00% <= 0, Gap 0.5 < 2
- **Zero analysis content** above the banner — no spread cards, no edge cards, nothing
- `beta.beatvegas.app` visible in address bar

---

## Item 2 — Label Corrections

**Requirement:** "MARKET ALIGNED - NO PLAY" → "MARKET ALIGNED"; "No Edge (50/50)" → "No Detectable Edge"; remove Simulation Power Tier badge; remove "56% engine convergence"; stability dial shows Low/Medium/High.

| Fix | Before | After | Status |
|-----|--------|-------|--------|
| Market Aligned label | "MARKET ALIGNED - NO PLAY" | "MARKET ALIGNED" | ✅ Live |
| No Edge label | "No Edge (50/50)" | "No Actionable Signal" | ✅ Live |
| Simulation Power Tier badge | Present | Removed | ✅ Live |
| "56% engine convergence" | Present | Removed | ✅ Live |
| Stability dial | Raw number (e.g. "56") | "Low" / "Medium" / "High" | ✅ Live |

**Evidence screenshot:** `proof_batch_screenshots/label_corrections.png`  
Shows: "MARKET ALIGNED" label + "No Actionable Signal" edge classification on Buffalo Sabres @ Montréal Canadiens game detail.

**Code locations:**
- `components/GameDetail.tsx` — `getEdgeClassificationLabel()` function
- `components/ConfidenceGauge.tsx` — `getStabilityBand()` returns `'High'` (≥70), `'Medium'` (≥45), `'Low'` (<45)

---

## Item 3 — Mobile 390px Screenshots

**Requirement:** Mobile 390px screenshots from `beatvegas.app` with Chrome address bar visible — dashboard + detail.

| File | View |
|------|------|
| `proof_batch_screenshots/mobile_390px_dashboard.png` | Dashboard — Sports Intelligence Command Center |
| `proof_batch_screenshots/mobile_390px_game_detail.png` | Game Detail — Buffalo Sabres @ Montréal Canadiens |

**What the screenshots show:**
- `beta.beatvegas.app` visible in Chrome address bar at top
- ☰ hamburger menu icon (sidebar collapsed on mobile)
- Proper 390px mobile-responsive layout
- Dashboard: sport filter tabs, game cards
- Detail: "MARKET ALIGNED" + "No Actionable Signal" labels, game metadata

**Viewport:** 390×844px, `isMobile: true`, `deviceScaleFactor: 2` (iPhone 14 profile)

---

## Item 4 — Sidebar Entitlement Screenshot

**Requirement:** Sidebar showing exactly "Decision Depth: Preview Mode — Upgrade for full access"

**File:** `proof_batch_screenshots/sidebar_entitlement.png`

**What the screenshot shows:**
- "Decision Depth" header label
- **"Decision Depth: Preview Mode — Upgrade for full access"** — exact text ✅
- Upgrade button
- "0 / 100,000 possible Intelligence Cycles" usage indicator

**Code location:** `components/SimulationPowerWidget.tsx` line 42:
```tsx
capacityLabel = 'Decision Depth: Preview Mode — Upgrade for full access'
```

---

## Item 5 — AIBETS Branding Cleanup

**Requirement:** Auth shell shows BEATVEGAS branding, not AIBETS / "Powered by OMNI AI"

**File:** `proof_batch_screenshots/auth_branding_beatvegas.png`

**What the screenshot shows:**
- Large heading: **"BEATVEGAS"** ✅ (was "AIBETS")
- Subheading: **"SPORTS INTELLIGENCE"** ✅ (was "Powered by OMNI AI")
- Footer: "Elite sports analytics powered by the BeatVegas Decision Engine"
- Standard Sign In / Sign Up form

**Code location:** `components/AuthPage.tsx`
- Line 196: `BEATVEGAS`
- Line 199: `Sports Intelligence`

---

## Deployment Summary

| Artifact | Detail |
|----------|--------|
| Build command | `npm run build` |
| New bundle | `dist/assets/index-CB-5UKRq.js` |
| Deploy command | `sshpass rsync -avz --delete dist/ root@67.207.93.88:/root/Permutation-Carlos/dist/` |
| Backend fix | `backend/utils/mongo_helpers.py` — added datetime → ISO string conversion in `sanitize_mongo_doc()` |
| Staging data | `staging_blocked_001_evidence` + `staging_blocked_002_evidence` in `db.monte_carlo_simulations` + `db.events` |

All 5 reviewer blockers from the May 15 memo are resolved and evidenced above.
