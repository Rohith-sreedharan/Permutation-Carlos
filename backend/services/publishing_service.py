"""
Prediction Publishing Service
==============================
Manages the publishing workflow for predictions.

CRITICAL PRINCIPLE:
Only published predictions count for public track record.
Separates internal/testing predictions from official recommendations.
"""
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from db.mongo import db
from db.schemas.logging_calibration_schemas import (
    PublishedPrediction,
    Channel,
    Visibility
)
import logging

logger = logging.getLogger(__name__)


class PublishingService:
    """
    Publishes predictions with idempotency and official tracking
    """
    
    def __init__(self):
        self.published_collection = db.published_predictions
        self.predictions_collection = db.predictions
    
    def publish_prediction(
        self,
        prediction_id: str,
        channel: str,
        visibility: str,
        decision_reason_codes: List[str],
        ticket_terms: Dict[str, Any],
        copy_template_id: Optional[str] = None,
        is_official: bool = True
    ) -> str:
        """
        Publish a prediction to a channel
        
        This is the ONLY way predictions enter the public track record.
        
        Args:
            prediction_id: FK to predictions table
            channel: telegram, app, web, internal
            visibility: free, premium, truth, internal
            decision_reason_codes: Machine-readable decision codes
            ticket_terms: {line, price, book, ...}
            copy_template_id: Template used for messaging
            is_official: Whether this counts for grading (default True)
        
        Returns:
            publish_id
        
        Raises:
            ValueError: If prediction_id not found or already published
        """
        # Check if prediction exists
        prediction = self.predictions_collection.find_one(
            {"prediction_id": prediction_id}
        )
        
        if not prediction:
            raise ValueError(f"Prediction {prediction_id} not found")
        
        # Check for duplicate publish (idempotency)
        existing = self.published_collection.find_one({
            "prediction_id": prediction_id,
            "channel": channel,
            "is_official": True
        })
        
        if existing:
            logger.warning(
                f"Prediction {prediction_id} already published to {channel}. "
                f"Returning existing publish_id."
            )
            return existing["publish_id"]
        
        # Create publish record
        publish_id = str(uuid.uuid4())
        
        published = PublishedPrediction(
            publish_id=publish_id,
            prediction_id=prediction_id,
            event_id=prediction["event_id"],
            published_at_utc=datetime.now(timezone.utc),
            channel=Channel(channel),
            visibility=Visibility(visibility),
            copy_template_id=copy_template_id,
            locked_market_snapshot_id=prediction.get("market_snapshot_id", "unknown"),
            locked_engine_version=prediction.get("engine_version", "unknown"),
            locked_model_version=prediction.get("model_version", "unknown"),
            locked_decision_policy_version=prediction.get("decision_policy_version", "1.0"),
            locked_p_calibrated=prediction.get("p_calibrated"),
            locked_market_key=prediction.get("market_key", "unknown"),
            locked_selection=prediction.get("selection", "unknown"),
            decision_reason_codes=decision_reason_codes,
            ticket_terms=ticket_terms,
            is_official=is_official
        )
        
        self.published_collection.insert_one(published.model_dump())
        
        logger.info(
            f"📢 Published prediction: {publish_id} "
            f"(pred={prediction_id}, channel={channel}, vis={visibility})"
        )
        
        return publish_id
    
    def get_published_prediction(
        self,
        publish_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get a published prediction
        """
        return self.published_collection.find_one({"publish_id": publish_id})
    
    def get_published_predictions_for_event(
        self,
        event_id: str,
        is_official: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get all published predictions for an event
        """
        query: Dict[str, Any] = {"event_id": event_id}
        if is_official:
            query["is_official"] = True
        
        return list(self.published_collection.find(query))
    
    def get_recent_published_predictions(
        self,
        visibility: Optional[str] = None,
        channel: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get recent published predictions
        """
        query: Dict[str, Any] = {"is_official": True}
        
        if visibility:
            query["visibility"] = visibility
        
        if channel:
            query["channel"] = channel
        
        return list(
            self.published_collection
            .find(query)
            .sort("published_at_utc", -1)
            .limit(limit)
        )
    
    def void_published_prediction(
        self,
        publish_id: str,
        reason: str
    ) -> bool:
        """
        Void a published prediction (game cancelled, data error, etc.)
        
        This marks it as not official for grading purposes.
        """
        result = self.published_collection.update_one(
            {"publish_id": publish_id},
            {
                "$set": {
                    "is_official": False,
                    "void_reason": reason,
                    "voided_at": datetime.now(timezone.utc)
                }
            }
        )
        
        if result.modified_count > 0:
            logger.warning(f"❌ Voided published prediction: {publish_id} ({reason})")
            return True
        
        return False
    
    def get_publishable_predictions(
        self,
        event_id: Optional[str] = None,
        recommendation_state: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get predictions that are eligible for publishing
        (not yet published, pass RCL gate, etc.)
        """
        query: Dict[str, Any] = {"rcl_gate_pass": True}
        
        if event_id:
            query["event_id"] = event_id
        
        if recommendation_state:
            query["recommendation_state"] = recommendation_state
        
        # Find predictions not yet officially published
        predictions = list(self.predictions_collection.find(query))
        
        # Filter out already published
        publishable = []
        for pred in predictions:
            existing = self.published_collection.find_one({
                "prediction_id": pred["prediction_id"],
                "is_official": True
            })
            
            if not existing:
                publishable.append(pred)
        
        return publishable


# Singleton instance
publishing_service = PublishingService()
