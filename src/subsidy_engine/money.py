"""The money model (spec M-1..M-7): converts stored scheme records into the
cumulative totals, run-rates and per-second rates the dashboard presents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

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
    # run-rate in 2024 prices, converted from the line's own year
    # (runrate_real_factor); None until the build sets it
    runrate_gbp_per_year_2024: float | None = None


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


def carry_from(data_to: date) -> datetime:
    """The instant a line's estimate starts: midnight UTC at the end of the last
    day its published data cover (data_to is inclusive)."""
    d = data_to + timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def estimated_since(runrate_gbp_per_year: float, data_to: date | None,
                    at: datetime) -> float:
    """Cost incurred since a line's published data end, carried forward at the
    line's latest annual rate: rate x (at - end of data) / 365.25 days.

    Technical Paper No. 1 §8.1 rule (lag = latest rate x (build date - data
    end) / 365.25). The estimate starts at the end of data_to (data_to is the
    last day counted) and runs continuously, so at the END of the build day
    (00:00 UTC the day after) it has run (build date - data_to) whole days and
    equals the paper's figure to the penny; at the build instant itself it
    falls short only by the rest of that day. Never negative: a line
    whose data reach past `at` carries nothing. When the next build moves
    data_to forward, published data replace the estimate for those days."""
    if data_to is None:
        return 0.0
    secs = (at - carry_from(data_to)).total_seconds()
    return runrate_gbp_per_year * max(0.0, secs) / SECONDS_PER_YEAR


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


def runrate_year(data_to: date) -> int:
    """The price year of a line's run-rate: the calendar year of the mid-point
    of the twelve months ending at its data_to. RO/FiT (Apr 2024-Mar 2025) and
    the calendar-2024 lines -> 2024; a trailing 365 days to Oct 2026 -> 2026."""
    return (data_to - timedelta(days=182)).year


def runrate_real_factor(data_to: date | None, deflators: pl.DataFrame) -> float:
    """Factor converting ONE line's run-rate from its own year's prices to
    REAL_BASE_YEAR prices: CPIH(2024) / CPIH(runrate_year), the latest index for
    years past the series (add_real's rule).

    Richard, 15 Oct 2026 (Technical Paper No. 1 §4.3): the real run-rate, the
    per-household, per-second and per-MWh figures are the sum of the lines each
    converted from its own year. The rule it replaced converted the whole cash
    run-rate with the latest index in one step, which counted inflation twice
    on the lines already in 2024 money (£18.36bn / £633 a household at the
    14 Oct 2026 build, against £18.83bn / £649 by this rule). A line with no
    data end takes the latest index.

    Not used for the carry-forward estimate: that money falls after the data
    end, so it is converted at the latest index (paper §8.1;
    sitedata._carry_forward)."""
    base = _base_index(deflators)
    if data_to is None:
        return base / _latest_index(deflators)
    hit = deflators.filter(pl.col("year") == runrate_year(data_to))
    idx = float(hit["index"][0]) if hit.height else _latest_index(deflators)
    return base / idx


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
    if members and all(s.runrate_gbp_per_year_2024 is not None for s in members):
        # line by line, each from its own year (runrate_real_factor)
        real_run = sum(s.runrate_gbp_per_year_2024 or 0.0 for s in members)
        out["runrate_gbp_per_year_2024"] = real_run
        out["rate_gbp_per_sec_2024"] = rate_per_second(real_run)
    return out


def perspective_totals(schemes: list[SchemeResult]) -> dict:
    direct = [s for s in schemes if s.layer == "direct"]
    return {p: _aggregate([s for s in direct if p in s.perspectives])
            for p in PERSPECTIVES}


def layer_total(schemes: list[SchemeResult], layer: str) -> dict:
    return _aggregate([s for s in schemes if s.layer == layer])
