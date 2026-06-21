import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.simulation_entitlement_filter import apply_simulation_entitlement_filter


def _sample_payload():
    return {
        "event_id": "evt_1",
        "market_views": {"spread": {"edge_class": "EDGE", "model_preference_selection_id": "sel_1"}},
        "sharp_analysis": {"spread": {"reasoning": "Long explanation"}},
        "distribution_curve": [1, 2, 3],
        "total_distribution": {"total_o210.5": 0.52},
        "spread_distribution": {"home_cover": 0.55},
        "injury_summary": {"impact": "moderate"},
        "top_props": [{"player": "X"}],
        "confidence_score": 61,
        "volatility_score": "Medium",
        "market_context": {
            "total_line": 210.5,
            "bookmaker_1h_line": 104.5,
            "bookmaker_1h_source": "book_a",
        },
    }


def test_non_platform_redacts_platform_intelligence_fields():
    payload = _sample_payload()

    filtered = apply_simulation_entitlement_filter(payload, "free")

    assert "market_views" not in filtered
    assert "sharp_analysis" not in filtered
    assert "distribution_curve" not in filtered
    assert "total_distribution" not in filtered
    assert "spread_distribution" not in filtered
    assert "injury_summary" not in filtered
    assert "top_props" not in filtered
    assert "confidence_score" not in filtered
    assert "volatility_score" not in filtered
    assert filtered["market_context"]["total_line"] == 210.5
    assert "bookmaker_1h_line" not in filtered["market_context"]
    assert filtered["entitlement_redaction"]["applied"] is True


def test_platform_keeps_full_payload():
    payload = _sample_payload()

    filtered = apply_simulation_entitlement_filter(payload, "platform")

    assert "market_views" in filtered
    assert "sharp_analysis" in filtered
    assert "distribution_curve" in filtered
    assert "top_props" in filtered
    assert "entitlement_redaction" not in filtered
