"""Fix 5 guard (robustness spec, 17 Oct 2026; aios-harness#37): what breakdown.json publishes of it.
The guard itself, and that the model goes through it, are tested in model-bill-already-paid
(aios-harness#140)."""
import json

from clocksite import sitedata


def _breakdown(model, ctx, tmp_path):
    sitedata.build(model, ctx, {}, tmp_path / "site", generated_at="2026-10-17T00:00:00+00:00")
    return json.loads((tmp_path / "site" / "breakdown.json").read_text())


def test_the_pinned_year_and_the_held_window_are_published_in_breakdown_json(tmp_path, real_results):
    # the pages say from which year Elexon replaces REF and from which day data is held
    model = real_results.model
    bd = _breakdown(model, real_results.ctx, tmp_path)
    assert bd["elexon_first_year"] == model["elexon_first_year"] == 2024
    con_model = next(s for s in model["schemes"] if s.scheme_id == "constraints")
    con = next(s for s in bd["schemes"] if s["id"] == "constraints")
    assert (con["held_from"], con["held_to"]) == (con_model.extras["held_from"], con_model.extras["held_to"])
    assert "bottom_up_from" not in con and "bottom_up_from" not in bd


def test_with_no_elexon_data_the_elexon_year_is_not_published(tmp_path, real_results):
    # nothing from Elexon is used then, so publishing 2024 would be false
    model = {**real_results.model, "elexon_first_year": None}
    assert "elexon_first_year" not in _breakdown(model, real_results.ctx, tmp_path)
