"""Scotland claims briefing — computes every derived figure on /scotland-claims.

The paper is fixed, not live. Two steps:

    uv run python tools/scotland_claims.py compute   # fetch + compute -> figures.json
    uv run python tools/scotland_claims.py render    # figures.json -> index.html

`render` reads only the frozen figures.json, so the published page never moves.
Run `compute` once a year when DESNZ republishes, as a new edition in a new
folder (site/papers/scotland-<year>/); never overwrite a published edition.
Every number is either computed from an official source or quoted from an
official table (quoted constants carry their source URL and the date checked).
The PDF is printed from the rendered page (see the folder's README).

Sources computed live:
  NESO Historic Demand Data 2025   Scotland -> England flow (SCOTTISH_TRANSFER)
                                   and Northern Ireland flow (MOYLE_FLOW), half-hourly
  Elexon B1610                     metered output of named farms and of
                                   Torness + Peterhead, 2025 / 13 Oct 2025
  Clock store                      switch-off payments per farm (constraints)
                                   and CfD payments per farm (cfd/generation)
"""
from __future__ import annotations

import csv
import re
import io
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx
import polars as pl
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from subsidy_engine.store import SnapshotStore  # noqa: E402

ELEXON = "https://data.elexon.co.uk/bmrs/api/v1"
NESO_DEMAND_PKG = "https://api.neso.energy/api/3/action/package_show?id=historic-demand-data"
RANK = {"II": 0, "SF": 1, "R1": 2, "R2": 3, "R3": 4, "RF": 5, "DF": 6}
UA = {"User-Agent": "subsidyclock.co.uk scotland-claims"}
FIRM = ["T_TORN-1", "T_TORN-2", "T_PEHE-1"]
CALM_DAY = "2025-10-13"
CHECKED = "2026-10-10"
EDITION = "2026"
PUBLISHED = "2026-10-10"
PAPER = ROOT / "site" / "papers" / f"scotland-{EDITION}"
URL = f"https://subsidyclock.co.uk/papers/scotland-{EDITION}"

# Quoted from official tables. Each carries its source; re-check when DESNZ republishes.
DESNZ_REGIONAL = ("https://www.gov.uk/government/statistics/regional-renewable-statistics")
DESNZ_SUPPLY = ("https://www.gov.uk/government/statistics/energy-trends-september-2026-special-"
                "feature-article-electricity-generation-and-supply-in-scotland-wales-northern-"
                "ireland-and-england-2021-to-2025")
