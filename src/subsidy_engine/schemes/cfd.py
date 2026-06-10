"""Contracts for Difference (spec 3.1). Bottom-up daily per-contract payments
published by LCCC, the scheme counterparty."""

from __future__ import annotations

import httpx
import polars as pl

from subsidy_engine.ckan import fetch_all_records
from subsidy_engine.store import SnapshotStore

GENERATION_RESOURCE = "37d1bef4-55d7-4b8e-8a47-1d24b123a20e"
TRACKING_RESOURCE = "003f527c-aa35-4198-adbb-21a61fc760eb"
DATASET_URL = (
    "https://dp.lowcarboncontracts.uk/dataset/actual-cfd-generation-and-avoided-ghg-emissions"
)
TRACKING_URL = "https://dp.lowcarboncontracts.uk/dataset/in-period-tracking"

# Technologies counted in the renewables-only total. Anything not listed
# (Nuclear, biomass variants, energy-from-waste, unknown future labels)
# counts toward "all low-carbon" only, so the renewables figure is never
# overstated by accident (spec M-7).
RENEWABLE_TECHNOLOGIES = {
    "Offshore Wind",
    "Onshore Wind",
    "Remote Island Wind",
    "Solar PV",
    "Tidal Stream",
    "Wave",
    "Hydro",
    "Geothermal",
}


def _lccc_date(col: str) -> pl.Expr:
    return pl.col(col).str.slice(0, 10).str.to_date().alias("date")


def parse_generation(records: list[dict]) -> pl.DataFrame:
    df = pl.DataFrame(records, infer_schema_length=None)
    return (
        df.select(
            _lccc_date("Settlement_Date"),
            pl.col("CfD_ID").alias("cfd_id"),
            pl.col("Name_of_CfD_Unit").alias("unit_name"),
            pl.col("Technology").alias("technology"),
            pl.col("CFD_Generation_MWh").cast(pl.Float64, strict=False).alias("generation_mwh"),
            pl.col("CFD_Payments_GBP").cast(pl.Float64, strict=False).alias("payment_gbp"),
            pl.col("Strike_Price_GBP_Per_MWh").cast(pl.Float64, strict=False)
              .alias("strike_price_gbp_mwh"),
        )
        .drop_nulls("payment_gbp")
        .with_columns(pl.col("technology").is_in(RENEWABLE_TECHNOLOGIES).fill_null(False).alias("is_renewable"))
        .sort("date", "cfd_id")
    )


def parse_tracking(records: list[dict]) -> pl.DataFrame:
    df = pl.DataFrame(records, infer_schema_length=None)
    return (
        df.select(
            _lccc_date("Settlement_Date"),
            pl.col("Actual_CFD_Payments_GBP").cast(pl.Float64, strict=False).alias("payment_gbp"),
        )
        .drop_nulls("payment_gbp")
        .sort("date")
    )


def update(store: SnapshotStore, *, client: httpx.Client | None = None) -> None:
    gen = parse_generation(fetch_all_records(GENERATION_RESOURCE, client=client))
    store.write("cfd", "generation", gen, source_url=DATASET_URL, date_col="date")
    trk = parse_tracking(fetch_all_records(TRACKING_RESOURCE, client=client))
    store.write("cfd", "tracking", trk, source_url=TRACKING_URL, date_col="date")
