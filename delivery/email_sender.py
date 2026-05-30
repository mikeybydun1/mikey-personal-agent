"""Render Markdown report(s) into a polished HTML email and send via SMTP.

Resource-agnostic and composable:
- ``send_report_email`` sends a single themed report (garmin, tech, stocks, ...).
- ``send_combined_email`` sends ONE email composed of several report sections,
  each with its own colored banner — used by the Mikey pipeline to deliver the
  Garmin health report and the weekly tech briefing together.
"""

from __future__ import annotations

import logging
import smtplib
import ssl
from dataclasses import dataclass
from datetime import date
from email.message import EmailMessage

import markdown as md

from .config import EmailConfig

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Branding presets — pick one per report type (extensible).
# --------------------------------------------------------------------------- #
THEMES: dict[str, dict[str, str]] = {
    "garmin": {"accent_start": "#0a84ff", "accent_end": "#00b3a4", "emoji": "🏃"},
    "tech": {"accent_start": "#6d28d9", "accent_end": "#2563eb", "emoji": "🧠"},
    "stocks": {"accent_start": "#1f7a3d", "accent_end": "#0f9d58", "emoji": "📈"},
    "mikey": {"accent_start": "#4361ee", "accent_end": "#7209b7", "emoji": "📬"},
    "default": {"accent_start": "#4361ee", "accent_end": "#7209b7", "emoji": "📊"},
}


@dataclass
class ReportSection:
    """One report inside a combined email."""

    title: str
    markdown: str
    theme: str = "default"
    subtitle: str = ""


def _theme(name: str) -> dict[str, str]:
    return THEMES.get(name, THEMES["default"])


def _render_markdown(markdown_text: str) -> str:
    return md.markdown(
        markdown_text,
        extensions=["tables", "fenced_code", "sane_lists", "nl2br"],
    )


