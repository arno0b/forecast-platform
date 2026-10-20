from datetime import datetime, timedelta

import boto3
import pytest
from moto import mock_aws

from forecast_platform.models import Observation
from forecast_platform.store import S3Store

BUCKET = "fp-observations-test"
REGION = "ap-southeast-2"


def _obs(minutes: int, region: str = "NSW1", demand: float = 6000.0) -> Observation:
    return Observation(
        settlement_date=datetime(2026, 10, 21, 0, 0) + timedelta(minutes=minutes),
        region_id=region,
        total_demand=demand,
        price=60.0,
        scheduled_generation=4000.0,
        semi_scheduled_generation=800.0,
    )


@pytest.fixture
def store():
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        yield S3Store(bucket=BUCKET, region_name=REGION)


def test_append_writes_new_observations(store):
    assert store.append([_obs(0), _obs(5)]) == 2
    assert len(store.read_region("NSW1")) == 2


def test_append_is_idempotent_on_the_same_interval(store):
    store.append([_obs(0)])
    assert store.append([_obs(0)]) == 0
    assert len(store.read_region("NSW1")) == 1


def test_append_deduplicates_within_a_single_call(store):
    assert store.append([_obs(0), _obs(0)]) == 1


def test_a_revision_of_a_stored_interval_does_not_create_a_second_row(store):
    # AEMO revises published figures. The same interval coming back with a
    # different demand is a correction, not a new event. First write wins,
    # matching CsvStore.
    store.append([_obs(0, demand=6000.0)])
    assert store.append([_obs(0, demand=6005.5)]) == 0
    rows = store.read_region("NSW1")
    assert len(rows) == 1
    assert rows[0].total_demand == 6000.0


def test_regions_are_stored_separately(store):
    store.append([_obs(0, region="NSW1"), _obs(0, region="VIC1")])
    assert len(store.read_region("NSW1")) == 1
    assert len(store.read_region("VIC1")) == 1


def test_read_region_returns_chronological_order(store):
    store.append([_obs(10), _obs(0), _obs(5)])
    dates = [o.settlement_date for o in store.read_region("NSW1")]
    assert dates == sorted(dates)


def test_read_region_is_empty_for_an_unknown_region(store):
    assert store.read_region("QLD1") == []


def test_append_of_nothing_writes_nothing(store):
    assert store.append([]) == 0
    assert store.read_region("NSW1") == []


def test_observations_split_across_market_days_land_in_separate_objects(store):
    # 23:55 and 00:05 the next day. These are consecutive-ish in market time
    # but ten hours apart in UTC, so a key derived from a UTC date would put
    # them in the same object and split every market day at 10am instead.
    store.append([_obs(23 * 60 + 55), _obs(24 * 60 + 5)])
    client = boto3.client("s3", region_name=REGION)
    keys = sorted(o["Key"] for o in client.list_objects_v2(Bucket=BUCKET)["Contents"])
    assert keys == [
        "observations/nsw1/2026-10-21.csv",
        "observations/nsw1/2026-10-22.csv",
    ]
    assert len(store.read_region("NSW1")) == 2


def test_a_concurrent_write_does_not_lose_data(store, monkeypatch):
    # S3 has no append, only replace. Two writers doing read-modify-write on
    # the same object will silently lose one of them unless the write is
    # conditional on the object not having changed.
    #
    # Simulate a competing writer landing between our read and our write.
    store.append([_obs(0)])
    original_put = store._client.put_object
    state = {"fired": False}

    def racing_put(**kwargs):
        if not state["fired"]:
            state["fired"] = True
            # Another process writes while our PUT is in flight.
            S3Store(bucket=BUCKET, region_name=REGION).append([_obs(5)])
        return original_put(**kwargs)

    monkeypatch.setattr(store._client, "put_object", racing_put)
    store.append([_obs(10)])

    minutes = sorted(o.settlement_date.minute for o in store.read_region("NSW1"))
    assert minutes == [0, 5, 10], "a concurrent write was lost"
