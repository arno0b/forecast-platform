"""CLI entrypoint: fetch the current NEM summary and store it.

Exits 1 rather than raising when AEMO is unreachable. A missed interval is
a gap to backfill later, not a reason for a red build every time AEMO has
a bad minute, so the workflow that calls this decides how to react.
"""

import argparse
import sys
from pathlib import Path

import httpx

from forecast_platform.aemo import fetch_summary
from forecast_platform.store import CsvStore

DEFAULT_DATA_DIR = Path("data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest AEMO NEM demand data.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Directory to store observations in.",
    )
    args = parser.parse_args(argv)

    try:
        observations = fetch_summary()
    except httpx.HTTPError as error:
        print(f"fetch failed: {error}", file=sys.stderr)
        return 1

    written = CsvStore(args.data_dir).append(observations)
    print(f"fetched {len(observations)}, wrote {written}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
