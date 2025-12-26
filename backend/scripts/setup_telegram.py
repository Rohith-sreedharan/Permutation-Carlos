"""
Setup Telegram Channel Configurations
Run this once to seed Telegram channel data
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

from backend.db.schemas.telegram_schemas import TelegramChannel, COLLECTIONS


async def seed_telegram_channels():
    """Seed Telegram channel configurations"""
    
    # Connect to MongoDB
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "beatvegas")
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[database_name]
    
    print("Seeding Telegram channel configurations...")
    
    # Channel configurations
    channels = [
        TelegramChannel(
            channel_id=os.getenv("TELEGRAM_SIGNALS_CHANNEL_ID", "-1001234567890"),
            channel_name="signals",
            channel_type="private_signals",
            requires_entitlement=True,
            entitlement_field="telegram_signals",
            bot_is_admin=True,
            join_requests_enabled=True,
            invite_link=None  # Will be generated dynamically
        ),
        TelegramChannel(
            channel_id=os.getenv("TELEGRAM_PREMIUM_CHANNEL_ID", "-1009876543210"),
            channel_name="premium",
            channel_type="private_premium",
            requires_entitlement=True,
            entitlement_field="telegram_premium",
            bot_is_admin=True,
            join_requests_enabled=True,
            invite_link=None
        ),
        TelegramChannel(
            channel_id=os.getenv("TELEGRAM_PUBLIC_CHANNEL_ID", "@BeatVegasPublic"),
            channel_name="public",
            channel_type="public",
            requires_entitlement=False,
            entitlement_field=None,
            bot_is_admin=False,
            join_requests_enabled=False,
            invite_link="https://t.me/BeatVegasPublic"
        )
    ]
    
    # Upsert channels
    for channel in channels:
        await db[COLLECTIONS["telegram_channels"]].update_one(
            {"channel_name": channel.channel_name},
            {"$set": channel.dict()},
            upsert=True
        )
        print(f"  ✓ Seeded channel: {channel.channel_name} ({channel.channel_type})")
    
    print("\n✅ Telegram channels configured successfully!")
    print("\nNext steps:")
    print("1. Create private Telegram channels")
    print("2. Add bot as admin with 'Invite Users' permission")
    print("3. Enable 'Join Requests' in channel settings")
    print("4. Update .env with channel IDs (negative numbers)")
    print("5. Run setup_telegram_indexes.py to create database indexes")
    
    client.close()


async def setup_telegram_indexes():
    """Create database indexes for Telegram collections"""
    
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    database_name = os.getenv("DATABASE_NAME", "beatvegas")
    
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[database_name]
    
    print("Creating Telegram database indexes...")
    
    # telegram_integrations
    await db[COLLECTIONS["telegram_integrations"]].create_index("user_id", unique=True)
    await db[COLLECTIONS["telegram_integrations"]].create_index("external_user_id", unique=True)
    await db[COLLECTIONS["telegram_integrations"]].create_index("link_token")
    print("  ✓ telegram_integrations indexes")
    
    # user_entitlements
    await db[COLLECTIONS["user_entitlements"]].create_index("user_id", unique=True)
    await db[COLLECTIONS["user_entitlements"]].create_index("telegram_signals")
    print("  ✓ user_entitlements indexes")
    
    # telegram_memberships
    await db[COLLECTIONS["telegram_memberships"]].create_index([
        ("user_id", 1),
        ("channel_name", 1)
    ])
    await db[COLLECTIONS["telegram_memberships"]].create_index("telegram_user_id")
    await db[COLLECTIONS["telegram_memberships"]].create_index("status")
    print("  ✓ telegram_memberships indexes")
    
    # telegram_subscriptions
    await db[COLLECTIONS["telegram_subscriptions"]].create_index("user_id")
    await db[COLLECTIONS["telegram_subscriptions"]].create_index("stripe_subscription_id", unique=True)
    await db[COLLECTIONS["telegram_subscriptions"]].create_index("status")
    print("  ✓ telegram_subscriptions indexes")
    
    # signals
    await db[COLLECTIONS["signals"]].create_index("signal_id", unique=True)
    await db[COLLECTIONS["signals"]].create_index("game_id")
    await db[COLLECTIONS["signals"]].create_index("state")
    await db[COLLECTIONS["signals"]].create_index("created_at")
    await db[COLLECTIONS["signals"]].create_index([
        ("state", 1),
        ("created_at", -1)
    ])
    print("  ✓ signals indexes")
    
    # telegram_delivery_log
    await db[COLLECTIONS["telegram_delivery_log"]].create_index("signal_id")
    await db[COLLECTIONS["telegram_delivery_log"]].create_index("channel_id")
    await db[COLLECTIONS["telegram_delivery_log"]].create_index("posted_at")
    print("  ✓ telegram_delivery_log indexes")
    
    # access_change_events
    await db[COLLECTIONS["access_change_events"]].create_index([
        ("user_id", 1),
        ("created_at", -1)
    ])
    await db[COLLECTIONS["access_change_events"]].create_index("is_read")
    print("  ✓ access_change_events indexes")
    
    # audit_events
    await db[COLLECTIONS["audit_events"]].create_index("event_type")
    await db[COLLECTIONS["audit_events"]].create_index("timestamp")
    await db[COLLECTIONS["audit_events"]].create_index("user_id")
    print("  ✓ audit_events indexes")
    
    print("\n✅ Database indexes created successfully!")
    
    client.close()


async def verify_telegram_setup():
    """Verify Telegram bot setup and channel access"""
    import aiohttp
    
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN not set in .env")
        return
    
    print("Verifying Telegram bot setup...")
    
    # Check bot info
    url = f"https://api.telegram.org/bot{bot_token}/getMe"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                bot_info = data["result"]
                print(f"  ✓ Bot: @{bot_info['username']} ({bot_info['first_name']})")
            else:
                print(f"  ❌ Failed to get bot info: {await resp.text()}")
                return
    
    # Check webhook
    url = f"https://api.telegram.org/bot{bot_token}/getWebhookInfo"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                webhook = data["result"]
                
                if webhook.get("url"):
                    print(f"  ✓ Webhook: {webhook['url']}")
                    if webhook.get("pending_update_count", 0) > 0:
                        print(f"  ⚠️  Pending updates: {webhook['pending_update_count']}")
                else:
                    print("  ⚠️  No webhook configured")
                    print("     Set webhook: POST https://api.telegram.org/bot{TOKEN}/setWebhook")
    
    print("\n✅ Telegram bot verified!")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python setup_telegram.py seed     # Seed channel configs")
        print("  python setup_telegram.py indexes  # Create database indexes")
        print("  python setup_telegram.py verify   # Verify bot setup")
        print("  python setup_telegram.py all      # Run all setup tasks")
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "seed":
        asyncio.run(seed_telegram_channels())
    elif command == "indexes":
        asyncio.run(setup_telegram_indexes())
    elif command == "verify":
        asyncio.run(verify_telegram_setup())
    elif command == "all":
        asyncio.run(seed_telegram_channels())
        asyncio.run(setup_telegram_indexes())
        asyncio.run(verify_telegram_setup())
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)
