import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.canonical_contract_enforcer import _normalize_spread_contract


def test_spread_contract_fails_closed_on_missing_binding() -> None:
    simulation = {
        "sharp_analysis": {
            "spread": {
                "has_edge": True,
                "sharp_selection": "Los Angeles Dodgers +1.5",
                "sharp_side": "Los Angeles Dodgers +1.5",
                "sharp_team": None,
                "sharp_line": 1.5,
                "sharp_action": "TAKE_POINTS",
                "sharp_side_display": "Los Angeles Dodgers +1.5",
            }
        },
        "market_views": {
            "spread": {
                "model_preference_selection_id": "NO_EDGE",
                "model_direction_selection_id": "NO_EDGE",
                "edge_class": "MARKET_ALIGNED",
                "ui_render_mode": "FULL",
                "integrity_status": {"status": "ok", "is_valid": True, "errors": []},
            }
        },
    }

    _normalize_spread_contract(simulation)

    spread = simulation["sharp_analysis"]["spread"]
    view = simulation["market_views"]["spread"]

    assert spread["has_edge"] is False
    assert spread["sharp_selection"] == "NO PLAY"
    assert spread["sharp_team"] is None
    assert spread["sharp_side_display"] == "NO PLAY"
    assert view["edge_class"] == "INVALID"
    assert view["model_preference_selection_id"] == "NO_EDGE"
    assert view["model_direction_selection_id"] == "NO_EDGE"
    assert view["integrity_status"]["is_valid"] is False
    assert "SPREAD_CANONICAL_BINDING_MISSING" in simulation["integrity_warnings"]
