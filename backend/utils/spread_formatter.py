"""
Spread Display Formatter — LOCKED DEFINITION

Ensures all API responses include properly formatted spread display strings.

■ MANDATORY FIELDS FOR ALL SPREAD RESPONSES:
- market_spread: float (raw value)
- model_spread: float (SIGNED: + = underdog, - = favorite)
- market_spread_display: str (e.g., "Hawks +5.5")
- model_spread_display: str (e.g., "Hawks +12.3")
- sharp_side_display: str (e.g., "Knicks -5.5")
"""
from typing import Dict, Optional


def format_spread_for_api(
    home_team: str,
    away_team: str,
    market_spread_home: float,
    model_spread: float,
    sharp_side: Optional[str] = None
) -> Dict[str, str]:
    """
    Format spread values for API response with team labels
    
    Args:
        home_team: Home team name
        away_team: Away team name
        market_spread_home: Market spread from HOME perspective (negative = home favored)
        model_spread: SIGNED model spread (+ = underdog, - = favorite)
        sharp_side: Optional sharp side selection (e.g., "Knicks -5.5")
    
    Returns:
        Dict with display strings for UI
        
    Example:
        format_spread_for_api("Knicks", "Hawks", -5.5, 12.3)
        # Returns:
        # {
        #     'market_spread_display': 'Hawks +5.5',
        #     'model_spread_display': 'Hawks +12.3',
        #     'sharp_side_display': 'Knicks -5.5',  # If provided
        #     'market_favorite': 'Knicks',
        #     'market_underdog': 'Hawks'
        # }
    """
    # Calculate away spread
    market_spread_away = -market_spread_home
    
    # Determine market favorite/underdog
    if market_spread_home < 0:
        # Home is favorite
        market_favorite = home_team
        market_underdog = away_team
        market_spread_underdog = market_spread_away  # Positive
    else:
        # Away is favorite (or pick'em)
        market_favorite = away_team
        market_underdog = home_team
        market_spread_underdog = market_spread_home  # Positive
    
    # Format market spread display (always show underdog + points)
    market_spread_display = f"{market_underdog} +{market_spread_underdog:.1f}"
    
    # Format model spread display (always show from underdog perspective with sign)
    model_spread_sign = '+' if model_spread >= 0 else ''
    model_spread_display = f"{market_underdog} {model_spread_sign}{model_spread:.1f}"
    
    result = {
        'market_spread_display': market_spread_display,
        'model_spread_display': model_spread_display,
        'market_favorite': market_favorite,
        'market_underdog': market_underdog,
        'market_spread_underdog': market_spread_underdog
    }
    
    # Add sharp side if provided
    if sharp_side:
        result['sharp_side_display'] = sharp_side
    
    return result


def validate_spread_response(response_data: Dict) -> tuple[bool, Optional[str]]:
    """
    Validate that API response includes all required spread display fields
    
    Args:
        response_data: API response dictionary
        
    Returns:
        (is_valid, error_message)
    """
    required_fields = [
        'market_spread_display',
        'model_spread_display',
        'market_favorite',
        'market_underdog'
    ]
    
    # Check if spread data exists
    if 'spread' not in response_data and 'sharp_analysis' not in response_data:
        return True, None  # Not a spread response, no validation needed
    
    # Extract spread section
    spread_section = response_data.get('spread') or response_data.get('sharp_analysis', {}).get('spread')
    
    if not spread_section:
        return True, None
    
    # Check required fields
    missing_fields = []
    for field in required_fields:
        if field not in spread_section:
            missing_fields.append(field)
    
    if missing_fields:
        return False, f"Missing required spread display fields: {', '.join(missing_fields)}"
    
    # Validate sharp_side if edge exists
    if spread_section.get('has_edge') and 'sharp_side_display' not in spread_section:
        return False, "has_edge=True but sharp_side_display is missing"
    
    return True, None


def enrich_simulation_response(simulation_data: Dict) -> Dict:
    """
    Enrich simulation response with formatted spread displays
    
    Call this before returning simulation data from API
    
    Args:
        simulation_data: Raw simulation response
        
    Returns:
        Enhanced response with display strings
    """
    # Check if spread analysis exists
    if 'sharp_analysis' not in simulation_data:
        return simulation_data
    
    sharp_analysis = simulation_data['sharp_analysis']
    
    if 'spread' not in sharp_analysis:
        return simulation_data
    
    spread = sharp_analysis['spread']
    
    # Extract required data
    home_team = simulation_data.get('home_team')
    away_team = simulation_data.get('away_team')
    market_spread_home = spread.get('vegas_spread')
    model_spread = spread.get('model_spread')
    sharp_side = spread.get('sharp_side')
    
    # Validate inputs - ensure we have all required data
    if not home_team or not away_team or market_spread_home is None or model_spread is None:
        return simulation_data
    
    # Type assertions for Pylance (data validated above)
    assert isinstance(home_team, str)
    assert isinstance(away_team, str)
    
    # Generate display strings
    display_data = format_spread_for_api(
        home_team,
        away_team,
        market_spread_home,
        model_spread,
        sharp_side
    )
    
    # Enrich spread section
    spread.update(display_data)
    
    return simulation_data


# Example usage in API endpoint:
"""
@app.get("/api/simulation/{sim_id}")
async def get_simulation(sim_id: str):
    # Fetch raw simulation data
    simulation = db.simulations.find_one({"sim_id": sim_id})
    
    # Enrich with display strings
    simulation = enrich_simulation_response(simulation)
    
    # Validate before returning
    is_valid, error = validate_spread_response(simulation)
    if not is_valid:
        logger.error(f"Spread validation failed: {error}")
        # Fix it or raise error
    
    return simulation
"""
