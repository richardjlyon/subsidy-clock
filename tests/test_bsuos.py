from datetime import date

import httpx
import pytest

from subsidy_engine_uk.schemes import bsuos
from subsidy_engine.store import SnapshotStore

# Pre-reform shape: BSUoS was an ex-post pass-through, so the published
# half-hourly charge IS the cost, and it foots to the dataset's own daily total.
PRE_RECORDS = [
    {"_id": 1, "Settlement Day": "2016-04-01T00:00:00", "Settlement Period": 1,
     "BSUoS Price (£/MWh Hour)": 1.73522, "Half-hourly Charge": 45644.41,
     "Total Daily BSUoS Charge": 102133.71, "Run Type": "RF"},
    {"_id": 2, "Settlement Day": "2016-04-01T00:00:00", "Settlement Period": 2,
     "BSUoS Price (£/MWh Hour)": 1.8027, "Half-hourly Charge": 56489.30,
     "Total Daily BSUoS Charge": 102133.71, "Run Type": "RF"},
    {"_id": 3, "Settlement Day": "2016-04-02T00:00:00", "Settlement Period": 1,
     "BSUoS Price (£/MWh Hour)": 2.16164, "Half-hourly Charge": 56839.49,
     "Total Daily BSUoS Charge": 56839.49, "Run Type": "RF"},
]

# Post-reform shape: the fixed-tariff reform broke charge == cost, so recovery
# and cost are published separately and we must take COST.
POST_RECORDS = [
    {"_id": 1, "Settlement Day": "2023-04-01", "Settlement Period": 1,
     "BSUoS Tariff (£/MWh)": 13.41, "BSUoS Fund Tariff (£/MWh)": None,
     "Volume (MWh)": 12885.56, "BSUoS Recovery (£)": 172795.36,
     "BSUoS Fund Recovery (£)": 0, "BSUoS Total Recovery ()": 172795.36,
     "Run Type": "RF", "Actual BSUoS Cost (£)": 233653.56},
    {"_id": 2, "Settlement Day": "2023-04-01", "Settlement Period": 2,
     "BSUoS Tariff (£/MWh)": 13.41, "BSUoS Fund Tariff (£/MWh)": None,
     "Volume (MWh)": 12000.0, "BSUoS Recovery (£)": 160000.0,
     "BSUoS Fund Recovery (£)": 0, "BSUoS Total Recovery ()": 160000.0,
     "Run Type": "RF", "Actual BSUoS Cost (£)": 100000.0},
]


def test_parse_pre_reform_uses_half_hourly_charge_and_foots_to_daily_total():
    df = bsuos.parse_periods(PRE_RECORDS)
    assert df.columns == ["date", "cost_gbp"]
    rows = {r["date"]: r["cost_gbp"] for r in df.to_dicts()}
    # The two periods sum to the row's own Total Daily BSUoS Charge — the
    # identity that licenses treating charge as cost pre-reform.
    assert abs(rows[date(2016, 4, 1)] - 102133.71) < 1e-6
    assert abs(rows[date(2016, 4, 2)] - 56839.49) < 1e-6


def test_parse_post_reform_takes_actual_cost_not_recovery():
    df = bsuos.parse_periods(POST_RECORDS)
    rows = {r["date"]: r["cost_gbp"] for r in df.to_dicts()}
    # Cost, not the £332,795.36 of recovery: post-reform the BSUoS fund makes
    # what users were billed diverge from what balancing actually cost.
    assert abs(rows[date(2023, 4, 1)] - (233653.56 + 100000.0)) < 1e-6


def test_parse_rejects_a_resource_with_no_known_cost_column():
    # Guards the real failure mode: NESO renames a column and the engine
    # silently sums nothing instead of failing loudly.
    with pytest.raises(ValueError, match="neither"):
        bsuos.parse_periods([{"Settlement Day": "2016-04-01",
                              "Some New Column": 1.0}])


def test_parse_rejects_a_resource_with_no_day_column():
    with pytest.raises(ValueError, match="no settlement-day column"):
        bsuos.parse_periods([{"Actual BSUoS Cost (£)": 1.0}])


def test_parse_tolerates_nesos_inconsistent_column_spellings():
    """Real spellings observed across resources of this one dataset: the day is
    'Settlement Date' in the Current RF/SF files and the cost is
    'Actual BSUoS Cost(£)' (no space) in the II 2023-2024 file. Exact-string
    matching broke the live fetch on both."""
    variants = [
        {"Settlement Date": "2026-04-01", "Actual BSUoS Cost (£)": 111.0},
        {"Settlement Day": "2026-04-01", "Actual BSUoS Cost(£)": 222.0},
    ]
    for rec in variants:
        df = bsuos.parse_periods([rec])
        assert df.height == 1, rec
        assert df["date"][0] == date(2026, 4, 1)
        assert df["cost_gbp"][0] == list(rec.values())[1]


