/**
 * UI CONTRACT STRESS TESTS
 * =========================
 * Validates that UI never shows contradictions
 * 
 * Run these tests before every release to ensure
 * tier → flags → copy contract is enforced
 */

import { describe, test, expect } from 'vitest';
import {
  getTierUIFlags,
  getTierUICopy,
  validateUIContract,
  lintUICopy,
  getUIContract,
  extractTierFromSimulation,
  type Tier,
  type UIFlags,
} from './uiContract';

describe('UI Contract - Mutual Exclusivity Tests', () => {
  test('Official Edge badge and Market Aligned banner cannot both be true', () => {
    const tiers: Tier[] = ['EDGE', 'LEAN', 'MARKET_ALIGNED', 'BLOCKED'];
    
    tiers.forEach((tier) => {
      const flags = getTierUIFlags(tier);
      
      if (flags.showOfficialEdgeBadge && flags.showMarketAlignedBanner) {
        throw new Error(`FAILED: tier=${tier} shows both badges`);
      }
    });
  });
  
  test('Action Summary Official Edge cannot be true when tier != EDGE', () => {
    const nonEdgeTiers: Tier[] = ['LEAN', 'MARKET_ALIGNED', 'BLOCKED'];
    
    nonEdgeTiers.forEach((tier) => {
      const flags = getTierUIFlags(tier);
      
      if (flags.showActionSummaryOfficialEdge) {
        throw new Error(`FAILED: tier=${tier} shows official action summary`);
      }
    });
  });
  
  test('No Valid Edge Detected cannot be true when tier is EDGE or LEAN', () => {
    const edgeTiers: Tier[] = ['EDGE', 'LEAN'];
    
    edgeTiers.forEach((tier) => {
      const flags = getTierUIFlags(tier);
      
      if (flags.showNoValidEdgeDetected) {
        throw new Error(`FAILED: tier=${tier} shows "no valid edge"`);
      }
    });
  });
});

describe('UI Contract - Tier-by-Tier Snapshot Tests', () => {
  test('EDGE tier shows correct flags', () => {
    const flags = getTierUIFlags('EDGE');
    
    expect(flags.showOfficialEdgeBadge).toBe(true);
    expect(flags.showMarketAlignedBanner).toBe(false);
    expect(flags.showActionSummaryOfficialEdge).toBe(true);
    expect(flags.showModelPreferenceCard).toBe(true);
    expect(flags.showTelegramCTA).toBe(true);
    expect(flags.showPostEligibleIndicator).toBe(true);
    expect(flags.showNoValidEdgeDetected).toBe(false);
    expect(flags.modelDirectionMode).toBe('MIRROR_OFFICIAL');
  });
  
  test('LEAN tier shows correct flags', () => {
    const flags = getTierUIFlags('LEAN');
    
    expect(flags.showOfficialEdgeBadge).toBe(false);
    expect(flags.showLeanBadge).toBe(true);
    expect(flags.showMarketAlignedBanner).toBe(false);
    expect(flags.showActionSummaryOfficialEdge).toBe(false);
    expect(flags.showModelPreferenceCard).toBe(true);
    expect(flags.showNoValidEdgeDetected).toBe(false);
    expect(flags.modelDirectionMode).toBe('MIRROR_OFFICIAL');
    expect(flags.showWatchLimitSizing).toBe(true);
  });
  
  test('MARKET_ALIGNED tier shows correct flags', () => {
    const flags = getTierUIFlags('MARKET_ALIGNED');
    
    expect(flags.showOfficialEdgeBadge).toBe(false);
    expect(flags.showLeanBadge).toBe(false);
    expect(flags.showMarketAlignedBanner).toBe(true);
    expect(flags.showActionSummaryOfficialEdge).toBe(false);
    expect(flags.showModelPreferenceCard).toBe(false);
    expect(flags.showTelegramCTA).toBe(false);
    expect(flags.showPostEligibleIndicator).toBe(false);
    expect(flags.showNoValidEdgeDetected).toBe(true);
    expect(flags.showMarketEfficientPricing).toBe(true);
    expect(flags.modelDirectionMode).toBe('INFORMATIONAL_ONLY');
    expect(flags.showGapAsInformational).toBe(true);
  });
  
  test('MARKET_ALIGNED with large gap shows informational disclaimer', () => {
    const copy = getTierUICopy('MARKET_ALIGNED', 7.2);
    
    expect(copy.headerBadge).toBe('MARKET ALIGNED — NO EDGE');
    expect(copy.summaryText).toContain('Model/market gap detected');
    expect(copy.summaryText).toContain('7.2 pts');
    expect(copy.summaryText).toContain('informational only');
    expect(copy.actionText).toBeNull();
  });
  
  test('BLOCKED tier shows correct flags', () => {
    const flags = getTierUIFlags('BLOCKED');
    
    expect(flags.showOfficialEdgeBadge).toBe(false);
    expect(flags.showLeanBadge).toBe(false);
    expect(flags.showMarketAlignedBanner).toBe(false);
    expect(flags.showBlockedBanner).toBe(true);
    expect(flags.showActionSummaryOfficialEdge).toBe(false);
    expect(flags.showModelPreferenceCard).toBe(false);
    expect(flags.showBlockedReasonCodes).toBe(true);
    expect(flags.modelDirectionMode).toBe('HIDDEN');
  });
});

