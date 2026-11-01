"""The UK build: assembles the UK scheme results the dashboard presents.

Each scheme with data of its own builds its result in its scheme module
(subsidy_engine_uk.schemes.*, aios-harness#38); the annual reference schemes are built
here. The generic money primitives stay in subsidy_engine.money.
"""

from __future__ import annotations

import polars as pl

from subsidy_engine.money import (
    SchemeResult,
    add_real,
    annual_to_result,
    latest_real_factor,
    layer_total,
    perspective_totals,
)
from subsidy_engine.reference import ReferenceScheme
from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk.schemes import bsuos, capacity_market, carbon as carbon_mod, cfd, constraints, vat
from subsidy_engine_uk.uplift import road_extras, road_uplift


def build(store: SnapshotStore, refs: dict[str, ReferenceScheme],
          *, deflators: pl.DataFrame, road: dict | None = None,
          station_map: dict | None = None,
          ro_stations: list | None = None,
          bmu_map: dict | None = None,
          cm_share: dict | None = None,
          to_register=None,
          carbon: dict | None = None,
          domestic_share: dict | None = None) -> dict:
    """Assemble every scheme result plus perspective totals and the indirect layer total.

    ``station_map`` (cfd_id -> physical-station short name) collapses phased CfD
    contracts into one station for the recipients view; omitted in unit tests.
    ``ro_stations`` are the named RO recipients (buy-out basis) surfaced in the
    recipients table; omitted in unit tests. ``to_register``
    (subsidy_engine_uk.register.ToRegister) makes every closed year of the daily and
    monthly lines sum to the shared cost register's figure (decision 0168); omitted in
    unit tests."""
    schemes: list[SchemeResult] = []
    schemes += cfd.result(store, station_map=station_map, bmu_map=bmu_map,
                          to_register=to_register)
    con = constraints.result(store, refs["constraints_history"], to_register)
    schemes += con
    schemes += capacity_market.result(store, cm_share, deflators, to_register)

    # --- Annual reference schemes (RO, FIT). RO carries named per-station
    # recipients (buy-out basis) for the recipients table; the scheme total
    # stays the recycle-inclusive Ofgem figure.
    for scheme_id in ("ro", "fit"):
        extra = ({"by_station": ro_stations[:25], "recipient_basis": "buyout"}
                 if scheme_id == "ro" and ro_stations else None)
        schemes.append(annual_to_result(scheme_id, refs[scheme_id], extra_extras=extra))

    # --- Indirect layer (phase 2): CCL as stored; carbon from the engine (#44, in place of
    # the old ETS line and the CPS inside CCL); TNUoS, BSUoS above the road
    # (``road``: subsidy_engine_uk.register.road_from_engine, the engine's GO5 and GO4)
    road = road or {}
    if "ccl" in refs:
        schemes.append(annual_to_result("ccl", refs["ccl"], layer="indirect"))
    if "ets" in refs:
        raise ValueError("an 'ets' reference line is loaded: carbon is counted once, in the carbon line "
                         "(aios-harness#44), never next to the old emissions-trading line")
    schemes += carbon_mod.result(carbon)

    if "tnuos" in refs and "tnuos" in road:
        ref = refs["tnuos"]
        attributed = road_uplift(ref.annual, road["tnuos"], deflators)
        raw_total = float(ref.annual["cost_gbp"].sum())
        result = annual_to_result("tnuos", ref, layer="indirect")
        result.annual = attributed
        result.cumulative_gbp = float(attributed["cost_gbp"].sum())
        latest = int(attributed["year"].max())
        result.runrate_gbp_per_year = float(
            attributed.filter(pl.col("year") == latest)["cost_gbp"][0])
        result.attribution_pct = (result.cumulative_gbp / raw_total) if raw_total else 0.0
        result.extras["raw_annual"] = ref.annual.rename({"cost_gbp": "cost"}).to_dicts()
        result.extras.update(road_extras(ref.annual["year"].to_list(), road["tnuos"], deflators))
        schemes.append(result)

    if "bsuos_history" in refs and "bsuos" in road:
        schemes += bsuos.result(store, refs["bsuos_history"],
                                road["bsuos"], deflators, con[0],
                                to_register, refs["constraints_history"])

    # --- VAT on households' share of the lines above (#45; its own indirect line)
    schemes += vat.result(schemes, domestic_share)

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
            # the first year Elexon replaces REF for constraints (fix 5 guard); published
            # in breakdown.json so the pages state the same year as the figures
            "elexon_first_year": (refs["constraints_history"].bottom_up_from
                                  if con[0].extras["held_from"] else None),
            # 0168: the register read, and any closed year where a feed differs from it
            **({"register": to_register.report()} if to_register is not None else {}),
            "indirect": out_indirect}
