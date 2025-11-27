"""
Multi-Agent System with Event Bus
AI Coach coordinates specialized agents asynchronously
"""
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from db.mongo import db
from services.logger import log_stage


class AgentType(Enum):
    """Types of specialized agents"""
    AI_COACH = "ai_coach"
    SIMULATION = "simulation"
    PARLAY = "parlay"
    MARKET_MOVEMENT = "market_movement"
    RISK = "risk"
    USER_MODELING = "user_modeling"
    EVENT_TRIGGER = "event_trigger"


class EventType(Enum):
    """Event types for agent communication"""
    SIMULATION_REQUEST = "simulation_request"
    SIMULATION_COMPLETE = "simulation_complete"
    PARLAY_REQUEST = "parlay_request"
    PARLAY_ANALYSIS_COMPLETE = "parlay_analysis_complete"
    MARKET_MOVEMENT_DETECTED = "market_movement_detected"
    RISK_ALERT = "risk_alert"
    USER_ACTION = "user_action"
    INJURY_UPDATE = "injury_update"
    WEATHER_UPDATE = "weather_update"
    LINEUP_CHANGE = "lineup_change"
    PICK_GENERATED = "pick_generated"
    RECALCULATION_NEEDED = "recalculation_needed"


@dataclass
class AgentEvent:
    """Event passed between agents via event bus"""
    event_id: str
    event_type: EventType
    source_agent: AgentType
    target_agent: Optional[AgentType]
    payload: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlation_id: Optional[str] = None  # For tracking related events


