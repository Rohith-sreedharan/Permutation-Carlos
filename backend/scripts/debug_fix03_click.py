import os
#!/usr/bin/env python3
import asyncio
from playwright.async_api import async_playwright
import requests, random

BASE='http://localhost:8000'
FRONT='http://localhost:3000'

async def main():
    email=f'dbg_{random.randint(1000,9999)}@example.com'
    pw='ProofPass123!'
    requests.post(f'{BASE}/api/auth/register',json={'email':email,'username':email.split('@')[0],'password':pw},timeout=10)
    lg=requests.post(f'{BASE}/api/token',headers={'Content-Type':'application/x-www-form-urlencoded'},data={'username':email,'password':pw},timeout=10)
    tok=lg.json().get('access_token')
    print('token', bool(tok))

    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        ctx=await browser.new_context(viewport={'width':1600,'height':1100})
        page=await ctx.new_page()
        await page.goto(FRONT)
        await page.evaluate("(t)=>localStorage.setItem('authToken',t)", tok)
        await page.reload(wait_until='networkidle')
        await page.wait_for_timeout(1500)

        search=page.locator("input[placeholder*='Search']")
        print('search count', await search.count())
        body_text = await page.evaluate("() => document.body.innerText.slice(0, 800)")
        print('body snippet:\n', body_text)
        if await search.count()>0:
            await search.first.fill('Atlanta Hawks')
            await page.wait_for_timeout(1200)

        cards=page.locator('.cursor-pointer')
        print('cards', await cards.count())
        h3=page.locator('h3')
        print('h3 count', await h3.count())
        if await h3.count()>0:
            print('first h3', await h3.first.text_content())

        await page.screenshot(path='proof_batch_screenshots/DEBUG_before_click.png', full_page=True)

        match = page.locator("text=Rutgers Scarlet Knights @ Creighton Bluejays").first
        if await match.count()>0:
            await match.click()
            await page.wait_for_timeout(1800)

        back=page.locator('text=Back to Dashboard')
        print('back count', await back.count())
        blocked=page.locator('text=ANALYSIS BLOCKED')
        print('blocked count', await blocked.count())
        await page.screenshot(path='proof_batch_screenshots/DEBUG_after_click.png', full_page=True)
        await browser.close()

asyncio.run(main())
