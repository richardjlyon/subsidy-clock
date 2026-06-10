from datetime import date

import httpx
import polars as pl

from subsidy_engine.schemes import bsuos
from subsidy_engine.store import SnapshotStore

RECORDS = [
    {"_id": 1, "SETT_DATE": "2026-04-01", "SETT_PERIOD": 1,
     "Energy Imbalance": -7803.335, "Frequency Control": 0.0,
     "Positive Reserve": 1575.625, "Constraints": 177096.418,
     "Negative Reserve": 0.0, "Other": 5.43},
    {"_id": 2, "SETT_DATE": "2026-04-01", "SETT_PERIOD": 2,
     "Energy Imbalance": 1000.0, "Frequency Control": 100.0,
     "Positive Reserve": 0.0, "Constraints": 50000.0,
     "Negative Reserve": -50.0, "Other": 0.0},
    {"_id": 3, "SETT_DATE": "2026-04-02", "SETT_PERIOD": 1,
     "Energy Imbalance": 0.0, "Frequency Control": 0.0,
     "Positive Reserve": 0.0, "Constraints": 200000.0,
     "Negative Reserve": 0.0, "Other": 0.0},
]


def test_parse_daily_sums_components_per_day():
    df = bsuos.parse_daily(RECORDS)
    assert df.columns == ["date", "cost_gbp"]
    rows = {r["date"]: r["cost_gbp"] for r in df.to_dicts()}
    day1 = (-7803.335 + 1575.625 + 177096.418 + 5.43) + (1000.0 + 100.0 + 50000.0 - 50.0)
    assert abs(rows[date(2026, 4, 1)] - day1) < 1e-6
    assert rows[date(2026, 4, 2)] == 200000.0


def test_parse_daily_empty():
    assert bsuos.parse_daily([]).height == 0


def test_fiscal_year_resources_filters_and_maps():
    payload = {"success": True, "result": {"resources": [
        {"id": "aaa", "name": "Daily Balancing Costs 2025-2026", "format": "CSV"},
        {"id": "bbb", "name": "Daily Balancing Costs 2026-2027", "format": "CSV"},
        {"id": "zzz", "name": "Missing Settlement Periods since January 2017",
         "format": "XLSX"},
    ]}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert bsuos.fiscal_year_resources(client) == {
        "2025-2026": "aaa", "2026-2027": "bbb"}


def test_update_fetches_missing_and_latest_two(tmp_path):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "package_show" in url:
            return httpx.Response(200, json={"success": True, "result": {"resources": [
                {"id": "old", "name": "Daily Balancing Costs 2024-2025", "format": "CSV"},
                {"id": "prev", "name": "Daily Balancing Costs 2025-2026", "format": "CSV"},
                {"id": "cur", "name": "Daily Balancing Costs 2026-2027", "format": "CSV"},
            ]}})
        rid = dict(request.url.params)["resource_id"]
        calls.append(rid)
        return httpx.Response(200, json={"success": True,
                                         "result": {"total": len(RECORDS),
                                                    "records": RECORDS}})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SnapshotStore(tmp_path)
    bsuos.update(store, client=client)
    assert set(calls) == {"old", "prev", "cur"}      # first run: everything missing

    calls.clear()
    bsuos.update(store, client=client)
    assert set(calls) == {"prev", "cur"}             # second run: latest two refreshed
    df = store.read_all_partitions("bsuos", "daily")
    assert df.height == 2 * 3                        # 2 days x 3 stored partitions