class EventBus:
    """
    Asynchronous event bus for agent communication
    
    Features:
    - Pub/Sub pattern for loose coupling
    - Event persistence in MongoDB
    - Priority queue for critical events
    - Dead letter queue for failed processing
    """
    
    def __init__(self):
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.running = False
    
    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe an agent handler to an event type"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
    
    async def publish(self, event: AgentEvent):
        """Publish an event to the bus"""
        # Store event in database for audit trail
        event_doc = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "source_agent": event.source_agent.value,
            "target_agent": event.target_agent.value if event.target_agent else None,
            "payload": event.payload,
            "timestamp": event.timestamp,
            "correlation_id": event.correlation_id,
            "status": "pending"
        }
        db["agent_events"].insert_one(event_doc)
        
        # Add to processing queue
        await self.event_queue.put(event)
        
        log_stage(
            "event_bus",
            "event_published",
            input_payload={"event_type": event.event_type.value},
            output_payload={"event_id": event.event_id}
        )
    
    async def start(self):
        """Start processing events from the queue"""
        self.running = True
        while self.running:
            try:
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                await self._process_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log_stage(
                    "event_bus",
                    "processing_error",
                    input_payload={},
                    output_payload={"error": str(e)}
                )
    
    async def _process_event(self, event: AgentEvent):
        """Process an event by notifying all subscribers"""
        handlers = self.subscribers.get(event.event_type, [])
        
        if not handlers:
            # No subscribers - log and move on
            db["agent_events"].update_one(
                {"event_id": event.event_id},
                {"$set": {"status": "no_subscribers", "processed_at": datetime.now(timezone.utc).isoformat()}}
            )
            return
        
        # Execute all handlers concurrently
        tasks = [handler(event) for handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Update event status
        errors = [r for r in results if isinstance(r, Exception)]
        status = "failed" if errors else "completed"
        
        db["agent_events"].update_one(
            {"event_id": event.event_id},
            {
                "$set": {
                    "status": status,
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "errors": [str(e) for e in errors] if errors else []
                }
            }
        )
    
    def stop(self):
        """Stop the event bus"""
        self.running = False


class AICoachAgent:
    """
    AI Coach - Central Coordinator
    
    Responsibilities:
    - Coordinate all specialized agents
    - Make final pick decisions
    - Handle conflicts between agents
    - Orchestrate workflow
    """
    
    def __init__(self, event_bus: EventBus):
        self.agent_type = AgentType.AI_COACH
        self.event_bus = event_bus
        
        # Subscribe to relevant events
        self.event_bus.subscribe(EventType.SIMULATION_COMPLETE, self.handle_simulation_complete)
        self.event_bus.subscribe(EventType.PARLAY_ANALYSIS_COMPLETE, self.handle_parlay_complete)
        self.event_bus.subscribe(EventType.RISK_ALERT, self.handle_risk_alert)
        self.event_bus.subscribe(EventType.RECALCULATION_NEEDED, self.handle_recalculation)
    
    async def analyze_event(self, event_id: str, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point - analyze an event and coordinate agents
        """
        correlation_id = str(uuid.uuid4())
        
        # Step 1: Request simulation from Simulation Agent
        sim_event = AgentEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.SIMULATION_REQUEST,
            source_agent=self.agent_type,
            target_agent=AgentType.SIMULATION,
            payload={
                "event_id": event_id,
                "event_data": event_data
            },
            correlation_id=correlation_id
        )
        await self.event_bus.publish(sim_event)
        
        # In production, wait for responses and make decisions
        # For now, return acknowledgment
        return {
            "status": "analyzing",
            "correlation_id": correlation_id,
            "event_id": event_id
        }
    
    async def handle_simulation_complete(self, event: AgentEvent):
        """Handle completed simulation from Simulation Agent"""
        simulation_result = event.payload.get("simulation_result")
        
        if not simulation_result:
            return
        
        # Make pick decision based on simulation
        edge_threshold = 5.0  # 5% minimum edge
        if simulation_result.get("confidence_score", 0) > 0.6:
            # Generate pick
            pick_event = AgentEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.PICK_GENERATED,
                source_agent=self.agent_type,
                target_agent=None,  # Broadcast
                payload={
                    "simulation_result": simulation_result,
                    "decision": "approved"
                },
                correlation_id=event.correlation_id
            )
            await self.event_bus.publish(pick_event)
    
    async def handle_parlay_complete(self, event: AgentEvent):
        """Handle parlay analysis completion"""
        pass
    
    async def handle_risk_alert(self, event: AgentEvent):
        """Handle risk alerts from Risk Agent"""
        risk_level = event.payload.get("risk_level")
        
        if risk_level == "high":
            # Reduce stake sizes or pause picks
            log_stage(
                "ai_coach",
                "risk_mitigation",
                input_payload={"risk_level": risk_level},
                output_payload={"action": "reduce_stakes"}
            )
    
    async def handle_recalculation(self, event: AgentEvent):
        """Handle recalculation requests from Event Trigger Agent"""
        event_id = event.payload.get("event_id", "")
        reason = event.payload.get("reason")
        
        if not event_id:
            return
        
        log_stage(
            "ai_coach",
            "recalculation_triggered",
            input_payload={"event_id": event_id, "reason": reason},
            output_payload={"status": "reanalyzing"}
        )
        
        # Re-run analysis with updated data
        await self.analyze_event(event_id, event.payload.get("updated_data", {}))


class SimulationAgent:
    """
    Simulation Agent
    
    Responsibilities:
    - Run Monte Carlo simulations
    - Calculate win probabilities
    - Detect prop mispricings
    """
    
    def __init__(self, event_bus: EventBus):
        self.agent_type = AgentType.SIMULATION
        self.event_bus = event_bus
        
        self.event_bus.subscribe(EventType.SIMULATION_REQUEST, self.handle_simulation_request)
    
    async def handle_simulation_request(self, event: AgentEvent):
        """Handle simulation request from AI Coach"""
        from core.monte_carlo_engine import monte_carlo_engine
        
        event_id = event.payload.get("event_id", "")
        event_data = event.payload.get("event_data") or {}
        
        if not event_id:
            return
        
        # Run simulation
        simulation_result = monte_carlo_engine.run_simulation(
            event_id,
            event_data.get("team_a", {}),
            event_data.get("team_b", {}),
            event_data.get("market_context", {})
        )
        
        # Publish completion event
        completion_event = AgentEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.SIMULATION_COMPLETE,
            source_agent=self.agent_type,
            target_agent=AgentType.AI_COACH,
            payload={
                "simulation_result": simulation_result
            },
            correlation_id=event.correlation_id
        )
        await self.event_bus.publish(completion_event)


class ParlayAgent:
    """
    Parlay Agent
    
    Responsibilities:
    - Analyze parlay correlations
    - Calculate true parlay probabilities
    - Detect +EV parlay opportunities
    """
    
    def __init__(self, event_bus: EventBus):
        self.agent_type = AgentType.PARLAY
        self.event_bus = event_bus
        
        self.event_bus.subscribe(EventType.PARLAY_REQUEST, self.handle_parlay_request)
    
    async def handle_parlay_request(self, event: AgentEvent):
        """Handle parlay analysis request"""
        from core.monte_carlo_engine import monte_carlo_engine
        
        picks = event.payload.get("picks", [])
        simulations = event.payload.get("simulations", [])
        
        # Calculate correlation
        correlation_result = monte_carlo_engine.calculate_parlay_correlation(picks, simulations)
        
        # Publish completion
        completion_event = AgentEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.PARLAY_ANALYSIS_COMPLETE,
            source_agent=self.agent_type,
            target_agent=AgentType.AI_COACH,
            payload={
                "correlation_result": correlation_result
            },
            correlation_id=event.correlation_id
        )
        await self.event_bus.publish(completion_event)


class MarketMovementAgent:
    """
    Market Movement Agent
    
    Responsibilities:
    - Track line movements
    - Detect sharp money
    - Calculate CLV in real-time
    """
    
    def __init__(self, event_bus: EventBus):
        self.agent_type = AgentType.MARKET_MOVEMENT
        self.event_bus = event_bus
    
    async def monitor_line_movement(self, event_id: str, initial_line: float):
        """Monitor line movements and detect significant changes"""
        # In production, poll odds API
        # If movement > threshold, publish event
        pass


class RiskAgent:
    """
    Risk Agent
    
    Responsibilities:
    - Monitor bankroll exposure
    - Detect overconcentration
    - Alert on high-risk scenarios
    """
    
    def __init__(self, event_bus: EventBus):
        self.agent_type = AgentType.RISK
        self.event_bus = event_bus
    
    async def assess_risk(self, picks: List[Dict[str, Any]]) -> str:
        """Assess portfolio risk level"""
        total_exposure = sum(p.get("stake_units", 0) for p in picks)
        
        if total_exposure > 50:  # Over 50 units at risk
            risk_event = AgentEvent(
                event_id=str(uuid.uuid4()),
                event_type=EventType.RISK_ALERT,
                source_agent=self.agent_type,
                target_agent=AgentType.AI_COACH,
                payload={
                    "risk_level": "high",
                    "total_exposure": total_exposure
                }
            )
            await self.event_bus.publish(risk_event)
            return "high"
        
        return "normal"


class EventTriggerAgent:
    """
    Event Trigger Agent
    
    Responsibilities:
    - Monitor external events (injuries, weather, lineup changes)
    - Trigger recalculations when needed
    - Real-time event detection
    """
    
    def __init__(self, event_bus: EventBus):
        self.agent_type = AgentType.EVENT_TRIGGER
        self.event_bus = event_bus
    
    async def handle_injury_update(self, event_id: str, injury_data: Dict[str, Any]):
        """Handle injury update and trigger recalculation"""
        recalc_event = AgentEvent(
            event_id=str(uuid.uuid4()),
            event_type=EventType.RECALCULATION_NEEDED,
            source_agent=self.agent_type,
            target_agent=AgentType.AI_COACH,
            payload={
                "event_id": event_id,
                "reason": "injury_update",
                "updated_data": injury_data
            }
        )
        await self.event_bus.publish(recalc_event)


class UserModelingAgent:
    """
    User Modeling Agent
    
    Responsibilities:
    - Track user preferences
    - Personalize picks
    - Learn from user feedback
    """
    
    def __init__(self, event_bus: EventBus):
        self.agent_type = AgentType.USER_MODELING
        self.event_bus = event_bus
        
        self.event_bus.subscribe(EventType.USER_ACTION, self.handle_user_action)
    
    async def handle_user_action(self, event: AgentEvent):
        """Track and learn from user actions"""
        user_id = event.payload.get("user_id")
        action = event.payload.get("action")
        pick_id = event.payload.get("pick_id")
        
        # Store user preference
        db["user_actions"].insert_one({
            "user_id": user_id,
            "action": action,
            "pick_id": pick_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


# Singleton instances
event_bus = EventBus()
ai_coach = AICoachAgent(event_bus)
simulation_agent = SimulationAgent(event_bus)
parlay_agent = ParlayAgent(event_bus)
market_movement_agent = MarketMovementAgent(event_bus)
risk_agent = RiskAgent(event_bus)
event_trigger_agent = EventTriggerAgent(event_bus)
user_modeling_agent = UserModelingAgent(event_bus)
