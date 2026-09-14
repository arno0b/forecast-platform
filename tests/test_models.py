from datetime import datetime

from forecast_platform.models import Observation


def _obs() -> Observation:
    return Observation(
        settlement_date=datetime(2026, 9, 14, 2, 0, 0),
        region_id="NSW1",
        total_demand=6685.03,
        price=64.95,
        scheduled_generation=4701.90784,
        semi_scheduled_generation=803.51216,
    )


def test_observation_holds_the_fields_we_forecast_on():
    o = _obs()
    assert o.region_id == "NSW1"
    assert o.total_demand == 6685.03


def test_key_identifies_an_observation_uniquely():
    assert _obs().key() == ("2026-09-14T02:00:00", "NSW1")


def test_two_observations_at_the_same_time_and_region_share_a_key():
    assert _obs().key() == _obs().model_copy(update={"price": 999.0}).key()
