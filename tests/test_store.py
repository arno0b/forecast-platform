from datetime import datetime, timedelta

from forecast_platform.models import Observation
from forecast_platform.store import CsvStore


def _obs(minutes: int, region: str = "NSW1", demand: float = 6000.0) -> Observation:
    return Observation(
        settlement_date=datetime(2026, 9, 14, 0, 0) + timedelta(minutes=minutes),
        region_id=region,
        total_demand=demand,
        price=60.0,
        scheduled_generation=4000.0,
        semi_scheduled_generation=800.0,
    )


def test_append_writes_new_observations(tmp_path):
    store = CsvStore(tmp_path)
    assert store.append([_obs(0), _obs(5)]) == 2
    assert len(store.read_region("NSW1")) == 2


def test_append_is_idempotent_on_the_same_interval(tmp_path):
    store = CsvStore(tmp_path)
    store.append([_obs(0)])
    assert store.append([_obs(0)]) == 0
    assert len(store.read_region("NSW1")) == 1


def test_append_deduplicates_within_a_single_call(tmp_path):
    store = CsvStore(tmp_path)
    assert store.append([_obs(0), _obs(0)]) == 1


def test_regions_are_stored_separately(tmp_path):
    store = CsvStore(tmp_path)
    store.append([_obs(0, region="NSW1"), _obs(0, region="VIC1")])
    assert len(store.read_region("NSW1")) == 1
    assert len(store.read_region("VIC1")) == 1


def test_read_region_returns_chronological_order(tmp_path):
    store = CsvStore(tmp_path)
    store.append([_obs(10), _obs(0), _obs(5)])
    dates = [o.settlement_date for o in store.read_region("NSW1")]
    assert dates == sorted(dates)


def test_read_region_is_empty_for_an_unknown_region(tmp_path):
    assert CsvStore(tmp_path).read_region("QLD1") == []


def test_append_survives_a_restart(tmp_path):
    CsvStore(tmp_path).append([_obs(0)])
    assert len(CsvStore(tmp_path).read_region("NSW1")) == 1


def test_append_handles_a_full_day_backfill_in_one_batch(tmp_path):
    # 288 five-minute intervals is one full market day. This is the Phase 2
    # backfill shape, and the case the per-file key cache exists for.
    store = CsvStore(tmp_path)
    day = [_obs(5 * i) for i in range(288)]
    assert store.append(day) == 288
    assert len(store.read_region("NSW1")) == 288
    assert store.append(day) == 0
