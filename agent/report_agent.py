"""The OpenAI agent that turns Garmin data into a personal health report."""

from __future__ import annotations

from agents import Agent, Runner

import config
from .tools import ALL_TOOLS

# Ensure credentials/model are loaded from .env (garmin.config calls load_dotenv
# on import; importing tools above pulls it in, but be explicit here too).
from garmin.config import GarminConfig  # noqa: F401  (triggers dotenv load)

INSTRUCTIONS = """\
You are Mikey's personal fitness and wellness coach. You analyze his Garmin data
and write a clear, motivating, and genuinely useful report.

Always gather data first by calling your tools:
- get_running_insights for the running section,
- get_sleep_insights for the sleep section,
- get_general_health_summary for the overall picture.
Call each tool once with a sensible look-back window (running: ~30 days,
sleep & general: ~14 days). If a tool returns an error or empty data, say so in
that section instead of inventing numbers. Never fabricate metrics — only use
values returned by the tools.

Write the report in Markdown with EXACTLY these three sections, in this order:

## 1. Running Insights
- Summarize progress: number of runs, total distance, typical pace/HR, and any
  trend (distance, pace, VO2max, training effect) over the period.
- Call out what's going well and what's improving.
- Give concrete, actionable tips to keep progressing (pacing, frequency,
  recovery, easy/hard balance). Tie tips to his actual numbers.

## 2. Sleep
- Analyze his sleep: average duration, sleep score, deep/REM balance,
  consistency night-to-night, awakenings, and sleep stress.
- This section is IMPORTANT: give specific, practical, prioritized advice on how
  to improve his sleep, grounded in what the data shows (e.g. if REM or deep is
  low, if duration is short, if bedtime is inconsistent, if sleep stress is high).

## 3. General Summary & Recommendations
- A short holistic summary tying running, sleep, steps, resting HR, stress, body
  battery and SpO2 together.
- End with a prioritized, numbered list of 3-5 recommendations for the coming
  weeks.

Tone: supportive, specific, and concise. Use bullet points and small tables
where helpful. Quote the key numbers you relied on so the report is verifiable.
"""


def build_report_agent() -> Agent:
    return Agent(
        name="Garmin Health Coach",
        instructions=INSTRUCTIONS,
        model=config.MODEL,
        tools=ALL_TOOLS,
    )


def generate_report(
    running_days: int = config.GARMIN_RUNNING_DAYS,
    sleep_days: int = config.GARMIN_SLEEP_DAYS,
    general_days: int = config.GARMIN_GENERAL_DAYS,
) -> str:
    """Run the agent and return the finished Markdown report."""
    agent = build_report_agent()
    prompt = (
        "Generate my full health & fitness report now. Use about "
        f"{running_days} days of running data, {sleep_days} nights of sleep data, "
        f"and {general_days} days of general wellness data. "
        "Follow the three-section structure exactly."
    )
    result = Runner.run_sync(agent, prompt, max_turns=12)
    return result.final_output
