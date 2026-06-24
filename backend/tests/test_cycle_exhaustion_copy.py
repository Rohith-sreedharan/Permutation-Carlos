from routes import simulation_routes


def test_exhaustion_copy_base_message(monkeypatch) -> None:
    monkeypatch.setattr(
        simulation_routes,
        "_compute_weekly_opened_record",
        lambda _user_id: {"wins": 0, "losses": 0, "pushes": 0},
    )

    msg = simulation_routes._exhaustion_upgrade_message("user_1")

    assert msg == "You've used today's intelligence allocation. Upgrade to continue analyzing today's board."


def test_exhaustion_copy_stat_variant(monkeypatch) -> None:
    monkeypatch.setattr(
        simulation_routes,
        "_compute_weekly_opened_record",
        lambda _user_id: {"wins": 4, "losses": 2, "pushes": 1},
    )

    msg = simulation_routes._exhaustion_upgrade_message("user_2")

    assert msg == "You're 4-2 this week. Upgrade to Platform to access every game, every day."
