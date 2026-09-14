from datetime import datetime, timedelta

import pytest

from forecast_platform.forecaster import MODEL_NAME, forecast
from forecast_platform.models import Observation

BASE = datetime(2026, 9, 1, 0, 0)
HOUR = timedelta(hours=1)
HALF_HOUR = timedelta(minutes=30)
FIVE_MIN = timedelta(minutes=5)


def _obs(minute: int, demand: float) -> Observation:
    return Observation(
        settlement_date=BASE + timedelta(minutes=minute),
        region_id="NSW1",
        total_demand=demand,
        price=60.0,
        scheduled_generation=4000.0,
        semi_scheduled_generation=800.0,
    )


def _regular(count: int) -> list[Observation]:
    """count observations at a clean five-minute spacing, demand == minute."""
    return [_obs(5 * i, float(5 * i)) for i in range(count)]


def test_model_has_a_name_we_report_in_the_api():
    assert MODEL_NAME == "seasonal-naive"


def test_returns_one_value_per_horizon_step():
    assert len(forecast(_regular(13), horizon=6, season=HOUR)) == 6


def test_looks_up_the_value_one_season_before_each_step():
    # Last observation is at minute 60. With a one-hour season, step 1
    # targets minute 65 and looks up minute 5; step 2 targets 70, looks up 10.
    assert forecast(_regular(13), horizon=2, season=HOUR) == [5.0, 10.0]


def test_accepts_the_nearest_observation_within_tolerance():
    # Lookup lands on minute 5. Nothing is exactly there, but minute 8 is
    # three minutes away, well inside the tolerance.
    history = [_obs(0, 100.0), _obs(8, 200.0), _obs(60, 999.0)]
    assert forecast(history, horizon=1, season=HOUR) == [200.0]


def test_falls_back_to_persistence_when_nothing_is_close_enough():
    # Lookup lands on minute 35. Nearest observation is minute 60, which is
    # 25 minutes away and outside the 15 minute tolerance, so persist instead.
    history = [_obs(0, 100.0), _obs(60, 999.0)]
    assert forecast(history, horizon=1, season=HALF_HOUR) == [999.0]


def test_cold_start_persists_because_the_lookup_predates_all_history():
    # A week-long season against twenty minutes of history. Every lookup is
    # far before the first observation, so every step persists.
    history = _regular(5)
    assert forecast(history, horizon=3) == [20.0, 20.0, 20.0]


def test_irregular_spacing_does_not_shift_the_lookup():
    # Deliberately ragged: a dropped scheduled run leaves a gap. Positional
    # indexing would silently read the wrong time here. Timestamp lookup
    # still resolves minute 5 correctly.
    history = [_obs(0, 100.0), _obs(5, 111.0), _obs(37, 222.0), _obs(60, 999.0)]
    assert forecast(history, horizon=1, season=HOUR) == [111.0]


def test_raises_on_empty_history():
    with pytest.raises(ValueError):
        forecast([], horizon=3)


def test_raises_on_a_non_positive_horizon():
    with pytest.raises(ValueError):
        forecast(_regular(13), horizon=0)


def test_history_arriving_out_of_order_is_still_handled():
    # /predict takes history from a client, so arrival order is not
    # guaranteed. Everything here depends on knowing which observation is
    # the most recent, so the forecaster must not trust the caller's order.
    ordered = _regular(13)
    shuffled = [ordered[7], ordered[0], ordered[12], ordered[3]] + ordered[1:7]
    assert forecast(shuffled, horizon=2, season=HOUR) == [5.0, 10.0]
