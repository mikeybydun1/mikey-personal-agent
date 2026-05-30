"""SMTP / email configuration, loaded from the gitignored .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(override=False)


@dataclass(frozen=True)
class EmailConfig:
    sender: str
    app_password: str
    recipient: str
    smtp_host: str
    smtp_port: int

    @classmethod
    def from_env(cls) -> "EmailConfig":
        """Build email config from environment variables.

        Requires EMAIL_SENDER and EMAIL_APP_PASSWORD (a Gmail *App Password*,
        not the normal account password — Google blocks basic-auth SMTP).
        """
        sender = os.getenv("EMAIL_SENDER", "").strip()
        # App passwords are shown with spaces (e.g. "abcd efgh ijkl mnop");
        # strip them so either form works.
        app_password = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "").strip()
        recipient = os.getenv("EMAIL_RECIPIENT", sender).strip() or sender
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com").strip()
        smtp_port = int(os.getenv("SMTP_PORT", "587"))

        if not sender or not app_password:
            raise RuntimeError(
                "Missing email credentials. Set EMAIL_SENDER and EMAIL_APP_PASSWORD "
                "in .env. For Gmail, EMAIL_APP_PASSWORD must be a 16-character App "
                "Password (Google Account > Security > 2-Step Verification > App "
                "passwords), not your normal login password."
            )

        return cls(
            sender=sender,
            app_password=app_password,
            recipient=recipient,
            smtp_host=smtp_host,
            smtp_port=smtp_port,
        )
