#!/usr/bin/env python3
"""
Capture Section 4 required screenshots from the running local app.

Outputs to proof_batch_screenshots/section4_required:
- 01_FIX03_BLOCKED_DETAIL_VIEW_A.png
- 02_FIX03_BLOCKED_DETAIL_VIEW_B.png
- 03_FIX07_ISSUE09_MARKET_ALIGNED_CARD.png
- 04_FIX07_ISSUE09_BLOCKED_CARD.png
- 05_PARLAY_ARCHITECT_CTA.png
- 06_SIDEBAR_ENTITLEMENT_COPY.png
"""

from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
from playwright.async_api import BrowserContext, Page, async_playwright
from pymongo import MongoClient


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "proof_batch_screenshots" / "section4_required"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FRONTEND_URL = "http://localhost:3000"
BACKEND_URL = "http://localhost:8000"


@dataclass
class EventRef:
    league: str
    game_id: str
    away_team: str
    home_team: str


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


def ensure_auth_token() -> str:
    email = f"prooflive_section4_{random.randint(10000, 99999)}@example.com"
    password = "ProofPass123!"

    reg = requests.post(
        f"{BACKEND_URL}/api/auth/register",
        json={"email": email, "username": email.split("@")[0], "password": password},
        timeout=12,
    )
    if reg.status_code not in (200, 201):
        raise RuntimeError(f"Register failed: {reg.status_code} {reg.text[:180]}")

    login = requests.post(
        f"{BACKEND_URL}/api/token",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"username": email, "password": password},
        timeout=12,
    )
    if login.status_code != 200:
        raise RuntimeError(f"Login failed: {login.status_code} {login.text[:180]}")

    token = login.json().get("access_token")
    if not token:
        raise RuntimeError("No access_token returned from /api/token")
    return token


def find_candidates(token: str) -> dict[str, Any]:
    client = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
    db = client["beatvegas"]

    headers = {"Authorization": f"Bearer {token}"}

    out: dict[str, Any] = {
        "blocked_details": [],
        "market_aligned": None,
        "blocked_card": None,
    }

    # Mirror dashboard top-card selection priority.
    priority = {
        "EDGE": 1,
        "LEAN": 2,
        "MARKET_ALIGNED": 3,
        "BLOCKED": 4,
        "NO_ACTION": 5,
    }

    # Prefer deterministic IDs first (known stable in this repo)
    deterministic = [
        # Verified renderable blocked detail candidates
        EventRef("NBA", "8071f80d106d512c88016b240e766d84", "Phoenix Suns", "Chicago Bulls"),
        EventRef("NBA", "8bce3373da945128589ce3cabae25443", "Charlotte Hornets", "Minnesota Timberwolves"),
        EventRef("NCAAB", "ea153e70b04bef91397d9b8900b00b77", "Oklahoma Sooners", "West Virginia Mountaineers"),
    ]

    for ref in deterministic:
        try:
            response = requests.get(
                f"{BACKEND_URL}/api/games/{ref.league}/{ref.game_id}/decisions",
                headers=headers,
                timeout=8,
            )
            if response.status_code != 200:
                continue
            payload = response.json()
            classes = [
                str((payload.get(market) or {}).get("classification", "")).upper()
                for market in ("spread", "moneyline", "total")
            ]
            if "BLOCKED" in classes and len(out["blocked_details"]) < 2:
                out["blocked_details"].append(ref)
        except Exception:
            continue

    # Scan current DB events and classify using decisions endpoint.
    cursor = db.events.find(
        {},
        {"_id": 1, "event_id": 1, "sport_key": 1, "home_team": 1, "away_team": 1},
    ).limit(450)

    for event in cursor:
        league = map_league(event.get("sport_key"))
        if not league:
            continue

        game_id = str(event.get("event_id") or event.get("_id"))
        ref = EventRef(
            league=league,
            game_id=game_id,
            away_team=str(event.get("away_team") or "Away"),
            home_team=str(event.get("home_team") or "Home"),
        )

        try:
            response = requests.get(
                f"{BACKEND_URL}/api/games/{league}/{game_id}/decisions",
                headers=headers,
                timeout=8,
            )
            if response.status_code != 200:
                continue
            payload = response.json()
        except Exception:
            continue

        classes = []
        for market in ("spread", "moneyline", "total"):
            decision = payload.get(market) or {}
            classes.append(str(decision.get("classification", "")).upper())

        # Determine dashboard top-card classification (same priority behavior as frontend).
        present = [c for c in classes if c in priority]
        top_class = None
        if present:
            top_class = sorted(present, key=lambda c: priority[c])[0]

        if "BLOCKED" in classes:
            if len(out["blocked_details"]) < 2 and not any(x.game_id == ref.game_id for x in out["blocked_details"]):
                out["blocked_details"].append(ref)
            if out["blocked_card"] is None and top_class == "BLOCKED":
                out["blocked_card"] = ref

        if out["market_aligned"] is None and top_class == "MARKET_ALIGNED":
            out["market_aligned"] = ref

        if len(out["blocked_details"]) >= 2 and out["market_aligned"] and out["blocked_card"]:
            break

    # fallback: if no blocked-card-specific candidate, reuse blocked detail candidate
    if out["blocked_card"] is None and out["blocked_details"]:
        out["blocked_card"] = out["blocked_details"][0]

    return out


