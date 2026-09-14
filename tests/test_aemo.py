import json
from datetime import datetime
from pathlib import Path

import httpx
import pytest
import respx

from forecast_platform.aemo import NEM_SUMMARY_URL, fetch_summary, parse_summary

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "nem_summary.json").read_text()
)


def test_parse_returns_one_observation_per_region():
    observations = parse_summary(FIXTURE)
    assert len(observations) == 2
    assert {o.region_id for o in observations} == {"NSW1", "VIC1"}


def test_parse_maps_the_fields_we_care_about():
    nsw = next(o for o in parse_summary(FIXTURE) if o.region_id == "NSW1")
    assert nsw.total_demand == 6685.03
    assert nsw.price == 64.95
    assert nsw.semi_scheduled_generation == 803.51216
    assert nsw.settlement_date == datetime(2026, 9, 14, 2, 0, 0)


def test_parse_tolerates_an_empty_payload():
    assert parse_summary({"ELEC_NEM_SUMMARY": []}) == []


def test_parse_raises_on_a_payload_missing_the_expected_key():
    with pytest.raises(KeyError):
        parse_summary({"something_else": []})


@respx.mock
def test_fetch_calls_aemo_and_parses_the_response():
    respx.get(NEM_SUMMARY_URL).mock(
        return_value=httpx.Response(200, json=FIXTURE)
    )
    observations = fetch_summary()
    assert len(observations) == 2


@respx.mock
def test_fetch_raises_on_a_server_error():
    respx.get(NEM_SUMMARY_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        fetch_summary()
