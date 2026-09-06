"""MCP server exposing the Google AdMob API v1: accounts, apps, ad units,
and network/mediation performance reports.

Scope is deliberately read-only. AdMob's v1beta surface also supports
creating apps/ad units and managing mediation groups — those touch billing
and monetization configuration directly and are treated as a human action
in the AdMob UI, not something an agent automates. See
https://developers.google.com/admob/api/v1/reference/rest
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from .auth import AdmobCredentials, TokenProvider
from .client import AdmobClient, date_to_struct

mcp = MCPServer(
    name="admob",
    version="0.1.0",
    instructions=(
        "Read AdMob account, app, ad unit, and performance-report data. "
        "Requires ADMOB_CLIENT_ID, ADMOB_CLIENT_SECRET, and ADMOB_REFRESH_TOKEN "
        "to be set in the environment (run `admob-mcp-authorize` once to obtain "
        "the refresh token)."
    ),
)

_client: AdmobClient | None = None

_NETWORK_DIMENSIONS = {
    "DATE", "MONTH", "WEEK", "AD_UNIT", "APP", "AD_TYPE", "COUNTRY", "FORMAT",
    "PLATFORM", "MOBILE_OS_VERSION", "GMA_SDK_VERSION", "APP_VERSION_NAME",
    "SERVING_RESTRICTION",
}
_NETWORK_METRICS = {
    "AD_REQUESTS", "CLICKS", "ESTIMATED_EARNINGS", "IMPRESSIONS", "IMPRESSION_CTR",
    "IMPRESSION_RPM", "MATCHED_REQUESTS", "MATCH_RATE", "SHOW_RATE",
}
_MEDIATION_DIMENSIONS = {
    "DATE", "MONTH", "WEEK", "AD_SOURCE", "AD_SOURCE_INSTANCE", "AD_UNIT", "APP",
    "MEDIATION_GROUP", "COUNTRY", "FORMAT", "PLATFORM", "MOBILE_OS_VERSION",
    "GMA_SDK_VERSION", "APP_VERSION_NAME", "SERVING_RESTRICTION",
}
_MEDIATION_METRICS = {
    "AD_REQUESTS", "CLICKS", "ESTIMATED_EARNINGS", "IMPRESSIONS", "IMPRESSION_CTR",
    "MATCHED_REQUESTS", "MATCH_RATE", "OBSERVED_ECPM",
}


def _get_client() -> AdmobClient:
    global _client
    if _client is None:
        credentials = AdmobCredentials.from_env()
        _client = AdmobClient(TokenProvider(credentials))
    return _client


def _validate(values: list[str], allowed: set[str], label: str) -> None:
    invalid = [v for v in values if v not in allowed]
    if invalid:
        raise ValueError(
            f"Invalid {label}: {invalid}. Valid values are: {sorted(allowed)}"
        )


# --- Accounts ----------------------------------------------------------------


@mcp.tool()
async def list_accounts() -> list[dict[str, Any]]:
    """List AdMob publisher accounts accessible to this credential."""
    client = _get_client()
    rows = await client.get_all_pages("/accounts", items_key="account")
    return [
        {
            "name": row.get("name"),
            "publisherId": row.get("publisherId"),
            "currencyCode": row.get("currencyCode"),
            "reportingTimeZone": row.get("reportingTimeZone"),
        }
        for row in rows
    ]


@mcp.tool()
async def get_account(account_name: str) -> dict[str, Any]:
    """Fetch one account's details. account_name looks like 'accounts/pub-1234567890123456'."""
    client = _get_client()
    return await client.get(f"/{account_name}")


# --- Apps & ad units -----------------------------------------------------------


@mcp.tool()
async def list_apps(account_name: str) -> list[dict[str, Any]]:
    """List apps under an account. account_name looks like 'accounts/pub-1234567890123456'."""
    client = _get_client()
    return await client.get_all_pages(f"/{account_name}/apps", items_key="apps")


@mcp.tool()
async def list_ad_units(account_name: str) -> list[dict[str, Any]]:
    """List ad units under an account. account_name looks like 'accounts/pub-1234567890123456'."""
    client = _get_client()
    return await client.get_all_pages(f"/{account_name}/adUnits", items_key="adUnits")


