"""The money model (spec M-1..M-7): converts stored scheme records into the
cumulative totals, run-rates and per-second rates the dashboard presents."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

import polars as pl

from subsidy_engine.reference import ReferenceScheme
from subsidy_engine.schemes import cfd
from subsidy_engine.store import SnapshotStore

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
BASELINE_YEARS = (2002, 2005)  # inclusive window for uplift baselines


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


def baseline_uplift(
    raw_annual: pl.DataFrame,
    baseline_gbp: float,
    deflators: pl.DataFrame,
    *,
    subtract: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Conservative attribution: cost above the CPIH-indexed 2002-05 baseline,
    optionally net of costs already counted elsewhere, floored at zero."""
    lo, hi = BASELINE_YEARS
    base_idx = float(deflators.filter(
        pl.col("year").is_between(lo, hi))["index"].mean())
    latest = _latest_index(deflators)
    df = raw_annual.join(deflators, on="year", how="left").with_columns(
        (baseline_gbp * pl.col("index").fill_null(latest) / base_idx).alias("baseline"))
    if subtract is not None:
        df = (df.join(subtract.rename({"cost_gbp": "sub"}).select("year", "sub"),
                      on="year", how="left")
              .with_columns(pl.col("sub").fill_null(0.0)))
    else:
        df = df.with_columns(pl.lit(0.0).alias("sub"))
    return (df.with_columns(
                pl.max_horizontal(pl.lit(0.0),
                                  pl.col("cost_gbp") - pl.col("baseline") - pl.col("sub"))
                .alias("cost_gbp"))
            .select("year", "cost_gbp"))


def annual_to_result(scheme_id: str, ref: ReferenceScheme, *,
                     layer: str = "direct") -> SchemeResult:
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
        data_to=(date(latest_year, 12, 31) if ref.year_basis == "calendar"
                 else date(latest_year + 1, 3, 31)),  # calendar series end 31 Dec; obligation years 31 Mar
        layer=layer,
        attribution_note=ref.attribution_rule,
        attribution_confidence=ref.attribution_confidence,
        extras={"source": ref.source, "source_url": ref.source_url,
                "verified": ref.verified},
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


