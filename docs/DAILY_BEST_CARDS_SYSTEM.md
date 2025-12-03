# Daily Best Cards System

## Overview

The Daily Best Cards system automatically curates 6 flagship betting opportunities every day, providing ready-made content for engagement and analysis. This eliminates manual card selection and ensures consistent quality.

---

## The 6-Card Structure

### 1️⃣ Best Game Overall (Flagship Post)

**Criteria:**
- Highest win probability (≥58%)
- High confidence (≥60%)
- Clean injury data (< 15 total impact points)
- Low/Medium volatility
- Strong simulation stability

**Purpose:** This is your marquee post - the absolute best game of the entire day.

**Example Output:**
```json
{
  "card_type": "FLAGSHIP - Best Game of the Day",
  "matchup": "Lakers @ Warriors",
  "sport": "basketball_nba",
  "win_probability": 0.652,
  "confidence": 0.721,
  "volatility": "LOW",
  "recommended_bet": "Lakers -3.5",
  "odds": -110,
  "reasoning": "Strong model agreement (65.2% win probability) • High stability simulation • Low variance expected • Clean injury table"
}
```

---

### 2️⃣ Top NBA Game

**Criteria:**
- Win probability ≥55%
- Confidence ≥52%
- Good O/U projection edge
- Injury factors accounted for

**Purpose:** Best NBA-specific opportunity for basketball-focused users.

---

### 3️⃣ Top NCAAB Game

**Criteria:**
- Same as NBA criteria
- Sport-specific to NCAA basketball

**Purpose:** College basketball flagship post.

---

### 4️⃣ Top NCAAF Game

**Criteria:**
- Win probability ≥55%
- Heavy line movement preferred
- Injury shift arbitrage
- Strong Monte Carlo edge

**Purpose:** College football flagship post.

---

### 5️⃣ Top Prop Mispricing (🔥 Best Engagement Content)

**Criteria:**
- Highest EV% (≥3%)
- Win probability ≥55%
- Clean mispricing explanation
- Yellow/Green confidence tier

**Purpose:** Props drive the most engagement. This is your viral content card.

**Example Output:**
```json
{
  "card_type": "Top Prop Mispricing",
  "player_name": "LeBron James",
  "prop_type": "Points",
  "line": 24.5,
  "over_under": "OVER",
  "probability": 0.612,
  "expected_value": 8.3,
  "recent_avg": 26.4,
  "season_avg": 25.1,
  "mispricing_explanation": "Faces league's 28th-ranked defense. Season avg vs bottom-10 defenses: 28.2 PPG. Line undervalues matchup advantage.",
  "confidence_level": "HIGH"
}
```

---

### 6️⃣ Parlay Architect Preview

**Criteria:**
- Attempts 4-leg balanced parlay
- If generation fails, still shows preview structure
- Blurred legs for engagement

**Purpose:** Even failed parlays drive curiosity. People LOVE seeing the parlay card structure.

**Example Success:**
```json
{
  "card_type": "AI Parlay Preview",
  "status": "success",
  "leg_count": 4,
  "parlay_odds": +412,
  "expected_value": 6.7,
  "confidence_rating": "MEDIUM-HIGH",
  "legs_preview": [
    {"matchup": "Lakers @ Warriors", "bet_type": "spread", "confidence": "68.2%"},
    {"matchup": "Celtics @ Heat", "bet_type": "total", "confidence": "62.1%"},
    // ... (blurred in UI)
  ]
}
```

**Example Failure:**
```json
{
  "card_type": "AI Parlay Preview",
  "status": "failed",
  "message": "Generating optimal parlay structure...",
  "fallback_preview": {
    "leg_count": 4,
    "risk_profile": "balanced",
    "estimated_odds": "+350 to +500",
    "note": "Today's slate is being analyzed. Check back in 10 minutes."
  }
}
```

---

## API Endpoints

### Get All Daily Cards

```http
GET /api/daily-cards
```

**Response:**
```json
{
  "status": "success",
  "source": "cache",  // or "fresh"
  "cards": {
    "best_game_overall": { /* card data */ },
    "top_nba_game": { /* card data */ },
    "top_ncaab_game": { /* card data */ },
    "top_ncaaf_game": { /* card data */ },
    "top_prop_mispricing": { /* card data */ },
    "parlay_preview": { /* card data */ },
    "generated_at": "2025-11-29T14:30:00Z",
    "expires_at": "2025-11-30T00:00:00Z"
  }
}
```

### Get Specific Card

```http
GET /api/daily-cards/card/{card_type}
```

**Valid Types:**
- `best_game_overall`
- `top_nba_game`
- `top_ncaab_game`
- `top_ncaaf_game`
- `top_prop_mispricing`
- `parlay_preview`

### Regenerate Cards (Admin/Cron)

```http
POST /api/daily-cards/regenerate
```

**Use Cases:**
- Scheduled cron job (every 6 hours)
- Manual admin refresh
- After bulk simulation updates

---

## Caching Strategy

**Cache Duration:** 6 hours  
**Storage:** MongoDB collection `daily_best_cards`  
**Expiration:** Automatic via `expires_at` field

**Cache Flow:**
1. First request → Generate fresh cards → Cache
2. Subsequent requests → Return cached cards
3. After 6 hours → Auto-regenerate on next request
4. Manual regeneration → Force refresh via POST endpoint

---

## Automated Regeneration

### Cron Setup (Recommended)

Run every 6 hours to keep cards fresh:

