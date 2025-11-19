# BeatVegas MVP — Startup Guide

A concise guide to start the BeatVegas MVP app. Minimum required terminals: 2 (Backend + Frontend). Optional third terminal if running MongoDB locally.

## Terminal setup
- Terminal 1 — Backend (FastAPI)
- Terminal 2 — Frontend (React + Vite)
- Terminal 3 (optional) — MongoDB (local) or use MongoDB Atlas (no local process)

## Step-by-step

### Terminal 1 — Start Backend API
Commands:
```bash
# from backend directory
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Expected:
- Backend: http://localhost:8000
- API docs (Swagger): http://localhost:8000/docs
- Alternative docs (Redoc): http://localhost:8000/redoc

### Terminal 2 — Start Frontend
Commands:
```bash
# from frontend directory
npm install
npm run dev
```
Expected:
- Frontend: http://localhost:5173

### Terminal 3 (Optional) — MongoDB
Option A — MongoDB Atlas (recommended)
- No local process required.
- Set MONGODB_URI in .env to your Atlas connection string.

Option B — Local MongoDB (development)
```bash
# ensure mongod is running
mongod --port 27017 --dbpath ./data/db
```

## Pre-start checklist
- .env: required variables present (e.g. MONGODB_URI, ODDS_API_KEY, other app-specific keys)
- Dependencies installed:
   - Backend: Python packages from requirements.txt
   - Frontend: npm packages
- MongoDB reachable (Atlas or local)

## Quick start (two terminals)
Terminal 1 (backend):
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
Terminal 2 (frontend):
```bash
cd frontend
npm run dev
```

## Test the setup
- Backend health / API: curl http://localhost:8000/health or open /docs
- Frontend: open http://localhost:5173
- Full flow: exercise a UI action that triggers a backend request

## How to stop
- Backend / Frontend: press Ctrl + C in each terminal
- Local MongoDB: stop mongod process

## Troubleshooting (common issues)
- "Port 8000 already in use": stop the process using that port or change backend port.
- "MongoDB connection refused": verify MONGODB_URI, network access, and that mongod is running.
- "ODDS_API_KEY not configured": add the key to .env.
- "Module not found" (Python): ensure virtualenv is active and requirements are installed.
- Frontend errors: run npm install; check console for missing packages or build errors.

## Summary
| Component   | Terminal | Command (example)                          | Port  | URL                      |
|-------------|----------|-------------------------------------------|-------|--------------------------|
| Backend API | 1        | uvicorn main:app --reload --port 8000     | 8000  | http://localhost:8000    |
| Frontend    | 2        | npm run dev                               | 5173  | http://localhost:5173    |
| MongoDB     | 3 (opt)  | mongod --port 27017                       | 27017 | (local)                 |

Minimum required: 2 terminals (Backend + Frontend). Optional: 3 if running MongoDB locally.

Need a startup script or help creating a .env template? I can generate one for you.