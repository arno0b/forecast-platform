"""Prometheus metric definitions.

Only the two request-level metrics in Phase 1a. forecast_prediction_mape and
forecast_drift_score arrive in Phase 3, once there is enough stored history
to compare a forecast against what actually happened.
"""

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

REQUESTS = Counter(
    "forecast_requests_total",
    "Total forecast API requests.",
    ("endpoint", "status"),
)

LATENCY = Histogram(
    "forecast_request_duration_seconds",
    "Forecast API request duration in seconds.",
    ("endpoint",),
)


def render() -> tuple[bytes, str]:
    """The exposition payload and its content type."""
    return generate_latest(), CONTENT_TYPE_LATEST
