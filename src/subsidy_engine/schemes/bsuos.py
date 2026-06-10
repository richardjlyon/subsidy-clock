"""BSUoS balancing costs (phase 2 spec section 3): NESO's daily balancing
cost data, fetched per fiscal-year resource from the NESO CKAN portal.

Stored RAW (total daily cost). Attribution to renewables - the uplift above
the CPIH-indexed 2002-05 baseline, NET of wind constraint payments already
counted in the direct layer - happens in the money model, never here."""

from __future__ import annotations

import re

import httpx
import polars as pl

from subsidy_engine import ckan
from subsidy_engine.store import SnapshotStore

DATASET = "daily-balancing-costs-balancing-services-use-of-system"
DATASET_URL = ("https://www.neso.energy/data-portal/"
               "daily-balancing-costs-balancing-services-use-of-system")

COST_COLUMNS = ["Energy Imbalance", "Frequency Control", "Positive Reserve",
                "Constraints", "Negative Reserve", "Other"]

_RESOURCE_NAME = re.compile(r"Daily Balancing Costs (\d{4}-\d{4})")

SCHEMA = {"date": pl.Date, "cost_gbp": pl.Float64}


def parse_daily(records: list[dict]) -> pl.DataFrame:
    if not records:
        return pl.DataFrame(schema=SCHEMA)
    df = pl.DataFrame(records, infer_schema_length=None)
    return (
        df.select(
            pl.col("SETT_DATE").cast(pl.Utf8).str.slice(0, 10).str.to_date().alias("date"),
            pl.sum_horizontal(
                [pl.col(c).cast(pl.Float64, strict=False).fill_null(0.0)
                 for c in COST_COLUMNS]
            ).alias("cost_gbp"),
        )
        .group_by("date").agg(pl.col("cost_gbp").sum())
        .sort("date")
    )


def fiscal_year_resources(client: httpx.Client) -> dict[str, str]:
    """fiscal-year label ('2026-2027') -> CKAN resource id."""
    resources = ckan.dataset_resources(DATASET, api_base=ckan.NESO_API, client=client)
    out: dict[str, str] = {}
    for r in resources:
        m = _RESOURCE_NAME.fullmatch((r.get("name") or "").strip())
        if m:
            out[m.group(1)] = r["id"]
    return out


def update(store: SnapshotStore, *, client: httpx.Client | None = None) -> None:
    """Fetch any fiscal year not yet stored; always refresh the latest two
    (the current year grows daily and the prior year still settles)."""
    own = client is None
    client = client or httpx.Client(timeout=120)
    try:
        years = fiscal_year_resources(client)
        refresh = set(sorted(years)[-2:])
        for fy in sorted(years):
            if fy not in refresh and store.latest("bsuos", "daily", fy) is not None:
                continue
            records = ckan.fetch_all_records(
                years[fy], api_base=ckan.NESO_API, client=client)
            store.write("bsuos", "daily", parse_daily(records),
                        source_url=DATASET_URL, partition=fy, source_date=fy)
    finally:
        if own:
            client.close()
