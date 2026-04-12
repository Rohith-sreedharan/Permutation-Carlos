#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE='http://localhost:8000'
FRONT='http://localhost:3000'

async def main() -> None:
    email=f'probe_{random.randint(1000,9999)}@x.com'
    password='ProofPass123!'
    requests.post(f'{BASE}/api/auth/register', json={'email': email, 'username': email.split('@')[0], 'password': password}, timeout=10)
    token=requests.post(
        f'{BASE}/api/token',
        headers={'Content-Type':'application/x-www-form-urlencoded'},
        data={'username': email, 'password': password},
        timeout=10,
    ).json().get('access_token')

    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        context=await browser.new_context(viewport={'width':1600,'height':1100})
        page=await context.new_page()
        await page.goto(FRONT)
        await page.evaluate("(tk)=>localStorage.setItem('authToken', tk)", token)
        await page.reload(wait_until='networkidle')
        await page.wait_for_timeout(1800)

        data=await page.evaluate('''() => {
            const out=[];
            const headings=[...document.querySelectorAll('h3')];
            for (const h of headings){
                const txt=(h.textContent||'').trim();
                if (!txt.includes(' @ ')) continue;
                const clickable=h.closest('.cursor-pointer, button, [role="button"], a, div');
                out.push({
                    h3Text: txt,
                    h3Class: String(h.className||''),
                    clickableTag: clickable ? clickable.tagName : null,
                    clickableClass: clickable ? String(clickable.className||'') : null,
                    clickableRole: clickable ? clickable.getAttribute('role') : null,
                    clickableAria: clickable ? clickable.getAttribute('aria-label') : null,
                    clickableOnClick: clickable ? !!clickable.onclick : false,
                });
            }
            return out.slice(0, 30);
        }''')
        print(data)
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
