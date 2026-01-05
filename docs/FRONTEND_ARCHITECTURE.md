# Frontend Architecture Documentation

**BeatVegas/SimSports Frontend**  
**Date:** January 5, 2026  
**Tech Stack:** React.js + Vite + TypeScript + TailwindCSS

---

## 📁 Directory Structure

```
/
├── components/        # React components
├── services/          # API clients and external services
├── utils/             # Utility functions and helpers
├── src/               # Source files (styles, assets)
├── public/            # Static assets
├── App.tsx            # Main app component
├── index.tsx          # React entry point
├── types.ts           # TypeScript type definitions
├── vite.config.ts     # Vite configuration
└── tailwind.config.js # TailwindCSS configuration
```

---

## 🎨 COMPONENTS MODULE (`components/`)

**Purpose:** React UI components

### Core Pages

#### Landing & Auth
- **`LandingPage.tsx`** - Marketing homepage, value proposition
- **`AuthPage.tsx`** - Login/signup flow
- **`OnboardingWizard.tsx`** - New user onboarding (3-step)
- **`LegalDisclaimer.tsx`** - Terms of service, disclaimers

#### Dashboard
- **`Dashboard.tsx`** - Main user dashboard, today's picks
- **`BettingCommandCenter.tsx`** - Command center layout
- **`DecisionCommandCenter.tsx`** - Decision-making interface

#### Game Analysis
- **`GameDetail.tsx`** - **CORE** - Single game detailed view
  - Market spread display with team labels
  - Model spread display (LOCKED LOGIC)
  - Sharp side display (prominent)
  - Spread context cards
  - AI Analyzer integration
  - Volatility indicators
  - Edge metrics
- **`EventCard.tsx`** - Game card in list view
- **`EventListItem.tsx`** - Compact game list item
- **`FirstHalfAnalysis.tsx`** - 1H-specific analysis

#### Simulation & Signals
- **`SimulationDisplay.tsx`** - Simulation results viewer
- **`SimulationBadge.tsx`** - Simulation tier badge (25K/50K/100K)
- **`SimulationPowerBadge.tsx`** - Simulation power indicator
- **`SimulationPowerWidget.tsx`** - Simulation count widget
- **`SignalCard.tsx`** - Signal display card (EDGE/LEAN/NO_PLAY)

#### Parlay System
- **`ParlayArchitect.tsx`** - **MAJOR** - Parlay generation UI
  - Risk profile selector (High Confidence, Balanced, High Volatility)
  - Leg count selector (3-6)
  - Sport filter
  - Props toggle
  - Truth Mode gate indicators
  - Fallback ladder messaging
  - Portfolio scoring display
- **`ParlayBuilder.tsx`** - Legacy parlay builder
- **`PropCard.tsx`** - Player prop display card

#### AI & Analysis
- **`AIAnalyzer.tsx`** - AI explanation interface
  - Locked system prompt
  - Explanation cards
  - Sharp side reasoning
  - Risk warnings

#### Community & War Room
- **`Community.tsx`** - Community hub
- **`CommunityEnhanced.tsx`** - Enhanced community features
- **`WarRoom.tsx`** - **MAJOR** - War Room interface
  - Game room threading
  - Market thread routing
  - Post templates (Market Callout, Receipt, Parlay Build)
  - BeatVegas context cards
  - Auto-archiving (TTL)
- **`WarRoomLeaderboard.tsx`** - War Room leaderboards
- **`WarRoomOverlays.tsx`** - Overlay UI components
- **`WarRoomTemplates.tsx`** - Post template components
- **`SharpsRoom.tsx`** - Wire Pro channel (verified sharps only)

#### Sharp Pass & Verification
- **`CLVTracker.tsx`** - CLV tracking dashboard
- **`PerformanceMetrics.tsx`** - User performance stats

#### Subscription & Payments
- **`SubscriptionPlans.tsx`** - Pricing page ($29.99/$49.99/$89.99)
- **`SubscriptionSettings.tsx`** - Subscription management
- **`UpgradeModal.tsx`** - Upgrade prompt modal
- **`UpgradePrompt.tsx`** - Inline upgrade CTA
- **`TierShowcase.tsx`** - Tier comparison table

