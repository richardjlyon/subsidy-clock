"""Builds the JSON files the static dashboard consumes (spec D-1..D-12 and
phase-2 spec section 5). This module is the engine<->dashboard contract."""

from __future__ import annotations

import html
import json
import math
from datetime import datetime
from pathlib import Path

import polars as pl

from subsidy_engine.sharecards import EXPLAINERS


def _annual_records(annual: pl.DataFrame) -> list[dict]:
    cols = [pl.col("year").cast(pl.Int64), pl.col("cost_gbp").cast(pl.Float64)]
    if "cost_gbp_2024" in annual.columns:
        cols.append(pl.col("cost_gbp_2024").cast(pl.Float64))
    return annual.select(cols).to_dicts()


def _money_block(p: dict, households: int, population: int, demand_mwh: float) -> dict:
    runrate = p["runrate_gbp_per_year"]
    block = {
        "cumulative_gbp": p["cumulative_gbp"],
        "runrate_gbp_per_year": runrate,
        "rate_gbp_per_sec": p["rate_gbp_per_sec"],
        "per_household_per_year_gbp": _floor2(runrate / households),
        "per_person_per_year_gbp": _floor2(runrate / population),
        "per_mwh_delivered_gbp": _floor2(runrate / demand_mwh),
        "since_year": p["since_year"],
    }
    if "cumulative_gbp_2024" in p:
        real_run = p["runrate_gbp_per_year_2024"]
        block["real_2024"] = {
            "cumulative_gbp": p["cumulative_gbp_2024"],
            "runrate_gbp_per_year": real_run,
            "rate_gbp_per_sec": p["rate_gbp_per_sec_2024"],
            "per_household_per_year_gbp": _floor2(real_run / households),
            "per_person_per_year_gbp": _floor2(real_run / population),
            "per_mwh_delivered_gbp": _floor2(real_run / demand_mwh),
        }
    return block


def _floor_to(v: float, step: float) -> float:
    return math.floor(v / step) * step


def _floor2(v: float) -> float:
    """Floor a money value to 2 dp, so every per-unit framing understates and
    the figure is identical wherever it appears (totals.json and the factoids
    must never disagree by a rounding penny)."""
    return math.floor(v * 100) / 100


def _floor_step_below(v: float, step: float) -> float:
    """Floor to the nearest step STRICTLY below v (the F8/I1 rule: a floor,
    never a midpoint, so every sentence quoting it understates).
    app.js's combinedRealFlooredGbp() applies the same rule - keep them in step."""
    f = _floor_to(v, step)
    return f - step if f == v else f


def _combined_real_gbp(model: dict) -> float | None:
    """The full combined direct+indirect cumulative in 2024 prices (no rounding).
    This is the headline share card's figure — the impact is the full number."""
    r = model["perspectives"]["renewables"]
    if ("cumulative_gbp_2024" in r and "indirect" in model
            and "cumulative_gbp_2024" in model["indirect"]):
        return r["cumulative_gbp_2024"] + model["indirect"]["cumulative_gbp_2024"]
    return None


def _combined_real_floored_gbp(model: dict) -> float | None:
    """The combined direct+indirect cumulative in 2024 prices, floored to the
    nearest £10bn STRICTLY BELOW (the I1/F8 rule: a floor, never a midpoint, so
    every sentence quoting it understates). Used by the hero lead-in and the
    'could have built' factoids — NOT the headline card, which shows the full
    figure. app.js's combinedRealFlooredGbp() applies the same rule - keep them in step."""
    combined = _combined_real_gbp(model)
    return _floor_step_below(combined, 1e10) if combined is not None else None


