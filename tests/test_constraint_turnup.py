from datetime import date

import httpx
import polars as pl

from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk.schemes import constraint_turnup as tu

FUEL = {"T_WIND-1": "WIND", "T_GAS-1": "CCGT", "T_GAS-2": "CCGT",
        "T_NOFUEL": None}


def _offer(uid, vol, price, *, so=True, seq=1, cadl=None):
    return {"settlementDate": "2026-06-01", "settlementPeriod": 10, "id": uid,
            "soFlag": so, "cadlFlag": cadl, "sequenceNumber": seq,
            "volume": vol, "originalPrice": price}


def _bid(uid, vol, price, *, so=True):
    return {"settlementDate": "2026-06-01", "settlementPeriod": 10, "id": uid,
            "soFlag": so, "volume": vol, "originalPrice": price}


def test_accepted_offers_counts_only_system_flagged_non_wind():
    offers = [
        _offer("T_GAS-1", 10.0, 90.0),             # counted
        _offer("T_WIND-1", 5.0, 50.0),             # wind: excluded
        _offer("T_GAS-2", 20.0, 70.0, so=False),   # energy action: excluded
        _offer("T_GAS-1", -3.0, 90.0),             # not an offer volume: excluded
    ]
    rows = tu.accepted_offers(offers, FUEL)
    assert rows == {"CCGT": (10.0, 900.0)}


def test_accepted_offers_keeps_unclassified_and_missing_ids():
    offers = [_offer("T_NOFUEL", 2.0, 100.0), _offer("T_UNKNOWN", 1.0, 50.0),
              _offer(None, 4.0, 10.0)]
    rows = tu.accepted_offers(offers, FUEL)
    assert rows == {tu.UNCLASSIFIED: (2.0, 200.0), tu.UNMAPPED: (1.0, 50.0),
                    tu.NO_ID: (4.0, 40.0)}


def test_accepted_offers_labels_neso_trades():
    trade = _offer("20", 2.0, 97.0)
    trade["acceptanceId"] = None
    assert tu.accepted_offers([trade], FUEL) == {tu.TRADE: (2.0, 194.0)}


def test_wind_bids_so_counts_only_flagged_wind_bids():
    bids = [_bid("T_WIND-1", -10.0, -60.0), _bid("T_WIND-1", -4.0, -60.0, so=False),
            _bid("T_GAS-1", -5.0, 30.0)]
    assert tu.wind_bids_so(bids, FUEL) == (-10.0, 600.0)


def test_replacement_estimate_pro_rata_at_margin():
    # 15 MWh switched off; walk: 10 MWh @80 then 10 MWh @100 -> 800 + 500
    offers = [_offer("T_GAS-1", 10.0, 80.0, seq=1),
              _offer("T_GAS-2", 10.0, 100.0, seq=2)]
    assert tu.replacement_estimate(offers, 15.0) == (15.0, 1300.0)


def test_replacement_estimate_orders_unflagged_first_and_skips_cadl():
    offers = [_offer("T_GAS-1", 10.0, 200.0, so=True, seq=1),
              _offer("T_GAS-2", 10.0, 50.0, so=False, seq=9),
              _offer("T_GAS-2", 10.0, 1.0, so=False, seq=1, cadl=True)]
    # unflagged (seq 9) first at 50, CADL excluded, then flagged at 200
    assert tu.replacement_estimate(offers, 12.0) == (12.0, 10 * 50.0 + 2 * 200.0)


def test_replacement_estimate_zero_volume():
    assert tu.replacement_estimate([_offer("T_GAS-1", 10.0, 80.0)], 0.0) == (0.0, 0.0)


