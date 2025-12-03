# Phase 15: Manual Intake & Command Center Architecture

**Project:** BeatVegas Analytics Engine → Betting Operating System  
**Phase:** 15 (V1 Manual Intake Engine)  
**Status:** Architecture & Design Document  
**Last Updated:** November 28, 2025

---

## 🎯 Executive Summary

**The Pivot:** Transform BeatVegas from a pure "prediction tool" into a **Betting Operating System** that tracks real user behavior to generate behavioral analytics and coaching. Phase 15 adds manual ingestion capabilities before automated syncing (Phase 16).

**Core Value:** Users manually track their positions → System calculates behavioral indices (Chase, Tilt, Discipline) → AI Coach provides personalized feedback comparing "Reality vs Edge".

**Compliance:** Maintains "Decision Capital" terminology while backend handles standard betting data structures.

---

## 📊 Part 1: Gap Analysis & Required Changes

### 1.1 New MongoDB Collections

#### **manual_positions** (Primary Collection)
```json
{
  "_id": ObjectId,
  "position_id": String,              // UUID
  "user_id": String,
  "ingestion_method": "ocr" | "text_paste" | "manual_form",
  "ingestion_timestamp": ISODate,
  
  // Normalized Position Data
  "sport_key": String,                // "basketball_nba", "americanfootball_nfl"
  "event_id": String,                 // Links to events collection (if matched)
  "event_description": String,        // "Lakers vs Celtics"
  "commence_time": ISODate,
  
  // Market Details
  "market_key": String,               // "h2h", "spreads", "totals", "player_props"
  "selection": String,                // "Lakers", "Over 220.5", "LeBron Over 25.5 pts"
  "odds": {
    "american": String,               // "+150" or "-110"
    "decimal": Number,                // 2.50
    "implied_probability": Number     // 0.40
  },
  
  // Position Sizing
  "stake": Number,                    // Amount risked
  "potential_payout": Number,         // Calculated from odds
  "unit_size": Number,                // Derived from user's Decision Capital Profile
  "units_risked": Number,             // stake / unit_size
  
  // Position Type
  "position_type": "single" | "parlay",
  "parlay_legs": Array,               // If parlay, array of leg objects
  "parlay_legs_count": Number,
  
  // Result Tracking
  "status": "pending" | "won" | "lost" | "push" | "void",
  "settled_at": ISODate,
  "profit_loss": Number,              // Actual result
  "roi": Number,                      // (profit_loss / stake) * 100
  
  // AI Analysis Integration
  "matched_simulation_id": String,    // Links to monte_carlo_simulations
  "our_edge": Number,                 // Our model's EV for this position
  "edge_variance": Number,            // User's odds vs our fair value
  "edge_alignment": "with_edge" | "against_edge" | "no_data",
  
  // Behavioral Context
  "user_capital_at_time": Number,     // Snapshot of bankroll
  "positions_in_last_hour": Number,   // For Tilt Index
  "loss_streak_at_time": Number,      // For Chase Index
  "time_since_last_position": Number, // Minutes
  
  // Raw Ingestion Data (for audit)
  "raw_ocr_text": String,             // If OCR method
  "raw_llm_response": Object,         // LLM parsing output
  "confidence_score": Number,         // OCR/Parser confidence
  
  "created_at": ISODate,
  "updated_at": ISODate
}
```

#### **ingestion_logs** (Audit Trail)
```json
{
  "_id": ObjectId,
  "user_id": String,
  "ingestion_id": String,
  "method": "ocr" | "text_paste" | "manual_form",
  "status": "success" | "failed" | "pending_review",
  
  // Input
  "input_type": "image" | "text",
  "input_size_bytes": Number,
  "image_url": String,                // S3 path if image
  
  // Processing
  "ocr_service": "tesseract" | "google_vision" | "aws_textract",
  "ocr_duration_ms": Number,
  "llm_model": String,                // "gpt-4o", "gemini-1.5-pro"
  "llm_tokens_used": Number,
  "llm_duration_ms": Number,
  "parser_confidence": Number,
  
  // Output
  "parsed_positions_count": Number,
  "created_position_ids": Array,
  "validation_errors": Array,
  
  // Error Handling
  "error_message": String,
  "requires_manual_review": Boolean,
  "admin_notes": String,
  
  "created_at": ISODate
}
```

#### **behavioral_analytics** (Time-Series Collection)
```json
{
  "_id": ObjectId,
  "user_id": String,
  "calculation_date": ISODate,
  "window": "daily" | "weekly" | "monthly" | "all_time",
  
  // Core Indices
  "chase_index": Number,              // avg_stake_after_losses / baseline_avg_stake
  "tilt_index": Number,               // avg_positions_after_streak / baseline_avg_activity
  "discipline_score": Number,         // 0-100, starts at 80
  "risk_score": Number,               // Weighted: volatility + parlay_ratio + exposure
  
  // Supporting Metrics
  "baseline_avg_stake": Number,
  "avg_stake_after_losses": Number,
  "baseline_avg_activity": Number,    // positions per day
  "avg_positions_after_streak": Number,
  "loss_streak_count": Number,
  "win_streak_count": Number,
  
  // Behavioral Flags
  "chasing_detected": Boolean,
  "tilt_detected": Boolean,
  "oversizing_detected": Boolean,
  "late_night_betting": Boolean,      // 11pm-6am activity
  
  // Performance Context
  "total_positions": Number,
  "win_rate": Number,
  "roi": Number,
  "total_profit_loss": Number,
  "largest_win": Number,
  "largest_loss": Number,
  "avg_odds": Number,
  "parlay_ratio": Number,             // % of positions that are parlays
  
  // Edge Alignment
  "positions_with_edge": Number,      // Aligned with our simulations
  "positions_against_edge": Number,
  "edge_alignment_rate": Number,
  
  // Discipline Score Components
  "discipline_penalties": Array,      // [{reason, points_lost, timestamp}]
  "discipline_bonuses": Array,        // [{reason, points_gained, timestamp}]
  
  "created_at": ISODate
}
```

