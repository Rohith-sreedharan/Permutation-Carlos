#!/usr/bin/env python3
import asyncio
import random

import requests
from playwright.async_api import async_playwright

BACKEND = "http://localhost:8000"
FRONT = "http://localhost:3000"
GAME_ID = "8071f80d106d512c88016b240e766d84"


def make_token() -> str:
    email = f"dbg_{random.randint(10000,99999)}@example.com"
    password = "ProofPass123!"
    r = requests.post(
        f"{BACKEND}/api/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": password},
        timeout=12,
    )
    print("register", r.status_code)
    l = requests.post(
        f"{BACKEND}/api/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": email, "password": password},
        timeout=12,
    )
    print("login", l.status_code)
    return l.json()["access_token"]


async def main() -> None:
    token = make_token()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await context.new_page()
        await page.goto(FRONT, wait_until="domcontentloaded")
        await page.evaluate("(tk) => localStorage.setItem('authToken', tk)", token)
        await page.goto(f"{FRONT}/?gameId={GAME_ID}", wait_until="domcontentloaded")
        await page.wait_for_timeout(2600)

        checks = [
            "Back to Dashboard",
            "ANALYSIS BLOCKED",
            "ANALYSIS UNAVAILABLE",
            "market analysis unavailable due to integrity violations",
            "Key Drivers",
            "EDGE SUMMARY",
            "MARKET ALIGNED - NO PLAY",
            "Baseline Mode",
        ]
        for text in checks:
            count = await page.locator(f"text={text}").count()
            print(f"{text}: {count}")

        await page.screenshot(path="../proof_batch_screenshots/section4_required/DEBUG_blocked_detail_probe.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
