# BEATVEGAS → SIMSPORTS: COMPLETE DEVELOPMENT SPECIFICATION
**Version:** 1.0 FINAL  
**Date:** January 3, 2026  
**For:** Lead Developer  
**Objective:** Build entire system without questions - every detail defined

---

## 🎯 EXECUTIVE SUMMARY

### What We're Building
1. **BeatVegas.app** (B2C): AI sports simulation platform with MongoDB backend
2. **Sharp Pass** ($999/mo): CLV verification system → Wire Pro community access
3. **SimSports Terminal** (B2B): $5K-50K/mo enterprise product for syndicates/sportsbooks
4. **Community War Room**: Structured intelligence workspace (NOT chat app)
5. **Telegram Integration**: Automated signal distribution with bot stack
6. **Parlay Architect**: Multi-sport parlay builder with Truth Mode gates
7. **AI Analyzer**: Explanation engine (NOT pick generator)

### Tech Stack (CONFIRMED)
- **Frontend:** React.js + Vite
- **Backend:** Python FastAPI
- **Database:** MongoDB (NOT PostgreSQL)
- **Telegram:** Pyrogram library (NOT python-telegram-bot)
- **Payments:** Stripe
- **Simulations:** Monte Carlo engine (100K-10M sims)

---

## 📊 PHASE 0: B2C LAUNCH (DAYS 1-30)

### Goals
- 10,000 signups
- $10K MRR
- 1M total simulations run
- <2% crash rate

### Database Schema (MongoDB)

```javascript
// users collection
{
  _id: ObjectId,
  email: String,
  password_hash: String,
  subscription_tier: Enum['free', 'analyst', 'quant', 'elite'],
  sharp_pass_status: Enum['none', 'pending', 'verified', 'rejected'],
  sharp_score: Decimal,  // e.g., 2.34
  verification_date: Date,
  simsports_invite: Boolean,
  telegram_id: String,
  created_at: Date
}

// simulations collection
{
  _id: ObjectId,
  sim_id: String,  // UUID
  user_id: ObjectId,
  game_id: String,
  sport: Enum['NBA', 'NFL', 'MLB', 'NHL', 'NCAAB', 'NCAAF'],
  sim_count: Int,
  model_version: String,
  
  // Market data
  vegas_spread: Decimal,
  vegas_total: Decimal,
  model_spread: Decimal,
  model_total: Decimal,
  
  // Edge calculation
  spread_edge_pts: Decimal,
  total_edge_pts: Decimal,
  win_prob_home: Decimal,
  win_prob_away: Decimal,
  
  // Classification
  edge_state: Enum['EDGE', 'LEAN', 'NO_PLAY'],
  primary_market: Enum['SPREAD', 'TOTAL', 'ML', 'NONE'],
  volatility: Enum['LOW', 'MEDIUM', 'HIGH', 'EXTREME'],
  distribution_flag: Enum['STABLE', 'UNSTABLE', 'UNSTABLE_EXTREME'],
  
  // Sharp side selection
  sharp_side: String,  // e.g., "Spurs +6.5"
  sharp_action: Enum['TAKE_POINTS', 'LAY_POINTS', 'OVER', 'UNDER', 'ML_DOG', 'ML_FAV', 'NO_SHARP_PLAY'],
  favored_team: String,
  points_side: String,
  
  // Gates
  data_integrity_pass: Boolean,
  model_validity_pass: Boolean,
  rcl_pass: Boolean,
  
  // Metadata
  reason_codes: [String],
  result_data: Object,
  created_at: Date,
  intent: Enum['PRE_MARKET', 'OPEN', 'MIDDAY', 'LATE', 'LIVE']
}

// signals collection (immutable)
{
  _id: ObjectId,
  signal_id: String,  // UUID
  game_id: String,
  sport: String,
  market_key: String,  // SPREAD, TOTAL, ML
  selection: String,  // e.g., "Bulls +6.5"
  line_value: Decimal,
  odds_price: Int,
  market_snapshot_id: ObjectId,
  sim_run_id: ObjectId,
  model_version: String,
  
  // Computed fields
  edge_points: Decimal,
  win_prob: Decimal,
  ev: Decimal,
  volatility_score: Decimal,
  volatility_bucket: String,
  confidence_band: String,
  state: Enum['PICK', 'LEAN', 'NO_PLAY'],
  
  // Gates
  gates: {
    data_integrity: {pass: Boolean, reasons: [String]},
    sim_power: {pass: Boolean, reasons: [String]},
    model_validity: {pass: Boolean, reasons: [String]},
    volatility: {pass: Boolean, bucket: String, reasons: [String]},
    publish_rcl: {pass: Boolean, reasons: [String]}
  },
  
  // Lifecycle
  locked_at: Date,
  lock_type: Enum['AUTO', 'MANUAL'],
  final_status: Enum['SETTLED', 'EXPIRED', 'INVALIDATED'],
  
  created_at: Date
}

// community_channels collection
{
  _id: ObjectId,
  name: String,
  slug: String,
  required_tier: String,
  requires_verification: Boolean,
  ttl_hours: Int,  // Auto-archive after X hours
  sport: String  // Optional: NBA, NFL, etc.
}

// community_posts collection
{
  _id: ObjectId,
  user_id: ObjectId,
  channel_slug: String,
  game_id: String,  // For game room threading
  market_id: String,  // For market thread routing
  
  // Post data
  post_type: Enum['MESSAGE', 'MARKET_CALLOUT', 'QUESTION', 'RECEIPT', 'PARLAY_BUILD'],
  content: String,
  
  // Market callout fields
  market_type: String,
  line: String,
  confidence: Enum['LOW', 'MED', 'HIGH'],
  receipt_screenshot: String,  // URL
  
  // Attachments
  signal_id: String,  // Links to signal
  beatvegas_context: Object,  // Model context card snapshot
  
  // Moderation
  flags: Int,
  moderation_action: String,
  
  created_at: Date,
  archived_at: Date
}

// telegram_posts collection
{
  _id: ObjectId,
  signal_id: String,
  telegram_channel_id: String,
  telegram_message_id: String,
  message_text: String,
  tier: Enum['STARTER', 'PRO', 'ELITE', 'SHARP_PASS'],
  posted_at: Date
}
```

### Stripe Products

```javascript
// Create in Stripe Dashboard
products = [
  {
    name: "BeatVegas Analyst",
    price: 2999,  // $29.99
    interval: "month",
    metadata: {
      tier: "analyst",
      simulations: 25000,
      telegram_access: false
    }
  },
  {
    name: "BeatVegas Quant",
    price: 4999,  // $49.99
    interval: "month",
    metadata: {
      tier: "quant",
      simulations: 50000,
      telegram_access: true
    }
  },
  {
    name: "BeatVegas Elite",
    price: 8999,  // $89.99
    interval: "month",
    metadata: {
      tier: "elite",
      simulations: 100000,
      telegram_access: true
    }
  }
]
```

