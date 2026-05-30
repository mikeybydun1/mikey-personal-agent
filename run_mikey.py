"""CLI: run the full Mikey Agent pipeline.

Generates the Garmin health report, the weekly AI & tech briefing, and the stock
watch-list insights, then sends a single combined email.

Tunable content (model, tech topics, stock watch-list) lives in config.py.

Examples
--------
  python run_mikey.py
  python run_mikey.py --running-days 60 --sleep-days 21
  python run_mikey.py --no-email
  python run_mikey.py --to someone@example.com
"""

from __future__ import annotations

import argparse
import logging
import sys

import config
from agent import run_mikey_pipeline


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run the Mikey Agent: health + tech + stocks -> one email.")
    p.add_argument("--running-days", type=int, default=config.GARMIN_RUNNING_DAYS,
                   help=f"Look-back window for running (default {config.GARMIN_RUNNING_DAYS}).")
    p.add_argument("--sleep-days", type=int, default=config.GARMIN_SLEEP_DAYS,
                   help=f"Look-back window for sleep (default {config.GARMIN_SLEEP_DAYS}).")
    p.add_argument("--general-days", type=int, default=config.GARMIN_GENERAL_DAYS,
                   help=f"Look-back window for wellness (default {config.GARMIN_GENERAL_DAYS}).")
    p.add_argument("--no-email", action="store_true", help="Generate reports but do not send the email.")
    p.add_argument("--no-save", action="store_true", help="Do not save the Markdown reports to reports/.")
    p.add_argument("--to", type=str, help="Override the recipient email address.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)

    args = parse_args(argv)

    print("Running Mikey Agent: Garmin health + weekly tech briefing + stock insights ...\n")
    result = run_mikey_pipeline(
        running_days=args.running_days,
        sleep_days=args.sleep_days,
        general_days=args.general_days,
        send_email=not args.no_email,
        recipient=args.to,
        save=not args.no_save,
    )

    print(f"Reports generated: {len(result.sections)} section(s).")
    for err in result.errors:
        print(f"  warning: {err}", file=sys.stderr)

    if result.emailed_to:
        print(f"Combined email sent to: {result.emailed_to}")
    elif not args.no_email:
        print("Email was requested but not sent — see warnings above.", file=sys.stderr)
        return 1

    return 0 if not result.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