#### **command_center_snapshots** (Dashboard State)
```json
{
  "_id": ObjectId,
  "user_id": String,
  "snapshot_date": ISODate,
  
  // The Reality (User's Actual Performance)
  "reality": {
    "total_positions": Number,
    "win_rate": Number,
    "roi": Number,
    "total_profit_loss": Number,
    "units_won_lost": Number,
    "avg_odds": Number,
    "favorite_sports": Array,         // [{sport, count, roi}]
    "favorite_markets": Array          // [{market, count, roi}]
  },
  
  // The Edge (Our AI's Recommendations)
  "edge": {
    "total_simulations_run": Number,
    "high_confidence_picks": Number,  // >65% confidence
    "avg_model_accuracy": Number,     // From Trust Loop
    "suggested_positions": Array      // Top opportunities
  },
  
  // The Gap (Reality vs Edge)
  "gap_analysis": {
    "edge_alignment_rate": Number,    // % of user positions that matched our edge
    "missed_opportunities": Number,   // High-EV sims user didn't take
    "negative_ev_positions": Number,  // User took positions we flagged as -EV
    "roi_if_followed_edge": Number,   // Hypothetical ROI if user only took our picks
    "improvement_potential": Number   // Gap between actual and potential ROI
  },
  
  // Behavioral Summary
  "behavioral": {
    "discipline_score": Number,
    "chase_index": Number,
    "tilt_index": Number,
    "risk_score": Number,
    "primary_weakness": String,       // "Chasing losses", "Oversizing", etc.
    "primary_strength": String         // "Consistent sizing", "High edge alignment"
  },
  
  "created_at": ISODate
}
```

### 1.2 Schema Modifications to Existing Collections

#### **users** (Add Behavioral Tracking)
```json
{
  // ... existing fields ...
  
  "behavioral_profile": {
    "current_discipline_score": Number,
    "discipline_trend": "improving" | "declining" | "stable",
    "primary_behavioral_flag": String,
    "baseline_stake": Number,
    "baseline_activity": Number,
    "total_manual_positions": Number,
    "last_position_at": ISODate
  },
  
  "command_center_config": {
    "enable_tilt_alerts": Boolean,
    "enable_chase_alerts": Boolean,
    "alert_threshold_discipline": Number,  // Alert if drops below X
    "preferred_sports": Array,
    "hide_negative_positions": Boolean     // UI preference
  }
}
```

#### **risk_profiles** (Extend Existing Collection)
```json
{
  // ... existing fields ...
  
  "actual_performance": {
    "tracked_positions": Number,
    "actual_avg_stake": Number,
    "actual_win_rate": Number,
    "actual_roi": Number,
    "actual_sharpe_ratio": Number,
    "actual_max_drawdown": Number
  },
  
  "variance_from_plan": {
    "stake_variance": Number,           // Actual vs planned unit size
    "frequency_variance": Number,       // Actual vs planned bet frequency
    "risk_classification_drift": String // "on_target", "too_aggressive", "too_conservative"
  }
}
```

---

## 🏗️ Part 2: Updated System Architecture

### 2.1 High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                      PHASE 15 ARCHITECTURE                           │
│                  Manual Intake & Command Center                      │
└─────────────────────────────────────────────────────────────────────┘

┌──────────────────────┐
│   USER INTERFACE     │
│  (React/TypeScript)  │
└──────────┬───────────┘
           │
           ├─────► Screenshot Upload (Image File)
           ├─────► Text Paste (Raw Text)
           └─────► Manual Form (Structured Input)
                   │
                   ▼
┌──────────────────────────────────────────────────────────────────────┐
│                    INGESTION LAYER (FastAPI)                          │
│  POST /api/positions/ingest                                           │
└───────────┬──────────────────────────────────────────────────────────┘
            │
            ├──► IF image:
            │    ┌──────────────────┐
            │    │  OCR SERVICE     │ (Tesseract/Google Vision/AWS Textract)
            │    │  Extract Text    │
            │    └────────┬─────────┘
            │             │
            ▼             ▼