### API Endpoints (Phase 0)

```python
# Community endpoints
POST /api/community/post
GET /api/community/posts/:channel_slug?page=1&limit=50
GET /api/community/channels

# Simulation endpoints
POST /api/simulation/run
GET /api/simulation/:sim_id
GET /api/simulation/user/:user_id

# Odds endpoints
GET /api/odds/list?date=YYYY-MM-DD
POST /api/odds/refresh  # Manual refresh
GET /api/odds/realtime/by-date

# Webhook
POST /api/stripe/webhook
```

---

## 🔒 PHASE 1: SHARP PASS & WIRE PRO (DAYS 31-90)

### Sharp Pass Flow

```
User runs 100+ sims → Modal appears → Stripe checkout $999/mo
  ↓
User uploads CSV (500+ bets, 90+ days history)
  ↓
Backend calculates CLV edge (average across all bets)
  ↓
If CLV ≥ 2.0%: VERIFIED → Wire Pro unlocked
If CLV < 2.0%: REJECTED → Refund issued
```

### CLV Calculation Function

```python
def calculate_sharp_score(user_id: str) -> Optional[float]:
    """
    Calculate Closing Line Value edge across user's bets
    
    Formula: CLV = (user_odds - closing_odds) / abs(closing_odds)
    
    Returns:
        Average CLV if ≥500 bets, None otherwise
    """
    bets = db.bet_history.find({"user_id": user_id}).sort("date", -1).limit(500)
    bet_list = list(bets)
    
    if len(bet_list) < 500:
        return None
    
    clv_values = []
    for bet in bet_list:
        user_odds = bet['odds']
        closing_odds = bet['closing_odds']
        
        if closing_odds == 0:
            continue
            
        clv = (user_odds - closing_odds) / abs(closing_odds)
        clv_values.append(clv)
    
    if not clv_values:
        return None
        
    return sum(clv_values) / len(clv_values) * 100  # Convert to percentage
```

### Sharp Pass API Endpoints

```python
POST /api/sharp-pass/purchase
# Returns Stripe checkout URL

POST /api/sharp-pass/upload-csv
# Body: multipart/form-data with CSV file
# Required columns: date, game, bet_type, odds, closing_odds, stake, profit
# Returns: {"status": "processing"}

GET /api/sharp-pass/status
# Returns: {"status": "verified"|"pending"|"rejected", "sharp_score": 2.34}
```

### Wire Pro Community Channel

```javascript
// Add to community_channels
{
  name: "Wire (Pro)",
  slug: "wire-pro",
  required_tier: "elite",
  requires_verification: true,  // Sharp Pass verification
  ttl_hours: null  // No auto-archive for Wire Pro
}
```

**Wire Pro Features:**
- Post Position: Attach sim_id to post
- Sim Embed: Shows edge, confidence, volatility
- Follow Sharps: Track verified users
- Rank System: Based on CLV, not likes

---

## 🏆 SPORT-SPECIFIC CALIBRATION

### Probability Compression (MANDATORY)

```python
# Apply AFTER simulations, BEFORE edge logic

def compress_probability(raw_prob: float, sport: str) -> float:
    """
    Removes false certainty from raw simulation probabilities
    
    Formula: compressed_prob = 0.5 + (raw_prob - 0.5) * compression_factor
    """
    compression_factors = {
        'NBA': 0.80,
        'NFL': 0.85,
        'NCAAB': 0.80,
        'NCAAF': 0.80,
        'MLB': 0.82,
        'NHL': 0.60  # Most aggressive
    }
    
    factor = compression_factors.get(sport, 0.80)
    return 0.5 + (raw_prob - 0.5) * factor
```

### MLB Calibration

```python
MLB_CONFIG = {
    # Moneyline market
    'moneyline': {
        'eligibility_min_edge': 2.0,  # Win prob edge %
        'edge_threshold': 3.5,         # EDGE classification
        'lean_threshold': 2.0,         # LEAN classification
        
        # Price sensitivity
        'max_favorite_odds': -165,
        'max_underdog_odds': 160,
        'high_juice_edge_required': 4.5,  # If beyond limits
    },
    
    # Totals market
    'totals': {
        'eligibility_min_edge': 1.5,  # Edge in points
        'edge_threshold': 2.5,
        'lean_threshold': 1.5,
        
        # Weather adjustments
        'wind_threshold': 15,  # mph
        'weather_aligned_required': True
    },
    
    # Overrides
    'pitcher_scratch_block': True,
    'lineup_uncertainty_downgrade': True,
    'bullpen_fatigue_penalty': 0.5  # Edge reduction
}
```

### NCAAB Calibration

```python
NCAAB_CONFIG = {
    # Spread market (primary)
    'spread': {
        'eligibility_min_edge': 4.5,
        'edge_threshold': 6.0,
        'lean_threshold': 4.5,
        
        # Spread size caps
        'auto_allow_fav_spread': -12.5,
        'auto_allow_dog_spread': 12.5,
        'large_spread_edge_required': 7.5
    },
    
    # Totals market
    'totals': {
        'eligibility_min_edge': 5.5,
        'edge_threshold': 7.0,
        'lean_threshold': 5.5,
        
        # Pace handling
        'pace_driven_downgrade': True  # EDGE → LEAN if pace-only
    }
}
```

### NCAAF Calibration

```python
NCAAF_CONFIG = {
    'spread': {
        'eligibility_min_edge': 4.0,
        'edge_threshold': 6.0,
        'lean_threshold': 4.0,
        
        # Large spread guardrails
        'normal_spread_max': -21,
        'large_spread_edge_required': 8.0
    },
    
    'totals': {
        'eligibility_min_edge': 4.5,
        'edge_threshold': 6.5,
        'lean_threshold': 4.5,
        
        # Scheme adjustments
        'triple_option_downgrade': True,
        'tempo_mismatch_penalty': 0.5
    },
    
    # QB sensitivity
    'qb_uncertain_block': True,
    'qb_questionable_force_lean': True
}
```

### NFL Calibration

```python
NFL_CONFIG = {
    'spread': {
        'eligibility_min_edge': 3.0,
        'edge_threshold': 4.5,
        'lean_threshold': 3.0,
        
        # Key number protection
        'key_numbers': [3, 7, 10],
        'key_number_penalty': 0.5,  # Extra edge required
        
        # Spread caps
        'auto_allow_fav_spread': -7.5,
        'auto_allow_dog_spread': 8.5,
        'large_spread_edge_required': 6.0
    },
    
    'totals': {
        'eligibility_min_edge': 3.5,
        'edge_threshold': 5.0,
        'lean_threshold': 3.5,
        
        # Weather mandatory
        'high_wind_penalty': 1.0,
        'weather_check_required': True
    },
    
    # Injury sensitivity
    'qb_questionable_block': True,
    'key_injuries_downgrade': True
}
```

