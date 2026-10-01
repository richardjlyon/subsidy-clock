# Subsidy Clock — operational state

Read at session start. Update when state changes. Durable knowledge lives in the vault hub `Projects/The Subsidy Clock.md`; this is live working state only.

## Headline figures (always re-read live — these go stale)

- Direct hero (ticking, nominal, renewables-only, measured): **~£105–110bn**
- Combined direct + indirect, real 2024 prices — the public headline, floored to
  **"over £220 billion"**: **£240.09bn** (measured from the live build 2026-09-30,
  `meta.json` `headline.combined_real` = 240,090,844,344). Was £228.5bn before the
  **BSUoS basis correction of 30 Sep 2026** (below), which added £11.2bn; it then
  moved again when the nightly bot's fresher data was merged.
  The floored public headline is unaffected — it still floors to "over £220bn".
- Direct-only, real 2024 prices (the four measured schemes): **£132.27bn**.
  **Always say which basis a figure is on** — the same schemes are £22.8bn
  (BSUoS, cash as paid) or £26.3bn (real) depending on it. See the basis section.
- ✅ The **£228bn vs £223bn** drift (flagged Daily 2026-08-15) was settled 1 Sep
  against the built site data; superseded by the 30 Sep correction.

## BSUoS basis correction — 30 Sep 2026 (logged publicly)

- **The defect.** The BSUoS series was built from NESO's *Daily Balancing Costs*
  dataset, which is a breakdown of balancing-mechanism spend, NOT the balancing
  cost recovered through BSUoS. It ran **23–39% below** the outturn in NESO's
  Annual Balancing Costs Report every year from 2018-19 (2023-24: £1,824m vs
  £2,455m; 2018-25 total £12.07bn vs £16.80bn). Worse than a narrow source: the
  pre-2017 history and the £0.4bn baseline are on the **gross BSUoS** basis, so
  the engine spliced two definitions mid-series — a **63% cliff** between raw
  2016 (£1,200m) and raw 2017 (£439m).