#### User Profile
- **`Profile.tsx`** - User profile page
- **`Settings.tsx`** - User settings
- **`DecisionCapitalProfile.tsx`** - Decision capital tracking
- **`CreatorProfile.tsx`** - Creator mode profile

#### Navigation & Layout
- **`Sidebar.tsx`** - App sidebar navigation
- **`PageHeader.tsx`** - Page header component
- **`LoadingSpinner.tsx`** - Loading states

#### Trust & Social Proof
- **`TrustLoop.tsx`** - Social proof loop
- **`Leaderboard.tsx`** - Global leaderboard
- **`SocialMetaTags.tsx`** - SEO meta tags

#### Misc Components
- **`DailyBestCards.tsx`** - Daily best picks carousel
- **`ManualBetEntry.tsx`** - Manual bet tracking
- **`FeatureGate.tsx`** - Feature flag gating
- **`ConfidenceGauge.tsx`** - Confidence visualization
- **`EdgeIndicator.tsx`** - Edge badge component
- **`RiskAlert.tsx`** - Risk warning component
- **`NumericalAccuracyComponents.tsx`** - Float precision display
- **`TelegramConnection.tsx`** - Telegram account linking

#### Affiliate System
- **`Affiliates.tsx`** - Affiliate dashboard
- **`AffiliateWallet.tsx`** - Affiliate earnings

#### Admin
- **`admin/`** - Admin dashboard components

---

## 🔧 SERVICES MODULE (`services/`)

**Purpose:** API clients and external integrations

### `api.ts` - Main API Client

**Endpoints:**

#### Authentication
```typescript
login(email, password)
signup(email, password)
resetPassword(email)
```

#### Simulations
```typescript
runSimulation(gameId, simCount)
getSimulation(simId)
getUserSimulations(userId)
```

#### Odds
```typescript
getOdds(date, sport)
refreshOdds()
getRealtimeOdds()
```

#### Signals
```typescript
getSignals(filters)
getSignal(signalId)
lockSignal(signalId)
```

#### Parlay
```typescript
generateParlay(legCount, riskProfile, sports, includeProps)
calculateParlayOdds(legs)
```

#### AI Analyzer
```typescript
explainSignal(gameId, sport)
```

#### Community
```typescript
getCommunityPosts(channelSlug, page)
createPost(channelSlug, postData)
getChannels()
```

#### Sharp Pass
```typescript
purchaseSharpPass()
uploadCSV(file)
getVerificationStatus()
```

#### Subscriptions
```typescript
createCheckoutSession(tierId)
updateSubscription(tierId)
cancelSubscription()
```

### `tracking.ts` - Analytics Tracking

**Events:**
- Page views
- Button clicks
- Simulation runs
- Signal views
- Parlay generations
- Conversions

**Integrations:**
- Amplitude
- Mixpanel
- Google Analytics
- Facebook Pixel

---

## 🛠️ UTILS MODULE (`utils/`)

**Purpose:** Helper functions and business logic

### **CRITICAL LOCKED FILES:**

#### `modelSpreadLogic.ts` - **LOCKED**
**Purpose:** Model spread interpretation and sharp side selection

**Functions:**
```typescript
// Core logic (NON-NEGOTIABLE)
determineSharpSide(modelSpread, marketSpreadUnderdog): 'FAV' | 'DOG'

// Context calculator
calculateSpreadContext(
  homeTeam,
  awayTeam,
  marketSpreadHome,
  modelSpread
): SpreadContext

// Display formatter
formatSpreadForDisplay(context): {
  market: { label, value },
  model: { label, value },
  sharpSide: { label, value, highlight },
  edge: { label, value },
  reasoning: string
}

// Reasoning generator
getSharpSideReasoning(context): string

// Confidence calculator
getEdgeConfidenceLevel(edgePoints): {
  level: 'HIGH' | 'MEDIUM' | 'LOW',
  label: string,
  description: string
}

// Quick helper
getQuickSharpSide(homeTeam, awayTeam, marketSpreadHome, modelSpread)

// Validation
validateSpreadInputs(modelSpread, marketSpread): { isValid, error? }
```

