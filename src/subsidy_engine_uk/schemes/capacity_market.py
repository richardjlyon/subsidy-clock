"""Capacity Market (spec 3.5): actual monthly capacity payments by auction,
published by LCCC/EMRS. Shown as a separate band (all-levy total only)."""

from __future__ import annotations

import httpx
import polars as pl

from subsidy_engine.ckan import fetch_all_records
from subsidy_engine.store import SnapshotStore

RESOURCE = "2ed26d4f-ceb0-4a96-895e-4a3cc38c788c"
DATASET_URL = "https://dp.lowcarboncontracts.uk/dataset/capacity-obligation-by-auction"

_MONTHS = {
    "January": 1, "February": 2, "March": 3, "April": 4, "May": 5, "June": 6,
    "July": 7, "August": 8, "September": 9, "October": 10, "November": 11,
    "December": 12,
}


def parse_payments(records: list[dict]) -> pl.DataFrame:
    df = pl.DataFrame(records, infer_schema_length=None)
    return (
        df.select(
            pl.date(
                pl.col("Calendar_Year").cast(pl.Int32),
                pl.col("Calendar_Month").replace_strict(_MONTHS, default=None, return_dtype=pl.Int8),
                1,
            ).alias("date"),
            pl.col("Auction_Identifier").alias("auction"),
            pl.col("Capacity_Payment_GBP").cast(pl.Float64, strict=False).alias("payment_gbp"),
        )
        .drop_nulls("date")
        .drop_nulls("payment_gbp")
        .sort("date", "auction")
    )


def update(store: SnapshotStore, *, client: httpx.Client | None = None) -> None:
    df = parse_payments(fetch_all_records(RESOURCE, client=client))
    store.write("capacity_market", "payments", df, source_url=DATASET_URL, date_col="date")
