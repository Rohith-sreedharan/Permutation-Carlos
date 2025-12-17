# Quick Start: Testing the Automated Grading System

## Prerequisites

1. **MongoDB must be running**:
   ```bash
   # Check if MongoDB is running
   pgrep -l mongod
   
   # If not running, install and start it:
   brew tap mongodb/brew
   brew install mongodb-community
   brew services start mongodb-community
   ```

2. **Virtual environment activated**:
   ```bash
   cd /Users/rohithaditya/Downloads/Permutation-Carlos
   source .venv/bin/activate
   ```

3. **Backend server running**:
   ```bash
   cd backend
   uvicorn main:app --reload --port 8000
   ```

---

## Testing the Grading API

### Fix for zsh URL Issue
**Problem**: zsh interprets `?` as a glob pattern  
**Solution**: Quote the entire URL

```bash
# ❌ WRONG (zsh will fail)
curl http://localhost:8000/api/simulations/grading/stats?days_back=7

# ✅ CORRECT (quoted URL)
curl "http://localhost:8000/api/simulations/grading/stats?days_back=7"
```

---

## API Endpoints

### 1. Get Grading Statistics
```bash
# Last 7 days (all sports)
curl "http://localhost:8000/api/simulations/grading/stats?days_back=7"

# Last 30 days
curl "http://localhost:8000/api/simulations/grading/stats?days_back=30"

# Filter by sport
curl "http://localhost:8000/api/simulations/grading/stats?days_back=7&sport_key=basketball_nba"
```

**Response**:
```json
{
  "success": true,
  "data": {
    "total_games": 145,
    "model_fault_count": 23,
    "model_fault_rate": 0.159,
    "avg_delta_model": 6.8,
    "avg_delta_vegas": 5.2,
    "variance_breakdown": {
      "normal": 98,
      "upper_tail_scoring_burst": 15,
      "lower_tail_brickfest": 12,
      "model_drift": 8,
      "model_fault_heavy": 7,
      "rcl_blocked_pre": 5
    },
    "calibration_weight_avg": 1.08
  },
  "days_back": 7
}
```

### 2. Manually Trigger Grading
```bash
# Grade all finished games from last 48 hours
curl -X POST "http://localhost:8000/api/simulations/grading/run?hours_back=48"

# Grade last 24 hours only
curl -X POST "http://localhost:8000/api/simulations/grading/run?hours_back=24"
```

**Response**:
```json
{
  "success": true,
  "summary": {
    "graded": 12,
    "skipped": 8,
    "errors": 0
  },
  "message": "Graded 12 games, skipped 8, errors: 0"
}
```

---

## Cron Job Setup

### Automated Grading Every 30 Minutes

**Option 1: Use setup script** (Recommended)
```bash
cd backend/scripts
./setup_grading_cron.sh
```

**Option 2: Manual crontab**
```bash
# Edit crontab
crontab -e

# Add this line:
*/30 * * * * cd /Users/rohithaditya/Downloads/Permutation-Carlos/backend && source ../.venv/bin/activate && python scripts/grade_finished_games.py >> /var/log/beatvegas/grading.log 2>&1
```

### View Logs
```bash
# Create log directory
sudo mkdir -p /var/log/beatvegas
sudo chown $USER:$USER /var/log/beatvegas

# Watch live logs
tail -f /var/log/beatvegas/grading.log
```

---

## Troubleshooting

### Server Won't Start

**Issue**: `ModuleNotFoundError` or connection errors  
**Fix**: Ensure virtual environment is activated and MongoDB is running

```bash
# 1. Check MongoDB
pgrep -l mongod  # Should show mongod process

# 2. Activate venv
source .venv/bin/activate

# 3. Check Python path
which python  # Should be in .venv/bin/python

# 4. Start server
cd backend
uvicorn main:app --reload --port 8000
```

### MongoDB Connection Timeout

**Issue**: Server hangs at "Waiting for application startup"  
**Fix**: MongoDB not running

```bash
# Start MongoDB
brew services start mongodb-community

# Verify it's running
mongo --eval "db.version()"
```

### Cron Job Not Running

**Issue**: Grading not happening automatically  
**Fix**: Check crontab and logs

```bash
# List current cron jobs
crontab -l

# Check system logs
tail -f /var/log/beatvegas/grading.log

# Test script manually
cd backend
python scripts/grade_finished_games.py
```

### Empty Grading Stats

**Issue**: API returns `total_games: 0`  
**Reason**: No finished games have been graded yet

**Fix**: Either:
1. Wait for games to finish and cron to run
2. Manually trigger grading: `curl -X POST "http://localhost:8000/api/simulations/grading/run"`
3. Seed test data (if in development)

---

## Next Steps

1. **Start MongoDB** (currently installing)
2. **Start backend server** with venv activated
3. **Test endpoints** using quoted URLs
4. **Set up cron job** for automated grading
5. **Monitor logs** to ensure grading runs smoothly

---

## Common Commands Cheat Sheet

```bash
# Start everything
brew services start mongodb-community
cd /Users/rohithaditya/Downloads/Permutation-Carlos
source .venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000

# Test grading API (in another terminal)
curl "http://localhost:8000/api/simulations/grading/stats?days_back=7"
curl -X POST "http://localhost:8000/api/simulations/grading/run"

# View logs
tail -f /var/log/beatvegas/grading.log

# Stop everything
brew services stop mongodb-community
# Ctrl+C to stop uvicorn
```