def _factoids(model: dict, ctx: dict, deflators: pl.DataFrame | None) -> list[dict]:
    """The equivalence factoids (impact I4/I5), composed once here so the
    dashboard, the share-card PNGs and the /s/ stubs can never disagree.
    Integrity rules: every division floors; the combined figure is the
    real-2024 £10bn floor and carries 'in today's money' wherever it appears.
    app.js renders display_html verbatim; sharecards.py uses figure+label."""
    eq = ctx.get("equivalences") or {}
    if not eq:
        return []
    r = model["perspectives"]["renewables"]
    runrate = r["runrate_gbp_per_year"]
    out: list[dict] = []

    def src(entry: dict, text: str) -> str:
        return (f'<a class="eq-src" href="{html.escape(entry["source_url"])}" '
                f'title="{html.escape(entry["source"])}">{text}</a>')

    nurse = eq.get("nurse_salary_gbp")
    if nurse:
        fig = f"{int(_floor_to(runrate / nurse['value'], 1000)):,}"
        out.append({
            "slug": "nurses", "figure": fig,
            "sentence": f"A year of direct UK renewable subsidy pays the salaries of {fig} NHS nurses.",
            "display_html": ('A year of this pays the salaries of '
                             f'<span class="money num">{fig}</span> {src(nurse, "NHS nurses")}'),
            "label": "NHS nurses' annual salaries paid by one year of direct renewable subsidy",
            "source_name": nurse["source"], "source_url": nurse["source_url"],
        })

    # counts divide the quoted £10bn floor, not the raw total, so a reader
    # checking the sentence's own arithmetic can only get MORE than we claim —
    # self-consistent and stricter
    combined_floor = _combined_real_floored_gbp(model)
    if combined_floor is not None:
        floored_bn = int(combined_floor / 1e9)
        full = f"£{floored_bn}bn+"
        home = eq.get("social_home_gbp")
        if home:
            fig = f"{int(_floor_to(combined_floor / home['value'], 1000)):,}"
            out.append({
                "slug": "homes", "figure": fig,
                "sentence": (f"The {full} full cost of subsidising UK renewables, including "
                             f"estimated indirect costs, would have built "
                             f"{fig} social homes — land included — in today’s money."),
                "display_html": (f'The {full} full cost would have built '
                                 f'<span class="money num">{fig}</span> {src(home, "social homes")}, '
                                 'land included — in today’s money'),
                "label": (f"social homes (land included) the {full} full UK renewables cost "
                          "would have built, in today's money"),
                "source_name": home["source"], "source_url": home["source_url"],
            })
        hpc = eq.get("hinkley_point_c_gbp")
        if hpc and deflators is not None:
            idx = dict(deflators.iter_rows())
            base = hpc.get("price_base")
            unit = hpc["value"] * (idx[2024] / idx[base]) if base else hpc["value"]
            n = int(combined_floor // unit)
            out.append({
                "slug": "hinkley", "figure": str(n),
                "sentence": (f"The {full} full cost of subsidising UK renewables, including "
                             f"estimated indirect costs, would have built "
                             f"{n} Hinkley Point C-scale nuclear stations in the UK, in today’s money."),
                "display_html": (f'— or <span class="money num">{n}</span> '
                                 f'{src(hpc, "Hinkley Point C")}-scale nuclear stations'),
                "label": (f"Hinkley Point C-scale nuclear stations the {full} full UK renewables "
                          "cost would have built, in today's money"),
                "source_name": hpc["source"], "source_url": hpc["source_url"],
            })

    demand = ctx.get("annual_demand_twh")
    if demand:
        per_mwh = _floor2(runrate / (demand["value"] * 1_000_000))
        fig = f"£{per_mwh:,.2f}"
        out.append({
            "slug": "per-mwh", "figure": fig,
            "sentence": f"Direct renewable subsidy adds {fig} to every MWh of electricity delivered in the UK.",
            "display_html": (f'That is <span class="money num">{fig}</span> on every '
                             f'{src(demand, "MWh of electricity delivered")}'),
            "label": "added to every MWh of electricity delivered in the UK by direct renewable subsidy",
            "source_name": demand["source"], "source_url": demand["source_url"],
        })
    pop = ctx.get("population")
    if pop:
        per_person = _floor2(runrate / pop["value"])
        fig = f"£{per_person:,.2f}"
        out.append({
            "slug": "per-person", "figure": fig,
            "sentence": f"Direct renewable subsidy costs every UK person {fig} a year.",
            "display_html": (f'Per person, it is <span class="money num">{fig}</span> a year '
                             f'{src(pop, "(UK population)")}'),
            "label": "per person per year — the direct cost of renewable subsidy to every UK resident",
            "source_name": pop["source"], "source_url": pop["source_url"],
        })
    return out


def _mapbox_static_url(bm: dict) -> str:
    """Build the Mapbox Static Images API URL for the basemap (served by Mapbox,
    not self-hosted, per their ToS). center/zoom/size fix the Web Mercator frame.
    The access token is deliberately NOT included — it is a per-deploy secret kept
    out of git and appended client-side (see site/map.js + scripts/inject-mapbox-token.js)."""
    retina = "@2x" if bm.get("retina") else ""
    lon, lat = bm["center"]
    return (f"https://api.mapbox.com/styles/v1/{bm['style']}/static/"
            f"{lon},{lat},{bm['zoom']},0/{bm['width']}x{bm['height']}{retina}")


def _web_mercator(lat: float, lon: float, bm: dict) -> tuple[float, float]:
    """Project (lat, lon) to logical pixels on a Mapbox static image defined by
    center/zoom/width/height (512-px tiles). Matches the rendered basemap exactly."""
    world = 512 * 2 ** bm["zoom"]
    def wx(deg: float) -> float:
        return (deg + 180.0) / 360.0 * world
    def wy(deg: float) -> float:
        s = math.sin(math.radians(deg))
        return (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * world
    clon, clat = bm["center"]
    return (bm["width"] / 2 + (wx(lon) - wx(clon)),
            bm["height"] / 2 + (wy(lat) - wy(clat)))


def _map_data(model: dict, coords: dict, basemap: dict) -> dict:
    """One bubble per physical station for the recipients map, over a Mapbox basemap.

    Pulls the ``by_station`` lists from the ``cfd_renewable`` and ``ro``
    SchemeResults' extras; a station appears once per scheme it pays out under
    (so Drax yields two markers). Each (lat, lon) is Web-Mercator-projected into
    the basemap's pixel frame. Stations absent from ``coords`` are dropped."""
    by_id = {s.scheme_id: s for s in model["schemes"]}
    markers = []
    for scheme_id in ("cfd_renewable", "ro"):
        scheme = by_id.get(scheme_id)
        if not scheme:
            continue
        for st in scheme.extras.get("by_station", []):
            ll = coords.get(st["station"])
            if ll is None:
                continue
            x, y = _web_mercator(ll[0], ll[1], basemap)
            markers.append({
                "name": st["station"],
                "scheme": scheme_id,
                "technology": st["technology"],
                "cost_gbp": st["cost_gbp"],
                "x": x,
                "y": y,
            })
    return {
        "basemap": {
            "url": _mapbox_static_url(basemap),
            "width": basemap["width"],
            "height": basemap["height"],
            "attribution": basemap["attribution"],
        },
        "markers": markers,
    }


def build(model: dict, ctx: dict, freshness: dict, out_dir: Path | str,
          *, generated_at: str, deflator_info: dict | None = None,
          bill_annual: pl.DataFrame | None = None,
          bill_info: dict | None = None,
          deflators: pl.DataFrame | None = None,
          coords: dict | None = None, basemap: dict | None = None) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    households = ctx["households"]["value"]
    population = ctx["population"]["value"]
    demand_mwh = ctx["annual_demand_twh"]["value"] * 1_000_000

    totals: dict = {
        "generated_at": generated_at,
        "perspectives": {
            name: _money_block(p, households, population, demand_mwh)
            for name, p in model["perspectives"].items()
        },
    }
    if "indirect" in model:
        totals["indirect"] = _money_block(
            model["indirect"], households, population, demand_mwh)
    (out / "totals.json").write_text(json.dumps(totals, indent=1, allow_nan=False))

    ts: dict = {
        "generated_at": generated_at,
        "perspectives": {
            name: {"annual": _annual_records(p["annual"])}
            for name, p in model["perspectives"].items()
        },
        "indirect": ({"annual": _annual_records(model["indirect"]["annual"])}
                     if "indirect" in model else None),
        "schemes": {
            s.scheme_id: {"annual": _annual_records(s.annual)}
            for s in model["schemes"]
        },
    }
    if bill_annual is not None:
        ts["electricity_bill"] = {"annual": bill_annual.select(
            pl.col("year").cast(pl.Int64),
            pl.col("total_bill_gbp").cast(pl.Float64),
            pl.col("total_bill_gbp_2024").cast(pl.Float64),
        ).to_dicts()}
    (out / "timeseries.json").write_text(json.dumps(ts, indent=1, allow_nan=False))

    (out / "breakdown.json").write_text(json.dumps({
        "generated_at": generated_at,
        "schemes": [
            {
                "id": s.scheme_id,
                "label": s.label,
                "perspectives": s.perspectives,
                "cadence": s.cadence,
                "layer": s.layer,
                "attribution_pct": s.attribution_pct,
                "attribution_note": s.attribution_note,
                "attribution_confidence": s.attribution_confidence,
                "cumulative_gbp": s.cumulative_gbp,
                "runrate_gbp_per_year": s.runrate_gbp_per_year,
                "data_to": s.data_to.isoformat() if s.data_to else None,
                **{k: v for k, v in s.extras.items()},
            }
            for s in model["schemes"]
        ],
    }, indent=1, default=str, allow_nan=False))

    combined_real = _combined_real_gbp(model)
    headline = ({"combined_real_gbp": combined_real}
                if combined_real is not None else None)
    (out / "meta.json").write_text(json.dumps({
        "generated_at": generated_at,
        "freshness": freshness,
        "context": ctx,
        "deflator": deflator_info,
        "bill": bill_info,
        "headline": headline,
        "factoids": _factoids(model, ctx, deflators),
    }, indent=1, allow_nan=False))

    if coords is not None and basemap is not None:
        map_data = _map_data(model, coords, basemap)
        (out / "map.json").write_text(json.dumps(map_data, indent=1, allow_nan=False))
        by_id = {s.scheme_id: s for s in model["schemes"]}
        located = {m["name"] for m in map_data["markers"]}
        wanted = {st["station"] for sid in ("cfd_renewable", "ro")
                  if (s := by_id.get(sid))
                  for st in s.extras.get("by_station", [])}
        print(f"[map] {len(map_data['markers'])} markers, "
              f"{len(wanted - located)} stations missing coords")


# public CSV filename per scheme id - part of the published URL contract (/data/*.csv)
CSV_NAMES = {
    "cfd_renewable":   "cfd",
    "cfd_low_carbon":  "cfd-nuclear",
    "ro":              "renewables-obligation",
    "fit":             "feed-in-tariffs",
    "constraints":     "constraints",
    "capacity_market": "capacity-market",
    "ccl":             "climate-change-levy",
    "ets":             "emissions-trading",
    "tnuos":           "tnuos",
    "bsuos":           "bsuos",
}

RESTATEMENT_COLS = ["scheme", "table", "detected_at", "partition",
                    "previous_version", "new_version"]

CORRECTION_FIELDS = ["date", "figure", "figure_label", "was", "now", "cause"]


def load_corrections(path: Path | str) -> list[dict]:
    """Append-only log of confirmed errors in our own published figures
    (corrections C4) — the restatement-log honesty pattern applied to our own
    mistakes. A missing file means no corrections; a malformed entry fails the
    build loudly — never publish a half-readable log."""
    p = Path(path)
    if not p.is_file():
        return []
    entries = []
    for i, line in enumerate(p.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"corrections.jsonl line {i}: invalid JSON") from exc
        missing = [k for k in CORRECTION_FIELDS if not rec.get(k)]
        if missing:
            raise ValueError(f"corrections.jsonl line {i}: missing {missing}")
        out = {k: rec[k] for k in CORRECTION_FIELDS}
        out["credit"] = rec.get("credit") or ""
        entries.append(out)
    entries.sort(key=lambda r: r["date"])
    return entries


# indirect schemes with their own attribution-rule anchor on /methodology;
# the rest fall back to the #indirect section. Anchors are public contracts.
ATTR_ANCHORS = {"bsuos", "ccl", "ets", "tnuos"}


def _attribution(generated: str) -> str:
    """First two of the three comment lines at the top of every published CSV.
    Stamped (to the minute, UTC) from the same generated_at as the JSON.
    Documented on the /data page: skip with pandas comment='#' or R
    comment.char='#'."""
    return ("# The Subsidy Clock — subsidyclock.co.uk\n"
            '# Licence: CC BY 4.0 (credit "The Subsidy Clock — '
            'subsidyclock.co.uk") · contains public sector information '
            f'licensed under OGL v3.0 — generated {generated[:10]} '
            f'{generated[11:16]} UTC\n')


def write_corrections(entries: list[dict], out_dir: Path | str,
                      *, generated: str) -> None:
    """Publish the corrections log (corrections C4): JSON for the /corrections
    page, CSV for the /data table. Written even when empty — the absence of
    corrections is itself published, not implied."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "corrections.json").write_text(json.dumps(
        {"generated_at": generated, "corrections": entries}, indent=1))
    cols = CORRECTION_FIELDS + ["credit"]
    rows = [{k: str(r.get(k, "")) for k in cols} for r in entries]
    note = ("# Corrections to our own published figures — every confirmed "
            "error: subsidyclock.co.uk/corrections\n")
    (out / "corrections.csv").write_text(
        _attribution(generated) + note +
        pl.DataFrame(rows, schema={k: pl.String for k in cols}).write_csv())


def _series_note(scheme) -> str:
    """Third comment line: what kind of number this is, and where its
    derivation lives. Measured-vs-estimated must travel with the file."""
    if scheme.layer == "indirect":
        anchor = (f"attr-{scheme.scheme_id}"
                  if scheme.scheme_id in ATTR_ANCHORS else "indirect")
        return ("# Estimated share attributed to renewables — method: "
                f"subsidyclock.co.uk/methodology#{anchor}\n")
    slug = EXPLAINERS.get(scheme.scheme_id,
                          (CSV_NAMES.get(scheme.scheme_id, scheme.scheme_id),))[0]
    return ("# Measured payments — derivation: "
            f"subsidyclock.co.uk/explainers/{slug}\n")


def write_csvs(model: dict, out_dir: Path | str,
               *, restatements: list[dict], generated: str) -> None:
    """Per-scheme annual CSVs, one combined wide table, and the restatement
    log (distribution F4). Values are written from the same model that feeds
    the JSON, so CSVs can never disagree with the dashboard. Every file
    carries a three-line attribution header (source, licence, method)."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    header = _attribution(generated)

    def write(df: pl.DataFrame, name: str, note: str) -> None:
        # fixed 2 dp: measured pennies are kept intact, while estimated and
        # deflated values stop carrying spurious float-tail precision
        (out / name).write_text(header + note + df.write_csv(float_precision=2))

    combined = None
    for s in model["schemes"]:
        name = CSV_NAMES.get(s.scheme_id, s.scheme_id)
        df = s.annual.sort("year")
        write(df, f"{name}.csv", _series_note(s))
        col = df.select(pl.col("year"),
                        pl.col("cost_gbp").alias(f"{s.scheme_id}_gbp"))
        combined = col if combined is None else combined.join(
            col, on="year", how="full", coalesce=True)
    if combined is not None:
        write(combined.sort("year"), "combined-annual.csv",
              "# Mixes measured and estimated series — see "
              "subsidyclock.co.uk/methodology#indirect\n")

    rows = [{k: str(r.get(k, "")) for k in RESTATEMENT_COLS} for r in restatements]
    write(pl.DataFrame(rows, schema={k: pl.String for k in RESTATEMENT_COLS}),
          "restatements.csv",
          "# Source revisions log — every restatement the engine has "
          "recorded: subsidyclock.co.uk/data\n")


WIDGET_TEMPLATE = Path(__file__).parent / "templates" / "widget.html"


def write_widget(totals: dict, out_path: Path | str) -> None:
    """Render the embeddable widget (distribution F5), stamping the latest
    figure so a JS-blocked iframe still shows a dated number."""
    r = totals["perspectives"]["renewables"]
    d = datetime.fromisoformat(totals["generated_at"])
    asof = f"{d.day} {d.strftime('%B %Y')}"
    html = (WIDGET_TEMPLATE.read_text()
            .replace("{{CUM}}", repr(r["cumulative_gbp"]))
            .replace("{{RATE}}", repr(r["rate_gbp_per_sec"]))
            .replace("{{GENERATED}}", totals["generated_at"])
            .replace("{{FIGURE}}", f"£{int(r['cumulative_gbp']):,}")
            .replace("{{ASOF}}", asof))
    if "{{" in html:
        raise ValueError("unfilled token in widget template")
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