async def wait_ready(page: Page, path: str = "") -> None:
    await page.goto(f"{FRONTEND_URL}{path}", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(1400)


async def set_auth_local_storage(context: BrowserContext, token: str) -> Page:
    page = await context.new_page()
    await page.goto(FRONTEND_URL, wait_until="domcontentloaded")
    await page.evaluate(
        """(tk) => {
            localStorage.setItem('authToken', tk);
        }""",
        token,
    )
    await page.reload(wait_until="domcontentloaded")
    await page.wait_for_timeout(1200)
    return page


async def capture_blocked_detail(page: Page, ref: EventRef, filename: str) -> bool:
    await wait_ready(page, f"/?gameId={ref.game_id}")

    if await page.locator("text=Back to Dashboard").count() == 0:
        return False

    # Some events are blocked only on specific tabs; cycle tabs to locate a blocked view.
    tab_candidates = ["SPREAD", "MONEYLINE", "TOTAL"]
    blocked_visible = False
    for tab_name in tab_candidates:
        tab = page.locator(f"button:has-text('{tab_name}')").first
        if await tab.count() > 0:
            await tab.click()
            await page.wait_for_timeout(500)

        blocked_visible = (
            await page.locator("text=ANALYSIS BLOCKED").count() > 0
            or await page.locator("text=ANALYSIS UNAVAILABLE").count() > 0
            or await page.locator("text=market analysis unavailable due to integrity violations").count() > 0
        )
        if blocked_visible:
            break

    if not blocked_visible:
        return False

    # Capture the blocked section only, ensuring no analysis content appears above it in-frame.
    blocked_locator = page.locator("text=ANALYSIS BLOCKED").first
    if await blocked_locator.count() == 0:
        blocked_locator = page.locator("text=ANALYSIS UNAVAILABLE").first
    if await blocked_locator.count() == 0:
        blocked_locator = page.locator("text=market analysis unavailable due to integrity violations").first
    if await blocked_locator.count() == 0:
        return False

    await blocked_locator.scroll_into_view_if_needed()
    await page.wait_for_timeout(300)
    box = await blocked_locator.bounding_box()
    if not box:
        return False

    clip_y = max(0, box["y"] - 110)
    clip_h = min(560, 1100 - clip_y)
    clip = {"x": 250, "y": clip_y, "width": 1320, "height": clip_h}
    await page.screenshot(path=str(OUT_DIR / filename), clip=clip)
    return True


async def capture_market_aligned_card(page: Page, ref: EventRef, filename: str) -> bool:
    await wait_ready(page, "")

    search = page.locator("input[placeholder*='Search']")
    if await search.count() > 0:
        # Search by away team keyword to isolate real dashboard card.
        keyword = (ref.away_team.split()[0] if ref.away_team else "").strip()
        await search.first.fill(keyword)
        await page.wait_for_timeout(1400)

    # Must be a real card (not empty state)
    if await page.locator("text=No games found").count() > 0:
        return False

    if await page.locator("text=MARKET ALIGNED").count() == 0:
        return False

    await page.screenshot(path=str(OUT_DIR / filename), full_page=True)
    return True


async def capture_blocked_card(page: Page, ref: EventRef, filename: str) -> bool:
    await wait_ready(page, "")

    search = page.locator("input[placeholder*='Search']")
    if await search.count() > 0:
        keyword = (ref.away_team.split()[0] if ref.away_team else "").strip()
        await search.first.fill(keyword)
        await page.wait_for_timeout(1400)

    # Must be a real card surface, not placeholder.
    if await page.locator("text=No games found").count() > 0:
        return False

    blocked_on_card = (
        await page.locator("text=BLOCKED").count() > 0
        or await page.locator("text=ANALYSIS UNAVAILABLE").count() > 0
    )
    if not blocked_on_card:
        return False

    await page.screenshot(path=str(OUT_DIR / filename), full_page=True)
    return True


async def capture_parlay_cta(page: Page, filename: str) -> bool:
    await wait_ready(page, "")

    parlay_nav = page.locator("text=Parlay Architect").first
    if await parlay_nav.count() == 0:
        return False

    await parlay_nav.click()
    await page.wait_for_timeout(1300)

    exact_cta = page.locator("text=Get Platform Access - $97/month")
    if await exact_cta.count() == 0:
        return False

    await page.screenshot(path=str(OUT_DIR / filename), full_page=True)
    return True


async def capture_sidebar_copy(page: Page, filename: str) -> bool:
    await wait_ready(page, "")

    txt = "Decision Depth: Preview Mode — Upgrade for full access"
    loc = page.locator(f"text={txt}")
    if await loc.count() == 0:
        return False

    await page.screenshot(path=str(OUT_DIR / filename), full_page=True)
    return True


async def run() -> int:
    token = ensure_auth_token()
    candidates = find_candidates(token)

    blocked_refs = candidates.get("blocked_details", [])
    if len(blocked_refs) < 2:
        raise RuntimeError("Unable to find two BLOCKED detail candidates")
    if not candidates.get("market_aligned"):
        raise RuntimeError("Unable to find MARKET_ALIGNED candidate")
    if not candidates.get("blocked_card"):
        raise RuntimeError("Unable to find BLOCKED card candidate")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1600, "height": 1100})
        page = await set_auth_local_storage(context, token)

        captured = 0
        blocked_files = [
            "01_FIX03_BLOCKED_DETAIL_VIEW_A.png",
            "02_FIX03_BLOCKED_DETAIL_VIEW_B.png",
        ]
        for ref in blocked_refs:
            if captured >= 2:
                break
            ok = await capture_blocked_detail(page, ref, blocked_files[captured])
            if ok:
                captured += 1

        if captured < 2:
            raise RuntimeError("Failed to capture two blocked detail screenshots")

        ok = await capture_market_aligned_card(
            page,
            candidates["market_aligned"],
            "03_FIX07_ISSUE09_MARKET_ALIGNED_CARD.png",
        )
        if not ok:
            raise RuntimeError("Failed to capture MARKET_ALIGNED dashboard card screenshot")

        ok = await capture_blocked_card(
            page,
            candidates["blocked_card"],
            "04_FIX07_ISSUE09_BLOCKED_CARD.png",
        )
        if not ok:
            raise RuntimeError("Failed to capture BLOCKED dashboard card screenshot")

        ok = await capture_parlay_cta(page, "05_PARLAY_ARCHITECT_CTA.png")
        if not ok:
            raise RuntimeError("Failed to capture Parlay Architect CTA screenshot")

        ok = await capture_sidebar_copy(page, "06_SIDEBAR_ENTITLEMENT_COPY.png")
        if not ok:
            raise RuntimeError("Failed to capture sidebar entitlement copy screenshot")

        await context.close()
        await browser.close()

    files = sorted(p.name for p in OUT_DIR.glob("*.png"))
    stamp = datetime.utcnow().isoformat() + "Z"
    print(f"Captured {len(files)} files at {stamp}")
    for f in files:
        print(f" - {f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
