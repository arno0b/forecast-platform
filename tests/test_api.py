from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from forecast_platform.api import app

client = TestClient(app)


def _payload(count: int = 20, horizon: int = 3) -> dict:
    start = datetime(2026, 9, 1, 0, 0)
    return {
        "region_id": "NSW1",
        "horizon": horizon,
        "history": [
            {
                "settlement_date": (start + timedelta(minutes=5 * i)).isoformat(),
                "region_id": "NSW1",
                "total_demand": float(i),
                "price": 60.0,
                "scheduled_generation": 4000.0,
                "semi_scheduled_generation": 800.0,
            }
            for i in range(count)
        ],
    }


def test_healthz_is_up():
    assert client.get("/healthz").status_code == 200


def test_readyz_is_ready():
    response = client.get("/readyz")
    assert response.status_code == 200
    assert response.json()["model"] == "seasonal-naive"


def test_predict_returns_one_prediction_per_horizon_step():
    response = client.post("/predict", json=_payload(horizon=3))
    assert response.status_code == 200
    body = response.json()
    assert len(body["predictions"]) == 3
    assert body["model"] == "seasonal-naive"
    assert body["region_id"] == "NSW1"


def test_predict_timestamps_continue_from_the_last_observation():
    response = client.post("/predict", json=_payload(count=20, horizon=2))
    predicted = [p["settlement_date"] for p in response.json()["predictions"]]
    # Last observation is 00:00 + 19*5min = 01:35, so the next two intervals
    # are 01:40 and 01:45.
    assert predicted[0].endswith("01:40:00")
    assert predicted[1].endswith("01:45:00")


def test_predict_rejects_empty_history_with_422_not_500():
    payload = _payload()
    payload["history"] = []
    assert client.post("/predict", json=payload).status_code == 422


def test_predict_rejects_a_zero_horizon_with_422():
    payload = _payload()
    payload["horizon"] = 0
    assert client.post("/predict", json=payload).status_code == 422


def test_metrics_endpoint_exposes_the_counter():
    client.post("/predict", json=_payload())
    body = client.get("/metrics").text
    assert "forecast_requests_total" in body
