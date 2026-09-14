from forecast_platform.metrics import LATENCY, REQUESTS, render


def test_counter_is_named_as_the_spec_requires():
    REQUESTS.labels(endpoint="/predict", status="200").inc()
    body, _ = render()
    assert b"forecast_requests_total" in body


def test_histogram_is_named_as_the_spec_requires():
    LATENCY.labels(endpoint="/predict").observe(0.01)
    body, _ = render()
    assert b"forecast_request_duration_seconds" in body


def test_render_returns_the_prometheus_content_type():
    _, content_type = render()
    assert content_type.startswith("text/plain")
