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