┌──────────────────────────────────────────────────────────────────────┐
│                      LLM PARSER SERVICE                               │
│  (GPT-4o / Gemini 1.5 Pro)                                           │
│                                                                       │
│  Input: Raw OCR text or pasted text                                  │
│  Output: Structured JSON with bet details                            │
│                                                                       │
│  System Prompt: "BetSlip Parser v1.0" (see Part 3)                  │
└───────────┬──────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   DATA NORMALIZATION ENGINE                           │
│  - Convert American/Decimal odds                                      │
│  - Match event_id from events collection                             │
│  - Derive market_key (h2h, spreads, totals)                          │
│  - Calculate implied probability                                      │
│  - Link to existing simulations (if available)                       │
└───────────┬──────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                     MONGODB STORAGE                                   │
│  Collections:                                                         │
│  - manual_positions (primary data)                                    │
│  - ingestion_logs (audit trail)                                       │
└───────────┬──────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│              BEHAVIORAL ANALYTICS ENGINE (NEW)                        │
│                                                                       │
│  Triggers on new position insert:                                    │
│  1. Calculate Chase Index                                            │
│  2. Calculate Tilt Index                                             │
│  3. Update Discipline Score                                          │
│  4. Calculate Risk Score                                             │
│  5. Detect behavioral flags                                          │
│  6. Store in behavioral_analytics collection                         │
└───────────┬──────────────────────────────────────────────────────────┘
            │
            ├──────────────────────────────────────────┐
            ▼                                          ▼
┌─────────────────────────┐              ┌─────────────────────────┐
│   EXISTING AGENTS       │              │   EVENT BUS (Redis)     │
│   (Integration Points)  │              │   New Event Types:      │
│                         │              │   - POSITION_INGESTED   │
│  Agent 5: Risk Agent    │◄─────────────┤   - CHASE_DETECTED      │
│  - Now uses actual data │              │   - TILT_DETECTED       │
│  - Real vs planned risk │              │   - DISCIPLINE_UPDATE   │
│                         │              └─────────────────────────┘
│  Agent 6: User Modeling │                          │
│  - Behavioral patterns  │                          │
│  - Tilt prediction      │                          ▼
│  - Enhanced with actual │              ┌─────────────────────────┐
│    position history     │              │   WEBSOCKET MANAGER     │
└─────────────────────────┘              │   Real-time alerts to   │
            │                            │   frontend              │
            │                            └─────────────────────────┘
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│              COMMAND CENTER AGGREGATION (NEW)                         │
│                                                                       │
│  Scheduled Job (Hourly):                                             │
│  1. Query manual_positions for user                                  │
│  2. Query monte_carlo_simulations for recommendations                │
│  3. Calculate "The Reality" (actual performance)                     │
│  4. Calculate "The Edge" (AI recommendations)                        │
│  5. Calculate "The Gap" (variance analysis)                          │
│  6. Store snapshot in command_center_snapshots                       │
└───────────┬──────────────────────────────────────────────────────────┘
            │
            ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   COMMAND CENTER UI (NEW)                             │
│  Components/CommandCenter.tsx                                         │
│                                                                       │
│  Three-Panel Layout:                                                  │
│  ┌────────────┬────────────┬────────────┐                           │
│  │ THE REALITY│  THE EDGE  │  THE GAP   │                           │
│  │            │            │            │                           │
│  │ Actual PnL │ AI Picks   │ Alignment  │                           │
│  │ Win Rate   │ High EV    │ Missed Ops │                           │
│  │ ROI        │ Accuracy   │ -EV Taken  │                           │
│  └────────────┴────────────┴────────────┘                           │
│                                                                       │
│  Behavioral Dashboard:                                                │
│  - Discipline Score (Gamified 0-100)                                 │
│  - Chase Index Meter                                                  │
│  - Tilt Index Meter                                                   │
│  - Risk Score Gauge                                                   │
└───────────────────────────────────────────────────────────────────────┘
```

### 2.2 Integration with Existing Multi-Agent System

#### **Enhanced Agent 5: Risk Agent**
**Old Behavior:** Validated hypothetical bet sizing using Kelly Criterion
**New Behavior:** 
- Monitors actual manual positions in real-time
- Compares actual stake vs recommended position size
- Calculates real-time bankroll exposure
- Triggers alerts when user oversizes

**New Event Subscriptions:**
- `POSITION_INGESTED` → Validate against risk profile
- `CHASE_DETECTED` → Trigger immediate WebSocket alert
- `TILT_DETECTED` → Coordinate with User Modeling Agent

#### **Enhanced Agent 6: User Modeling Agent**
**Old Behavior:** Generic tilt detection based on hypothetical patterns
**New Behavior:**
- Uses actual position history for behavioral analysis
- Predicts tilt probability based on loss streaks
- Calculates Chase/Tilt indices after each position
- Builds user-specific behavioral model over time

**New Database Queries:**
```python
# Real loss streak calculation
recent_positions = db.manual_positions.find({
    "user_id": user_id,
    "status": {"$in": ["won", "lost"]},
    "created_at": {"$gte": datetime.now() - timedelta(days=7)}
}).sort("created_at", -1)

# Real stake variance
stake_variance = calculate_std_dev([p["stake"] for p in positions])
```

#### **New Agent 8: Behavioral Coach (Optional Enhancement)**
**Purpose:** Provides personalized coaching based on behavioral analytics
**Triggers:**
- Discipline Score drops below 60
- Chase Index > 1.5
- User takes -EV position against high-confidence simulation

**Coach Messages:**
```
"🚨 Your Chase Index is elevated (1.8). You're increasing position size after losses. 
Recommend: Return to baseline 2% unit sizing."

"✅ Great discipline! You're consistently taking positions aligned with our Edge. 
Your alignment rate is 78% this week."

