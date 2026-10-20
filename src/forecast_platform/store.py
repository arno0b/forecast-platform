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
import io
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

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


# --------------------------------------------------------------------------
# Shared serialisation, so both stores produce byte-identical CSV and a human
# can diff an S3 object against a local file.
# --------------------------------------------------------------------------


def _row_of(observation: Observation) -> dict:
    return {
        "settlement_date": observation.settlement_date.isoformat(),
        "region_id": observation.region_id,
        "total_demand": observation.total_demand,
        "price": observation.price,
        "scheduled_generation": observation.scheduled_generation,
        "semi_scheduled_generation": observation.semi_scheduled_generation,
    }


def _observation_of(row: dict) -> Observation:
    return Observation(
        settlement_date=datetime.fromisoformat(row["settlement_date"]),
        region_id=row["region_id"],
        total_demand=float(row["total_demand"]),
        price=float(row["price"]),
        scheduled_generation=float(row["scheduled_generation"]),
        semi_scheduled_generation=float(row["semi_scheduled_generation"]),
    )


def _serialise(observations: list[Observation]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    for observation in observations:
        writer.writerow(_row_of(observation))
    return buffer.getvalue()


def _deserialise(text: str) -> list[Observation]:
    if not text.strip():
        return []
    return [_observation_of(row) for row in csv.DictReader(io.StringIO(text))]


class Store(Protocol):
    """What the ingester and the service depend on.

    CsvStore and S3Store both satisfy this, which is what lets the Lambda and
    the CLI share one code path.
    """

    def append(self, observations: Iterable[Observation]) -> int: ...

    def read_region(self, region_id: str) -> list[Observation]: ...


class S3Store:
    """Append-only observation storage in S3.

    Same object layout as CsvStore: one CSV per region per MARKET date, keyed
    from the observation's own timestamp. Deriving the key from a UTC date
    would split every market day across two objects at 10am, because AEMO
    publishes in AEST.

    S3 has no append, only replace, so writing means read-modify-write. That
    is a lost-update race if two Lambda invocations land together, and the
    rows lost cannot be refetched because AEMO only serves the current
    interval. The write is therefore conditional: IfMatch on the ETag we read,
    or IfNoneMatch when creating. A competing write fails the precondition and
    we retry against the newer object rather than overwriting it.
    """

    MAX_ATTEMPTS = 5

    def __init__(
        self,
        bucket: str,
        prefix: str = "observations",
        region_name: str = "ap-southeast-2",
        client=None,
    ):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._client = client or boto3.client("s3", region_name=region_name)

    def _key_for(self, observation: Observation) -> str:
        day = observation.settlement_date.date().isoformat()
        return f"{self.prefix}/{observation.region_id.lower()}/{day}.csv"

    def _region_prefix(self, region_id: str) -> str:
        return f"{self.prefix}/{region_id.lower()}/"

    def _get(self, key: str) -> tuple[list[Observation], str | None]:
        """Observations at this key and its ETag, or ([], None) if absent."""
        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
        except self._client.exceptions.NoSuchKey:
            return [], None
        body = response["Body"].read().decode("utf-8")
        return _deserialise(body), response.get("ETag")

    def append(self, observations: Iterable[Observation]) -> int:
        seen: set[tuple[str, str]] = set()
        batch: list[Observation] = []
        for observation in observations:
            if observation.key() in seen:
                continue
            seen.add(observation.key())
            batch.append(observation)
        if not batch:
            return 0

        by_key: dict[str, list[Observation]] = {}
        for observation in batch:
            by_key.setdefault(self._key_for(observation), []).append(observation)

        return sum(self._merge_write(k, v) for k, v in by_key.items())

    def _merge_write(self, key: str, incoming: list[Observation]) -> int:
        for _ in range(self.MAX_ATTEMPTS):
            existing, etag = self._get(key)
            already = {o.key() for o in existing}
            new = [o for o in incoming if o.key() not in already]
            if not new:
                return 0

            merged = sorted(existing + new, key=lambda o: o.settlement_date)
            condition = {"IfMatch": etag} if etag else {"IfNoneMatch": "*"}
            try:
                self._client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=_serialise(merged).encode("utf-8"),
                    ContentType="text/csv",
                    **condition,
                )
                return len(new)
            except ClientError as error:
                code = error.response.get("Error", {}).get("Code")
                if code in ("PreconditionFailed", "ConditionalRequestConflict"):
                    continue  # someone else wrote; re-read and merge again
                raise
        raise RuntimeError(
            f"gave up after {self.MAX_ATTEMPTS} attempts writing {key}; "
            "something is writing this object continuously"
        )

    def read_region(self, region_id: str) -> list[Observation]:
        observations: list[Observation] = []
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(
            Bucket=self.bucket, Prefix=self._region_prefix(region_id)
        ):
            for obj in page.get("Contents", []):
                if not obj["Key"].endswith(".csv"):
                    continue
                found, _ = self._get(obj["Key"])
                observations.extend(found)
        observations.sort(key=lambda o: o.settlement_date)
        return observations
