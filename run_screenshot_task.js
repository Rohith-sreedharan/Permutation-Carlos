import { chromium } from 'playwright';
import fs from 'fs';
import path from 'path';

(async () => {
    const browser = await chromium.launch({ headless: true });
    const context = await browser.newContext({
        viewport: { width: 390, height: 844 },
        deviceScaleFactor: 1,
    });
    const page = await context.newPage();

    // Set localStorage auth token
    await page.addInitScript(() => {
        window.localStorage.setItem('auth_token', 'mock-token');
    });

    // Mock API calls
    await page.route('**/api/account/profile', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ id: 1, email: 'test@example.com', username: 'testuser' })
    }));

    await page.route('**/api/subscription/status', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ active: true, plan: 'premium' })
    }));

    await page.route('**/api/odds/list', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
            { id: 'game-1', home_team: 'Team A', away_team: 'Team B', league: 'League 1', start_time: new Date().toISOString() },
            { id: 'game-2', home_team: 'Team C', away_team: 'Team D', league: 'League 2', start_time: new Date().toISOString() }
        ])
    }));

    await page.route('**/api/core/predictions', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
             { game_id: 'game-1', signal: 'No Actionable Signal', confidence: 0.5 },
             { game_id: 'game-2', signal: 'Analysis Blocked', confidence: 0 }
        ])
    }));

    await page.route('**/api/analytics/confidence-tooltip', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ text: 'Mock confidence info' })
    }));

    await page.route('**/api/simulations/no-action-game', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            game_id: 'game-1',
            edge_classification: 'No Actionable Signal',
            analysis: 'Some analysis that leads to no signal'
        })
    }));

    await page.route('**/api/simulations/blocked-game', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
            game_id: 'game-2',
            edge_classification: 'ANALYSIS BLOCKED',
            analysis: null
        })
    }));

    await page.route('**/*period/1H*', route => route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: '1H data' })
    }));

    console.log('Opening Dashboard...');
    try {
        await page.goto('http://127.0.0.1:4173', { timeout: 10000 });
        await page.waitForLoadState('networkidle');
        await page.screenshot({ path: 'proof_batch_screenshots/mobile-dashboard-390-final.png' });
        console.log('Saved: proof_batch_screenshots/mobile-dashboard-390-final.png');
    } catch (e) { console.error('Dashboard Error:', e.message); }

    console.log('Opening No Action Detail...');
    try {
        await page.goto('http://127.0.0.1:4173/simulation/no-action-game', { timeout: 10000 }); 
        await page.waitForLoadState('networkidle');
        await page.screenshot({ path: 'proof_batch_screenshots/mobile-detail-no-action-390-final.png' });
        console.log('Saved: proof_batch_screenshots/mobile-detail-no-action-390-final.png');
    } catch (e) { console.error('No Action Error:', e.message); }

    console.log('Opening Blocked Detail...');
    try {
        await page.goto('http://127.0.0.1:4173/simulation/blocked-game', { timeout: 10000 });
        await page.waitForLoadState('networkidle');
        await page.screenshot({ path: 'proof_batch_screenshots/mobile-detail-blocked-390-final.png' });
        console.log('Saved: proof_batch_screenshots/mobile-detail-blocked-390-final.png');
    } catch (e) { console.error('Blocked Error:', e.message); }

    await browser.close();
})();
