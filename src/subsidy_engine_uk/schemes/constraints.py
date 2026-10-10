"""Wind constraint (curtailment) payments (spec 3.2): accepted Balancing
Mechanism bids from wind units — money paid to NOT generate.

Methodology: ALL accepted bids from wind BM units are counted, regardless of
soFlag, consistent with REF's published curtailment methodology. The soFlag
governs imbalance-price tagging, not whether the unit is paid; wind units bid
in the BM almost exclusively when being constrained off.

Cost basis (corrected 2026-10-10): cost = volume x originalPrice x
transmissionLossMultiplier, which is what Elexon settles. The multiplier
scales each unit's metered volume for transmission losses in its zone; for
northern Scottish units it is about 0.96. Volume alone (no multiplier) ran
3.7-3.9% above REF every year: 2024 GBP 410.8m vs REF 394.3m, 2025 GBP 397.4m
vs 382.1m. With the multiplier: 395.7m and 382.1m. Volume stays unscaled, as
REF publishes it (8.36 / 10.24 TWh, an exact match). Known limitations:
a failed day aborts the remainder of a backfill run (the missing day is
retried on the next run because its partition was never written), and a day
stored with zero rows is treated as complete by skip_existing."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import polars as pl

from subsidy_engine_uk import elexon
from subsidy_engine.store import SnapshotStore

SOURCE_URL = elexon.API_BASE + "/balancing/settlement/stack/all/bid"

SCHEMA = {
    "date": pl.Date,
    "settlement_period": pl.Int64,
    "bmu": pl.Utf8,
    "lead_party": pl.Utf8,
    "volume_mwh": pl.Float64,
    "price_gbp_mwh": pl.Float64,
    "cost_gbp": pl.Float64,
}


RESTATEMENT_CAUSE = ("basis change 2026-10-10: switch-off cost now applies Elexon's "
                     "transmission loss multiplier, as settled — see /corrections")
# Versions written before this were on the old basis (no multiplier).
BASIS_CHANGE_VERSION = "20261010T155900"  # the recount was written at 15:59 UTC


def parse_stack(rows: list[dict], wind: dict[str, str]) -> pl.DataFrame:
    out = [
        {
            "date": date.fromisoformat(r["settlementDate"]),
            "settlement_period": r["settlementPeriod"],
            "bmu": r["id"],
            "lead_party": wind[r["id"]],
            "volume_mwh": float(r["volume"]),
            "price_gbp_mwh": float(r["originalPrice"]),
            "cost_gbp": float(r["volume"]) * float(r["originalPrice"])
                        * float(r.get("transmissionLossMultiplier") or 1.0),
        }
        for r in rows
        if r.get("id") in wind
        and float(r.get("volume") or 0) < 0
        and r.get("originalPrice") is not None
        and r.get("settlementDate") and r.get("settlementPeriod") is not None
    ]
    return pl.DataFrame(out, schema=SCHEMA)


def daily_summary(df: pl.DataFrame) -> pl.DataFrame:
    return (
        df.group_by("date", "bmu", "lead_party")
        .agg(pl.col("volume_mwh").sum(), pl.col("cost_gbp").sum())
        .sort("date", "bmu")
    )


def fetch_day(d: date, wind: dict[str, str], client: httpx.Client) -> pl.DataFrame:
    frames = []
    for period in range(1, 51):  # 46-50 periods on clock-change days
        payload = elexon.get_json(
            f"/balancing/settlement/stack/all/bid/{d.isoformat()}/{period}", client
        )
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if rows:
            frames.append(parse_stack(rows, wind))
    if not frames:
        return pl.DataFrame(schema=SCHEMA)
    return pl.concat(frames)


def write_day(store: SnapshotStore, partition: str, day_df: pl.DataFrame) -> None:
    prev = store.latest_version("constraints", "daily", partition)
    ours = prev is not None and prev < BASIS_CHANGE_VERSION
    store.write(
        "constraints", "daily", day_df,
        source_url=SOURCE_URL, partition=partition, source_date=partition,
        restatement_cause=RESTATEMENT_CAUSE if ours else None,
    )


def backfill(
    store: SnapshotStore,
    start: date,
    end: date,
    *,
    client: httpx.Client | None = None,
    skip_existing: bool = True,
) -> None:
    own = client is None
    client = client or httpx.Client(timeout=60)
    try:
        wind = elexon.wind_bmu_map(client)
        d = start
        while d <= end:
            partition = d.isoformat()
            if skip_existing and store.latest("constraints", "daily", partition) is not None:
                d += timedelta(days=1)
                continue
            day_df = daily_summary(fetch_day(d, wind, client))
            write_day(store, partition, day_df)
            d += timedelta(days=1)
    finally:
        if own:
            client.close()


def update(store: SnapshotStore, *, days: int = 3, client: httpx.Client | None = None) -> None:
    """Refetch the last `days` complete days (settlement data firms up)."""
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    backfill(store, end - timedelta(days=days - 1), end, client=client, skip_existing=False)
