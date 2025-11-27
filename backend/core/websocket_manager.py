"""
WebSocket Connection Manager
Handles persistent connections for real-time updates
Replaces polling with push notifications for:
- Recalculation alerts (line movement, injury updates)
- Community message notifications
- Parlay correlation updates
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Set
import json
import asyncio
from datetime import datetime, timezone


class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts
    """
    
    def __init__(self):
        # Active connections by connection_id
        self.active_connections: Dict[str, WebSocket] = {}
        
        # Subscriptions: user can subscribe to specific channels
        # Format: {"user_123": {"events", "community", "parlay_abc123"}}
        self.subscriptions: Dict[str, Set[str]] = {}
    
    async def connect(self, websocket: WebSocket, connection_id: str):
        """
        Accept new WebSocket connection
        """
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        self.subscriptions[connection_id] = set()
        
        # Send welcome message
        await websocket.send_json({
            "type": "CONNECTED",
            "connection_id": connection_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "WebSocket connected. Subscribe to channels with SUBSCRIBE message."
        })
    
    def disconnect(self, connection_id: str):
        """
        Remove connection and subscriptions
        """
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]
        if connection_id in self.subscriptions:
            del self.subscriptions[connection_id]
    
    async def subscribe(self, connection_id: str, channel: str):
        """
        Subscribe connection to a channel
        Channels:
        - 'events' - All game event updates
        - 'community' - Community message notifications
        - 'parlay_{parlay_id}' - Specific parlay correlation updates
        """
        if connection_id in self.subscriptions:
            self.subscriptions[connection_id].add(channel)
            
            # Acknowledge subscription
            if connection_id in self.active_connections:
                await self.active_connections[connection_id].send_json({
                    "type": "SUBSCRIBED",
                    "channel": channel,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
    
    async def unsubscribe(self, connection_id: str, channel: str):
        """
        Unsubscribe from channel
        """
        if connection_id in self.subscriptions:
            self.subscriptions[connection_id].discard(channel)
            
            if connection_id in self.active_connections:
                await self.active_connections[connection_id].send_json({
                    "type": "UNSUBSCRIBED",
                    "channel": channel,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
    
    async def broadcast_to_channel(self, channel: str, message: dict):
        """
        Send message to all subscribers of a channel
        
        Args:
            channel: Channel name (e.g., 'events', 'community')
            message: Dict with 'type', 'payload', etc.
        """
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Find all connections subscribed to this channel
        for connection_id, channels in self.subscriptions.items():
            if channel in channels:
                if connection_id in self.active_connections:
                    try:
                        await self.active_connections[connection_id].send_json(message)
                    except Exception as e:
                        print(f"Error sending to {connection_id}: {e}")
                        # Connection broken, will be cleaned up on next message
    
    async def send_to_connection(self, connection_id: str, message: dict):
        """
        Send message to specific connection
        """
        if connection_id in self.active_connections:
            try:
                message["timestamp"] = datetime.now(timezone.utc).isoformat()
                await self.active_connections[connection_id].send_json(message)
            except Exception as e:
                print(f"Error sending to {connection_id}: {e}")
    
    async def broadcast_all(self, message: dict):
        """
        Broadcast to all active connections (use sparingly)
        """
        message["timestamp"] = datetime.now(timezone.utc).isoformat()
        
        # Create list to avoid dict size change during iteration
        connections = list(self.active_connections.items())
        
        for connection_id, websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"Error broadcasting to {connection_id}: {e}")
                # Clean up broken connection
                self.disconnect(connection_id)
    
    def get_connection_count(self) -> int:
        """
        Get number of active connections
        """
        return len(self.active_connections)
    
    def get_channel_subscribers(self, channel: str) -> int:
        """
        Count subscribers to a channel
        """
        count = 0
        for channels in self.subscriptions.values():
            if channel in channels:
                count += 1
        return count


# Global singleton instance
manager = ConnectionManager()


# Example usage in routes:
# 
# When line moves:
# await manager.broadcast_to_channel("events", {
#     "type": "LINE_MOVEMENT",
#     "payload": {
#         "event_id": "game_123",
#         "old_spread": -3.5,
#         "new_spread": -4.0,
#         "steam_move": True
#     }
# })
#
# When community message posted:
# await manager.broadcast_to_channel("community", {
#     "type": "NEW_MESSAGE",
#     "payload": {
#         "thread_type": "daily",
#         "user_id": "user_123",
#         "message": "Lakers look good tonight"
#     }
# })
#
# When parlay correlation changes:
# await manager.broadcast_to_channel(f"parlay_{parlay_id}", {
#     "type": "CORRELATION_UPDATE",
#     "payload": {
#         "parlay_id": parlay_id,
#         "new_correlation": 0.73,
#         "new_grade": "HIGH_RISK"
#     }
# })
