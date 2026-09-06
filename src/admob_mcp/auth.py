"""OAuth 2.0 access-token management for the AdMob API.

AdMob does not support service accounts — every call must be authorized on
behalf of a real Google account via the standard OAuth 2.0 flow. See
https://developers.google.com/admob/api/v1/getting-started

This module only *refreshes* an existing refresh token into short-lived
access tokens. The one-time interactive consent flow that produces the
refresh token lives in authorize.py.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

import httpx

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_REFRESH_MARGIN_SECONDS = 60


@dataclass(frozen=True)
class AdmobCredentials:
    client_id: str
    client_secret: str
    refresh_token: str

    @classmethod
    def from_env(cls) -> "AdmobCredentials":
        return cls(
            client_id=_require_env("ADMOB_CLIENT_ID"),
            client_secret=_require_env("ADMOB_CLIENT_SECRET"),
            refresh_token=_require_env("ADMOB_REFRESH_TOKEN"),
        )


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Missing required environment variable {name!r}. Set ADMOB_CLIENT_ID, "
            "ADMOB_CLIENT_SECRET, and ADMOB_REFRESH_TOKEN before starting the server "
            "(run `admob-mcp-authorize` once if you don't have a refresh token yet)."
        )
    return value


class TokenProvider:
    """Caches an access token and refreshes it shortly before it would expire."""

    def __init__(self, credentials: AdmobCredentials) -> None:
        self._credentials = credentials
        self._http = httpx.AsyncClient(timeout=30.0)
        self._token: str | None = None
        self._expires_at: float = 0.0

    async def aclose(self) -> None:
        await self._http.aclose()

    async def get_token(self) -> str:
        now = time.time()
        if self._token is None or now >= self._expires_at - _REFRESH_MARGIN_SECONDS:
            self._token, expires_in = await self._refresh()
            self._expires_at = now + expires_in
        return self._token

    async def _refresh(self) -> tuple[str, int]:
        response = await self._http.post(
            _TOKEN_URL,
            data={
                "client_id": self._credentials.client_id,
                "client_secret": self._credentials.client_secret,
                "refresh_token": self._credentials.refresh_token,
                "grant_type": "refresh_token",
            },
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Failed to refresh AdMob access token ({response.status_code}): "
                f"{response.text}. The refresh token may have been revoked — "
                "run `admob-mcp-authorize` again."
            )
        body = response.json()
        return body["access_token"], int(body.get("expires_in", 3600))
