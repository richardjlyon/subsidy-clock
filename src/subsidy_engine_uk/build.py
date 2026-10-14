"""The UK build: assembles the UK scheme results the dashboard presents.

Moved verbatim from subsidy_engine.money in the Phase 1 shared-core extraction.
The generic money primitives stay in subsidy_engine.money; the UK-policy-specific
pieces (the uplift above the engine's no-net-zero cost, the scheme wiring) live here.
"""

from __future__ import annotations

from datetime import date

import polars as pl

# Explicit import list, never `import *`: `*` excludes underscore-prefixed names,
# which would silently drop _latest_index and NameError inside build().
from subsidy_engine.money import (
    PERSPECTIVES,
    SchemeResult,
    add_real,
    annual_to_result,
    annualise_daily,
    cumulative,
    gross_net,
    latest_real_factor,
    layer_total,
    merge_annual,
    perspective_totals,
    trailing_runrate,
    # Deliberate private cross-package import, deferred: renaming _latest_index to a
    # public name is behaviour-neutral but a drive-by on money.py. Revisit in Phase 2
    # when a second adapter needs it.
    _latest_index,
)
from subsidy_engine.reference import ReferenceScheme
from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk.stations import group_by_station
from subsidy_engine_uk.schemes import cfd, constraint_turnup

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


def _with_counterfactual(note: str | None, cf: dict) -> str | None:
    """Fill {counterfactual} and {carry_forward} in a published attribution rule
    from the pinned engine series, so the text can never state a figure or rule
    the build did not use."""
    if note is None:
        return note
    last = cf["carry_forward_from"]
    note = note.replace(
        "{counterfactual}",
        f"release {cf['engine_version']}; GBP {cf['years'][last] / 1e9:.2f}bn in {last}")
    return note.replace(
        "{carry_forward}",
        f"Years after {last}, the model's last year, carry the {last} figure forward "
        f"with CPIH.")


def counterfactual_series(years: list[int], cf: dict, deflators: pl.DataFrame,
                          tag: str = "years") -> pl.DataFrame:
    """The engine's no-net-zero cost (GBP nominal) for each Clock year.

    Years the engine covers take its own figure; a later year carries the
    engine's last-year figure by CPIH (index(y)/index(last), the latest index
    for a year with none), the rule stated in the pinned export; a year before
    the engine's first year is an error."""
    series, last = cf[tag], cf["carry_forward_from"]
    idx = dict(zip(deflators["year"].to_list(), deflators["index"].to_list()))
    latest = _latest_index(deflators)
    first = min(series)
    out = []
    for y in years:
        if y in series:
            out.append(series[y])
        elif y > last:
            out.append(series[last] * idx.get(y, latest) / idx[last])
        else:
            raise ValueError(f"no engine no-net-zero cost for {y} (engine starts {first})")
    return pl.DataFrame({"year": years, "cf": out}, schema={"year": pl.Int64, "cf": pl.Float64})


def counterfactual_runrate(cf: dict, deflators: pl.DataFrame) -> float:
    """The no-net-zero cost at today's prices: the engine's last-year figure
    carried by CPIH to the latest index (the run-rate's money)."""
    last = cf["carry_forward_from"]
    idx = dict(zip(deflators["year"].to_list(), deflators["index"].to_list()))
    return cf["years"][last] * _latest_index(deflators) / idx[last]


FY_WEIGHT_PRIOR = 0.25   # Jan-Mar of calendar year y fall in the financial year starting y-1