def _email_shell(
    *,
    title: str,
    subtitle: str,
    emoji: str,
    accent_start: str,
    accent_end: str,
    h2_color: str,
    content_html: str,
    footer_note: str,
) -> str:
    """Wrap pre-rendered content HTML in the responsive email shell."""
    today = date.today().strftime("%B %d, %Y")
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  body {{ margin:0; padding:0; background:#eef1f5;
         font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;
         color:#1f2933; -webkit-text-size-adjust:100%; }}
  .wrapper {{ width:100%; background:#eef1f5; padding:24px 12px; }}
  .container {{ max-width:660px; margin:0 auto; background:#ffffff; border-radius:14px;
               overflow:hidden; box-shadow:0 6px 24px rgba(20,30,50,0.10); }}
  .header {{ background:linear-gradient(135deg,{accent_start} 0%,{accent_end} 100%);
            padding:32px 32px 28px; color:#ffffff; }}
  .header .emoji {{ font-size:34px; line-height:1; }}
  .header h1 {{ margin:10px 0 4px; font-size:24px; font-weight:700; color:#ffffff; }}
  .header p {{ margin:0; font-size:14px; opacity:0.92; }}
  .header .date {{ margin-top:10px; font-size:12px; letter-spacing:0.5px;
                  text-transform:uppercase; opacity:0.85; }}
  .content {{ padding:28px 32px 8px; font-size:15px; line-height:1.65; }}
  .section-banner {{ color:#ffffff; padding:13px 18px; border-radius:10px;
                    font-size:17px; font-weight:700; margin:30px 0 16px; }}
  .section-banner:first-child {{ margin-top:4px; }}
  .content h2 {{ font-size:18px; margin:24px 0 12px; padding-bottom:8px;
                color:{h2_color}; border-bottom:2px solid #eef1f5; }}
  .content h3 {{ font-size:15px; margin:20px 0 8px; color:#334155; }}
  .content p {{ margin:0 0 14px; }}
  .content ul, .content ol {{ margin:0 0 16px; padding-left:22px; }}
  .content li {{ margin-bottom:7px; }}
  .content a {{ color:{accent_start}; text-decoration:none; }}
  .content strong {{ color:#0f172a; }}
  .content table {{ width:100%; border-collapse:collapse; margin:14px 0 20px; font-size:14px; }}
  .content th {{ background:#f4f6fb; text-align:left; padding:9px 12px;
                border-bottom:2px solid #e2e8f0; color:#334155; }}
  .content td {{ padding:9px 12px; border-bottom:1px solid #edf1f7; }}
  .content code {{ background:#f4f6fb; padding:2px 6px; border-radius:5px;
                  font-family:'SFMono-Regular',Consolas,monospace; font-size:13px; }}
  .footer {{ padding:20px 32px 28px; color:#94a3b8; font-size:12px;
            text-align:center; border-top:1px solid #eef1f5; }}
</style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="emoji">{emoji}</div>
        <h1>{title}</h1>
        {f'<p>{subtitle}</p>' if subtitle else ''}
        <div class="date">{today}</div>
      </div>
      <div class="content">
{content_html}
      </div>
      <div class="footer">
        {footer_note}
      </div>
    </div>
  </div>
</body>
</html>"""


def markdown_to_email_html(
    markdown_text: str,
    *,
    title: str,
    subtitle: str = "",
    theme: str = "default",
    footer_note: str = "Generated automatically by your personal agent.",
) -> str:
    """Convert a single Markdown report into a responsive HTML email document."""
    colors = _theme(theme)
    return _email_shell(
        title=title,
        subtitle=subtitle,
        emoji=colors["emoji"],
        accent_start=colors["accent_start"],
        accent_end=colors["accent_end"],
        h2_color=colors["accent_start"],
        content_html=_render_markdown(markdown_text),
        footer_note=footer_note,
    )


def combined_email_html(
    sections: list[ReportSection],
    *,
    title: str,
    subtitle: str = "",
    theme: str = "mikey",
    footer_note: str = "Generated automatically by Mikey Agent.",
) -> str:
    """Compose several reports into ONE HTML email, each with its own banner."""
    parts: list[str] = []
    for section in sections:
        colors = _theme(section.theme)
        banner = (
            f'<div class="section-banner" style="background:linear-gradient(135deg,'
            f'{colors["accent_start"]} 0%,{colors["accent_end"]} 100%);">'
            f'{colors["emoji"]}&nbsp;&nbsp;{section.title}</div>'
        )
        sub = f'<p style="color:#64748b;margin:-6px 0 14px;">{section.subtitle}</p>' if section.subtitle else ""
        parts.append(banner + sub + _render_markdown(section.markdown))

    master = _theme(theme)
    return _email_shell(
        title=title,
        subtitle=subtitle,
        emoji=master["emoji"],
        accent_start=master["accent_start"],
        accent_end=master["accent_end"],
        h2_color="#334155",  # neutral; section banners carry the color identity
        content_html="\n".join(parts),
        footer_note=footer_note,
    )


# --------------------------------------------------------------------------- #
# Sending
# --------------------------------------------------------------------------- #
def _send(
    *,
    subject: str,
    html: str,
    text_fallback: str,
    config: EmailConfig,
) -> None:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.sender
    message["To"] = config.recipient
    message.set_content(text_fallback)
    message.add_alternative(html, subtype="html")

    logger.info("Sending '%s' to %s via %s:%d", subject, config.recipient,
                config.smtp_host, config.smtp_port)

    context = ssl.create_default_context()
    if config.smtp_port == 465:
        with smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, context=context) as server:
            server.login(config.sender, config.app_password)
            server.send_message(message)
    else:
        with smtplib.SMTP(config.smtp_host, config.smtp_port) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(config.sender, config.app_password)
            server.send_message(message)

    logger.info("Email sent to %s", config.recipient)


def send_report_email(
    markdown_report: str,
    *,
    subject: str,
    title: str,
    subtitle: str = "",
    theme: str = "default",
    config: EmailConfig | None = None,
) -> None:
    """Render a single ``markdown_report`` and email it. Raises on failure."""
    config = config or EmailConfig.from_env()
    html = markdown_to_email_html(markdown_report, title=title, subtitle=subtitle, theme=theme)
    _send(subject=subject, html=html, text_fallback=markdown_report, config=config)


def send_combined_email(
    sections: list[ReportSection],
    *,
    subject: str,
    title: str,
    subtitle: str = "",
    config: EmailConfig | None = None,
) -> None:
    """Render several report sections into ONE email and send it. Raises on failure."""
    config = config or EmailConfig.from_env()
    html = combined_email_html(sections, title=title, subtitle=subtitle)
    text_fallback = "\n\n\n".join(f"# {s.title}\n\n{s.markdown}" for s in sections)
    _send(subject=subject, html=html, text_fallback=text_fallback, config=config)
