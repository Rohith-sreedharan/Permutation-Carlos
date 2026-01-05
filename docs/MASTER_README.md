# 🎯 BeatVegas/SimSports Master Documentation

**Complete System Specification & Developer Handoff**  
**Version:** 2.0  
**Last Updated:** January 5, 2026  
**Status:** Production Ready ✅

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Tech Stack](#tech-stack)
3. [Architecture](#architecture)
4. [Backend Modules](#backend-modules)
5. [Frontend Modules](#frontend-modules)
6. [Critical Rules & Locked Logic](#critical-rules--locked-logic)
7. [Database Schema](#database-schema)
8. [API Endpoints](#api-endpoints)
9. [Deployment Guide](#deployment-guide)
10. [Testing](#testing)
11. [Documentation Index](#documentation-index)

---

## 🎯 System Overview

**BeatVegas/SimSports** is an AI-powered sports betting decision platform that runs Monte Carlo simulations to identify sharp betting opportunities.

### Core Value Proposition

**For Users:**
- Run 25K/50K/100K Monte Carlo simulations per game
- Get AI-analyzed sharp sides with model spreads
- Access Truth Mode gates (CLV thresholds, volatility filters)
- Build optimized parlays with risk profiles
- Join War Room for real-time market discussion
- Track performance with Decision Capital

**For Sharps:**
- Verify status via Sharp Pass (CLV audit)
- Access Wire Pro channel (verified sharps only)
- Upload historical betting CSV
- Get AI-powered CLV analysis

### User Tiers

| Tier | Price | Simulations | Telegram | Sharp Pass |
|------|-------|-------------|----------|------------|
| **ANALYST** | $29.99/mo | 25,000 | No | No |
| **QUANT** | $49.99/mo | 50,000 | Yes | No |
| **ELITE** | $89.99/mo | 100,000 | Yes | Yes |

---

## 🛠️ Tech Stack

### Backend
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Database:** MongoDB
- **AI:** OpenAI GPT-4
- **Telegram:** Pyrogram
- **Testing:** pytest
- **Environment:** Python .venv

### Frontend
- **Framework:** React.js 18+
- **Build Tool:** Vite
- **Language:** TypeScript
- **Styling:** TailwindCSS
- **Routing:** React Router
- **State:** React Context

### Infrastructure
- **Hosting:** TBD
- **Payments:** Stripe
- **Analytics:** Amplitude, Mixpanel, Google Analytics

---

## 🏗️ Architecture

### High-Level Flow

```
User → Frontend (React) → API (FastAPI) → MongoDB
                        ↓
                   OpenAI GPT-4 (AI Analyzer)
                        ↓
                   Telegram Bot (Pyrogram)
```

### Data Flow

1. **User requests simulation** → Frontend calls `/api/simulations/run`
2. **Backend receives request** → Route validates subscription tier
3. **Core engine runs** → `monte_carlo_simulation.py` executes 25K-100K iterations
4. **Sharp side calculated** → `sharp_side_selection.py` applies LOCKED LOGIC
5. **AI analyzes** → `ai_analyzer.py` calls GPT-4 with locked prompt
6. **Response formatted** → `spread_formatter.py` adds display strings
7. **Frontend displays** → `GameDetail.tsx` shows 3-card spread view
8. **Telegram notified** → `telegram_bot.py` posts signal to channels

### Directory Structure

```
/
├── backend/                 # Python FastAPI backend
│   ├── core/               # Business logic (60+ files)
│   ├── services/           # Service layer (70+ files)
│   ├── routes/             # API endpoints (60+ files)
│   ├── integrations/       # External APIs
│   ├── db/                 # MongoDB models
│   ├── utils/              # Helpers
│   ├── tests/              # Test suites
│   ├── config.py           # Configuration
│   └── main.py             # FastAPI app
├── components/             # React components (40+ files)
├── services/               # API clients
├── utils/                  # Frontend helpers
├── docs/                   # Documentation
└── [config files]
```

---

## 🔧 Backend Modules

**See:** [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md) for complete details.

### `backend/core/` (60+ files)

**Purpose:** Core business logic

#### Sport Calibration Engines
- `calibration_mlb.py` - MLB-specific thresholds
- `calibration_ncaab.py` - NCAAB-specific thresholds
- `calibration_ncaaf.py` - NCAAF-specific thresholds
- `calibration_nfl.py` - NFL-specific thresholds
- `calibration_nhl.py` - NHL-specific thresholds
- `calibration_nba.py` - NBA-specific thresholds (legacy)

#### Sharp Side Selection ⚠️ **LOCKED**
- `sharp_side_selection.py` - Universal sharp side logic
  - **Rule:** If `|model_spread| > market_spread_underdog` → Sharp = FAVORITE
  - **Input:** Signed model spread (+ underdog, - favorite)
  - **Output:** Display strings with team labels

#### Monte Carlo Simulation
- `monte_carlo_simulation.py` - Core simulation engine
  - Runs 25K/50K/100K iterations
  - Outputs win probabilities, confidence intervals
  - Sport-aware variance modeling

#### Truth Mode Gates
- `truth_mode_clv_gate.py` - CLV threshold enforcement
- `truth_mode_volatility_gate.py` - Volatility filter
- `truth_mode_parlay_filter.py` - Parlay Truth Mode

#### Parlay System
- `parlay_generation.py` - Risk profile-based parlay builder
- `parlay_portfolio_scoring.py` - Portfolio optimization
- `parlay_truth_mode_filter.py` - Truth Mode leg validation
- `parlay_fallback_ladder.py` - Cascading fallback logic

#### Multi-Agent AI System
- `agent_coordinator.py` - Agent orchestration
- `sharp_sentiment_agent.py` - Sharp sentiment analysis
- `ai_analyzer.py` - **LOCKED** GPT-4 integration

### `backend/services/` (70+ files)

**Purpose:** Service layer

#### AI Services
- `ai_service.py` - GPT-4 client wrapper
- `locked_system_prompt.py` - **LOCKED** AI system prompt

#### Edge Evaluators
- `edge_evaluator_spread.py` - Spread edge calculation
- `edge_evaluator_total.py` - Total edge calculation
- `edge_evaluator_ml.py` - Moneyline edge calculation
- `edge_state_classifier.py` - EDGE/LEAN/NO_PLAY determination

#### Simulation Services
- `simulation_service.py` - Simulation orchestration
- `simulation_cache.py` - Redis cache layer
- `simulation_tier_enforcement.py` - Tier limit checks

#### Signal Management
- `signal_generator.py` - Signal creation
- `signal_enrichment.py` - Add context to signals
- `signal_validation.py` - Validate signal quality

#### Sharp Pass
- `sharp_pass_verifier.py` - CLV CSV audit
- `clv_calculator.py` - CLV computation

#### Community Services
- `community_post_service.py` - Post CRUD
- `war_room_routing.py` - Thread routing logic
- `post_template_service.py` - Template rendering

#### Telegram Integration
- `telegram_service.py` - Telegram API wrapper
- `telegram_channel_manager.py` - Channel management

### `backend/routes/` (60+ endpoints)

**Purpose:** API endpoints

#### Key Endpoints
- `/api/auth/login` - User authentication
- `/api/simulations/run` - Run Monte Carlo simulation
- `/api/odds/refresh` - Refresh odds from APIs
- `/api/signals/list` - Get signals with filters
- `/api/parlay/generate` - Generate parlay
- `/api/community/posts` - War Room posts
- `/api/sharp-pass/purchase` - Buy Sharp Pass
- `/api/subscriptions/checkout` - Stripe checkout

---

## 🎨 Frontend Modules

**See:** [FRONTEND_ARCHITECTURE.md](./FRONTEND_ARCHITECTURE.md) for complete details.

### `components/` (40+ files)

**Purpose:** React UI components

#### Core Pages
- `LandingPage.tsx` - Marketing homepage
- `Dashboard.tsx` - Main dashboard
- `GameDetail.tsx` - **CORE** - Game analysis view
- `ParlayArchitect.tsx` - **MAJOR** - Parlay builder
- `WarRoom.tsx` - **MAJOR** - Community hub

#### Game Analysis
- `GameDetail.tsx` - Single game detail
  - Market spread display
  - Model spread display (LOCKED LOGIC)
  - Sharp side display (prominent)
  - AI Analyzer integration
- `SimulationDisplay.tsx` - Simulation results
- `SignalCard.tsx` - Signal display

#### Community
- `WarRoom.tsx` - War Room interface
- `Community.tsx` - Community hub
- `WarRoomTemplates.tsx` - Post templates

### `services/api.ts`

**Purpose:** API client

**Endpoints:** Login, Simulations, Odds, Signals, Parlay, Community, Sharp Pass, Subscriptions

### `utils/` (Helper Functions)

**CRITICAL LOCKED FILES:**

#### `modelSpreadLogic.ts` ⚠️ **LOCKED**
- `determineSharpSide()` - Sharp side selection
- `calculateSpreadContext()` - Spread context builder
- `formatSpreadForDisplay()` - Display formatter

**Rule:**
```typescript
if (modelSpread > marketSpread) → Sharp = FAVORITE
if (modelSpread < marketSpread) → Sharp = UNDERDOG
```

#### Other Utils
- `edgeValidation.ts` - Edge state validation
- `lockedTierSystem.ts` - Tier enforcement
- `simulationTiers.ts` - Simulation badges
- `confidenceTiers.ts` - Confidence bands
- `dataValidation.ts` - Input validation

---

## 🔒 Critical Rules & Locked Logic

### 1. Model Spread Logic ⚠️ **NON-NEGOTIABLE**

**Definition:**
- Model spread is a **SIGNED** value relative to **TEAM DIRECTION**
- Positive (+) model spread → Underdog
- Negative (−) model spread → Favorite

**Sharp Side Rule:**
```python
model_spread_abs = abs(model_spread)

if model_spread_abs > market_spread_underdog:
    sharp_side = "FAVORITE"
else:
    sharp_side = "UNDERDOG"
```

**Example:**

| Home | Away | Market | Model | Sharp |
|------|------|--------|-------|-------|
| Hawks | Knicks | Hawks +5.5 | Hawks +12.3 | Knicks -5.5 (FAV) |
| Lakers | Celtics | Lakers -3.0 | Lakers -8.2 | Lakers -3.0 (FAV) |

**Display Requirements:**
- **MANDATORY:** All API responses MUST include `market_spread_display`, `model_spread_display`, `sharp_side_display`
- **Format:** `"Team +/-Line"` (e.g., `"Hawks +5.5"`)
- **UI:** Show 3 separate cards: Market Spread, Model Spread, Sharp Side

**Files:**
- Backend: `backend/core/sharp_side_selection.py`
- Backend: `backend/utils/spread_formatter.py`
- Frontend: `utils/modelSpreadLogic.ts`
- Frontend: `components/GameDetail.tsx`

### 2. Edge State Classification

**States:**
- **EDGE** 🔥 - High conviction, passes all Truth Mode gates
- **LEAN** ⚡ - Moderate conviction, edge exists but below thresholds
- **NO_PLAY** - No actionable edge

**Rules:**
```python
if edge_points >= sport_thresholds['edge_min'] and volatility <= sport_thresholds['volatility_max']:
    state = 'EDGE'
elif edge_points >= sport_thresholds['lean_min']:
    state = 'LEAN'
else:
    state = 'NO_PLAY'
```

**Sport-Specific Thresholds:**

| Sport | Edge Min | Lean Min | Volatility Max |
|-------|----------|----------|----------------|
| NFL | 5.0 | 3.0 | 2.5 |
| NCAAF | 6.0 | 4.0 | 3.0 |
| NBA | 4.5 | 2.5 | 2.8 |
| NCAAB | 5.5 | 3.5 | 3.2 |
| MLB | 0.15 (ML) | 0.10 | 0.20 |
| NHL | 0.12 (ML) | 0.08 | 0.18 |

### 3. Simulation Tier Limits ⚠️ **LOCKED**

| Tier | Max Sim | Daily Limit | Telegram | Sharp Pass |
|------|---------|-------------|----------|------------|
| ANALYST | 25,000 | 10 games/day | No | No |
| QUANT | 50,000 | 25 games/day | Yes | No |
| ELITE | 100,000 | Unlimited | Yes | Yes |

### 4. AI Analyzer System Prompt ⚠️ **LOCKED**

**File:** `backend/services/locked_system_prompt.py`

**Cannot be modified.** Prompts GPT-4 to:
- Explain sharp side reasoning
- Highlight volatility risks
- Reference sport-specific factors
- Never recommend betting actions

### 5. Truth Mode Gates

**CLV Gate:**
- Sharp Pass holders only
- Requires documented CLV > 2% over 100+ bets

**Volatility Gate:**
- Filters high-variance games
- Sport-specific thresholds

**Parlay Truth Mode:**
- All legs must pass Truth Mode gates
- Fallback ladder if insufficient legs

### 6. War Room Routing

**Channels:**
- `#general` - All posts not game/market-specific
- `#game-threads` - Game-specific discussion (auto-routes by game_id)
- `#market-threads` - Market-specific threads (auto-routes by market_type)
- `#sharps-only` - Wire Pro (Sharp Pass verified only)

**Post Types:**
- `MESSAGE` - Standard post
- `MARKET_CALLOUT` - Market position announcement
- `RECEIPT` - Bet confirmation
- `PARLAY_BUILD` - Parlay share

**Auto-Archiving:**
- Game threads archived 24h after game end
- Market threads archived 48h after creation

---

## 💾 Database Schema

**Database:** MongoDB

### Collections

#### `users`
```javascript
{
  _id: ObjectId,
  email: string,
  password_hash: string,
  subscription_tier: 'ANALYST' | 'QUANT' | 'ELITE',
  subscription_status: 'active' | 'canceled' | 'past_due',
  stripe_customer_id: string,
  sharp_pass_status: 'none' | 'pending' | 'verified' | 'rejected',
  telegram_user_id: number,
  created_at: Date
}
```

#### `simulations`
```javascript
{
  _id: ObjectId,
  sim_id: string,
  user_id: ObjectId,
  game_id: string,
  sport: string,
  sim_count: 25000 | 50000 | 100000,
  win_prob_home: number,
  win_prob_away: number,
  sharp_analysis: {
    spread: {
      vegas_spread: number,
      model_spread: number,  // SIGNED
      sharp_side: string,
      market_spread_display: string,  // MANDATORY
      model_spread_display: string,   // MANDATORY
      sharp_side_display: string,     // MANDATORY
      has_edge: boolean,
      edge_grade: string
    },
    total: { ... },
    moneyline: { ... }
  },
  created_at: Date
}
```

#### `signals`
```javascript
{
  _id: ObjectId,
  signal_id: string,
  game_id: string,
  sport: string,
  market_key: 'SPREAD' | 'TOTAL' | 'ML',
  selection: string,
  edge_state: 'EDGE' | 'LEAN' | 'NO_PLAY',
  sharp_side: string,  // MANDATORY if edge_state != NO_PLAY
  locked_at: Date,
  created_at: Date
}
```

#### `community_posts`
```javascript
{
  _id: ObjectId,
  user_id: ObjectId,
  channel_slug: string,
  game_id: string,  // Optional, for game threads
  post_type: string,
  content: string,
  market_type: string,  // For market callouts
  line: string,
  confidence: string,
  beatvegas_context: object,
  created_at: Date
}
```

#### `sharp_pass_applications`
```javascript
{
  _id: ObjectId,
  user_id: ObjectId,
  csv_file_url: string,
  total_bets: number,
  clv_percentage: number,
  status: 'pending' | 'approved' | 'rejected',
  reviewed_at: Date,
  created_at: Date
}
```

#### `telegram_posts`
```javascript
{
  _id: ObjectId,
  signal_id: ObjectId,
  channel_id: string,
  message_id: number,
  posted_at: Date
}
```

---

## 🔌 API Endpoints

**See:** [BACKEND_ARCHITECTURE.md](./BACKEND_ARCHITECTURE.md) for complete endpoint list.

### Authentication
- `POST /api/auth/login`
- `POST /api/auth/signup`
- `POST /api/auth/reset-password`

### Simulations
- `POST /api/simulations/run`
- `GET /api/simulations/{sim_id}`
- `GET /api/simulations/user/{user_id}`

### Odds
- `GET /api/odds?date=2026-01-05&sport=NFL`
- `POST /api/odds/refresh`

### Signals
- `GET /api/signals?sport=NFL&edge_state=EDGE`
- `GET /api/signals/{signal_id}`
- `POST /api/signals/{signal_id}/lock`

### Parlay
- `POST /api/parlay/generate`
- `POST /api/parlay/calculate-odds`

### Community
- `GET /api/community/posts?channel=general&page=1`
- `POST /api/community/posts`
- `GET /api/community/channels`

### Sharp Pass
- `POST /api/sharp-pass/purchase`
- `POST /api/sharp-pass/upload-csv`
- `GET /api/sharp-pass/status`

### Subscriptions
- `POST /api/subscriptions/checkout`
- `PUT /api/subscriptions/update`
- `DELETE /api/subscriptions/cancel`

---

## 🚀 Deployment Guide

### Backend Deployment

**Prerequisites:**
- Python 3.11+
- MongoDB instance
- OpenAI API key
- Telegram Bot Token
- Stripe API keys

**Setup:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Environment Variables:**
```bash
# .env
MONGODB_URI=mongodb://localhost:27017
OPENAI_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=...
STRIPE_SECRET_KEY=sk_test_...
ENVIRONMENT=production
```

**Run:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Frontend Deployment

**Prerequisites:**
- Node.js 18+
- npm

**Setup:**
```bash
npm install
```

**Environment Variables:**
```bash
# .env
VITE_API_URL=https://api.beatvegas.com
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_...
VITE_AMPLITUDE_KEY=...
```

**Build:**
```bash
npm run build
# Output: dist/
```

**Run:**
```bash
npm run preview
# Or deploy dist/ to hosting provider
```

---

## ✅ Testing

### Backend Tests

**Location:** `backend/tests/`

**Test Files:**
- `test_locked_spread_logic.py` - Model spread logic (5 tests)
- `validate_deployment.py` - Pre-deployment checks (5 checks)

**Run Tests:**
```bash
cd backend
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/test_locked_spread_logic.py -v
python tests/validate_deployment.py
```

**Status:** ✅ ALL TESTS PASSING (10/10)

### Frontend Tests

**Not yet implemented** - Recommend adding:
- Jest for unit tests
- React Testing Library for component tests
- Cypress for E2E tests

---

## 📚 Documentation Index

### Core Specs
1. **MASTER_DEV_SPECIFICATION.md** - Complete system specification (10,000+ words)
   - Product overview
   - Feature requirements
   - AI Analyzer specs
   - War Room specs
   - Parlay Architect specs
   - Model spread logic with examples
   - Truth Mode gates
   - Subscription tiers

2. **MODEL_SPREAD_LOCKED_DEFINITION.md** - Model spread logic deep dive
   - FINAL CLARIFICATION
   - Sign convention
   - Sharp side algorithm
   - Examples
   - Edge cases
   - Validation rules

3. **IMPLEMENTATION_SUMMARY.md** - Change summary
   - Files modified
   - Files created
   - Testing results

4. **MODEL_SPREAD_QUICK_REFERENCE.txt** - Quick developer reference
   - One-page summary
   - Code snippets
   - Common pitfalls

### Architecture Docs
5. **BACKEND_ARCHITECTURE.md** (this file) - Backend structure
   - Directory overview
   - Module breakdown (60+ core, 70+ services, 60+ routes)
   - Data flow
   - Critical files

6. **FRONTEND_ARCHITECTURE.md** - Frontend structure
   - Component inventory (40+ components)
   - Utils breakdown
   - API client
   - Routing
   - UI rules

7. **MASTER_README.md** (this file) - Master documentation
   - System overview
   - Tech stack
   - All modules summary
   - Critical rules
   - Database schema
   - API endpoints
   - Deployment guide

### Misc Docs
8. **ENV_VARIABLES_GUIDE.md** - Environment variable setup
9. **ODDS_POLLING_FIX.md** - Odds polling implementation
10. **PRODUCTION_CONFIG_UPDATE.md** - Production config changes
11. **SYSTEM_FIXES_2025_12_29.md** - Recent system fixes
12. **PIXEL_INTEGRATION_TEMPLATE.html** - Facebook Pixel template
13. **STALE_ODDS_GRACEFUL_DEGRADATION.md** - Stale odds handling

---

## 🎯 Quick Start for Developers

### 1. Clone & Setup
```bash
git clone <repo>
cd Permutation-Carlos

# Backend
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Configure environment

# Frontend
cd ..
npm install
cp .env.example .env  # Configure environment
```

### 2. Run Tests
```bash
# Backend
cd backend
source .venv/bin/activate
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/ -v
python tests/validate_deployment.py

# Frontend
npm run test  # (if tests exist)
```

### 3. Start Dev Servers
```bash
# Backend (Terminal 1)
cd backend
source .venv/bin/activate
uvicorn main:app --reload

# Frontend (Terminal 2)
npm run dev
```

### 4. Access App
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

---

## ⚠️ Critical Reminders

### LOCKED MODULES (DO NOT MODIFY)
1. `backend/core/sharp_side_selection.py` - Sharp side logic
2. `backend/utils/spread_formatter.py` - API formatter
3. `backend/services/locked_system_prompt.py` - AI prompt
4. `utils/modelSpreadLogic.ts` - Frontend spread logic
5. Sport calibration files (all 6 sports)

### MANDATORY VALIDATIONS
- All simulation responses MUST include display strings
- All edge states must have sharp_side if not NO_PLAY
- All Telegram posts must be non-blocking
- All subscription checks must happen before simulation runs

### NEVER DO
- Modify model spread sign convention
- Skip display string generation
- Change sharp side algorithm
- Bypass Truth Mode gates
- Modify AI system prompt

---

## 🆘 Support & Contact

**Documentation:** See docs/ folder  
**Issues:** [GitHub Issues]  
**Questions:** [Discord/Slack]  

**Developer Handoff Checklist:**
- ✅ Read MASTER_DEV_SPECIFICATION.md
- ✅ Read BACKEND_ARCHITECTURE.md
- ✅ Read FRONTEND_ARCHITECTURE.md
- ✅ Read MODEL_SPREAD_LOCKED_DEFINITION.md
- ✅ Run all tests (10/10 passing)
- ✅ Review locked modules
- ✅ Set up environment variables
- ✅ Start dev servers
- ✅ Test model spread display in GameDetail.tsx

---

**Last Updated:** January 5, 2026  
**Version:** 2.0  
**Status:** Production Ready ✅  
**All Tests Passing:** 10/10 ✅
