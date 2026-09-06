"""Minimal async client for the Google AdMob API v1."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx

from .auth import TokenProvider

_BASE_URL = "https://admob.googleapis.com/v1"
_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


class AdmobApiError(RuntimeError):
    def __init__(self, status_code: int, body: Any) -> None:
        self.status_code = status_code
        self.body = body
        super().__init__(f"AdMob API error {status_code}: {body}")


def date_to_struct(date_str: str) -> dict[str, int]:
    """Convert 'YYYY-MM-DD' to AdMob's {year, month, day} Date object."""
    match = _DATE_RE.match(date_str)
    if not match:
        raise ValueError(f"Expected a date as 'YYYY-MM-DD', got {date_str!r}")
    year, month, day = match.groups()
    return {"year": int(year), "month": int(month), "day": int(day)}


class AdmobClient:
    def __init__(self, token_provider: TokenProvider) -> None:
        self._tokens = token_provider
        self._http = httpx.AsyncClient(base_url=_BASE_URL, timeout=60.0)

    async def aclose(self) -> None:
        await self._http.aclose()
        await self._tokens.aclose()

    async def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {await self._tokens.get_token()}"}

    async def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        response = await self._http.get(path, params=params, headers=await self._headers())
        return self._parse_json_response(response)

    async def get_all_pages(
        self,
        path: str,
        items_key: str,
        params: dict[str, Any] | None = None,
        max_pages: int = 20,
    ) -> list[dict[str, Any]]:
        """Follow `nextPageToken` up to max_pages, returning the concatenated items."""
        results: list[dict[str, Any]] = []
        page_params = dict(params or {})
        for _ in range(max_pages):
            page = await self.get(path, params=page_params)
            results.extend(page.get(items_key, []))
            next_token = page.get("nextPageToken")
            if not next_token:
                break
            page_params["pageToken"] = next_token
        return results

    async def generate_report(self, path: str, report_spec: dict[str, Any]) -> dict[str, Any]:
        """POST a networkReport:generate / mediationReport:generate call.

        The API streams the response as a sequence of JSON objects, each a
        `header`, `row`, or `footer`. Google's own client libraries handle
        this via gRPC streaming; over plain HTTP it comes back either as a
        single JSON array or as newline-delimited JSON depending on
        transport — this parses both defensively rather than assuming one.
        """
        response = await self._http.post(
            path, json={"reportSpec": report_spec}, headers=await self._headers()
        )
        if response.status_code >= 400:
            raise AdmobApiError(response.status_code, self._error_body(response))

        chunks = self._parse_stream(response.text)

        header: dict[str, Any] = {}
        rows: list[dict[str, Any]] = []
        footer: dict[str, Any] = {}
        for chunk in chunks:
            if "header" in chunk:
                header = chunk["header"]
            elif "row" in chunk:
                rows.append(chunk["row"])
            elif "footer" in chunk:
                footer = chunk["footer"]
        return {"header": header, "rows": rows, "footer": footer}

    @staticmethod
    def _parse_stream(text: str) -> list[dict[str, Any]]:
        text = text.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return parsed
            return [parsed]
        except json.JSONDecodeError:
            pass
        # Fall back to newline-delimited JSON.
        return [json.loads(line) for line in text.splitlines() if line.strip()]

    @staticmethod
    def _parse_json_response(response: httpx.Response) -> dict[str, Any]:
        if response.status_code >= 400:
            raise AdmobApiError(response.status_code, AdmobClient._error_body(response))
        if not response.content:
            return {}
        return response.json()

    @staticmethod
    def _error_body(response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            return response.text
