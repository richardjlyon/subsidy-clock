"""BSUoS balancing costs (phase 2 spec section 3): NESO's settled BSUoS data,
fetched per run-type/fiscal-year resource from the NESO CKAN portal.

Stored RAW (total daily gross BSUoS cost). Attribution to renewables - the
uplift above the CPIH-indexed 2002-05 baseline, NET of wind constraint payments
already counted in the direct layer - happens in the money model, never here.

SOURCE BASIS (corrected 2026-09-30, amendment `bsuos-basis-2026-09-30`).
This scheme previously summed the six cost columns of NESO's *Daily Balancing
Costs (BSUoS)* dataset. That dataset is a breakdown of balancing-mechanism and
ancillary spend, NOT the balancing cost recovered through BSUoS: its columns sum
to 23-39% BELOW the outturn in NESO's Annual Balancing Costs Report in every
year from 2018-19 (2023-24: GBP 1,824m against GBP 2,455m). Because the pre-2017
history in `reference/indirect_annual.yaml` and the GBP 0.4bn/yr 2002-05
baseline are both on the GROSS BSUoS basis, the old series spliced two
definitions mid-run - visible as a 63% cliff between raw 2016 (GBP 1,200m) and
raw 2017 (GBP 439m), a discontinuity no real event explains.

We now read the *Current Balancing Services Use of System (BSUoS) Charges*
dataset, which publishes the settled gross BSUoS cost per settlement period:

  * to 31 Mar 2023 - column ``Half-hourly Charge``. Pre-reform BSUoS was an
    ex-post pass-through, so charge == cost. Verified against the dataset's own
    ``Total Daily BSUoS Charge``: the half-hourly values foot to it to the penny.
  * from 1 Apr 2023 - column ``Actual BSUoS Cost``. The CMP308 fixed-tariff
    reform broke charge == cost (a BSUoS fund now absorbs the difference), so
    ``BSUoS Total Recovery`` is what users were billed, not what balancing cost.
    Cost is the basis that is continuous with the pre-reform series and with the
    baseline, so cost is what we take.

The resulting series runs 1.10-1.23x the Annual Balancing Costs Report outturn
with no step at either seam - the expected relationship, since the ABCR excludes
internal/administrative costs that BSUoS recovers and the NAO history includes.

Run types are the same days settled to different finality: II (interim initial),
SF (settlement final), RF (reconciliation final). We take the most settled figure
available for each DAY - RF, then SF, then II - so a partially-published resource
cannot displace a settled one.
"""

from __future__ import annotations

import re
from datetime import date

import httpx
import polars as pl

from subsidy_engine import ckan
from subsidy_engine.store import SnapshotStore

DATASET = "current-balancing-services-use-of-system-bsuos-data"
DATASET_URL = ("https://www.neso.energy/data-portal/"
               "current-balancing-services-use-of-system-bsuos-data")

# The CMP308 fixed-tariff reform. Before: BSUoS was an ex-post pass-through and
# the published half-hourly charge IS the cost. After: charge and cost diverge,
# and the dataset publishes cost explicitly.
REFORM = date(2023, 4, 1)

COST_COL_PRE = "Half-hourly Charge"
COST_COL_POST = "Actual BSUoS Cost (£)"

# NESO's column spelling is not stable across the resources of this one dataset:
# the day column is "Settlement Day" in most and "Settlement Date" in the Current
# RF/SF files; the cost column is "Actual BSUoS Cost (£)" in most and
# "Actual BSUoS Cost(£)" (no space) in the II 2023-2024 file; and recovery
# appears as both "BSUoS Total Recovery ()" and "...(£)". Matching on exact
# strings therefore breaks a fetch whenever a resource is republished with a
# different spelling. We match on a normalised key instead — case, whitespace
# and punctuation stripped — and still fail loudly when nothing matches.
DAY_KEYS = ("settlementday", "settlementdate")
COST_KEYS_POST = ("actualbsuoscost",)
COST_KEYS_PRE = ("halfhourlycharge",)


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _find(columns: list[str], keys: tuple[str, ...]) -> str | None:
    by_norm = {_norm(c): c for c in columns}
    for k in keys:
        if k in by_norm:
            return by_norm[k]
    return None

# Most-settled first. A day present in several run types takes the first hit.
RUN_TYPE_PRECEDENCE = ("RF", "SF", "II")

# "Historic RF BSUoS Data"           -> the pre-reform archive (no year suffix)
# "Historic RF BSUoS Data 2023-2024" -> one post-reform fiscal year
# "Current RF BSUoS Data"            -> the fiscal year in progress
_RESOURCE_NAME = re.compile(
    r"(?P<era>Historic|Current) (?P<run_type>II|SF|RF) BSUoS Data"
    r"(?: (?P<fy>\d{4}-\d{4}))?")

