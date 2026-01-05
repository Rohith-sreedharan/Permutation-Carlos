# Backend Architecture Documentation

**BeatVegas/SimSports Backend**  
**Date:** January 5, 2026  
**Tech Stack:** Python FastAPI + MongoDB + Pyrogram

---

## 📁 Directory Structure

```
backend/
├── core/              # Core business logic and algorithms
├── services/          # Service layer (business services)
├── routes/            # API endpoints (FastAPI routers)
├── integrations/      # Third-party integrations
├── db/                # Database models and connections
├── utils/             # Utility functions
├── middleware/        # Request/response middleware
├── config/            # Configuration files
├── tests/             # Test suites
├── scripts/           # Deployment and utility scripts
└── main.py            # FastAPI application entry point
```

---

## 🧠 CORE MODULE (`backend/core/`)

**Purpose:** Core business logic, algorithms, and sport-specific calibration

### Key Files:

#### Sport Calibration Engines
- **`mlb_calibration.py`** - MLB-specific probability compression (0.82 factor), pitcher scratch handling, weather adjustments
- **`ncaab_calibration.py`** - NCAAB edge thresholds (4.5+ pts), pace-driven downgrade logic
- **`ncaaf_calibration.py`** - NCAAF spread caps, triple option downgrade, QB uncertainty blocks
- **`nfl_calibration.py`** - NFL key number protection (3, 7, 10), QB injury sensitivity
- **`nhl_calibration.py`** - NHL totals focus (not spread), 0.60 compression factor, goalie status checks

#### Edge Evaluation
- **`sharp_side_selection.py`** - **LOCKED LOGIC**: Model spread sign interpretation, sharp side determination
- **`edge_evaluation_integration.py`** - Universal edge evaluator, integrates all sport calibrations
- **`universal_edge_evaluator.py`** - Edge state classification (EDGE/LEAN/NO_PLAY)
- **`sharp_analysis.py`** - Sharp action determination (LAY_POINTS, TAKE_POINTS, etc.)

#### Simulation & Monte Carlo
- **`monte_carlo_engine.py`** - 10K-10M simulation engine, variance calculation
- **`calibration_engine.py`** - Probability compression engine (sport-specific factors)
- **`permutation.py`** - Outcome permutation generator

#### Truth Mode & Gates
- **`truth_mode.py`** - Data Integrity + Model Validity + Reality Check Layer gates
- **`reality_check_layer.py`** - Post-simulation sanity checks, prevents unrealistic outputs
- **`truth_mode_parlay.py`** - Parlay-specific Truth Mode gates

#### Parlay System
- **`parlay_eligibility.py`** - Candidate filtering, risk profile constraints
- **`parlay_optimization_engine.py`** - Portfolio scoring, fallback ladder
- **`locked_tier_system.py`** - Simulation tier enforcement (25K/50K/100K)

#### Signal Lifecycle
- **`signal_lifecycle.py`** - Signal state machine (OPEN → LOCKED → SETTLED)
- **`pick_state_machine.py`** - Pick state transitions

#### Multi-Agent AI
- **`multi_agent_system.py`** - Orchestrates specialized agents (MLB Agent, NFL Agent, etc.)
- **`agent_orchestrator.py`** - Agent task routing
- **`agents/`** - Sport-specific AI agents

#### Safety & Validation
- **`safety_engine.py`** - Input validation, sanity checks
- **`numerical_accuracy.py`** - Float precision handling
- **`market_line_integrity.py`** - Detects stale/manipulated lines

#### Configuration
- **`sport_configs.py`** - Sport enums, volatility levels, edge states
- **`sport_calibration_config.py`** - Sport-specific thresholds and penalties
- **`engine_config.py`** - Simulation engine configuration

#### Model Spread (LOCKED)
- **`model_spread_logic.py`** - Model spread interpretation (+ = underdog, - = favorite)

---

## 🔧 SERVICES MODULE (`backend/services/`)

**Purpose:** Business services and external integrations

### Key Services:

#### AI Services
- **`ai_analyzer_service.py`** - OpenAI GPT-4 integration for signal explanation
- **`ai_analyzer_system_prompt.py`** - **LOCKED** system prompt (non-overridable sharp_side)
- **`ai_analyzer_llm.py`** - LLM client wrapper
- **`ai_analyzer_audit.py`** - Audit trail for AI responses
- **`ai_analyzer_context.py`** - Context builder for LLM input

