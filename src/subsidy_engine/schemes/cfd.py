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

# Renewable CfD technologies. These are the generators that hold renewable
# CfDs and count toward the UK's renewable targets and REF's renewable
# subsidy totals — so they belong in the renewables headline. The biomass
# family (conversions like Drax, dedicated biomass, advanced conversion and
# energy-from-waste) is officially renewable and is counted here; excluding it
# would understate renewable subsidy and mismatch every external aggregate we
# reconcile against (spec M-7).
RENEWABLE_TECHNOLOGIES = {
    "Offshore Wind",
    "Onshore Wind",
    "Remote Island Wind",
    "Solar PV",
    "Tidal Stream",
    "Wave",
    "Hydro",
    "Geothermal",
    "Biomass Conversion",
    "Dedicated Biomass",
    "Advanced Conversion Technology",
    "Energy from Waste",
}

# The only non-renewable low-carbon CfD technology. Nuclear is listed
# explicitly (rather than caught as a residual) so that an unrecognised
# technology label fails the build loudly — see _check_technologies — instead
# of silently dropping into either bucket.
NUCLEAR_TECHNOLOGIES = {
    "Nuclear",
}

KNOWN_TECHNOLOGIES = RENEWABLE_TECHNOLOGIES | NUCLEAR_TECHNOLOGIES


def _check_technologies(df: pl.DataFrame) -> None:
    """Fail loudly if LCCC publishes a technology we have not classified.

    Every CfD technology must be explicitly assigned to either the renewable
    or the nuclear set. An unknown label is the one way a generator could be
    silently mis-bucketed (the failure mode that previously left biomass out
    of the renewables headline), so we refuse to build until it is classified."""
    seen = set(df.select("technology").unique().to_series().to_list())
    unknown = {t for t in seen if t is not None} - KNOWN_TECHNOLOGIES
    if unknown:
        raise ValueError(
            "Unclassified CfD technology label(s): "
            f"{sorted(unknown)}. Add each to RENEWABLE_TECHNOLOGIES or "
            "NUCLEAR_TECHNOLOGIES in schemes/cfd.py before rebuilding.")


def is_renewable_expr() -> pl.Expr:
    """The single source of truth for the renewable/non-renewable CfD split.

    Used both when parsing freshly fetched data and when building the money
    model from the stored history, so a change to RENEWABLE_TECHNOLOGIES takes
    effect on the whole back-catalogue without refetching — the classification
    is a live policy, not a value frozen into the immutable store."""
    return (pl.col("technology").is_in(RENEWABLE_TECHNOLOGIES)
            .fill_null(False).alias("is_renewable"))


def classify(df: pl.DataFrame) -> pl.DataFrame:
    """Apply the current renewable/nuclear policy to a generation frame,
    failing loudly on any unclassified technology label."""
    _check_technologies(df)
    return df.with_columns(is_renewable_expr())


def _lccc_date(col: str) -> pl.Expr:
    return pl.col(col).str.slice(0, 10).str.to_date().alias("date")


def parse_generation(records: list[dict]) -> pl.DataFrame:
    df = pl.DataFrame(records, infer_schema_length=None)
    parsed = (
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
        .sort("date", "cfd_id")
    )
    # The store holds only what LCCC publishes; is_renewable is our
    # classification (a live policy) and is derived at build time, not frozen
    # into the snapshot — see classify(). We still guard at fetch so a new
    # technology label fails fast.
    _check_technologies(parsed)
    return parsed


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