SCHEMA = {"date": pl.Date, "cost_gbp": pl.Float64}

# Stamped on every restatement this scheme writes, so the published log does not
# credit NESO with a revision that was ours. Days already stored under the old
# Daily Balancing Costs basis differ from the same days read here, and that
# difference is a change of source, not a publisher restating its history.
RESTATEMENT_CAUSE = ("basis change 2026-09-30: series moved from NESO's Daily "
                     "Balancing Costs dataset to settled BSUoS charge data "
                     "(gross BSUoS basis) — see /corrections")


def _fiscal_year(d: date) -> str:
    """'2023-2024' for any day in the fiscal year beginning April 2023."""
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{start + 1}"


def parse_periods(records: list[dict]) -> pl.DataFrame:
    """Settlement-period rows -> one gross cost per day.

    Reads whichever day and cost column the resource carries, so pre- and
    post-reform resources parse through the same path despite NESO's
    inconsistent column spellings.
    """
    if not records:
        return pl.DataFrame(schema=SCHEMA)
    df = pl.DataFrame(records, infer_schema_length=None)
    day = _find(df.columns, DAY_KEYS)
    if day is None:
        raise ValueError(
            f"BSUoS resource carries no settlement-day column "
            f"(looked for {DAY_KEYS}); columns were {df.columns}")
    # Post-reform cost wins where both are present: after the fixed-tariff
    # reform the half-hourly charge is no longer the cost.
    cost = (_find(df.columns, COST_KEYS_POST)
            or _find(df.columns, COST_KEYS_PRE))
    if cost is None:
        raise ValueError(
            f"BSUoS resource carries neither an actual-cost nor a "
            f"half-hourly-charge column; columns were {df.columns}")
    return (
        df.select(
            pl.col(day).cast(pl.Utf8).str.slice(0, 10)
              .str.to_date().alias("date"),
            pl.col(cost).cast(pl.Float64, strict=False)
              .fill_null(0.0).alias("cost_gbp"),
        )
        .group_by("date").agg(pl.col("cost_gbp").sum())
        .sort("date")
    )


def _expected_cost_col(d: date) -> str:
    return COST_COL_POST if d >= REFORM else COST_COL_PRE


def resources(client: httpx.Client) -> list[dict]:
    """The CSV BSUoS run-type resources, most-settled run type first.

    The XLSX CMP381/CMP395 resources are charge-model impact assessments, not
    the settled series, and are skipped.
    """
    out: list[dict] = []
    for r in ckan.dataset_resources(DATASET, api_base=ckan.NESO_API,
                                    client=client):
        if (r.get("format") or "").upper() != "CSV":
            continue
        m = _RESOURCE_NAME.fullmatch((r.get("name") or "").strip())
        if not m:
            continue
        out.append({"id": r["id"], "name": r["name"],
                    "run_type": m.group("run_type"),
                    "era": m.group("era"),
                    "fy": m.group("fy")})
    out.sort(key=lambda r: RUN_TYPE_PRECEDENCE.index(r["run_type"]))
    if not out:
        raise RuntimeError(
            f"no BSUoS run-type resources found in CKAN dataset {DATASET!r}")
    return out


def update(store: SnapshotStore, *, client: httpx.Client | None = None) -> None:
    """Rebuild the daily series from the most settled run type per day.

    Every resource is read on each run. The pre-reform archive is static, but
    post-reform fiscal years re-settle for months (II -> SF -> RF), so a
    "fetch once" rule would pin a year to its interim figures for good. The
    store's restatement log records any day whose settled value moves.
    """
    own = client is None
    client = client or httpx.Client(timeout=180)
    try:
        # date -> cost, filled in run-type precedence order; first write wins,
        # so the most settled run type present for a day is the one kept.
        best: dict[date, float] = {}
        for res in resources(client):
            records = ckan.fetch_all_records(
                res["id"], api_base=ckan.NESO_API, client=client)
            df = parse_periods(records)
            for d, cost in zip(df["date"], df["cost_gbp"]):
                best.setdefault(d, cost)

        if not best:
            raise RuntimeError("BSUoS: every run-type resource was empty")

        daily = (pl.DataFrame({"date": list(best), "cost_gbp": list(best.values())},
                              schema=SCHEMA)
                 .sort("date"))
        by_fy: dict[str, list[date]] = {}
        for d in daily["date"]:
            by_fy.setdefault(_fiscal_year(d), []).append(d)
        for fy, days in sorted(by_fy.items()):
            part = daily.filter(pl.col("date").is_in(days))
            store.write("bsuos", "daily", part,
                        source_url=DATASET_URL, partition=fy, source_date=fy,
                        date_col="date",
                        restatement_cause=RESTATEMENT_CAUSE)
    finally:
        if own:
            client.close()
