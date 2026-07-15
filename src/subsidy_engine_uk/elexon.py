"""Client for the Elexon Insights (BMRS) API. Public, no key required."""

from __future__ import annotations

import httpx

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
