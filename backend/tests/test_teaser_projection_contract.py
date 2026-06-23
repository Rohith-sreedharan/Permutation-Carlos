from routes.odds_routes import _serialize_teaser_event, TEASER_EVENT_ALLOWLIST


def test_teaser_projection_drops_forbidden_fields() -> None:
    source = {
        "id": "evt_1",
        "event_id": "evt_1",
        "sport_key": "basketball_nba",
        "commence_time": "2026-01-01T00:00:00Z",
        "home_team": "Lakers",
        "away_team": "Celtics",
        "classification": "EDGE",
        "edge_classification": "EDGE",
        "pick_state": "PICK",
        "release_status": "OFFICIAL",
        "confidence_tier": "STRONG",
        "bookmakers": [{"key": "draftkings"}],
        "sharp_analysis": {"spread": {"model_spread": -4.2}},
        "market_views": {"spread": {"edge_class": "EDGE"}},
        "rcl_total": 221.5,
    }

    projected = _serialize_teaser_event(source)

    assert set(projected.keys()).issubset(TEASER_EVENT_ALLOWLIST)
    assert "bookmakers" not in projected
    assert "sharp_analysis" not in projected
    assert "market_views" not in projected
    assert "rcl_total" not in projected


def test_teaser_projection_is_zero_transform_copy() -> None:
    source = {
        "event_id": "evt_2",
        "sport_key": "americanfootball_nfl",
        "commence_time": "2026-02-01T20:25:00Z",
        "home_team": "Chiefs",
        "away_team": "Bills",
        "status": "IN_PROGRESS",
        "completed": False,
        "home_score": 14,
        "away_score": 10,
        "classification": "LEAN",
        "pick_state": "LEAN",
    }

    projected = _serialize_teaser_event(source)

    for key, value in projected.items():
        assert key in source
        assert value == source[key]


def test_teaser_projection_does_not_synthesize_id() -> None:
    source = {
        "event_id": "evt_3",
        "sport_key": "baseball_mlb",
        "home_team": "Dodgers",
        "away_team": "Yankees",
    }

    projected = _serialize_teaser_event(source)

    assert projected["event_id"] == "evt_3"
    assert "id" not in projected
