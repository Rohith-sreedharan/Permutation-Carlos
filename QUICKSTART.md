# BeatVegas Platform - Quick Start Guide

## 🚀 Prerequisites

Before starting, ensure you have:

1. **Python 3.9+** installed
2. **MongoDB** installed and running
3. **Odds API Key** from [The Odds API](https://the-odds-api.com)

## 📦 Installation

### 1. Clone and Navigate

```bash
cd /Users/rohithaditya/Downloads/Permutation-Carlos
```

### 2. Start MongoDB

**macOS (Homebrew):**
```bash
brew services start mongodb-community
```

**Linux (systemd):**
```bash
sudo systemctl start mongod
```

**Docker:**
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### 3. Configure Environment

Edit `backend/.env` with your credentials:

```bash
# Required
ODDS_API_KEY=your_odds_api_key_here
MONGO_URI=mongodb://localhost:27017
DATABASE_NAME=beatvegas_db

# Stripe (for production)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# CORS (adjust for your frontend)
CORS_ALLOW_ORIGINS=http://localhost:5173,https://beatvegas.app
```

### 4. Run the Platform

**Automated (Recommended):**
```bash
chmod +x start.sh
./start.sh
```

**Manual:**
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## 🔍 Verify Installation

### Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "database": "connected"
}
```

### System Info
```bash
curl http://localhost:8000/
```

### API Documentation
Open your browser: http://localhost:8000/docs

## 🧪 Test the System

### 1. Test A/B Testing
```bash
# Get session variant
curl http://localhost:8000/api/ab-test/session

# Track event
curl -X POST http://localhost:8000/api/ab-test/track \
  -H "Content-Type: application/json" \
  -d '{"event": "view_landing"}'
```

### 2. Test Affiliate System
```bash
# Create affiliate account
curl -X POST "http://localhost:8000/api/affiliate/create-account?name=TestAffiliate&email=test@example.com"

# Register subscriber with ref
curl -X POST http://localhost:8000/api/affiliate/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "ref": "AFF_12345"}'
```

### 3. Test Community System
```bash
# Post a message
curl -X POST http://localhost:8000/api/community/message \
  -H "Content-Type: application/json" \
  -d '{
    "channel_id": "nba-picks",
    "text": "Lakers -5.5 is a lock! Hammering 3u.",
    "user_id": "usr_test123",
    "user_plan": "elite"
  }'

# Get community leaderboard
curl http://localhost:8000/api/community/leaderboard
```

### 4. Test AI Picks
```bash
# Fetch odds
curl "http://localhost:8000/api/core/fetch-odds?sport=basketball_nba"

# Normalize data
curl -X POST "http://localhost:8000/api/core/normalize?limit=5"

# Generate predictions
curl -X POST "http://localhost:8000/api/core/predict?event_id=YOUR_EVENT_ID"
```

## 📊 Monitor Background Jobs

The scheduler runs automatically on startup:

- **NBA Odds Polling:** Every 60 seconds
- **NFL Odds Polling:** Every 60 seconds  
- **MLB Odds Polling:** Every 60 seconds
- **Reflection Loop:** Sundays at 2 AM

### Check Logs
```bash
# In the terminal running uvicorn
# Look for:
✓ Polled 14 events for basketball_nba in 850ms
⟳ Running Module 7: Reflection Loop...
✓ Reflection Loop complete: ROI 8.2%, CLV 2.1%
```

## 🔧 Troubleshooting

### MongoDB Connection Failed
```bash
# Check if MongoDB is running
pgrep -x mongod

# If not, start it
brew services start mongodb-community  # macOS
sudo systemctl start mongod            # Linux
```

### Missing Dependencies
```bash
cd backend
source .venv/bin/activate
pip install -r requirements.txt
```

### Port 8000 Already in Use
```bash
# Use a different port
uvicorn main:app --reload --port 8001
```

### Odds API Rate Limit
```bash
# Check your API usage at https://the-odds-api.com/account
# Free tier: 500 requests/month
# Consider upgrading for production
```

## 📈 Next Steps

1. **Frontend Integration**
   - Connect React app to backend API
   - Implement A/B test variants in UI
   - Build affiliate dashboard

2. **Stripe Integration**
   - Add webhook endpoint to production
   - Test subscription flows
   - Verify commission calculations

3. **Production Deployment**
   - Deploy to cloud (AWS/GCP/Azure)
   - Configure MongoDB Atlas
   - Set up monitoring (Datadog/New Relic)
   - Enable HTTPS and rate limiting

4. **Data Collection**
   - Start gathering pick performance data
   - Build historical CLV dataset
   - Train production ML model

## 📚 Additional Resources

- **System Overview:** `SYSTEM_OVERVIEW.md`
- **API Documentation:** `backend/docs/API_FLOW.md`
- **Module Documentation:** `backend/docs/MODULE_DOCS.md`
- **Database Schemas:** `backend/db/schemas/`

## 💡 Tips

- **Development Mode:** Auto-reload is enabled with `--reload` flag
- **Database GUI:** Use MongoDB Compass to visualize data
- **API Testing:** Use Postman or the built-in Swagger UI
- **Logs:** Check `backend/logs_core_ai` collection in MongoDB

## 🆘 Support

For technical issues or questions:
- Email: engineering@beatvegas.io
- Internal Docs: Confluence/Notion

---

**Ready to disrupt the sports betting industry? Let's build! 🚀**