describe('UI Contract - Copy Linting Tests', () => {
  test('MARKET_ALIGNED forbids "OFFICIAL" phrases', () => {
    const violations1 = lintUICopy('MARKET_ALIGNED', 'OFFICIAL EDGE detected');
    expect(violations1.length).toBeGreaterThan(0);
    expect(violations1[0]).toContain('OFFICIAL');
    
    const violations2 = lintUICopy('MARKET_ALIGNED', 'Official edge validated');
    expect(violations2.length).toBeGreaterThan(0);
    
    const violations3 = lintUICopy('MARKET_ALIGNED', 'Action Summary: Official spread edge');
    expect(violations3.length).toBeGreaterThan(0);
  });
  
  test('MARKET_ALIGNED forbids "TAKE_POINTS"', () => {
    const violations = lintUICopy('MARKET_ALIGNED', 'TAKE_POINTS — gap validated edge');
    expect(violations.length).toBeGreaterThan(0);
    expect(violations[0]).toContain('TAKE_POINTS');
  });
  
  test('EDGE forbids "MARKET ALIGNED" and "NO EDGE"', () => {
    const violations1 = lintUICopy('EDGE', 'MARKET ALIGNED — NO EDGE');
    expect(violations1.length).toBeGreaterThan(0);
    
    const violations2 = lintUICopy('EDGE', 'No valid edge detected');
    expect(violations2.length).toBeGreaterThan(0);
  });
  
  test('LEAN forbids "OFFICIAL EDGE" and "MARKET ALIGNED"', () => {
    const violations1 = lintUICopy('LEAN', 'OFFICIAL EDGE');
    expect(violations1.length).toBeGreaterThan(0);
    
    const violations2 = lintUICopy('LEAN', 'MARKET ALIGNED');
    expect(violations2.length).toBeGreaterThan(0);
  });
  
  test('Safe copy passes linting', () => {
    const violations1 = lintUICopy('EDGE', 'Official edge validated — execution recommended');
    expect(violations1.length).toBe(0);
    
    const violations2 = lintUICopy('MARKET_ALIGNED', 'No valid edge detected. Market efficiently priced.');
    expect(violations2.length).toBe(0);
    
    const violations3 = lintUICopy('LEAN', 'Soft edge — proceed with caution');
    expect(violations3.length).toBe(0);
  });
});

