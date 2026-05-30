"""Resource-agnostic report delivery (email).

Any report pipeline (health, tech, stocks, ...) can hand a Markdown report to
:func:`send_report_email` (or several to :func:`send_combined_email`) to deliver
a polished HTML email.
"""

from .config import EmailConfig
from .email_sender import (
    ReportSection,
    combined_email_html,
    markdown_to_email_html,
    send_combined_email,
    send_report_email,
)

__all__ = [
    "EmailConfig",
    "ReportSection",
    "send_report_email",
    "send_combined_email",
    "markdown_to_email_html",
    "combined_email_html",
]
