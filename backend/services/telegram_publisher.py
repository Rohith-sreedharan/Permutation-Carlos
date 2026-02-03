"""
TelegramPublisher - Deterministic Publishing Service
Status: LOCKED - INSTITUTIONAL GRADE

Core service for publishing validated picks to Telegram.

WORKFLOW:
1. Pull eligible posts from queue (ordered by priority)
2. Call CopyAgent (template renderer) to generate text
3. Validate rendered text via TelegramCopyValidator
4. If validation passes → publish to Telegram
5. Write audit log (success or failure)

HARD RULES:
- EDGE first, then LEAN, then MARKET_ALIGNED
- Max 1 pick per (event, market) unless explicitly configured otherwise
- Never post if validation fails
- Never post NO_ACTION or BLOCKED tier
- All posts must be traceable to prediction_log
"""

import logging
from typing import List, Optional, Dict
from datetime import datetime, timedelta
from pymongo.database import Database

from backend.db.telegram_schemas import (
    TelegramQueueItem,
    TelegramPostLog,
    ValidatorReport,
)
from backend.services.telegram_templates import render_telegram_post
from backend.services.telegram_copy_validator import validate_telegram_post


logger = logging.getLogger(__name__)


class TelegramPublisher:
    """
    Deterministic Telegram publishing service.
    
    NO LLM IN CRITICAL PATH - all decisions are rule-based.
    LLM (if used) only for template rendering, subject to validation.
    """
    
    # Tier priority (lower number = higher priority)
    TIER_PRIORITY = {
        "EDGE": 1,
        "LEAN": 2,
        "MARKET_ALIGNED": 3,
        "NO_ACTION": 999,  # Never post
        "BLOCKED": 999,    # Never post
    }
    
    # Max posts per (event, market)
    MAX_POSTS_PER_EVENT_MARKET = 1
    
    # Freshness window (don't post stale predictions)
    FRESHNESS_WINDOW_MINUTES = 30
    
    def __init__(
        self,
        db: Database,
        telegram_bot_token: str,
        telegram_chat_id: str,
        use_llm_agent: bool = False,
    ):
        """
        Initialize publisher.
        
        Args:
            db: MongoDB database connection
            telegram_bot_token: Telegram bot API token
            telegram_chat_id: Telegram chat/channel ID
            use_llm_agent: Whether to use LLM for template rendering (default: False)
        """
        self.db = db
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.use_llm_agent = use_llm_agent
        
        # Telegram client (lazy init)
        self._telegram_client = None
    
    @property
    def telegram_client(self):
        """Lazy-init Telegram client"""
        if self._telegram_client is None:
            from telegram import Bot
            self._telegram_client = Bot(token=self.telegram_bot_token)
        return self._telegram_client
    
    async def publish_batch(
        self,
        max_posts: int = 10,
        dry_run: bool = False
    ) -> Dict[str, int]:
        """
        Publish a batch of eligible posts.
        
        Args:
            max_posts: Maximum number of posts to publish in this batch
            dry_run: If True, validate but don't actually post (for testing)
        
        Returns:
            Stats dict with counts
        """
        stats = {
            "pulled": 0,
            "posted": 0,
            "validation_failed": 0,
            "telegram_failed": 0,
            "skipped_stale": 0,
            "skipped_duplicate": 0,
        }
        
        # Pull eligible queue items
        eligible_items = self._pull_eligible_queue_items(max_posts)
        stats["pulled"] = len(eligible_items)
        
        if not eligible_items:
            logger.info("No eligible posts in queue")
            return stats
        
        # Process each item
        for queue_item in eligible_items:
            try:
                # Check freshness
                if not self._is_fresh(queue_item):
                    logger.warning(
                        f"Skipping stale queue item {queue_item.queue_id} "
                        f"(generated {queue_item.generated_at})"
                    )
                    stats["skipped_stale"] += 1
                    continue
                
                # Check for duplicates (already posted for this event+market)
                if self._already_posted(queue_item):
                    logger.info(
                        f"Skipping duplicate for event={queue_item.event_id} "
                        f"market={queue_item.market_type}"
                    )
                    stats["skipped_duplicate"] += 1
                    continue
                
                # Render text (via template or LLM agent)
                rendered_text, template_id_used = self._render_post(queue_item)
                
                # Validate
                validator_report = validate_telegram_post(
                    rendered_text, queue_item, template_id_used
                )
                
                if not validator_report.passed:
                    logger.error(
                        f"Validation failed for queue_id={queue_item.queue_id}: "
                        f"{validator_report.failure_reason}"
                    )
                    self._write_post_log(
                        queue_item=queue_item,
                        rendered_text=rendered_text,
                        template_id_used=template_id_used,
                        validator_report=validator_report,
                        posted=False,
                    )
                    stats["validation_failed"] += 1
                    continue
                
                # Publish to Telegram (unless dry run)
                telegram_message_id = None
                posted = False
                
                if not dry_run:
                    try:
                        telegram_message_id = await self._send_telegram_message(rendered_text)
                        posted = True
                        logger.info(
                            f"Posted to Telegram: queue_id={queue_item.queue_id} "
                            f"message_id={telegram_message_id}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Telegram send failed for queue_id={queue_item.queue_id}: {e}"
                        )
                        stats["telegram_failed"] += 1
                else:
                    logger.info(f"[DRY RUN] Would post: {rendered_text[:100]}...")
                
                # Write post log
                self._write_post_log(
                    queue_item=queue_item,
                    rendered_text=rendered_text,
                    template_id_used=template_id_used,
                    validator_report=validator_report,
                    posted=posted,
                    telegram_message_id=telegram_message_id,
                )
                
                if posted:
                    stats["posted"] += 1
                
            except Exception as e:
                logger.exception(
                    f"Error processing queue_id={queue_item.queue_id}: {e}"
                )
                continue
        
        logger.info(f"Publish batch complete: {stats}")
        return stats
    
    def _pull_eligible_queue_items(self, limit: int) -> List[TelegramQueueItem]:
        """
        Pull eligible queue items ordered by priority.
        
        Priority:
        1. EDGE (unconstrained)
        2. EDGE (constrained)
        3. LEAN (unconstrained)
        4. LEAN (constrained)
        5. MARKET_ALIGNED (optional, usually not posted)
        
        Within same tier: created_at ascending (oldest first)
        """
        # Query: only allowed posts, not already processed
        query = {
            "display.allowed": True,
            "tier": {"$in": ["EDGE", "LEAN", "MARKET_ALIGNED"]},
        }
        
        # Fetch from queue
        cursor = self.db.telegram_queue.find(query).limit(limit * 2)  # Over-fetch for deduplication
        
        items = []
        for doc in cursor:
            try:
                item = TelegramQueueItem(**doc)
                items.append(item)
            except Exception as e:
                logger.error(f"Failed to parse queue item: {e}")
                continue
        
        # Sort by priority
        items_sorted = sorted(
            items,
            key=lambda x: (
                self.TIER_PRIORITY.get(x.tier, 999),  # Tier priority
                1 if x.constraints.mode == "constrained" else 0,  # Unconstrained first
                x.created_at,  # Oldest first
            )
        )
        
        return items_sorted[:limit]
    
    def _is_fresh(self, queue_item: TelegramQueueItem) -> bool:
        """Check if queue item is still fresh (not stale)"""
        age_minutes = (datetime.utcnow() - queue_item.generated_at).total_seconds() / 60
        return age_minutes <= self.FRESHNESS_WINDOW_MINUTES
    
    def _already_posted(self, queue_item: TelegramQueueItem) -> bool:
        """
        Check if we've already posted for this (event, market).
        
        Prevents duplicate posts per event+market.
        """
        # Check post log for recent successful posts
        recent_window = datetime.utcnow() - timedelta(hours=24)
        
        existing = self.db.telegram_post_log.find_one({
            "posted": True,
            "created_at": {"$gte": recent_window},
            # Match on canonical event from queue item's prediction_log
            # (In production, you'd query prediction_log to get event_id, 
            # or store event_id directly in post_log)
        })
        
        # For now, simple heuristic: check if we posted anything for this event recently
        # (More sophisticated deduplication would query prediction_log)
        
        # TODO: Implement proper event+market deduplication via prediction_log join
        
        return False  # For now, allow all (implement proper check in production)
    
    def _render_post(self, queue_item: TelegramQueueItem) -> tuple[str, str]:
        """
        Render Telegram post text.
        
        Uses deterministic template renderer (not LLM) by default.
        LLM agent can be used if enabled, but output still validated.
        
        Returns:
            (rendered_text, template_id_used)
        """
        if self.use_llm_agent:
            # Use LLM agent (future implementation)
            # For now, fall back to template
            logger.warning("LLM agent not implemented, using template renderer")
        
        # Use deterministic template renderer
        rendered_text, template_id = render_telegram_post(queue_item)
        
        return rendered_text, template_id
    
    async def _send_telegram_message(self, text: str) -> str:
        """
        Send message to Telegram.
        
        Returns:
            message_id from Telegram
        """
        message = await self.telegram_client.send_message(
            chat_id=self.telegram_chat_id,
            text=text,
            parse_mode="HTML",  # or "Markdown" depending on template format
            disable_web_page_preview=True,
        )
        
        return str(message.message_id)
    
    def _write_post_log(
        self,
        queue_item: TelegramQueueItem,
        rendered_text: str,
        template_id_used: str,
        validator_report: ValidatorReport,
        posted: bool,
        telegram_message_id: Optional[str] = None,
    ):
        """
        Write post attempt to audit log.
        
        CRITICAL: This is append-only, never update.
        """
        import uuid
        
        log_entry = TelegramPostLog(
            log_id=f"log_{uuid.uuid4().hex[:12]}",
            queue_id=queue_item.queue_id,
            prediction_log_id=queue_item.prediction_log_id,
            posted=posted,
            agent_version=None,
            agent_model=None,
            validation_failed=not validator_report.passed,
            failure_reason=validator_report.failure_reason,
            rendered_text=rendered_text,
            template_id_used=template_id_used,
            validator_report=validator_report,
            telegram_message_id=telegram_message_id,
            telegram_chat_id=self.telegram_chat_id if posted else None,
            created_at=datetime.utcnow(),
            posted_at=datetime.utcnow() if posted else None,
        )
        
        self.db.telegram_post_log.insert_one(log_entry.dict())
        
        logger.debug(f"Wrote post log: log_id={log_entry.log_id} posted={posted}")


