#!/usr/bin/env python3
import asyncio
import random

import requests
from playwright.async_api import async_playwright
from pymongo import MongoClient

BACKEND = "http://localhost:8000"
FRONT = "http://localhost:3000"


def map_league(sport_key: str | None) -> str | None:
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


def make_token() -> str:
    email = f"findblk_{random.randint(10000,99999)}@example.com"
    password = "ProofPass123!"
    r = requests.post(
        f"{BACKEND}/api/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": password},
        timeout=12,
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"register failed: {r.status_code}")
    l = requests.post(
        f"{BACKEND}/api/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": email, "password": password},
        timeout=12,
    )
    if l.status_code != 200:
        raise RuntimeError(f"login failed: {l.status_code}")
    return l.json()["access_token"]


def blocked_candidates(token: str):
    headers = {"Authorization": f"Bearer {token}"}
    db = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)["beatvegas"]
    out = []
    for event in db.events.find({}, {"event_id": 1, "sport_key": 1, "away_team": 1, "home_team": 1}).limit(600):
        league = map_league(event.get("sport_key"))
        if not league:
            continue
        game_id = str(event.get("event_id"))
        if not game_id:
            continue
        try:
            resp = requests.get(f"{BACKEND}/api/games/{league}/{game_id}/decisions", headers=headers, timeout=8)
            if resp.status_code != 200:
                continue
            payload = resp.json()
            classes = [str((payload.get(m) or {}).get("classification", "")).upper() for m in ("spread", "moneyline", "total")]
            if "BLOCKED" in classes:
                out.append((league, game_id, event.get("away_team", "Away"), event.get("home_team", "Home"), classes))
        except Exception:
            continue
    return out


async def main():
    token = make_token()
    cands = blocked_candidates(token)
    print("blocked candidates from decisions:", len(cands))
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await ctx.new_page()
        await page.goto(FRONT, wait_until="domcontentloaded")
        await page.evaluate("(tk) => localStorage.setItem('authToken', tk)", token)

        found = []
        for league, game_id, away, home, classes in cands[:80]:
            await page.goto(f"{FRONT}/?gameId={game_id}", wait_until="domcontentloaded")
            await page.wait_for_timeout(900)
            visible = False
            for tab in ("SPREAD", "MONEYLINE", "TOTAL"):
                btn = page.locator(f"button:has-text('{tab}')").first
                if await btn.count() > 0:
                    await btn.click()
                    await page.wait_for_timeout(250)
                is_blocked = (
                    await page.locator("text=ANALYSIS BLOCKED").count() > 0
                    or await page.locator("text=ANALYSIS UNAVAILABLE").count() > 0
                    or await page.locator("text=market analysis unavailable due to integrity violations").count() > 0
                )
                if is_blocked:
                    visible = True
                    break
            if visible:
                found.append((league, game_id, away, home, classes))
                print("RENDERABLE_BLOCKED", league, game_id, away, "@", home, classes)
            if len(found) >= 5:
                break

        await browser.close()

    print("renderable blocked count found:", len(found))


if __name__ == "__main__":
    asyncio.run(main())