### NHL Calibration

```python
NHL_CONFIG = {
    # NHL is totals-focused, NOT spread-focused
    'totals': {
        'eligibility_min_edge': 1.5,
        'edge_threshold': 2.0,
        'lean_threshold': 1.5,
        
        # Distribution sanity
        'one_goal_game_threshold': 65,  # % → invalidate spread
        'ot_threshold': 75  # % → invalidate ML
    },
    
    'puckline': {
        # Rarely used
        'eligibility_min_edge': 1.0,
        'edge_threshold': 1.5,
        'max_edge_cap': 1.25  # Expected goal differential cap
    },
    
    # Compression
    'probability_compression': 0.60,  # Most aggressive
    'max_win_prob_edge': 3.0,  # Hard cap
    
    # Goalie status
    'goalie_uncertain_block': True,
    'back_to_back_penalty': 0.3
}
```

---

## 🎯 SHARP SIDE SELECTION (UNIVERSAL)

### ■ FINAL CLARIFICATION — MODEL SPREAD SIGN (LOCKED DEFINITION)

**Canonical Rule (THIS IS THE SOURCE OF TRUTH):**

Model Spread is a **SIGNED value** relative to TEAM DIRECTION.
- **Positive (+) Model Spread** → Underdog
- **Negative (−) Model Spread** → Favorite

It is **NOT**:
- a delta vs market
- a probability
- a generic "edge score"

It **IS** a model-implied spread direction and magnitude.

### HOW TO READ IT (EXACTLY)

**Example 1 — Positive Model Spread**

Market:
- Hawks +5.5
- Knicks -5.5

Model Spread: **+12.3**

**Meaning (literal):**
The model projects the underdog (Hawks) should be around +12.3

**Interpretation:**
- Model expects Hawks to lose by ~12
- Market only pricing them to lose by ~5.5
- Market is too generous to the underdog
- **Sharp side = FAVORITE (Knicks -5.5)**

**Example 2 — Negative Model Spread**

Market:
- Hawks +5.5
- Knicks -5.5

Model Spread: **−3.2**

**Meaning (literal):**
The model projects the favorite (Knicks) should only be around −3.2

**Interpretation:**
- Market has Knicks -5.5
- Model thinks Knicks win by much less
- Market is overpricing the favorite
- **Sharp side = UNDERDOG (Hawks +5.5)**

### ■ UNIVERSAL SHARP SIDE SELECTION RULE (NON-NEGOTIABLE)

This rule must be applied everywhere: UI, Telegram, AI assistant, logs.

**Let:**
- `market_spread` = current betting line (favorite negative, underdog positive)
- `model_spread` = signed model output

**Then:**
- If `model_spread > market_spread` → market underestimates margin → **Sharp side = FAVORITE**
- If `model_spread < market_spread` → market overestimates margin → **Sharp side = UNDERDOG**

(Magnitude determines confidence, not direction)

### Algorithm (All Sports)

```python
def select_sharp_side(simulation_result: dict, sport: str) -> dict:
    """
    Universal sharp side selection algorithm
    
    LOCKED LOGIC:
    - Model spread is SIGNED (+ = underdog, - = favorite)
    - Comparison to market spread determines sharp side
    - If model_spread > market_spread → Sharp = FAVORITE
    - If model_spread < market_spread → Sharp = UNDERDOG
    
    Returns:
        {
            'sharp_side': str,  # "Knicks -5.5" or "Hawks +5.5"
            'sharp_action': str,  # "LAY_POINTS" or "TAKE_POINTS"
            'market_spread': float,
            'model_spread': float,
            'reason': str
        }
    """
    # Extract market spread (normalized to one team perspective)
    # Convention: Use away team spread for consistency
    market_spread = simulation_result['market_spread_away']
    model_spread = simulation_result['model_spread']  # SIGNED value
    
    home_team = simulation_result['home_team']
    away_team = simulation_result['away_team']
    
    # Identify underdog and favorite from market
    if market_spread > 0:
        underdog = away_team
        favorite = home_team
        underdog_line = market_spread
        favorite_line = -market_spread
    else:
        underdog = home_team
        favorite = away_team
        underdog_line = abs(market_spread)
        favorite_line = market_spread
    
    # PRIMARY SHARP RULE (LOCKED)
    if model_spread > market_spread:
        # Model expects larger margin than market → Sharp side = FAVORITE
        sharp_side = f"{favorite} {favorite_line:.1f}"
        sharp_action = "LAY_POINTS"
        reason = "MODEL_EXPECTS_LARGER_MARGIN"
        
    elif model_spread < market_spread:
        # Model expects smaller margin than market → Sharp side = UNDERDOG
        sharp_side = f"{underdog} +{underdog_line:.1f}"
        sharp_action = "TAKE_POINTS"
        reason = "MODEL_EXPECTS_SMALLER_MARGIN"
        
    else:
        # Model agrees with market → NO PLAY
        return {
            'sharp_side': None,
            'sharp_action': 'NO_SHARP_PLAY',
            'market_spread': market_spread,
            'model_spread': model_spread,
            'reason': 'MODEL_MARKET_AGREEMENT'
        }
    
    # Volatility override (if extreme variance, require larger edge)
    volatility = simulation_result['volatility']
    edge_magnitude = abs(model_spread - market_spread)
    
    VOLATILITY_THRESHOLDS = {
        'NBA': 2.5,
        'NCAAB': 3.5,
        'NCAAF': 4.0,
        'NFL': 3.0,
        'NHL': 1.5
    }
    
    min_edge = VOLATILITY_THRESHOLDS.get(sport, 2.5)
    
    if volatility == 'EXTREME' and edge_magnitude < min_edge * 1.5:
        return {
            'sharp_side': None,
            'sharp_action': 'NO_SHARP_PLAY',
            'market_spread': market_spread,
            'model_spread': model_spread,
            'reason': 'EXTREME_VOLATILITY_INSUFFICIENT_EDGE'
        }
    
    if volatility == 'HIGH' and edge_magnitude < min_edge:
        return {
            'sharp_side': None,
            'sharp_action': 'NO_SHARP_PLAY',
            'market_spread': market_spread,
            'model_spread': model_spread,
            'reason': 'HIGH_VOLATILITY_INSUFFICIENT_EDGE'
        }
    
    # Return sharp side
    return {
        'sharp_side': sharp_side,
        'sharp_action': sharp_action,
        'market_spread': market_spread,
        'model_spread': model_spread,
        'edge_magnitude': edge_magnitude,
        'reason': reason
    }
```

