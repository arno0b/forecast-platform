"""AWS Lambda entry point: fetch the current NEM summary and store it in S3.

This is the other half of a pair. `ingest.py` is the CLI, invoked by a
GitHub Actions workflow; this is the Lambda, invoked by EventBridge every
five minutes. Both wire the same `aemo` client to the same `Store`
interface, so the ingestion logic exists once.

They differ deliberately in exactly one way: how they treat failure.

The CLI returns exit code 1 so the calling workflow can decide whether a
missed interval is worth a red build. A Lambda has no such caller to
decide, so it raises. An unhandled exception is what makes EventBridge
record the invocation as failed and move the Errors metric, which is the
only thing that will ever tell you ingestion has stopped. Swallowing the
error here would produce a function that reports success forever while
quietly storing nothing, which is the failure this whole phase exists to
fix.
"""

import logging
import os

from forecast_platform.aemo import fetch_summary
from forecast_platform.store import S3Store

BUCKET_VAR = "OBSERVATIONS_BUCKET"

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict, context) -> dict:
    """Fetch one AEMO snapshot and append it to S3.

    Returns the number of observations fetched and the number actually
    written after deduplication. Those two numbers differing is normal and
    expected: AEMO publishes the same interval repeatedly between dispatch
    runs, so a `written` of zero means nothing new had been published yet,
    not that something went wrong.
    """
    bucket = os.environ.get(BUCKET_VAR)
    if not bucket:
        raise RuntimeError(
            f"{BUCKET_VAR} is not set. Refusing to run, because a function "
            "that cannot name its destination would otherwise fetch data and "
            "discard it while reporting success."
        )

    observations = fetch_summary()
    written = S3Store(bucket=bucket).append(observations)

    logger.info(
        "ingest complete",
        extra={"fetched": len(observations), "written": written, "bucket": bucket},
    )
    print(f"fetched {len(observations)}, wrote {written}")

    return {"fetched": len(observations), "written": written}
