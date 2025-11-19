from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(
    title="BeatVegas & Omni Edge AI Platform",
    description="Sports Analytics Data Asset with A/B Testing, Affiliate System, and Self-Improving AI",
    version="2.0.0"
)

# Read CORS configuration from environment
# Example values in backend/.env.example
cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
if cors_origins.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

# Only allow credentials when explicit origins are configured
allow_credentials = False
if allow_origins != ["*"]:
    allow_credentials = os.getenv("CORS_ALLOW_CREDENTIALS", "false").lower() in ("1", "true", "yes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add A/B testing middleware
from services.ab_testing import ab_test_middleware
app.middleware("http")(ab_test_middleware)

# Import routers
from routes.auth_routes import router as auth_router
from routes.odds_routes import router as odds_router
from routes.core_routes import router as core_router
from routes.account_routes import router as account_router
from routes.ab_test_routes import router as ab_test_router
from routes.affiliate_routes import router as affiliate_router
from routes.community_routes import router as community_router

app.include_router(auth_router)
app.include_router(odds_router)
app.include_router(core_router)
app.include_router(account_router)
app.include_router(ab_test_router)
app.include_router(affiliate_router)
app.include_router(community_router)


@app.on_event("startup")
async def startup_event():
    """Initialize database indexes on startup"""
    from db.mongo import ensure_indexes
    ensure_indexes()
    print("✓ Database indexes initialized")
    
    # Start background scheduler
    from services.scheduler import start_scheduler
    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    from services.scheduler import stop_scheduler
    stop_scheduler()


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "BeatVegas & Omni Edge AI Platform",
        "version": "2.0.0",
        "features": [
            "A/B Testing (5 variants, 90-day tracking)",
            "Affiliate Viral Loop (zero-ad spend growth)",
            "Module 7: Reflection Loop (self-improving AI)",
            "Community Data Pipeline (NLP + Reputation)",
            "Hybrid AI (odds + weighted sentiment)",
            "Real-time Odds Polling (< 20s freshness)",
            "CLV/ROI Optimization"
        ]
    }


@app.get("/health")
def health_check():
    """Health check for load balancers"""
    from db.mongo import db
    try:
        # Test MongoDB connection
        db.command("ping")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}