def test_period_rows_and_daily_frame():
    bids = [_bid("T_WIND-1", -15.0, -60.0)]
    offers = [_offer("T_GAS-1", 10.0, 80.0, seq=1),
              _offer("T_GAS-2", 10.0, 100.0, seq=2)]
    df = tu.day_frame(date(2026, 6, 1), [(bids, offers)], FUEL)
    got = {(r["basis"], r["fuel"]): (r["volume_mwh"], r["cost_gbp"])
           for r in df.to_dicts()}
    assert got == {
        ("accepted_offers", "CCGT"): (20.0, 1800.0),
        ("accepted_offers_wind", "CCGT"): (20.0, 1800.0),
        ("replacement_estimate", "ALL"): (15.0, 1300.0),
        ("wind_bids_so", "WIND"): (-15.0, 900.0),
    }
    assert df.schema == tu.SCHEMA


def test_accepted_offers_wind_only_counts_periods_with_wind_switched_off():
    gas = [_offer("T_GAS-1", 10.0, 80.0)]
    df = tu.day_frame(date(2026, 6, 1),
                      [([_bid("T_WIND-1", -5.0, -60.0)], gas),   # wind off
                       ([], gas)], FUEL)                          # no wind off
    got = {(r["basis"], r["fuel"]): r["cost_gbp"] for r in df.to_dicts()}
    assert got[("accepted_offers", "CCGT")] == 1600.0
    assert got[("accepted_offers_wind", "CCGT")] == 800.0


def test_daily_cost_defaults_to_the_replacement_estimate(tmp_path):
    store = SnapshotStore(tmp_path)
    df = tu.day_frame(date(2026, 6, 1),
                      [([_bid("T_WIND-1", -5.0, -60.0)],
                        [_offer("T_GAS-1", 10.0, 80.0)])], FUEL)
    store.write(tu.SCHEME, tu.TABLE, df, source_url="u", partition="2026-06-01")
    assert tu.daily_cost(store).to_dicts() == [{"date": date(2026, 6, 1), "cost_gbp": 400.0}]
    assert tu.daily_cost(store, tu.ACCEPTED)["cost_gbp"].to_list() == [800.0]


def test_backfill_writes_one_partition_per_day(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.endswith("/reference/bmunits/all"):
            return httpx.Response(200, json=[
                {"elexonBmUnit": "T_WIND-1", "fuelType": "WIND"},
                {"elexonBmUnit": "T_GAS-1", "fuelType": "CCGT"}])
        period = int(path.rsplit("/", 1)[-1])
        if period != 10:
            return httpx.Response(200, json={"data": []})
        if "/bid/" in path:
            return httpx.Response(200, json={"data": [_bid("T_WIND-1", -10.0, -60.0)]})
        return httpx.Response(200, json={"data": [_offer("T_GAS-1", 10.0, 80.0)]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SnapshotStore(tmp_path)
    assert tu.backfill(store, date(2026, 6, 1), date(2026, 6, 2), client=client) == (2, [])
    daily = tu.daily_cost(store)
    assert daily["cost_gbp"].to_list() == [800.0, 800.0]   # 10 MWh x £80 both ways
    assert store.latest(tu.SCHEME, tu.TABLE, "2026-06-02") is not None


def test_stack_retries_after_a_transient_error(monkeypatch):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"data": [_offer("T_GAS-1", 1.0, 1.0)]})

    monkeypatch.setattr(tu.time, "sleep", lambda s: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert len(tu._stack("offer", date(2026, 6, 1), 1, client)) == 1
    assert len(calls) == 3


def test_backfill_skips_and_reports_a_failed_day(tmp_path, monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/reference/bmunits/all"):
            return httpx.Response(200, json=[])
        if "2026-06-01" in request.url.path:
            return httpx.Response(503)
        return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(tu.time, "sleep", lambda s: None)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    store = SnapshotStore(tmp_path)
    written, failed = tu.backfill(store, date(2026, 6, 1), date(2026, 6, 2), client=client)
    assert (written, failed) == (1, [date(2026, 6, 1)])
    assert store.latest(tu.SCHEME, tu.TABLE, "2026-06-01") is None