**Rule:**
```typescript
if (modelSpread > marketSpread) → Sharp = FAVORITE
if (modelSpread < marketSpread) → Sharp = UNDERDOG
```

#### `edgeValidation.ts`
**Purpose:** Edge state validation

```typescript
validateEdge(edge, volatility, sport): {
  classification: 'EDGE' | 'LEAN' | 'NO_PLAY',
  passed_rules: number,
  total_rules: number,
  reasons: string[]
}
```

#### `lockedTierSystem.ts`
**Purpose:** Simulation tier enforcement

```typescript
getTierLimits(subscriptionTier): {
  maxSimulations: 25000 | 50000 | 100000,
  dailyLimit: number,
  telegramAccess: boolean
}
```

#### `simulationTiers.ts`
**Purpose:** Simulation tier badges and limits

```typescript
getSimulationTier(count): {
  tier: 'ANALYST' | 'QUANT' | 'ELITE',
  badge: string,
  color: string
}
```

#### `edgeStateClassification.ts`
**Purpose:** Edge state determination logic

```typescript
classifyEdgeState(
  edgePoints,
  volatility,
  sport
): 'EDGE' | 'LEAN' | 'NO_PLAY'
```

#### `confidenceTiers.ts`
**Purpose:** Confidence band mapping

```typescript
getConfidenceTier(winProb): {
  band: 'HIGH' | 'MEDIUM' | 'LOW',
  color: string,
  label: string
}
```

#### `dataValidation.ts`
**Purpose:** Input validation and sanitization

```typescript
validateGameData(game): { isValid, errors }
validateBetInput(bet): { isValid, errors }
sanitizeUserInput(input): string
```

#### `sportLabels.ts`
**Purpose:** Sport display labels and emojis

```typescript
getSportLabel(sport): string
getSportEmoji(sport): string
getSportColor(sport): string
```

---

## 📝 TYPE DEFINITIONS (`types.ts`)

**Purpose:** TypeScript interfaces and types

### Key Interfaces:

```typescript
interface Game {
  id: string;
  home_team: string;
  away_team: string;
  sport: Sport;
  commence_time: string;
  home_odds: number;
  away_odds: number;
  // ...
}

interface Simulation {
  sim_id: string;
  game_id: string;
  sport: Sport;
  sim_count: number;
  win_prob_home: number;
  win_prob_away: number;
  sharp_analysis: {
    spread?: {
      vegas_spread: number;
      model_spread: number;  // SIGNED (+underdog, -favorite)
      sharp_side: string;
      market_spread_display: string;  // MANDATORY
      model_spread_display: string;   // MANDATORY
      sharp_side_display: string;     // MANDATORY
      has_edge: boolean;
      edge_grade: 'S' | 'A' | 'B' | 'C';
    };
    total?: { ... };
    moneyline?: { ... };
  };
  // ...
}

interface Signal {
  signal_id: string;
  game_id: string;
  sport: Sport;
  market_key: 'SPREAD' | 'TOTAL' | 'ML';
  selection: string;
  edge_state: 'EDGE' | 'LEAN' | 'NO_PLAY';
  sharp_side: string;  // MANDATORY if edge_state != NO_PLAY
  locked_at: Date;
  // ...
}

interface SpreadContext {
  homeTeam: string;
  awayTeam: string;
  marketSpreadHome: number;
  marketSpreadAway: number;
  modelSpread: number;
  marketFavorite: string;
  marketUnderdog: string;
  sharpSide: 'FAV' | 'DOG';
  sharpSideTeam: string;
  sharpSideLine: number;
  marketSpreadDisplay: string;   // "Hawks +5.5"
  modelSpreadDisplay: string;    // "Hawks +12.3"
  sharpSideDisplay: string;      // "Knicks -5.5"
  edgePoints: number;
  edgeDirection: 'FAV' | 'DOG';
}

interface CommunityPost {
  _id: string;
  user_id: string;
  channel_slug: string;
  game_id?: string;
  post_type: 'MESSAGE' | 'MARKET_CALLOUT' | 'RECEIPT' | 'PARLAY_BUILD';
  content: string;
  // Market callout fields
  market_type?: 'SPREAD' | 'TOTAL' | 'ML' | 'PROP';
  line?: string;
  confidence?: 'LOW' | 'MED' | 'HIGH';
  beatvegas_context?: object;
  created_at: Date;
}

interface Parlay {
  parlay_id: string;
  risk_profile: 'HIGH_CONFIDENCE' | 'BALANCED' | 'HIGH_VOLATILITY';
  legs: Simulation[];
  expected_hit_rate: number;
  total_weight: number;
  combined_odds: number;
  potential_payout: number;
}
```

