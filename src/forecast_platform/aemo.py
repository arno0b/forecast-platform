"""Fetch and parse AEMO National Electricity Market summary data.

This module knows two things and nothing else: how to talk to AEMO over
HTTP, and what AEMO's payload looks like. It has no idea where the data
ends up. That seam is what lets the store move to S3 in Phase 2 without
touching any parsing code.
"""

import httpx

from forecast_platform.models import Observation

NEM_SUMMARY_URL = (
    "https://visualisations.aemo.com.au/aemo/apps/api/report/ELEC_NEM_SUMMARY"
)

USER_AGENT = "forecast-platform/0.1 (+https://github.com/arno0b/forecast-platform)"
TIMEOUT_SECONDS = 30.0


def parse_summary(payload: dict) -> list[Observation]:
    """Turn an ELEC_NEM_SUMMARY payload into Observations.

    Raises KeyError if the payload does not carry the expected top-level key,
    because that means AEMO changed their schema and we want a loud failure
    rather than silently ingesting nothing.
    """
    rows = payload["ELEC_NEM_SUMMARY"]
    return [
        Observation(
            settlement_date=row["SETTLEMENTDATE"],
            region_id=row["REGIONID"],
            total_demand=row["TOTALDEMAND"],
            price=row["PRICE"],
            scheduled_generation=row["SCHEDULEDGENERATION"],
            semi_scheduled_generation=row["SEMISCHEDULEDGENERATION"],
        )
        for row in rows
    ]


def fetch_summary(client: httpx.Client | None = None) -> list[Observation]:
    """Fetch the current NEM summary. Raises on any non-2xx response."""
    owned = client is None
    client = client or httpx.Client(
        timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT}
    )
    try:
        response = client.get(NEM_SUMMARY_URL)
        response.raise_for_status()
        return parse_summary(response.json())
    finally:
        if owned:
            client.close()
