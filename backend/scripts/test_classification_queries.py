import asyncio
import aiohttp
import json

BASE_URL = "http://localhost:8000"
TOKEN = "user:69cc659e2e46df6f143380eb"

# Event IDs from our scan:
BLOCKED_ID = "7d18651bc9124e2b06c6ffbc3af06ee6"
EDGE_ID = "2ba4ff0cef51aafdf9c5509533b14091"
LEAN_ID = "7bab999d0c94806e44c5de1d60333079"
MARKET_ALIGNED_ID = "cb56684da584f70f8c48dec3ad5bdb7c"

async def check_classification(event_id, label):
    async with aiohttp.ClientSession() as sess:
        try:
            for league in ["NBA", "NHL", "MLB", "NCAAB"]:
                url = f"{BASE_URL}/api/games/{league}/{event_id}/decisions"
                headers = {"Authorization": f"Bearer {TOKEN}"}
                async with sess.get(url, headers=headers) as r:
                    if r.status == 200:
                        data = await r.json()
                        spreads = data.get("spread", [])
                        for s in spreads:
                            print(f"{label}: {league} {event_id} - classification: {s.get('classification')}")
                        return
        except Exception as e:
            print(f"Error checking {label}: {e}")

async def main():
    await asyncio.gather(
        check_classification(BLOCKED_ID, "BLOCKED"),
        check_classification(EDGE_ID, "EDGE"),
        check_classification(LEAN_ID, "LEAN"),
        check_classification(MARKET_ALIGNED_ID, "MARKET_ALIGNED"),
    )

asyncio.run(main())