---

## 🎨 STYLING

### TailwindCSS Configuration (`tailwind.config.js`)

**Custom Colors:**
```javascript
colors: {
  'navy': '#0A1628',
  'charcoal': '#1A2332',
  'electric-blue': '#00D9FF',
  'neon-green': '#00FF88',
  'gold': '#FFD700',
  'blood-orange': '#FF4500',
  'purple-500': '#8B5CF6',
  'light-gray': '#E5E7EB'
}
```

**Font Families:**
- **Primary:** Inter (body text)
- **Display:** Teko (headings, numbers)

---

## ⚙️ VITE CONFIGURATION (`vite.config.ts`)

**Features:**
- React Fast Refresh
- TypeScript support
- TailwindCSS PostCSS processing
- Environment variable loading
- API proxy (dev mode)

**Dev Server:**
```bash
npm run dev
# Runs on http://localhost:5173
```

---

## 🌐 ROUTING

**React Router Routes:**
```
/ - Landing page
/auth - Login/signup
/dashboard - Main dashboard
/game/:id - Game detail
/parlay - Parlay Architect
/community - Community hub
/war-room - War Room
/sharp-pass - Sharp Pass purchase
/profile - User profile
/settings - Settings
/admin - Admin dashboard
```

---

## 🔒 CRITICAL UI RULES

### Model Spread Display (LOCKED)

**MANDATORY 3-Value Display:**
```tsx
<div>
  <div>Market Spread: {marketSpreadDisplay}</div>
  <div>Model Spread: {modelSpreadDisplay}</div>
  <div>🎯 Sharp Side: {sharpSideDisplay}</div>
</div>
```

**Example:**
```
Market Spread: Hawks +5.5
Model Spread:  Hawks +12.3
🎯 Sharp Side: Knicks -5.5
```

**NEVER show raw model spread without team label!**

### Edge State Badges

```tsx
{edgeState === 'EDGE' && <Badge color="purple">🔥 EDGE</Badge>}
{edgeState === 'LEAN' && <Badge color="gold">⚡ LEAN</Badge>}
{edgeState === 'NO_PLAY' && <Badge color="gray">NO PLAY</Badge>}
```

### Simulation Tier Badges

```tsx
<SimulationBadge count={100000} /> // "🔥 ELITE (100K)"
<SimulationBadge count={50000} />  // "⚡ QUANT (50K)"
<SimulationBadge count={25000} />  // "📊 ANALYST (25K)"
```

---

## 📊 STATE MANAGEMENT

**Approach:** React Context + Local State

**Contexts:**
- `AuthContext` - User authentication state
- `SubscriptionContext` - Subscription tier, limits
- `SimulationContext` - Active simulations cache
- `CommunityContext` - War Room state

---

## 🔌 INTEGRATIONS

### Analytics
- Amplitude (event tracking)
- Mixpanel (funnel analysis)
- Google Analytics (page views)

### Payments
- Stripe Checkout
- Stripe Customer Portal

### Social
- Telegram Web App SDK
- Facebook Pixel
- Twitter Cards

---

## 📱 RESPONSIVE DESIGN

**Breakpoints:**
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px

**Mobile-First Approach:**
All components designed for mobile, enhanced for desktop.

---

## 🚀 BUILD & DEPLOYMENT

**Development:**
```bash
npm run dev
```

**Production Build:**
```bash
npm run build
# Output: dist/
```

**Preview:**
```bash
npm run preview
```

---

## 📚 Related Documentation

- `BACKEND_ARCHITECTURE.md` - Backend structure
- `MASTER_DEV_SPECIFICATION.md` - Complete system spec
- `MODEL_SPREAD_LOCKED_DEFINITION.md` - Model spread logic
