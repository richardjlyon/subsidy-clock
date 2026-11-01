"""Capacity Market (spec 3.5): actual monthly capacity payments by auction,
published by LCCC/EMRS. Shown as a separate band (all-levy total only)."""

from __future__ import annotations

from datetime import date

import httpx
import polars as pl

from subsidy_engine.ckan import fetch_all_records
from subsidy_engine.money import SchemeResult, add_real, annualise_daily, cumulative
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


# --- Result (moved from build.py, aios-harness#38)

CM_SHARE_DRIFT = 0.02   # max relative gap between the Clock's annual CM and the engine's cm_paid


def cm_netzero_shares(raw_annual: pl.DataFrame, cm_share: dict) -> pl.DataFrame:
    """Per calendar year of Capacity Market data: the share of the levy that
    net zero caused (central, low, high) and its basis.

    Years the engine covers take its own share; any later year takes the share
    of ``carry_forward_from`` (basis "carried forward"); a year BEFORE the
    engine's first year is an error, not a silent 100%. Fails if the Clock's own
    annual total for a covered year drifts more than CM_SHARE_DRIFT from the
    engine's cm_paid, because the share was computed against that total."""
    years = cm_share["years"]
    carry = cm_share["carry_forward_from"]
    first = min(years)
    rows = []
    for r in raw_annual.to_dicts():
        y = int(r["year"])
        if y in years:
            row, basis = years[y], "modelled"
            paid = float(row["cm_paid_gbp"])
            if abs(r["cost_gbp"] - paid) > CM_SHARE_DRIFT * paid:
                raise ValueError(
                    f"Capacity Market {y}: the Clock's total {r['cost_gbp']:,.0f} differs "
                    f"from the {paid:,.0f} the net-zero share was computed against by more "
                    f"than {CM_SHARE_DRIFT:.0%}; rerun the gas-counterfactual engine")
        elif y > carry:
            row, basis = years[carry], f"carried forward from {carry}"
        else:
            raise ValueError(f"Capacity Market {y}: no net-zero share (engine starts {first})")
        rows.append({"year": y, "share": row["share"], "share_low": row["share_low"],
                     "share_high": row["share_high"], "basis": basis})
    return pl.DataFrame(rows, schema={"year": pl.Int64, "share": pl.Float64,
                                      "share_low": pl.Float64, "share_high": pl.Float64,
                                      "basis": pl.String})


def result(store: SnapshotStore, cm_share: dict | None,
           deflators: pl.DataFrame) -> list[SchemeResult]:
    """The Capacity Market line, or none without data."""
    # --- Capacity Market: bottom-up monthly, net-zero share only (change of
    # 13 Oct 2026). Any power system needs backup, so the levy is NOT counted
    # in full: each month's LCCC payment is scaled by share(year) = (CM paid -
    # what "Reliable Britain", the actual system with net-zero policy removed,
    # would have paid for its own backup) / CM paid, from
    # reference/capacity_market_netzero_share.yaml (gas-counterfactual engine,
    # spec 5.4). The same rule as TNUoS/BSUoS: count only what net zero added.
    # Years after the engine's last year carry its last share forward.
    # Rejected: pasting in the engine's pounds per year. Scaling the measured
    # months keeps the line on LCCC's live data, so a restated month moves it
    # in proportion; the drift guard below says when the shares are stale.
    cm = store.latest("capacity_market", "payments")
    if cm is None or not cm.height:
        return []
    if cm_share is None:
        raise ValueError(
            "capacity_market data present but no cm_share table: the Clock "
            "counts only the net-zero share of the Capacity Market "
            "(reference/capacity_market_netzero_share.yaml)")
    daily_like = cm.rename({"payment_gbp": "cost_gbp"})
    monthly = daily_like.group_by("date").agg(pl.col("cost_gbp").sum()).sort("date")
    raw_annual_cm = annualise_daily(monthly)
    shares = cm_netzero_shares(raw_annual_cm, cm_share)
    weighted = (monthly.with_columns(pl.col("date").dt.year().cast(pl.Int64).alias("year"))
                .join(shares, on="year", how="left"))
    attributed_monthly = weighted.select(
        "date", (pl.col("cost_gbp") * pl.col("share")).alias("cost_gbp"))
    # run-rate: the 12 calendar months ending at the latest published month
    max_d = monthly["date"].max()
    cutoff = date(max_d.year - 1, max_d.month, 1)
    last12 = attributed_monthly.filter(pl.col("date") > cutoff)
    cm_annual = annualise_daily(attributed_monthly)
    raw_total = cumulative(monthly)
    cm_cum = cumulative(attributed_monthly)
    rng = {}
    for tag in ("low", "high"):
        band = annualise_daily(weighted.select(
            "date", (pl.col("cost_gbp") * pl.col(f"share_{tag}")).alias("cost_gbp")))
        band = add_real(band, deflators)
        rng[tag] = {"cumulative": float(band["cost_gbp"].sum()),
                    "cumulative_real": float(band["cost_gbp_2024"].sum())}
    carry = cm_share["carry_forward_from"]
    carry_pct = cm_share["years"][carry]["share"] * 100
    return [SchemeResult(
        scheme_id="capacity_market", label="Capacity Market",
        perspectives=[], cadence="monthly",
        layer="indirect",
        attribution_pct=(cm_cum / raw_total) if raw_total else 0.0,
        attribution_note=(
            "Only the part of the Capacity Market that net zero caused is "
            "counted. Any power system needs backup, so each year's levy is "
            "reduced by what the same system without net-zero policy would "
            "have paid at that year's capacity price for its own backup; the "
            "remainder is counted. Shares for 2016-" + str(carry) + " come "
            "from a model of that system; later years use the " + str(carry) +
            f" share ({carry_pct:.1f}%) until the model covers them. The "
            "figure is a floor: a 550 g/kWh emissions limit has kept about 11 GW "
            "of coal out of the four-year-ahead auctions since 2021, and "
            "capacity prices rose after it; no published source measures how "
            "much of that rise net zero caused, so none of it is counted."),
        attribution_confidence="medium",
        annual=cm_annual,
        cumulative_gbp=cm_cum,
        runrate_gbp_per_year=float(last12["cost_gbp"].sum()),
        data_to=monthly["date"].max(),
        extras={"source": "LCCC data portal, capacity market payments",
                "source_url": "https://dp.lowcarboncontracts.uk/dataset/capacity-obligation-by-auction",
                "raw_annual": raw_annual_cm.rename({"cost_gbp": "cost"}).to_dicts(),
                "netzero_share": [
                    {"year": r["year"], "share": r["share"],
                     "share_low": r["share_low"], "share_high": r["share_high"],
                     "basis": r["basis"]}
                    for r in shares.to_dicts()],
                "range": rng,
                "share_provenance": {
                    k: cm_share.get("provenance", {}).get(k)
                    for k in ("engine", "commit", "commit_date", "file")},
                "carry_forward_from": carry},
    )]