QUOTED = {
    "load_factor_2025": {"scotland_offshore": 0.2354, "england_offshore": 0.4129,
                         "scotland_onshore": 0.2412, "england_onshore": 0.2414,
                         "source": "DESNZ, Regional renewable statistics: load factors 2009-2025, sheet LF 2025",
                         "url": DESNZ_REGIONAL},
    "generation_2025_gwh": {"onshore": 21980, "offshore": 8870,
                            "source": "DESNZ, Regional renewable statistics: generation 2003-2025, sheet GWh 2025",
                            "url": DESNZ_REGIONAL},
    "capacity_mw": {"onshore_2022": 9027, "offshore_2022": 2166,
                    "onshore_2025": 10490, "offshore_2025": 4301,
                    "source": "DESNZ, Regional renewable statistics: installed capacity 2003-2025 (end of year)",
                    "url": DESNZ_REGIONAL},
    "supply_2025_gwh": {"generated": 54015, "consumed": 27997, "to_england_net": 18519,
                        "to_ni_net": 2232,
                        "source": "DESNZ, Electricity generation and supply in Scotland, Wales, Northern Ireland and England, 2004 to 2025, table 1",
                        "url": DESNZ_SUPPLY},
    "targets": [
        {"what": "Onshore wind", "target": "20 GW by 2030", "now_mw": 10490, "now_label": "10.5 GW",
         "source": "Scottish Government, Onshore Wind Policy Statement, December 2022",
         "url": "https://www.gov.scot/publications/onshore-wind-policy-statement-2022/"},
        {"what": "Offshore wind", "target": "8–11 GW by 2030", "now_mw": 4301, "now_label": "4.3 GW",
         "source": "Scottish Government, Offshore Wind Policy Statement, October 2020",
         "url": "https://www.gov.scot/publications/offshore-wind-policy-statement/"},
        {"what": "Hydrogen production", "target": "5 GW by 2030", "now_mw": None, "now_label": "no official figure",
         "source": "Scottish Government, Hydrogen Action Plan, December 2022",
         "url": "https://www.gov.scot/publications/hydrogen-action-plan/"},
        {"what": "Emissions: 75% cut by 2030", "target": "in law since 2019", "now_mw": None,
         "now_label": "repealed November 2024",
         "source": "Climate Change (Emissions Reduction Targets) (Scotland) Act 2024, section 2",
         "url": "https://www.legislation.gov.uk/asp/2024/15/section/2/enacted"},
    ],
    "firm": {"torness_close": "2030", "peterhead_mw": 1180,
             "torness_source": "EDF, 4 December 2024: Heysham 2 and Torness to generate until 2030",
             "torness_url": "https://www.edfenergy.com/media-centre/edf-confirms-boost-uks-clean-power-targets-nuclear-life-extensions",
             "peterhead_source": "SSE Thermal, Peterhead Power Station",
             "peterhead_url": "https://www.ssethermal.com/flexible-generation/operational/peterhead/",
             "nuclear_policy": "We oppose the building of new nuclear stations using current technologies.",
             "nuclear_policy_url": "https://www.gov.scot/policies/nuclear-energy/nuclear-stations/"},
    "consent": {"text": "Scottish Ministers decide applications for onshore generating stations over 50 MW, and for offshore wind in Scottish waters.",
                "url": "https://www.energyconsents.scot/",
                "offshore_url": "https://www.gov.scot/publications/marine-licensing-and-consent-section-36-consent/"},
}

FARMS = {  # farm prefix -> (display name, offshore?)
    "T_SGRWO": ("Seagreen", True), "T_MOWEO": ("Moray East", True), "T_MOWWO": ("Moray West", True),
    "T_VKNGW": ("Viking", False),
}
CFD_SCOTTISH = ["Beatrice", "Neart na Gaoithe", "Moray Offshore Windfarm (East)", "Dorenell",
                "Kype Muir", "Middle Muir", "Nanclach", "Solwaybank", "Sneddon Law", "Bad A Cheo",
                "Coire Na Cloiche", "Tralorg", "Achlachan"]


def get(url: str, client: httpx.Client):
    for attempt in range(6):
        try:
            r = client.get(url, headers=UA, follow_redirects=True)
            r.raise_for_status()
            return r
        except httpx.HTTPError:
            if attempt == 5:
                raise
    raise RuntimeError(url)


def border(client: httpx.Client) -> dict:
    pkg = get(NESO_DEMAND_PKG, client).json()["result"]["resources"]
    url = next(r["url"] for r in pkg if r["url"].endswith("demanddata_2025.csv"))
    rows = list(csv.DictReader(io.StringIO(get(url, client).text)))
    days: dict[str, list[float]] = defaultdict(list)
    for r in rows:
        own = float(r["SCOTTISH_TRANSFER"]) - float(r["MOYLE_FLOW"] or 0)   # >0: Scotland net exporter, after NI
        days[r["SETTLEMENT_DATE"]].append(own)
    flat = [x for v in days.values() for x in v]
    imp = [x for x in flat if x < 0]
    cd = days[CALM_DAY]
    return {
        "source": "NESO, Historic Demand Data 2025 (SCOTTISH_TRANSFER less MOYLE_FLOW)",
        "url": "https://www.neso.energy/data-portal/historic-demand-data",
        "half_hours": len(flat),
        "importing_half_hours": len(imp),
        "importing_share": round(len(imp) / len(flat), 4),
        "days_net_importer": sum(1 for v in days.values() if sum(v) < 0),
        "imported_gwh": round(-sum(imp) / 2 / 1e3, 1),
        "calm_day_import_half_hours": sum(1 for x in cd if x < 0),
        "calm_day_peak_import_mw": round(-min(cd)),
    }


