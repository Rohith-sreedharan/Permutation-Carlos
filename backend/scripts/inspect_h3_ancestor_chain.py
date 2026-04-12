#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"


async def main() -> None:
    email = f"chain_{random.randint(1000,9999)}@x.com"
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
        await page.wait_for_timeout(1800)

        chain = await page.evaluate(
            """() => {
                const h = [...document.querySelectorAll('h3')].find((x) => (x.textContent || '').includes(' @ '));
                if (!h) return null;
                const result = [];
                let el = h;
                for (let i = 0; i < 10 && el; i++) {
                    result.push({
                        tag: el.tagName,
                        cls: String(el.className || ''),
                        text: (el.textContent || '').trim().slice(0, 120),
                    });
                    el = el.parentElement;
                }
                return result;
            }"""
        )
        print(chain)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
