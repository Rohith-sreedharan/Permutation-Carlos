import os
#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"
GAME_ID = "4f3f3b8a05f65c9938f8dff1229df5e3"


async def main() -> None:
    email = f"probeblk_{random.randint(1000,9999)}@example.com"
    password = os.getenv("PROOF_PASS", "")
    requests.post(
        f"{BASE}/api/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": password},
        timeout=10,
    )
    token = requests.post(
        f"{BASE}/api/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": email, "password": password},
        timeout=10,
    ).json().get("access_token")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await context.new_page()
        page.on("pageerror", lambda e: print("PAGEERROR", str(e)))
        page.on("console", lambda m: print("CONSOLE", m.type, m.text))
        await page.goto(FRONT)
        await page.evaluate("(t)=>localStorage.setItem('authToken',t)", token)
        await page.goto(f"{FRONT}/?gameId={GAME_ID}", wait_until="networkidle")
        await page.wait_for_timeout(2200)

        back = await page.locator("text=Back to Dashboard").count()
        print("back", back)

        body = await page.evaluate("() => document.body.innerText")
        for key in [
            "ANALYSIS BLOCKED",
            "ANALYSIS UNAVAILABLE",
            "SAFE MODE",
            "market analysis unavailable due to integrity violations",
            "BLOCKED",
            "Model Prob",
            "Market Prob",
        ]:
            print(key, key in body)

        print("BODY_START")
        print(body[:2500])
        print("BODY_END")
        await page.screenshot(path="proof_batch_screenshots/DEBUG_blocked_detail_probe.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
