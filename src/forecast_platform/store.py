"""Append-only observation storage on the local filesystem.

One CSV per region per market date, which keeps files small, makes git
diffs readable, and means a day can be reprocessed without touching any
other.

Timestamps are AEMO market time, which is AEST (UTC+10) year-round. They
are NOT UTC and must not be converted as if they were. The NEM does not
observe daylight saving, and that is load-bearing: the forecaster finds
"one week ago" by counting back 2016 five-minute rows, which only holds if
every day has exactly 288 intervals. A DST-observing timezone would delete
an hour in October and duplicate one in April, silently misaligning the
seasonal lookup twice a year.

This module does not know AEMO exists. It stores Observations.
"""

import csv
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from forecast_platform.models import Observation

FIELDS = [
    "settlement_date",
    "region_id",
    "total_demand",
    "price",
    "scheduled_generation",
    "semi_scheduled_generation",
]


class CsvStore:
    def __init__(self, root: Path):
        self.root = Path(root)

    def _region_dir(self, region_id: str) -> Path:
        return self.root / region_id.lower()

    def _path_for(self, observation: Observation) -> Path:
        day = observation.settlement_date.date().isoformat()
        return self._region_dir(observation.region_id) / f"{day}.csv"

    def append(self, observations: Iterable[Observation]) -> int:
        """Write observations that are not already stored.

        Returns the number actually written. Deduplicates both against what
        is on disk and within the batch itself, so an overlapping schedule
        or a retried run cannot create duplicate rows.
        """
        seen = set()
        batch: list[Observation] = []
        for observation in observations:
            if observation.key() in seen:
                continue
            seen.add(observation.key())
            batch.append(observation)

        # Cache each file's existing keys so a batch touching one day reads
        # that file once rather than once per observation. A Phase 2 backfill
        # is 288 observations against a single file; without this it is
        # quadratic on exactly the case it will be used for.
        written = 0
        existing_by_path: dict[Path, set[tuple[str, str]]] = {}
        for observation in batch:
            path = self._path_for(observation)
            if path not in existing_by_path:
                existing_by_path[path] = {o.key() for o in self._read_file(path)}
            if observation.key() in existing_by_path[path]:
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            is_new_file = not path.exists()
            with path.open("a", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                if is_new_file:
                    writer.writeheader()
                writer.writerow(
                    {
                        "settlement_date": observation.settlement_date.isoformat(),
                        "region_id": observation.region_id,
                        "total_demand": observation.total_demand,
                        "price": observation.price,
                        "scheduled_generation": observation.scheduled_generation,
                        "semi_scheduled_generation": observation.semi_scheduled_generation,
                    }
                )
            existing_by_path[path].add(observation.key())
            written += 1
        return written

    def read_region(self, region_id: str) -> list[Observation]:
        """Every stored observation for a region, oldest first."""
        directory = self._region_dir(region_id)
        if not directory.exists():
            return []
        observations: list[Observation] = []
        for path in sorted(directory.glob("*.csv")):
            observations.extend(self._read_file(path))
        observations.sort(key=lambda o: o.settlement_date)
        return observations

    @staticmethod
    def _read_file(path: Path) -> list[Observation]:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8") as handle:
            return [
                Observation(
                    settlement_date=datetime.fromisoformat(row["settlement_date"]),
                    region_id=row["region_id"],
                    total_demand=float(row["total_demand"]),
                    price=float(row["price"]),
                    scheduled_generation=float(row["scheduled_generation"]),
                    semi_scheduled_generation=float(row["semi_scheduled_generation"]),
                )
                for row in csv.DictReader(handle)
            ]
