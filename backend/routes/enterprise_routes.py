"""
Enterprise API Routes
=====================

B2B API endpoints for enterprise customers (sportsbooks, media companies, hedge funds).

Authentication: X-API-KEY header (validated against api_keys collection)
Rate Limiting: 5 requests/second per API key
Revenue Model: $50K-$500K/year tiered pricing

Endpoints:
----------
1. GET /api/enterprise/predictions - Distribution curves for all active events
2. GET /api/enterprise/predictions/{event_id} - Single event distribution curve
3. GET /api/enterprise/health - API key status and rate limit info
4. POST /api/enterprise/webhook - Configure webhook for real-time updates

Tier Pricing:
-------------
- Starter ($50K/year): 5 req/s, 1 sport, 10K requests/day
- Growth ($150K/year): 10 req/s, 2 sports, 50K requests/day
- Enterprise ($500K/year): 25 req/s, all sports, unlimited requests

Example Response (distribution_curve):
--------------------------------------
{
  "event_id": "nba_lakers_celtics_20240115",
  "sport": "NBA",
  "home_team": "Los Angeles Lakers",
  "away_team": "Boston Celtics",
  "win_probability": 0.6234,
  "distribution_curve": {
    "home_scores": [110, 112, 115, 108, 113, ...],  # 10,000 simulations
    "away_scores": [105, 109, 103, 111, 107, ...],
    "mean_spread": -5.2,
    "std_spread": 10.3,
    "percentiles": {
      "5th": -25.1,
      "25th": -12.4,
      "50th": -5.2,
      "75th": 2.1,
      "95th": 14.8
    }
  },
  "volatility": "MEDIUM",
  "last_updated": "2024-01-15T19:30:00Z"
}
"""

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import time

router = APIRouter(prefix="/api/enterprise", tags=["enterprise"])

# In-memory rate limiter (production: use Redis)
rate_limit_store: Dict[str, List[float]] = {}


class DistributionCurveResponse(BaseModel):
    event_id: str
    sport: str
    home_team: str
    away_team: str
    win_probability: float
    distribution_curve: Dict[str, Any]
    volatility: str
    last_updated: str


class APIKeyInfo(BaseModel):
    tier: str
    rate_limit: int
    daily_limit: int
    requests_today: int
    expires_at: str


class WebhookConfig(BaseModel):
    url: str
    events: List[str]  # ['prediction_update', 'game_result', 'odds_change']
    secret: str  # For webhook signature validation


def validate_api_key(x_api_key: str, db) -> Dict[str, Any]:
    """
    Validate X-API-KEY header against MongoDB api_keys collection.
    
    Args:
        x_api_key: API key from request header
        db: MongoDB database instance
        
    Returns:
        API key document with tier, rate_limit, daily_limit
        
    Raises:
        HTTPException: 401 if key invalid/expired, 403 if rate limited
    """
    api_keys_collection = db['api_keys']
    key_doc = api_keys_collection.find_one({'key': x_api_key, 'active': True})
    
    if not key_doc:
        raise HTTPException(status_code=401, detail="Invalid or expired API key")
    
    # Check expiration
    if key_doc.get('expires_at') and key_doc['expires_at'] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="API key expired")
    
    # Check tier limits
    tier = key_doc.get('tier', 'starter')
    tier_limits = {
        'starter': {'rate_limit': 5, 'daily_limit': 10000},
        'growth': {'rate_limit': 10, 'daily_limit': 50000},
        'enterprise': {'rate_limit': 25, 'daily_limit': None}  # Unlimited
    }
    
    limits = tier_limits.get(tier, tier_limits['starter'])
    
    # Rate limiting (requests per second)
    current_time = time.time()
    if x_api_key not in rate_limit_store:
        rate_limit_store[x_api_key] = []
    
    # Remove timestamps older than 1 second
    rate_limit_store[x_api_key] = [
        ts for ts in rate_limit_store[x_api_key] 
        if current_time - ts < 1.0
    ]
    
    # Check rate limit
    if len(rate_limit_store[x_api_key]) >= limits['rate_limit']:
        raise HTTPException(
            status_code=429, 
            detail=f"Rate limit exceeded: {limits['rate_limit']} req/s for {tier} tier"
        )
    
    # Add current request timestamp
    rate_limit_store[x_api_key].append(current_time)
    
    # Check daily limit (if applicable)
    if limits['daily_limit']:
        today = datetime.now(timezone.utc).date()
        usage_key = f"{x_api_key}_{today}"
        # In production, store this in Redis/MongoDB
        # For now, skip daily limit check (future enhancement)
    
    return {
        'tier': tier,
        'rate_limit': limits['rate_limit'],
        'daily_limit': limits['daily_limit'],
        'customer_id': key_doc.get('customer_id'),
        'allowed_sports': key_doc.get('allowed_sports', ['NBA'])  # Tier-restricted sports
    }


