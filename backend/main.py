from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv
import os
import traceback

load_dotenv()

app = FastAPI(
    title="BeatVegas Analytics Engine",
    description="Enterprise Sports Analytics Platform with Monte Carlo Simulations and Multi-Agent AI System",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Read CORS configuration from environment
# Example values in backend/.env.example
cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "*")
if cors_origins.strip() == "*":
    allow_origins = ["*"]
else:
    allow_origins = [o.strip() for o in cors_origins.split(",") if o.strip()]

# Add common localhost variations for development
if allow_origins != ["*"]:
    # Ensure both localhost and 127.0.0.1 with common ports are allowed
    dev_origins = ["http://localhost:3000", "http://localhost:3001", 
                   "http://127.0.0.1:3000", "http://127.0.0.1:3001"]
    for origin in dev_origins:
        if origin not in allow_origins:
            allow_origins.append(origin)

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

# Custom exception handler to ensure CORS headers are always sent
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions and ensure CORS headers are included"""
    print(f"❌ Unhandled exception: {str(exc)}")
    traceback.print_exc()
    
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {str(exc)}"},
        headers={
            "Access-Control-Allow-Origin": request.headers.get("origin", "*"),
            "Access-Control-Allow-Credentials": "true",
        }
    )

# Add A/B testing middleware
try:
    from services.ab_testing import ab_test_middleware
    app.middleware("http")(ab_test_middleware)
except ImportError:
    print("Warning: ab_testing service not available")

# Import routers
from routes.auth_routes import router as auth_router
from routes.whoami_routes import router as whoami_router
from routes.odds_routes import router as odds_router
from routes.core_routes import router as core_router
from routes.account_routes import router as account_router
from routes.ab_test_routes import router as ab_test_router
from routes.affiliate_routes import router as affiliate_router
from routes.community_routes import router as community_router
from routes.simulation_routes import router as simulation_router
from routes.performance_routes import router as performance_router
from routes.tier_routes import router as tier_router
from routes.parlay_routes import router as parlay_router
from routes.notification_routes import router as notification_router
from routes.payment_routes import router as payment_router
from routes.user_routes import router as user_router
from routes.creator_routes import router as creator_router
from routes.enterprise_routes import router as enterprise_router
from routes.predictions_routes import router as predictions_router
from routes.subscription_routes import router as subscription_router, stripe_router
from routes.risk_profile_routes import router as risk_profile_router
from routes.admin_routes import router as admin_router
from routes.verification_routes import router as verification_router
from routes.decision_log_routes import router as decision_log_router
from routes.waitlist_routes import router as waitlist_router
from routes.architect_routes import router as architect_router
from routes.trust_routes import router as trust_router
from routes.daily_cards_routes import router as daily_cards_router
from routes.analytics_routes import router as analytics_router
from routes.clv_routes import router as clv_router
from routes.recap_routes import router as recap_router
from routes.community_enhanced_routes import router as community_enhanced_router
from routes.truth_mode_routes import router as truth_mode_router
from routes.debug_routes import router as debug_router
from routes.daily_preview_routes import router as daily_preview_router
from routes.tracking_routes import router as tracking_router
from routes.war_room_routes import router as war_room_router
from routes.telegram_routes import router as telegram_router
from routes.stripe_webhook_routes import router as stripe_webhook_router
from routes.signal_routes import router as signal_router
from routes.autonomous_edge_routes import router as autonomous_edge_router
from routes.ncaab_routes import router as ncaab_router
from routes.ncaaf_routes import router as ncaaf_router
from routes.nfl_routes import router as nfl_router
from routes.nhl_routes import router as nhl_router
from routes.mlb_routes import router as mlb_router
from routes.analyzer import router as analyzer_router
from routes.market_state_routes import router as market_state_router
from routes.api_key_routes import router as api_key_router

app.include_router(auth_router)
app.include_router(whoami_router)
app.include_router(odds_router)
app.include_router(core_router)
app.include_router(account_router)
app.include_router(ab_test_router)
app.include_router(affiliate_router)
app.include_router(community_router)
app.include_router(community_enhanced_router)  # NEW: Enhanced community features
app.include_router(war_room_router)  # NEW: War Room v1.0 - Intelligence workspace
app.include_router(signal_router)  # NEW: Signal Locks - Immutable signal architecture
app.include_router(autonomous_edge_router)  # NEW: Autonomous Edge Execution - Three-wave simulation system
app.include_router(ncaab_router)  # NEW: NCAAB Edge Evaluation - Two-layer college basketball system
app.include_router(ncaaf_router)  # NEW: NCAAF Edge Evaluation - Two-layer college football system
app.include_router(nfl_router)  # NEW: NFL Edge Evaluation - Two-layer professional football system
app.include_router(nhl_router)  # NEW: NHL Edge Evaluation - Locked spec with 6 protective gates
app.include_router(mlb_router)  # NEW: MLB Edge Evaluation - Locked spec (moneyline primary, weather-aware totals)
app.include_router(analyzer_router)  # NEW: AI Analyzer - LLM-powered game explanations
app.include_router(telegram_router)  # NEW: Telegram Signal Distribution System
app.include_router(stripe_webhook_router)  # Enhanced Stripe webhooks with entitlements
app.include_router(api_key_router)  # NEW: API Key Management - Monitor and rotate The Odds API keys
app.include_router(simulation_router)
app.include_router(performance_router)
app.include_router(tier_router)
app.include_router(parlay_router)
app.include_router(notification_router)
app.include_router(payment_router)
app.include_router(user_router)
app.include_router(creator_router)
app.include_router(enterprise_router)
app.include_router(predictions_router, prefix="/api/admin", tags=["admin"])
app.include_router(subscription_router)
app.include_router(stripe_router)  # Stripe customer portal
app.include_router(risk_profile_router)
app.include_router(admin_router)  # Super-admin routes
app.include_router(verification_router)  # Public Trust Loop data
app.include_router(trust_router)  # Phase 17: Automated Trust Metrics
app.include_router(waitlist_router)  # V1 Launch waitlist
app.include_router(decision_log_router)  # User decision tracking
app.include_router(architect_router)  # AI Parlay Architect
app.include_router(daily_cards_router)  # Daily Best Cards
app.include_router(analytics_router)  # Phase 18: Numerical Accuracy
app.include_router(clv_router)  # CLV Tracking & Performance
app.include_router(recap_router)  # Post-Game Recap & Feedback Loop
app.include_router(truth_mode_router)  # Truth Mode v1.0: Zero-Lies Enforcement
app.include_router(debug_router)  # Debug endpoints for pick state diagnostics
app.include_router(tracking_router)  # Pixel & event tracking (Phase 1.2)
app.include_router(daily_preview_router)  # Daily Preview for marketing conversion
app.include_router(market_state_router)  # Market State Registry - Single source of truth


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, connection_id: str | None = None):
    """
    WebSocket endpoint for real-time updates
    
    Usage from frontend:
    ```typescript
    const ws = new WebSocket('ws://localhost:8000/ws?connection_id=user_123');
    
    // Subscribe to channels
    ws.send(JSON.stringify({
        action: 'subscribe',
        channel: 'events'  // or 'community', 'parlay_{id}'
    }));
    
    // Listen for updates
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === 'RECALCULATION') {
            // Update UI
        }
    };
    ```
    
    Message Types:
    - CONNECTED: Initial connection acknowledgment
    - SUBSCRIBED/UNSUBSCRIBED: Subscription confirmations
    - RECALCULATION: Line movement, injury update
    - NEW_MESSAGE: Community message posted
    - CORRELATION_UPDATE: Parlay correlation changed
    """
    from core.websocket_manager import manager
    import uuid
    import json
    
    # Generate connection ID if not provided
    if not connection_id:
        connection_id = str(uuid.uuid4())
    
    await manager.connect(websocket, connection_id)
    
    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                action = message.get("action")
                
                if action == "subscribe":
                    channel = message.get("channel")
                    if channel:
                        await manager.subscribe(connection_id, channel)
                
                elif action == "unsubscribe":
                    channel = message.get("channel")
                    if channel:
                        await manager.unsubscribe(connection_id, channel)
                
                elif action == "ping":
                    # Keepalive
                    await manager.send_to_connection(connection_id, {
                        "type": "PONG"
                    })
            
            except json.JSONDecodeError:
                await manager.send_to_connection(connection_id, {
                    "type": "ERROR",
                    "message": "Invalid JSON"
                })
    
    except WebSocketDisconnect:
        manager.disconnect(connection_id)
        print(f"WebSocket disconnected: {connection_id}")


@app.on_event("startup")
async def startup_event():
    """Initialize database indexes and multi-agent system"""
    from db.mongo import ensure_indexes, db, client
    ensure_indexes()
    print("✓ Database indexes initialized")
    
    # Initialize v0 audit tables (Phase 1 Option C)
    try:
        from db.audit_schemas import initialize_audit_collections
        from db.audit_logger import get_audit_logger
        
        audit_status = initialize_audit_collections(db)
        audit_logger = get_audit_logger(db)
        
        success_count = sum(1 for v in audit_status.values() if v)
        print(f"✓ Audit tables initialized ({success_count}/4 collections ready)")
    except Exception as e:
        print(f"⚠️ Audit table initialization warning: {e}")
        print("   Audit logging will be limited")
    
    # Start background scheduler
    from services.scheduler import start_scheduler
    start_scheduler()
    
    # Initialize multi-agent system
    try:
        from core.agent_orchestrator import get_orchestrator
        orchestrator = await get_orchestrator(client)
        print("✓ Multi-Agent System initialized")
        
        # Initialize feedback loop
        from services.feedback_loop import FeedbackLoop
        from core.event_bus import get_event_bus
        bus = await get_event_bus()
        feedback = FeedbackLoop(client, bus)
        await feedback.start()
        print("✓ Behavioral Feedback Loop (MOAT) active")
    except Exception as e:
        print(f"⚠️ Agent system startup error: {e}")
        print("   Agents will be unavailable but API will function")
    
    # Start Autonomous Edge Scheduler
    try:
        from services.autonomous_edge_scheduler import start_autonomous_scheduler
        await start_autonomous_scheduler(db)
        print("✓ Autonomous Edge Scheduler active (three-wave system)")
    except Exception as e:
        print(f"⚠️ Autonomous Edge Scheduler startup error: {e}")
        print("   Manual simulation triggers still available")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean shutdown"""
    from services.scheduler import stop_scheduler
    stop_scheduler()
    
    # Shutdown agent system
    try:
        from core.agent_orchestrator import shutdown_orchestrator
        await shutdown_orchestrator()
        print("✓ Multi-Agent System shutdown complete")
    except Exception:
        pass
    
    # Shutdown autonomous edge scheduler
    try:
        from services.autonomous_edge_scheduler import stop_autonomous_scheduler
        await stop_autonomous_scheduler()
        print("✓ Autonomous Edge Scheduler shutdown complete")
    except Exception:
        pass


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "BeatVegas & Omni Edge AI Platform",
        "version": "2.0.0",
        "features": [
            "Monte Carlo Simulations (10K-100K iterations)",
            "Multi-Agent AI System (7 specialized agents)",
            "Tiered Subscriptions (Starter/Pro/Sharps Room/Founder)",
            "CLV Tracking (Pro+)",
            "Performance Metrics (Brier Score, Log Loss, ROI)",
            "A/B Testing (5 variants, 90-day tracking)",
            "Affiliate Viral Loop (20-40% tiered commissions)",
            "Module 7: Reflection Loop (self-improving AI)",
            "Community Data Pipeline (NLP + Reputation)",
            "Hybrid AI (odds + weighted sentiment)",
            "Real-time Odds Polling (< 20s freshness)"
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

