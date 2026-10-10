"""Constraint turn-up: what NESO pays plant to switch ON (spec: constraint-turnup).

When wind behind a bottleneck is paid to switch off (the `constraints` scheme),
the same energy has to be bought from somewhere else on the right side of the
bottleneck - mostly gas. That second payment has always been inside the BSUoS
line; this scheme measures it on its own so it can be shown and so BSUoS can be
netted of it.

Source: Elexon Insights settlement stacks, the same public API as
`constraints.py` - `/balancing/settlement/stack/all/{bid,offer}/{date}/{period}`.
Stack data starts in mid-November 2015; earlier days return no rows.

Four bases are stored per day, one row per (basis, fuel):

  replacement_estimate  THE ENGINE FIGURE (Octopus Wasted Wind's method): the
                        volume of system-flagged wind bids in each period,
                        priced by walking that period's accepted offers (CADL
                        offers excluded; unflagged first, then by sequence
                        number; pro-rata at the margin). Tied by construction
                        to the wind volume switched off; reproduces Octopus's
                        published monthly figures. It is an estimate of the
                        cost of replacement energy, not money paid to named
                        units.
  accepted_offers       Cross-check. Accepted offers (positive volume)
                        flagged as system actions (soFlag) from units that are
                        not wind, volume x original price, by registered fuel.
                        soFlag marks actions taken for locational/system reasons
                        rather than energy balance. It is broader than thermal
                        constraints (voltage and inertia actions carry it too),
                        so it overstates wind-caused turn-up.
  accepted_offers_wind  Cross-check. accepted_offers restricted to periods in
                        which wind was switched off: money actually paid while
                        wind was being constrained.
  wind_bids_so          System-flagged wind bids (Octopus's curtailment
                        definition; the `constraints` scheme counts all wind
                        bids). Reconciliation only.

Only replacement_estimate enters a published total.
"""

from __future__ import annotations

import concurrent.futures as cf
import time
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

import httpx
import polars as pl

from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk import elexon

SCHEME = "constraint_turnup"
TABLE = "daily"
SOURCE_URL = elexon.API_BASE + "/balancing/settlement/stack/all/offer"
FIRST_STACK_DATE = date(2015, 11, 1)   # first month Elexon returns stack rows

ACCEPTED = "accepted_offers"
ACCEPTED_WIND = "accepted_offers_wind"
ESTIMATE = "replacement_estimate"
WIND_SO = "wind_bids_so"

UNCLASSIFIED = "UNCLASSIFIED"   # in the register, no fuel type
UNMAPPED = "UNMAPPED"           # not in the current register (e.g. retired)
NO_ID = "NO_ID"                 # stack row carries no unit id
TRADE = "NESO_TRADE"            # numeric id, no acceptance: a NESO trade
                                # (balancing services adjustment), not a BM unit

SCHEMA = {
    "date": pl.Date,
    "basis": pl.Utf8,
    "fuel": pl.Utf8,
    "volume_mwh": pl.Float64,
    "cost_gbp": pl.Float64,
}


def fuel_map(client: httpx.Client) -> dict[str, str | None]:
    """elexonBmUnit -> registered fuel type (None where the register has none)."""
    units = elexon.get_json("/reference/bmunits/all", client)
    return {u["elexonBmUnit"]: u.get("fuelType")
            for u in units if u.get("elexonBmUnit")}


def _fuel(uid: str | None, fuel: dict[str, str | None],
          acceptance_id: object = 0) -> str:
    if not uid:
        return NO_ID
    if uid.isdigit() and acceptance_id is None:
        return TRADE
    if uid not in fuel:
        return UNMAPPED
    return fuel[uid] or UNCLASSIFIED


def accepted_offers(offers: list[dict], fuel: dict) -> dict[str, tuple[float, float]]:
    """Method (a): system-flagged accepted offers from non-wind units, by fuel."""
    out: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    for o in offers:
        vol = float(o.get("volume") or 0)
        price = o.get("originalPrice")
        if not o.get("soFlag") or vol <= 0 or price is None:
            continue
        f = _fuel(o.get("id"), fuel, o.get("acceptanceId", 0))
        if f == "WIND":
            continue
        out[f][0] += vol
        out[f][1] += vol * float(price)
    return {k: (v[0], v[1]) for k, v in out.items()}


def wind_bids_so(bids: list[dict], fuel: dict) -> tuple[float, float]:
    """System-flagged wind bids: (volume, cost). Volume is negative."""
    vol = cost = 0.0
    for b in bids:
        if b.get("soFlag") and fuel.get(b.get("id")) == "WIND" \
                and b.get("originalPrice") is not None:
            v = float(b.get("volume") or 0)
            vol += v
            cost += v * float(b["originalPrice"])
    return vol, cost


def replacement_estimate(offers: list[dict], lost_mwh: float) -> tuple[float, float]:
    """Method (b), Octopus's walk: price `lost_mwh` against the period's offers."""
    target = abs(lost_mwh)
    if target <= 0:
        return 0.0, 0.0
    stack = sorted((o for o in offers if not o.get("cadlFlag")
                    and o.get("originalPrice") is not None),
                   key=lambda o: (bool(o.get("soFlag")), o.get("sequenceNumber") or 0))
    n = r = 0.0
    for o in stack:
        v = float(o.get("volume") or 0)
        p = float(o["originalPrice"])
        if n + v > target:
            share = min(max((target - n) / v, 0.0), 1.0) if v else 0.0
            n += v * share
            r += p * v * share
        else:
            n += v
            r += p * v
        if n >= target:
            break
    return n, r