@router.get("/predictions", response_model=List[DistributionCurveResponse])
async def get_all_predictions(
    request: Request,
    x_api_key: str = Header(...),
    sport: Optional[str] = None,
    limit: int = 100
):
    """
    Get distribution curves for all active events.
    
    Query Parameters:
        - sport: Filter by sport (NBA, NFL, MLB, NHL, or 'all')
        - limit: Max number of events to return (default: 100, max: 500)
    
    Headers:
        - X-API-KEY: Your enterprise API key
    
    Returns:
        List of distribution curve objects with win probabilities
    """
    db = request.app.state.db
    
    # Validate API key and check rate limits
    key_info = validate_api_key(x_api_key, db)
    
    # Check if sport is allowed for this tier
    if sport and sport != 'all':
        if sport not in key_info['allowed_sports']:
            raise HTTPException(
                status_code=403, 
                detail=f"Sport '{sport}' not included in {key_info['tier']} tier. Upgrade to access."
            )
    
    # Query simulations collection
    simulations_collection = db['monte_carlo_simulations']
    
    # Build query
    query: Dict[str, Any] = {'is_active': True}
    if sport and sport != 'all':
        # Map frontend sport names to odds API keys
        sport_key_map = {
            'NBA': 'basketball_nba',
            'NFL': 'americanfootball_nfl',
            'MLB': 'baseball_mlb',
            'NHL': 'icehockey_nhl'
        }
        query['sport_key'] = sport_key_map.get(sport, sport.lower())
    
    # Limit results
    limit = min(limit, 500)  # Cap at 500 events
    
    simulations = simulations_collection.find(query).limit(limit).sort('created_at', -1)
    
    results = []
    for sim in simulations:
        # Extract distribution curve data
        distribution = {
            'home_scores': sim.get('distribution_curve', {}).get('home_scores', []),
            'away_scores': sim.get('distribution_curve', {}).get('away_scores', []),
            'mean_spread': sim.get('distribution_curve', {}).get('mean_spread', 0.0),
            'std_spread': sim.get('distribution_curve', {}).get('std_spread', 0.0),
            'percentiles': sim.get('distribution_curve', {}).get('percentiles', {})
        }
        
        results.append(DistributionCurveResponse(
            event_id=sim.get('event_id', ''),
            sport=sim.get('sport_key', '').upper(),
            home_team=sim.get('home_team', ''),
            away_team=sim.get('away_team', ''),
            win_probability=sim.get('win_probability', 0.0),
            distribution_curve=distribution,
            volatility=sim.get('volatility', 'MEDIUM'),
            last_updated=sim.get('created_at', datetime.now(timezone.utc)).isoformat()
        ))
    
    return results


@router.get("/predictions/{event_id}", response_model=DistributionCurveResponse)
async def get_single_prediction(
    event_id: str,
    request: Request,
    x_api_key: str = Header(...)
):
    """
    Get distribution curve for a specific event.
    
    Path Parameters:
        - event_id: Event identifier (e.g., 'nba_lakers_celtics_20240115')
    
    Headers:
        - X-API-KEY: Your enterprise API key
    
    Returns:
        Distribution curve object with full simulation data
    """
    db = request.app.state.db
    
    # Validate API key and check rate limits
    validate_api_key(x_api_key, db)
    
    # Query simulations collection
    simulations_collection = db['monte_carlo_simulations']
    sim = simulations_collection.find_one({'event_id': event_id})
    
    if not sim:
        raise HTTPException(status_code=404, detail=f"Event '{event_id}' not found")
    
    # Extract distribution curve data
    distribution = {
        'home_scores': sim.get('distribution_curve', {}).get('home_scores', []),
        'away_scores': sim.get('distribution_curve', {}).get('away_scores', []),
        'mean_spread': sim.get('distribution_curve', {}).get('mean_spread', 0.0),
        'std_spread': sim.get('distribution_curve', {}).get('std_spread', 0.0),
        'percentiles': sim.get('distribution_curve', {}).get('percentiles', {})
    }
    
    return DistributionCurveResponse(
        event_id=sim.get('event_id', ''),
        sport=sim.get('sport_key', '').upper(),
        home_team=sim.get('home_team', ''),
        away_team=sim.get('away_team', ''),
        win_probability=sim.get('win_probability', 0.0),
        distribution_curve=distribution,
        volatility=sim.get('volatility', 'MEDIUM'),
        last_updated=sim.get('created_at', datetime.now(timezone.utc)).isoformat()
    )