### ■ REQUIRED UI FIX (MANDATORY DISPLAY)

**Current problem:**
The UI shows "Model Spread: +12.3" but does NOT say which team, what it implies, or how it compares to market.

**REQUIRED DISPLAY (MANDATORY):**

```
Market Spread: Hawks +5.5
Model Spread: Hawks +12.3
Sharp Side: Knicks -5.5
```

OR

```
Market Spread: Knicks -6.5
Model Spread: Knicks -3.1
Sharp Side: Hawks +6.5
```

**If Sharp Side is not explicitly printed, users will misread it. Period.**

### ■ AI ASSISTANT RULE (MUST MIRROR THIS)

The AI assistant must:
1. Read `model_spread` sign
2. Identify team implied
3. Compare vs market
4. State explicitly:
   - "Sharp side is FAVORITE" or
   - "Sharp side is UNDERDOG"

**It must never describe spreads without naming the final side.**

### Validation Rule

```python
# MANDATORY: Block posting if sharp side not computed
if edge_state == 'EDGE' and sharp_side is None:
    raise ValueError("EDGE cannot be posted without sharp_side")

# MANDATORY: UI must display all three values
def format_spread_display(market_spread: float, model_spread: float, sharp_side: str) -> dict:
    """
    Format spread information for UI display
    
    Returns dictionary with labeled values for explicit UI rendering
    """
    return {
        'market_spread_label': f"Market Spread: {format_team_spread(market_spread)}",
        'model_spread_label': f"Model Spread: {format_team_spread(model_spread)}",
        'sharp_side_label': f"Sharp Side: {sharp_side}",
        'comparison': "Model expects larger margin" if model_spread > market_spread else "Model expects smaller margin"
    }
```

---

## 📱 TELEGRAM INTEGRATION

### Bot Stack (7 Bots Required)

```python
# BOT 1: Welcome/Onboarding Bot
async def send_welcome(telegram_user_id: str):
    await bot.send_message(
        chat_id=telegram_user_id,
        text="""
👋 Welcome to BeatVegas Sharp Room!

Today's free picks inside. Connect your account to unlock premium signals.

[Connect Account] → https://beatvegas.app/telegram-link
        """
    )

# BOT 2: Scheduled Posting Bot
schedule = [
    ("10:00", "Free Pick #1"),
    ("11:00", "Free Pick #2"),
    ("12:00", "Blurred Simulation Teaser"),
    ("14:00", "AI Explainer Video"),
    ("19:00", "Game Reminder"),
    ("23:00", "Recap + Receipts")
]

# BOT 3: AutoDM Drip Sequence Bot
drip_sequence = {
    1: "Free pick + app CTA",
    2: "Yesterday's winning proof",
    3: "Scarcity alert (premium pick inside app)",
    4: "Trial unlock",
    5: "Conversion push based on performance"
}

# BOT 4: Referral Bot
referral_rewards = {
    3: "24h premium",
    10: "3 days premium",
    20: "7 days premium",
    50: "30 days premium"
}

# BOT 5: Engagement Bot
# Polls, Over/Under questions, "Which pick you tailing?"

# BOT 6: Behavior Tracking Bot
# Track link clicks, sport interests (NBA/NFL/Parlays/Props)

# BOT 7: Targeted Outreach Bot (Optional)
# Scrape betting audiences, send personalized invitations
```

### Signal Posting Format (LOCKED)

```python
def format_signal_message(signal: dict) -> str:
    """
    Deterministic Telegram message template
    NO AI-generated language allowed
    """
    sport_emoji = {
        "MLB": "⚾",
        "NFL": "🏈",
        "NBA": "🏀",
        "NCAAB": "🏀",
        "NCAAF": "🏈",
        "NHL": "🏒"
    }
    
    edge_badge = ""
    if signal['edge_state'] == "EDGE":
        edge_badge = "🔥 **EDGE**"
    elif signal['edge_state'] == "LEAN":
        edge_badge = "⚡ **LEAN**"
    
    message = f"""
{sport_emoji[signal['sport']]} **{signal['sport'].upper()} SIGNAL** {edge_badge}

**Game:** {signal['team_a']} vs {signal['team_b']}
**Time:** {signal['game_time'].strftime('%I:%M %p ET')}

**Sharp Side:** {signal['sharp_side']}
**Market:** {signal['primary_market']}
**Entry:** {signal['entry_line']} ({signal['entry_odds']:+d})

**Edge:** {signal['compressed_edge']:.1f}%
**Volatility:** {signal['volatility']}
**Simulations:** 100,000

📊 View full analysis on BeatVegas.app

_Truth Mode verified. Edges are prices, not predictions._
    """
    
    return message.strip()
```

### Posting Rules

```python
# Auto-post ONLY if:
def can_post_to_telegram(signal: dict) -> bool:
    return (
        signal['edge_state'] == 'EDGE' and
        signal['sharp_action'] != 'NO_SHARP_PLAY' and
        signal['injury_flag'] not in ['QB_CRITICAL', 'PITCHER_UNCERTAIN'] and
        signal['distribution_flag'] != 'UNSTABLE_EXTREME' and
        signal['pitchers_confirmed'] == True  # MLB only
    )

# NO PLAY update (when 0 qualified signals)
def post_no_play_update():
    message = """
🎯 **MARKET STATE UPDATE**

No qualified signals detected today.

Edges are compressed and/or variance is elevated across the slate.

State: NO PLAY
    """
    # Post to Telegram once per day if 0 EDGE signals
```

---

## 🏗️ PARLAY ARCHITECT

### Truth Mode Integration