- **The fix.** `schemes/bsuos.py` now reads NESO's *Current BSUoS Charges*
  dataset: `Half-hourly Charge` to 31 Mar 2023 (pre-reform pass-through, charge
  == cost, and it foots to the dataset's own daily total to the penny), and
  `Actual BSUoS Cost` after — the Apr 2023 fixed-tariff reform broke charge ==
  cost, so **recovery is the wrong column**. Most-settled run type per day wins
  (RF → SF → II). Corrected series runs 1.10–1.23× ABCR with **no step at either
  seam**; 2016→2017 is now **+3.2%**.
- **Effect:** BSUoS attributed £12.54bn → **£22.85bn**; run-rate £1.62 →
  **£3.39bn/yr**; attribution 44.9% → **59.4%**. Headline +£11.2bn (+4.92%).
- **NESO column spellings are not stable within this one dataset** — day is
  "Settlement Day" or "Settlement Date"; cost is "Actual BSUoS Cost (£)" or
  "...Cost(£)" (no space). Exact-string matching broke the live fetch. Matching
  is now on a normalised key, still fail-loud when nothing matches.
- **Consequence for the REF review (unsent).** Review §5.1 tells Constable the
  correction "raises the Clock's BSUoS line by about £4.7bn and its headline by
  2.5%". Measured: **+£10.3bn on the line and +4.92% on the headline.** §5.1 must
  be revised before the review goes out. Awaiting Richard's decision on whether
  to revise the review or publish the correction first.

## Price basis must be stated on every figure — 30 Sep 2026

- **The defect.** The front page showed BSUoS as £26.3bn, `/explainers/bsuos`
  showed £22.8bn. Both correct: the front page sums `cost_real` (2024 prices;
  the basis switch **defaults to real**), the explainers read `breakdown.json`'s
  nominal `cumulative`. Neither page said which basis, so they read as a
  contradiction. **Every scheme was affected** — RO differed by £17.7bn on the
  same data, CCL by 31%.
- **The fix.** Explainers label the total "(cash as paid)" and print the
  real-terms equivalent beneath; front-page cards say "in today's money" or
  "in cash as paid", following the switch; share cards carry the same wording.
  No figure changed, so **no corrections entry** (Richard's call: unlabelled but
  correct goes to methodology, not the log).
- **Rule:** a money figure without its basis is a defect, even when the number
  is right. Two pages disagreeing is how it surfaces; the cause is the missing
  label, not the arithmetic.
- **Open judgement:** the front page defaults to real terms, so the casual
  reader sees the larger number. Defensible and now disclosed, but it is a
  choice — worth a methodology line if it is ever challenged.

## Share-image caching and stubs — 30 Sep 2026

- **og:image needs a content-hash `?v=` on EVERY page, not just the homepage.**
  The nine explainers shipped unstamped. Platforms cache previews by URL, so the
  corrected BSUoS card would never have reached anyone re-sharing those links —
  they would have gone on serving the pre-correction image indefinitely.
  `stamp_index_og` is now a wrapper over the general `stamp_og_images`, and the
  build walks the whole site (reports "N og:image tags cache-busted").
- **Unknown slugs are deliberately left unstamped.** An empty token changes the
  URL without tracking the content — busts the cache once, then sticks. Worse
  than no token.
- **Every scheme card now has a `/s/` stub** (21 → 29) whose click-through lands
  on that scheme's explainer, not the homepage: that page carries the basis,
  sources and method. Previously the 8 scheme cards had no stub, so a scheme
  figure could only be shared via the explainer URL — the exact path with the
  stale-cache fault. The two defects compounded.
- **`verify_stub_targets` fails the build on a dead click-through.** The
  explainer slug map includes `cfd-nuclear`, which has **no page** — an
  unguarded `target_path` publishes a 404 link on a share card. Proved by
  breaking a target deliberately, not by a passing test.
- **Verify cards by reading the rendered PNG, not the stub HTML** (`tesseract`
  is on this host). OCR misreads digits — it read RO as £92,325,105,597 when
  `cards.json` says £92,325,705,597 — so use OCR to confirm *wording/basis*, and
  `cards.json` or the data for *figures*. To prove the deployed PNG is the one
  built: `curl -s <url> | sha256sum` against the local file.

## Re-sharing a link when a platform shows the old card

- **To bust a stale unfurl, append any unused query string to the link you
  paste**: `https://subsidyclock.co.uk/s/bsuos?v=2` (bump to `?v=3` next time).
  Platforms key their preview cache on the exact URL, so this reads as a new
  page and forces a re-scrape; the reader sees the identical page. Twitter
  retired its Card Validator, so there is no flush button any more.
- **Stubs canonicalise to THEMSELVES** (`/s/<slug>`), fixed 30 Sep 2026. They
  previously pointed at `/`, so Facebook and LinkedIn could collapse a shared
  scheme link to the homepage and unfurl the £240bn headline card instead of the
  card shared — and a `?v=` buster dissolves with it. `noindex` (already present)
  is what keeps these out of search; canonical is not a de-indexing tool.
  There is a test asserting this, proved against a full revert. Do not "tidy" it.
- Diagnosing a wrong unfurl: **old card = cache** (use `?v=`); **headline card on
  a scheme link = canonical**. Different faults.

## Factoid audit — 1 Oct 2026

- **hospitals swapped (c9e4eb90, live 1 Oct).** Was 120 x "£2bn largest new NHS
  hospitals": £2bn is the FLOOR of NAO Fig 15's top band ("£2 billion or more"),
  so the count overstated, and NHP costs include future inflation. Now 4 x the
  whole New Hospital Programme (£60bn, 46 schemes, NAO Jan 2026 Summary para 16);
  inflation-inclusive, so it understates. Verified live meta.json + PNG by OCR.
- **homes 610,000 -> 590,000 (1 Oct).** Unit £393,333 = Cebr's £35.4bn /
  90,000 in **2023 prices**; record lacked `price_base`, so it was never uplifted
  to 2024 (~3% overstatement). Now `price_base: 2023`. Residual weakness: source
  is a Shelter/NHF-commissioned study, not official; England only.

## Open correspondence (Aug 2026)

- **Gordon Hughes (gordon.hughes@cantab.net) + John Constable (john.constable@ref.org.uk)** — both replied warmly 14–15 Aug to Richard's collaboration offer. Hughes & Moroney put UK subsidies at £274bn (2025 prices, 2005–25) via an independent route; the Clock's bottom-up ~£223bn lands nearby. The Clock caught REF's constraints double-count, which Constable acknowledged in writing. Offer: reconcile the two reconstructions, Clock as public front-end for REF's numbers, share the engine. **Hughes cannot travel — his wife is disabled** (per his 14 Aug email) — so propose a call/video, not a table. Reply drafted; awaiting Richard's approval.
- **Robert Eldred (roberteldred@gmail.com)** — asked (6 Aug) for embed restyle: transparent bg, red #D0001B counter, dark-mode variant, "As of [date]" on new line. **Shipped 14 Aug (commit a3d3c27); SUBCLK-4 closed Done.** Verified 2026-08-28 — no action outstanding unless Richard still wants to tell him the URLs are live.
- **BP Jones (bobpjones5@gmail.com)** — corrections-form report (6 Aug): Goole's Fields windfarm (SE of Drax, M62/M18) appears missing. Verify whether intentional gap (SUBCLK-3).

## Standing data obligation

- **Annual data refresh: DUKES done 1 Sep 2026.** DUKES 1.3 ingested at the
  2026 edition (published 30 July); the share-of-bill denominator is current
  again after serving stale figures 30 Jul – 1 Sep. Other seven upstream series
  cluster Jan–Mar. Full table: vault `Tasks/Subsidy Clock — annual data refresh`.
- **Citations rot, and nothing watches them.** Verified against the live web
  1 Sep 2026: the stored DUKES asset URL 301-redirects to a NEWER edition (so
  re-fetching to check a stored figure silently returns different data), and the
  **REF April 2025 study URL now 404s** — it has been pulled from ref.org.uk and
  was cited in three files as the cross-check anchoring the whole indirect layer.
  Both now cite archive captures. Treat publisher URLs as unstable. SUBCLK-13
  proposes a build-time freshness + URL sweep; the sweep found two real defects
  on its first run.
- **ETS/DUKES figures are edition-dependent.** DESNZ restates: 2023 power
  emissions moved ~1.0 Mt between report editions, and DUKES revised 2010–2024.
  `reference/indirect_annual.yaml` now records the edition per figure
  (`emissions_vintage`). Always state which edition a number came from.

## Verification machinery

- **Golden master lives at `tools/golden_master.py` (revived 1 Sep 2026).** Run
  `uv run python tools/golden_master.py check` before and after any data or
  engine change; `capture` re-baselines. Re-baselined 30 Sep 2026 after the BSUoS
  correction (123 files) and again after the scheme share stubs landed — **131
  files, PASS**. A changed file SET is reported separately from changed content:
  read that list before re-baselining, it is the cheapest check that you added
  what you meant and removed nothing. It had been DEAD since the AIOS
  migration — the only copy sat in `~/Archive` hardcoded to the deleted
  `/Users/rjl/Code/web-subsidy-clock` and imported three APIs that no longer
  exist, while the openspec docs cited it as a gate on every engine change.
  Proven to fail on a deliberate £1m perturbation (exit 1), not merely to pass.
- **`tests/test_sharecards.py` needs a browser binary**: if it fails with
  "Executable doesn't exist", run `uv run playwright install
  chromium-headless-shell`. Done on this host 30 Sep 2026 — full suite is
  **169 passed, exit 0**, so a sharecard failure is now a real failure.
- `check` leaves the rebuilt `site/` in the tree — `git restore -- site/` after,
  since `site/data` is bot-owned (`.githooks/pre-commit` blocks committing it).

## Siblings (do not conflate in public copy)

- `uk-subsidy-tracker` — scholarly audit resource, **archived 2026-07-09**, superseded by the Clock; owes it the Q1 gas-counterfactual port.
- `cfd-payment` / CfD Visualiser — **shelved 2026-07-09**; two charts queued as ports.
- **Australia** — private development under disclosure embargo (D0), pushes to gitea only. See vault AU spokes.

## The embed widget is most of the team's Vercel Edge Requests — 2026-10-01

Vercel Hobby team went over **Edge Requests** (1.9M of 1M, 6 Sep – 1 Oct); bandwidth
was only 13 GB of 100. This project made 1.33M of them. Matomo (core VM, `matomo-db`,
idsite 2, event category `embed`) logs ~10k widget loads/day, **265k of 268k from
dailysceptic.org** (iframe `/embed/widget?size=card&basis=real&scope=combined`,
`loading=lazy`). Each load = 2 Vercel requests (widget.html + `data/totals.json`),
both `max-age=0`, so nothing is cached in the browser. Matomo undercounts (ad
blockers), which plausibly covers the rest. Main-site pageviews are only ~100/day.
Options put to Richard, not yet chosen: stamp every basis/scope variant into the
widget (drop the fetch) + cache `/embed/*` for an hour; or move the whole static
site to Cloudflare Pages (zone already on Cloudflare, free unlimited requests).
The Matomo API tokens in 1Password are dead again; query the DB via
`qm guest exec 102` → `docker exec matomo-db mariadb -u$MARIADB_USER …`.
