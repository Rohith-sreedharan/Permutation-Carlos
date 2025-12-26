"""
AI Analyzer API Routes
FastAPI endpoints for AI Analyzer feature.
"""

from fastapi import APIRouter, HTTPException, Depends, Header
from typing import Optional
import os

from ..services.ai_analyzer_schemas import AnalyzerRequest, AnalyzerResponse
from ..services.ai_analyzer_service import AnalyzerService
from ..services.ai_analyzer_llm import AnalyzerLLMClient
from ..services.ai_analyzer_audit import AnalyzerAuditLogger
from ..db.mongo import db


router = APIRouter(prefix="/api/analyzer", tags=["AI Analyzer"])


# Dependency injection for analyzer service
def get_analyzer_service():
    """Get analyzer service instance"""
    from db.mongo import db
    
    # Initialize components
    llm_client = AnalyzerLLMClient(
        api_key=os.getenv("OPENAI_API_KEY"),
        model=os.getenv("ANALYZER_LLM_MODEL", "gpt-4o-mini"),
        timeout_seconds=int(os.getenv("ANALYZER_TIMEOUT_SECONDS", "10")),
        max_tokens=int(os.getenv("ANALYZER_MAX_TOKENS", "800"))
    )
    
    audit_logger = AnalyzerAuditLogger(db)
    
    service = AnalyzerService(
        db=db,
        llm_client=llm_client,
        audit_logger=audit_logger,
        cache_ttl_seconds=int(os.getenv("ANALYZER_CACHE_TTL", "300")),
        rate_limit_per_user=int(os.getenv("ANALYZER_RATE_LIMIT", "20")),
        rate_limit_window_seconds=int(os.getenv("ANALYZER_RATE_WINDOW", "3600"))
    )
    
    return service


@router.post("/explain", response_model=AnalyzerResponse)
async def explain_game(
    request: AnalyzerRequest,
    user_id: Optional[str] = Header(None, alias="X-User-ID"),
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Generate AI explanation for a game.
    
    **Purpose**: Explain existing model output in plain English.
    
    **Important**:
    - This endpoint does NOT generate picks
    - It explains what the model sees based on existing analysis
    - Respects and reinforces the EDGE/LEAN/NO_PLAY state
    
    **Request**:
    - game_id: Unique game identifier
    - sport: Sport (NBA, NFL, NCAAB, NCAAF, MLB, NHL)
    - market_focus: Optional market focus (SPREAD, TOTAL, ML, etc.)
    
    **Response**:
    - success: Whether explanation was generated
    - explanation: Structured explanation with sections
    - fallback_triggered: Whether fallback was used
    - cached: Whether response was cached
    
    **Rate Limiting**:
    - 20 requests per hour per user (configurable)
    - Pass X-User-ID header for per-user rate limiting
    
    **Caching**:
    - Responses cached for 5 minutes (configurable)
    - Same input returns cached result
    
    **Safety**:
    - All outputs validated for banned terms
    - State alignment enforced
    - Fallback returned on any safety violation
    """
    try:
        response = service.explain(request, user_id=user_id)
        return response
    
    except Exception as e:
        # Should not reach here (service handles all errors)
        # But provide safe fallback anyway
        raise HTTPException(
            status_code=500,
            detail=f"Analyzer service error: {str(e)}"
        )


@router.get("/stats")
async def get_analyzer_stats(
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Get analyzer service statistics.
    
    **Returns**:
    - cache_size: Number of cached responses
    - llm_stats: LLM client statistics
    """
    return service.get_stats()


@router.post("/clear-cache")
async def clear_analyzer_cache(
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Clear analyzer cache.
    
    **Use case**: Force fresh LLM calls for all games
    
    **Note**: Requires admin authorization (add auth middleware as needed)
    """
    service.clear_cache()
    return {"message": "Cache cleared successfully"}


@router.get("/audit/{audit_id}")
async def get_audit_entry(
    audit_id: str,
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Retrieve specific audit entry.
    
    **Returns**: Full audit log entry with hashes, timing, and metadata
    """
    entry = service.audit_logger.get_audit_entry(audit_id)
    
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    
    return entry


@router.get("/audit/game/{game_id}")
async def get_game_audit_history(
    game_id: str,
    limit: int = 10,
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Get audit history for a specific game.
    
    **Use case**: See all analyzer calls for a game
    
    **Returns**: List of audit entries, most recent first
    """
    history = service.audit_logger.get_game_audit_history(game_id, limit)
    return {"game_id": game_id, "entries": history}


@router.get("/audit/user/{user_id}")
async def get_user_audit_history(
    user_id: str,
    limit: int = 20,
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Get audit history for a specific user.
    
    **Use case**: User request history, abuse detection
    
    **Returns**: List of audit entries, most recent first
    """
    history = service.audit_logger.get_user_audit_history(user_id, limit)
    return {"user_id": user_id, "entries": history}


@router.get("/monitoring/blocked")
async def get_blocked_requests(
    hours: int = 24,
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Get blocked requests in last N hours.
    
    **Use case**: Safety monitoring, abuse detection
    
    **Returns**: List of blocked requests with reasons
    """
    blocked = service.audit_logger.get_blocked_requests(hours)
    return {
        "hours": hours,
        "blocked_count": len(blocked),
        "blocked_requests": blocked
    }


@router.get("/monitoring/stats")
async def get_monitoring_stats(
    hours: int = 24,
    service: AnalyzerService = Depends(get_analyzer_service)
):
    """
    Get comprehensive monitoring statistics.
    
    **Returns**:
    - total_requests: Total analyzer calls
    - success_rate: Percentage of successful explanations
    - fallback_rate: Percentage of fallback triggers
    - blocked_rate: Percentage of blocked requests
    - avg_response_time_ms: Average response time
    - total_tokens_used: Total LLM tokens consumed
    """
    return service.audit_logger.get_stats_summary(hours)


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    **Returns**: Service status
    """
    # Check OpenAI API key configured
    if not os.getenv("OPENAI_API_KEY"):
        return {
            "status": "unhealthy",
            "error": "OPENAI_API_KEY not configured"
        }
    
    return {
        "status": "healthy",
        "model": os.getenv("ANALYZER_LLM_MODEL", "gpt-4o-mini"),
        "cache_ttl": int(os.getenv("ANALYZER_CACHE_TTL", "300")),
        "rate_limit": int(os.getenv("ANALYZER_RATE_LIMIT", "20"))
    }