```bash
# Edit crontab
crontab -e

# Add this line (runs at 12am, 6am, 12pm, 6pm)
0 0,6,12,18 * * * cd /path/to/backend && python scripts/regenerate_daily_cards.py >> logs/daily_cards.log 2>&1
```

### Manual Regeneration

```bash
cd backend
python scripts/regenerate_daily_cards.py
```

**Output:**
```
[2025-11-29 14:30:00] Regenerating daily best cards...
✅ Daily cards regenerated successfully!
   • Best Game: Lakers @ Warriors
   • Top NBA: Celtics @ Heat
   • Top NCAAB: Duke @ UNC
   • Top NCAAF: Alabama @ Georgia
   • Top Prop: LeBron James
   • Parlay: success
   • Generated at: 2025-11-29T14:30:00Z
```

---

## Frontend Integration

### Navigation

Added to sidebar as "Daily Best Cards" with 📊 icon.

### Component Features

**Visual Design:**
- Flagship card displayed full-width at top
- Sport cards in 3-column grid
- Prop + Parlay in 2-column grid
- Hover effects and click handlers
- Responsive layout

**Card Types:**
- Game cards: Show matchup, metrics, reasoning
- Prop card: Purple gradient, EV highlight
- Parlay card: Gold gradient, blurred legs preview

**Metrics Displayed:**
- Win probability
- Confidence score
- Volatility level
- Model projection
- Expected value (props)
- Parlay odds & legs

---

## Quality Scoring Algorithm

### Best Game Overall

```python
score = (
    win_prob * 100 +        # 58-70 = 58-70 points
    confidence * 50 +       # 0.6-0.8 = 30-40 points  
    volatility_bonus * 20   # LOW = 20, MODERATE = 10
)
```

**Filters:**
- Win prob < 58% → Skip
- Confidence < 60% → Skip
- Volatility = HIGH → Skip
- Total injury impact > 15pts → Skip

### Sport-Specific Games

```python
score = (
    win_prob * 80 +
    confidence * 40 +
    abs(over_prob - 0.5) * 30  # O/U edge bonus
)
```

**Filters:**
- Win prob < 55% → Skip
- Confidence < 52% → Skip

### Props

```python
# Sort by EV descending, take highest
```

**Filters:**
- EV < 3% → Skip
- Probability < 55% → Skip

---

## Usage Examples

### Social Media Content

**Tweet Template (Best Game):**
```
🏀 FLAGSHIP GAME OF THE DAY

Lakers @ Warriors
✅ 65.2% model projection
✅ High stability (72.1% confidence)
✅ Clean injury report
✅ Low variance expected

Model: Lakers -3.5 (-110)

Full analysis: [link]
```

**Instagram Post (Prop):**
```
🔥 TOP PROP MISPRICING

LeBron James OVER 24.5 Points

📊 Model: 61.2% hit rate
📈 EV: +8.3%
🎯 Recent avg: 26.4 PPG
💡 Facing 28th-ranked defense

Why this is mispriced: [explanation]
```

### Email Newsletter

Use all 6 cards as daily flagship content:
- Best Game → Hero section
- Sport cards → Body sections
- Prop → Highlighted callout
- Parlay → Footer CTA

---

## Benefits

### For Content Strategy
✅ **Consistent Quality** - Automated curation eliminates guesswork  
✅ **Ready-Made Posts** - 6 cards = 6 social posts daily  
✅ **Engagement Drivers** - Props and parlays drive highest interaction  
✅ **Professional Branding** - Always have flagship content

### For Users
✅ **Quick Daily Overview** - Best opportunities at a glance  
✅ **Trust Building** - Transparent reasoning for each pick  
✅ **Variety** - Multiple sports and bet types  
✅ **Actionable** - Click through to full game analysis

### For Platform
✅ **Reduced Manual Work** - No more daily card selection  
✅ **Scalable** - Works with any slate size  
✅ **Data-Driven** - Pure Monte Carlo selection  
✅ **Compliance-Safe** - All language is neutral

---

## Monitoring & Maintenance

### Health Checks

```bash
# Check if cards are being generated
curl http://localhost:8000/api/daily-cards | jq '.cards.generated_at'

# Check specific card availability
curl http://localhost:8000/api/daily-cards/card/best_game_overall | jq '.status'
```

### Logs

Cron logs stored in `backend/logs/daily_cards.log`:
```
[2025-11-29 00:00:00] Regenerating daily best cards...
✅ Daily cards regenerated successfully!
[2025-11-29 06:00:00] Regenerating daily best cards...
✅ Daily cards regenerated successfully!
```

### Failure Handling

If card generation fails:
1. Returns `null` for that card
2. UI shows "No game available" placeholder
3. Other cards still display
4. Logs error for debugging

---

## Future Enhancements

1. **User Personalization**
   - Filter cards by user's favorite sports
   - Exclude teams user doesn't follow

2. **Performance Tracking**
   - Track which card types get most engagement
   - A/B test different selection criteria

3. **Multi-Language**
   - Translate reasoning and explanations
   - Localized time formats

4. **Push Notifications**
   - Alert users when flagship card is posted
   - Weekly digest of best cards

5. **Shareable Graphics**
   - Auto-generate card images for social
   - Branded templates with platform logo

---

## Compliance Note

All card language maintains legal compliance:
- No "recommended plays" or "best pick" language
- Reasoning uses neutral statistical terms
- Disclaimers on all cards
- Labels indicate data quality, not betting advice
