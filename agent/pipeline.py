"""Mikey Agent — the orchestrator.

Runs the report-producing agents in sequence and delivers a single combined
email:
  1. Garmin health report   (running / sleep / wellness)
  2. Weekly AI & tech briefing  (web-researched, last 7 days)
  3. Stock watch-list insights  (per-stock news, earnings, metrics + top picks)

Designed to grow: to add a new report, generate its Markdown and append another
``ReportSection`` to ``sections``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

import config
from delivery import EmailConfig, ReportSection, send_combined_email

from .report_agent import generate_report as generate_garmin_report
from .stock_agent import generate_stock_report
from .tech_agent import generate_tech_report

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    garmin_markdown: str | None = None
    tech_markdown: str | None = None
    stock_markdown: str | None = None
    sections: list[ReportSection] = field(default_factory=list)
    emailed_to: str | None = None
    errors: list[str] = field(default_factory=list)


def _save(markdown: str, name: str) -> Path:
    out_dir = Path("reports")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}_{date.today().isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    return path


def run_mikey_pipeline(
    *,
    running_days: int = config.GARMIN_RUNNING_DAYS,
    sleep_days: int = config.GARMIN_SLEEP_DAYS,
    general_days: int = config.GARMIN_GENERAL_DAYS,
    send_email: bool = True,
    recipient: str | None = None,
    save: bool = True,
) -> PipelineResult:
    """Run all report agents and send one combined email."""
    result = PipelineResult()

    # 1) Garmin health report ------------------------------------------------
    logger.info("[1/3] Garmin health report — starting ...")
    t0 = time.monotonic()
    try:
        garmin_md = generate_garmin_report(
            running_days=running_days, sleep_days=sleep_days, general_days=general_days
        )
        result.garmin_markdown = garmin_md
        if save:
            _save(garmin_md, "garmin_report")
        result.sections.append(
            ReportSection(
                title="Garmin Health Report",
                markdown=garmin_md,
                theme="garmin",
                subtitle="Running • Sleep • Wellness",
            )
        )
        logger.info("[1/3] Garmin health report — done (%.1fs)", time.monotonic() - t0)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[1/3] Garmin report failed (%.1fs)", time.monotonic() - t0)
        result.errors.append(f"Garmin report failed: {exc}")

    # 2) Weekly tech briefing ------------------------------------------------
    logger.info("[2/3] AI & tech briefing — starting ...")
    t0 = time.monotonic()
    try:
        tech_md = generate_tech_report()
        result.tech_markdown = tech_md
        if save:
            _save(tech_md, "tech_report")
        result.sections.append(
            ReportSection(
                title="Weekly AI & Tech Briefing",
                markdown=tech_md,
                theme="tech",
                subtitle="The most significant updates from the last 7 days",
            )
        )
        logger.info("[2/3] AI & tech briefing — done (%.1fs)", time.monotonic() - t0)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[2/3] Tech report failed (%.1fs)", time.monotonic() - t0)
        result.errors.append(f"Tech report failed: {exc}")

    # 3) Stock watch-list insights -------------------------------------------
    logger.info("[3/3] Stock watch-list — starting ...")
    t0 = time.monotonic()
    try:
        stock_md = generate_stock_report()
        result.stock_markdown = stock_md
        if save:
            _save(stock_md, "stock_report")
        result.sections.append(
            ReportSection(
                title="Stock Watch-list Insights",
                markdown=stock_md,
                theme="stocks",
                subtitle="News, earnings & metrics for your stocks — plus top picks",
            )
        )
        logger.info("[3/3] Stock watch-list — done (%.1fs)", time.monotonic() - t0)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[3/3] Stock report failed (%.1fs)", time.monotonic() - t0)
        result.errors.append(f"Stock report failed: {exc}")

    if not result.sections:
        raise RuntimeError("All reports failed: " + "; ".join(result.errors))

    # 4) Send a single combined email ----------------------------------------
    if send_email:
        logger.info("Sending combined email ...")
        email_config = EmailConfig.from_env()
        if recipient:
            email_config = replace(email_config, recipient=recipient)
        send_combined_email(
            result.sections,
            subject=f"📬 Your Mikey Briefing — {date.today().strftime('%b %d, %Y')}",
            title="Your Mikey Briefing",
            subtitle="Health, tech & stocks — gathered and summarized for you",
            config=email_config,
        )
        result.emailed_to = email_config.recipient
        logger.info("Email sent to %s", email_config.recipient)

    return result
