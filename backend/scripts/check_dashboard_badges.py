#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"


async def main() -> None:
    email = f"badge_{random.randint(1000,9999)}@example.com"
    password = "ProofPass123!"
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
        await page.goto(FRONT)
        await page.evaluate("(t)=>localStorage.setItem('authToken',t)", token)
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)

        for label in ["BLOCKED", "EDGE", "LEAN", "MARKET ALIGNED"]:
            count = await page.locator(f"text={label}").count()
            print(label, count)

        blocked_cards = page.locator(".cursor-pointer", has_text="BLOCKED")
        print("blocked_cards", await blocked_cards.count())
        if await blocked_cards.count() > 0:
            text = await blocked_cards.first.inner_text()
            print("blocked_first", text[:300].replace("\n", " | "))

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
