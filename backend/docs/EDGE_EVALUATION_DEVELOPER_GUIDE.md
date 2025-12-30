# BeatVegas Edge Evaluation System — Developer Documentation

## Overview

This document provides complete documentation for the BeatVegas edge evaluation system. It covers all sport-specific calibration, classification logic, and integration points.

**Last Updated:** Production Spec v1.0

---

## Table of Contents

1. [System Architecture](#1-system-architecture)
2. [Sport-Specific Calibration](#2-sport-specific-calibration)
3. [Two-Layer Evaluation System](#3-two-layer-evaluation-system)
4. [Edge Classification Logic](#4-edge-classification-logic)
5. [Signal Lifecycle](#5-signal-lifecycle)
6. [Sharp Side Selection](#6-sharp-side-selection)
7. [Telegram Posting Rules](#7-telegram-posting-rules)
8. [AI Analyzer Integration](#8-ai-analyzer-integration)
9. [Monitoring & Alerting](#9-monitoring--alerting)
10. [API Reference](#10-api-reference)

---

## 1. System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    EDGE EVALUATION PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Game Data   │───▶│ Sport Sanity     │───▶│ Universal     │  │
│  │ + Sim Output│    │ Config           │    │ Edge Evaluator│  │
│  └─────────────┘    └──────────────────┘    └───────┬───────┘  │
│                                                      │          │
│                     ┌────────────────────────────────┘          │
│                     │                                           │
│                     ▼                                           │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              TWO-LAYER EVALUATION                         │  │
│  │  ┌─────────────────┐      ┌─────────────────────────┐    │  │
│  │  │ Layer A:        │      │ Layer B:                │    │  │
│  │  │ ELIGIBILITY     │ ───▶ │ GRADING                 │    │  │
│  │  │ (Pass/Fail)     │      │ (EDGE/LEAN/NO_PLAY)     │    │  │
│  │  └─────────────────┘      └─────────────────────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                     │                                           │
│                     ▼                                           │
│  ┌─────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │ Sharp Side  │───▶│ Signal Locking   │───▶│ Telegram      │  │
│  │ Selector    │    │ Service          │    │ Integration   │  │
│  └─────────────┘    └──────────────────┘    └───────────────┘  │
│                                                                  │
│                     ┌──────────────────┐                        │
│                     │ Sanity Check     │ (Monitoring Only)      │
│                     │ Service          │                        │
│                     └──────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

### File Structure

```
backend/
├── core/
│   ├── sport_sanity_config.py       # Sport thresholds & compression
│   ├── universal_edge_evaluator.py  # Two-layer evaluation
│   ├── sharp_side_selector.py       # Side selection logic
│   └── edge_evaluation_integration.py # Master orchestrator
│
├── services/
│   ├── signal_locking_service.py    # Signal immutability
│   ├── sanity_check_service.py      # Monitoring & alerting
│   ├── ai_analyzer_system_prompt.py # AI Analyzer prompts
│   └── ai_analyzer_context.py       # Context building
```

---

## 2. Sport-Specific Calibration

### Compression Factors (LOCKED — DO NOT MODIFY)

| Sport  | Compression | Rationale |
|--------|-------------|-----------|
| NBA    | 0.85        | Moderately efficient, some edge exists |
| NFL    | 0.85        | Sharp market, key numbers matter |
| NCAAF  | 0.80        | More variance, wider edges possible |
| NCAAB  | 0.80        | High variance, home court strong |
| MLB    | 0.82        | Pitcher-dependent, price-sensitive |
| NHL    | 0.60        | Tightest market, edges are small |

### Compression Formula

```python
compressed_prob = 0.50 + (raw_prob - 0.50) * compression_factor
```

**Example (NHL):**
- Raw probability: 55%
- Compressed: 0.50 + (0.55 - 0.50) * 0.60 = 53%

### Edge Thresholds by Sport and Market

#### NBA
| Market     | EDGE Threshold | LEAN Threshold |
|------------|----------------|----------------|
| Spread     | 4.5 pts        | 2.0 pts        |
| Total      | 6.0 pts        | 3.0 pts        |
| Moneyline  | 4.0%           | 2.0%           |

#### NFL
| Market     | EDGE Threshold | LEAN Threshold |
|------------|----------------|----------------|
| Spread     | 4.5 pts        | 2.0 pts        |
| Total      | 5.0 pts        | 2.5 pts        |
| Moneyline  | 4.0%           | 2.0%           |

#### NCAAF
| Market     | EDGE Threshold | LEAN Threshold |
|------------|----------------|----------------|
| Spread     | 6.0 pts        | 3.0 pts        |
| Total      | 6.5 pts        | 3.5 pts        |
| Moneyline  | 5.0%           | 2.5%           |

#### NCAAB
| Market     | EDGE Threshold | LEAN Threshold |
|------------|----------------|----------------|
| Spread     | 6.0 pts        | 3.0 pts        |
| Total      | 7.0 pts        | 3.5 pts        |
| Moneyline  | 4.5%           | 2.0%           |

#### MLB
| Market     | EDGE Threshold | LEAN Threshold |
|------------|----------------|----------------|
| Spread     | 1.5 pts        | 0.75 pts       |
| Total      | 2.5 pts        | 1.5 pts        |
| Moneyline  | 3.5%           | 2.0%           |

#### NHL (Tightest Market)
| Market     | EDGE Threshold | LEAN Threshold | Hard Cap |
|------------|----------------|----------------|----------|
| Spread     | 0.8 pts        | 0.4 pts        | ±3.0%    |
| Total      | 0.8 pts        | 0.4 pts        | N/A      |
| Moneyline  | 3.0%           | 1.5%           | ±3.0%    |

---

## 3. Two-Layer Evaluation System

### Layer A: Eligibility (Pass/Fail)

Layer A determines if a game is even eligible for edge classification.

**Eligibility Requirements:**
1. Minimum simulation count (10,000)
2. Valid market data exists
3. Game hasn't started
4. No critical data issues
5. Volatility within bounds
6. Distribution passes sanity checks

**If Layer A fails → immediate NO_PLAY**

### Layer B: Grading (EDGE/LEAN/NO_PLAY)

Layer B grades eligible games based on sport-specific thresholds.

**Grading Logic:**
```python
if compressed_edge >= EDGE_THRESHOLD:
    if confidence >= MIN_CONFIDENCE:
        if no_override_blocking:
            return EDGE
return LEAN if compressed_edge >= LEAN_THRESHOLD else NO_PLAY
```

---

## 4. Edge Classification Logic

### EdgeState Definitions

| State    | Meaning | Telegram? | User Action |
|----------|---------|-----------|-------------|
| EDGE     | Strong, actionable signal | YES | Bet-worthy |
| LEAN     | Informational edge | NO | Watch list |
| NO_PLAY  | No significant edge | NO | Pass |

### Classification Decision Tree

```
START
  │
  ├─▶ Layer A: Eligible?
  │     │
  │     NO ──▶ NO_PLAY (reason: eligibility failure)
  │     │
  │     YES
  │     │
  │     ▼
  │   Layer B: Edge Check
  │     │
  │     ├─▶ edge >= EDGE_THRESHOLD?
  │     │     │
  │     │     YES ──▶ confidence >= MIN_CONFIDENCE?
  │     │     │         │
  │     │     │         YES ──▶ override blocking?
  │     │     │         │         │
  │     │     │         │         NO ──▶ EDGE ✓
  │     │     │         │         │
  │     │     │         │         YES ──▶ LEAN (override active)
  │     │     │         │
  │     │     │         NO ──▶ LEAN (low confidence)
  │     │     │
  │     │     NO
  │     │     │
  │     │     ▼
  │     ├─▶ edge >= LEAN_THRESHOLD?
  │     │     │
  │     │     YES ──▶ LEAN
  │     │     │
  │     │     NO ──▶ NO_PLAY
  │
  ▼
END
```

### Override Conditions

Overrides can DOWNGRADE an EDGE to LEAN (never upgrade):

1. **Pitcher Override (MLB):** Starter changed, bullpen game, opener
2. **QB Override (NFL/NCAAF):** Backup QB, injury-questionable starter
3. **Goalie Override (NHL):** Backup goalie, unconfirmed starter
4. **Lineup Override:** Key player(s) out, significant rotation
5. **Weather Override:** High wind (totals), extreme conditions
6. **Volatility Override:** Extreme volatility in simulations

---

## 5. Signal Lifecycle

### Signal States

```
PENDING ──▶ ACTIVE_EDGE ──▶ SETTLED
              │
              ├──▶ ACTIVE_MONITORING
              │
              ├──▶ WEAKENED
              │
              └──▶ INVALIDATED
```

### State Definitions

| State | Description |
|-------|-------------|
| PENDING | Awaiting N-of-M confirmation |
| ACTIVE_EDGE | Confirmed, posted to Telegram |
| ACTIVE_MONITORING | Valid but variance rising |
| WEAKENED | Confidence dropped post-lock |
| INVALIDATED | Explicit invalidation (injury, etc.) |
| SETTLED | Game completed, graded |

### Immutability Rules

**ONCE LOCKED, NEVER CHANGE:**
- Selection (e.g., "Bulls +6.5")
- Line value at decision time
- Original edge points
- Original win probability

**CAN CHANGE:**
- Current confidence (monitoring)
- Current win probability (monitoring)
- State (only valid transitions)

### Confirmation Window (N-of-M)

Before locking, signal must pass N-of-M confirmation:

```
Default: 2-of-3 (must see edge in 2 of 3 consecutive runs)
```

**Purpose:** Anti-noise filter. Prevents locking on simulation variance.

---

## 6. Sharp Side Selection

### Selection Hierarchy

1. **CONSENSUS** — All models agree → follow consensus
2. **RCL_OVERRIDE** — RCL model confidence > 75% → follow RCL
3. **HISTORICAL_BIAS** — Sport-specific bias triggers
4. **EFFICIENT_MARKET** — Default when split

### Sport-Specific Biases

| Sport | Bias | Condition |
|-------|------|-----------|
| NFL | Home dogs | Home dog > +7 pts |
| NBA | Road favorites | Road team favored |
| MLB | Home underdogs | Home team underdog |
| NHL | Road favorites | Road team favored on B2B |
| NCAAF | Home dogs | Home dog > +7 pts, conference game |
| NCAAB | Home court | Strong home court advantage |

### Key Number Protection (Football Only)

Key numbers: 3, 7, 10, 14 (NFL/NCAAF)

If line is near a key number, require **+1.5 additional edge** to classify as EDGE.

```python
if line_near_key_number:
    required_edge = base_threshold + 1.5
```

---

## 7. Telegram Posting Rules

### Post-Worthy Signals

**ONLY post if:**
- EdgeState = EDGE
- Confirmation achieved (N-of-M passed)
- Signal locked
- No active override blocking

### Message Format

```
🔥 EDGE ALERT 🔥

🏀 Lakers @ Bulls
📊 Bulls +6.5
💰 Win Prob: 56%
📈 Edge: 4.8 pts

🧠 Why: Model sees 4.8-point gap vs market

⚠️ Locked at 8:15 PM ET
```

### Update Rules

- **Line move > 1.5 pts:** Post update with "LINE MOVED" flag
- **Invalidation:** Post explanation with reason
- **Settlement:** Post result with CLV tracking

---

## 8. AI Analyzer Integration

### System Prompt (Vic Personality)

The AI Analyzer uses the "Vic" personality — a sharp, experienced analyst who explains in plain English.

**Key Guardrails:**
1. NEVER guarantee outcomes
2. NEVER tell users what to bet
3. ALWAYS acknowledge variance
4. ALWAYS explain the "why"

### Context Payload Structure

```python
{
    "system_prompt": MASTER_SYSTEM_PROMPT,
    "signal_data": {
        "game": {...},
        "signal": {...},
        "edge": {...},
        "simulation": {...},
    },
    "analysis_sections": {
        "setup": "...",
        "edge_explanation": "...",
        "data_summary": "...",
        "sport_context": "...",
    },
    "risk_factors": ["...", "..."],
    "user_question": "..."
}
```

---

## 9. Monitoring & Alerting

### Sanity Check Service

The sanity check service monitors for calibration drift and anomalies.

**It does NOT:**
- Block valid edges
- Cap probabilities
- Override classification

**It DOES:**
- Track EDGE/LEAN/NO_PLAY distribution
- Monitor probability clustering
- Alert on anomalies

### Alert Types

| Alert | Trigger | Severity |
|-------|---------|----------|
| EDGE_COUNT_HIGH | > expected max per day | WARNING |
| PROB_CLUSTERING_HIGH | > 30% above 60% | WARNING |
| NO_PLAY_RATE_LOW | < expected rate | WARNING |
| OVERRIDE_RATE_HIGH | > 40% overridden | INFO |

### Expected Distributions

| Sport | Expected NO_PLAY Rate | Expected Prob Range |
|-------|----------------------|---------------------|
| NBA | 70% | 52-58% |
| NFL | 75% | 52-57% |
| NCAAF | 70% | 52-60% |
| NCAAB | 70% | 52-58% |
| MLB | 75% | 52-56% |
| NHL | 80% | 52-55% |

---

## 10. API Reference

### Main Entry Point

```python
from core.edge_evaluation_integration import EdgeEvaluationOrchestrator

# Initialize
orchestrator = EdgeEvaluationOrchestrator(db=mongo_db)

# Evaluate a game
result = orchestrator.evaluate_game(
    game_data={
        "game_id": "nba_20240115_lakers_bulls",
        "sport": "basketball_nba",
        "home_team": "Bulls",
        "away_team": "Lakers",
        "game_time": datetime.now(timezone.utc),
    },
    simulation_output={
        "sim_run_id": "run_abc123",
        "sim_count": 10000,
        "win_prob": 0.56,
        "model_spread": -4.2,
        "market_spread": -6.5,
        "edge_points": 2.3,
        "std_dev": 12.5,
    },
    market_data={
        "spread": -6.5,
        "total": 215.5,
    },
    market_type="SPREAD"
)

# Result is EdgeEvaluationResult
print(result.edge_state)  # EdgeState.EDGE
print(result.selection)   # "Bulls +6.5"
print(result.is_telegram_worthy)  # True
```

### Convenience Function

```python
from core.edge_evaluation_integration import evaluate_game

result = evaluate_game(
    game_data={...},
    simulation_output={...},
    market_data={...},
    market_type="SPREAD"
)
```

### Get Sport Config

```python
from core.sport_sanity_config import get_sport_sanity_config

config = get_sport_sanity_config("basketball_nba")
print(config.compression_factor)  # 0.85
print(config.spread_edge_threshold)  # 4.5
```

### Compress Probability

```python
from core.sport_sanity_config import compress_probability

compressed = compress_probability("basketball_nba", 0.58)
# Returns: 0.568 (0.50 + (0.58 - 0.50) * 0.85)
```

---

## Appendix A: Reason Codes Reference

| Code | Meaning |
|------|---------|
| EDGE_SPREAD_THRESHOLD_MET | Spread edge met threshold |
| EDGE_TOTAL_THRESHOLD_MET | Total edge met threshold |
| EDGE_MONEYLINE_THRESHOLD_MET | ML edge met threshold |
| LEAN_THRESHOLD_MET | Met LEAN but not EDGE |
| ELIGIBILITY_FAILED | Layer A failure |
| CONFIDENCE_LOW | Below min confidence |
| VOLATILITY_HIGH | High volatility bucket |
| VOLATILITY_EXTREME | Extreme volatility bucket |
| VOLATILITY_DOWNGRADE | Downgraded due to volatility |
| DISTRIBUTION_UNSTABLE | Unstable simulation distribution |
| OVERRIDE_PITCHER | Pitcher override active |
| OVERRIDE_QB | QB override active |
| OVERRIDE_GOALIE | Goalie override active |
| OVERRIDE_LINEUP | Lineup override active |
| OVERRIDE_WEATHER | Weather override active |
| KEY_NUMBER_DOWNGRADE | Near key number, insufficient edge |
| MARKET_CONFIRMATION_POSITIVE | Market supports position |
| MARKET_CONFIRMATION_NEGATIVE | Market against position |
| NHL_HARD_CAP_EXCEEDED | Exceeded NHL 3% cap |

---

## Appendix B: Configuration Quick Reference

### To modify thresholds:

Edit `backend/core/sport_sanity_config.py`

```python
SPORT_SANITY_CONFIGS["basketball_nba"] = SportSanityConfig(
    sport_key="basketball_nba",
    spread_edge_threshold=4.5,  # Modify here
    # ...
)
```

### To add a new sport:

1. Add config in `sport_sanity_config.py`
2. Add evaluation method in `universal_edge_evaluator.py`
3. Add bias config in `sharp_side_selector.py`
4. Add prompt addition in `ai_analyzer_system_prompt.py`

---

## Appendix C: Testing Checklist

Before deploying changes:

- [ ] All sport configs have valid compression factors
- [ ] All thresholds are positive
- [ ] Edge thresholds > Lean thresholds
- [ ] Compression factors between 0 and 1
- [ ] N-of-M confirmation is 2-of-3 or stricter
- [ ] Key number protection active for football
- [ ] NHL hard caps are enforced
- [ ] Sanity monitoring is recording
- [ ] Telegram posting rules are enforced
- [ ] Signal locking is immutable

---

*Document Version: 1.0*
*Last Updated: Production Release*
