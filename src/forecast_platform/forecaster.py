"""Seasonal-naive baseline forecaster.

The forecast for a future time is the demand observed one season (one week)
before it. Electricity demand is strongly weekly: Tuesday 6pm resembles last
Tuesday 6pm far more than it resembles this morning.

Lookup is by TIMESTAMP, never by row position. Observations arrive at
irregular intervals because ingestion samples rather than capturing every
dispatch interval, and because scheduled runs get dropped. Counting back a
fixed number of rows would silently read the wrong time of day. Indexing by
time is also immune to daylight saving, which matters if this is ever
pointed at a market that observes it.

No I/O. Give it observations, get numbers back.
"""

import bisect
from datetime import datetime, timedelta

from forecast_platform.models import Observation

MODEL_NAME = "seasonal-naive"

SEASON = timedelta(days=7)
DISPATCH_INTERVAL = timedelta(minutes=5)
TOLERANCE = timedelta(minutes=15)


def forecast(
    history: list[Observation],
    horizon: int,
    season: timedelta = SEASON,
    interval: timedelta = DISPATCH_INTERVAL,
    tolerance: timedelta = TOLERANCE,
) -> list[float]:
    """Forecast the next `horizon` intervals of demand.

    For each step, look up the demand one season earlier. If no observation
    sits within `tolerance` of that time, fall back to persistence and repeat
    the most recent value. Persistence covers the cold start, when there is
    not yet a season of history to look back at.
    """
    if not history:
        raise ValueError("history must not be empty")
    if horizon <= 0:
        raise ValueError("horizon must be positive")

    # Never trust the caller's ordering. /predict takes history over HTTP and
    # everything below depends on knowing which observation is most recent.
    ordered = sorted(history, key=lambda o: o.settlement_date)
    times = [o.settlement_date for o in ordered]
    demands = [o.total_demand for o in ordered]
    last = times[-1]

    predictions = []
    for step in range(1, horizon + 1):
        lookup = last + interval * step - season
        value = _nearest(times, demands, lookup, tolerance)
        predictions.append(demands[-1] if value is None else value)
    return predictions


def _nearest(
    times: list[datetime],
    demands: list[float],
    target: datetime,
    tolerance: timedelta,
) -> float | None:
    """Demand nearest to `target`, or None if nothing is within tolerance.

    Binary search, so this stays cheap as history grows. Only the two
    observations bracketing the target can be the nearest one.
    """
    index = bisect.bisect_left(times, target)
    best_value: float | None = None
    best_delta: timedelta | None = None
    for candidate in (index - 1, index):
        if 0 <= candidate < len(times):
            delta = abs(times[candidate] - target)
            if best_delta is None or delta < best_delta:
                best_delta = delta
                best_value = demands[candidate]
    if best_delta is None or best_delta > tolerance:
        return None
    return best_value
