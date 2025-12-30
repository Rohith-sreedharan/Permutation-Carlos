# Environment Variables Configuration Guide

This document describes all environment variables used in the BeatVegas application for production deployment.

## Frontend Environment Variables

Create a `.env` file in the root directory:

```bash
# API Configuration
VITE_API_BASE_URL=http://localhost:8000  # Change to https://api.beatvegas.app in production
VITE_API_URL=http://localhost:8000        # Change to https://api.beatvegas.app in production
```

### Usage in Frontend

All frontend components now use the `VITE_API_BASE_URL` constant:

```typescript
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

// Then use it in fetch calls:
fetch(`${API_BASE_URL}/api/endpoint`)
```

Components using this pattern:
- `BettingCommandCenter.tsx`
- `WarRoom.tsx`
- `LandingPage.tsx`
- `TrustLoop.tsx`
- `DailyBestCards.tsx`
- `WarRoomLeaderboard.tsx`
- `CommunityEnhanced.tsx`
- `DecisionCommandCenter.tsx`
- `SharpsRoom.tsx`
- `ParlayBuilder.tsx`
- `GameDetail.tsx`
- `ManualBetEntry.tsx`
- `OnboardingWizard.tsx`
- `ParlayArchitect.tsx`

## Backend Environment Variables

Edit `backend/.env`:

```bash
# Database
MONGO_URI=mongodb://localhost:27017  # Change to production MongoDB URI

# CORS Configuration
CORS_ALLOW_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,https://beatvegas.app

# Frontend URL (for redirects, emails, etc.)
FRONTEND_URL=http://localhost:5173  # Change to https://beatvegas.app in production

# API Keys
ODDS_API_KEY=your_odds_api_key
CFB_API_KEY=your_cfb_api_key

# Stripe
STRIPE_SECRET_KEY=your_stripe_secret_key
STRIPE_WEBHOOK_SECRET=your_stripe_webhook_secret

# Redis (optional)
REDIS_URL=redis://localhost:6379  # Change to production Redis URL
```

### Backend Files Using Environment Variables

**Routes:**
- `payment_routes.py` - Uses `FRONTEND_URL` for success/cancel redirects
- `auth_routes.py` - WebAuthn configuration
- `account_routes.py` - WebAuthn expected_origin
- `subscription_routes.py` - Uses `FRONTEND_URL` for billing portal
- `war_room_routes.py` - MongoDB connection
- `telegram_routes.py` - MongoDB connection
- `signal_routes.py` - MongoDB connection
- `stripe_webhook_routes.py` - MongoDB connection

**Scripts:**
- `regenerate_daily_cards.py` - Uses `API_URL` environment variable
- `setup_telegram.py` - Uses `MONGODB_URI`
- `update_user_tier.py` - Uses `MONGO_URI`
- `remediation.py` - Uses `MONGO_URI`
- `fix_beatvegas_db.py` - Uses `MONGO_URI`
- `nightly_reconciliation.py` - Uses `MONGO_URI`

**Core:**
- `db/mongo.py` - Uses `MONGO_URI`
- `main.py` - Uses `CORS_ALLOW_ORIGINS`
- `core/event_bus.py` - Redis URL configuration

## Production Deployment

### 1. Update Frontend .env

```bash
VITE_API_BASE_URL=https://api.beatvegas.app
VITE_API_URL=https://api.beatvegas.app
```

### 2. Update Backend .env

```bash
MONGO_URI=mongodb+srv://username:password@cluster.mongodb.net/beatvegas
CORS_ALLOW_ORIGINS=https://beatvegas.app,https://www.beatvegas.app
FRONTEND_URL=https://beatvegas.app
REDIS_URL=redis://production-redis-host:6379
```

### 3. Build Frontend

```bash
npm run build
```

The built files in `dist/` will use the environment variables from `.env`.

### 4. Run Backend

```bash
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Development vs Production

### Development
- Frontend: `http://localhost:5173` (Vite dev server)
- Backend: `http://localhost:8000`
- WebSocket: `ws://localhost:8000/ws`
- MongoDB: `mongodb://localhost:27017`

### Production
- Frontend: `https://beatvegas.app` (static files served by Nginx/CDN)
- Backend: `https://api.beatvegas.app`
- WebSocket: `wss://api.beatvegas.app/ws`
- MongoDB: `mongodb+srv://cluster.mongodb.net`

## Notes

1. **WebAuthn Configuration**: The `rpId` in `AuthPage.tsx` and backend routes is hardcoded to `"localhost"` for development. For production, update to your production domain (e.g., `"beatvegas.app"`).

2. **WebSocket**: The `useWebSocket.ts` utility automatically detects the environment and uses the correct protocol (ws:// for localhost, wss:// for production).

3. **API Module**: The `services/api.ts` module already handles environment detection and uses the appropriate API URL.

4. **Vite Proxy**: The `vite.config.ts` proxy configuration is only used in development mode and doesn't affect production builds.

5. **Settings.tsx**: Contains a UI warning for users accessing via `127.0.0.1` instead of `localhost` (WebAuthn requirement).

## Verification

After deployment, verify:

1. ✅ Frontend loads from production domain
2. ✅ API calls go to production API URL (check browser DevTools Network tab)
3. ✅ WebSocket connects to production WSS endpoint
4. ✅ CORS allows production domain
5. ✅ Stripe redirects use production URLs
6. ✅ No hardcoded localhost URLs in production builds

## Troubleshooting

**Issue**: API calls fail with CORS errors
- **Solution**: Add your production domain to `CORS_ALLOW_ORIGINS` in backend/.env

**Issue**: Stripe redirects to localhost after payment
- **Solution**: Update `FRONTEND_URL` in backend/.env to production URL

**Issue**: WebSocket fails to connect
- **Solution**: Ensure your reverse proxy (Nginx) supports WebSocket upgrades

**Issue**: MongoDB connection fails
- **Solution**: Check `MONGO_URI` format and network access from server
