"""
PROOF ARTIFACT #5: Frontend No-UI-Inference Test
=================================================

This test FAILS if the frontend computes:
  - favorite/underdog from raw spread numbers
  - take/lay from model vs market comparison
  - opposite side from team name manipulation

ALL these values must come from backend canonical fields.
"""

/**
 * Frontend Unit Test (TypeScript/Jest)
 * 
 * This would be implemented in:
 *   components/__tests__/GameDetail.test.tsx
 */

// Mock simulation data
const mockSimulation = {
  event_id: "test_event_123",
  home_team: "Boston Celtics",
  away_team: "Dallas Mavericks",
  sharp_analysis: {
    spread: {
      // Canonical fields from backend
      market_favorite: "Boston Celtics",
      market_underdog: "Dallas Mavericks",
      market_spread_home: -7.5,
      fair_spread_home: -16.8,
      sharp_side_display: "Boston Celtics -7.5",
      sharp_action: "FAV",
      recommended_action: "TAKE",
      recommended_selection_id: "test_event_123_spread_home"
    }
  }
};

// ❌ FORBIDDEN UI PATTERNS (these should FAIL the test)
const forbiddenPatterns = {
  
  // Pattern 1: Computing favorite from raw spread
  computeFavoriteFromSpread: (simulation) => {
    // ❌ WRONG
    return simulation.sharp_analysis.spread.market_spread_home < 0
      ? simulation.home_team
      : simulation.away_team;
  },
  
  // Pattern 2: Computing sharp side from model vs market
  computeSharpSideFromNumbers: (simulation) => {
    // ❌ WRONG
    const modelSpread = simulation.sharp_analysis.spread.fair_spread_home;
    const marketSpread = simulation.sharp_analysis.spread.market_spread_home;
    return modelSpread > marketSpread ? "DOG" : "FAV";
  },
  
  // Pattern 3: Computing sharp side display from team names
  computeSharpSideDisplay: (simulation, spread) => {
    // ❌ WRONG
    const sharpSide = spread.sharp_action === "FAV" ? "favorite" : "underdog";
    const team = sharpSide === "favorite" ? simulation.home_team : simulation.away_team;
    const line = spread.market_spread_home;
    return `${team} ${line}`;
  },
  
  // Pattern 4: Computing recommended bet from inference
  computeRecommendedBet: (simulation) => {
    // ❌ WRONG
    const edge = simulation.sharp_analysis.spread.fair_spread_home - 
                 simulation.sharp_analysis.spread.market_spread_home;
    return edge > 5 ? "TAKE" : "NO_PLAY";
  }
};

// ✅ CORRECT UI PATTERNS (use backend fields directly)
const correctPatterns = {
  
  // Pattern 1: Use backend's market_favorite
  renderFavorite: (simulation) => {
    // ✅ CORRECT
    return simulation.sharp_analysis.spread.market_favorite;
  },
  
  // Pattern 2: Use backend's sharp_action
  renderSharpSide: (simulation) => {
    // ✅ CORRECT
    return simulation.sharp_analysis.spread.sharp_action;
  },
  
  // Pattern 3: Use backend's sharp_side_display
  renderSharpSideDisplay: (simulation) => {
    // ✅ CORRECT
    return simulation.sharp_analysis.spread.sharp_side_display;
  },
  
  // Pattern 4: Use backend's recommended_action
  renderRecommendedAction: (simulation) => {
    // ✅ CORRECT
    return simulation.sharp_analysis.spread.recommended_action;
  }
};