def fy_start_to_calendar(fy_annual: pl.DataFrame) -> pl.DataFrame:
    """Financial-year series (keyed by the year the Apr-Mar year starts) to calendar years:
    CY(y) = 0.25 x FY(y-1) + 0.75 x FY(y), the gas-counterfactual engine's own rule (spec
    section 2), so the actual and the no-net-zero cost subtracted from it are on one year
    basis (Richard, 14 Oct 2026, fix F2). The first stored year has no FY(y-1) and takes
    FY(y) alone (TNUoS and BSUoS history both hold one flat REF figure for 2002-04, so
    the earlier year would carry the same value)."""
    fy = dict(zip(fy_annual["year"].to_list(), fy_annual["cost_gbp"].to_list()))
    years = sorted(fy)
    out = [fy[y] if (y - 1) not in fy
           else FY_WEIGHT_PRIOR * fy[y - 1] + (1 - FY_WEIGHT_PRIOR) * fy[y] for y in years]
    return pl.DataFrame({"year": years, "cost_gbp": out},
                        schema={"year": pl.Int64, "cost_gbp": pl.Float64})


def counterfactual_uplift(
    raw_annual: pl.DataFrame,
    cf: dict,
    deflators: pl.DataFrame,
    *,
    subtract: pl.DataFrame | None = None,
) -> pl.DataFrame:
    """Conservative attribution: measured cost above the pinned engine's
    no-net-zero cost for the year, optionally net of costs already counted
    elsewhere, floored at zero."""
    years = [int(y) for y in raw_annual["year"].to_list()]
    df = raw_annual.join(counterfactual_series(years, cf, deflators), on="year", how="left")
    if subtract is not None:
        df = (df.join(subtract.rename({"cost_gbp": "sub"}).select("year", "sub"),
                      on="year", how="left")
              .with_columns(pl.col("sub").fill_null(0.0)))
    else:
        df = df.with_columns(pl.lit(0.0).alias("sub"))
    return (df.with_columns(
                pl.max_horizontal(pl.lit(0.0),
                                  pl.col("cost_gbp") - pl.col("cf") - pl.col("sub"))
                .alias("cost_gbp"))
            .select("year", "cost_gbp"))


def _cf_extras(cf: dict, years: list[int], deflators: pl.DataFrame, what: str) -> dict:
    """The no-net-zero cost the build subtracted, per year, with its range and source."""
    rows = []
    for tag in ("years", "low", "high"):
        ser = counterfactual_series(years, cf, deflators, tag)
        rows.append(dict(zip(ser["year"].to_list(), ser["cf"].to_list())))
    return {"counterfactual_annual": [
                {"year": y, "cost": rows[0][y], "cost_low_netzero": rows[1][y],
                 "cost_high_netzero": rows[2][y],
                 "basis": ("modelled" if y <= cf["carry_forward_from"]
                           else f"carried forward from {cf['carry_forward_from']} by CPIH")}
                for y in years],
            "counterfactual_source": (f"gas-counterfactual engine {cf['engine_version']} "
                                      f"({what}; generators' share included)"),
            "counterfactual_method": cf["method"],
            "counterfactual_carry_forward": cf["rule"]}


