"""The money model (spec M-1..M-7): converts stored scheme records into the
cumulative totals, run-rates and per-second rates the dashboard presents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import polars as pl

from subsidy_engine.reference import ReferenceScheme
from subsidy_engine.store import SnapshotStore

SECONDS_PER_YEAR = 365.25 * 86400  # 31_557_600
PERSPECTIVES = ["renewables", "low_carbon", "all_levy"]


@dataclass
class SchemeResult:
    scheme_id: str
    label: str
    perspectives: list[str]
    cadence: str
    annual: pl.DataFrame                  # year, cost_gbp
    cumulative_gbp: float
    runrate_gbp_per_year: float
    data_to: date | None
    extras: dict = field(default_factory=dict)


def cumulative(daily: pl.DataFrame, col: str = "cost_gbp") -> float:
    return float(daily[col].sum()) if daily.height else 0.0


def annualise_daily(daily: pl.DataFrame, col: str = "cost_gbp") -> pl.DataFrame:
    return (
        daily.group_by(pl.col("date").dt.year().alias("year"))
        .agg(pl.col(col).sum().alias("cost_gbp"))
        .sort("year")
        .cast({"year": pl.Int64, "cost_gbp": pl.Float64})
    )


def trailing_runrate(daily: pl.DataFrame, *, col: str = "cost_gbp",
                     window_days: int = 365) -> float:
    """Annualised rate from the trailing window, scaled by the days the data
    actually covers so short backfills are not understated."""
    if not daily.height:
        return 0.0
    end = daily["date"].max()
    start = end - timedelta(days=window_days - 1)
    window = daily.filter(pl.col("date") >= start)
    covered_days = (end - max(start, daily["date"].min())).days + 1
    return float(window[col].sum()) * (365.25 / covered_days)


def rate_per_second(runrate_gbp_per_year: float) -> float:
    return runrate_gbp_per_year / SECONDS_PER_YEAR


def gross_net(df: pl.DataFrame, col: str) -> tuple[float, float]:
    if not df.height:
        return 0.0, 0.0
    gross = float(df.filter(pl.col(col) > 0)[col].sum())
    net = float(df[col].sum())
    return gross, net


def merge_annual(reference: pl.DataFrame, bottom_up: pl.DataFrame) -> pl.DataFrame:
    """Bottom-up data wins for any year it covers (spec: honest precedence)."""
    if not bottom_up.height:
        return reference.sort("year")
    bu_years = bottom_up["year"].to_list()
    keep = reference.filter(~pl.col("year").is_in(bu_years))
    return pl.concat([keep, bottom_up]).sort("year")


def annual_to_result(scheme_id: str, ref: ReferenceScheme) -> SchemeResult:
    annual = ref.annual
    latest_year = int(annual["year"].max())
    return SchemeResult(
        scheme_id=scheme_id,
        label=ref.label,
        perspectives=ref.perspectives,
        cadence=ref.cadence,
        annual=annual,
        cumulative_gbp=float(annual["cost_gbp"].sum()),
        runrate_gbp_per_year=float(
            annual.filter(pl.col("year") == latest_year)["cost_gbp"][0]
        ),
        data_to=date(latest_year + 1, 3, 31),  # obligation/scheme year ends 31 March of the following year
        extras={"source": ref.source, "source_url": ref.source_url,
                "verified": ref.verified},
    )


def perspective_totals(schemes: list[SchemeResult]) -> dict:
    totals: dict = {}
    for p in PERSPECTIVES:
        members = [s for s in schemes if p in s.perspectives]
        annual = (
            pl.concat([s.annual for s in members])
            .group_by("year").agg(pl.col("cost_gbp").sum()).sort("year")
            if members else pl.DataFrame({"year": [], "cost_gbp": []})
        )
        runrate = sum(s.runrate_gbp_per_year for s in members)
        totals[p] = {
            "cumulative_gbp": sum(s.cumulative_gbp for s in members),
            "runrate_gbp_per_year": runrate,
            "rate_gbp_per_sec": rate_per_second(runrate),
            "annual": annual,
            "since_year": int(annual["year"].min()) if annual.height else None,
        }
    return totals


def build(store: SnapshotStore, refs: dict[str, ReferenceScheme]) -> dict:
    """Assemble every scheme result plus the three perspective totals."""
    schemes: list[SchemeResult] = []

    # --- CfD: bottom-up, split renewable / non-renewable by technology (M-7)
    gen = store.latest("cfd", "generation")
    if gen is not None and gen.height:
        for part, flag, perspectives, label in [
            ("cfd_renewable", True, PERSPECTIVES, "CfD - renewables"),
            ("cfd_low_carbon", False, ["low_carbon", "all_levy"],
             "CfD - nuclear & biomass"),
        ]:
            sub = gen.filter(pl.col("is_renewable") == flag)
            daily = (sub.group_by("date").agg(pl.col("payment_gbp").sum().alias("cost_gbp"))
                     .sort("date"))
            gross, net = gross_net(sub, "payment_gbp")
            schemes.append(SchemeResult(
                scheme_id=part, label=label, perspectives=perspectives, cadence="daily",
                annual=annualise_daily(daily),
                cumulative_gbp=cumulative(daily),
                runrate_gbp_per_year=trailing_runrate(daily),
                data_to=daily["date"].max() if daily.height else None,
                extras={"gross_gbp": gross, "net_gbp": net,
                        "mwh": float(sub["generation_mwh"].sum() or 0.0),
                        "by_technology": sub.group_by("technology")
                            .agg(pl.col("payment_gbp").sum().alias("cost_gbp"),
                                 pl.col("generation_mwh").sum())
                            .sort("cost_gbp", descending=True).to_dicts(),
                        "by_recipient": sub.group_by("unit_name", "technology")
                            .agg(pl.col("payment_gbp").sum().alias("cost_gbp"))
                            .sort("cost_gbp", descending=True).head(25).to_dicts()},
            ))

    # --- Constraints: bottom-up daily merged with curated annual history
    con_daily = store.read_all_partitions("constraints", "daily")
    history = refs["constraints_history"]
    if con_daily is not None and con_daily.height:
        daily = (con_daily.group_by("date").agg(pl.col("cost_gbp").sum()).sort("date"))
        bottom_up_annual = annualise_daily(daily)
        # Only trust bottom-up for years fully covered by the backfill window,
        # but also keep partial years that are after the history's last year.
        first_full_year = int(daily["date"].min().year) + (
            0 if daily["date"].min().month == 1 and daily["date"].min().day == 1 else 1
        )
        last_history_year = int(history.annual["year"].max())
        usable = bottom_up_annual.filter(
            (pl.col("year") >= first_full_year)
            | (pl.col("year") > last_history_year)
        )
        annual = merge_annual(history.annual, usable)
        runrate = trailing_runrate(daily)
        data_to = daily["date"].max()
        by_recipient = (con_daily.group_by("lead_party")
                        .agg(pl.col("cost_gbp").sum(),
                             pl.col("volume_mwh").sum())
                        .sort("cost_gbp", descending=True).head(25).to_dicts())
        curtailed_mwh = float(-con_daily["volume_mwh"].sum())
        bottom_up_from = daily["date"].min().isoformat()
        bottom_up_to = daily["date"].max().isoformat()
    else:
        annual = history.annual
        runrate = float(annual["cost_gbp"][-1])
        data_to = date(int(annual["year"].max()), 12, 31)
        by_recipient, curtailed_mwh = [], 0.0
        bottom_up_from = None
        bottom_up_to = None
    schemes.append(SchemeResult(
        scheme_id="constraints", label="Constraint payments (paid to switch off)",
        perspectives=PERSPECTIVES, cadence="daily",
        annual=annual,
        cumulative_gbp=float(annual["cost_gbp"].sum()),
        runrate_gbp_per_year=runrate,
        data_to=data_to,
        extras={"by_recipient": by_recipient, "curtailed_mwh": curtailed_mwh,
                "history_source_url": history.source_url,
                "bottom_up_from": bottom_up_from, "bottom_up_to": bottom_up_to},
    ))

    # --- Capacity Market: bottom-up monthly
    cm = store.latest("capacity_market", "payments")
    if cm is not None and cm.height:
        daily_like = cm.rename({"payment_gbp": "cost_gbp"})
        monthly = daily_like.group_by("date").agg(pl.col("cost_gbp").sum()).sort("date")
        # run-rate: the 12 calendar months ending at the latest published month
        max_d = monthly["date"].max()
        cutoff = date(max_d.year - 1, max_d.month, 1)
        last12 = monthly.filter(pl.col("date") > cutoff)
        schemes.append(SchemeResult(
            scheme_id="capacity_market", label="Capacity Market",
            perspectives=["all_levy"], cadence="monthly",
            annual=annualise_daily(monthly),
            cumulative_gbp=cumulative(monthly),
            runrate_gbp_per_year=float(last12["cost_gbp"].sum()),
            data_to=monthly["date"].max(),
        ))

    # --- Annual reference schemes (RO, FIT)
    for scheme_id in ("ro", "fit"):
        schemes.append(annual_to_result(scheme_id, refs[scheme_id]))

    return {"schemes": schemes, "perspectives": perspective_totals(schemes)}