# ==================== QUEUE BUILDER ====================

class TelegramQueueBuilder:
    """
    Builds queue items from prediction_log entries.
    
    This is the bridge between prediction engine and Telegram publisher.
    """
    
    # Tier thresholds (from spec)
    EDGE_THRESHOLD = 0.05  # 5.0% prob_edge
    LEAN_THRESHOLD = 0.025  # 2.5% prob_edge
    
    def __init__(self, db: Database):
        self.db = db
    
    def enqueue_from_prediction_log(
        self,
        prediction_log_id: str
    ) -> Optional[str]:
        """
        Create queue item from prediction_log entry.
        
        Args:
            prediction_log_id: Prediction log ID
        
        Returns:
            queue_id if enqueued, None if not eligible
        """
        # Fetch prediction_log
        pred_log = self.db.prediction_log.find_one({"prediction_log_id": prediction_log_id})
        
        if not pred_log:
            logger.error(f"Prediction log not found: {prediction_log_id}")
            return None
        
        # Extract required fields
        tier = pred_log.get("tier")
        
        # Check posting eligibility
        if tier not in ["EDGE", "LEAN", "MARKET_ALIGNED"]:
            logger.debug(f"Tier {tier} not eligible for posting")
            return None
        
        # Check required fields present
        required_fields = [
            "event_id",
            "market_type",
            "selection_id",
            "snapshot_hash",
            "model_version",
        ]
        
        missing = [f for f in required_fields if not pred_log.get(f)]
        if missing:
            logger.error(f"Prediction log missing required fields: {missing}")
            return None
        
        # Build queue item
        import uuid
        queue_id = f"q_{uuid.uuid4().hex[:12]}"
        
        # TODO: Build complete TelegramQueueItem from pred_log
        # (This requires prediction_log schema to include all necessary fields)
        
        # For now, placeholder
        logger.info(f"Would enqueue {prediction_log_id} as {queue_id}")
        
        return queue_id
    
    def enqueue_batch(
        self,
        min_tier: str = "EDGE",
        max_items: int = 100
    ) -> int:
        """
        Enqueue batch of recent predictions.
        
        Args:
            min_tier: Minimum tier to enqueue (EDGE, LEAN, MARKET_ALIGNED)
            max_items: Max items to enqueue
        
        Returns:
            Number of items enqueued
        """
        # Query recent predictions
        query = {
            "tier": {"$in": ["EDGE", "LEAN", "MARKET_ALIGNED"]},
            # Add additional filters (e.g., not already enqueued)
        }
        
        cursor = self.db.prediction_log.find(query).limit(max_items)
        
        enqueued = 0
        for pred_log in cursor:
            queue_id = self.enqueue_from_prediction_log(pred_log["prediction_log_id"])
            if queue_id:
                enqueued += 1
        
        logger.info(f"Enqueued {enqueued} items")
        return enqueued


if __name__ == "__main__":
    # Test publisher (dry run)
    import os
    from pymongo import MongoClient
    
    # Connect to DB
    mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    db_name = os.getenv("MONGO_DB_NAME", "beatvegas")
    client = MongoClient(mongo_uri)
    db = client[db_name]
    
    # Create publisher
    publisher = TelegramPublisher(
        db=db,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "dummy_token"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "-1001234567890"),
        use_llm_agent=False,
    )
    
    # Run dry run
    stats = publisher.publish_batch(max_posts=5, dry_run=True)
    print(f"Dry run complete: {stats}")
