"""Elexon REMIT unavailability history for the mapped stations' BM units.

Feeds the per-asset X-ray panels' outage strips. Coverage was verified before
this module was built (openspec change add-interactive-asset-map,
verification.md): the Insights platform carries the historical archive from
2016, per-BMU filtering works via ``assetId``, and ``latestRevisionOnly=true``
collapses revisions server-side. We still re-collapse per mRID defensively —
REMIT messages are revision-heavy and a stale revision that slipped through
would misstate an outage.

Fetch shape: one light list call per (BMU, 6-month window) to collect message
ids, then batched detail fetches. ~37 BMUs x ~21 windows is ~800 small
requests per update.
"""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import polars as pl

from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk.elexon import API_BASE

# Platform history depth, verified 2026-07-29 (2014-15 hold single-figure
# stragglers; usable coverage starts 2016). Stamped into every asset's outage
# block so the panel can state its window — records before this date are
# unknown, not absent.
COVERAGE_FROM = date(2016, 1, 1)

SOURCE_URL = "https://bmrs.elexon.co.uk/remit"

_WINDOW_DAYS = 180   # stream endpoint caps ranges well above this; 6-month steps
_BATCH = 50          # message-detail ids per request


def _windows(start: date, end: date):
    d = start
    while d < end:
        e = min(d + timedelta(days=_WINDOW_DAYS), end)
        yield d, e
        d = e


def fetch_messages(bmu_ids: list[str], *, client: httpx.Client,
                   today: date) -> list[dict]:
    """All REMIT unavailability messages for the given BMUs since COVERAGE_FROM."""
    ids: set[int] = set()
    for bmu in bmu_ids:
        for frm, to in _windows(COVERAGE_FROM, today):
            r = client.get(f"{API_BASE}/remit/list/by-event/stream",
                           params={"from": frm.isoformat(), "to": to.isoformat(),
                                   "assetId": bmu, "latestRevisionOnly": "true"})
            r.raise_for_status()
            ids.update(rec["id"] for rec in (r.json() or []))
    details: list[dict] = []
    ordered = sorted(ids)
    for i in range(0, len(ordered), _BATCH):
        batch = ordered[i:i + _BATCH]
        r = client.get(f"{API_BASE}/remit",
                       params=[("messageId", m) for m in batch])
        r.raise_for_status()
        details.extend(r.json().get("data", []))
    return details


def parse_messages(records: list[dict]) -> pl.DataFrame:
    """Message details -> one row per outage message, latest revision per mRID."""
    rows = [
        {
            "mrid": r["mrid"],
            "revision": int(r.get("revisionNumber") or 0),
            "bmu": r.get("assetId"),
            "unavailability_type": r.get("unavailabilityType"),
            "event_start": r.get("eventStartTime"),
            "event_end": r.get("eventEndTime"),
            "unavailable_mw": float(r["unavailableCapacity"])
                if r.get("unavailableCapacity") is not None else None,
            "normal_mw": float(r["normalCapacity"])
                if r.get("normalCapacity") is not None else None,
        }
        for r in records
        if r.get("mrid") and r.get("eventStartTime") and r.get("eventEndTime")
    ]
    if not rows:
        return pl.DataFrame(schema={
            "mrid": pl.Utf8, "revision": pl.Int64, "bmu": pl.Utf8,
            "unavailability_type": pl.Utf8, "event_start": pl.Utf8,
            "event_end": pl.Utf8, "unavailable_mw": pl.Float64,
            "normal_mw": pl.Float64,
        })
    df = pl.DataFrame(rows, infer_schema_length=None)
    # defensive revision collapse (the list call already asked for latest only)
    return (df.sort("revision")
              .group_by("mrid", maintain_order=True).last()
              .sort("event_start", "mrid"))


def update(store: SnapshotStore, bmu_ids: list[str], *,
           client: httpx.Client | None = None,
           today: date | None = None) -> None:
    own = client is None
    client = client or httpx.Client(timeout=60)
    try:
        msgs = fetch_messages(bmu_ids, client=client,
                              today=today or date.today())
        df = parse_messages(msgs)
        store.write("remit", "outages", df, source_url=SOURCE_URL)
    finally:
        if own:
            client.close()
