from unittest.mock import patch

import favorite_picks
from future_projection_live import build_current_market_state
from test_v5111_favorite_picks import YEARS, live_fixture, market_fixture


def test_partial_breadth_quotes_do_not_cancel_market_state():
    live = {
        "prices": {"AAA": 101.0, "BBB": 99.0},
        "histories": {},
        "fundamentals": {"AAA": {"forward_pe": 20.0}},
        "breadth_symbols": ["AAA", "BBB"],
    }
    state = build_current_market_state(["AAA", "BBB"], live)
    assert state["breadth_above_50_day"] == 50.0
    assert state["breadth_above_200_day"] == 50.0
    assert state["breadth_sample_size"] == 0


def test_favorite_picks_falls_back_when_optional_live_conditioning_is_malformed():
    original = favorite_picks.build_current_market_state

    def fail_only_live(symbols, context):
        if context and context.get("prices"):
            raise KeyError("malformed optional breadth record")
        return original(symbols, context)

    with patch.object(favorite_picks, "build_current_market_state", side_effect=fail_only_live):
        result = favorite_picks.build_favorite_picks(
            market_fixture(), YEARS, live_fixture(), simulations=100, shortlist_per_sector=4
        )

    assert len(result["table"]) == 4
    assert result["market_state"]["live_conditioning_active"] is False
    assert any("KeyError" in item for item in result["market_state"]["failures"])