"⚠️ Tilt Alert: 5 positions in 20 minutes. Our AI suggests a 1-hour cooldown."
```

---

## 🤖 Part 3: LLM Parser System Prompt

### System Prompt: "BetSlip Parser v1.0"

```markdown
# SYSTEM ROLE
You are a specialized betslip parser for BeatVegas Analytics. Your ONLY job is to extract structured betting data from raw text input (OCR or user-pasted) and output strictly formatted JSON.

# INPUT TYPES
You will receive:
1. OCR text from a betslip screenshot (messy, may have OCR errors)
2. User-pasted text from a betting app
3. Manual text description of a bet

# OUTPUT FORMAT
You MUST respond with ONLY valid JSON in this exact structure (no markdown, no explanations):

```json
{
  "positions": [
    {
      "sport": "basketball_nba|americanfootball_nfl|baseball_mlb|icehockey_nhl|soccer_epl",
      "event_description": "Los Angeles Lakers vs Boston Celtics",
      "home_team": "Boston Celtics",
      "away_team": "Los Angeles Lakers",
      "commence_time": "2025-11-28T19:30:00Z",
      "market_type": "h2h|spreads|totals|player_props",
      "selection": "Los Angeles Lakers|Lakers -5.5|Over 220.5|LeBron James Over 25.5 Points",
      "odds": {
        "format": "american|decimal",
        "value": "+150|-110|2.50",
        "american": "+150",
        "decimal": 2.50,
        "implied_probability": 0.40
      },
      "stake": 100.00,
      "potential_payout": 250.00,
      "position_type": "single|parlay",
      "parlay_legs": [],
      "confidence": 0.95
    }
  ],
  "parsing_notes": "Any issues or ambiguities encountered",
  "requires_review": false
}
```

# PARSING RULES

## 1. SPORT DETECTION
- Keywords: "NBA", "NFL", "MLB", "NHL", "Soccer", "Premier League"
- Map to: basketball_nba, americanfootball_nfl, baseball_mlb, icehockey_nhl, soccer_epl
- If ambiguous, use "unknown" and set requires_review: true

## 2. EVENT MATCHING
- Extract full team names (prefer full names over abbreviations)
- Format: "Away Team vs Home Team" or "Home Team vs Away Team"
- Handle common OCR errors: "LA Lakers" = "Los Angeles Lakers"
- Remove special characters: "49ers" → "San Francisco 49ers"

## 3. MARKET TYPE DETECTION
Identify from context:
- "Moneyline", "ML", "Win" → h2h
- "Spread", "Handicap", "ATS", "-5.5", "+3" → spreads  
- "Total", "O/U", "Over", "Under", "220.5" → totals
- Player name + stat → player_props

## 4. ODDS CONVERSION
Handle BOTH American and Decimal odds:

**American Odds:**
- Positive: +150 means decimal 2.50, implied prob = 100/(150+100) = 0.40
- Negative: -110 means decimal 1.91, implied prob = 110/(110+100) = 0.524

**Decimal Odds:**
- 2.50 means american +150, implied prob = 1/2.50 = 0.40
- 1.91 means american -110, implied prob = 1/1.91 = 0.524

**ALWAYS provide both formats in output.**

## 5. STAKE EXTRACTION
- Look for: "Bet", "Stake", "Risk", "Wager", "$", "Amount"
- Extract numeric value: "$100" → 100.00
- If missing, set to 0 and requires_review: true

## 6. PARLAY DETECTION
- Keywords: "Parlay", "Multi", "Combo", "Accumulator"
- If multiple legs detected, set position_type: "parlay"
- Extract each leg into parlay_legs array with same structure

## 7. CONFIDENCE SCORING
Rate your confidence in parsing accuracy (0-1):
- 0.95+ : Clean, unambiguous text
- 0.80-0.94 : Minor OCR errors corrected
- 0.60-0.79 : Multiple ambiguities resolved
- < 0.60 : Requires human review, set requires_review: true

# EXAMPLE INPUTS & OUTPUTS

## Example 1: Single Bet (Clean)
INPUT:
```
DraftKings Betslip
Lakers vs Celtics
Moneyline: Lakers +150
Stake: $100
To Win: $150
```

OUTPUT:
```json
{
  "positions": [{
    "sport": "basketball_nba",
    "event_description": "Los Angeles Lakers vs Boston Celtics",
    "home_team": "Boston Celtics",
    "away_team": "Los Angeles Lakers",
    "commence_time": null,
    "market_type": "h2h",
    "selection": "Los Angeles Lakers",
    "odds": {
      "format": "american",
      "value": "+150",
      "american": "+150",
      "decimal": 2.50,
      "implied_probability": 0.40
    },
    "stake": 100.00,
    "potential_payout": 250.00,
    "position_type": "single",
    "parlay_legs": [],
    "confidence": 0.95
  }],
  "parsing_notes": "Clean parse, no issues",
  "requires_review": false
}
```

## Example 2: Messy OCR with Parlay
INPUT:
```
FanDuel
3-Leg Parlay
1. LAL -5.5 (-110)
2. Over 220.5 (-115)
3. LeBron Over 25.5 Pts (-105)
Risk: $50
Win: $325
```

