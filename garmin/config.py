"""Configuration loading for Garmin data fetching.

Credentials are read from environment variables (loaded from a gitignored
``.env`` file). Nothing sensitive is ever hard-coded in the repo.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load variables from a local .env file if present. Existing real environment
# variables always take precedence over .env values.
load_dotenv(override=False)


def _as_bool(value: str | None) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class GarminConfig:
    """Resolved settings for talking to Garmin Connect."""

    email: str
    password: str
    token_store: Path
    data_dir: Path
    is_cn: bool

    @classmethod
    def from_env(cls) -> "GarminConfig":
        """Build a config from environment variables.

        Raises:
            RuntimeError: if the required credentials are missing.
        """
        email = os.getenv("GARMIN_EMAIL", "").strip()
        password = os.getenv("GARMIN_PASSWORD", "")

        if not email or not password:
            raise RuntimeError(
                "Missing Garmin credentials. Copy .env.example to .env and set "
                "GARMIN_EMAIL and GARMIN_PASSWORD (or export them in your shell)."
            )

        token_store = Path(os.getenv("GARMIN_TOKEN_STORE", ".garmin_tokens")).expanduser()
        data_dir = Path(os.getenv("GARMIN_DATA_DIR", "data")).expanduser()
        is_cn = _as_bool(os.getenv("GARMIN_IS_CN"))

        return cls(
            email=email,
            password=password,
            token_store=token_store,
            data_dir=data_dir,
            is_cn=is_cn,
        )
