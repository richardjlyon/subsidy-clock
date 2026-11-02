"""Client for the Elexon Insights (BMRS) API. Public, no key required."""

from __future__ import annotations

from datetime import date

import httpx

# The settlement stack's first day: earlier days return no rows. Checked against the API on 2 Nov 2026
# (bids from late on 6 Nov 2015, full days from 7 Nov). The backward backfill stops here (0176).
STACK_FIRST_DAY = date(2015, 11, 6)

API_BASE = "https://data.elexon.co.uk/bmrs/api/v1"


def get_json(path: str, client: httpx.Client) -> dict | list:
    resp = client.get(f"{API_BASE}{path}")
    resp.raise_for_status()
    return resp.json()


def wind_bmu_map(client: httpx.Client) -> dict[str, str]:
    """elexonBmUnit -> leadPartyName for all BM units registered as WIND."""
    units = get_json("/reference/bmunits/all", client)
    return {
        u["elexonBmUnit"]: u.get("leadPartyName") or ""
        for u in units
        if u.get("fuelType") == "WIND" and u.get("elexonBmUnit")
    }
