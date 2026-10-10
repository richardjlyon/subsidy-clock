from datetime import date

import httpx
import polars as pl

from subsidy_engine_uk.elexon import wind_bmu_map
from subsidy_engine_uk.schemes import constraints

WIND = {"T_ABRBO-1": "Aberdeen Offshore Wind Farm"}

STACK_ROWS = [
    {   # wind turn-down: negative volume at negative price -> positive cost
        "settlementDate": "2026-06-01", "settlementPeriod": 10,
        "id": "T_ABRBO-1", "acceptanceId": 1, "soFlag": True,
        "volume": -10.0, "originalPrice": -60.0,
    },
    {   # battery bid at positive price -> unit pays back, negative cost
        "settlementDate": "2026-06-01", "settlementPeriod": 10,
        "id": "E_LITRB-1", "acceptanceId": 2, "soFlag": False,
        "volume": -2.475, "originalPrice": 97.74,
    },
]


def test_parse_stack_filters_to_wind_and_computes_cost():
    df = constraints.parse_stack(STACK_ROWS, WIND)
    assert df.height == 1
    row = df.to_dicts()[0]
    assert row["date"] == date(2026, 6, 1)
    assert row["bmu"] == "T_ABRBO-1"
    assert row["lead_party"] == "Aberdeen Offshore Wind Farm"
    assert row["volume_mwh"] == -10.0
    assert row["cost_gbp"] == 600.0  # -10 MWh * -£60/MWh


def test_parse_stack_empty_input():
    df = constraints.parse_stack([], WIND)
    assert df.height == 0
    assert set(df.columns) == {
        "date", "settlement_period", "bmu", "lead_party",
        "volume_mwh", "price_gbp_mwh", "cost_gbp",
    }


def test_daily_summary_aggregates_periods():
    rows = [
        dict(STACK_ROWS[0]),
        dict(STACK_ROWS[0], settlementPeriod=11, acceptanceId=3, volume=-5.0),
    ]
    daily = constraints.daily_summary(constraints.parse_stack(rows, WIND))
    assert daily.to_dicts() == [{
        "date": date(2026, 6, 1), "bmu": "T_ABRBO-1",
        "lead_party": "Aberdeen Offshore Wind Farm",
        "volume_mwh": -15.0, "cost_gbp": 900.0,
    }]


def test_wind_bmu_map_filters_fuel_type():
    payload = [
        {"elexonBmUnit": "T_ABRBO-1", "fuelType": "WIND",
         "leadPartyName": "Aberdeen Offshore Wind Farm"},
        {"elexonBmUnit": "E_LITRB-1", "fuelType": "BATTERY", "leadPartyName": "X"},
        {"elexonBmUnit": "T_FOO-1", "fuelType": None, "leadPartyName": "Y"},
    ]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert wind_bmu_map(client) == {"T_ABRBO-1": "Aberdeen Offshore Wind Farm"}


def test_parse_stack_skips_rows_missing_price():
    row = dict(STACK_ROWS[0])
    del row["originalPrice"]
    df = constraints.parse_stack([row], WIND)
    assert df.height == 0


def test_fetch_day_collects_all_periods():
    def handler(request: httpx.Request) -> httpx.Response:
        period = int(request.url.path.rsplit("/", 1)[-1])
        if period == 10:
            return httpx.Response(200, json={"data": STACK_ROWS})
        return httpx.Response(200, json={"data": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    df = constraints.fetch_day(date(2026, 6, 1), WIND, client)
    assert df.height == 1
    assert df.to_dicts()[0]["bmu"] == "T_ABRBO-1"  # battery row filtered out
    assert df.to_dicts()[0]["cost_gbp"] == 600.0


def test_cost_applies_transmission_loss_multiplier():
    """Elexon settles volume x price x TLM; REF's totals match only with it."""
    row = dict(STACK_ROWS[0], transmissionLossMultiplier=0.96)
    df = constraints.parse_stack([row], WIND)
    r = df.to_dicts()[0]
    assert abs(r["cost_gbp"] - 576.0) < 1e-9   # -10 x -60 x 0.96
    assert r["volume_mwh"] == -10.0            # volume is not scaled


def test_write_day_labels_only_the_first_reread_as_ours(tmp_path):
    import json
    from subsidy_engine.store import SnapshotStore
    store = SnapshotStore(tmp_path)
    day = lambda c: pl.DataFrame({"date": [date(2026, 6, 1)], "bmu": ["T_ABRBO-1"],
                                  "lead_party": ["x"], "volume_mwh": [-10.0], "cost_gbp": [c]})
    store.write("constraints", "daily", day(600.0), source_url="u",
                partition="2026-06-01", source_date="2026-06-01")
    import subsidy_engine_uk.schemes.constraints as c
    old = c.BASIS_CHANGE_VERSION
    c.BASIS_CHANGE_VERSION = "99999999T"          # the stored version predates the change
    c.write_day(store, "2026-06-01", day(576.0))
    c.BASIS_CHANGE_VERSION = "00000000T"          # later re-reads are the publisher's
    c.write_day(store, "2026-06-01", day(570.0))
    c.BASIS_CHANGE_VERSION = old
    log = [json.loads(l) for l in open(tmp_path / "raw/constraints/daily/restatements.jsonl")]
    assert [e["origin"] for e in log] == ["ours", "publisher"]