def test_parse_prefers_cost_over_charge_when_a_resource_carries_both():
    df = bsuos.parse_periods([{"Settlement Day": "2023-04-01",
                               "Half-hourly Charge": 999.0,
                               "Actual BSUoS Cost (£)": 500.0}])
    assert df["cost_gbp"][0] == 500.0


def test_parse_empty():
    assert bsuos.parse_periods([]).height == 0


def test_fiscal_year_boundary_is_april():
    assert bsuos._fiscal_year(date(2023, 3, 31)) == "2022-2023"
    assert bsuos._fiscal_year(date(2023, 4, 1)) == "2023-2024"
    assert bsuos._fiscal_year(date(2023, 12, 31)) == "2023-2024"


RESOURCES = [
    {"id": "rf_hist", "name": "Historic RF BSUoS Data", "format": "CSV"},
    {"id": "sf_hist", "name": "Historic SF BSUoS Data", "format": "CSV"},
    {"id": "ii_hist", "name": "Historic II BSUoS Data", "format": "CSV"},
    {"id": "sf_2324", "name": "Historic SF BSUoS Data 2023-2024", "format": "CSV"},
    {"id": "cur_ii", "name": "Current II BSUoS Data", "format": "CSV"},
    # Charge-model impact assessments, not the settled series: must be skipped.
    {"id": "cmp381", "name": "CMP381 II BSUoS Data", "format": "XLSX"},
    {"id": "junk", "name": "Missing Settlement Periods since January 2017",
     "format": "XLSX"},
]


def test_resources_skips_non_csv_and_orders_most_settled_first():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True,
                                         "result": {"resources": RESOURCES}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    got = bsuos.resources(client)
    assert [r["id"] for r in got] == ["rf_hist", "sf_hist", "sf_2324",
                                      "ii_hist", "cur_ii"]
    assert all(r["run_type"] in ("RF", "SF", "II") for r in got)


def test_resources_raises_when_the_dataset_has_no_run_type_resources():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"success": True, "result": {
            "resources": [{"id": "x", "name": "Something Else", "format": "CSV"}]}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(RuntimeError, match="no BSUoS run-type resources"):
        bsuos.resources(client)


