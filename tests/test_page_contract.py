"""The page contract: the fields breakdown.json publishes, declared in one table
(sitedata.SCHEME_FIELDS, BREAKDOWN_KEYS; aios-harness#52). A field cannot appear or
vanish unseen: an unlisted field, or a listed one missing, fails the build."""
import json
from datetime import date

import polars as pl
import pytest

from subsidy_engine import sitedata
from subsidy_engine.money import SchemeResult

REF_EXTRAS = {"source": "s", "source_url": "u", "verified": True}


def _scheme(sid, extras, layer="direct"):
    return SchemeResult(scheme_id=sid, label=sid, perspectives=["renewables"],
                        cadence="annual", layer=layer, cumulative_gbp=1.0,
                        runrate_gbp_per_year=1.0, data_to=date(2024, 12, 31),
                        annual=pl.DataFrame({"year": [2024], "cost_gbp": [1.0],
                                             "cost_gbp_2024": [1.0]}),
                        extras=extras)


def test_a_field_the_contract_does_not_list_fails_naming_scheme_and_field():
    with pytest.raises(ValueError, match=r"fit.*publishes 'bottom_up_from'.*not in the page contract"):
        sitedata.scheme_fields(_scheme("fit", REF_EXTRAS | {"bottom_up_from": "2023-08-18"}))


def test_a_listed_field_missing_fails_naming_scheme_and_field():
    with pytest.raises(ValueError, match=r"fit.*lacks 'verified'"):
        sitedata.scheme_fields(_scheme("fit", {"source": "s", "source_url": "u"}))


def test_an_optional_field_may_be_absent():
    assert sitedata.scheme_fields(_scheme("ro", REF_EXTRAS)) == REF_EXTRAS
    full = REF_EXTRAS | {"by_station": [], "recipient_basis": "buyout"}
    assert sitedata.scheme_fields(_scheme("ro", full)) == full


def test_a_scheme_with_no_contract_entry_fails():
    with pytest.raises(ValueError, match="mystery.*no entry in the page contract"):
        sitedata.scheme_fields(_scheme("mystery", {}))


def test_every_scheme_lists_the_common_fields_once():
    assert sitedata.COMMON_FIELDS == ("id", "label", "perspectives", "cadence", "layer",
                                      "attribution_pct", "attribution_note",
                                      "attribution_confidence", "cumulative",
                                      "runrate_per_year", "data_to", "carry_forward")
    for sid, (required, optional) in sitedata.SCHEME_FIELDS.items():
        assert not (set(required) | set(optional)) & set(sitedata.COMMON_FIELDS), sid
        assert not set(required) & set(optional), sid


def test_breakdown_json_carries_exactly_the_declared_fields(tmp_path):
    model = {"schemes": [_scheme("fit", REF_EXTRAS)],
             "perspectives": {}, "indirect": {}}
    doc = sitedata.breakdown_doc(model, "2026-11-01T00:00:00+00:00")
    assert set(doc) <= set(sitedata.BREAKDOWN_KEYS[0]) | set(sitedata.BREAKDOWN_KEYS[1])
    assert set(doc["schemes"][0]) == set(sitedata.COMMON_FIELDS) | set(REF_EXTRAS)
    json.dumps(doc, default=str)


def test_totals_blocks_carry_the_carry_forward_fields(tmp_path):
    """aios-harness#46: each totals.json block (both price bases) declares published_cumulative,
    estimated_since, running_total and the per-line carry_forward."""
    assert sitedata.TOTALS_CARRY_FIELDS == ("published_cumulative", "estimated_since",
                                            "running_total", "carry_forward")