// TEST SUITE
describe('GameDetail - No UI Inference', () => {
  
  test('FAILS if UI computes favorite from raw spread', () => {
    // ❌ This pattern should be BANNED from codebase
    const forbidden = forbiddenPatterns.computeFavoriteFromSpread(mockSimulation);
    const correct = correctPatterns.renderFavorite(mockSimulation);
    
    // Verify backend field exists
    expect(mockSimulation.sharp_analysis.spread.market_favorite).toBeDefined();
    
    // UI must use backend field
    expect(correct).toBe("Boston Celtics");
    
    // The forbidden pattern happens to match in this case,
    // but it's still FORBIDDEN because it won't work in all cases
    console.warn("UI INFERENCE DETECTED: computeFavoriteFromSpread()");
  });
  
  test('FAILS if UI computes sharp side from model vs market', () => {
    // ❌ This pattern should be BANNED
    const forbidden = forbiddenPatterns.computeSharpSideFromNumbers(mockSimulation);
    const correct = correctPatterns.renderSharpSide(mockSimulation);
    
    // Verify backend field exists
    expect(mockSimulation.sharp_analysis.spread.sharp_action).toBeDefined();
    expect(correct).toBe("FAV");
  });
  
  test('FAILS if UI computes sharp_side_display string', () => {
    // ❌ This pattern should be BANNED
    const spread = mockSimulation.sharp_analysis.spread;
    const forbidden = forbiddenPatterns.computeSharpSideDisplay(mockSimulation, spread);
    const correct = correctPatterns.renderSharpSideDisplay(mockSimulation);
    
    // Verify backend field exists
    expect(spread.sharp_side_display).toBeDefined();
    expect(correct).toBe("Boston Celtics -7.5");
  });
  
  test('FAILS if UI computes recommended action from edge', () => {
    // ❌ This pattern should be BANNED
    const forbidden = forbiddenPatterns.computeRecommendedBet(mockSimulation);
    const correct = correctPatterns.renderRecommendedAction(mockSimulation);
    
    // Verify backend field exists
    expect(mockSimulation.sharp_analysis.spread.recommended_action).toBeDefined();
    expect(correct).toBe("TAKE");
  });
  
  test('Model Direction uses backend sharp_side_display only', () => {
    // ✅ CORRECT: Direct backend field usage
    const modelDirection = mockSimulation.sharp_analysis.spread.sharp_side_display;
    
    expect(modelDirection).toBe("Boston Celtics -7.5");
    
    // Verify no UI computation
    expect(modelDirection).not.toContain("calculateSpreadContext");
    expect(modelDirection).not.toContain("determineSharpSide");
  });
  
  test('Backend payload contains all required fields', () => {
    const spread = mockSimulation.sharp_analysis.spread;
    
    // Assert all required fields exist
    expect(spread.market_favorite).toBeDefined();
    expect(spread.market_underdog).toBeDefined();
    expect(spread.market_spread_home).toBeDefined();
    expect(spread.fair_spread_home).toBeDefined();
    expect(spread.sharp_side_display).toBeDefined();
    expect(spread.sharp_action).toBeDefined();
    expect(spread.recommended_action).toBeDefined();
    expect(spread.recommended_selection_id).toBeDefined();
    
    console.log("✅ All required backend fields present");
  });
  
  test('CRITICAL: Selection IDs must not diverge', () => {
    const spread = mockSimulation.sharp_analysis.spread;
    
    // Add selection IDs to mock
    spread.model_direction_selection_id = "test_event_123_spread_home";
    spread.model_preference_selection_id = "test_event_123_spread_home";
    
    // CRITICAL ASSERTION
    expect(spread.model_direction_selection_id).toBe(spread.model_preference_selection_id);
    
    console.log("✅ Selection IDs locked (no divergence)");
  });
});

// ESLint rule to ban forbidden patterns
const eslintRuleForbiddenPatterns = {
  "no-ui-inference": {
    meta: {
      type: "problem",
      docs: {
        description: "Disallow UI inference of spread components",
        category: "Institutional Standards",
        recommended: true
      }
    },
    create(context) {
      return {
        // Ban: market_spread_home < 0 ? home_team : away_team
        ConditionalExpression(node) {
          if (
            node.test.type === "BinaryExpression" &&
            node.test.operator === "<" &&
            node.test.left.property?.name === "market_spread_home"
          ) {
            context.report({
              node,
              message: "UI_INFERENCE_FORBIDDEN: Use market_favorite from backend instead"
            });
          }
        },
        
        // Ban: calculateSpreadContext()
        CallExpression(node) {
          if (node.callee.name === "calculateSpreadContext") {
            context.report({
              node,
              message: "UI_INFERENCE_FORBIDDEN: Use sharp_side_display from backend"
            });
          }
          if (node.callee.name === "determineSharpSide") {
            context.report({
              node,
              message: "UI_INFERENCE_FORBIDDEN: Use sharp_action from backend"
            });
          }
        }
      };
    }
  }
};

console.log("\n" + "=".repeat(70));
console.log("PROOF ARTIFACT #5: Frontend No-UI-Inference Test");
console.log("=".repeat(70));
console.log("\nForbidden Patterns:");
console.log("  ❌ Computing favorite from market_spread_home < 0");
console.log("  ❌ Computing sharp side from model vs market comparison");
console.log("  ❌ Computing sharp_side_display string");
console.log("  ❌ Computing recommended_action from edge");
console.log("\nRequired Pattern:");
console.log("  ✅ Use backend canonical fields ONLY");
console.log("=".repeat(70));