#### Simulation & Edge
- **`simulation_engine.py`** - Main simulation orchestrator
- **`edge_analysis.py`** - Edge calculation and classification
- **`autonomous_edge_engine.py`** - Automated edge detection scheduler
- **`autonomous_edge_scheduler.py`** - Cron-based edge scanning

#### Sport-Specific Evaluators
- **`mlb_edge_evaluator.py`** - MLB edge logic
- **`ncaab_edge_evaluator.py`** - NCAAB edge logic
- **`ncaaf_edge_evaluator.py`** - NCAAF edge logic
- **`nfl_edge_evaluator.py`** - NFL edge logic
- **`nhl_edge_evaluator.py`** - NHL edge logic

#### Parlay Services
- **`parlay_architect.py`** - Parlay generation with Truth Mode
- **`parlay_calculator.py`** - Parlay odds and payout calculation
- **`parlay_architect_adapter.py`** - Adapter for legacy parlay builder

#### Signal Management
- **`signal_manager.py`** - Signal CRUD operations
- **`signal_generation_service.py`** - Signal creation pipeline
- **`signal_locking_service.py`** - Automated signal locking
- **`signal_posting_service.py`** - Signal distribution (Telegram, UI)

#### Sharp Pass & Verification
- **`sharp_pass_verifier.py`** - CLV calculation, CSV upload processing
- **`clv_tracker.py`** - Closing Line Value tracking
- **`verification_service.py`** - User verification workflow

#### Community & War Room
- **`community_manager.py`** - Community post management
- **`war_room_service.py`** - War Room threading, game room routing
- **`ugc_service.py`** - User-generated content moderation
- **`moderation_service.py`** - Post flagging, rate limiting

#### Telegram Integration
- **`telegram_bot_service.py`** - Pyrogram bot manager
- **`community_bot.py`** - Community engagement automation

#### Monitoring & Analytics
- **`sanity_check_service.py`** - Daily health checks (edge count alerts)
- **`monitoring.py`** - System health monitoring
- **`analytics_service.py`** - User behavior tracking
- **`pixel_tracking.py`** - Event tracking (Amplitude/Mixpanel)

#### User Services
- **`entitlements_service.py`** - Subscription tier enforcement
- **`user_identity.py`** - User authentication
- **`reputation_engine.py`** - User reputation scoring

#### Odds & Market Data
- **`odds_refresh_service.py`** - Real-time odds polling
- **`market_state_registry_service.py`** - Market state tracking

#### Post-Game
- **`post_game_grader.py`** - Result grading (W/L/P)
- **`result_grading.py`** - Bet outcome calculation
- **`post_game_recap.py`** - Automated recap generation

#### Utilities
- **`logger.py`** - Structured logging
- **`slack_notifier.py`** - Slack alert integration
- **`scheduler.py`** - Background job scheduler
- **`notification_service.py`** - User notification system

---

## 🌐 ROUTES MODULE (`backend/routes/`)

**Purpose:** FastAPI endpoints (API layer)

### Key Route Groups:

#### Authentication & Users
- **`auth_routes.py`** - Login, signup, password reset
- **`user_routes.py`** - User profile, preferences
- **`account_routes.py`** - Account management
- **`whoami_routes.py`** - Current user info

#### Simulations
- **`simulation_routes.py`** - Run simulations, get results
- **`simulation.py`** - Legacy simulation endpoints

#### Sport-Specific
- **`mlb_routes.py`** - MLB games and odds
- **`nfl_routes.py`** - NFL games and odds
- **`ncaab_routes.py`** - NCAAB games and odds
- **`ncaaf_routes.py`** - NCAAF games and odds
- **`nhl_routes.py`** - NHL games and odds

#### Odds & Markets
- **`odds_routes.py`** - Real-time odds, line movements
- **`market_state_routes.py`** - Market state API

#### Signals
- **`signal_routes.py`** - Signal CRUD, history

#### Edge & Analysis
- **`edge_analysis_routes.py`** - Edge calculation endpoints
- **`autonomous_edge_routes.py`** - Autonomous edge scanning

#### Parlay
- **`parlay_routes.py`** - Parlay generation, optimization
- **`architect_routes.py`** - Parlay Architect API

#### AI Analyzer
- **`analyzer.py`** - AI explanation endpoint

#### Community & War Room
- **`community_routes.py`** - Community posts, channels
- **`war_room_routes.py`** - War Room API
- **`ugc_routes.py`** - User content submission

#### Sharp Pass
- **`sharp_pass.py`** - Sharp Pass purchase, CSV upload
- **`clv_routes.py`** - CLV tracking, verification status

