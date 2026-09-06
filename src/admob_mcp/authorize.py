"""One-time interactive OAuth 2.0 consent flow for the AdMob API.

Run this once per Google account with `admob-mcp-authorize`. It opens a
browser, asks you to sign in and grant access, then prints a refresh token
to put in ADMOB_REFRESH_TOKEN. The MCP server itself (server.py / auth.py)
never does this interactive step — it only refreshes the token this
produces.

Uses the OAuth 2.0 "installed app" / loopback flow described at
https://developers.google.com/identity/protocols/oauth2/native-app
"""

from __future__ import annotations

import os
import sys
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx

_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_SCOPES = [
    "https://www.googleapis.com/auth/admob.readonly",
    "https://www.googleapis.com/auth/admob.report",
]


class _CallbackHandler(BaseHTTPRequestHandler):
    auth_code: str | None = None
    error: str | None = None

    def do_GET(self) -> None:  # noqa: N802 (http.server API)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            _CallbackHandler.auth_code = params["code"][0]
            body = b"Authorized. You can close this tab and return to the terminal."
        else:
            _CallbackHandler.error = params.get("error", ["unknown_error"])[0]
            body = f"Authorization failed: {_CallbackHandler.error}".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # silence default request logging
        pass


def main() -> None:
    client_id = os.environ.get("ADMOB_CLIENT_ID") or input("ADMOB_CLIENT_ID: ").strip()
    client_secret = os.environ.get("ADMOB_CLIENT_SECRET") or input("ADMOB_CLIENT_SECRET: ").strip()
    if not client_id or not client_secret:
        print("ADMOB_CLIENT_ID and ADMOB_CLIENT_SECRET are required.", file=sys.stderr)
        raise SystemExit(1)

    server = HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    port = server.server_address[1]
    # Use "localhost" (not 127.0.0.1) to match the redirect_uri registered on
    # Desktop-app OAuth clients in Google Cloud Console.
    redirect_uri = f"http://localhost:{port}/"

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(_SCOPES),
        "access_type": "offline",
        "prompt": "consent",  # force a refresh_token even on a re-auth
    }
    auth_url = f"{_AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    print("Opening browser for Google sign-in and AdMob consent...")
    print(f"If it doesn't open automatically, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    server.handle_request()  # blocks until the redirect hits us, once
    server.server_close()

    if _CallbackHandler.error or not _CallbackHandler.auth_code:
        print(f"Authorization failed: {_CallbackHandler.error}", file=sys.stderr)
        raise SystemExit(1)

    response = httpx.post(
        _TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": _CallbackHandler.auth_code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
        },
        timeout=30.0,
    )
    if response.status_code >= 400:
        print(f"Token exchange failed ({response.status_code}): {response.text}", file=sys.stderr)
        raise SystemExit(1)

    body = response.json()
    refresh_token = body.get("refresh_token")
    if not refresh_token:
        print(
            "No refresh_token in the response. This usually means this Google account "
            "already granted consent before without `prompt=consent` — revoke prior "
            "access at https://myaccount.google.com/permissions and try again.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    print("\nSuccess. Put this in your .env:\n")
    print(f"ADMOB_CLIENT_ID={client_id}")
    print(f"ADMOB_CLIENT_SECRET={client_secret}")
    print(f"ADMOB_REFRESH_TOKEN={refresh_token}")


if __name__ == "__main__":
    main()