@router.get("/health", response_model=APIKeyInfo)
async def check_api_key_health(
    request: Request,
    x_api_key: str = Header(...)
):
    """
    Check API key status, tier, and rate limits.
    
    Headers:
        - X-API-KEY: Your enterprise API key
    
    Returns:
        API key info with tier, limits, and usage stats
    """
    db = request.app.state.db
    
    # Validate API key (will throw 401 if invalid)
    key_info = validate_api_key(x_api_key, db)
    
    # Get key document for expiration date
    api_keys_collection = db['api_keys']
    key_doc = api_keys_collection.find_one({'key': x_api_key})
    
    # Calculate requests today (mock for now)
    # In production, query usage_logs collection
    requests_today = len(rate_limit_store.get(x_api_key, []))
    
    return APIKeyInfo(
        tier=key_info['tier'],
        rate_limit=key_info['rate_limit'],
        daily_limit=key_info['daily_limit'] or 999999,
        requests_today=requests_today,
        expires_at=key_doc.get('expires_at', datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
    )


@router.post("/webhook")
async def configure_webhook(
    webhook_config: WebhookConfig,
    request: Request,
    x_api_key: str = Header(...)
):
    """
    Configure webhook for real-time prediction updates.
    
    Headers:
        - X-API-KEY: Your enterprise API key
    
    Body:
        - url: Webhook endpoint URL (must be HTTPS)
        - events: List of event types to subscribe to
        - secret: Shared secret for webhook signature validation
    
    Returns:
        Webhook configuration confirmation
    """
    db = request.app.state.db
    
    # Validate API key
    key_info = validate_api_key(x_api_key, db)
    
    # Validate webhook URL (must be HTTPS)
    if not webhook_config.url.startswith('https://'):
        raise HTTPException(status_code=400, detail="Webhook URL must use HTTPS")
    
    # Validate event types
    valid_events = ['prediction_update', 'game_result', 'odds_change', 'volatility_alert']
    for event in webhook_config.events:
        if event not in valid_events:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {event}")
    
    # Store webhook config in MongoDB
    webhooks_collection = db['webhooks']
    webhook_doc = {
        'api_key': x_api_key,
        'customer_id': key_info['customer_id'],
        'url': webhook_config.url,
        'events': webhook_config.events,
        'secret': webhook_config.secret,  # In production, hash this!
        'active': True,
        'created_at': datetime.now(timezone.utc)
    }
    
    # Upsert webhook config
    webhooks_collection.update_one(
        {'api_key': x_api_key},
        {'$set': webhook_doc},
        upsert=True
    )
    
    return {
        'message': 'Webhook configured successfully',
        'url': webhook_config.url,
        'events': webhook_config.events,
        'active': True
    }


@router.get("/usage")
async def get_usage_stats(
    request: Request,
    x_api_key: str = Header(...),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """
    Get API usage statistics for billing and monitoring.
    
    Query Parameters:
        - start_date: ISO 8601 date string (e.g., '2024-01-01')
        - end_date: ISO 8601 date string (e.g., '2024-01-31')
    
    Headers:
        - X-API-KEY: Your enterprise API key
    
    Returns:
        Usage stats with request counts, latency, and error rates
    """
    db = request.app.state.db
    
    # Validate API key
    key_info = validate_api_key(x_api_key, db)
    
    # Parse dates
    if start_date:
        start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    else:
        start_dt = datetime.now(timezone.utc) - timedelta(days=30)
    
    if end_date:
        end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    else:
        end_dt = datetime.now(timezone.utc)
    
    # Query usage_logs collection (future enhancement)
    # For now, return mock data
    usage_logs_collection = db.get('usage_logs')
    
    if usage_logs_collection:
        logs = usage_logs_collection.find({
            'api_key': x_api_key,
            'timestamp': {'$gte': start_dt, '$lte': end_dt}
        })
        
        total_requests = 0
        total_latency = 0.0
        error_count = 0
        
        for log in logs:
            total_requests += 1
            total_latency += log.get('latency_ms', 0)
            if log.get('status_code', 200) >= 400:
                error_count += 1
        
        avg_latency = total_latency / total_requests if total_requests > 0 else 0
        error_rate = (error_count / total_requests * 100) if total_requests > 0 else 0
    else:
        # Mock data if usage_logs doesn't exist yet
        total_requests = 1247
        avg_latency = 145.3
        error_rate = 0.8
    
    return {
        'customer_id': key_info['customer_id'],
        'tier': key_info['tier'],
        'start_date': start_dt.isoformat(),
        'end_date': end_dt.isoformat(),
        'total_requests': total_requests,
        'avg_latency_ms': round(avg_latency, 2),
        'error_rate_percent': round(error_rate, 2),
        'daily_limit': key_info['daily_limit'],
        'rate_limit_per_second': key_info['rate_limit']
    }