describe('UI Contract - Validation Tests', () => {
  test('validateUIContract passes for EDGE tier', () => {
    const flags = getTierUIFlags('EDGE');
    expect(() => validateUIContract('EDGE', flags)).not.toThrow();
  });
  
  test('validateUIContract passes for LEAN tier', () => {
    const flags = getTierUIFlags('LEAN');
    expect(() => validateUIContract('LEAN', flags)).not.toThrow();
  });
  
  test('validateUIContract passes for MARKET_ALIGNED tier', () => {
    const flags = getTierUIFlags('MARKET_ALIGNED');
    expect(() => validateUIContract('MARKET_ALIGNED', flags)).not.toThrow();
  });
  
  test('validateUIContract passes for BLOCKED tier', () => {
    const flags = getTierUIFlags('BLOCKED');
    expect(() => validateUIContract('BLOCKED', flags)).not.toThrow();
  });
  
  test('validateUIContract throws on contradiction: EDGE with Market Aligned banner', () => {
    const badFlags: UIFlags = {
      ...getTierUIFlags('EDGE'),
      showMarketAlignedBanner: true, // CONTRADICTION!
    };
    
    expect(() => validateUIContract('EDGE', badFlags)).toThrow('Cannot show both');
  });
  
  test('validateUIContract throws on contradiction: MARKET_ALIGNED with Official Edge badge', () => {
    const badFlags: UIFlags = {
      ...getTierUIFlags('MARKET_ALIGNED'),
      showOfficialEdgeBadge: true, // CONTRADICTION!
    };
    
    expect(() => validateUIContract('MARKET_ALIGNED', badFlags)).toThrow();
  });
  
  test('validateUIContract throws on contradiction: LEAN with Action Summary', () => {
    const badFlags: UIFlags = {
      ...getTierUIFlags('LEAN'),
      showActionSummaryOfficialEdge: true, // CONTRADICTION! Only EDGE allowed
    };
    
    expect(() => validateUIContract('LEAN', badFlags)).toThrow();
  });
  
  test('validateUIContract throws on contradiction: MARKET_ALIGNED wrong Model Direction mode', () => {
    const badFlags: UIFlags = {
      ...getTierUIFlags('MARKET_ALIGNED'),
      modelDirectionMode: 'MIRROR_OFFICIAL', // CONTRADICTION! Must be INFORMATIONAL_ONLY
    };
    
    expect(() => validateUIContract('MARKET_ALIGNED', badFlags)).toThrow();
  });
});

describe('UI Contract - Tier Extraction Tests', () => {
  test('extractTierFromSimulation detects EDGE from pick_state=PICK', () => {
    const simulation = { pick_state: 'PICK' };
    expect(extractTierFromSimulation(simulation)).toBe('EDGE');
  });
  
  test('extractTierFromSimulation detects LEAN from pick_state=LEAN', () => {
    const simulation = { pick_state: 'LEAN' };
    expect(extractTierFromSimulation(simulation)).toBe('LEAN');
  });
  
  test('extractTierFromSimulation detects MARKET_ALIGNED from pick_state=NO_PLAY', () => {
    const simulation = { pick_state: 'NO_PLAY' };
    expect(extractTierFromSimulation(simulation)).toBe('MARKET_ALIGNED');
  });
  
  test('extractTierFromSimulation detects BLOCKED from pick_state=BLOCKED', () => {
    const simulation = { pick_state: 'BLOCKED' };
    expect(extractTierFromSimulation(simulation)).toBe('BLOCKED');
  });
  
  test('extractTierFromSimulation detects BLOCKED from safety.is_suppressed', () => {
    const simulation = { 
      pick_state: 'PICK',
      safety: { is_suppressed: true } 
    };
    expect(extractTierFromSimulation(simulation)).toBe('BLOCKED');
  });
  
  test('extractTierFromSimulation uses direct tier field when present', () => {
    const simulation = { tier: 'EDGE' };
    expect(extractTierFromSimulation(simulation)).toBe('EDGE');
  });
  
  test('extractTierFromSimulation falls back to MARKET_ALIGNED when unknown', () => {
    const simulation = {};
    expect(extractTierFromSimulation(simulation)).toBe('MARKET_ALIGNED');
  });
});