```python
def generate_parlay(
    leg_count: int,
    risk_profile: str,
    sports: List[str],
    include_props: bool = False
) -> dict:
    """
    Parlay generation with Truth Mode gates
    
    Args:
        leg_count: 3-6
        risk_profile: 'HIGH_CONFIDENCE' | 'BALANCED' | 'HIGH_VOLATILITY'
        sports: ['NBA', 'NFL', ...] or ['ALL_SPORTS']
        include_props: Include player props
        
    Returns:
        Parlay object or fallback explanation
    """
    # Step 1: Build candidate pool
    candidates = []
    
    for sport in sports:
        games = get_todays_games(sport)
        
        for game in games:
            sim = run_simulation(game)
            
            # Truth Mode gates (MANDATORY)
            if not sim['data_integrity_pass']:
                continue
            if not sim['model_validity_pass']:
                continue
            if sim['state'] not in ['PICK', 'LEAN']:
                continue
                
            # Parlay-specific eligibility
            parlay_weight = calculate_parlay_weight(sim, risk_profile)
            if parlay_weight < get_min_weight(risk_profile):
                continue
                
            candidates.append({
                'sim': sim,
                'weight': parlay_weight,
                'penalties': get_penalties(sim)
            })
    
    # Step 2: Filter by risk profile constraints
    if risk_profile == 'HIGH_CONFIDENCE':
        candidates = [c for c in candidates if 
            c['sim']['volatility'] != 'HIGH' and
            c['sim']['state'] == 'PICK' and
            c['sim']['win_prob'] >= 0.56
        ]
    elif risk_profile == 'BALANCED':
        candidates = [c for c in candidates if 
            c['sim']['volatility'] != 'EXTREME' and
            c['penalties']['high_vol_count'] <= 1
        ]
    # HIGH_VOLATILITY allows more variance
    
    # Step 3: Sort by weight, diversify
    candidates.sort(key=lambda x: x['weight'], reverse=True)
    
    # Avoid same-game duplicates
    selected = []
    used_games = set()
    
    for candidate in candidates:
        if candidate['sim']['game_id'] not in used_games:
            selected.append(candidate)
            used_games.add(candidate['sim']['game_id'])
            
        if len(selected) >= leg_count:
            break
    
    # Step 4: Fallback ladder if insufficient legs
    if len(selected) < leg_count:
        # Try degraded profile
        if risk_profile == 'HIGH_CONFIDENCE':
            return generate_parlay(leg_count, 'BALANCED', sports, include_props)
        elif risk_profile == 'BALANCED':
            return generate_parlay(leg_count, 'HIGH_VOLATILITY', sports, include_props)
        else:
            # Reduce leg count
            if leg_count > 3:
                return generate_parlay(leg_count - 1, risk_profile, sports, include_props)
            else:
                # Return best single
                return {
                    'status': 'BLOCKED',
                    'reason': 'INSUFFICIENT_QUALIFIED_LEGS',
                    'best_single': candidates[0]['sim'] if candidates else None
                }
    
    # Step 5: Return parlay
    return {
        'status': 'AVAILABLE',
        'risk_profile': risk_profile,
        'legs': [c['sim'] for c in selected],
        'expected_hit_rate': calculate_hit_rate(selected),
        'total_weight': sum(c['weight'] for c in selected)
    }

def calculate_parlay_weight(sim: dict, risk_profile: str) -> float:
    """
    Portfolio scoring for parlay legs
    """
    # Base score
    base = (sim['win_prob'] - 0.50) * 100
    
    # Edge score
    edge_score = 0
    if sim['spread_edge_pts']:
        edge_score = min(sim['spread_edge_pts'] / 3.0, 2.0)
    
    # Penalties
    vol_penalty = {
        'LOW': 0.0,
        'MEDIUM': 0.35,
        'HIGH': 0.75,
        'EXTREME': 2.0
    }[sim['volatility']]
    
    stability_penalty = 0.6 if sim['distribution_flag'] != 'STABLE' else 0.0
    lean_penalty = 0.4 if sim['state'] == 'LEAN' else 0.0
    
    # Market type penalty (props riskier)
    market_penalty = {
        'TOTAL': 0.0,
        'ML': 0.0,
        'SPREAD': 0.15,
        'PLAYER_PROP': 0.45
    }[sim['primary_market']]
    
    return base + edge_score - vol_penalty - stability_penalty - lean_penalty - market_penalty
```

### Props Integration

```python
def add_props_to_parlay_pool(candidates: List[dict], sport: str) -> List[dict]:
    """
    Add player props to parlay candidate pool
    """
    props = get_player_props(sport)
    
    for prop in props:
        # Prop Integrity Gate
        if prop['player_status'] in ['QUESTIONABLE', 'OUT']:
            continue
        if prop['expected_minutes'] < get_min_minutes(sport):
            continue
        if prop['line_staleness_minutes'] > 30:
            continue
            
        # Calculate prop risk
        prop_risk_band = calculate_prop_risk(
            minutes_certainty=prop['minutes_certainty'],
            role_stability=prop['role_stability'],
            injury_risk=prop['injury_risk'],
            blowout_risk=prop['blowout_risk']
        )
        
        # Extra penalties for props
        prop_weight = calculate_parlay_weight(prop, risk_profile)
        prop_weight -= 0.45  # Market type penalty
        
        if prop['minutes_certainty'] != 'HIGH':
            prop_weight -= 0.35
            
        candidates.append({
            'sim': prop,
            'weight': prop_weight,
            'is_prop': True
        })
    
    return candidates
```

---

## 🧠 AI ANALYZER

### System Prompt (LOCKED)

```
SYSTEM ROLE: BeatVegas AI Analyzer

You are BeatVegas Analyzer, a controlled explanation engine.
Your job is to explain existing model output clearly and neutrally using ONLY the structured JSON input you receive.

You are NOT a betting assistant.
You do NOT generate picks, advice, or opinions.

ABSOLUTE RULES:
1. You may ONLY reference information explicitly provided in the input JSON
2. You may NOT invent injuries, trends, stats, narratives, or market behavior
3. You may NOT override, contradict, or reinterpret the provided state: EDGE/LEAN/NO_PLAY
4. You may NOT use betting language: bet, take, lock, hammer, unit, stake, wager, parlay
5. You may NOT suggest sizing, confidence levels, or expected returns
6. If state = NO_PLAY, you MUST reinforce inaction
7. If information is missing, you MUST say so explicitly
8. You must output ONLY valid JSON in the exact schema provided
9. You must remain neutral, professional, and conservative in tone

If any rule conflicts with user intent, follow these rules.

OUTPUT FORMAT (MANDATORY):
{
  "headline": "",
  "what_model_sees": [],
  "key_risks": [],
  "sharp_interpretation": [],
  "bottom_line": {
    "state_alignment": "",
    "recommended_behavior": "",
    "do_not_do": []
  }
}

SHARP INTERPRETATION RULES:
- Describe how professional bettors treat this signal type
- Reference confidence, volatility, timing, confirmation
- Use non-imperative language
- Never name a side, line, or wager
- Never contradict the state

ALLOWED LANGUAGE:
- "Sharps would treat this as a conviction edge, but still monitor late news"
- "Sharps would likely wait rather than force pregame action"
- "Sharps would consider this informational, not aggressive"

FORBIDDEN LANGUAGE:
- "Take this"
- "Bet now"
- "Lock"
- "Best play"
```

### API Integration