OUTPUT:
```json
{
  "positions": [{
    "sport": "basketball_nba",
    "event_description": "Multi-leg Parlay",
    "market_type": "parlay",
    "selection": "3-Leg Parlay",
    "odds": {
      "format": "american",
      "value": "+650",
      "american": "+650",
      "decimal": 7.50,
      "implied_probability": 0.133
    },
    "stake": 50.00,
    "potential_payout": 375.00,
    "position_type": "parlay",
    "parlay_legs": [
      {
        "sport": "basketball_nba",
        "market_type": "spreads",
        "selection": "Los Angeles Lakers -5.5",
        "odds": {"american": "-110", "decimal": 1.91}
      },
      {
        "sport": "basketball_nba",
        "market_type": "totals",
        "selection": "Over 220.5",
        "odds": {"american": "-115", "decimal": 1.87}
      },
      {
        "sport": "basketball_nba",
        "market_type": "player_props",
        "selection": "LeBron James Over 25.5 Points",
        "odds": {"american": "-105", "decimal": 1.95}
      }
    ],
    "confidence": 0.85
  }],
  "parsing_notes": "Abbreviation 'LAL' resolved to 'Los Angeles Lakers'",
  "requires_review": false
}
```

## Example 3: Ambiguous (Requires Review)
INPUT:
```
Bet on game tonight
Team A -3
$200
```

OUTPUT:
```json
{
  "positions": [{
    "sport": "unknown",
    "event_description": "Team A vs Unknown",
    "market_type": "spreads",
    "selection": "Team A -3",
    "odds": {
      "format": "american",
      "value": "-110",
      "american": "-110",
      "decimal": 1.91,
      "implied_probability": 0.524
    },
    "stake": 200.00,
    "potential_payout": 381.82,
    "position_type": "single",
    "confidence": 0.45
  }],
  "parsing_notes": "Unable to identify sport or specific teams. Assumed standard -110 odds for spread.",
  "requires_review": true
}
```

# ERROR HANDLING
If the input is completely unparseable:
```json
{
  "positions": [],
  "parsing_notes": "Unable to extract any bet structure from input",
  "requires_review": true
}
```

# CRITICAL CONSTRAINTS
1. NEVER add explanatory text outside the JSON
2. ALWAYS include both american and decimal odds
3. NEVER invent data - if unsure, set requires_review: true
4. Use null for missing optional fields (like commence_time)
5. Default odds to -110 (decimal 1.91) for spreads if not specified

