"""
Agent Orchestrator
Manages agent lifecycle and coordinates the multi-agent system
"""
import asyncio
from typing import Dict, Any, List
import logging

from core.event_bus import get_event_bus, shutdown_event_bus
from core.agents.parlay_agent import ParlayAgent
from core.agents.risk_agent import RiskAgent
from core.agents.market_agent import MarketAgent
from core.agents.user_modeling_agent import UserModelingAgent
from core.agents.event_trigger_agent import EventTriggerAgent
from core.agents.ai_coach import AICoach

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """
    Agent Orchestrator
    - Initializes all agents
    - Manages agent lifecycle
    - Coordinates Event Bus
    - Handles graceful shutdown
    """
    
    def __init__(self, db_client):
        self.db = db_client
        self.bus = None
        self.agents = {}
        self.running = False
        
    async def start(self):
        """Initialize and start all agents"""
        try:
            # Initialize Event Bus
            self.bus = await get_event_bus()
            logger.info("🚀 Starting Agent Orchestrator...")
            
            # Initialize agents
            self.agents = {
                "parlay": ParlayAgent(self.bus),
                "risk": RiskAgent(self.bus, self.db),
                "market": MarketAgent(self.bus, self.db),
                "user_modeling": UserModelingAgent(self.bus, self.db),
                "event_trigger": EventTriggerAgent(self.bus, self.db),
                "ai_coach": AICoach(self.bus)
            }
            
            # Start all agents
            for name, agent in self.agents.items():
                await agent.start()
                logger.info(f"✅ {name.title()} Agent initialized")
                
            # Start Event Bus listener
            self.running = True
            asyncio.create_task(self.bus.start_listening())
            
            logger.info("🎯 Multi-Agent System ONLINE")
            logger.info("📡 Event Bus listening on topics:")
            logger.info("   - parlay.requests / parlay.responses")
            logger.info("   - risk.alerts / risk.responses")
            logger.info("   - simulation.responses")
            logger.info("   - user.activity")
            logger.info("   - market.movements")
            logger.info("   - ui.updates")
            logger.info("   - feedback.outcomes")
            
        except Exception as e:
            logger.error(f"❌ Agent Orchestrator startup failed: {e}")
            raise
            
    async def shutdown(self):
        """Gracefully shutdown all agents"""
        logger.info("🛑 Shutting down Agent Orchestrator...")
        
        self.running = False
        
        # Shutdown Event Bus
        await shutdown_event_bus()
        
        logger.info("✅ Agent Orchestrator shutdown complete")
        
    async def publish_user_activity(self, user_id: str, activity_type: str, data: Dict[str, Any]):
        """
        Convenience method to publish user activity
        Called by API routes when users take actions
        """
        if not self.bus:
            logger.warning("Event Bus not initialized")
            return
            
        message_data = {
            "user_id": user_id,
            "activity_type": activity_type,
            **data
        }
        
        await self.bus.publish("user.activity", message_data)
        
    async def request_parlay_analysis(self, user_id: str, legs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Request parlay analysis from Parlay Agent
        Returns immediately, response comes via ui.updates
        """
        if not self.bus:
            raise RuntimeError("Event Bus not initialized")
            
        await self.bus.publish("parlay.requests", {
            "type": "build",
            "user_id": user_id,
            "legs": legs
        })
        
        return {"status": "processing", "message": "Parlay analysis in progress"}
        
    async def check_bet_size(self, user_id: str, amount: float, bet_data: Dict[str, Any]):
        """
        Request bet size validation from Risk Agent
        """
        if not self.bus:
            raise RuntimeError("Event Bus not initialized")
            
        await self.bus.publish("risk.alerts", {
            "type": "bet_size_check",
            "user_id": user_id,
            "amount": amount,
            **bet_data
        })
        
    async def record_pick_outcome(self, user_id: str, pick_id: str, outcome: str):
        """
        Record pick outcome for feedback loop
        Triggers behavioral learning
        """
        if not self.bus:
            raise RuntimeError("Event Bus not initialized")
            
        await self.bus.publish("feedback.outcomes", {
            "user_id": user_id,
            "pick_id": pick_id,
            "outcome": outcome
        })


# Global orchestrator instance
_orchestrator = None


async def get_orchestrator(db_client) -> AgentOrchestrator:
    """Get or create orchestrator singleton"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator(db_client)
        await _orchestrator.start()
    return _orchestrator


async def shutdown_orchestrator():
    """Shutdown orchestrator singleton"""
    global _orchestrator
    if _orchestrator:
        await _orchestrator.shutdown()
        _orchestrator = None