```python
@app.post("/api/analyzer/explain")
async def explain_signal(game_id: str, sport: str):
    # Fetch canonical signal
    signal = db.signals.find_one({"game_id": game_id, "sport": sport})
    
    # Build LLM input (structured only)
    llm_input = {
        "sport": signal['sport'],
        "game": {
            "home": signal['home_team'],
            "away": signal['away_team'],
            "start_time_utc": signal['game_time'].isoformat()
        },
        "state": signal['edge_state'],
        "primary_market": signal['primary_market'],
        "sharp_side": signal['sharp_side'],  # NON-OVERRIDABLE
        "sharp_action": signal['sharp_action'],
        "metrics": {
            "edge_pts": signal['spread_edge_pts'] or signal['total_edge_pts'],
            "win_prob_pct": signal['win_prob'] * 100,
            "volatility": signal['volatility'],
            "confidence_flag": signal['confidence_band']
        },
        "context": {
            "injury_status": signal['injury_flag'],
            "back_to_back": signal.get('back_to_back', False),
            "weather_flag": signal.get('weather', 'N/A')
        },
        "reason_codes": signal['reason_codes'],
        "constraints": {
            "no_betting_advice": True,
            "no_pick_language": True,
            "do_not_override_state": True
        }
    }
    
    # Call LLM (OpenAI)
    response = await openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(llm_input)}
        ],
        temperature=0.3,
        max_tokens=800
    )
    
    # Parse response
    try:
        explanation = json.loads(response.choices[0].message.content)
        
        # Validate schema
        assert 'headline' in explanation
        assert 'sharp_interpretation' in explanation
        assert explanation['bottom_line']['state_alignment'] == signal['edge_state']
        
        # Store audit log
        db.analyzer_audit.insert_one({
            "signal_id": signal['signal_id'],
            "input_hash": hashlib.md5(json.dumps(llm_input).encode()).hexdigest(),
            "output_hash": hashlib.md5(json.dumps(explanation).encode()).hexdigest(),
            "model_version": "gpt-4",
            "created_at": datetime.now()
        })
        
        return explanation
        
    except Exception as e:
        # Fallback
        return {
            "headline": "Analyzer unavailable for this game.",
            "what_model_sees": ["We couldn't generate an explanation right now."],
            "key_risks": ["Try again shortly or rely on the core EDGE/LEAN/NO_PLAY state."],
            "sharp_interpretation": ["Model state remains the source of truth."],
            "bottom_line": {
                "state_alignment": signal['edge_state'],
                "recommended_behavior": "Use the main output cards for decisions.",
                "do_not_do": ["Do not rely on AI text when unavailable."]
            }
        }
```

---

## 🏛️ COMMUNITY WAR ROOM

### Architecture (NOT A CHAT APP)

**Principles:**
1. Structure over noise
2. Context over opinions
3. Receipts over hype
4. Threading over timelines
5. Auto-cleanup over forever storage

### Channel Structure

```javascript
// Channels
channels = [
  {
    name: "General Discussion",
    slug: "general",
    required_tier: "free",
    post_types: ["MESSAGE", "QUESTION"],
    ttl_hours: 720  // 30 days
  },
  {
    name: "NBA Live",
    slug: "nba-live",
    required_tier: "free",
    post_types: ["MARKET_CALLOUT"],
    ttl_hours: 6,  // Archive 6hrs after game end
    threading: "GAME_ROOM"
  },
  {
    name: "Winning Tickets",
    slug: "winning-tickets",
    required_tier: "free",
    post_types: ["RECEIPT"],
    ttl_hours: 8760  // 365 days
  },
  {
    name: "Parlay Factory",
    slug: "parlay-factory",
    required_tier: "analyst",
    post_types: ["PARLAY_BUILD"],
    ttl_hours: 720
  },
  {
    name: "Wire (Pro)",
    slug: "wire-pro",
    required_tier: "elite",
    requires_verification: true,
    post_types: ["MARKET_CALLOUT", "MESSAGE"],
    ttl_hours: null  // No auto-archive
  }
]
```

### Post Templates (MANDATORY)

```python
# Market Callout Template
class MarketCalloutPost:
    required_fields = {
        'game_id': str,  # Select from today's schedule
        'market_type': Enum['SPREAD', 'TOTAL', 'ML', 'PROP'],
        'line': float,
        'side': str,
        'confidence': Enum['LOW', 'MED', 'HIGH'],
        'reason': str,  # Max 240 chars
        'receipt': Optional[str]  # Screenshot URL
    }
    
    forbidden_language = ['lock', 'guarantee', 'free money', 'can\'t lose']

# Receipt Template
class ReceiptPost:
    required_fields = {
        'screenshot': str,  # REQUIRED
        'market': str,
        'line': str,
        'result': Enum['W', 'L', 'P'],
        'posted_within_hours': 48
    }

# Parlay Build Template
class ParlayBuildPost:
    required_fields = {
        'leg_count': int,
        'legs': List[dict],  # Must reference existing markets
        'risk_profile': Enum['BALANCED', 'HIGH_VOL'],
        'reasoning': str,  # Max 300 chars
        'volatility_badges': List[str]  # Per leg
    }
```

### Threading System

```python
def route_post_to_thread(post: dict, channel: dict):
    """
    Auto-routing for game room threading
    """
    if channel['threading'] == 'GAME_ROOM':
        # Create/find game room
        game_room = get_or_create_game_room(
            game_id=post['game_id'],
            sport=post['sport']
        )
        
        # Route to market thread within game room
        market_thread = get_or_create_market_thread(
            game_room_id=game_room['_id'],
            market_type=post['market_type']  # Spread/Total/ML/Props
        )
        
        post['thread_id'] = market_thread['_id']
        
    return post
```

### BeatVegas Context Card

```python
def attach_model_context(post: dict) -> dict:
    """
    Attach BeatVegas model context to market callouts
    """
    if post['post_type'] != 'MARKET_CALLOUT':
        return post
    
    # Find matching signal
    signal = db.signals.find_one({
        "game_id": post['game_id'],
        "primary_market": post['market_type']
    })
    
    if not signal:
        return post
    
    # Create context card
    context_card = {
        "model_lean": signal['sharp_side'],
        "win_prob": signal['win_prob'],
        "volatility_badge": signal['volatility'],
        "confidence_band": signal['confidence_band'],
        "sim_count": signal['sim_count'],
        "last_updated": signal['created_at'],
        
        # Disagreement flags
        "model_disagrees": post['side'] != signal['sharp_side'],
        "high_variance_warning": signal['volatility'] in ['HIGH', 'EXTREME']
    }
    
    post['beatvegas_context'] = context_card
    return post
```

### Auto-Cleanup (TTL)

