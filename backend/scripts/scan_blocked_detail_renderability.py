import os
#!/usr/bin/env python3
import asyncio
import random
import requests
from playwright.async_api import async_playwright

BASE = "http://localhost:8000"
FRONT = "http://localhost:3000"


def league_from_sport_key(sport_key: str) -> str | None:
    key = (sport_key or "").lower()
    if "basketball_nba" in key:
        return "NBA"
    if "basketball_ncaab" in key:
        return "NCAAB"
    if "americanfootball_nfl" in key:
        return "NFL"
    if "americanfootball_ncaaf" in key:
        return "NCAAF"
    if "icehockey_nhl" in key:
        return "NHL"
    if "baseball_mlb" in key:
        return "MLB"
    return None


def has_blocked(decisions: dict) -> bool:
    for m in ("spread", "moneyline", "total"):
        d = decisions.get(m) or {}
        if str(d.get("classification", "")).upper() == "BLOCKED":
            return True
    return False


async def main() -> None:
    email = f"scanblk_{random.randint(1000,9999)}@example.com"
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
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(f"{BASE}/api/odds/list?upcoming_only=true&limit=300", timeout=20)
    r.raise_for_status()
    obj = r.json()
    events = obj.get("events", []) if isinstance(obj, dict) else obj

    blocked = []
    for ev in events:
        event_id = ev.get("id") or ev.get("event_id")
        league = league_from_sport_key(ev.get("sport_key", ""))
        if not event_id or not league:
            continue
        d = requests.get(f"{BASE}/api/games/{league}/{event_id}/decisions", headers=headers, timeout=10)
        if d.status_code != 200:
            continue
        if has_blocked(d.json()):
            blocked.append((event_id, ev.get("away_team"), ev.get("home_team")))

    print("blocked_candidates", len(blocked))

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await context.new_page()
        await page.goto(FRONT)
        await page.evaluate("(t)=>localStorage.setItem('authToken',t)", token)

        ok = []
        for event_id, away, home in blocked[:20]:
            try:
                await page.goto(f"{FRONT}/?gameId={event_id}", wait_until="domcontentloaded", timeout=45000)
                await page.wait_for_timeout(2200)
                has_back = await page.locator("text=Back to Dashboard").count() > 0
                has_marker = (
                    await page.locator("text=ANALYSIS BLOCKED").count() > 0
                    or await page.locator("text=BLOCKED").count() > 0
                    or await page.locator("text=MARKET ALIGNED - NO PLAY").count() > 0
                )
                print(event_id[:8], has_back, has_marker, away, "@", home)
                if has_back and has_marker:
                    ok.append((event_id, away, home))
            except Exception as e:
                print(event_id[:8], "ERR", str(e)[:80])

        print("renderable", len(ok))
        for row in ok:
            print("OK", row)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
