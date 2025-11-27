"""
Event Bus for Multi-Agent Communication
Implements both in-memory Observer pattern and Redis pub/sub for agent-to-agent messaging
"""
import json
import asyncio
import redis.asyncio as redis
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class InMemoryEventBus:
    """
    In-Memory Event Bus for Multi-Agent Communication (Observer Pattern)
    
    Topics:
    - simulation.completed: Monte Carlo results ready
    - odds.update: Line movements detected
    - user.bet_attempt: User trying to place bet
    - parlay.request: Parlay correlation analysis needed
    - risk.alert: Risk management warnings
    - market.movement: Sharp money detected
    """
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_log: List[Dict[str, Any]] = []
        self.max_log_size = 1000
        
    def subscribe(self, topic: str, handler: Callable):
        """
        Subscribe to topic with handler function
        Args:
            topic: Event topic (e.g., 'simulation.completed')
            handler: Function to handle messages (can be sync or async)
        """
        self.subscribers[topic].append(handler)
        logger.info(f"📥 {handler.__name__} subscribed to {topic}")
        
    def unsubscribe(self, topic: str, handler: Callable):
        """Remove subscription"""
        if topic in self.subscribers and handler in self.subscribers[topic]:
            self.subscribers[topic].remove(handler)
            logger.info(f"❌ {handler.__name__} unsubscribed from {topic}")
            
    async def publish(self, topic: str, data: Dict[str, Any]):
        """
        Publish event to all subscribers
        Args:
            topic: Event topic
            data: Event payload dict
        """
        message = {
            "topic": topic,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        # Log event
        self.event_log.append(message)
        if len(self.event_log) > self.max_log_size:
            self.event_log = self.event_log[-self.max_log_size:]
        
        logger.debug(f"📤 Published to {topic}: {data.get('type', 'event')}")
        
        # Notify all subscribers
        if topic in self.subscribers:
            for handler in self.subscribers[topic]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(message)
                    else:
                        handler(message)
                except Exception as e:
                    logger.error(f"❌ Handler {handler.__name__} failed on {topic}: {e}")
                    
    def get_event_log(self, topic: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent events, optionally filtered by topic"""
        logs = self.event_log if not topic else [e for e in self.event_log if e["topic"] == topic]
        return logs[-limit:]


# Global in-memory bus instance
in_memory_bus = InMemoryEventBus()


class EventBus:
    """
    Redis-based Event Bus for distributed agent communication
    Topics:
    - parlay.requests: Parlay build requests
    - parlay.responses: Parlay agent responses
    - risk.alerts: Risk management warnings
    - risk.responses: Risk assessment outputs
    - simulation.responses: Monte Carlo results
    - user.activity: User actions/picks
    - market.movements: Line movement alerts
    - ui.updates: Clean outputs for frontend
    - feedback.outcomes: Game results for learning
    """
    
    def __init__(self, redis_url: str = "redis://localhost:6379"):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        self.subscribers: Dict[str, List[Callable]] = {}
        self.running = False
        
    async def connect(self):
        """Establish Redis connection"""
        try:
            self.redis_client = await redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True
            )
            self.pubsub = self.redis_client.pubsub()  # type: ignore
            logger.info(f"✅ Event Bus connected to {self.redis_url}")
        except Exception as e:
            logger.error(f"❌ Event Bus connection failed: {e}")
            raise
            
    async def disconnect(self):
        """Close Redis connection"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Event Bus disconnected")
        
    async def publish(self, topic: str, data: Dict[str, Any]):
        """
        Publish event to topic
        Args:
            topic: Event topic (e.g., 'parlay.responses')
            data: Event payload dict
        """
        if not self.redis_client:
            raise RuntimeError("Event Bus not connected")
            
        message = {
            "topic": topic,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        try:
            await self.redis_client.publish(topic, json.dumps(message))
            logger.debug(f"📤 Published to {topic}: {data.get('type', 'event')}")
        except Exception as e:
            logger.error(f"❌ Publish failed on {topic}: {e}")
            raise
            
    async def subscribe(self, topic: str, handler: Callable):
        """
        Subscribe to topic with handler function
        Args:
            topic: Topic to subscribe to
            handler: Async function to handle messages
        """
        if topic not in self.subscribers:
            self.subscribers[topic] = []
            await self.pubsub.subscribe(topic)  # type: ignore
            logger.info(f"📥 Subscribed to {topic}")
            
        self.subscribers[topic].append(handler)
        
    async def start_listening(self):
        """Start background task to process messages"""
        if not self.pubsub:
            raise RuntimeError("Event Bus not connected")
            
        self.running = True
        logger.info("🎧 Event Bus listening for messages...")
        
        try:
            async for message in self.pubsub.listen():
                if not self.running:
                    break
                    
                if message["type"] == "message":
                    topic = message["channel"]
                    try:
                        payload = json.loads(message["data"])
                        
                        # Route to all handlers for this topic
                        if topic in self.subscribers:
                            for handler in self.subscribers[topic]:
                                try:
                                    await handler(payload)
                                except Exception as e:
                                    logger.error(f"❌ Handler error on {topic}: {e}")
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ Invalid JSON on {topic}: {e}")
        except Exception as e:
            logger.error(f"❌ Event Bus listener error: {e}")
            
    async def stop_listening(self):
        """Stop message processing"""
        self.running = False
        logger.info("Event Bus stopped listening")


# Singleton instance
_bus: Optional[EventBus] = None


async def get_event_bus() -> EventBus:
    """Get or create Event Bus singleton"""
    global _bus
    if _bus is None:
        _bus = EventBus()
        await _bus.connect()
    return _bus


async def shutdown_event_bus():
    """Shutdown Event Bus singleton"""
    global _bus
    if _bus:
        await _bus.stop_listening()
        await _bus.disconnect()
        _bus = None
