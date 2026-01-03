"""
API Routes for Community War Room

Threaded game rooms with market-specific threads.
Access control by subscription tier.
"""
from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect
from typing import Optional, List, Dict
from datetime import datetime, timedelta
from pydantic import BaseModel
import asyncio

from ..middleware.auth import require_user, require_wire_pro
from ..services.community_manager import CommunityManager

router = APIRouter(prefix="/api/community", tags=["community"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateChannelRequest(BaseModel):
    channel_type: str  # GAME_THREAD, MARKET_THREAD, GENERAL
    title: str
    description: Optional[str] = None
    game_id: Optional[str] = None
    market_type: Optional[str] = None  # SPREAD, TOTAL, MONEYLINE
    access_level: str = "FREE"  # FREE, PRO, WIRE_PRO, SHARP_PASS
    parent_channel_id: Optional[str] = None  # For market threads
    ttl_hours: Optional[int] = 48  # Auto-expire after game


class CreatePostRequest(BaseModel):
    channel_id: str
    content: str
    sim_id: Optional[str] = None  # Attach simulation
    parent_post_id: Optional[str] = None  # For replies


class ChannelResponse(BaseModel):
    channel_id: str
    slug: str
    channel_type: str
    title: str
    description: Optional[str]
    
    # Game association
    game_id: Optional[str]
    market_type: Optional[str]
    
    # Access
    access_level: str
    
    # Stats
    post_count: int
    member_count: int
    
    # Timing
    created_at: datetime
    last_activity_at: Optional[datetime]
    expires_at: Optional[datetime]
    
    # Sub-threads (for game channels)
    sub_threads: Optional[List['ChannelResponse']] = []


class PostResponse(BaseModel):
    post_id: str
    channel_id: str
    user_id: str
    user_display_name: str
    
    # Content
    content: str
    
    # Simulation attachment
    sim_id: Optional[str]
    sim_edge_state: Optional[str]
    sim_sharp_side: Optional[str]
    sim_compressed_edge: Optional[float]
    
    # Parent (for replies)
    parent_post_id: Optional[str]
    
    # Reactions
    upvotes: int
    downvotes: int
    
    # Timing
    created_at: datetime
    updated_at: Optional[datetime]


# =============================================================================
# CHANNEL MANAGEMENT
# =============================================================================

@router.post("/channels", response_model=ChannelResponse)
async def create_channel(
    request: CreateChannelRequest,
    user = Depends(require_user)
):
    """
    Create a community channel
    
    Wire Pro users can create game threads automatically
    """
    # Check permissions
    if request.access_level == "WIRE_PRO":
        # Verify user has Wire Pro access
        if not user.wire_pro_access:
            raise HTTPException(status_code=403, detail="Wire Pro access required")
    
    community_manager = CommunityManager()
    
    # Calculate expiration
    expires_at = None
    if request.ttl_hours and request.game_id:
        expires_at = datetime.now() + timedelta(hours=request.ttl_hours)
    
    channel = await community_manager.create_channel(
        channel_type=request.channel_type,
        title=request.title,
        description=request.description,
        game_id=request.game_id,
        market_type=request.market_type,
        access_level=request.access_level,
        parent_channel_id=request.parent_channel_id,
        expires_at=expires_at
    )
    
    return ChannelResponse(**channel)


@router.get("/channels", response_model=List[ChannelResponse])
async def get_channels(
    game_id: Optional[str] = None,
    access_level: Optional[str] = None,
    include_expired: bool = False,
    user = Depends(require_user)
):
    """
    Get community channels
    
    Filters by user's subscription tier
    """
    community_manager = CommunityManager()
    
    # Determine user's max access level
    user_access_levels = ["FREE"]
    if user.subscription_tier in ["STARTER", "PRO", "ELITE"]:
        user_access_levels.append("PRO")
    if user.wire_pro_access:
        user_access_levels.append("WIRE_PRO")
    if user.sharp_pass_status == "APPROVED":
        user_access_levels.append("SHARP_PASS")
    
    channels = await community_manager.get_channels(
        game_id=game_id,
        access_levels=user_access_levels,
        include_expired=include_expired
    )
    
    return [ChannelResponse(**c) for c in channels]


@router.get("/channels/{channel_slug}", response_model=ChannelResponse)
async def get_channel(
    channel_slug: str,
    user = Depends(require_user)
):
    """
    Get channel details by slug
    
    Includes sub-threads for game channels
    """
    community_manager = CommunityManager()
    channel = await community_manager.get_channel_by_slug(channel_slug)
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check access
    if not await community_manager.user_has_access(user.user_id, channel['channel_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get sub-threads if game channel
    sub_threads = []
    if channel['channel_type'] == "GAME_THREAD":
        sub_threads = await community_manager.get_sub_threads(channel['channel_id'])
    
    return ChannelResponse(**channel, sub_threads=[ChannelResponse(**t) for t in sub_threads])


# =============================================================================
# POST MANAGEMENT
# =============================================================================

@router.post("/posts", response_model=PostResponse)
async def create_post(
    request: CreatePostRequest,
    user = Depends(require_user)
):
    """
    Create a post in a channel
    
    Wire Pro users can attach simulations
    """
    community_manager = CommunityManager()
    
    # Check channel access
    if not await community_manager.user_has_access(user.user_id, request.channel_id):
        raise HTTPException(status_code=403, detail="Access denied to this channel")
    
    # Check if attaching simulation (Wire Pro only)
    if request.sim_id:
        if not user.wire_pro_access:
            raise HTTPException(status_code=403, detail="Wire Pro access required to attach simulations")
    
    post = await community_manager.create_post(
        channel_id=request.channel_id,
        user_id=user.user_id,
        content=request.content,
        sim_id=request.sim_id,
        parent_post_id=request.parent_post_id
    )
    
    return PostResponse(**post)


@router.get("/channels/{channel_slug}/posts", response_model=List[PostResponse])
async def get_channel_posts(
    channel_slug: str,
    limit: int = 50,
    offset: int = 0,
    user = Depends(require_user)
):
    """
    Get posts in a channel
    
    Threaded view: top-level posts only, with reply counts
    """
    community_manager = CommunityManager()
    
    # Get channel
    channel = await community_manager.get_channel_by_slug(channel_slug)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Check access
    if not await community_manager.user_has_access(user.user_id, channel['channel_id']):
        raise HTTPException(status_code=403, detail="Access denied")
    
    posts = await community_manager.get_channel_posts(
        channel_id=channel['channel_id'],
        limit=limit,
        offset=offset
    )
    
    return [PostResponse(**p) for p in posts]


@router.post("/posts/{post_id}/react")
async def react_to_post(
    post_id: str,
    reaction: str,  # UPVOTE, DOWNVOTE
    user = Depends(require_user)
):
    """
    React to a post
    """
    community_manager = CommunityManager()
    
    await community_manager.react_to_post(
        post_id=post_id,
        user_id=user.user_id,
        reaction=reaction
    )
    
    return {"success": True}


# =============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# =============================================================================

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, channel_id: str, websocket: WebSocket):
        await websocket.accept()
        if channel_id not in self.active_connections:
            self.active_connections[channel_id] = []
        self.active_connections[channel_id].append(websocket)
    
    def disconnect(self, channel_id: str, websocket: WebSocket):
        if channel_id in self.active_connections:
            self.active_connections[channel_id].remove(websocket)
    
    async def broadcast(self, channel_id: str, message: dict):
        if channel_id in self.active_connections:
            for connection in self.active_connections[channel_id]:
                await connection.send_json(message)


manager = ConnectionManager()


@router.websocket("/ws/{channel_slug}")
async def websocket_endpoint(
    websocket: WebSocket,
    channel_slug: str
):
    """
    WebSocket for real-time channel updates
    
    Client receives:
    - New posts
    - Reactions
    - Signal updates
    """
    # TODO: Authenticate WebSocket connection
    # For now, accepting all connections
    
    community_manager = CommunityManager()
    channel = await community_manager.get_channel_by_slug(channel_slug)
    
    if not channel:
        await websocket.close(code=404)
        return
    
    await manager.connect(channel['channel_id'], websocket)
    
    try:
        while True:
            # Keep connection alive
            data = await websocket.receive_text()
            
            # Echo back (or handle client commands)
            await websocket.send_json({"type": "ping", "data": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(channel['channel_id'], websocket)


# =============================================================================
# WIRE PRO FEATURES
# =============================================================================

@router.post("/wire-pro/post-with-sim", response_model=PostResponse)
async def wire_pro_post_with_simulation(
    channel_slug: str,
    content: str,
    sim_id: str,
    user = Depends(require_wire_pro)
):
    """
    Wire Pro: Post with simulation attachment
    
    Access: Wire Pro users only
    """
    community_manager = CommunityManager()
    
    channel = await community_manager.get_channel_by_slug(channel_slug)
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    post = await community_manager.create_post(
        channel_id=channel['channel_id'],
        user_id=user.user_id,
        content=content,
        sim_id=sim_id
    )
    
    # Broadcast to WebSocket subscribers
    await manager.broadcast(
        channel['channel_id'],
        {
            "type": "new_post",
            "post": PostResponse(**post).dict()
        }
    )
    
    return PostResponse(**post)
