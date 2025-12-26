"""
Telegram Bot Service
Handles bot interactions, join requests, and DM delivery
"""
import os
from typing import Optional, Dict, List, cast, Literal
from datetime import datetime, timezone, timedelta
import uuid
import asyncio
from pymongo.database import Database
import aiohttp

from db.schemas.telegram_schemas import (
    TelegramIntegration,
    TelegramMembership,
    TelegramChannel,
    TelegramDeliveryLog,
    AuditEvent,
    COLLECTIONS
)


class TelegramBotService:
    """
    Core Telegram bot integration
    Handles account linking, join request approvals, and message delivery
    """
    
    def __init__(self, db: Database, bot_token: Optional[str] = None):
        self.db = db
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    # ========================================================================
    # ACCOUNT LINKING
    # ========================================================================
    
    async def generate_link_token(self, user_id: str) -> str:
        """
        Generate one-time link token for user
        
        Returns:
            6-character alphanumeric token
        """
        token = str(uuid.uuid4().hex[:6]).upper()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        
        # Store token in integrations collection
        await self.db[COLLECTIONS["telegram_integrations"]].update_one(
            {"user_id": user_id},
            {
                "$set": {
                    "link_token": token,
                    "link_token_expires_at": expires_at
                }
            },
            upsert=True
        )
        
        return token
    
    async def link_telegram_account(
        self,
        link_token: str,
        telegram_user_id: str,
        telegram_username: Optional[str] = None,
        telegram_first_name: Optional[str] = None
    ) -> Optional[TelegramIntegration]:
        """
        Link Telegram account using link token
        
        Returns:
            TelegramIntegration if successful, None if token invalid
        """
        # Find user by link token
        integration_doc = await self.db[COLLECTIONS["telegram_integrations"]].find_one({
            "link_token": link_token,
            "link_token_expires_at": {"$gt": datetime.now(timezone.utc)}
        })
        
        if not integration_doc:
            return None
        
        # Update with Telegram data
        integration = TelegramIntegration(
            user_id=integration_doc["user_id"],
            provider="telegram",
            external_user_id=telegram_user_id,
            telegram_username=telegram_username,
            telegram_first_name=telegram_first_name,
            linked_at=datetime.now(timezone.utc)
        )
        
        await self.db[COLLECTIONS["telegram_integrations"]].update_one(
            {"user_id": integration.user_id},
            {
                "$set": integration.dict(),
                "$unset": {"link_token": "", "link_token_expires_at": ""}
            }
        )
        
        # Audit log
        await self._create_audit_event(
            event_type="telegram_link_completed",
            user_id=integration.user_id,
            payload_snapshot={
                "telegram_user_id": telegram_user_id,
                "telegram_username": telegram_username
            }
        )
        
        return integration
    
    async def get_telegram_integration(self, user_id: str) -> Optional[TelegramIntegration]:
        """Get Telegram integration for user"""
        doc = await self.db[COLLECTIONS["telegram_integrations"]].find_one(
            {"user_id": user_id}
        )
        if not doc:
            return None
        
        # Parse integration
        integration = TelegramIntegration(**doc)
        
        # Only return if properly linked (has external_user_id)
        # Incomplete/legacy integrations are treated as not linked
        if not integration.external_user_id:
            return None
        
        return integration
    
    # ========================================================================
    # CHANNEL MEMBERSHIP MANAGEMENT
    # ========================================================================
    
    async def grant_channel_access(
        self,
        user_id: str,
        channel_name: str
    ) -> bool:
        """
        Grant user access to Telegram channel
        
        Steps:
        1. Get user's Telegram ID
        2. Generate invite link (if needed)
        3. Create membership record
        4. Send DM with invite link
        
        Returns:
            True if successful
        """
        # Get Telegram integration
        integration = await self.get_telegram_integration(user_id)
        if not integration:
            return False
        
        # Get channel config
        channel = await self._get_channel_config(channel_name)
        if not channel:
            return False
        
        # Create membership record
        membership_id = f"mem_{uuid.uuid4().hex[:12]}"
        membership = TelegramMembership(
            membership_id=membership_id,
            telegram_user_id=integration.external_user_id,
            user_id=user_id,
            channel_id=channel.channel_id,
            channel_name=channel_name,
            status="granted",
            granted_at=datetime.now(timezone.utc),
            granted_by="system"
        )
        
        await self.db[COLLECTIONS["telegram_memberships"]].insert_one(
            membership.dict()
        )
        
        # Send DM with invite link
        invite_link = channel.invite_link or await self._generate_invite_link(channel.channel_id)
        
        message = (
            f"🎉 You now have access to {channel_name.upper()} signals!\n\n"
            f"Join here: {invite_link}\n\n"
            f"Note: Join requests are auto-approved for paid members."
        )
        
        await self.send_dm(integration.external_user_id, message)
        
        # Audit log
        await self._create_audit_event(
            event_type="entitlement_granted",
            user_id=user_id,
            payload_snapshot={
                "channel_name": channel_name,
                "telegram_user_id": integration.external_user_id
            }
        )
        
        return True
    
    async def revoke_channel_access(
        self,
        user_id: str,
        channel_name: str,
        reason: str = "subscription_ended"
    ) -> bool:
        """
        Revoke user access to Telegram channel
        
        Steps:
        1. Remove user from channel (via Bot API)
        2. Update membership status
        3. Send notification DM
        
        Returns:
            True if successful
        """
        # Get Telegram integration
        integration = await self.get_telegram_integration(user_id)
        if not integration:
            return False
        
        # Get channel config
        channel = await self._get_channel_config(channel_name)
        if not channel:
            return False
        
        # Remove from Telegram channel
        await self._kick_chat_member(channel.channel_id, integration.external_user_id)
        
        # Update membership record
        await self.db[COLLECTIONS["telegram_memberships"]].update_one(
            {
                "user_id": user_id,
                "channel_name": channel_name,
                "status": "granted"
            },
            {
                "$set": {
                    "status": "revoked",
                    "revoked_at": datetime.now(timezone.utc),
                    "revoke_reason": reason
                }
            }
        )
        
        # Send notification DM
        message = (
            f"⚠️ Your access to {channel_name.upper()} has been paused.\n\n"
            f"Reason: {reason}\n\n"
            f"Visit beatvegas.com/billing to restore access."
        )
        
        await self.send_dm(integration.external_user_id, message)
        
        # Audit log
        await self._create_audit_event(
            event_type="telegram_member_removed",
            user_id=user_id,
            payload_snapshot={
                "channel_name": channel_name,
                "reason": reason
            }
        )
        
        return True
    
    # ========================================================================
    # JOIN REQUEST HANDLING
    # ========================================================================
    
    async def handle_join_request(
        self,
        telegram_user_id: str,
        channel_id: str
    ) -> bool:
        """
        Handle Telegram join request (via webhook)
        
        Logic:
        1. Find user by telegram_user_id
        2. Check entitlements
        3. Approve/deny request
        
        Returns:
            True if approved
        """
        # Find user integration
        integration_doc = await self.db[COLLECTIONS["telegram_integrations"]].find_one({
            "external_user_id": telegram_user_id
        })
        
        if not integration_doc:
            # User not linked to BeatVegas
            await self._deny_join_request(channel_id, telegram_user_id)
            await self._send_link_instructions(telegram_user_id)
            return False
        
        user_id = integration_doc["user_id"]
        
        # Check entitlements
        entitlements_doc = await self.db[COLLECTIONS["user_entitlements"]].find_one({
            "user_id": user_id
        })
        
        if not entitlements_doc or not entitlements_doc.get("telegram_signals", False):
            # No access
            await self._deny_join_request(channel_id, telegram_user_id)
            await self.send_dm(
                telegram_user_id,
                "❌ Access denied: No active Telegram subscription.\n\n"
                "Visit beatvegas.com/billing to subscribe."
            )
            
            # Audit log
            await self._create_audit_event(
                event_type="telegram_join_denied",
                user_id=user_id,
                payload_snapshot={
                    "reason": "no_entitlement",
                    "telegram_user_id": telegram_user_id
                }
            )
            
            return False
        
        # Approve join request
        await self._approve_join_request(channel_id, telegram_user_id)
        
        # Audit log
        await self._create_audit_event(
            event_type="telegram_join_approved",
            user_id=user_id,
            payload_snapshot={
                "telegram_user_id": telegram_user_id,
                "channel_id": channel_id
            }
        )
        
        return True
    
    async def _approve_join_request(self, channel_id: str, telegram_user_id: str):
        """Approve join request via Bot API"""
        url = f"{self.base_url}/approveChatJoinRequest"
        payload = {
            "chat_id": channel_id,
            "user_id": telegram_user_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"Failed to approve join request: {await resp.text()}")
    
    async def _deny_join_request(self, channel_id: str, telegram_user_id: str):
        """Deny join request via Bot API"""
        url = f"{self.base_url}/declineChatJoinRequest"
        payload = {
            "chat_id": channel_id,
            "user_id": telegram_user_id
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status != 200:
                    print(f"Failed to deny join request: {await resp.text()}")
    
    async def _send_link_instructions(self, telegram_user_id: str):
        """Send account linking instructions"""
        message = (
            "👋 Welcome to BeatVegas!\n\n"
            "To join this channel, you need to link your Telegram account:\n\n"
            "1. Go to beatvegas.com/settings/telegram\n"
            "2. Click 'Link Telegram'\n"
            "3. Enter your 6-character code\n"
            "4. Try joining again!\n\n"
            "Questions? DM @BeatVegasSupport"
        )
        
        await self.send_dm(telegram_user_id, message)
    
    # ========================================================================
    # MESSAGE SENDING
    # ========================================================================
    
    async def send_dm(self, telegram_user_id: str, message: str) -> bool:
        """Send direct message to user"""
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": telegram_user_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                return resp.status == 200
    
    async def send_channel_message(
        self,
        channel_id: str,
        message: str,
        signal_id: Optional[str] = None
    ) -> Optional[str]:
        """
        Send message to Telegram channel
        
        Returns:
            Telegram message ID if successful
        """
        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": channel_id,
            "text": message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True
        }
        
        telegram_message_id = None
        status = "failed"
        error_payload = None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        telegram_message_id = str(data["result"]["message_id"])
                        status = "success"
                    else:
                        error_payload = {"status": resp.status, "text": await resp.text()}
        except Exception as e:
            error_payload = {"error": str(e)}
        
        # Log delivery
        if signal_id:
            channel = await self._get_channel_by_id(channel_id)
            channel_name = channel.channel_name if channel else "unknown"
            
            delivery_log = TelegramDeliveryLog(
                delivery_id=f"del_{uuid.uuid4().hex[:12]}",
                signal_id=signal_id,
                channel_id=channel_id,
                channel_name=channel_name,
                telegram_message_id=telegram_message_id,
                status=status,
                error_payload=error_payload,
                message_content=message
            )
            
            await self.db[COLLECTIONS["telegram_delivery_log"]].insert_one(
                delivery_log.dict()
            )
        
        return telegram_message_id
    
    # ========================================================================
    # CHANNEL MANAGEMENT
    # ========================================================================
    
    async def _get_channel_config(self, channel_name: str) -> Optional[TelegramChannel]:
        """Get channel configuration"""
        doc = await self.db[COLLECTIONS["telegram_channels"]].find_one({
            "channel_name": channel_name
        })
        return TelegramChannel(**doc) if doc else None
    
    async def _get_channel_by_id(self, channel_id: str) -> Optional[TelegramChannel]:
        """Get channel by Telegram channel ID"""
        doc = await self.db[COLLECTIONS["telegram_channels"]].find_one({
            "channel_id": channel_id
        })
        return TelegramChannel(**doc) if doc else None
    
    async def _generate_invite_link(self, channel_id: str) -> Optional[str]:
        """Generate invite link for channel"""
        url = f"{self.base_url}/createChatInviteLink"
        payload = {
            "chat_id": channel_id,
            "creates_join_request": True
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["result"]["invite_link"]
        
        return None
    
    async def _kick_chat_member(self, channel_id: str, telegram_user_id: str):
        """Remove user from channel"""
        # Ban user
        url_ban = f"{self.base_url}/banChatMember"
        payload_ban = {
            "chat_id": channel_id,
            "user_id": telegram_user_id
        }
        
        # Unban user (allows them to rejoin later if they resubscribe)
        url_unban = f"{self.base_url}/unbanChatMember"
        payload_unban = {
            "chat_id": channel_id,
            "user_id": telegram_user_id,
            "only_if_banned": True
        }
        
        async with aiohttp.ClientSession() as session:
            await session.post(url_ban, json=payload_ban)
            await asyncio.sleep(1)  # Brief delay
            await session.post(url_unban, json=payload_unban)
    
    # ========================================================================
    # AUDIT LOGGING
    # ========================================================================
    
    async def _create_audit_event(
        self,
        event_type: str,
        user_id: Optional[str] = None,
        signal_id: Optional[str] = None,
        payload_snapshot: Optional[Dict] = None,
        triggered_by: Optional[str] = None
    ):
        """Create audit event"""
        event = AuditEvent(
            event_id=f"aud_{uuid.uuid4().hex[:12]}",
            event_type=cast(Literal['entitlement_granted', 'entitlement_revoked', 'entitlement_denied', 'signal_posted', 'webhook_received', 'telegram_link_completed', 'telegram_join_approved', 'telegram_join_denied', 'telegram_member_removed', 'reconciliation_run'], event_type),
            user_id=user_id,
            signal_id=signal_id,
            payload_snapshot=payload_snapshot or {},
            triggered_by=triggered_by
        )
        
        await self.db[COLLECTIONS["audit_events"]].insert_one(event.dict())
