"""Every reference input a build reads, loaded once, and the model built from them
(aios-harness#53; assemble_model moved from cli.py). The CLI, tools and tests take their
inputs and model from here."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import polars as pl
import yaml

from subsidy_engine import money, reference
from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk import build as uk_build
from subsidy_engine_uk import register as reg_mod
from subsidy_engine_uk import scotland, stations


@dataclass
class Inputs:
    refs: dict              # annual reference histories (overlaid by the register in assemble_model)
    deflators: pl.DataFrame
    deflator_info: dict     # provenance of the deflator series
    road: dict              # the engine's no-net-zero road, GO5 and GO4 (aios-harness#43)
    station_map: dict
    ro_stations: list
    bmu_map: dict
    ctx: dict
    equivalences: list
    bill: pl.DataFrame      # electricity bill, cash and 2024 prices
    bill_info: dict
    coords: dict
    notes: dict
    tiles: dict
    bmu_zones: dict
    pinned: dict            # the pinned shared cost register (decision 0168)


def load(root: Path) -> Inputs:
    ref = root / "reference"
    refs = reference.load_annual_costs(ref / "annual_scheme_costs.yaml")
    refs.update(reference.load_annual_costs(ref / "indirect_annual.yaml"))
    deflators = reference.load_deflators(ref / "deflators.yaml")
    deflator_yaml = yaml.safe_load((ref / "deflators.yaml").read_text())
    bill_raw = reference.load_electricity_bill(ref / "electricity_bill.yaml")
    bill_yaml = yaml.safe_load((ref / "electricity_bill.yaml").read_text())
    return Inputs(
        refs=refs,
        deflators=deflators,
        deflator_info={"source": deflator_yaml["source"],
                       "source_url": deflator_yaml["source_url"],
                       "base_year": deflator_yaml["base_year"],
                       "verified": deflator_yaml.get("verified", False)},
        road=reg_mod.road_from_engine(root),
        station_map=stations.load_station_map(ref / "cfd_stations.csv"),
        ro_stations=stations.load_ro_stations(ref / "ro_stations.csv"),
        bmu_map=stations.load_station_bmus(ref / "station_bmu_map.csv"),
        ctx=reference.load_context(ref / "context.yaml"),
        equivalences=yaml.safe_load((ref / "equivalences.yaml").read_text()),
        bill=(money.add_real(bill_raw.rename({"total_bill_gbp": "cost_gbp"}), deflators)
              .rename({"cost_gbp": "total_bill_gbp", "cost_gbp_2024": "total_bill_gbp_2024"})),
        bill_info={"source": bill_yaml["source"], "source_url": bill_yaml["source_url"],
                   "verified": bill_yaml.get("verified", False)},
        coords=stations.load_station_coords(ref / "station_coords.csv"),
        notes=stations.load_enforcement_notes(ref / "enforcement_notes.csv"),
        tiles=json.loads((ref / "map_tiles.json").read_text()),
        bmu_zones=scotland.load_bmu_zones(ref / "bmu_zone.csv"),
        pinned=reg_mod.load_pinned(root),
    )


def assemble_model(root: Path, inp: Inputs | None = None) -> tuple[dict, dict]:
    """The model the site is built from, and the register overlay report (decision 0168). Reads every covered
    series for a closed year from the pinned shared cost register (subsidy_engine_uk.register), less the
    register adjustments reference/clock_findings.yaml drops (subsidy_engine_uk.findings).
    ``inp`` is loaded from ``root`` when not given."""
    from subsidy_engine_uk import findings as findings_mod

    inp = inp or load(root)
    pinned = inp.pinned
    pinned["selection"] = findings_mod.load(root / "reference" / "clock_findings.yaml", pinned["register"],
                                            product=pinned["product"])
    moved = reg_mod.overlay_refs(inp.refs, pinned)
    cm_share = reg_mod.cm_share_from_engine(root, pinned)
    model = uk_build.build(SnapshotStore(root / "data"), inp.refs, deflators=inp.deflators,
                           road=inp.road, station_map=inp.station_map,
                           ro_stations=inp.ro_stations, bmu_map=inp.bmu_map,
                           cm_share=cm_share, to_register=reg_mod.ToRegister(pinned))
    model["findings"] = pinned["selection"].record()
    return model, {"refs_moved": moved, "refs": inp.refs}