def b1610(units: list[str], a: str, z: str, client: httpx.Client) -> dict[str, float]:
    q = "&".join(f"bmUnit={u}" for u in units)
    rows = get(f"{ELEXON}/datasets/B1610/stream?from={a}T00:00Z&to={z}T00:00Z&{q}", client).json()
    best: dict = {}
    for r in rows:
        k = (r["bmUnit"], r["settlementDate"], r["settlementPeriod"])
        rk = RANK.get(r["settlementRunType"], -1)
        if k not in best or rk > best[k][0]:
            best[k] = (rk, float(r["quantity"]))
    return best


def farm_units(client: httpx.Client) -> tuple[dict[str, list[str]], dict[str, float]]:
    reg = get(f"{ELEXON}/reference/bmunits/all", client).json()
    units, cap = defaultdict(list), {}
    for u in reg:
        b = u.get("elexonBmUnit") or ""
        for f in FARMS:
            if b.startswith(f + "-"):
                units[f].append(b)
                cap[b] = float(u.get("generationCapacity") or 0)
    return units, cap


def zones_all() -> dict[str, str]:
    return {r["bmu"]: r["nation"] for r in csv.DictReader(open(ROOT / "reference/bmu_zone.csv"))}


def compute() -> None:
    client = httpx.Client(timeout=180)
    store = SnapshotStore(ROOT / "data")
    out: dict = {"generated_at": datetime.now(timezone.utc).isoformat(), "checked": CHECKED,
                 "quoted": QUOTED}
    out["border"] = border(client)

    # Calm day: wind fleet, wind output, Torness + Peterhead, from the Grid Margin-style B1610 read
    units, cap = farm_units(client)
    months = [(f"2025-{m:02d}-01", f"2025-{m + 1:02d}-01" if m < 12 else "2026-01-01") for m in range(1, 13)]
    jobs = [(units[f], a, z) for f in FARMS for a, z in months]
    met: dict[str, float] = defaultdict(float)
    with ThreadPoolExecutor(6) as ex:
        for best in ex.map(lambda j: b1610(*j, client), jobs):
            for (b, _, _), (_, v) in best.items():
                met[b] += v
    con = store.read_all_partitions("constraints", "daily").filter(pl.col("date").dt.year() == 2025)
    farms = []
    for f, (name, off) in FARMS.items():
        us = units[f]
        mw = sum(cap[u] for u in us)
        gwh = sum(met[u] for u in us) / 1e3
        c = con.filter(pl.col("bmu").is_in(us))
        off_gwh = -c["volume_mwh"].sum() / 1e3
        farms.append({"farm": name, "offshore": off, "capacity_mw": round(mw),
                      "metered_gwh": round(gwh), "switched_off_gwh": round(off_gwh),
                      "paid_to_switch_off": round(c["cost_gbp"].sum()),
                      # share of what the farm could have made that it was paid not to make;
                      # needs no capacity figure (Elexon's registered capacities are not nameplate)
                      "share_switched_off": round(off_gwh / (gwh + off_gwh), 3)})
    out["farms_2025"] = farms

    fw = b1610(FIRM, CALM_DAY, "2025-10-14", client)
    firm_mw = sum(v for _, v in fw.values()) * 2 / 48
    sw = [b for b, z in zones_all().items() if z == "Scotland"]
    per_hh: dict = defaultdict(float)
    for i in range(0, len(sw), 40):
        for (b, dd, sp), (_, v) in b1610(sw[i:i + 40], CALM_DAY, "2025-10-14", client).items():
            per_hh[sp] += v * 2
    out["calm_day"] = {"date": CALM_DAY, "firm_mean_mw": round(firm_mw),
                       "wind_mean_mw": round(sum(per_hh.values()) / 48),
                       "wind_max_mw": round(max(per_hh.values())), "wind_units": len(sw)}

    # CfD subsidy to Scottish farms, 2025 — from the Clock's own CfD store
    cfd = store.read_all_partitions("cfd", "generation").filter(pl.col("date").dt.year() == 2025)
    pat = "|".join(re.escape(n) for n in CFD_SCOTTISH)
    sc = cfd.filter(pl.col("unit_name").str.contains(pat))
    by = (sc.with_columns(pl.col("unit_name").str.replace(r"(?i)\s*(Offshore Wind Farm Limited)?\s*\(?Phase.*$", "").alias("farm"))
          .group_by("farm").agg(pl.col("payment_gbp").sum()).sort("payment_gbp", descending=True))
    out["cfd_2025"] = {"total": round(sc["payment_gbp"].sum()),
                       "farms": [{"farm": r[0].strip(), "paid": round(r[1])} for r in by.iter_rows()],
                       "source": "LCCC, Contracts for Difference generation and payments (the Clock's CfD series)"}
    ctx = yaml.safe_load(open(ROOT / "reference/context.yaml"))["electricity_consumption_by_nation"]
    out["consumption"] = {"share": round(ctx["scotland_gwh"] / ctx["gb_gwh"], 4),
                          "source": ctx["source"], "url": ctx["source_url"]}
    zones = zones_all()
    nation = pl.col("bmu").replace_strict(zones, default="?")
    sc_con = con.filter(nation == "Scotland")
    offp = ("T_ABRBO", "T_BEATO", "T_INCWO", "T_MOWEO", "T_MOWWO", "T_NNGAO", "T_SGRWO")
    top = (sc_con.group_by("date").agg(pl.col("cost_gbp").sum(), (-pl.col("volume_mwh").sum()).alias("mwh"))
           .sort("cost_gbp", descending=True).row(0))
    out["switch_off_2025"] = {
        "gb_cost": round(con["cost_gbp"].sum()),
        "scotland_cost": round(sc_con["cost_gbp"].sum()),
        "scotland_share": round(sc_con["cost_gbp"].sum() / con["cost_gbp"].sum(), 4),
        "scotland_gwh": round(-sc_con["volume_mwh"].sum() / 1e3),
        "scotland_offshore_gwh": round(-sc_con.filter(pl.col("bmu").str.slice(0, 7).is_in(offp))["volume_mwh"].sum() / 1e3),
        "top_day": {"date": top[0].isoformat(), "cost": round(top[1]), "mwh": round(top[2])},
    }
    PAPER.mkdir(parents=True, exist_ok=True)
    (PAPER / "figures.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("wrote", PAPER / "figures.json")

# ---------------------------------------------------------------- render (static)

def _n(v): return f"{round(v):,}"
def _m(v): return f"£{round(v / 1e6):,}m"
def _pc(v, d=0): return f"{v * 100:.{d}f}%"
def _gw(mw): return f"{mw / 1000:.1f} GW"
def _day(iso):
    d = datetime.fromisoformat(iso)
    return f"{d.day} {d.strftime('%B %Y')}"
def _a(url, text): return f'<a href="{url}">{text}</a>'


def cards(d: dict) -> list[dict]:
    q, b, so = d["quoted"], d["border"], d["switch_off_2025"]
    lf, sup, cap, f = q["load_factor_2025"], q["supply_2025_gwh"], q["capacity_mw"], q["firm"]
    sg = next(r for r in d["farms_2025"] if r["farm"] == "Seagreen")
    share = d["consumption"]["share"]
    sub = d["cfd_2025"]["total"] + so["scotland_cost"]
    desnz_lf, desnz_sup = _a(lf["url"], "DESNZ load factors 2025"), _a(sup["url"], "DESNZ generation and supply 2025")
    neso = _a(b["url"], "NESO demand and flow data 2025")
    elexon = _a("https://bmrs.elexon.co.uk/", "Elexon metered output (B1610)")
    stack = _a("https://bmrs.elexon.co.uk/", "Elexon settlement bid data (method below)")
    rate = (cap["onshore_2025"] - cap["onshore_2022"]) / 3
    on2030 = cap["onshore_2025"] + 5 * rate
    off_lf = (q["generation_2025_gwh"]["offshore"] + so["scotland_offshore_gwh"]) / (cap["offshore_2025"] * 8.76)
    rows = "".join(f'<tr><td>{_a(t["url"], t["what"])}</td><td>{t["target"]}</td><td>{t["now_label"]}</td></tr>'
                   for t in q["targets"])
    cd, td = d["calm_day"], so["top_day"]
    exp = f"{sup['to_england_net'] / 1000:.1f} TWh"
    return [
        dict(claim="Scotland generates more renewable electricity than it uses.",
             answer=f"Over a year, yes: Scotland sent {exp} more to England than it took back in 2025. Hour by hour, no. "
                    f"In {_n(b['importing_half_hours'])} half-hours of 2025 ({_pc(b['importing_share'], 1)}) Scotland could not "
                    f"cover its own demand and was a net importer from England.",
             detail=f"On {_day(cd['date'])} the wind dropped. The {cd['wind_units']} wind farm units Elexon meters in Scotland "
                    f"averaged {_n(cd['wind_mean_mw'])} MW, and never more than {_n(cd['wind_max_mw'])} MW, against "
                    f"{_gw(cap['onshore_2025'] + cap['offshore_2025'])} of Scottish wind capacity. Torness and Peterhead supplied "
                    f"{_n(cd['firm_mean_mw'])} MW on average, and Scotland was still a net importer from England in "
                    f"{b['calm_day_import_half_hours']} of 48 half-hours, at up to {_n(b['calm_day_peak_import_mw'])} MW.",
             reply=f"Scotland is a net exporter: {exp} to England in 2025.",
             rejoin="The yearly surplus is made on windy days. On calm days Scotland relies on a nuclear station due to "
                    "close in 2030, a gas station, and power from England.",
             src=[desnz_sup, neso, elexon]),
        dict(claim="Scotland’s wind fleet is a national asset.",
             answer=f"Scottish offshore wind farms ran at {_pc(lf['scotland_offshore'], 1)} of their capacity in 2025. "
                    f"English offshore farms ran at {_pc(lf['england_offshore'], 1)}.",
             detail=f"The gap is not the wind. Scottish offshore farms were paid to switch off {_n(so['scotland_offshore_gwh'])} GWh "
                    f"in 2025. Add that to the {_n(q['generation_2025_gwh']['offshore'])} GWh they generated and they would have "
                    f"run at about {_pc(off_lf)}, close to England’s. Seagreen, the largest, was paid {_m(sg['paid_to_switch_off'])} "
                    f"to switch off {_pc(sg['share_switched_off'])} of what it could have generated "
                    f"({_n(sg['switched_off_gwh'])} of {_n(sg['switched_off_gwh'] + sg['metered_gwh'])} GWh).",
             reply="Curtailment is a grid problem. The grid is reserved to Westminster and run by NESO and Ofgem.",
             rejoin="Then the farms were approved faster than the grid could take their output. Scottish Ministers "
                    "approved them (claim 3).",
             src=[desnz_lf, elexon, stack]),
        dict(claim="Constraint payments are Westminster’s grid problem.",
             answer=f"In 2025, {_m(so['scotland_cost'])} was paid to Scottish wind farms to switch off: "
                    f"{_pc(so['scotland_share'])} of all such payments to wind farms in Britain.",
             detail=f"Scottish Ministers decide whether onshore power stations over 50 MW, and offshore wind farms in "
                    f"Scottish waters, are built. The most expensive single day of 2025 was {_day(td['date'])}: "
                    f"{_m(td['cost'])} paid to Scottish farms not to generate {_n(td['mwh'] / 1000)} GWh.",
             reply="Transmission is reserved. Scotland cannot build the lines.",
             rejoin="Approving the farms is devolved. Ministers chose how much generation to approve, and the "
                    "switch-off bill measures how far it ran ahead of the lines.",
             src=[_a(q["consent"]["url"], "Energy Consents Unit"),
                  _a(q["consent"]["offshore_url"], "section 36 offshore consents"), stack]),
        dict(claim="Scotland’s energy props up the rest of the UK.",
             answer=f"In 2025 Scottish wind farms received {_m(d['cfd_2025']['total'])} in Contracts for Difference top-ups "
                    f"and {_m(so['scotland_cost'])} to switch off: {_m(sub)}.",
             detail=f"Both are charged to suppliers across Great Britain for every unit of electricity they sell. Scotland "
                    f"uses {_pc(share, 1)} of Britain’s electricity, so about {_m(sub * (1 - share))} ({_pc(1 - share)}) was "
                    f"paid by bill-payers in England and Wales. Not counted: the Renewables Obligation, the older scheme "
                    f"most Scottish onshore farms are paid under, so the true figure is higher.",
             reply="Scottish generators pay the highest grid charges in Europe.",
             rejoin="Those charges reflect the cost of carrying Scottish power hundreds of miles south to where it is "
                    "used. They follow from where the farms were built.",
             src=[_a("https://www.lowcarboncontracts.uk/data-portal", "LCCC CfD payments"), stack,
                  _a(d["consumption"]["url"], "DESNZ consumption by nation")]),
        dict(claim="Scotland’s electricity supply is secure.",
             answer=f"Torness, Scotland’s last nuclear station, is due to close in 2030. That leaves Peterhead (gas, "
                    f"{_n(f['peterhead_mw'])} MW) as Scotland’s only large nuclear or fossil-fuelled power station.",
             detail=f"The Scottish Government’s stated position: “{f['nuclear_policy']}” On {_day(cd['date'])} Torness "
                    f"and Peterhead were both running and Scotland still needed power from England.",
             reply="Scotland is part of a single British grid. Drawing power from England on a calm day is normal.",
             rejoin="Then Scotland’s supply after 2030 depends on gas stations in England, and the claim of energy "
                    "self-sufficiency falls.",
             src=[_a(f["torness_url"], "EDF, December 2024"), _a(f["peterhead_url"], "SSE Thermal"),
                  _a(f["nuclear_policy_url"], "Scottish Government nuclear policy"), neso]),
        dict(claim="Scotland is on track for its 2030 targets.",
             answer=f"Onshore wind stood at {_gw(cap['onshore_2025'])} at the end of 2025, against a 20 GW target for "
                    f"2030. At the 2022–25 rate of building ({_n(rate)} MW a year) it reaches about {_gw(on2030)} by 2030.",
             detail='<table class="data-table claim-table"><thead><tr><th>Target</th><th>For 2030</th>'
                    f'<th>Where it stands</th></tr></thead><tbody>{rows}</tbody></table>',
             reply="Delivery depends on UK auctions and UK grid investment.",
             rejoin="Scottish Ministers set these targets. The one written into law, a 75% cut in emissions by 2030, "
                    "was repealed in 2024 rather than met.",
             src=[_a(cap["url"], "DESNZ installed capacity")]
                 + [_a(t["url"], ",".join(t["source"].split(",")[:2])) for t in q["targets"]]),
    ]


def render() -> None:
    d = json.loads((PAPER / "figures.json").read_text())
    body = "".join(
        f'<article class="claim"><p class="claim-n">{i}</p>'
        f'<p class="claim-said"><span class="claim-k">The claim</span>“{c["claim"]}”</p>'
        f'<p class="claim-answer">{c["answer"]}</p><p class="claim-detail">{c["detail"]}</p>'
        f'<p class="claim-reply"><span class="claim-k">The reply to expect</span>{c["reply"]}</p>'
        f'<p class="claim-rejoin"><span class="claim-k">The answer to it</span>{c["rejoin"]}</p>'
        f'<p class="claim-src"><span class="claim-k">Sources</span>{" · ".join(c["src"])}</p></article>'
        for i, c in enumerate(cards(d), 1))
    pub = _day(PUBLISHED)
    title = "Scotland’s energy claims, against the record"
    cite = f"Lyon, R. ({EDITION}). <em>{title}</em>. The Subsidy Clock, {pub}. {URL}"
    html = (ROOT / "tools/templates/paper.html").read_text()
    for k, v in {"TITLE": title, "URL": URL, "PUBLISHED": pub, "CHECKED": _day(d["checked"]), "EDITION": EDITION,
                 "CARDS": body, "CITE": cite, "PDF": f"scotland-claims-{EDITION}.pdf"}.items():
        html = html.replace("{{" + k + "}}", v)
    assert "{{" not in html
    (PAPER / "index.html").write_text(html)
    print("wrote", PAPER / "index.html")


if __name__ == "__main__":
    {"compute": compute, "render": render}[sys.argv[1]]()
