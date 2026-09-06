# AdMob MCP — Google AdMob Reporting for AI Clients

<div align="center">

<img src="https://img.shields.io/badge/python-3.12%2B-blue.svg?style=flat-square" alt="Python 3.12+">
<a href="https://github.com/jimsimoy/admob-mcp/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="License: MIT"></a>
<a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-green.svg?style=flat-square" alt="MCP Compatible"></a>
<img src="https://img.shields.io/badge/tools-6-brightgreen.svg?style=flat-square" alt="6 Tools">
<img src="https://img.shields.io/badge/package%20manager-uv-orange.svg?style=flat-square" alt="Managed with uv">

**6 read-only tools for the Google AdMob API — accounts, apps, ad units, and network/mediation performance reports — for Claude Desktop, Claude Code, and any MCP client.**

by [Jan Ivan Simoy](https://github.com/jimsimoy)

</div>

---

## What is this?

AdMob MCP is a [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI assistants structured, read-only access to the [Google AdMob API](https://developers.google.com/admob/api/v1) — publisher accounts, apps, ad units, and performance reports broken down by whatever dimensions you ask for (date, app, country, ad source, and more).

It deliberately covers only the stable, read-oriented v1 surface. The AdMob API's v1beta also supports creating apps/ad units and managing mediation groups — those touch monetization configuration and billing directly, so they stay a human action in the AdMob UI, not something this server automates.

**Supported platform:** any MCP client on macOS, Linux, or Windows with Python 3.12+.

---

## Tools

| Category | Tools | What you can do |
|---|---|---|
| **Accounts** | 2 | List accounts accessible to this credential, fetch one by name |
| **Apps & Ad Units** | 2 | List apps and ad units under an account |
| **Reports** | 2 | Generate a network (own ad serving) report, or a mediation (cross ad-source) report, by any combination of dimensions and metrics |

<details>
<summary>Full tool reference</summary>

| Tool | Description |
|---|---|
| `list_accounts` | List AdMob publisher accounts accessible to this credential |
| `get_account` | Fetch one account's details by name (`accounts/pub-...`) |
| `list_apps` | List apps under an account |
| `list_ad_units` | List ad units under an account |
| `generate_network_report` | Network performance report — earnings, impressions, clicks, requests, CTR, RPM, match rate, by DATE/APP/COUNTRY/PLATFORM/etc. |
| `generate_mediation_report` | Mediation performance report — same metrics broken down by AD_SOURCE / MEDIATION_GROUP as well |

</details>

---

## Requirements

| Requirement | Version |
|---|---|
| Python | 3.12 or later |
| [uv](https://docs.astral.sh/uv/) | any recent version |
| Google Cloud project | with the AdMob API enabled |
| OAuth client | type "Desktop app" (see below — AdMob does not support service accounts) |

---

## Authentication

**AdMob does not support service-account credentials** — every call must be authorized by a real Google account via OAuth 2.0. Setup:

1. In [Google Cloud Console](https://console.cloud.google.com), create/select a project and enable the **AdMob API** (APIs & Services → Library).
2. Configure the **OAuth consent screen** (user type "External"; "Testing" status with yourself added as a test user is enough for personal use).
3. Create an **OAuth client ID** of type **Desktop app** (APIs & Services → Credentials). Note the client ID and secret.
4. Run the one-time interactive authorization:

   ```bash
   uv run admob-mcp-authorize
   ```

   This opens a browser for Google sign-in and AdMob consent, then prints a refresh token.
5. Put all three values in `.env` (see [Installation](#installation)).

The server only ever *refreshes* this token into short-lived access tokens — it never re-runs the interactive flow itself. If the refresh token is ever revoked (visible/revocable at [myaccount.google.com/permissions](https://myaccount.google.com/permissions)), re-run step 4.

Scopes requested: `admob.readonly` (account/app/ad-unit data) and `admob.report` (performance reports).

---

## Installation

```bash
git clone https://github.com/jimsimoy/admob-mcp.git
cd admob-mcp
uv sync
cp .env.example .env   # fill in ADMOB_CLIENT_ID, ADMOB_CLIENT_SECRET, ADMOB_REFRESH_TOKEN
```

Run directly:

```bash
uv run admob-mcp
```

---

## Client Setup

```json
{
  "mcpServers": {
    "admob": {
      "command": "uv",
      "args": ["--directory", "/path/to/admob-mcp", "run", "admob-mcp"],
      "env": {
        "ADMOB_CLIENT_ID": "...",
        "ADMOB_CLIENT_SECRET": "...",
        "ADMOB_REFRESH_TOKEN": "..."
      }
    }
  }
}
```

Restart your MCP client after saving. The 6 AdMob tools will appear automatically.

---

## Usage Examples

### See what accounts and apps are visible

```
List my AdMob accounts, then list the apps under the first one
```

### Check last week's earnings by app

```
Generate a network report for accounts/pub-1234567890123456 from 2026-08-30 to
2026-09-05, dimensions DATE and APP, metrics ESTIMATED_EARNINGS and IMPRESSIONS
```

### Compare ad source performance

```
Generate a mediation report for the same account and date range, broken down
by AD_SOURCE
```

---

## Security

- Credentials (`ADMOB_CLIENT_ID`, `ADMOB_CLIENT_SECRET`, `ADMOB_REFRESH_TOKEN`) are read from the environment only — `.env`, `.env.*` (except `.env.example`), and `token.json` are gitignored.
- The refresh token is a long-lived credential with read access to your AdMob account and revenue data. Treat it like a password; revoke it at [myaccount.google.com/permissions](https://myaccount.google.com/permissions) if it's ever exposed.
- This is a read-only server by design — it does not expose the v1beta write endpoints (creating apps/ad units, mediation group management).

---

## Project Structure

```
src/admob_mcp/
  server.py     # MCP server entry point and tool definitions
  client.py     # AdMob API client (pagination, report-stream parsing)
  auth.py       # OAuth access-token refresh
  authorize.py  # One-time interactive OAuth consent flow (admob-mcp-authorize)
```

The server communicates over stdio using JSON-RPC 2.0, the standard MCP transport.

---

## A note on testing

This was built directly from Google's official AdMob API v1 reference (endpoints, OAuth scopes, and the exact dimension/metric enums for both report types), with token refresh/caching, pagination, and report-response parsing covered by tests against a mocked API. It has also been verified end-to-end against a live AdMob account: the OAuth loopback flow, `list_accounts`, `list_apps`, `list_ad_units`, `generate_network_report` (both an empty-result case and a populated one, confirming row and footer parsing), and `generate_mediation_report` all returned correct real data.

---

## License

[MIT](./LICENSE) — free to use, modify, and distribute.

---

<div align="center">

[Report a Bug](https://github.com/jimsimoy/admob-mcp/issues) · [Request a Feature](https://github.com/jimsimoy/admob-mcp/issues)

</div>