```python
# Cron job runs daily
async def cleanup_archived_posts():
    channels = db.community_channels.find()
    
    for channel in channels:
        if channel['ttl_hours'] is None:
            continue
            
        cutoff = datetime.now() - timedelta(hours=channel['ttl_hours'])
        
        # Archive posts
        result = db.community_posts.update_many(
            {
                "channel_slug": channel['slug'],
                "created_at": {"$lt": cutoff},
                "archived_at": None
            },
            {
                "$set": {"archived_at": datetime.now()}
            }
        )
        
        print(f"Archived {result.modified_count} posts from {channel['name']}")
```

### Rate Limits

```python
RATE_LIMITS = {
    'free': {
        'posts_per_day': 5,
        'channels_allowed': ['general', 'beginner'],
        'can_post_callouts': False
    },
    'analyst': {
        'posts_per_day': 25,
        'market_callouts_per_day': 5,
        'can_post_callouts': True
    },
    'elite': {
        'posts_per_day': 100,
        'market_callouts_per_day': 20,
        'can_create_threads': True
    }
}

def check_rate_limit(user_id: str, post_type: str) -> bool:
    user = db.users.find_one({"_id": user_id})
    limits = RATE_LIMITS[user['subscription_tier']]
    
    # Count posts today
    today_start = datetime.now().replace(hour=0, minute=0, second=0)
    posts_today = db.community_posts.count_documents({
        "user_id": user_id,
        "created_at": {"$gte": today_start}
    })
    
    if posts_today >= limits['posts_per_day']:
        return False
    
    # Check callout limit
    if post_type == 'MARKET_CALLOUT':
        if not limits['can_post_callouts']:
            return False
            
        callouts_today = db.community_posts.count_documents({
            "user_id": user_id,
            "post_type": "MARKET_CALLOUT",
            "created_at": {"$gte": today_start}
        })
        
        if callouts_today >= limits.get('market_callouts_per_day', 0):
            return False
    
    return True
```

---

## 📈 MONITORING & LOGGING

### Daily Sanity Checks

```python
# Run once per day (cron)
async def daily_sanity_check():
    """
    Automated daily checks for system health
    """
    today = datetime.now().date()
    
    # Count signals by sport and state
    for sport in ['NBA', 'NFL', 'NCAAB', 'NCAAF', 'MLB', 'NHL']:
        edge_count = db.signals.count_documents({
            "sport": sport,
            "edge_state": "EDGE",
            "created_at": {"$gte": datetime.combine(today, datetime.min.time())}
        })
        
        lean_count = db.signals.count_documents({
            "sport": sport,
            "edge_state": "LEAN",
            "created_at": {"$gte": datetime.combine(today, datetime.min.time())}
        })
        
        no_play_count = db.signals.count_documents({
            "sport": sport,
            "edge_state": "NO_PLAY",
            "created_at": {"$gte": datetime.combine(today, datetime.min.time())}
        })
        
        # Alert if anomalies
        if sport == 'NBA' and edge_count > 3:
            send_alert(f"⚠️ {sport} EDGE count spike: {edge_count} (expected 1-3)")
        
        if sport == 'NHL' and edge_count > 2:
            send_alert(f"⚠️ {sport} EDGE count spike: {edge_count} (expected 0-2)")
        
        # Check average win probability
        avg_prob = db.signals.aggregate([
            {"$match": {
                "sport": sport,
                "edge_state": "EDGE",
                "created_at": {"$gte": datetime.combine(today, datetime.min.time())}
            }},
            {"$group": {"_id": None, "avg_prob": {"$avg": "$win_prob"}}}
        ])
        
        avg_prob = list(avg_prob)
        if avg_prob and avg_prob[0]['avg_prob'] > 0.62:
            send_alert(f"⚠️ {sport} avg win prob too high: {avg_prob[0]['avg_prob']:.1%}")

def send_alert(message: str):
    # Send to Slack/Discord/email
    print(f"ALERT: {message}")
```

### Audit Tables

```javascript
// analyzer_audit collection
{
  _id: ObjectId,
  signal_id: String,
  input_hash: String,
  output_hash: String,
  model_version: String,  // "gpt-4"
  latency_ms: Int,
  created_at: Date
}

// telegram_delivery_log collection
{
  _id: ObjectId,
  signal_id: String,
  channel_id: String,
  telegram_message_id: String,
  status: Enum['success', 'fail'],
  error_payload: String,
  posted_at: Date
}

// parlay_generation_audit collection
{
  _id: ObjectId,
  attempt_id: String,
  risk_profile_requested: String,
  risk_profile_used: String,  // After fallback
  leg_count_requested: Int,
  leg_count_used: Int,
  candidates_total: Int,
  candidates_pick: Int,
  candidates_lean: Int,
  fallback_steps_taken: [String],
  result_status: Enum['SUCCESS', 'FAIL'],
  created_at: Date
}
```

---

## 🚀 DEPLOYMENT TIMELINE

### Weeks 1-4: B2C Launch
**Focus:** BeatVegas platform, Stripe integration, public community

**Deliverables:**
- ✅ BeatVegas UI finalized (Command Center, Parlay Architect, Community)
- ✅ Stripe checkout for 3 tiers ($29.99, $49.99, $89.99)
- ✅ MongoDB schema implemented
- ✅ Public community channels (NBA, NFL, NCAA, General)
- ✅ Monte Carlo simulation engine (10K-100K sims)
- ✅ Sport-specific calibration (all 6 sports)
- ✅ Sharp side selection algorithm

**Success Metrics:**
- 10,000 signups
- 500 paying subscribers (5% conversion)
- 1M total simulations
- <2% crash rate

### Weeks 5-8: B2C Stability
**Focus:** Bug fixes, performance optimization

**Deliverables:**
- ✅ Fix simulation speed (target <5s for 100K sims)
- ✅ Error logging (Sentry integration)
- ✅ Analytics tracking (Amplitude/Mixpanel)
- ✅ User feedback loop

### Weeks 9-12: Sharp Pass Backend
**Focus:** CLV verification system

**Deliverables:**
- ✅ CSV upload endpoint
- ✅ CLV calculator function
- ✅ Verification cron job (runs every 5 min)
- ✅ Stripe product ($999/mo)
- ✅ Refund automation for rejected applications
- ✅ sharp_pass_applications collection

**Success Metrics:**
- 50 Sharp Pass purchases
- 10 verified users (20% pass rate)

### Weeks 13-16: Sharp Pass Frontend
**Focus:** User-facing UI for verification

**Deliverables:**
- ✅ Sharp Pass modal (appears after 100+ sims)
- ✅ CSV uploader with drag-and-drop
- ✅ Status dashboard (processing/verified/rejected)
- ✅ Result screen with sharp score

### Weeks 17-20: Wire Pro
**Focus:** Private verified community