BEGIN PARSING.
```

---

## 📋 Part 4: Phase 15 Feature List (Merged)

### Positioning Statement
**From:** BeatVegas is a simulation tool that predicts outcomes.  
**To:** BeatVegas is a **Betting Operating System** where users track real performance against AI-generated edge.

---

### 🎯 Core Features (Phase 15)

#### **Feature 1: Manual Position Ingestion Pipeline**
**User Story:** *"As a user, I want to track my actual betting activity manually so I can see how I perform vs the AI's recommendations."*

**Capabilities:**
1. **Screenshot Upload**
   - Drag-and-drop betslip image
   - OCR extraction (Tesseract/Google Vision/AWS Textract)
   - LLM parsing (GPT-4o/Gemini) with confidence scoring
   - Real-time preview before saving

2. **Text Paste**
   - Paste raw text from betting app
   - Direct LLM parsing
   - Auto-detection of format (DraftKings, FanDuel, Bet365, etc.)

3. **Manual Form Entry**
   - Fallback structured form
   - Sport selector (NBA, NFL, MLB, NHL)
   - Event search (auto-complete from events collection)
   - Odds converter (American ↔ Decimal)
   - Stake input with unit calculation

4. **Data Normalization**
   - Match event_id to existing events
   - Link to monte_carlo_simulations (if available)
   - Calculate implied probability
   - Derive EV (Expected Value) against our model

**Backend:**
- `POST /api/positions/ingest` - Main ingestion endpoint
- `POST /api/positions/ocr` - Image upload + OCR
- `POST /api/positions/parse-text` - Text parsing
- `POST /api/positions/manual` - Manual form submission
- `GET /api/positions/list` - User's position history
- `PATCH /api/positions/{id}/result` - Update with outcome

**Frontend:**
- `components/PositionIngestion.tsx` - Main ingestion UI
- `components/ScreenshotUploader.tsx` - Drag-drop zone
- `components/TextPasteParser.tsx` - Text input
- `components/ManualPositionForm.tsx` - Structured form

**Database:**
- `manual_positions` collection (primary storage)
- `ingestion_logs` collection (audit trail)

---

#### **Feature 2: Behavioral Analytics Engine**
**User Story:** *"As a user, I want to see gamified scores that show my discipline and help me avoid tilt."*

**Calculated Indices:**

1. **Chase Index**
   ```
   Formula: avg_stake_after_losses / baseline_avg_stake
   
   Thresholds:
   - 1.0-1.2 (Green): Consistent sizing
   - 1.2-1.5 (Yellow): Mild chasing
   - 1.5-2.0 (Orange): Moderate chasing
   - >2.0 (Red): Severe chasing → Alert triggered
   
   Example:
   - Baseline stake: $100
   - Avg stake after 3+ losses: $180
   - Chase Index: 1.8 (Orange - trigger warning)
   ```

2. **Tilt Index**
   ```
   Formula: avg_positions_placed_after_streak / baseline_avg_activity
   
   Thresholds:
   - 1.0-1.3 (Green): Normal activity
   - 1.3-1.8 (Yellow): Elevated activity
   - 1.8-2.5 (Orange): Rapid-fire betting
   - >2.5 (Red): Tilt detected → Lock account for 1 hour
   
   Example:
   - Baseline: 5 positions per day
   - After 3-game win streak: 15 positions in 4 hours
   - Tilt Index: 3.0 (Red - tilt detected)
   ```

3. **Discipline Score**
   ```
   Starting Value: 80/100
   
   Penalties (-5 each):
   - Chase Index > 1.5
   - Tilt Index > 1.8
   - Taking -EV position against high-confidence sim
   - Oversizing (>5% of capital on single position)
   - High parlay ratio (>40% of positions)
   - Late-night betting (11pm-6am)
   
   Bonuses (+3 each):
   - Consistent unit sizing (variance < 15%)
   - Taking +EV position aligned with our edge
   - Following recommended Kelly sizing
   - Winning streak without oversizing
   - 7-day clean streak (no penalties)
   
   Display:
   - 80-100: "Elite Discipline" (Green badge)
   - 60-79: "Solid Discipline" (Blue badge)
   - 40-59: "Needs Improvement" (Yellow warning)
   - 0-39: "High Risk" (Red alert + coaching)
   ```

4. **Risk Score**
   ```
   Formula: (Stake_Volatility * 0.4) + (Parlay_Ratio * 0.3) + (Bankroll_Exposure * 0.3)
   
   Components:
   - Stake Volatility: Std dev of stake amounts
   - Parlay Ratio: % of positions that are parlays
   - Bankroll Exposure: % of capital at risk simultaneously
   
   Thresholds:
   - 0-25: Conservative
   - 26-50: Moderate
   - 51-75: Aggressive
   - 76-100: Reckless → Alert
   ```

**Calculation Triggers:**
- Real-time: After each position ingestion
- Scheduled: Hourly aggregation for trends
- On-demand: When user views Command Center

**Backend:**
- `backend/services/behavioral_analytics.py` - Calculation engine
- `POST /api/analytics/calculate` - On-demand calculation
- `GET /api/analytics/user/{user_id}` - Get current indices
- `GET /api/analytics/history` - Time-series data

**WebSocket Events:**
- `CHASE_DETECTED` → Push alert to frontend
- `TILT_DETECTED` → Modal warning + recommended break
- `DISCIPLINE_SCORE_UPDATE` → Live badge update

---

#### **Feature 3: The Command Center Dashboard**
**User Story:** *"As a user, I want a single dashboard that shows my reality vs the AI's edge, with clear visual gaps."*

**Three-Panel Layout:**

**Panel 1: THE REALITY (User's Actual Performance)**
```
┌─────────────────────────────────────────┐
│         THE REALITY                      │
│  "What You Actually Did"                 │
├─────────────────────────────────────────┤
│  Total Positions: 47                     │
│  Win Rate: 51.1% (24W-23L)              │
│  ROI: -3.2% 🔴                           │
│  Total P&L: -$320                        │
│  Units Won/Lost: -3.2u                   │
│  Avg Odds: +115                          │
│                                          │
│  Favorite Sports:                        │
│  🏀 NBA: 28 positions (ROI: +2.1%)      │
│  🏈 NFL: 12 positions (ROI: -12.3%) 🔴  │
│  ⚾ MLB: 7 positions (ROI: +8.4%)       │
│                                          │
│  Favorite Markets:                       │
│  Spreads: 23 (ROI: -1.2%)               │
│  Totals: 15 (ROI: +4.3%)                │
│  Parlays: 9 (ROI: -25.1%) ⚠️            │
└─────────────────────────────────────────┘
```

**Panel 2: THE EDGE (AI Recommendations)**
```
┌─────────────────────────────────────────┐
│          THE EDGE                        │
│  "What Our AI Suggested"                 │
├─────────────────────────────────────────┤
│  Simulations Run: 342                    │
│  High-Confidence Picks: 28               │
│   (>65% win probability)                 │
│  Model Accuracy: 64.3% (Last 90 days)   │
│  Avg EV on Recs: +5.8%                   │
│                                          │
│  Top Opportunities Flagged:              │
│  ✅ Lakers ML +150 (72% win prob)       │
│  ✅ Over 220.5 (68% confidence)         │
│  ✅ Celtics -3.5 (66% win prob)         │
│                                          │
│  If You Followed All Recs:               │
│  Hypothetical ROI: +12.4% 🟢            │
│  Hypothetical P&L: +$1,240               │
└─────────────────────────────────────────┘
```

**Panel 3: THE GAP (Variance Analysis)**
```
┌─────────────────────────────────────────┐
│           THE GAP                        │
│  "Reality vs Edge Analysis"              │
├─────────────────────────────────────────┤
│  Edge Alignment Rate: 43%                │
│   (20 of 47 positions matched our edge) │
│                                          │
│  Missed Opportunities: 8 ⚠️             │
│   High-EV sims you didn't take          │
│   - Potential gain: $480                 │
│                                          │
│  Negative EV Positions: 14 🔴            │
│   You took positions we flagged as -EV   │
│   - Cost: $620                           │
│                                          │
│  ROI Gap: -15.6%                         │
│   (Your -3.2% vs Potential +12.4%)      │
│                                          │
│  Improvement Potential:                  │
│   "If you increase edge alignment to     │
│    80%, projected ROI: +8.2%"            │
│                                          │
│  💡 Coach Insight:                       │
│  "Your NFL picks are against our edge.   │
│   Consider using our simulations more    │
│   heavily in NFL markets."               │
└─────────────────────────────────────────┘
```

**Behavioral Section (Below Panels):**
```
┌──────────────────────────────────────────────────────────────┐
│                    BEHAVIORAL DASHBOARD                       │
├──────────────────────────────────────────────────────────────┤
│  Discipline Score: 68/100 🟡                                  │
│  ████████████████░░░░░░░░ (Solid Discipline)                 │
│                                                               │
│  Chase Index: 1.4 🟡                                          │
│  ██████████░░░░░░░░░░ (Mild chasing detected)                │
│  "You're increasing position size after losses by 40%"       │
│                                                               │
│  Tilt Index: 0.9 🟢                                           │
│  ████████░░░░░░░░░░░░ (Activity is normal)                   │
│  "No rapid-fire betting detected"                            │
│                                                               │
│  Risk Score: 45/100 🟢                                        │
│  ██████████████░░░░░░ (Moderate risk profile)                │
│  "Bankroll exposure is within safe limits"                   │
│                                                               │
│  🏆 Primary Strength: "High edge alignment in NBA markets"   │
│  ⚠️  Primary Weakness: "Chasing losses in NFL spreads"       │
│                                                               │
│  📊 Last 7 Days Trend: Discipline declining (-8 points)      │
└──────────────────────────────────────────────────────────────┘
```

**Backend:**
- `GET /api/command-center/snapshot` - Get latest dashboard data
- `GET /api/command-center/history` - Time-series trends
- `backend/services/command_center_aggregator.py` - Data aggregation logic

**Frontend:**
- `components/CommandCenter.tsx` - Main dashboard
- `components/RealityPanel.tsx` - User performance
- `components/EdgePanel.tsx` - AI recommendations
- `components/GapAnalysisPanel.tsx` - Variance display
- `components/BehavioralDashboard.tsx` - Indices + gamification

**Scheduled Job:**
- Runs hourly via APScheduler
- Aggregates data into `command_center_snapshots`
- Triggers WebSocket update to refresh frontend

---

#### **Feature 4: Enhanced Risk Agent Integration**
**User Story:** *"As a user, I want the AI to alert me in real-time when I'm deviating from my plan."*

**Real-Time Monitoring:**
- Subscribe to `POSITION_INGESTED` events
- Compare actual stake vs Decision Capital Profile
- Calculate real-time bankroll exposure
- Trigger WebSocket alerts for violations

**Alert Types:**

1. **Oversizing Alert**
   ```
   Trigger: stake > (decision_capital * max_exposure_per_position)
   
   Message:
   "🚨 Oversizing Detected
   Your position of $250 is 5% of your Decision Capital.
   Your plan: Max 2% per position ($100).
   
   Recommendation: Reduce to $100 or review your risk profile."
   ```

2. **Chase Alert**
   ```
   Trigger: Chase Index > 1.5 after loss
   
   Message:
   "⚠️ Chase Pattern Detected
   You're increasing position size after losses.
   Current: $150 (baseline: $100)
   
   Recommendation: Return to baseline unit sizing."
   ```

3. **Negative EV Alert**
   ```
   Trigger: User takes position with EV < -2% vs our simulation
   
   Message:
   "❌ Negative EV Position
   You took: Lakers +150
   Our Model: Lakers fair odds +200 (EV: -8.3%)
   
   Insight: This position is against our edge. Consider waiting 
   for better value."
   ```

**Backend:**
- Enhanced `backend/core/agents.py` (Risk Agent)
- New event handlers for position ingestion
- Real-time EV calculation against simulations

---

#### **Feature 5: Position History & Outcome Tracking**
**User Story:** *"As a user, I want to easily update my positions with results and see my historical performance."*

**Capabilities:**
- List all positions with filters (sport, status, date)
- Bulk upload results via CSV
- Manual result entry (Won/Lost/Push)
- Auto-settlement via sports data APIs (Phase 16)

**Backend:**
- `GET /api/positions/list` - Paginated position history
- `PATCH /api/positions/{id}/result` - Update single result
- `POST /api/positions/bulk-settle` - CSV upload
- `GET /api/positions/pending` - Unsettled positions

**Frontend:**
- `components/PositionHistory.tsx` - Table view
- `components/PositionResultForm.tsx` - Quick update
- `components/BulkSettlement.tsx` - CSV upload

---

### 🎮 Gamification Features

#### **Achievement System**
- **"First Blood"** - Log your first position
- **"Edge Seeker"** - 10 positions aligned with our edge
- **"Discipline Master"** - 30 days with score >80
- **"Value Hunter"** - 5 positions with >+10% EV
- **"Ice Cold"** - 7 days without a tilt event

#### **Leaderboards**
- Highest Discipline Score (weekly)
- Best Edge Alignment Rate (monthly)
- Lowest Chase Index (all-time)

#### **Coaching Messages**
Dynamic AI-generated feedback based on behavioral patterns:
- "You're on a 5-day streak without chasing. Keep it up!"
- "Your NFL edge alignment is only 30%. Try using our simulations more."
- "Great discipline! You've earned +3 bonus points this week."

---

## 🔄 Phase 15 vs Phase 16 Scope

### ✅ Phase 15 (This Document)
- Manual position ingestion (Screenshot/Text/Form)
- Behavioral analytics (Chase/Tilt/Discipline/Risk indices)
- Command Center dashboard (Reality/Edge/Gap)
- Enhanced Risk Agent with real data
- Position history and manual result tracking

### ❌ Phase 16 (Future)
- SharpSports / BookLink API integration
- Automated position syncing from sportsbooks
- Auto-settlement via sports data APIs
- Live betting integration
- Multi-book arbitrage detection

---

## 🗂️ File Structure

### New Backend Files
```
backend/
├── routes/
│   └── position_routes.py          # NEW: Position ingestion endpoints
├── services/
│   ├── ocr_service.py               # NEW: OCR extraction (Tesseract/GCP/AWS)
│   ├── llm_parser.py                # NEW: LLM parsing service
│   ├── behavioral_analytics.py      # NEW: Index calculations
│   ├── command_center_aggregator.py # NEW: Dashboard data aggregation
│   └── position_normalizer.py       # NEW: Data normalization logic
└── core/
    └── agents.py                    # MODIFIED: Enhanced Risk + User Modeling agents
