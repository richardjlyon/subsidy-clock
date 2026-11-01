"""Contracts for Difference (spec 3.1). Bottom-up daily per-contract payments
published by LCCC, the scheme counterparty."""

from __future__ import annotations

import httpx
import polars as pl

from subsidy_engine.ckan import dataset_resources, fetch_all_records
from subsidy_engine.money import (PERSPECTIVES, SchemeResult, annualise_daily, cumulative,
                                  gross_net, trailing_runrate)
from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk.stations import group_by_station

GENERATION_RESOURCE = "37d1bef4-55d7-4b8e-8a47-1d24b123a20e"
# In-period Tracking is read through its dataset, not a fixed resource id:
# LCCC republished it under a new id in Oct 2026 and the old one went 404.
TRACKING_DATASET = "in-period-tracking"
DATASET_URL = (
    "https://dp.lowcarboncontracts.uk/dataset/actual-cfd-generation-and-avoided-ghg-emissions"
)
TRACKING_URL = "https://dp.lowcarboncontracts.uk/dataset/in-period-tracking"
# Contract portfolio status — per-contract lifecycle state (Live pre/post-FIC,
# Pre-MDD, Pre-Start Date, Terminated). Join key verified 2026-07-29: every
# settlement CfD_ID present (openspec add-interactive-asset-map, verification.md).
PORTFOLIO_RESOURCE = "fdaf09d2-8cff-4799-a5b0-1c59444e492b"
PORTFOLIO_URL = "https://dp.lowcarboncontracts.uk/dataset/cfd-contract-portfolio-status"

# Renewable CfD technologies. These are the generators that hold renewable
# CfDs and count toward the UK's renewable targets and REF's renewable
# subsidy totals — so they belong in the renewables headline. The biomass
# family (conversions like Drax, dedicated biomass, advanced conversion and
# energy-from-waste) is officially renewable and is counted here; excluding it
# would understate renewable subsidy and mismatch every external aggregate we
# reconcile against (spec M-7).
RENEWABLE_TECHNOLOGIES = {
    "Offshore Wind",
    "Onshore Wind",
    "Remote Island Wind",
    "Solar PV",
    "Tidal Stream",
    "Wave",
    "Hydro",
    "Geothermal",
    "Biomass Conversion",
    "Dedicated Biomass",
    "Advanced Conversion Technology",
    "Energy from Waste",
}

# The only non-renewable low-carbon CfD technology. Nuclear is listed
# explicitly (rather than caught as a residual) so that an unrecognised
# technology label fails the build loudly — see _check_technologies — instead
# of silently dropping into either bucket.
NUCLEAR_TECHNOLOGIES = {
    "Nuclear",
}

KNOWN_TECHNOLOGIES = RENEWABLE_TECHNOLOGIES | NUCLEAR_TECHNOLOGIES


def _check_technologies(df: pl.DataFrame) -> None:
    """Fail loudly if LCCC publishes a technology we have not classified.

    Every CfD technology must be explicitly assigned to either the renewable
    or the nuclear set. An unknown label is the one way a generator could be
    silently mis-bucketed (the failure mode that previously left biomass out
    of the renewables headline), so we refuse to build until it is classified."""
    seen = set(df.select("technology").unique().to_series().to_list())
    unknown = {t for t in seen if t is not None} - KNOWN_TECHNOLOGIES
    if unknown:
        raise ValueError(
            "Unclassified CfD technology label(s): "
            f"{sorted(unknown)}. Add each to RENEWABLE_TECHNOLOGIES or "
            "NUCLEAR_TECHNOLOGIES in schemes/cfd.py before rebuilding.")


def is_renewable_expr() -> pl.Expr:
    """The single source of truth for the renewable/non-renewable CfD split.

    Used both when parsing freshly fetched data and when building the money
    model from the stored history, so a change to RENEWABLE_TECHNOLOGIES takes
    effect on the whole back-catalogue without refetching — the classification
    is a live policy, not a value frozen into the immutable store."""
    return (pl.col("technology").is_in(RENEWABLE_TECHNOLOGIES)
            .fill_null(False).alias("is_renewable"))


def classify(df: pl.DataFrame) -> pl.DataFrame:
    """Apply the current renewable/nuclear policy to a generation frame,
    failing loudly on any unclassified technology label."""
    _check_technologies(df)
    return df.with_columns(is_renewable_expr())


def _lccc_date(col: str) -> pl.Expr:
    return pl.col(col).str.slice(0, 10).str.to_date().alias("date")


