# BeatVegas & Omni Edge AI Platform

**Version:** 2.0.0  
**Business Goal:** Build a "Sports Analytics" data asset targeting $3.6B acquisition at 25-30x ARR multiple

---

## 🎯 Core Business Mandate

### Primary Objective
Build a **licensable sports analytics data asset**, not just a SaaS app. Every architectural decision must be justifiable for a 25-30x ARR acquisition multiple by a major sportsbook (FanDuel, DraftKings, etc.).

### Growth Constraint
**Zero-ad spend growth** driven exclusively by:
1. **Event-driven Affiliate Viral Loop** - Track `?ref=AFF_ID` through entire funnel
2. **Community-based Data Moat** - "Pay-to-Influence" model where Pro/Elite users create the training data

---

## 🏗️ System Architecture (Dual-Domain)

### A) `BeatVegas.app` (The Consumer Funnel)
- **Purpose:** Public-facing marketing, user dashboard, payment processing
- **A/B Test Engine:** 5 concurrent variants with 90-day cookie persistence
- **Acquisition:** Event-driven referral tracking with Stripe webhook integration

### B) `BeatVegas.io` (The AI & Data Asset)
- **Purpose:** Backend, affiliate, and developer layer
- **Infrastructure:**
  - `api.beatvegas.io` - Core API
  - `partners.beatvegas.io` - Affiliate dashboard
  - `docs.beatvegas.io` - API documentation
- **Strategy:** Isolates licensable data asset (`.io`) from consumer brand (`.app`)

---

## 🧠 The AI Engine (Omni Edge)

### 11-Module Closed-Loop Pipeline

#### **Module 7: The Reflection Loop** (Critical Component)
Not a static report - an **agentic component** that:
- Computes ROI/CLV from user actions
- Programmatically suggests weekly JSON parameter patches
- Self-improves model filters and thresholds
- Runs weekly analysis and proposes config updates

#### Training Strategy
- **Primary Target:** CLV (closing line value) for stability/signal
- **Secondary Target:** Outcome (win/loss) for ROI
- **Hybrid Feature:** `sharp_weighted_consensus` fuses hard (odds) + soft (expert sentiment) data

#### Ingestion
- **Pre-match:** 30-60s polling
- **In-play:** 10-20s polling
- **SLO:** < 20s pre-match freshness, < 10s in-play

---

## 💬 The Community (The Data Moat)

### "Pay-to-Influence" Model

#### NLP Parser (LLM Service)
Parses user messages to extract:
- **Intent:** pick/news/injury/analysis/chat
- **Entities:** teams, players, markets
- **Sentiment:** -1 (bearish) to +1 (bullish)

#### Reputation Engine (ELO System)
- Assigns accuracy-weighted reputation scores to Pro/Elite members
- Calculates `sharp_weighted_consensus` for AI model
- Tracks win rate, ROI, CLV per user

#### Monetization Tiers
- **Pro ($49.99/mo):** Users *pay* to create raw data for NLP Parser
- **Elite ($99.99/mo):** Users pay to have sentiment *weighted 2x* in AI model
- **Free:** 0.5x weight (can view picks but minimal influence)

---

## 📊 Master Data Contracts

### Core Schemas

#### `ab_test_events`
A/B test performance tracking
```json
{
  "event": "view_landing | click_cta | start_trial | subscribe_paid | churn",
  "variant": "A | B | C | D | E",
  "ref": "AFF_12345",
  "session_id": "sess_abc123_B",
  "ts": "2025-11-10T12:00:00.000Z"
}
```

#### `subscribers`
Affiliate funnel tracking
```json
{
  "id": "usr_abc123",
  "email": "user@example.com",
  "ref": "AFF_12345",
  "status": "pending | trial | converted | churned",
  "variant": "A | B | C | D | E",
  "stripe_customer_id": "cus_xyz789",
  "plan": "pro | elite",
  "monthly_value": 49.99
}
```

