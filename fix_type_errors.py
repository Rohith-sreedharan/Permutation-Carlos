"""
Script to fix all type errors in sport calibration files
Adds null checks before function calls with Optional parameters
"""
import re
from pathlib import Path

def fix_sport_file(filepath: str, sport_name: str):
    """Fix type errors in a sport calibration file"""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern 1: Fix evaluate function null checks for NCAAB/NCAAF/NFL/NHL
    if 'calculate_spread_edge' in content or 'calculate_puckline_edge' in content:
        # These use spread markets
        patterns_to_fix = [
            # SPREAD market validation
            (
                r'(    # Calculate edge\n    if market_type == MarketType\.SPREAD:\n        raw_edge, compressed_edge = calculate_(?:spread|puckline)_edge\(\n            sim_cover_prob,)',
                r'''    # Validate required parameters based on market type
    if market_type == MarketType.SPREAD:
        if sim_cover_prob is None or spread is None or spread_odds is None:
            return {SPORT}MarketEvaluation(
                market_type=market_type,
                edge_state=EdgeState.NO_PLAY,
                raw_edge=0.0,
                compressed_edge=0.0,
                distribution_flag=DistributionFlag.STABLE,
                volatility=VolatilityLevel.LOW,
                eligible=False,
                blocking_reason="MISSING_MARKET_DATA"
            )
        raw_edge, compressed_edge = calculate_{CALC}_edge(
            sim_cover_prob,'''
            ),
        ]
        
        for pattern, replacement in patterns_to_fix:
            calc_type = 'puckline' if 'NHL' in sport_name.upper() else 'spread'
            replacement = replacement.replace('{SPORT}', sport_name.upper()).replace('{CALC}', calc_type)
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Pattern 2: Fix grade function null checks
    grade_patterns = [
        # Total line checks
        (
            r'(    elif market_type == MarketType\.TOTAL:\n        total_(?:points|goals|runs) = )',
            r'''    elif market_type == MarketType.TOTAL:
        if total_line is None:
            return "UNKNOWN"
            
        total_\1 = '''
        ),
        # Spread line checks
        (
            r'(    if market_type == MarketType\.SPREAD:\n        (?:cover_margin|adjusted_score) = )',
            r'''    if market_type == MarketType.SPREAD:
        if spread is None:
            return "UNKNOWN"
            
        \1 = '''
        ),
    ]
    
    for pattern, replacement in grade_patterns:
        content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
    
    # Write back
    with open(filepath, 'w') as f:
        f.write(content)
    
    print(f"Fixed {filepath}")

# Fix all sport files
sport_files = [
    ('backend/core/ncaab_calibration.py', 'NCAAB'),
    ('backend/core/ncaaf_calibration.py', 'NCAAF'),
    ('backend/core/nfl_calibration.py', 'NFL'),
    ('backend/core/nhl_calibration.py', 'NHL'),
    ('backend/core/nba_calibration.py', 'NBA'),
]

for filepath, sport in sport_files:
    try:
        fix_sport_file(filepath, sport)
    except Exception as e:
        print(f"Error fixing {filepath}: {e}")

print("Done!")