def day_frame(d: date, periods: list[tuple[list[dict], list[dict]]],
              fuel: dict) -> pl.DataFrame:
    """One day's (bids, offers) per period -> rows per (basis, fuel)."""
    acc: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    accw: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
    est = [0.0, 0.0]
    wso = [0.0, 0.0]
    for bids, offers in periods:
        wv, wc = wind_bids_so(bids, fuel)
        for f, (v, c) in accepted_offers(offers, fuel).items():
            acc[f][0] += v
            acc[f][1] += c
            if wv:
                accw[f][0] += v
                accw[f][1] += c
        wso[0] += wv
        wso[1] += wc
        ev, ec = replacement_estimate(offers, wv)
        est[0] += ev
        est[1] += ec
    rows = [{"date": d, "basis": ACCEPTED, "fuel": f, "volume_mwh": v[0],
             "cost_gbp": v[1]} for f, v in sorted(acc.items())]
    rows += [{"date": d, "basis": ACCEPTED_WIND, "fuel": f, "volume_mwh": v[0],
              "cost_gbp": v[1]} for f, v in sorted(accw.items())]
    if wso[0]:
        rows.append({"date": d, "basis": ESTIMATE, "fuel": "ALL",
                     "volume_mwh": est[0], "cost_gbp": est[1]})
        rows.append({"date": d, "basis": WIND_SO, "fuel": "WIND",
                     "volume_mwh": wso[0], "cost_gbp": wso[1]})
    return pl.DataFrame(rows, schema=SCHEMA)


def _stack(side: str, d: date, period: int, client: httpx.Client,
           *, attempts: int = 7, pause: float = 1.0) -> list[dict]:
    """One stack call, retried with exponential backoff (Elexon throttles
    bursts; an immediate retry just hits the same wall)."""
    err: Exception | None = None
    for i in range(attempts):
        try:
            payload = elexon.get_json(
                f"/balancing/settlement/stack/all/{side}/{d.isoformat()}/{period}", client)
            return payload.get("data", []) if isinstance(payload, dict) else []
        except (httpx.HTTPError, ValueError) as exc:
            err = exc
            if i < attempts - 1:
                time.sleep(pause * 2 ** i)
    raise RuntimeError(f"turn-up: {side} stack {d} SP{period} failed") from err


def fetch_day(d: date, fuel: dict, client: httpx.Client,
              *, workers: int = 10) -> pl.DataFrame:
    """Both stacks for all 50 possible periods (46-50 on clock-change days),
    fetched concurrently: 100 calls a day sequentially would make the decade
    backfill take hours."""
    periods = range(1, 51)
    with cf.ThreadPoolExecutor(workers) as ex:
        bids = list(ex.map(lambda p: _stack("bid", d, p, client), periods))
        offers = list(ex.map(lambda p: _stack("offer", d, p, client), periods))
    return day_frame(d, list(zip(bids, offers)), fuel)


def backfill(store: SnapshotStore, start: date, end: date, *,
             client: httpx.Client | None = None, skip_existing: bool = True,
             progress: bool = False) -> tuple[int, list[date]]:
    """Fetch and store each day in [start, end].

    Returns (days written, days that failed after all retries). A failed day is
    NOT written, so a rerun with skip_existing picks it up; writing it as empty
    would silently understate the series."""
    own = client is None
    client = client or httpx.Client(timeout=60, limits=httpx.Limits(max_connections=10))
    written, failed = 0, []
    try:
        fuel = fuel_map(client)
        d = max(start, FIRST_STACK_DATE)
        while d <= end:
            part = d.isoformat()
            if not (skip_existing and store.latest(SCHEME, TABLE, part) is not None):
                try:
                    frame = fetch_day(d, fuel, client)
                except RuntimeError as exc:
                    failed.append(d)
                    print(f"[turnup] FAILED {part}: {exc}", flush=True)
                else:
                    store.write(SCHEME, TABLE, frame, source_url=SOURCE_URL,
                                partition=part, source_date=part)
                    written += 1
                if progress and d.day == 1:
                    print(f"[turnup] {part}", flush=True)
            d += timedelta(days=1)
    finally:
        if own:
            client.close()
    return written, failed


def update(store: SnapshotStore, *, days: int = 3,
           client: httpx.Client | None = None) -> None:
    """Refetch the last `days` complete days (settlement data firms up)."""
    end = datetime.now(timezone.utc).date() - timedelta(days=1)
    _, failed = backfill(store, end - timedelta(days=days - 1), end,
                         client=client, skip_existing=False)
    if failed:
        raise RuntimeError(f"turn-up: {len(failed)} day(s) failed: "
                           + ", ".join(x.isoformat() for x in failed))


def read(store: SnapshotStore) -> pl.DataFrame | None:
    return store.read_all_partitions(SCHEME, TABLE)


def daily_cost(store: SnapshotStore, basis: str = ESTIMATE) -> pl.DataFrame:
    """date, cost_gbp for one basis (default: the engine figure, method b)."""
    df = read(store)
    if df is None or not df.height:
        return pl.DataFrame(schema={"date": pl.Date, "cost_gbp": pl.Float64})
    return (df.filter(pl.col("basis") == basis)
              .group_by("date").agg(pl.col("cost_gbp").sum()).sort("date"))