#### `ai_picks`
The atomic unit of value
```json
{
  "pick_id": "pick_abc123",
  "event_id": "evt_nba_lakers_celtics",
  "market": "spreads",
  "side": "Los Angeles Lakers",
  "market_decimal": 1.91,
  "model_fair_decimal": 2.10,
  "edge_pct": 9.95,
  "stake_units": 2.5,
  "kelly_fraction": 0.25,
  "rationale": ["..."],
  "sharp_weighted_consensus": 0.7,
  "clv_pct": 2.3,
  "outcome": "win",
  "roi": 91.0
}
```

#### `user_actions`
Module 7 input
```json
{
  "user_id": "usr_abc123",
  "pick_id": "pick_abc123",
  "action": "TAILED | FADED | SAVE | SELF_SUBMIT",
  "user_stake": 100.0,
  "user_plan": "elite",
  "user_elo": 1847.3
}
```

#### `community_messages`
NLP/Reputation pipeline
```json
{
  "id": "msg_abc123",
  "channel_id": "nba-picks",
  "user_id": "usr_xyz789",
  "text": "Lakers -5.5 is FREE MONEY...",
  "user_plan": "elite",
  "user_elo": 1847.3,
  "parsed_intent": "pick",
  "parsed_sentiment": 0.85
}
```

#### `commissions`
Affiliate ledger
```json
{
  "commission_id": "comm_abc123",
  "affiliate_id": "AFF_12345",
  "user_id": "usr_xyz789",
  "basis": 49.99,
  "commission_rate": 0.20,
  "amount": 10.00,
  "status": "pending | approved | paid"
}
```

---

## 🚀 Performance SLOs

### Non-Negotiable Targets

| Metric | Target | Purpose |
|--------|--------|---------|
| **Odds Freshness** | < 20s pre-match<br>< 10s in-play | Speed = competitive advantage |
| **Pick Latency (P95)** | < 5s end-to-end | User experience |
| **Chat Fanout (P95)** | < 250ms | Real-time community feel |

---

## 🔧 Implementation Guide

### 1. Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### 2. Environment Configuration

Copy `.env.example` to `.env` and configure:
```bash
ODDS_API_KEY=your_key_here
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=beatvegas_db
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 3. Start MongoDB

```bash
# macOS (Homebrew)
brew services start mongodb-community

# Or use Docker
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### 4. Run Backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

The server will:
- ✓ Initialize database indexes
- ✓ Start A/B testing middleware
- ✓ Start background scheduler (odds polling + reflection loop)
- ✓ Mount all API routes