def parse_generation(records: list[dict]) -> pl.DataFrame:
    df = pl.DataFrame(records, infer_schema_length=None)
    parsed = (
        df.select(
            _lccc_date("Settlement_Date"),
            pl.col("CfD_ID").alias("cfd_id"),
            pl.col("Name_of_CfD_Unit").alias("unit_name"),
            pl.col("Technology").alias("technology"),
            pl.col("CFD_Generation_MWh").cast(pl.Float64, strict=False).alias("generation_mwh"),
            pl.col("CFD_Payments_GBP").cast(pl.Float64, strict=False).alias("payment_gbp"),
            pl.col("Strike_Price_GBP_Per_MWh").cast(pl.Float64, strict=False)
              .alias("strike_price_gbp_mwh"),
        )
        .drop_nulls("payment_gbp")
        .sort("date", "cfd_id")
    )
    # The store holds only what LCCC publishes; is_renewable is our
    # classification (a live policy) and is derived at build time, not frozen
    # into the snapshot — see classify(). We still guard at fetch so a new
    # technology label fails fast.
    _check_technologies(parsed)
    return parsed


def parse_tracking(records: list[dict]) -> pl.DataFrame:
    df = pl.DataFrame(records, infer_schema_length=None)
    return (
        df.select(
            _lccc_date("Settlement_Date"),
            pl.col("Actual_CFD_Payments_GBP").cast(pl.Float64, strict=False).alias("payment_gbp"),
        )
        .drop_nulls("payment_gbp")
        .sort("date")
    )


def datastore_resource_id(resources: list[dict]) -> str:
    """The queryable (datastore-backed) resource of a CKAN dataset."""
    for r in resources:
        if r.get("datastore_active"):
            return r["id"]
    raise ValueError(f"dataset has no datastore resource: {[r.get('id') for r in resources]}")


def merge_tracking(stored: pl.DataFrame | None, fresh: pl.DataFrame) -> pl.DataFrame:
    """Stored actuals plus fresh ones; a fresh actual wins on the same day.

    LCCC's republished tracking resource starts at the current month, so a
    plain overwrite would discard every actual already captured."""
    if stored is None or stored.height == 0:
        return fresh.sort("date")
    keep = stored.join(fresh.select("date"), on="date", how="anti")
    return pl.concat([keep, fresh.select(stored.columns)]).sort("date")


def parse_portfolio(records: list[dict]) -> pl.DataFrame:
    """Contract id -> lifecycle status, one row per contract."""
    return (
        pl.DataFrame(records, infer_schema_length=None)
        .select(pl.col("CFD_ID").alias("cfd_id"),
                pl.col("Status").alias("status"))
        .drop_nulls("cfd_id")
        .unique(subset="cfd_id", keep="last")
        .sort("cfd_id")
    )


def update(store: SnapshotStore, *, client: httpx.Client | None = None) -> None:
    gen = parse_generation(fetch_all_records(GENERATION_RESOURCE, client=client))
    store.write("cfd", "generation", gen, source_url=DATASET_URL, date_col="date")
    trk_id = datastore_resource_id(dataset_resources(TRACKING_DATASET, client=client))
    trk = merge_tracking(store.latest("cfd", "tracking"),
                         parse_tracking(fetch_all_records(trk_id, client=client)))
    store.write("cfd", "tracking", trk, source_url=TRACKING_URL, date_col="date")
    port = parse_portfolio(fetch_all_records(PORTFOLIO_RESOURCE, client=client))
    store.write("cfd", "portfolio", port, source_url=PORTFOLIO_URL)


# --- Result (moved from build.py, aios-harness#38)

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


def result(store: SnapshotStore, *, station_map: dict | None = None,
           bmu_map: dict | None = None, to_register=None) -> list[SchemeResult]:
    """The CfD lines: renewables, and nuclear once it pays out. ``station_map``
    (cfd_id -> physical-station short name) collapses phased contracts into one station
    for the recipients view; ``bmu_map`` attaches REMIT outages to station detail.
    ``to_register`` (subsidy_engine_uk.register.ToRegister) makes each closed year of
    the renewables line the shared cost register's (0168); omitted in unit tests."""
    out: list[SchemeResult] = []
    # --- CfD: bottom-up, split renewable / non-renewable by technology (M-7).
    # is_renewable is classified here from the stored technology label, so the
    # split reflects the current policy across the whole history rather than
    # whatever was frozen into each snapshot at fetch time (cfd.classify also
    # fails the build on any unclassified technology label).
    gen = store.latest("cfd", "generation")
    if gen is not None and gen.height:
        gen = classify(gen)
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
            if flag and to_register is not None:
                # 0168: CFD = every technology LCCC has paid (no nuclear yet)
                daily = to_register(daily, ("CFD",))
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
            out.append(SchemeResult(
                scheme_id=part, label=label, perspectives=perspectives, cadence="daily",
                annual=annualise_daily(daily),
                cumulative_gbp=cumulative(daily),
                runrate_gbp_per_year=trailing_runrate(daily),
                data_to=daily["date"].max() if daily.height else None,
                extras=extras,
            ))
    return out
