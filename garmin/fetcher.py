"""Fetch and persist Garmin Connect data.

The fetcher pulls the data categories most relevant to a personal health/fitness
agent — sleep, steps, heart rate, stress, body battery, HRV, respiration, SpO2,
training readiness, intensity minutes, daily summary stats — for each day in a
range, plus activities (running, etc.) and the user profile.

Each category/day is written as a JSON file under ``data/<category>/<date>.json``
so the agent layer (built later) can consume them without re-hitting the API.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Callable

from garminconnect import Garmin

logger = logging.getLogger(__name__)

ISO = "%Y-%m-%d"


# Per-day endpoints: category name -> function(api, date_str) -> json-able data.
# Each is wrapped in error handling so a single failing endpoint (e.g. a device
# that never recorded SpO2) does not abort the whole run.
DAILY_ENDPOINTS: dict[str, Callable[[Garmin, str], Any]] = {
    "sleep": lambda api, d: api.get_sleep_data(d),
    "steps": lambda api, d: api.get_steps_data(d),
    "heart_rate": lambda api, d: api.get_heart_rates(d),
    "resting_hr": lambda api, d: api.get_rhr_day(d),
    "stress": lambda api, d: api.get_stress_data(d),
    "body_battery": lambda api, d: api.get_body_battery(d, d),
    "hrv": lambda api, d: api.get_hrv_data(d),
    "respiration": lambda api, d: api.get_respiration_data(d),
    "spo2": lambda api, d: api.get_spo2_data(d),
    "intensity_minutes": lambda api, d: api.get_intensity_minutes_data(d),
    "floors": lambda api, d: api.get_floors(d),
    "training_readiness": lambda api, d: api.get_training_readiness(d),
    "daily_summary": lambda api, d: api.get_user_summary(d),
    "stats_and_body": lambda api, d: api.get_stats_and_body(d),
}


def daterange(start: date, end: date):
    """Yield each date from ``start`` to ``end`` inclusive."""
    days = (end - start).days
    for offset in range(days + 1):
        yield start + timedelta(days=offset)


class GarminFetcher:
    def __init__(self, api: Garmin, data_dir: Path):
        self.api = api
        self.data_dir = Path(data_dir)

    # ---- persistence helpers -------------------------------------------------

    def _write(self, category: str, name: str, payload: Any) -> Path:
        out_dir = self.data_dir / category
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"{name}.json"
        with path.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False, default=str)
        return path

    # ---- daily metrics -------------------------------------------------------

    def fetch_day(self, day: date, categories: list[str] | None = None) -> dict[str, bool]:
        """Fetch all configured daily endpoints for a single day.

        Returns a map of category -> whether it was fetched successfully.
        """
        day_str = day.strftime(ISO)
        wanted = categories or list(DAILY_ENDPOINTS)
        results: dict[str, bool] = {}

        for category in wanted:
            endpoint = DAILY_ENDPOINTS.get(category)
            if endpoint is None:
                logger.warning("Unknown daily category '%s' — skipping", category)
                results[category] = False
                continue
            try:
                data = endpoint(self.api, day_str)
                self._write(category, day_str, data)
                results[category] = True
                logger.info("  %-20s %s  ok", category, day_str)
            except Exception as exc:  # noqa: BLE001 — keep going on any endpoint failure
                results[category] = False
                logger.warning("  %-20s %s  failed: %s", category, day_str, exc)

        return results

    def fetch_range(
        self,
        start: date,
        end: date,
        categories: list[str] | None = None,
    ) -> None:
        """Fetch daily metrics for every day from ``start`` to ``end`` inclusive."""
        for day in daterange(start, end):
            logger.info("Fetching daily metrics for %s", day.strftime(ISO))
            self.fetch_day(day, categories)

    # ---- activities (running, cycling, etc.) ---------------------------------

    def fetch_activities(self, start: date, end: date) -> int:
        """Fetch all activities within the date range and save them.

        Saves a combined index plus one detail file per activity (which includes
        per-activity splits and summary metrics).
        """
        start_str, end_str = start.strftime(ISO), end.strftime(ISO)
        logger.info("Fetching activities from %s to %s", start_str, end_str)

        try:
            activities = self.api.get_activities_by_date(start_str, end_str)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to list activities: %s", exc)
            return 0

        self._write("activities", f"index_{start_str}_to_{end_str}", activities)

        for activity in activities:
            activity_id = activity.get("activityId")
            if activity_id is None:
                continue
            try:
                details = self.api.get_activity(activity_id)
                self._write("activities", f"activity_{activity_id}", details)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Failed to fetch activity %s: %s", activity_id, exc)

        logger.info("Saved %d activities", len(activities))
        return len(activities)

    # ---- profile / account-level data ----------------------------------------

    def fetch_profile(self) -> None:
        """Fetch account-level data that is not tied to a single day."""
        profile_endpoints: dict[str, Callable[[], Any]] = {
            "user_profile": self.api.get_user_profile,
            "userprofile_settings": self.api.get_userprofile_settings,
            "devices": self.api.get_devices,
            "personal_records": self.api.get_personal_record,
        }
        for name, endpoint in profile_endpoints.items():
            try:
                self._write("profile", name, endpoint())
                logger.info("  profile/%-22s ok", name)
            except Exception as exc:  # noqa: BLE001
                logger.warning("  profile/%-22s failed: %s", name, exc)