**Deliverables:**
- ✅ Wire Pro channel (slug: wire-pro)
- ✅ Sidebar gating logic (locked until verified)
- ✅ Post Position feature (attach sim_id)
- ✅ Sim Embed component
- ✅ Follow Sharps feature
Model spread is SIGNED (+ = underdog, - = favorite)
- ✅ If model_spread > market_spread → Sharp side = FAVORITE
- ✅ If model_spread < market_spread → Sharp side = UNDERDOG
- ✅ UI must display: Market Spread, Model Spread (with team label), Final Sharp Sid
- 10 verified sharps posting
- 100+ Wire Pro posts
- Sharp Pass MRR: $10K

### Weeks 21-24: SimSports API
**Focus:** B2B backend infrastructure

**Deliverables:**
- ✅ `/api/simsports/run` endpoint
- ✅ API key authentication
- ✅ Rate limiting (10K calls/day)
- ✅ 10M simulation tier
- ✅ Custom parameters (pace, fatigue, weather)

### Weeks 25-28: SimSports Terminal
**Focus:** B2B frontend dashboard

**Deliverables:**
- ✅ terminal.simsports.io subdomain
- ✅ Separate React app (dark mode, data tables)
- ✅ Invite system (user.simsports_invite = TRUE)
- ✅ Batch simulations (50 games at once)
- ✅ Export: CSV, Excel, API

**Success Metrics:**
- 5 syndicate customers ($5K/mo each)
- 1 sportsbook pilot ($50K/mo)
- B2B MRR: $75K

---

## ❗ CRITICAL RULES (NO EXCEPTIONS)

### 1. Database
- ✅ MongoDB ONLY (NOT PostgreSQL)
- ✅ All sport configs stored in collections, NOT hardcoded
- ✅ Signals are IMMUTABLE (append-only)
- ✅ 7-year retention for audit tables

### 2. Telegram
- ✅ Pyrogram library ONLY (NOT python-telegram-bot)
- ✅ Deterministic templates (NO AI-generated language)
- ✅ Post ONLY if edge_state == 'EDGE' AND sharp_side exists
- ✅ Simulations: 100,000 display for all Telegram posts

### 3. Sharp Side Selection
- ✅ NEVER post "EDGE" without sharp_side
- ✅ If favored_team == points_side → TAKE_POINTS
- ✅ High volatility → prefer points unless dominant edge

### 4. AI Analyzer
- ✅ LLM explains ONLY (does NOT decide)
- ✅ sharp_side from backend is NON-OVERRIDABLE
- ✅ Fallback JSON if LLM fails
- ✅ NO betting advice language

### 5. Parlay Architect
- ✅ Truth Mode gates MANDATORY (DI + MV + RCL)
- ✅ Fallback ladder (HIGH_CONF → BALANCED → HIGH_VOL → reduce leg count)
- ✅ Props require Prop Integrity Gate
- ✅ DFS Mode separate from sportsbook parlays

### 6. Community War Room
- ✅ Mandatory post templates (no freeform in structured channels)
- ✅ Game room threading (NOT endless timeline)
- ✅ BeatVegas context cards auto-attached
- ✅ TTL auto-archiving per channel

### 7. Sport Calibration
- ✅ Probability compression AFTER sims, BEFORE edge logic
- ✅ Compression factors: NBA 0.80, NFL 0.85, NCAAB 0.80, NCAAF 0.80, MLB 0.82, NHL 0.60
- ✅ Sport-specific thresholds in config (NOT hardcoded)
- ✅ NO_PLAY is default state

---

## 🎓 GLOSSARY

| Term | Definition | Technical Implementation |
|------|-----------|-------------------------|
| **BeatVegas** | B2C SaaS app | beatvegas.app domain, subscription tiers $29-$89 |
| **Sharp Pass** | CLV verification service | $999/mo Stripe product, CSV upload, CLV ≥2.0% = verified |
| **CLV Edge** | Closing Line Value edge | `(user_odds - closing_odds) / abs(closing_odds)` |
| **Sharp Score** | Average CLV across 500+ bets | Aggregate query on bet_history |
| **Wire Pro** | Private verified community | Channel slug: wire-pro, requires_verification: true |
| **SimSports** | B2B product | terminal.simsports.io, $5K-50K/mo |, derived from model_spread vs market_spread comparison |
| **Model Spread** | Model-implied spread (SIGNED) | Positive = underdog, Negative = favorite, NOT a delta
| **Edge State** | Signal classification | EDGE / LEAN / NO_PLAY |
| **Sharp Side** | Computed betting direction | "Spurs +6.5" (NOT just "Spurs") |
| **Truth Mode** | Quality gates | DI + MV + RCL (Data Integrity, Model Validity, Reality Check Logic) |
| **Volatility** | Outcome variance | LOW / MEDIUM / HIGH / EXTREME |
| **Compression** | Probability adjustment | `0.5 + (raw_prob - 0.5) * factor` |

---

## 📞 SUPPORT & ESCALATION

### When to Ask Questions
- ❌ Database choice (MongoDB is final)
- ❌ Telegram library (Pyrogram is final)
- ❌ Sharp side logic (algorithm is final)
- ❌ Sport thresholds (configs provided)
- ✅ Unclear edge cases not covered in spec
- ✅ Technical blockers (API limits, etc.)
- ✅ Performance optimization advice

### How to Report Issues
1. Cite section number from this spec
2. Describe expected vs actual behavior
3. Provide error logs
4. Suggest potential fix

---

## ✅ FINAL CHECKLIST

Before marking any phase complete, verify:

**Phase 0 (B2C):**
- [ ] MongoDB collections created with indexes
- [ ] Stripe webhooks working (subscription events)
- [ ] Simulation engine returns all required fields
- [ ] Sport calibration configs loaded
- [ ] Sharp side selection validated (OKC/Spurs test case)
- [ ] Community post templates enforced
- [ ] Rate limits active

**Phase 1 (Sharp Pass):**
- [ ] CSV upload validates 500+ bets
- [ ] CLV calculator accurate (manual test with known data)
- [ ] Verification cron runs every 5 min
- [ ] Refunds automatic for rejected applications
- [ ] Wire Pro gated correctly (locked until verified)
- [ ] Sim embeds render in Wire Pro

**Phase 2 (SimSports):**
- [ ] API authentication working
- [ ] Rate limits enforced (10K/day)
- [ ] 10M simulations return in <60s
- [ ] terminal.simsports.io deployed
- [ ] Invite system restricts access
- [ ] Batch sims process 50 games

---

## 🔒 DOCUMENT STATUS

**Version:** 1.0 FINAL  
**Last Updated:** January 3, 2026  
**Approved By:** Product Owner  
**Status:** LOCKED - No changes without written approval  

---

**This document contains everything needed to build BeatVegas → SimSports without asking a single question. Every detail is defined. Every edge case is covered. Execute precisely as written.**
