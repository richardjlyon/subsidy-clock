"""The money model (spec M-1..M-7): converts stored scheme records into the
cumulative totals, run-rates and per-second rates the dashboard presents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import polars as pl

from subsidy_engine.reference import ReferenceScheme

SECONDS_PER_YEAR = 365.25 * 86400  # 31_557_600
PERSPECTIVES = ["renewables", "low_carbon"]


@dataclass
class SchemeResult:
    scheme_id: str
    label: str
    perspectives: list[str]
    cadence: str
    annual: pl.DataFrame                  # year, cost_gbp[, cost_gbp_2024]
    cumulative_gbp: float
    runrate_gbp_per_year: float
    data_to: date | None
    layer: str = "direct"
    attribution_pct: float = 1.0
    attribution_note: str = ""
    attribution_confidence: str = ""
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


REAL_BASE_YEAR = 2024


def _base_index(deflators: pl.DataFrame) -> float:
    return float(deflators.filter(
        pl.col("year") == REAL_BASE_YEAR)["index"][0])


def _latest_index(deflators: pl.DataFrame) -> float:
    return float(deflators.sort("year")["index"][-1])


def add_real(annual: pl.DataFrame, deflators: pl.DataFrame) -> pl.DataFrame:
    """Add cost_gbp_2024 restated in REAL_BASE_YEAR prices; years beyond the
    deflator series use the latest index (recent money ~ current prices)."""
    base = _base_index(deflators)
    latest = _latest_index(deflators)
    return (
        annual.join(deflators, on="year", how="left")
        .with_columns((pl.col("cost_gbp") * base / pl.col("index").fill_null(latest))
                      .alias("cost_gbp_2024"))
        .drop("index")
    )


def latest_real_factor(deflators: pl.DataFrame) -> float:
    """Factor converting current-year money to REAL_BASE_YEAR prices."""
    return _base_index(deflators) / _latest_index(deflators)


YEAR_ENDS = {           # year_basis -> (years after the keyed year, month, day)
    "calendar": (0, 12, 31),        # calendar series end 31 Dec
    "obligation_apr": (1, 3, 31),   # UK obligation years end 31 Mar
}


def year_end(latest_year: int, year_basis: str) -> date:
    """The date a scheme's reporting year closes. An unknown basis raises: the core
    carries no jurisdiction's convention as a fall-through, so a basis it has never
    heard of (an Australian 1 Jul-30 Jun year, say) fails loudly rather than being
    published as a plausible-looking UK 31 March."""
    if year_basis not in YEAR_ENDS:
        raise ValueError(f"unknown year_basis {year_basis!r}; known: {sorted(YEAR_ENDS)}")
    offset, month, day = YEAR_ENDS[year_basis]
    return date(latest_year + offset, month, day)


def annual_to_result(scheme_id: str, ref: ReferenceScheme, *,
                     layer: str = "direct",
                     extra_extras: dict | None = None) -> SchemeResult:
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
        data_to=year_end(latest_year, ref.year_basis),
        layer=layer,
        attribution_note=ref.attribution_rule,
        attribution_confidence=ref.attribution_confidence,
        extras={"source": ref.source, "source_url": ref.source_url,
                "verified": ref.verified, **(extra_extras or {})},
    )


def _aggregate(members: list[SchemeResult]) -> dict:
    has_real = bool(members and all("cost_gbp_2024" in s.annual.columns for s in members))
    agg_cols = [pl.col("cost_gbp").sum()] + (
        [pl.col("cost_gbp_2024").sum()] if has_real else [])
    annual = (
        pl.concat([s.annual for s in members])
        .group_by("year").agg(agg_cols).sort("year")
        if members else pl.DataFrame({"year": [], "cost_gbp": []})
    )
    runrate = sum(s.runrate_gbp_per_year for s in members)
    out = {
        "cumulative_gbp": sum(s.cumulative_gbp for s in members),
        "runrate_gbp_per_year": runrate,
        "rate_gbp_per_sec": rate_per_second(runrate),
        "annual": annual,
        "since_year": int(annual["year"].min()) if annual.height else None,
    }
    if has_real:
        out["cumulative_gbp_2024"] = float(annual["cost_gbp_2024"].sum())
    return out


def perspective_totals(schemes: list[SchemeResult]) -> dict:
    direct = [s for s in schemes if s.layer == "direct"]
    return {p: _aggregate([s for s in direct if p in s.perspectives])
            for p in PERSPECTIVES}


def layer_total(schemes: list[SchemeResult], layer: str) -> dict:
    return _aggregate([s for s in schemes if s.layer == layer])