```

### New Frontend Files
```
components/
├── CommandCenter.tsx                # NEW: Main command center dashboard
├── RealityPanel.tsx                 # NEW: User performance panel
├── EdgePanel.tsx                    # NEW: AI recommendations panel
├── GapAnalysisPanel.tsx             # NEW: Variance analysis panel
├── BehavioralDashboard.tsx          # NEW: Discipline/Chase/Tilt displays
├── PositionIngestion.tsx            # NEW: Main ingestion UI
├── ScreenshotUploader.tsx           # NEW: Drag-drop image upload
├── TextPasteParser.tsx              # NEW: Text input parser
├── ManualPositionForm.tsx           # NEW: Structured form entry
├── PositionHistory.tsx              # NEW: Position table view
├── PositionResultForm.tsx           # NEW: Result update form
└── BulkSettlement.tsx               # NEW: CSV upload
```

---

## 🚀 Implementation Priority

### Sprint 1: Core Ingestion (Week 1-2)
1. Set up MongoDB collections (manual_positions, ingestion_logs)
2. Build OCR service integration
3. Implement LLM parser with system prompt
4. Create data normalization engine
5. Build basic position ingestion API

### Sprint 2: Behavioral Analytics (Week 3-4)
1. Implement Chase Index calculation
2. Implement Tilt Index calculation
3. Implement Discipline Score logic
4. Implement Risk Score calculation
5. Create behavioral_analytics collection + API
6. Integrate with Risk Agent (Agent 5)

### Sprint 3: Command Center UI (Week 5-6)
1. Build Reality Panel
2. Build Edge Panel
3. Build Gap Analysis Panel
4. Build Behavioral Dashboard
5. Create Command Center aggregation service
6. Implement real-time WebSocket updates

### Sprint 4: Polish & Testing (Week 7-8)
1. Position history UI
2. Result tracking UI
3. Gamification (achievements, leaderboards)
4. WebSocket alert modals
5. End-to-end testing
6. Documentation

---

## 📊 Success Metrics

### User Engagement
- **Daily Active Users:** Track users logging positions daily
- **Positions Logged per User:** Target: 5+ per week
- **Command Center Views:** Track dashboard engagement
- **Behavioral Score Trends:** % of users improving Discipline Score

### Product Validation
- **OCR/LLM Accuracy:** Target: >90% correct parsing
- **Edge Alignment Rate:** Track % of user positions aligned with AI
- **Upgrade Conversion:** % of free users who upgrade to paid after using Command Center

### Behavioral Impact
- **Chase Index Reduction:** Track improvement over time
- **Tilt Events:** Count alerts triggered and user response
- **Negative EV Positions:** % reduction after coaching

---

## 🎯 Value Proposition Evolution

### Before Phase 15
**Old Pitch:** "We give you Monte Carlo simulations with 100k iterations."
**User Reaction:** "Cool, but how do I know it works?"

### After Phase 15
**New Pitch:** "Track your actual betting performance and see exactly where you're leaving money on the table vs our AI. We'll coach you to stop chasing losses and take higher-EV positions."

**User Reaction:** "This is like a personal trainer for betting. I can see my discipline score improving!"

---

## 📞 Next Steps

1. **Review & Approve Architecture** - Stakeholder sign-off
2. **Provision LLM API Keys** - OpenAI (GPT-4o) or Google (Gemini 1.5 Pro)
3. **Choose OCR Service** - Tesseract (free) vs Google Vision (paid)
4. **Update Database Indexes** - Optimize for position queries
5. **Begin Sprint 1** - Core ingestion pipeline

---

**Document Status:** ✅ Ready for Implementation  
**Estimated Delivery:** 8 weeks (4 sprints)  
**Risk Level:** 🟡 Medium (LLM parsing accuracy is key dependency)

---

*This architecture maintains compliance terminology ("Decision Capital", "Positions") while providing the sticky, behavioral analytics that convert free users to paid subscribers. The Command Center becomes the "moat" by showing users exactly how they're performing vs the AI's edge.*
