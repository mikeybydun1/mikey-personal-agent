"""CLI entry point: fetch Garmin Connect data into local JSON files.

Examples
--------
  # last 7 days of everything (default)
  python fetch_garmin.py

  # last 30 days
  python fetch_garmin.py --days 30

  # an explicit date range
  python fetch_garmin.py --start 2026-01-01 --end 2026-01-31

  # only sleep and heart-rate, skip activities/profile
  python fetch_garmin.py --days 14 --categories sleep heart_rate \
      --no-activities --no-profile
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date, datetime, timedelta

from garmin import GarminClient, GarminConfig, GarminFetcher
from garmin.fetcher import DAILY_ENDPOINTS, ISO


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Garmin Connect data to JSON.")
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days back from --end to fetch (default: 7). Ignored if --start is given.",
    )
    parser.add_argument("--start", type=str, help="Start date YYYY-MM-DD (inclusive).")
    parser.add_argument(
        "--end",
        type=str,
        help="End date YYYY-MM-DD (inclusive). Defaults to today.",
    )
    parser.add_argument(
        "--categories",
        nargs="+",
        choices=sorted(DAILY_ENDPOINTS),
        help="Subset of daily categories to fetch (default: all).",
    )
    parser.add_argument("--no-activities", action="store_true", help="Skip activities.")
    parser.add_argument("--no-profile", action="store_true", help="Skip profile/account data.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging.")
    return parser.parse_args(argv)


def resolve_range(args: argparse.Namespace) -> tuple[date, date]:
    end = datetime.strptime(args.end, ISO).date() if args.end else date.today()
    if args.start:
        start = datetime.strptime(args.start, ISO).date()
    else:
        start = end - timedelta(days=max(args.days - 1, 0))
    if start > end:
        raise SystemExit(f"start date {start} is after end date {end}")
    return start, end


def main(argv: list[str] | None = None) -> int:
    # Render non-ASCII names/values cleanly on the Windows console.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    args = parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    try:
        config = GarminConfig.from_env()
    except RuntimeError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    start, end = resolve_range(args)

    print(f"Logging in to Garmin Connect as {config.email} ...")
    client = GarminClient(config)
    client.login()

    fetcher = GarminFetcher(client.api, config.data_dir)

    print(f"Fetching daily metrics {start.strftime(ISO)} -> {end.strftime(ISO)} ...")
    fetcher.fetch_range(start, end, args.categories)

    if not args.no_activities:
        fetcher.fetch_activities(start, end)

    if not args.no_profile:
        print("Fetching profile / account data ...")
        fetcher.fetch_profile()

    print(f"Done. Data written under: {config.data_dir.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
