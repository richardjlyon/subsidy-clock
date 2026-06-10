"""Client for the LCCC data portal (CKAN datastore API)."""

from __future__ import annotations

import httpx

BASE_URL = "https://dp.lowcarboncontracts.uk/api/3/action/datastore_search"


def fetch_all_records(
    resource_id: str,
    *,
    client: httpx.Client | None = None,
    page_size: int = 10_000,
) -> list[dict]:
    own_client = client is None
    client = client or httpx.Client(timeout=120)
    try:
        records: list[dict] = []
        offset = 0
        while True:
            resp = client.get(BASE_URL, params={
                "resource_id": resource_id, "limit": page_size, "offset": offset,
            })
            resp.raise_for_status()
            result = resp.json()["result"]
            batch = result["records"]
            records.extend(batch)
            offset += len(batch)
            if not batch or offset >= int(result["total"]):
                return records
    finally:
        if own_client:
            client.close()