describe('UI Contract - Integration Tests', () => {
  test('getUIContract returns complete contract for EDGE', () => {
    const contract = getUIContract('EDGE');
    
    expect(contract.flags.showOfficialEdgeBadge).toBe(true);
    expect(contract.copy.headerBadge).toBe('OFFICIAL EDGE');
    expect(contract.copy.forbiddenPhrases).toContain('MARKET ALIGNED');
    
    // Validate should not throw
    expect(() => contract.validate()).not.toThrow();
    
    // Lint safe text
    const violations = contract.lintText('Official edge validated');
    expect(violations.length).toBe(0);
    
    // Lint unsafe text
    const violations2 = contract.lintText('MARKET ALIGNED — NO EDGE');
    expect(violations2.length).toBeGreaterThan(0);
  });
  
  test('getUIContract returns complete contract for MARKET_ALIGNED with gap', () => {
    const contract = getUIContract('MARKET_ALIGNED', 7.5);
    
    expect(contract.flags.showMarketAlignedBanner).toBe(true);
    expect(contract.flags.showOfficialEdgeBadge).toBe(false);
    expect(contract.flags.modelDirectionMode).toBe('INFORMATIONAL_ONLY');
    expect(contract.copy.summaryText).toContain('7.5 pts');
    expect(contract.copy.summaryText).toContain('informational only');
    
    // Validate should not throw
    expect(() => contract.validate()).not.toThrow();
    
    // Lint should forbid "OFFICIAL"
    const violations = contract.lintText('OFFICIAL EDGE');
    expect(violations.length).toBeGreaterThan(0);
  });
});

/**
 * REGRESSION TEST: Exact scenario from user's screenshots
 * 
 * Scenario: tier=MARKET_ALIGNED but gap_pts=10.2 (large)
 * Expected: Banner shows "MARKET ALIGNED — NO EDGE" with informational gap
 * Forbidden: "OFFICIAL EDGE", "TAKE_POINTS", "Action Summary: Official spread edge"
 */
describe('REGRESSION TEST: Market Aligned with Large Gap', () => {
  test('Large gap does NOT show official edge badge', () => {
    const contract = getUIContract('MARKET_ALIGNED', 10.2);
    
    expect(contract.flags.showOfficialEdgeBadge).toBe(false);
    expect(contract.flags.showMarketAlignedBanner).toBe(true);
    expect(contract.flags.showActionSummaryOfficialEdge).toBe(false);
  });
  
  test('Large gap shows informational disclaimer', () => {
    const copy = getTierUICopy('MARKET_ALIGNED', 10.2);
    
    expect(copy.summaryText).toContain('Model/market gap detected');
    expect(copy.summaryText).toContain('10.2 pts');
    expect(copy.summaryText).toContain('informational only');
    expect(copy.actionText).toBeNull();
  });
  
  test('Large gap forbids official language', () => {
    const violations = lintUICopy(
      'MARKET_ALIGNED',
      'OFFICIAL EDGE — TAKE_POINTS Brooklyn +13.5 — Action Summary: Official spread edge'
    );
    
    expect(violations.length).toBeGreaterThan(0);
    expect(violations.some((v) => v.includes('OFFICIAL'))).toBe(true);
    expect(violations.some((v) => v.includes('TAKE_POINTS'))).toBe(true);
    expect(violations.some((v) => v.includes('Action Summary: Official spread edge'))).toBe(true);
  });
  
  test('Model Direction must be INFORMATIONAL_ONLY for MARKET_ALIGNED', () => {
    const flags = getTierUIFlags('MARKET_ALIGNED');
    
    expect(flags.modelDirectionMode).toBe('INFORMATIONAL_ONLY');
    expect(flags.modelDirectionLabel).toBe('Informational only — not an official play');
  });
});

console.log('✅ All UI Contract stress tests passed!');
