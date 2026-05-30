"""Function tools that let the agent fetch Garmin data on demand.

Each tool logs in once (tokens are cached by ``GarminClient``), pulls the raw
data via the Garmin API, persists the raw JSON under ``data/`` (so the fetcher
stays the single source of truth), and returns a **condensed** summary so the
LLM reasons over compact, relevant numbers instead of huge raw payloads.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from agents import function_tool

from garmin import GarminClient, GarminConfig, GarminFetcher
from garmin.fetcher import ISO, daterange

logger = logging.getLogger(__name__)

# Garmin activity typeKeys that count as "running" for the running section.
_RUNNING_TYPES = {
    "running",
    "treadmill_running",
    "trail_running",
    "track_running",
    "indoor_running",
    "virtual_run",
    "obstacle_run",
    "ultra_run",
}


# --------------------------------------------------------------------------- #
# Shared, lazily-logged-in Garmin access
# --------------------------------------------------------------------------- #
class _Garmin:
    """Process-wide singleton holding one logged-in Garmin session."""

    _fetcher: GarminFetcher | None = None

    @classmethod
    def fetcher(cls) -> GarminFetcher:
        if cls._fetcher is None:
            config = GarminConfig.from_env()
            client = GarminClient(config)
            client.login()
            cls._fetcher = GarminFetcher(client.api, config.data_dir)
        return cls._fetcher


def _round(value: Any, ndigits: int = 1) -> Any:
    return round(value, ndigits) if isinstance(value, (int, float)) else value


def _secs_to_hours(seconds: Any) -> float | None:
    return round(seconds / 3600, 2) if isinstance(seconds, (int, float)) else None


def _pace_min_per_km(speed_mps: Any) -> str | None:
    """Convert m/s to a 'mm:ss /km' pace string."""
    if not isinstance(speed_mps, (int, float)) or speed_mps <= 0:
        return None
    sec_per_km = 1000.0 / speed_mps
    minutes, seconds = divmod(int(round(sec_per_km)), 60)
    return f"{minutes}:{seconds:02d} /km"


# --------------------------------------------------------------------------- #
# Tools
# --------------------------------------------------------------------------- #
@function_tool
def get_running_insights(days: int = 30) -> dict:
    """Fetch the user's running activities over the last N days from Garmin.

    Returns each run's distance, duration, pace, heart rate, VO2max and training
    effect, plus aggregate totals and trend, for building running insights.

    Args:
        days: How many days back to include (default 30).
    """
    fetcher = _Garmin.fetcher()
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))

    try:
        activities = fetcher.api.get_activities_by_date(start.strftime(ISO), end.strftime(ISO))
    except Exception as exc:  # noqa: BLE001
        return {"error": f"Failed to fetch activities: {exc}"}

    fetcher._write("activities", f"index_{start.strftime(ISO)}_to_{end.strftime(ISO)}", activities)

    runs = []
    for a in activities:
        type_key = (a.get("activityType") or {}).get("typeKey", "")
        if type_key not in _RUNNING_TYPES:
            continue
        distance_km = _round((a.get("distance") or 0) / 1000.0, 2)
        duration_min = _round((a.get("duration") or 0) / 60.0, 1)
        runs.append(
            {
                "date": (a.get("startTimeLocal") or "")[:10],
                "name": a.get("activityName"),
                "type": type_key,
                "distance_km": distance_km,
                "duration_min": duration_min,
                "avg_pace": _pace_min_per_km(a.get("averageSpeed")),
                "avg_hr": a.get("averageHR"),
                "max_hr": a.get("maxHR"),
                "calories": a.get("calories"),
                "elevation_gain_m": _round(a.get("elevationGain")),
                "avg_cadence_spm": _round(a.get("averageRunningCadenceInStepsPerMinute")),
                "vo2max": a.get("vO2MaxValue"),
                "aerobic_training_effect": _round(a.get("aerobicTrainingEffect")),
                "anaerobic_training_effect": _round(a.get("anaerobicTrainingEffect")),
                "training_effect_label": a.get("trainingEffectLabel"),
            }
        )

    runs.sort(key=lambda r: r["date"])
    total_km = round(sum(r["distance_km"] or 0 for r in runs), 2)
    total_min = round(sum(r["duration_min"] or 0 for r in runs), 1)
    hrs = [r["avg_hr"] for r in runs if r["avg_hr"]]
    vo2 = [r["vo2max"] for r in runs if r["vo2max"]]

    return {
        "period": {"start": start.strftime(ISO), "end": end.strftime(ISO), "days": days},
        "num_runs": len(runs),
        "total_distance_km": total_km,
        "total_duration_min": total_min,
        "avg_distance_per_run_km": round(total_km / len(runs), 2) if runs else 0,
        "avg_heart_rate": round(sum(hrs) / len(hrs)) if hrs else None,
        "latest_vo2max": vo2[-1] if vo2 else None,
        "vo2max_trend": (
            "improving" if len(vo2) >= 2 and vo2[-1] > vo2[0]
            else "declining" if len(vo2) >= 2 and vo2[-1] < vo2[0]
            else "stable" if vo2 else None
        ),
        "runs": runs,
    }


@function_tool
def get_sleep_insights(days: int = 14) -> dict:
    """Fetch the user's sleep data over the last N days from Garmin.

    Returns per-night sleep duration, deep/light/REM/awake breakdown, sleep
    score, resting respiration, sleep stress, and Garmin's own feedback, plus
    averages, for building the sleep analysis and improvement advice.

    Args:
        days: How many nights back to include (default 14).
    """
    fetcher = _Garmin.fetcher()
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))

    nights = []
    for day in daterange(start, end):
        day_str = day.strftime(ISO)
        try:
            data = fetcher.api.get_sleep_data(day_str)
        except Exception as exc:  # noqa: BLE001
            logger.warning("sleep fetch failed for %s: %s", day_str, exc)
            continue
        fetcher._write("sleep", day_str, data)

        dto = (data or {}).get("dailySleepDTO") or {}
        if not dto.get("sleepTimeSeconds"):
            continue
        scores = dto.get("sleepScores") or {}
        overall = (scores.get("overall") or {}) if isinstance(scores, dict) else {}
        nights.append(
            {
                "date": dto.get("calendarDate", day_str),
                "total_sleep_h": _secs_to_hours(dto.get("sleepTimeSeconds")),
                "deep_h": _secs_to_hours(dto.get("deepSleepSeconds")),
                "light_h": _secs_to_hours(dto.get("lightSleepSeconds")),
                "rem_h": _secs_to_hours(dto.get("remSleepSeconds")),
                "awake_h": _secs_to_hours(dto.get("awakeSleepSeconds")),
                "sleep_score": overall.get("value"),
                "sleep_quality": overall.get("qualifierKey"),
                "awake_count": dto.get("awakeCount"),
                "avg_sleep_stress": dto.get("avgSleepStress"),
                "avg_hr": dto.get("avgHeartRate"),
                "avg_respiration": dto.get("averageRespirationValue"),
                "garmin_feedback": dto.get("sleepScoreFeedback"),
                "garmin_insight": dto.get("sleepScoreInsight"),
            }
        )

    nights.sort(key=lambda n: n["date"])
    durations = [n["total_sleep_h"] for n in nights if n["total_sleep_h"]]
    scores_list = [n["sleep_score"] for n in nights if n["sleep_score"]]
    deep = [n["deep_h"] for n in nights if n["deep_h"] is not None]
    rem = [n["rem_h"] for n in nights if n["rem_h"] is not None]

    return {
        "period": {"start": start.strftime(ISO), "end": end.strftime(ISO), "days": days},
        "nights_recorded": len(nights),
        "avg_sleep_h": round(sum(durations) / len(durations), 2) if durations else None,
        "avg_sleep_score": round(sum(scores_list) / len(scores_list)) if scores_list else None,
        "avg_deep_h": round(sum(deep) / len(deep), 2) if deep else None,
        "avg_rem_h": round(sum(rem) / len(rem), 2) if rem else None,
        "nights": nights,
    }


@function_tool
def get_general_health_summary(days: int = 14) -> dict:
    """Fetch the user's daily wellness summary over the last N days from Garmin.

    Returns per-day steps, resting heart rate, average stress, body battery,
    SpO2, and intensity minutes, plus averages, for the general summary section.

    Args:
        days: How many days back to include (default 14).
    """
    fetcher = _Garmin.fetcher()
    end = date.today()
    start = end - timedelta(days=max(days - 1, 0))

    days_data = []
    for day in daterange(start, end):
        day_str = day.strftime(ISO)
        try:
            d = fetcher.api.get_user_summary(day_str)
        except Exception as exc:  # noqa: BLE001
            logger.warning("daily summary fetch failed for %s: %s", day_str, exc)
            continue
        fetcher._write("daily_summary", day_str, d)
        if not d or not d.get("totalSteps"):
            continue
        days_data.append(
            {
                "date": d.get("calendarDate", day_str),
                "steps": d.get("totalSteps"),
                "step_goal": d.get("dailyStepGoal"),
                "distance_km": _round((d.get("totalDistanceMeters") or 0) / 1000.0, 2),
                "active_calories": d.get("activeKilocalories"),
                "resting_hr": d.get("restingHeartRate"),
                "avg_stress": d.get("averageStressLevel"),
                "max_stress": d.get("maxStressLevel"),
                "body_battery_high": d.get("bodyBatteryHighestValue"),
                "body_battery_low": d.get("bodyBatteryLowestValue"),
                "avg_spo2": d.get("averageSpo2"),
                "intensity_min_moderate": d.get("moderateIntensityMinutes"),
                "intensity_min_vigorous": d.get("vigorousIntensityMinutes"),
                "floors_climbed": d.get("floorsAscended"),
            }
        )

    days_data.sort(key=lambda x: x["date"])

    def _avg(key: str) -> float | None:
        vals = [x[key] for x in days_data if isinstance(x.get(key), (int, float))]
        return round(sum(vals) / len(vals)) if vals else None

    return {
        "period": {"start": start.strftime(ISO), "end": end.strftime(ISO), "days": days},
        "days_recorded": len(days_data),
        "avg_steps": _avg("steps"),
        "avg_resting_hr": _avg("resting_hr"),
        "avg_stress": _avg("avg_stress"),
        "avg_spo2": _avg("avg_spo2"),
        "days": days_data,
    }


ALL_TOOLS = [get_running_insights, get_sleep_insights, get_general_health_summary]
