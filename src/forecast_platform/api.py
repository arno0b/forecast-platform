"""HTTP interface.

The contract defined here is final for the life of the project. Phase 4
replaces the model behind it; this file should not need to change when that
happens. That is the whole point of fixing the contract before the model.
"""

import time
from datetime import datetime

from fastapi import FastAPI, Response
from pydantic import BaseModel, Field

from forecast_platform.forecaster import DISPATCH_INTERVAL, MODEL_NAME, forecast
from forecast_platform.metrics import LATENCY, REQUESTS, render
from forecast_platform.models import Observation

app = FastAPI(title="forecast-platform", version="0.1.0")


class PredictRequest(BaseModel):
    region_id: str
    horizon: int = Field(gt=0, le=288, description="Intervals ahead to forecast.")
    history: list[Observation] = Field(min_length=1)


class Prediction(BaseModel):
    settlement_date: datetime
    predicted_demand: float


class PredictResponse(BaseModel):
    region_id: str
    model: str
    horizon: int
    predictions: list[Prediction]


@app.get("/healthz")
def healthz() -> dict:
    """Liveness. The process is running. Says nothing about usefulness."""
    return {"status": "ok"}


@app.get("/readyz")
def readyz() -> dict:
    """Readiness. In Phase 1a the model is a pure function with nothing to
    load, so this is always ready. Phase 4 makes it meaningful: it will fail
    until model weights are loaded and the online learner has caught up on
    the gap since the cluster was last running."""
    return {"status": "ready", "model": MODEL_NAME}


@app.post("/predict", response_model=PredictResponse)
def predict(request: PredictRequest) -> PredictResponse:
    started = time.perf_counter()
    values = forecast(request.history, request.horizon)
    # The forecaster sorts internally, so take the last timestamp from the
    # sorted view rather than trusting the request order here too.
    last = max(o.settlement_date for o in request.history)
    predictions = [
        Prediction(
            settlement_date=last + DISPATCH_INTERVAL * (i + 1),
            predicted_demand=value,
        )
        for i, value in enumerate(values)
    ]
    LATENCY.labels(endpoint="/predict").observe(time.perf_counter() - started)
    REQUESTS.labels(endpoint="/predict", status="200").inc()
    return PredictResponse(
        region_id=request.region_id,
        model=MODEL_NAME,
        horizon=request.horizon,
        predictions=predictions,
    )


@app.get("/metrics")
def metrics() -> Response:
    body, content_type = render()
    return Response(content=body, media_type=content_type)
