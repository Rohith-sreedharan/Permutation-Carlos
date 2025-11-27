# BeatVegas Analytics Engine v1.0

Enterprise-grade sports analytics platform with real-time Monte Carlo simulations, multi-agent AI system, and compliant decision intelligence features.

## 🏗️ Architecture

### Backend (Python/FastAPI)
- **Monte Carlo Engine**: 50,000+ iteration simulations for NBA, NFL, MLB, NHL
- **7-Agent Multi-Agent System**: Specialized AI agents for parlay analysis, risk management, market analysis, and behavioral modeling
- **Event Bus**: Redis-powered pub/sub for real-time agent communication
- **WebSocket Support**: Live updates for game events and risk alerts

### Frontend (React/TypeScript/Vite)
- **Dashboard**: Real-time event cards with simulation results
- **Decision Capital Profile**: Compliance-focused risk management (replaces gambling terminology)
- **Creator Intelligence Marketplace**: Verified analyst content platform
- **Stripe Integration**: Subscription billing (Starter/Pro/Enterprise)

### Database (MongoDB)
- Events, predictions, user profiles, decision logs
- Monte Carlo simulation results
- A/B testing analytics
- Subscription and payment tracking

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB (localhost:27017)
- Redis (localhost:6379)
- The Odds API key (optional, for live data)

### Installation

1. **Clone & Setup Environment**
```bash
git clone <repo-url>
cd Permutation-Carlos
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

2. **Install Dependencies**
```bash
# Frontend
npm install

# Backend
```

4. **Start Services**
```bash
# Terminal 1: Start backend
./start.sh

# Terminal 2: Start frontend  
npm run dev
```

5. **Access Application**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Features

### Core Analytics
- **Monte Carlo Simulations**: 50,000+ iterations for precise win probability calculations
- **Multi-Sport Support**: NBA, NFL, MLB, NHL with sport-specific modeling
- **Real-Time Odds Integration**: Live data from The Odds API
- **Player Props Analysis**: Individual player performance projections

### Decision Intelligence
- **Risk Management**: Kelly Criterion-based position sizing
- **Decision Capital Profile**: Compliance-focused bankroll management
- **Tilt Detection**: Behavioral pattern analysis with real-time alerts
- **Performance Tracking**: Brier Score, Log Loss, ROI metrics

### Enterprise Features
- **WebSocket Support**: Real-time updates for live games
- **Subscription Tiers**: Stripe-powered billing (Starter/Pro/Enterprise)
- **Affiliate System**: Commission tracking and payouts
- **A/B Testing**: Built-in experimentation framework

## API Documentation

Interactive API docs available at http://localhost:8000/docs

### Key Endpoints
- `GET /api/odds/` - Fetch current game odds
- `POST /api/simulate/` - Run Monte Carlo simulation
- `GET /api/predictions/` - Get AI predictions
- `POST /api/parlay/analyze` - Analyze parlay correlations
- `GET /health` - System health check

## Tech Stack

**Backend**
- FastAPI (Python 3.11+)
- MongoDB (database)
- Redis (event bus & caching)
- NumPy (simulations)
- APScheduler (background tasks)

**Frontend**
- React 19 + TypeScript
- Vite (build tool)
- Tailwind CSS
- WebSocket client

## Project Structure

```
Permutation-Carlos/
├── backend/
│   ├── core/              # Monte Carlo engine, AI agents
│   ├── routes/            # API endpoints
│   ├── services/          # Business logic
│   ├── db/                # MongoDB schemas
│   ├── integrations/      # External APIs
│   └── main.py            # FastAPI app
├── components/            # React UI components
├── services/              # Frontend API clients
├── utils/                 # Shared utilities
└── docs/                  # Documentation
```

## License

Proprietary - All rights reserved  
**Infrastructure:** Redis Event Bus for agent communication

## Documentation

- [MULTI_AGENT_SYSTEM.md](MULTI_AGENT_SYSTEM.md) - **NEW:** Complete agent architecture
- [AGENT_IMPLEMENTATION_COMPLETE.md](AGENT_IMPLEMENTATION_COMPLETE.md) - Implementation summary
- [BACKEND_FRONTEND_INTEGRATION.md](BACKEND_FRONTEND_INTEGRATION.md) - API integration guide
- [QUICKSTART.md](QUICKSTART.md) - Detailed setup instructions

## License

Proprietary - All Rights Reserved
