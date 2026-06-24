import pytest

from core.phase1_engine_lock_contract import (
    Classification,
    DecisionContext,
    League,
    MarketType,
    RecommendedAction,
    RecommendedReasonCode,
    ReleaseStatus,
    classification_for_release,
    classify_context_validity,
    derive_reason_code,
    derive_recommended_action,
)


def test_league_enum_closed_set():
    assert {x.value for x in League} == {"NBA", "NFL", "NHL", "NCAAB", "NCAAF", "MLB"}


def test_market_type_enum_closed_set():
    assert {x.value for x in MarketType} == {
        "SPREAD",
        "TOTAL",
        "MONEYLINE_2WAY",
        "MONEYLINE_3WAY",
    }


def test_release_status_enum_closed_set_no_approved():
    values = {x.value for x in ReleaseStatus}
    assert "APPROVED" not in values
    assert values == {
        "OFFICIAL",
        "INFO_ONLY",
        "BLOCKED_BY_RISK",
        "BLOCKED_BY_INTEGRITY",
        "BLOCKED_MISSING_CONTEXT",
    }


def test_context_invalid_market_or_league_is_blocked_missing_context():
    invalid = DecisionContext(
        league="UCL",
        event_id="e1",
        market_type="ML",
        odds_snapshot_id="s1",
        sim_result_id="r1",
        caller_surface="API",
    )
    valid, blocked_status = classify_context_validity(invalid)
    assert valid is False
    assert blocked_status == ReleaseStatus.BLOCKED_MISSING_CONTEXT


def test_classification_nullability_rules():
    assert (
        classification_for_release(ReleaseStatus.BLOCKED_BY_RISK, Classification.EDGE)
        is None
    )
    assert (
        classification_for_release(ReleaseStatus.BLOCKED_BY_INTEGRITY, Classification.LEAN)
        is None
    )
    assert (
        classification_for_release(ReleaseStatus.BLOCKED_MISSING_CONTEXT, Classification.NO_ACTION)
        is None
    )
    assert (
        classification_for_release(ReleaseStatus.OFFICIAL, Classification.EDGE)
        == Classification.EDGE
    )
    assert (
        classification_for_release(ReleaseStatus.INFO_ONLY, Classification.LEAN)
        == Classification.LEAN
    )


@pytest.mark.parametrize(
    "release,classification,directional,expected",
    [
        (ReleaseStatus.INFO_ONLY, Classification.EDGE, RecommendedAction.TAKE_THIS, RecommendedAction.NO_PLAY),
        (ReleaseStatus.BLOCKED_BY_RISK, None, None, RecommendedAction.NO_PLAY),
        (ReleaseStatus.OFFICIAL, Classification.NO_ACTION, RecommendedAction.TAKE_THIS, RecommendedAction.NO_PLAY),
        (ReleaseStatus.OFFICIAL, Classification.EDGE, RecommendedAction.TAKE_THIS, RecommendedAction.TAKE_THIS),
        (ReleaseStatus.OFFICIAL, Classification.LEAN, RecommendedAction.TAKE_OPPOSITE, RecommendedAction.TAKE_OPPOSITE),
    ],
)
def test_recommended_action_matrix(release, classification, directional, expected):
    assert derive_recommended_action(release, classification, directional) == expected


@pytest.mark.parametrize(
    "release,classification,signal_detected,expected",
    [
        (ReleaseStatus.BLOCKED_BY_RISK, None, False, RecommendedReasonCode.BLOCKED_BY_RISK),
        (
            ReleaseStatus.BLOCKED_BY_INTEGRITY,
            None,
            False,
            RecommendedReasonCode.BLOCKED_BY_INTEGRITY,
        ),
        (
            ReleaseStatus.BLOCKED_MISSING_CONTEXT,
            None,
            False,
            RecommendedReasonCode.BLOCKED_MISSING_CONTEXT,
        ),
        (ReleaseStatus.OFFICIAL, Classification.EDGE, True, RecommendedReasonCode.EDGE_THRESHOLD_MET),
        (ReleaseStatus.INFO_ONLY, Classification.LEAN, False, RecommendedReasonCode.LEAN_THRESHOLD_MET),
        (
            ReleaseStatus.OFFICIAL,
            Classification.NO_ACTION,
            False,
            RecommendedReasonCode.NO_ACTION_NO_SIGNAL,
        ),
        (
            ReleaseStatus.INFO_ONLY,
            Classification.NO_ACTION,
            True,
            RecommendedReasonCode.NO_ACTION_SIGNAL_BLOCKED,
        ),
    ],
)
def test_reason_code_matrix(release, classification, signal_detected, expected):
    assert derive_reason_code(release, classification, signal_detected) == expected
