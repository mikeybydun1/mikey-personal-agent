"""Authenticated Garmin Connect client with token caching.

On first login the username/password are exchanged for OAuth tokens, which are
cached on disk (``GARMIN_TOKEN_STORE``). Subsequent runs reuse those tokens, so
the password is not sent again and MFA is not re-prompted until the tokens
expire.
"""

from __future__ import annotations

import logging

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

from .config import GarminConfig

logger = logging.getLogger(__name__)


def _prompt_mfa() -> str:
    """Prompt for a Garmin multi-factor auth code on the terminal."""
    return input("Enter the Garmin MFA / 2FA code that was sent to you: ").strip()


class GarminClient:
    """Thin wrapper that returns a logged-in ``garminconnect.Garmin`` instance."""

    def __init__(self, config: GarminConfig):
        self.config = config
        self._api: Garmin | None = None

    @property
    def api(self) -> Garmin:
        if self._api is None:
            raise RuntimeError("Not logged in yet — call login() first.")
        return self._api

    def login(self) -> Garmin:
        """Authenticate, reusing cached tokens when available.

        Returns the underlying ``Garmin`` API object.
        """
        token_store = str(self.config.token_store)

        api = Garmin(
            email=self.config.email,
            password=self.config.password,
            is_cn=self.config.is_cn,
            prompt_mfa=_prompt_mfa,
        )

        try:
            # login() first tries the token store; if tokens are missing or
            # expired it falls back to the email/password and re-dumps fresh
            # tokens to the store.
            api.login(tokenstore=token_store)
        except (
            GarminConnectAuthenticationError,
            GarminConnectConnectionError,
            GarminConnectTooManyRequestsError,
        ) as exc:
            logger.error("Garmin login failed: %s", exc)
            raise

        self._api = api
        logger.info("Logged in to Garmin Connect as %s", api.get_full_name() or self.config.email)
        return api