### 5. Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# Get system info
curl http://localhost:8000/
```

---

## 📡 API Endpoints

### A/B Testing
- `POST /api/ab-test/track` - Track user events
- `GET /api/ab-test/session` - Get variant assignment
- `GET /api/ab-test/analytics` - View funnel stats

### Affiliate System
- `POST /api/affiliate/register` - Register subscriber with ref
- `POST /api/affiliate/webhook/stripe` - Stripe conversion webhook
- `GET /api/affiliate/dashboard/{affiliate_id}` - Affiliate performance
- `POST /api/affiliate/create-account` - Create affiliate account

### Community
- `POST /api/community/message` - Post message (auto-parsed for Pro/Elite)
- `GET /api/community/messages` - Get messages
- `GET /api/community/picks` - Get structured picks
- `POST /api/community/settle-pick` - Settle pick and update ELO
- `GET /api/community/consensus/{event_id}` - Get sharp consensus
- `GET /api/community/leaderboard` - ELO leaderboard
- `GET /api/community/reputation/{user_id}` - User reputation stats

### Core AI
- `GET /api/core/fetch-odds` - Fetch odds from API
- `POST /api/core/normalize` - Normalize events
- `POST /api/core/predict` - Generate AI picks
- `GET /api/core/logs` - View audit logs

---

## 🎨 A/B Test Variants

### Variant A: Control (Expertise & Accuracy)
- Focus on sharp bettors
- Technical metrics and accuracy
- Three-tier pricing

### Variant B: Urgency
- Countdown timer (stateful)
- "Spots remaining" counter (dynamic)
- Scarcity messaging

### Variant C: Social Proof
- Live testimonial carousel (new API endpoint)
- Member activity feed (new API endpoint)
- Social proof stats

### Variant D: Simplified
- Mass market appeal
- No technical jargon
- Single "Pro Plan" (removes 3-tier)

### Variant E: Challenger
- "Beat the house" narrative
- Anti-establishment branding
- Underdog positioning

---

## 🔄 Background Jobs

### Odds Polling
- **NBA:** Every 60 seconds
- **NFL:** Every 60 seconds
- **MLB:** Every 60 seconds
- **SLO:** < 20s latency per poll

### Reflection Loop (Module 7)
- **Schedule:** Sundays at 2 AM
- **Actions:**
  1. Compute 7-day ROI/CLV performance
  2. Analyze user behavior (tails/fades)
  3. Generate parameter patches
  4. Preview or auto-apply changes

---

## 📈 Metrics Dashboard (Future)

Track these KPIs:
- **Conversion Funnel:** view → click → trial → paid (by variant)
- **Affiliate Performance:** referrals, conversions, commissions
- **AI Performance:** ROI, CLV, win rate, edge accuracy
- **Community Health:** messages/day, ELO distribution, pick volume
- **Technical SLOs:** odds freshness, pick latency, API uptime

---

## 🛡️ Data Security

### PII Protection
- Anonymize leaderboards (first 3 chars only)
- Encrypt affiliate payout details
- GDPR-compliant data retention

### API Security
- API key authentication for external calls
- JWT tokens for user sessions
- Rate limiting per tier (Free/Pro/Elite)

### Webhook Validation
- Verify Stripe webhook signatures
- Validate affiliate ref parameters
- Sanitize community message inputs

---

## 🚧 Roadmap

### Phase 1 (Current - MVP)
- ✅ Database schemas
- ✅ A/B testing infrastructure
- ✅ Affiliate viral loop
- ✅ Module 7 reflection loop
- ✅ Community NLP parser
- ✅ Reputation engine
- ✅ Hybrid AI model
- ✅ Background scheduler

### Phase 2 (Next 30 Days)
- [ ] Stripe webhook integration (production)
- [ ] Real-time odds polling (production)
- [ ] Community frontend (Discord-style UI)
- [ ] Affiliate dashboard UI
- [ ] Admin analytics dashboard

### Phase 3 (Next 60 Days)
- [ ] Machine learning model training (replace stub)
- [ ] CLV tracking system
- [ ] Advanced ELO calculations
- [ ] API rate limiting
- [ ] Performance monitoring (Datadog/New Relic)

### Phase 4 (Next 90 Days)
- [ ] Multi-sport expansion (NHL, Soccer, Tennis)
- [ ] Mobile apps (iOS/Android)
- [ ] B2B API tiers and licensing
- [ ] Advanced reflection loop (auto-apply patches)

---

## 📚 Documentation

- **API Flow:** `backend/docs/API_FLOW.md`
- **Module Docs:** `backend/docs/MODULE_DOCS.md`
- **Database Schemas:** `backend/db/schemas/`
- **Configuration:** `backend/core/model_config.json`

---

## 🤝 Contributing

This is a proprietary system targeting acquisition. Internal team only.

For questions or technical support, contact: engineering@beatvegas.io

---

## 📄 License

Proprietary - All Rights Reserved  
© 2025 BeatVegas, Inc.

---

**Built with:** FastAPI, MongoDB, APScheduler, React, TypeScript  
**Targeting:** $3.6B acquisition at 25-30x ARR multiple  
**Strategy:** Zero-ad spend growth via affiliate viral loop + community data moat
