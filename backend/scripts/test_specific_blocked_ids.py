import os
#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"
IDS = [
    "4f3f3b8a05f65c9938f8dff1229df5e3",
    "d1686c3ffba608b202d00ecc3756d422",
    "6f4627df908d38c70424ce6896309b37",
    "6f0765b4c7ea31444ec8a23fb86e6648",
    "5f035331e20684a116344413531bab36",
]


async def main() -> None:
    email = f"specblk_{random.randint(1000,9999)}@example.com"
    password = os.getenv("PROOF_PASS", "")
    requests.post(
        f"{BASE}/api/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": password},
        timeout=10,
    )
    login = requests.post(
        f"{BASE}/api/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": email, "password": password},
        timeout=10,
    )
    token = login.json().get("access_token")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await context.new_page()
        await page.goto(FRONT)
        await page.evaluate("(t)=>localStorage.setItem('authToken',t)", token)

        for game_id in IDS:
            try:
                await page.goto(f"{FRONT}/?gameId={game_id}", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2200)
                has_back = await page.locator("text=Back to Dashboard").count() > 0
                markers = {
                    "ANALYSIS BLOCKED": await page.locator("text=ANALYSIS BLOCKED").count() > 0,
                    "BLOCKED": await page.locator("text=BLOCKED").count() > 0,
                    "MARKET ALIGNED - NO PLAY": await page.locator("text=MARKET ALIGNED - NO PLAY").count() > 0,
                    "Game data unavailable": await page.locator("text=Game data unavailable").count() > 0,
                }
                print(game_id[:8], "back", has_back, markers)
            except Exception as e:
                print(game_id[:8], "ERR", str(e)[:120])

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