#### Payments & Subscriptions
- **`payment_routes.py`** - Stripe checkout
- **`subscription_routes.py`** - Subscription management
- **`stripe_webhook_routes.py`** - Stripe webhook handler

#### Telegram
- **`telegram_routes.py`** - Telegram linking, bot interaction

#### Admin
- **`admin_routes.py`** - Admin dashboard, controls
- **`debug_routes.py`** - Debug utilities

#### Analytics
- **`analytics_routes.py`** - User analytics, tracking
- **`tracking_routes.py`** - Event tracking

#### Misc
- **`daily_cards_routes.py`** - Daily best picks
- **`recap_routes.py`** - Post-game recaps
- **`performance_routes.py`** - User performance stats
- **`trust_routes.py`** - Trust metrics
- **`tier_routes.py`** - Tier system info

---

## 🔌 INTEGRATIONS MODULE (`backend/integrations/`)

**Purpose:** Third-party service integrations

- **Telegram:** Pyrogram client, 7-bot automation stack
- **Stripe:** Payment processing, webhooks
- **OpenAI:** GPT-4 for AI Analyzer
- **Odds Providers:** The Odds API, BetOnline scraper
- **Email:** SendGrid for transactional emails

---

## 💾 DATABASE MODULE (`backend/db/`)

**Purpose:** MongoDB models and database operations

### Collections:
- **users** - User accounts, subscriptions
- **simulations** - Simulation runs (immutable)
- **signals** - Locked signals (immutable)
- **community_posts** - War Room posts
- **community_channels** - Channel definitions
- **telegram_posts** - Telegram delivery log
- **sharp_pass_applications** - Sharp Pass verification queue
- **bet_history** - User bet tracking for CLV

---

## 🛠️ UTILITIES MODULE (`backend/utils/`)

**Purpose:** Helper functions and formatters

- **`spread_formatter.py`** - API response formatter (LOCKED: adds display strings)
- Date/time utilities
- String formatting
- Data validation helpers

---

## 🧪 TESTS MODULE (`backend/tests/`)

**Purpose:** Test suites and validation

- **`test_locked_spread_logic.py`** - Model spread logic validation
- **`validate_deployment.py`** - Pre-deployment checks
- Unit tests for core modules
- Integration tests for API endpoints

---

## 📝 CONFIGURATION

### Environment Variables (`.env`)
```
MONGODB_URI=mongodb://...
STRIPE_SECRET_KEY=sk_...
TELEGRAM_API_ID=...
TELEGRAM_API_HASH=...
OPENAI_API_KEY=sk-...
THE_ODDS_API_KEY=...
```

### Config Files
- **`config.py`** - Main configuration
- **`legacy_config.py`** - Legacy settings (deprecated)
- **`requirements.txt`** - Python dependencies

---

## 🚀 API Entry Point

**File:** `backend/main.py`

FastAPI application with:
- CORS middleware
- Request logging
- Error handling
- Route registration
- WebSocket support

**Start command:**
```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

---

## 🔒 CRITICAL LOCKED MODULES

**DO NOT MODIFY WITHOUT APPROVAL:**

1. **`sharp_side_selection.py`** - Model spread logic
2. **`ai_analyzer_system_prompt.py`** - AI system prompt
3. **`truth_mode.py`** - Gate definitions
4. **`locked_tier_system.py`** - Simulation tier enforcement
5. **`spread_formatter.py`** - API response structure

---

## 📊 Data Flow

```
User Request
    ↓
API Route (routes/)
    ↓
Service Layer (services/)
    ↓
Core Logic (core/)
    ↓
Database (db/)
    ↓
Response Formatter (utils/)
    ↓
User Response
```

---

## 🎯 Key Architectural Principles

1. **Separation of Concerns:** Routes → Services → Core → DB
2. **Sport-Specific Calibration:** Each sport has its own evaluator
3. **Immutable Signals:** Once locked, signals never change
4. **Truth Mode Gates:** All outputs pass through 3-gate validation
5. **MongoDB-First:** All data in MongoDB (NOT PostgreSQL)
6. **Pyrogram for Telegram:** NOT python-telegram-bot
7. **Sharp Side Mandatory:** EDGE state requires sharp_side computed

---

## 📚 Related Documentation

- `MASTER_DEV_SPECIFICATION.md` - Complete system specification
- `MODEL_SPREAD_LOCKED_DEFINITION.md` - Model spread logic
- `IMPLEMENTATION_SUMMARY.md` - Recent changes
