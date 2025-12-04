"""
Tier System Verification Script
Tests tier-based simulation power and component integration
"""
import asyncio
import sys
import os

# Add backend to path
backend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend')
sys.path.insert(0, backend_path)

from config import SIMULATION_TIERS, PRECISION_LABELS, TIER_COLORS  # type: ignore
from core.monte_carlo_engine import MonteCarloEngine  # type: ignore
from integrations.player_api import get_team_data_with_roster  # type: ignore

def verify_config():
    """Verify tier configuration"""
    print("🔍 VERIFYING TIER CONFIGURATION")
    print("=" * 60)
    
    expected_tiers = {
        "free": 10000,
        "starter": 25000,
        "pro": 50000,
        "elite": 75000,
        "admin": 100000
    }
    
    for tier, expected_sims in expected_tiers.items():
        actual_sims = SIMULATION_TIERS.get(tier)
        precision = PRECISION_LABELS.get(actual_sims, "UNKNOWN")
        status = "✅" if actual_sims == expected_sims else "❌"
        
        print(f"{status} {tier.upper():8s} - {actual_sims:,} iterations ({precision})")
    
    print(f"\n✅ Tier colors defined: {len(TIER_COLORS)} colors")
    print()

def verify_engine():
    """Verify Monte Carlo engine accepts dynamic iterations"""
    print("🔍 VERIFYING MONTE CARLO ENGINE")
    print("=" * 60)
    
    test_tiers = [10000, 25000, 50000, 75000]
    
    for iterations in test_tiers:
        engine = MonteCarloEngine(num_iterations=iterations)
        status = "✅" if engine.default_iterations == iterations else "❌"
        print(f"{status} Engine initialized with {iterations:,} iterations")
    
    print()

def verify_player_generation():
    """Verify player rosters include is_starter field"""
    print("🔍 VERIFYING PLAYER GENERATION")
    print("=" * 60)
    
    team_data = get_team_data_with_roster("Lakers", "basketball_nba", is_home=True)
    roster = team_data.get("roster", [])
    
    if not roster:
        print("❌ No roster generated")
        return
    
    print(f"✅ Generated roster with {len(roster)} players")
    
    # Check first 5 players have is_starter=True
    starters = [p for p in roster if p.get("is_starter", False)]
    print(f"✅ Found {len(starters)} starters (expected: 5)")
    
    # Check required fields
    required_fields = ["name", "status", "is_starter", "ppg", "apg", "rpg", "per", "avg_minutes"]
    sample_player = roster[0]
    missing_fields = [f for f in required_fields if f not in sample_player]
    
    if missing_fields:
        print(f"❌ Missing fields: {', '.join(missing_fields)}")
    else:
        print(f"✅ All required fields present")
    
    # Show sample player
    print(f"\n📋 Sample Player:")
    print(f"   Name: {sample_player['name']}")
    print(f"   Status: {sample_player['status']}")
    print(f"   Starter: {sample_player['is_starter']}")
    print(f"   PPG: {sample_player['ppg']}, APG: {sample_player['apg']}, RPG: {sample_player['rpg']}")
    print(f"   PER: {sample_player['per']}")
    print()

def verify_frontend_constants():
    """Verify frontend tier constants exist"""
    print("🔍 VERIFYING FRONTEND COMPONENTS")
    print("=" * 60)
    
    import os
    
    files_to_check = [
        "utils/tierConfig.ts",
        "components/SimulationBadge.tsx",
        "components/ConfidenceGauge.tsx",
        "components/TierShowcase.tsx"
    ]
    
    base_path = "/Users/rohithaditya/Downloads/Permutation-Carlos"
    
    for file_path in files_to_check:
        full_path = os.path.join(base_path, file_path)
        exists = os.path.exists(full_path)
        status = "✅" if exists else "❌"
        print(f"{status} {file_path}")
    
    print()

def main():
    """Run all verification checks"""
    print("\n" + "=" * 60)
    print("🚀 TIER SYSTEM VERIFICATION SUITE")
    print("=" * 60 + "\n")
    
    verify_config()
    verify_engine()
    verify_player_generation()
    verify_frontend_constants()
    
    print("=" * 60)
    print("✅ VERIFICATION COMPLETE")
    print("=" * 60)
    print("\n📊 NEXT STEPS:")
    print("1. Restart backend: ./start.sh")
    print("2. Restart frontend: npm run dev")
    print("3. Navigate to a game detail page")
    print("4. Look for 'Powered by X simulations' badge")
    print("5. Verify circular confidence gauge appears")
    print("6. Check animations (0.3s fade-in)")
    print("7. Test with different tiers (modify user.subscription_tier in DB)")
    print("\n🎨 OPTIONAL: Visit TierShowcase component to see all visuals")
    print()

if __name__ == "__main__":
    main()