# --- Reports -------------------------------------------------------------------


@mcp.tool()
async def generate_network_report(
    account_name: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    metrics: list[str] | None = None,
    max_report_rows: int | None = None,
) -> dict[str, Any]:
    """Generate an AdMob network (own ad serving) performance report.

    account_name looks like 'accounts/pub-1234567890123456'. start_date/end_date
    are 'YYYY-MM-DD', inclusive.

    dimensions default to ["DATE", "APP"]; valid values: DATE, MONTH, WEEK,
    AD_UNIT, APP, AD_TYPE, COUNTRY, FORMAT, PLATFORM, MOBILE_OS_VERSION,
    GMA_SDK_VERSION, APP_VERSION_NAME, SERVING_RESTRICTION.

    metrics default to ["ESTIMATED_EARNINGS", "IMPRESSIONS", "CLICKS",
    "AD_REQUESTS"]; valid values: AD_REQUESTS, CLICKS, ESTIMATED_EARNINGS,
    IMPRESSIONS, IMPRESSION_CTR, IMPRESSION_RPM, MATCHED_REQUESTS, MATCH_RATE,
    SHOW_RATE.
    """
    dims = dimensions or ["DATE", "APP"]
    mets = metrics or ["ESTIMATED_EARNINGS", "IMPRESSIONS", "CLICKS", "AD_REQUESTS"]
    _validate(dims, _NETWORK_DIMENSIONS, "network report dimension")
    _validate(mets, _NETWORK_METRICS, "network report metric")

    report_spec: dict[str, Any] = {
        "dateRange": {
            "startDate": date_to_struct(start_date),
            "endDate": date_to_struct(end_date),
        },
        "dimensions": dims,
        "metrics": mets,
    }
    if max_report_rows is not None:
        report_spec["maxReportRows"] = max_report_rows

    client = _get_client()
    return await client.generate_report(f"/{account_name}/networkReport:generate", report_spec)


@mcp.tool()
async def generate_mediation_report(
    account_name: str,
    start_date: str,
    end_date: str,
    dimensions: list[str] | None = None,
    metrics: list[str] | None = None,
    max_report_rows: int | None = None,
) -> dict[str, Any]:
    """Generate an AdMob mediation performance report (earnings across ad sources).

    account_name looks like 'accounts/pub-1234567890123456'. start_date/end_date
    are 'YYYY-MM-DD', inclusive.

    dimensions default to ["DATE", "AD_SOURCE"]; valid values: DATE, MONTH,
    WEEK, AD_SOURCE, AD_SOURCE_INSTANCE, AD_UNIT, APP, MEDIATION_GROUP,
    COUNTRY, FORMAT, PLATFORM, MOBILE_OS_VERSION, GMA_SDK_VERSION,
    APP_VERSION_NAME, SERVING_RESTRICTION.

    metrics default to ["ESTIMATED_EARNINGS", "IMPRESSIONS", "CLICKS"]; valid
    values: AD_REQUESTS, CLICKS, ESTIMATED_EARNINGS, IMPRESSIONS,
    IMPRESSION_CTR, MATCHED_REQUESTS, MATCH_RATE, OBSERVED_ECPM.
    """
    dims = dimensions or ["DATE", "AD_SOURCE"]
    mets = metrics or ["ESTIMATED_EARNINGS", "IMPRESSIONS", "CLICKS"]
    _validate(dims, _MEDIATION_DIMENSIONS, "mediation report dimension")
    _validate(mets, _MEDIATION_METRICS, "mediation report metric")

    report_spec: dict[str, Any] = {
        "dateRange": {
            "startDate": date_to_struct(start_date),
            "endDate": date_to_struct(end_date),
        },
        "dimensions": dims,
        "metrics": mets,
    }
    if max_report_rows is not None:
        report_spec["maxReportRows"] = max_report_rows

    client = _get_client()
    return await client.generate_report(f"/{account_name}/mediationReport:generate", report_spec)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
