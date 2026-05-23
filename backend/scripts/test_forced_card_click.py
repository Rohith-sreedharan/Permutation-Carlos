import os
#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"


async def main() -> None:
    email = f"force_{random.randint(1000,9999)}@example.com"
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
        await page.goto(FRONT)
        await page.evaluate("(t)=>localStorage.setItem('authToken',t)", token)
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(1800)

        cards = page.locator("div.cursor-pointer")
        count = await cards.count()
        print("card_count", count)
        if count == 0:
            print("no cards")
            return

        await cards.first.evaluate(
            """(el) => {
                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            }"""
        )

        await page.wait_for_timeout(3500)
        markers = {
            "back": await page.locator("text=Back to Dashboard").count(),
            "share": await page.locator("button:has-text('Share')").count(),
            "game_unavailable": await page.locator("text=Game data unavailable").count(),
            "dashboard_header": await page.locator("text=Sports Intelligence Command Center").count(),
            "search": await page.locator("input[placeholder*='Search']").count(),
        }
        print(markers)
        await page.screenshot(path="proof_batch_screenshots/DEBUG_forced_click.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
