import os
#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"


async def main() -> None:
    email = f"click_{random.randint(1000,9999)}@example.com"
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

        cards = page.locator(".cursor-pointer")
        print("cards", await cards.count())
        h3s = page.locator("h3")
        print("h3", await h3s.count())
        titles = [t.strip() for t in await h3s.all_text_contents() if " @ " in (t or "")]
        print("matchups", len(titles))
        matchup = titles[0] if titles else None
        print("first_matchup", matchup)

        if matchup:
            matchup_card = page.locator(".cursor-pointer", has_text=matchup).first
            print("matchup_card_count", await page.locator(".cursor-pointer", has_text=matchup).count())
            if await matchup_card.count() > 0:
                await matchup_card.scroll_into_view_if_needed()
                await matchup_card.evaluate(
                    """(el) => {
                        el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true, view: window }));
                        el.dispatchEvent(new MouseEvent('mouseup', { bubbles: true, cancelable: true, view: window }));
                        el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    }"""
                )
            else:
                await page.locator("h3", has_text=matchup).first.click()
        elif await cards.count() > 0:
            await cards.first.click()

        await page.wait_for_timeout(1600)
        print("back", await page.locator("text=Back to Dashboard").count())
        print("blocked", await page.locator("text=ANALYSIS BLOCKED").count())
        print("unavailable", await page.locator("text=ANALYSIS UNAVAILABLE").count())
        await page.screenshot(path="proof_batch_screenshots/DEBUG_test_detail_click.png", full_page=True)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
