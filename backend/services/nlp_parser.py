"""
Community NLP Parser
LLM-based service to extract structured data from user messages
"""
from datetime import datetime, timezone
from typing import Optional, Dict, Any, Literal
import re
from db.mongo import db
from services.logger import log_stage


class CommunityNLPParser:
    """
    Parse community messages to extract:
    - Intent: pick/news/injury/analysis/chat
    - Entities: teams, players, markets
    - Sentiment: -1 (bearish) to +1 (bullish)
    
    This is the "Pay-to-Influence" data pipeline:
    Pro/Elite users create the raw data that feeds the AI
    """
    
    def __init__(self):
        # Simple keyword-based parser (stub for production LLM)
        # In production: Use OpenAI GPT-4 or Anthropic Claude
        self.intent_keywords = {
            "pick": ["pick", "bet", "tail", "hammer", "lock", "play", "taking"],
            "news": ["injury", "news", "report", "update", "announced"],
            "analysis": ["think", "expect", "should", "will", "analysis", "breakdown"]
        }
        
        # Common team abbreviations (NBA example)
        self.team_mappings = {
            "LAL": "Los Angeles Lakers",
            "LAC": "Los Angeles Clippers",
            "BOS": "Boston Celtics",
            "MIL": "Milwaukee Bucks",
            "GSW": "Golden State Warriors",
            # Add all teams...
        }
    
    def parse_message(self, message_id: str, text: str, user_plan: str, user_elo: Optional[float] = None) -> Dict[str, Any]:
        """
        Parse a community message
        
        Returns structured data:
        - intent: pick/news/injury/analysis/chat
        - entities: {teams: [], players: [], market: str, side: str}
        - sentiment: -1 to +1
        - confidence: 0 to 1
        """
        text_lower = text.lower()
        
        # Step 1: Detect intent
        intent = self._detect_intent(text_lower)
        
        # Step 2: Extract entities
        entities = self._extract_entities(text)
        
        # Step 3: Calculate sentiment
        sentiment = self._calculate_sentiment(text_lower, intent)
        
        # Step 4: Confidence based on user ELO and plan
        confidence = self._calculate_confidence(user_plan, user_elo, intent)
        
        # Update message in database
        db["community_messages"].update_one(
            {"id": message_id},
            {
                "$set": {
                    "parsed_intent": intent,
                    "parsed_entities": entities,
                    "parsed_sentiment": sentiment,
                    "parsed_confidence": confidence,
                    "parsed_at": datetime.now(timezone.utc).isoformat()
                }
            }
        )
        
        # If intent is "pick", create structured pick submission
        if intent == "pick" and entities.get("teams"):
            self._create_pick_submission(message_id, entities, user_elo)
        
        log_stage(
            "nlp_parser",
            "message_parsed",
            input_payload={"message_id": message_id, "text_length": len(text)},
            output_payload={"intent": intent, "sentiment": sentiment, "confidence": confidence}
        )
        
        return {
            "intent": intent,
            "entities": entities,
            "sentiment": sentiment,
            "confidence": confidence
        }
    
    def _detect_intent(self, text_lower: str) -> Literal["pick", "news", "injury", "analysis", "chat"]:
        """Detect message intent from keywords"""
        scores = {intent: 0 for intent in self.intent_keywords}
        
        for intent, keywords in self.intent_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[intent] += 1
        
        # Special case: injury reports
        if "injury" in text_lower or "injured" in text_lower or "out" in text_lower:
            return "injury"
        
        # Return highest scoring intent
        max_intent = max(scores.items(), key=lambda x: x[1])
        if max_intent[1] > 0:
            return max_intent[0]  # type: ignore
        
        return "chat"
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract teams, players, markets from text"""
        entities: Dict[str, Any] = {
            "teams": [],
            "market": None,
            "side": None,
            "stake": None
        }
        
        # Extract teams (look for team abbreviations or full names)
        for abbr, full_name in self.team_mappings.items():
            if abbr in text.upper() or full_name in text:
                entities["teams"].append(full_name)
        
        # Extract market type
        if any(word in text.lower() for word in ["spread", "line", "points"]):
            entities["market"] = "spreads"
        elif any(word in text.lower() for word in ["moneyline", "ml", "win"]):
            entities["market"] = "h2h"
        elif any(word in text.lower() for word in ["total", "over", "under", "o/u"]):
            entities["market"] = "totals"
        
        # Extract stake (e.g., "3u", "5 units")
        stake_match = re.search(r'(\d+)\s*(u|units?)', text.lower())
        if stake_match:
            entities["stake"] = float(stake_match.group(1))
        
        return entities
    
    def _calculate_sentiment(self, text_lower: str, intent: str) -> float:
        """
        Calculate sentiment score -1 to +1
        
        Positive words: lock, hammer, free money, love, smash
        Negative words: fade, avoid, trap, risky, concerned
        """
        positive_words = ["lock", "hammer", "free money", "love", "smash", "confident", "strong", "easy"]
        negative_words = ["fade", "avoid", "trap", "risky", "concerned", "worried", "dangerous", "skip"]
        
        positive_score = sum(1 for word in positive_words if word in text_lower)
        negative_score = sum(1 for word in negative_words if word in text_lower)
        
        # Normalize to -1..+1 range
        total_score = positive_score - negative_score
        if total_score > 0:
            sentiment = min(1.0, total_score / 3.0)  # Cap at 1.0
        else:
            sentiment = max(-1.0, total_score / 3.0)  # Cap at -1.0
        
        return round(sentiment, 2)
    
    def _calculate_confidence(self, user_plan: str, user_elo: Optional[float], intent: str) -> float:
        """
        Calculate parser confidence based on user quality
        
        Elite users with high ELO = higher confidence
        Free users with low ELO = lower confidence
        """
        base_confidence = 0.5
        
        # Plan modifier
        plan_modifiers = {
            "free": -0.2,
            "pro": 0.0,
            "elite": +0.2
        }
        confidence = base_confidence + plan_modifiers.get(user_plan, 0.0)
        
        # ELO modifier (1500 = baseline)
        if user_elo:
            elo_delta = (user_elo - 1500) / 1000  # Normalize around 1500
            confidence += elo_delta * 0.3  # ELO contributes up to ±30%
        
        # Intent modifier (picks are more confident than chat)
        if intent == "pick":
            confidence += 0.1
        elif intent == "chat":
            confidence -= 0.1
        
        return max(0.0, min(1.0, confidence))  # Clamp to 0-1
    
    def _create_pick_submission(self, message_id: str, entities: Dict[str, Any], user_elo: Optional[float]):
        """
        Create structured pick submission for reputation tracking
        """
        # Get original message
        message = db["community_messages"].find_one({"id": message_id})
        if not message:
            return
        
        pick_submission = {
            "submission_id": f"sub_{message_id}",
            "message_id": message_id,
            "user_id": message["user_id"],
            "event_id": None,  # To be matched later
            "market": entities.get("market"),
            "side": entities.get("side"),
            "odds": None,
            "stake_units": entities.get("stake"),
            "outcome": None,
            "submitted_at": message["ts"]
        }
        
        db["community_picks"].insert_one(pick_submission)


# Singleton instance
nlp_parser = CommunityNLPParser()
