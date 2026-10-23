import json
from pathlib import Path

import boto3
import httpx
import pytest
import respx
from moto import mock_aws

from forecast_platform.aemo import NEM_SUMMARY_URL
from forecast_platform.store import S3Store

BUCKET = "fp-observations-test"
REGION = "ap-southeast-2"
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "nem_summary.json").read_text()
)


@pytest.fixture
def bucket(monkeypatch):
    with mock_aws():
        boto3.client("s3", region_name=REGION).create_bucket(
            Bucket=BUCKET,
            CreateBucketConfiguration={"LocationConstraint": REGION},
        )
        monkeypatch.setenv("OBSERVATIONS_BUCKET", BUCKET)
        monkeypatch.setenv("AWS_DEFAULT_REGION", REGION)
        yield BUCKET


@respx.mock
def test_handler_fetches_and_writes(bucket):
    from forecast_platform.lambda_handler import handler

    respx.get(NEM_SUMMARY_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    assert handler({}, None) == {"fetched": 2, "written": 2}
    assert len(S3Store(bucket=BUCKET, region_name=REGION).read_region("NSW1")) == 1


@respx.mock
def test_handler_run_twice_writes_nothing_the_second_time(bucket):
    from forecast_platform.lambda_handler import handler

    respx.get(NEM_SUMMARY_URL).mock(return_value=httpx.Response(200, json=FIXTURE))
    handler({}, None)
    assert handler({}, None) == {"fetched": 2, "written": 0}


@respx.mock
def test_handler_raises_when_aemo_fails(bucket):
    # Unlike the CLI, which exits 1 so a workflow stays green, the Lambda
    # raises so EventBridge records the failure and the error metric moves.
    from forecast_platform.lambda_handler import handler

    respx.get(NEM_SUMMARY_URL).mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        handler({}, None)


def test_handler_raises_when_the_bucket_variable_is_unset(monkeypatch):
    # A Lambda that silently writes nowhere is worse than one that fails.
    monkeypatch.delenv("OBSERVATIONS_BUCKET", raising=False)
    from forecast_platform.lambda_handler import handler

    with pytest.raises(RuntimeError, match="OBSERVATIONS_BUCKET"):
        handler({}, None)