def test_update_prefers_the_most_settled_run_type_for_a_shared_day(tmp_path):
    """The same day in RF and II must land on the RF figure."""
    day = "2023-04-01"

    def rec(run_type, cost):
        return [{"_id": 1, "Settlement Day": day, "Settlement Period": 1,
                 "BSUoS Total Recovery ()": 999.0, "Run Type": run_type,
                 "Actual BSUoS Cost (£)": cost}]

    payload = {
        "rf_hist": rec("RF", 500.0),   # settled
        "ii_hist": rec("II", 900.0),   # interim — must lose
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return httpx.Response(200, json={"success": True, "result": {
                "resources": [r for r in RESOURCES if r["id"] in payload]}})
        rid = dict(request.url.params)["resource_id"]
        recs = payload[rid]
        return httpx.Response(200, json={"success": True,
                                         "result": {"total": len(recs),
                                                    "records": recs}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SnapshotStore(tmp_path)
    bsuos.update(store, client=client)
    df = store.read_all_partitions("bsuos", "daily")
    assert df.height == 1
    assert df["cost_gbp"][0] == 500.0


def test_update_partitions_by_fiscal_year_across_the_reform_seam(tmp_path):
    """Pre- and post-reform days land in the right fiscal-year partitions and
    each is parsed with its own cost column."""
    payload = {"rf_hist": PRE_RECORDS, "sf_2324": POST_RECORDS}

    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return httpx.Response(200, json={"success": True, "result": {
                "resources": [r for r in RESOURCES if r["id"] in payload]}})
        rid = dict(request.url.params)["resource_id"]
        recs = payload[rid]
        return httpx.Response(200, json={"success": True,
                                         "result": {"total": len(recs),
                                                    "records": recs}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SnapshotStore(tmp_path)
    bsuos.update(store, client=client)

    pre = store.latest("bsuos", "daily", "2016-2017")
    post = store.latest("bsuos", "daily", "2023-2024")
    assert pre is not None and post is not None
    assert pre.height == 2                                  # 1 and 2 April 2016
    assert abs(float(pre["cost_gbp"].sum()) - (102133.71 + 56839.49)) < 1e-6
    assert post.height == 1
    assert abs(float(post["cost_gbp"][0]) - 333653.56) < 1e-6


def test_update_rereads_every_year_so_resettlement_is_picked_up(tmp_path):
    """Post-reform years re-settle for months; a fetch-once rule would pin a
    year to its interim figures for good."""
    calls = []
    payload = {"rf_hist": PRE_RECORDS, "sf_2324": POST_RECORDS}

    def handler(request: httpx.Request) -> httpx.Response:
        if "package_show" in str(request.url):
            return httpx.Response(200, json={"success": True, "result": {
                "resources": [r for r in RESOURCES if r["id"] in payload]}})
        rid = dict(request.url.params)["resource_id"]
        calls.append(rid)
        recs = payload[rid]
        return httpx.Response(200, json={"success": True,
                                         "result": {"total": len(recs),
                                                    "records": recs}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SnapshotStore(tmp_path)
    bsuos.update(store, client=client)
    assert set(calls) == {"rf_hist", "sf_2324"}
    calls.clear()
    bsuos.update(store, client=client)
    assert set(calls) == {"rf_hist", "sf_2324"}   # re-read, not skipped


# --- Constraint turn-up split out of the BSUoS uplift (spec: constraint-turnup)

import polars as pl  # noqa: E402

from subsidy_engine_uk import build as uk_build  # noqa: E402
from subsidy_engine_uk.schemes import constraint_turnup  # noqa: E402

BASE_IDX = 71.5      # mean of the 2002-05 deflator index below
LATEST_IDX = 136.0   # 2026 has no index of its own: latest is used


def _deflators():
    return pl.DataFrame({"year": [2002, 2003, 2004, 2005, 2023, 2024, 2025],
                         "index": [70.0, 71.0, 72.0, 73.0, 128.0, 132.0, LATEST_IDX]},
                        schema={"year": pl.Int64, "index": pl.Float64})


def _annual_ref(scheme_id, annual_map, perspectives=()):
    from subsidy_engine.reference import ReferenceScheme
    annual = pl.DataFrame({"year": list(annual_map), "cost_gbp": list(annual_map.values())},
                          schema={"year": pl.Int64, "cost_gbp": pl.Float64})
    return ReferenceScheme(scheme_id, scheme_id, list(perspectives), "annual", "s",
                           "https://s", True, annual, attribution_rule="r",
                           attribution_confidence="low")


def _model(tmp_path, turnup_gbp_per_day=None):
    """Raw BSUoS 2026 = 1,000; wind constraint payments 2026 = 100;
    indexed baseline = 100 x 136/71.5. Turn-up, if given, on both BSUoS days."""
    store = SnapshotStore(tmp_path)
    store.write("constraints", "daily", pl.DataFrame({
        "date": [date(2026, 4, 10)], "bmu": ["T_W-1"], "lead_party": ["W"],
        "volume_mwh": [-10.0], "cost_gbp": [100.0]}),
        source_url="u", partition="2026-04-10")
    store.write("bsuos", "daily", pl.DataFrame(
        {"date": [date(2026, 4, 10), date(2026, 4, 11)], "cost_gbp": [600.0, 400.0]},
        schema={"date": pl.Date, "cost_gbp": pl.Float64}),
        source_url="u", partition="2026-2027")
    if turnup_gbp_per_day is not None:
        for d in (date(2026, 4, 10), date(2026, 4, 11)):
            rows = [{"date": d, "basis": constraint_turnup.ESTIMATE, "fuel": "ALL",
                     "volume_mwh": 1.0, "cost_gbp": turnup_gbp_per_day},
                    # cross-check bases must never reach the published line
                    {"date": d, "basis": constraint_turnup.ACCEPTED, "fuel": "CCGT",
                     "volume_mwh": 1.0, "cost_gbp": 10_000.0},
                    {"date": d, "basis": constraint_turnup.ACCEPTED_WIND, "fuel": "CCGT",
                     "volume_mwh": 1.0, "cost_gbp": 5_000.0}]
            store.write(constraint_turnup.SCHEME, constraint_turnup.TABLE,
                        pl.DataFrame(rows, schema=constraint_turnup.SCHEMA),
                        source_url="u", partition=d.isoformat())
    refs = {"constraints_history": _annual_ref("constraints_history", {2024: 200.0},
                                               ("renewables", "low_carbon")),
            "ro": _annual_ref("ro", {2024: 1000.0}, ("renewables", "low_carbon")),
            "fit": _annual_ref("fit", {2024: 500.0}, ("renewables", "low_carbon")),
            "bsuos_history": _annual_ref("bsuos_history", {2023: 500.0})}
    model = uk_build.build(store, refs, deflators=_deflators(),
                           baselines={"bsuos": {"value": 100.0}})
    return model, {s.scheme_id: s for s in model["schemes"]}


def _year(scheme, year):
    return {r["year"]: r["cost_gbp"] for r in scheme.annual.to_dicts()}.get(year, 0.0)


def test_bsuos_residual_plus_parts_sums_to_raw_bsuos(tmp_path):
    _, by_id = _model(tmp_path, turnup_gbp_per_day=150.0)
    raw = 1000.0
    baseline = 100.0 * LATEST_IDX / BASE_IDX
    wind = _year(by_id["constraints"], 2026)
    turnup = _year(by_id["constraint_turnup"], 2026)
    residual = _year(by_id["bsuos"], 2026)
    assert (wind, turnup) == (100.0, 300.0)
    assert abs(residual - (raw - baseline - wind - turnup)) < 1e-9
    assert abs(residual + turnup + wind + baseline - raw) < 1e-9
    # the published line is method (b) only: cross-check bases never leak in
    assert by_id["constraint_turnup"].layer == "indirect"
    assert by_id["constraint_turnup"].cumulative_gbp == 300.0


def test_turnup_is_capped_at_the_uplift_so_bsuos_never_goes_negative(tmp_path):
    _, by_id = _model(tmp_path, turnup_gbp_per_day=10_000.0)
    uplift = 1000.0 - 100.0 * LATEST_IDX / BASE_IDX - 100.0
    assert abs(_year(by_id["constraint_turnup"], 2026) - uplift) < 1e-9
    assert _year(by_id["bsuos"], 2026) == 0.0


def test_turnup_split_leaves_every_headline_total_unchanged(tmp_path):
    base, base_ids = _model(tmp_path / "without")
    split, split_ids = _model(tmp_path / "with", turnup_gbp_per_day=150.0)
    assert "constraint_turnup" not in base_ids
    for key in ("cumulative_gbp", "runrate_gbp_per_year"):
        assert abs(split["indirect"][key] - base["indirect"][key]) < 1e-6, key
        for p in base["perspectives"]:
            assert split["perspectives"][p][key] == base["perspectives"][p][key]
    # the BSUoS line fell by exactly the turn-up line
    assert abs(base_ids["bsuos"].cumulative_gbp
               - (split_ids["bsuos"].cumulative_gbp
                  + split_ids["constraint_turnup"].cumulative_gbp)) < 1e-9


def test_parse_tolerates_a_unit_suffix_on_the_cost_column():
    """NESO republished the cost column as 'Actual BSUoS Cost_GBP' (Oct 2026),
    alongside 'BSUoS Total Recovery_GBP'. The unit moved from '(£)' to a
    '_GBP' suffix; the parse must still find the cost, not the recovery."""
    df = bsuos.parse_periods([{"Settlement Date": "2026-09-13",
                               "BSUoS Total Recovery_GBP": 999.0,
                               "Actual BSUoS Cost_GBP": 333.0}])
    assert df["date"][0] == date(2026, 9, 13)
    assert df["cost_gbp"][0] == 333.0


def test_resettlement_after_the_basis_change_is_logged_as_the_publishers(tmp_path):
    """The basis-change cause belongs only to the first re-read of a year
    stored under the old basis. Once a year is on the new basis, a later
    change is NESO re-settling it, and must be credited to NESO."""
    import json
    store = SnapshotStore(tmp_path)
    old = pl.DataFrame({"date": [date(2023, 5, 1)], "cost_gbp": [1.0]}, schema=bsuos.SCHEMA)
    store.write("bsuos", "daily", old, source_url="x", partition="2023-2024", date_col="date")
    # pretend that version predates the basis change
    vdir = next((tmp_path / "raw/bsuos/daily/2023-2024").iterdir())
    vdir.rename(vdir.with_name("20260610T000000.000000"))
    for cost in (2.0, 3.0):
        df = pl.DataFrame({"date": [date(2023, 5, 1)], "cost_gbp": [cost]}, schema=bsuos.SCHEMA)
        bsuos.write_year(store, "2023-2024", df)
    log = [json.loads(l) for l in
           (tmp_path / "raw/bsuos/daily/restatements.jsonl").read_text().splitlines()]
    assert [e["origin"] for e in log] == ["ours", "publisher"]
