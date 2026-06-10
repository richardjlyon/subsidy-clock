"""Wind constraint (curtailment) payments (spec 3.2): accepted Balancing
Mechanism bids from wind units — money paid to NOT generate."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import polars as pl

from subsidy_engine import elexon
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


def parse_stack(rows: list[dict], wind: dict[str, str]) -> pl.DataFrame:
    out = [
        {
            "date": date.fromisoformat(r["settlementDate"]),
            "settlement_period": r["settlementPeriod"],
            "bmu": r["id"],
            "lead_party": wind[r["id"]],
            "volume_mwh": float(r["volume"]),
            "price_gbp_mwh": float(r["originalPrice"]),
            "cost_gbp": float(r["volume"]) * float(r["originalPrice"]),
        }
        for r in rows
        if r.get("id") in wind and float(r.get("volume") or 0) < 0
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
            store.write(
                "constraints", "daily", day_df,
                source_url=SOURCE_URL, partition=partition, source_date=partition,
            )
            d += timedelta(days=1)
    finally:
        if own:
            client.close()


def update(store: SnapshotStore, *, days: int = 3, client: httpx.Client | None = None) -> None:
    """Refetch the last `days` complete days (settlement data firms up)."""
    end = date.today() - timedelta(days=1)
    backfill(store, end - timedelta(days=days - 1), end, client=client, skip_existing=False)
