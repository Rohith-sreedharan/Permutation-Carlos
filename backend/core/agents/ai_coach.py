"""
AI Coach (Coordinator Agent)
Central gateway that consumes all agent responses and formats for UI
"""
import asyncio
from typing import Dict, Any, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class AICoach:
    """
    AI Coach - The Coordinator
    - Single unified gateway for frontend
    - Consumes all agent responses
    - Formats clean, non-jargon outputs
    - Publishes to ui.updates topic
    - Agents never communicate with frontend directly
    """
    
    def __init__(self, event_bus):
        self.bus = event_bus
        
    async def start(self):
        """Start coach and subscribe to all agent outputs"""
        await self.bus.subscribe("parlay.responses", self.handle_parlay_response)
        await self.bus.subscribe("risk.responses", self.handle_risk_response)
        await self.bus.subscribe("simulation.responses", self.handle_simulation_response)
        await self.bus.subscribe("market.movements", self.handle_market_response)
        logger.info("🧠 AI Coach started")
        
    async def handle_parlay_response(self, message: Dict[str, Any]):
        """Format parlay analysis for UI"""
        try:
            data = message.get("data", {})
            
            if data.get("type") == "parlay_analysis":
                ui_message = self._format_parlay_analysis(data)
                await self.bus.publish("ui.updates", ui_message)
            elif data.get("type") == "error":
                ui_message = {
                    "type": "error",
                    "message": f"❌ {data.get('error')}",
                    "user_id": data.get("user_id"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await self.bus.publish("ui.updates", ui_message)
                
        except Exception as e:
            logger.error(f"Error handling parlay response: {e}")
            
    async def handle_risk_response(self, message: Dict[str, Any]):
        """Format risk alerts for UI"""
        try:
            data = message.get("data", {})
            response_type = data.get("type")
            
            if response_type == "bet_size_assessment":
                ui_message = self._format_bet_size_alert(data)
                await self.bus.publish("ui.updates", ui_message)
            elif response_type == "parlay_risk_guidance":
                ui_message = self._format_risk_guidance(data)
                await self.bus.publish("ui.updates", ui_message)
            elif response_type == "tilt_warning":
                ui_message = {
                    "type": "alert",
                    "severity": "warning",
                    "message": data.get("alert"),
                    "user_id": data.get("user_id"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await self.bus.publish("ui.updates", ui_message)
                
        except Exception as e:
            logger.error(f"Error handling risk response: {e}")
            
    async def handle_simulation_response(self, message: Dict[str, Any]):
        """Format simulation results for UI"""
        try:
            data = message.get("data", {})
            
            ui_message = {
                "type": "simulation_complete",
                "event_id": data.get("event_id"),
                "summary": self._format_simulation_summary(data),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await self.bus.publish("ui.updates", ui_message)
            
        except Exception as e:
            logger.error(f"Error handling simulation response: {e}")
            
    async def handle_market_response(self, message: Dict[str, Any]):
        """Format market movements for UI"""
        try:
            data = message.get("data", {})
            movement_type = data.get("type")
            
            if movement_type == "line_movement":
                if data.get("is_sharp_money") or data.get("is_steam"):
                    ui_message = {
                        "type": "alert",
                        "severity": "info",
                        "title": "🚨 Sharp Money Detected" if data.get("is_sharp_money") else "⚡ Steam Move",
                        "message": self._format_line_movement(data),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    await self.bus.publish("ui.updates", ui_message)
            elif movement_type == "clv_calculated":
                ui_message = {
                    "type": "clv_update",
                    "user_id": data.get("user_id"),
                    "clv": data.get("clv"),
                    "message": self._format_clv(data),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await self.bus.publish("ui.updates", ui_message)
                
        except Exception as e:
            logger.error(f"Error handling market response: {e}")
            
    def _format_parlay_analysis(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format parlay analysis in clean, user-friendly format"""
        combined_prob = data.get("combined_probability")
        ev = data.get("expected_value")
        risk_score = data.get("risk_score")
        recommendation = data.get("recommendation")
        
        # Create clean summary
        summary = f"This parlay has a {combined_prob}% chance of hitting"
        
        if ev is not None and ev > 5:
            summary += f" with {ev}% positive expected value"
        
        if risk_score in ["HIGH", "EXTREME"]:
            summary += f". ⚠️ Risk level: {risk_score}"
            
        return {
            "type": "parlay_analysis",
            "user_id": data.get("user_id"),
            "summary": summary,
            "combined_probability": combined_prob,
            "expected_value": ev,
            "risk_score": risk_score,
            "recommendation": recommendation,
            "legs": data.get("legs"),
            "correlation_score": data.get("correlation_score"),
            "timestamp": data.get("timestamp")
        }
        
    def _format_bet_size_alert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format bet sizing alert"""
        alert_level = data.get("alert_level") or "SAFE"
        alerts = data.get("alerts", [])
        
        severity_map = {
            "SAFE": "success",
            "WARNING": "warning",
            "DANGER": "error"
        }
        
        return {
            "type": "bet_size_alert",
            "severity": severity_map.get(alert_level, "info"),
            "user_id": data.get("user_id"),
            "alerts": alerts,
            "recommended_size": data.get("recommended_size"),
            "timestamp": data.get("timestamp")
        }
        
    def _format_risk_guidance(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format risk guidance for parlay"""
        guidance = data.get("guidance", {})
        
        return {
            "type": "risk_guidance",
            "user_id": data.get("user_id"),
            "suggested_bet": guidance.get("suggested_bet_amount"),
            "max_bet": guidance.get("max_recommended_amount"),
            "units": guidance.get("suggested_units"),
            "warnings": [guidance.get("variance_warning")] if guidance.get("variance_warning") else [],
            "timestamp": data.get("timestamp")
        }
        
    def _format_simulation_summary(self, data: Dict[str, Any]) -> str:
        """Create human-readable simulation summary"""
        win_probs = data.get("win_probabilities", {})
        iterations = data.get("iterations", 0)
        
        if len(win_probs) == 2:
            teams = list(win_probs.keys())
            probs = list(win_probs.values())
            
            return f"{iterations:,} simulations: {teams[0]} {probs[0]*100:.1f}% | {teams[1]} {probs[1]*100:.1f}%"
            
        return f"Simulation complete ({iterations:,} iterations)"
        
    def _format_line_movement(self, data: Dict[str, Any]) -> str:
        """Format line movement alert"""
        team = data.get("team")
        old_line = data.get("old_line", {})
        new_line = data.get("new_line", {})
        
        old_price = old_line.get("price")
        new_price = new_line.get("price")
        
        return f"{team} moved from {old_price} to {new_price}"
        
    def _format_clv(self, data: Dict[str, Any]) -> str:
        """Format CLV update"""
        clv = data.get("clv")
        
        if clv is not None and clv > 0:
            return f"✅ +{clv} CLV - You beat the closing line!"
        elif clv is not None and clv < 0:
            return f"❌ {clv} CLV - Closing line was better"
        else:
            return "CLV: 0 - You matched the closing line"
