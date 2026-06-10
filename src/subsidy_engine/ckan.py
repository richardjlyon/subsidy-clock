"""Client for CKAN data portals (LCCC and NESO both run CKAN)."""

from __future__ import annotations

import httpx

LCCC_API = "https://dp.lowcarboncontracts.uk/api/3/action"
NESO_API = "https://api.neso.energy/api/3/action"


def fetch_all_records(
    resource_id: str,
    *,
    client: httpx.Client | None = None,
    page_size: int = 10_000,
    api_base: str = LCCC_API,
) -> list[dict]:
    own_client = client is None
    client = client or httpx.Client(timeout=120)
    try:
        records: list[dict] = []
        offset = 0
        while True:
            resp = client.get(f"{api_base}/datastore_search", params={
                "resource_id": resource_id, "limit": page_size, "offset": offset,
            })
            resp.raise_for_status()
            result = resp.json()["result"]
            batch = result["records"]
            records.extend(batch)
            offset += len(batch)
            total = int(result["total"])
            if offset >= total:
                return records
            if not batch:
                raise RuntimeError(
                    f"datastore_search returned {len(records)} of {total} "
                    f"records for {resource_id}"
                )
    finally:
        if own_client:
            client.close()


def dataset_resources(
    dataset_id: str,
    *,
    client: httpx.Client | None = None,
    api_base: str = LCCC_API,
) -> list[dict]:
    """The resources (id, name, format, ...) of a CKAN dataset."""
    own_client = client is None
    client = client or httpx.Client(timeout=120)
    try:
        resp = client.get(f"{api_base}/package_show", params={"id": dataset_id})
        resp.raise_for_status()
        return resp.json()["result"]["resources"]
    finally:
        if own_client:
            client.close()