def _station_detail(sub: pl.DataFrame, station_rows: list,
                    statuses: dict | None = None) -> list:
    """Per-station panel detail for the mapped CfD recipients.

    For each grouped station: the quarterly net payment/generation series
    (calendar quarters across all the station's contracts — negative quarters
    are real paybacks and pass through unclamped) and per-contract rows with
    first settlement date and latest strike price. Feeds the per-asset JSONs
    (sitedata.build); everything derives from the same daily settlement rows
    the scheme totals use, so the panel reconciles by construction."""
    out = []
    for row in station_rows:
        ids = [c["cfd_id"] for c in row["contracts"]]
        d = sub.filter(pl.col("cfd_id").is_in(ids)).sort("date")
        quarters = (
            d.with_columns(
                (pl.col("date").dt.year().cast(pl.Utf8) + "-Q"
                 + ((pl.col("date").dt.month() - 1) // 3 + 1).cast(pl.Utf8))
                .alias("q"))
            .group_by("q")
            .agg(pl.col("payment_gbp").sum(), pl.col("generation_mwh").sum())
            .sort("q").to_dicts())
        contracts = []
        for c in row["contracts"]:
            cd = d.filter(pl.col("cfd_id") == c["cfd_id"])
            strikes = cd.drop_nulls("strike_price_gbp_mwh")
            contracts.append({
                "cfd_id": c["cfd_id"],
                "unit_name": c["unit_name"],
                "technology": c["technology"],
                # LCCC lifecycle status placed verbatim; None -> the pinned
                # "unknown" wording at site-data build, never a guess
                "status": (statuses or {}).get(c["cfd_id"]),
                "cumulative_gbp": c["cost"],
                "first_settlement": cd["date"].min().isoformat() if cd.height else None,
                "latest_strike_gbp_mwh": (float(strikes["strike_price_gbp_mwh"][-1])
                                          if strikes.height else None),
            })
        out.append({
            "station": row["station"],
            "technology": row["technology"],
            "cost": row["cost"],
            "generation_mwh": float(d["generation_mwh"].sum() or 0.0),
            "data_to": d["date"].max().isoformat() if d.height else None,
            "quarters": quarters,
            "contracts": contracts,
        })
    return out


# Outage-strip significance filter, disclosed in the panel's pinned wording
# (sitedata.ASSET_STRINGS["outages_label"]): a REMIT message becomes a panel
# window only if it ran >= 24h with >= 20% of the unit's normal capacity
# unavailable. Big thermal units publish hundreds of small redeclarations a
# year; without a disclosed threshold the strip is noise.
OUTAGE_MIN_HOURS = 24
OUTAGE_MIN_SHARE = 0.20


def _attach_outages(station_detail: list, bmu_map: dict,
                    outages: pl.DataFrame) -> None:
    """Attach significant REMIT outage windows to each mapped station's detail.

    Stations absent from ``bmu_map`` are left untouched — the panel renders
    the pinned unavailable wording (unknown, never zero)."""
    from subsidy_engine_uk.schemes.remit import COVERAGE_FROM
    df = (outages
          .with_columns(
              pl.col("event_start").str.to_datetime("%Y-%m-%dT%H:%M:%S%#z",
                                                    strict=False).alias("start_dt"),
              pl.col("event_end").str.to_datetime("%Y-%m-%dT%H:%M:%S%#z",
                                                  strict=False).alias("end_dt"))
          .drop_nulls(["start_dt", "end_dt", "unavailable_mw", "normal_mw"])
          .filter(
              ((pl.col("end_dt") - pl.col("start_dt"))
               >= pl.duration(hours=OUTAGE_MIN_HOURS))
              & (pl.col("normal_mw") > 0)
              & (pl.col("unavailable_mw")
                 >= OUTAGE_MIN_SHARE * pl.col("normal_mw"))))
    for d in station_detail:
        ids = bmu_map.get(d["station"])
        if not ids:
            continue
        w = df.filter(pl.col("bmu").is_in(ids)).sort("start_dt")
        d["outages"] = {
            "coverage_from": COVERAGE_FROM.isoformat(),
            "windows": [
                {"start": r["start_dt"].date().isoformat(),
                 "end": r["end_dt"].date().isoformat(),
                 "type": ("Planned" if (r["unavailability_type"] or "")
                          .lower().startswith("plan") else "Unplanned"),
                 "mw_lost": r["unavailable_mw"]}
                for r in w.to_dicts()
            ],
        }


def build(store: SnapshotStore, refs: dict[str, ReferenceScheme],
          *, deflators: pl.DataFrame, counterfactual: dict | None = None,
          station_map: dict | None = None,
          ro_stations: list | None = None,
          bmu_map: dict | None = None,
          cm_share: dict | None = None,
          model_pin: dict | None = None) -> dict:
    """Assemble every scheme result plus perspective totals and the indirect layer total.

    ``station_map`` (cfd_id -> physical-station short name) collapses phased CfD
    contracts into one station for the recipients view; omitted in unit tests.
    ``ro_stations`` are the named RO recipients (buy-out basis) surfaced in the
    recipients table; omitted in unit tests."""
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
            by_station = group_by_station(
                sub.group_by("cfd_id", "unit_name", "technology")
                   .agg(pl.col("payment_gbp").sum().alias("cost"))
                   .to_dicts(),
                station_map or {})[:25]
            extras = {"gross": gross, "net": net,
                      "mwh": float(sub["generation_mwh"].sum() or 0.0),
                      "by_technology": sub.group_by("technology")
                          .agg(pl.col("payment_gbp").sum().alias("cost"),
                               pl.col("generation_mwh").sum())
                          .sort("cost", descending=True).to_dicts(),
                      "by_recipient": sub.group_by("unit_name", "technology")
                          .agg(pl.col("payment_gbp").sum().alias("cost"))
                          .sort("cost", descending=True).head(25).to_dicts(),
                      "by_station": by_station}
            if flag:
                # renewables carry the mapped stations' panel detail
                port = store.latest("cfd", "portfolio")
                statuses = (dict(zip(port["cfd_id"], port["status"]))
                            if port is not None and port.height else {})
                extras["station_detail"] = _station_detail(sub, by_station,
                                                           statuses)
                if bmu_map:
                    remit_df = store.latest("remit", "outages")
                    if remit_df is not None and remit_df.height:
                        _attach_outages(extras["station_detail"], bmu_map,
                                        remit_df)
            schemes.append(SchemeResult(
                scheme_id=part, label=label, perspectives=perspectives, cadence="daily",
                annual=annualise_daily(daily),
                cumulative_gbp=cumulative(daily),
                runrate_gbp_per_year=trailing_runrate(daily),
                data_to=daily["date"].max() if daily.height else None,
                extras=extras,
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
                        .agg(pl.col("cost_gbp").sum().alias("cost"),
                             pl.col("volume_mwh").sum())
                        .sort("cost", descending=True).head(25).to_dicts())
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

    # --- Capacity Market: bottom-up monthly, net-zero share only (change of
    # 13 Oct 2026). Any power system needs backup, so the levy is NOT counted
    # in full: each month's LCCC payment is scaled by share(year) = (CM paid -
    # what "Reliable Britain", the actual system with net-zero policy removed,
    # would have paid for its own backup) / CM paid, from
    # the pinned gas-counterfactual engine export (reference/model_pin.yaml ->
    # reference/engine/<version>.json; engine spec 5.4). The same rule as TNUoS/BSUoS: count only what net zero added.
    # Years after the engine's last year carry its last share forward.
    # Rejected: pasting in the engine's pounds per year. Scaling the measured
    # months keeps the line on LCCC's live data, so a restated month moves it
    # in proportion; the drift guard below says when the shares are stale.
    cm = store.latest("capacity_market", "payments")
    if cm is not None and cm.height:
        if cm_share is None:
            raise ValueError(
                "capacity_market data present but no cm_share table: the Clock "
                "counts only the net-zero share of the Capacity Market "
                "(reference/model_pin.yaml -> the pinned engine export)")
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
        schemes.append(SchemeResult(
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
                        for k in ("engine", "engine_version", "commit", "commit_date",
                                  "file", "file_sha256")
                        if k in cm_share.get("provenance", {})},
                    "carry_forward_from": carry},
        ))

    # --- Annual reference schemes (RO, FIT). RO carries named per-station
    # recipients (buy-out basis) for the recipients table; the scheme total
    # stays the recycle-inclusive Ofgem figure.
    for scheme_id in ("ro", "fit"):
        extra = ({"by_station": ro_stations[:25], "recipient_basis": "buyout"}
                 if scheme_id == "ro" and ro_stations else None)
        schemes.append(annual_to_result(scheme_id, refs[scheme_id], extra_extras=extra))

    # --- Indirect layer (phase 2): CCL, ETS as stored; TNUoS, BSUoS by uplift above
    # the pinned engine's no-net-zero cost (Richard, 14 Oct 2026: the Clock computes
    # no counterfactual itself; one carry-forward method in both models).
    cfs = counterfactual or {}
    for scheme_id in ("ccl", "ets"):
        if scheme_id in refs:
            schemes.append(annual_to_result(scheme_id, refs[scheme_id],
                                            layer="indirect"))

    if "tnuos" in refs and "tnuos" in cfs:
        ref = refs["tnuos"]
        cf = cfs["tnuos"]
        # stored by financial year (NESO charging years); put on calendar years, the
        # basis of the engine's no-net-zero cost (F2, 14 Oct 2026)
        tn_cy = fy_start_to_calendar(ref.annual)
        attributed = counterfactual_uplift(tn_cy, cf, deflators)
        raw_total = float(tn_cy["cost_gbp"].sum())
        result = annual_to_result("tnuos", ref, layer="indirect")
        result.data_to = date(int(tn_cy["year"].max()), 12, 31)
        result.annual = attributed
        result.cumulative_gbp = float(attributed["cost_gbp"].sum())
        latest = int(attributed["year"].max())
        result.runrate_gbp_per_year = float(
            attributed.filter(pl.col("year") == latest)["cost_gbp"][0])
        result.attribution_pct = (result.cumulative_gbp / raw_total) if raw_total else 0.0
        result.attribution_note = _with_counterfactual(result.attribution_note, cf)
        result.extras["raw_annual"] = tn_cy.rename({"cost_gbp": "cost"}).to_dicts()
        result.extras["raw_annual_fy"] = ref.annual.rename({"cost_gbp": "cost"}).to_dicts()
        result.extras["raw_year_basis"] = ("calendar: 0.25 x FY(y-1) + 0.75 x FY(y) of the stored "
                                           "financial-year charges (first year: FY(y))")
        result.extras.update(_cf_extras(cf, [int(y) for y in tn_cy["year"].to_list()],
                                        deflators, "GO5: no-net-zero grid cost"))
        schemes.append(result)

    if "bsuos_history" in refs and "bsuos" in cfs:
        cf = cfs["bsuos"]
        hist = refs["bsuos_history"]
        # pre-2017 history is by financial year (NAO/REF); calendar years like the
        # fetched daily series and the engine's no-net-zero cost (F2, 14 Oct 2026)
        hist_cy = fy_start_to_calendar(hist.annual)
        bs_daily = store.read_all_partitions("bsuos", "daily")
        if bs_daily is not None and bs_daily.height:
            daily = bs_daily.group_by("date").agg(pl.col("cost_gbp").sum()).sort("date")
            bottom_up = annualise_daily(daily)
            first_full = int(daily["date"].min().year) + (
                0 if daily["date"].min().month == 1 and daily["date"].min().day == 1
                else 1)
            last_hist = int(hist_cy["year"].max())
            usable = bottom_up.filter((pl.col("year") >= first_full)
                                      | (pl.col("year") > last_hist))
            raw_annual = merge_annual(hist_cy, usable)
            raw_runrate = trailing_runrate(daily)
            data_to = daily["date"].max()
        else:
            raw_annual = hist_cy
            raw_runrate = float(raw_annual["cost_gbp"][-1])
            data_to = date(int(raw_annual["year"].max()), 12, 31)
        # Uplift after wind constraint payments, then split constraint turn-up
        # out of it (spec: constraint-turnup). The turn-up line is capped at the
        # uplift, so BSUoS residual + turn-up == uplift exactly and the indirect
        # total cannot move; where no cap binds, residual + turn-up + wind
        # constraints + the engine's no-net-zero balancing cost == raw BSUoS.
        uplift = counterfactual_uplift(raw_annual, cf, deflators,
                                       subtract=constraints_annual)
        latest_cf = counterfactual_runrate(cf, deflators)
        constraints_runrate = next(
            s.runrate_gbp_per_year for s in schemes if s.scheme_id == "constraints")
        uplift_runrate = max(0.0, raw_runrate - latest_cf - constraints_runrate)
        # Same window as the BSUoS data, so a lagging BSUoS feed never has
        # turn-up subtracted for days it does not yet cover.
        tu_daily = constraint_turnup.daily_cost(store).filter(pl.col("date") <= data_to)
        if tu_daily.height:
            tu_measured = annualise_daily(tu_daily).rename({"cost_gbp": "tu"})
            split = (uplift.join(tu_measured, on="year", how="left")
                     .with_columns(pl.col("tu").fill_null(0.0))
                     .with_columns(pl.min_horizontal("tu", "cost_gbp").alias("tu")))
            tu_annual = split.select("year", pl.col("tu").alias("cost_gbp"))
            attributed = split.select("year", (pl.col("cost_gbp") - pl.col("tu"))
                                      .alias("cost_gbp"))
            tu_runrate = min(trailing_runrate(tu_daily), uplift_runrate)
            runrate = uplift_runrate - tu_runrate
            measured = constraint_turnup.read(store).filter(
                pl.col("date") <= data_to)
            by_fuel = (measured.filter(pl.col("basis") == constraint_turnup.ACCEPTED_WIND)
                       .group_by("fuel")
                       .agg(pl.col("cost_gbp").sum().alias("cost"),
                            pl.col("volume_mwh").sum())
                       .sort("cost", descending=True).to_dicts())
            cross_check = {b: float(measured.filter(pl.col("basis") == b)["cost_gbp"].sum())
                           for b in (constraint_turnup.ACCEPTED,
                                     constraint_turnup.ACCEPTED_WIND)}
            tu_cum = float(tu_annual["cost_gbp"].sum())
            schemes.append(SchemeResult(
                scheme_id="constraint_turnup",
                label="Constraint turn-up (paid to switch on)",
                perspectives=[], cadence="daily", layer="indirect",
                annual=tu_annual,
                cumulative_gbp=tu_cum,
                runrate_gbp_per_year=tu_runrate,
                data_to=tu_daily["date"].max(),
                attribution_pct=1.0,
                attribution_note=(
                    "Estimated cost of paying other stations to replace the wind "
                    "energy switched off for network constraints: each half-hour's "
                    "switched-off wind volume priced against that half-hour's "
                    "accepted offers (Octopus Energy Wasted Wind method). Taken out "
                    "of the balancing (BSUoS) uplift, never more than it, so no "
                    "total changes."),
                attribution_confidence="low",
                extras={"by_fuel_while_wind_constrained": by_fuel,
                        "cross_check_cumulative": cross_check,
                        "measured_from": tu_daily["date"].min().isoformat(),
                        "measured_annual": tu_measured.rename(
                            {"tu": "cost"}).to_dicts(),
                        "source": "Elexon Insights settlement stacks (bids and offers)",
                        "source_url": constraint_turnup.SOURCE_URL},
            ))
        else:
            attributed = uplift
            runrate = uplift_runrate
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
            attribution_note=_with_counterfactual(hist.attribution_rule, cf),
            attribution_confidence=hist.attribution_confidence or "low",
            extras={"raw_annual": raw_annual.rename({"cost_gbp": "cost"}).to_dicts(),
                    "source": hist.source, "source_url": hist.source_url,
                    "verified": hist.verified,
                    **_cf_extras(cf, [int(y) for y in raw_annual["year"].to_list()],
                                 deflators, "GO4: no-net-zero balancing cost, BSUoS basis")},
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
    out = {"schemes": schemes, "perspectives": out_perspectives,
           "indirect": out_indirect}
    if model_pin is not None:
        out["model_pin"] = {"engine_version": model_pin["engine_version"],
                            "sha256": model_pin["sha256"]}
    return out