def build(store: SnapshotStore, refs: dict[str, ReferenceScheme],
          *, deflators: pl.DataFrame, baselines: dict | None = None) -> dict:
    """Assemble every scheme result plus perspective totals and the indirect layer total."""
    schemes: list[SchemeResult] = []

    # --- CfD: bottom-up, split renewable / non-renewable by technology (M-7).
    # is_renewable is classified here from the stored technology label, so the
    # split reflects the current policy across the whole history rather than
    # whatever was frozen into each snapshot at fetch time (cfd.classify also
    # fails the build on any unclassified technology label).
    gen = store.latest("cfd", "generation")
    if gen is not None and gen.height:
        gen = cfd.classify(gen)
        for part, flag, perspectives, label in [
            ("cfd_renewable", True, PERSPECTIVES, "CfD - renewables"),
            ("cfd_low_carbon", False, ["low_carbon"],
             "CfD - nuclear"),
        ]:
            sub = gen.filter(pl.col("is_renewable") == flag)
            # Only emit a line that has payments. Nuclear holds CfDs but has not
            # generated, so it has no rows yet and simply does not appear until
            # Hinkley Point C starts paying out — no £0 placeholder to carry.
            if not sub.height:
                continue
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
    constraints_annual = annual.select("year", "cost_gbp")
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
            perspectives=[], cadence="monthly",
            layer="indirect",
            attribution_note=("Capacity Market levy counted in full: availability "
                              "payments procure backup for intermittent generation"),
            attribution_confidence="medium",
            annual=annualise_daily(monthly),
            cumulative_gbp=cumulative(monthly),
            runrate_gbp_per_year=float(last12["cost_gbp"].sum()),
            data_to=monthly["date"].max(),
            extras={"source": "LCCC data portal, capacity market payments",
                    "source_url": "https://dp.lowcarboncontracts.uk/dataset/capacity-obligation-by-auction"},
        ))

    # --- Annual reference schemes (RO, FIT)
    for scheme_id in ("ro", "fit"):
        schemes.append(annual_to_result(scheme_id, refs[scheme_id]))

    # --- Indirect layer (phase 2): CCL, ETS as stored; TNUoS, BSUoS by uplift
    baselines = baselines or {}
    for scheme_id in ("ccl", "ets"):
        if scheme_id in refs:
            schemes.append(annual_to_result(scheme_id, refs[scheme_id],
                                            layer="indirect"))

    if "tnuos" in refs and "tnuos" in baselines:
        ref = refs["tnuos"]
        attributed = baseline_uplift(ref.annual, float(baselines["tnuos"]["value"]),
                                     deflators)
        raw_total = float(ref.annual["cost_gbp"].sum())
        result = annual_to_result("tnuos", ref, layer="indirect")
        result.annual = attributed
        result.cumulative_gbp = float(attributed["cost_gbp"].sum())
        latest = int(attributed["year"].max())
        result.runrate_gbp_per_year = float(
            attributed.filter(pl.col("year") == latest)["cost_gbp"][0])
        result.attribution_pct = (result.cumulative_gbp / raw_total) if raw_total else 0.0
        result.extras["raw_annual"] = ref.annual.to_dicts()
        schemes.append(result)

    if "bsuos_history" in refs and "bsuos" in baselines:
        hist = refs["bsuos_history"]
        bs_daily = store.read_all_partitions("bsuos", "daily")
        if bs_daily is not None and bs_daily.height:
            daily = bs_daily.group_by("date").agg(pl.col("cost_gbp").sum()).sort("date")
            bottom_up = annualise_daily(daily)
            first_full = int(daily["date"].min().year) + (
                0 if daily["date"].min().month == 1 and daily["date"].min().day == 1
                else 1)
            last_hist = int(hist.annual["year"].max())
            usable = bottom_up.filter((pl.col("year") >= first_full)
                                      | (pl.col("year") > last_hist))
            raw_annual = merge_annual(hist.annual, usable)
            raw_runrate = trailing_runrate(daily)
            data_to = daily["date"].max()
        else:
            raw_annual = hist.annual
            raw_runrate = float(raw_annual["cost_gbp"][-1])
            data_to = date(int(raw_annual["year"].max()), 12, 31)
        attributed = baseline_uplift(raw_annual, float(baselines["bsuos"]["value"]),
                                     deflators, subtract=constraints_annual)
        latest_baseline = (float(baselines["bsuos"]["value"])
                           * _latest_index(deflators)
                           / float(deflators.filter(
                               pl.col("year").is_between(*BASELINE_YEARS))["index"].mean()))
        constraints_runrate = next(
            s.runrate_gbp_per_year for s in schemes if s.scheme_id == "constraints")
        runrate = max(0.0, raw_runrate - latest_baseline - constraints_runrate)
        raw_total = float(raw_annual["cost_gbp"].sum())
        cum = float(attributed["cost_gbp"].sum())
        schemes.append(SchemeResult(
            scheme_id="bsuos", label="Balancing costs (BSUoS uplift)",
            perspectives=[], cadence="daily", layer="indirect",
            annual=attributed,
            cumulative_gbp=cum,
            runrate_gbp_per_year=runrate,
            data_to=data_to,
            attribution_pct=(cum / raw_total) if raw_total else 0.0,
            attribution_note=hist.attribution_rule,
            attribution_confidence=hist.attribution_confidence or "low",
            extras={"raw_annual": raw_annual.to_dicts(),
                    "source": hist.source, "source_url": hist.source_url,
                    "verified": hist.verified},
        ))

    # --- Real-terms columns on every scheme, then totals
    for s in schemes:
        s.annual = add_real(s.annual, deflators)

    out_perspectives = perspective_totals(schemes)
    out_indirect = layer_total(schemes, "indirect")
    factor = latest_real_factor(deflators)
    for block in [*out_perspectives.values(), out_indirect]:
        block["runrate_gbp_per_year_2024"] = block["runrate_gbp_per_year"] * factor
        block["rate_gbp_per_sec_2024"] = block["rate_gbp_per_sec"] * factor
    return {"schemes": schemes, "perspectives": out_perspectives,
            "indirect": out_indirect}
