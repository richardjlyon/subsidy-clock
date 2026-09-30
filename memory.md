# Subsidy Clock — operational state

Read at session start. Update when state changes. Durable knowledge lives in the vault hub `Projects/The Subsidy Clock.md`; this is live working state only.

## Headline figures (always re-read live — these go stale)

- Direct hero (ticking, nominal, renewables-only, measured): **~£105–110bn**
- Combined direct + indirect, real 2024 prices — the public headline, floored to
  **"over £220 billion"**: **£239.9bn** (measured from the live build 2026-09-30,
  `meta.json` `headline.combined_real` = 239,864,…). Was £228.5bn before the
  **BSUoS basis correction of 30 Sep 2026** (below), which added £11.2bn.
  The floored public headline is unaffected — it still floors to "over £220bn".
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
  correction — 123 files, PASS. It had been DEAD since the AIOS
  migration — the only copy sat in `~/Archive` hardcoded to the deleted
  `/Users/rjl/Code/web-subsidy-clock` and imported three APIs that no longer
  exist, while the openspec docs cited it as a gate on every engine change.
  Proven to fail on a deliberate £1m perturbation (exit 1), not merely to pass.
- **`tests/test_sharecards.py` needs a browser binary**: if it fails with
  "Executable doesn't exist", run `uv run playwright install
  chromium-headless-shell`. Done on this host 30 Sep 2026 — full suite is
  **157 passed, exit 0**, so a sharecard failure is now a real failure.
- `check` leaves the rebuilt `site/` in the tree — `git restore -- site/` after,
  since `site/data` is bot-owned (`.githooks/pre-commit` blocks committing it).

## Siblings (do not conflate in public copy)

- `uk-subsidy-tracker` — scholarly audit resource, **archived 2026-07-09**, superseded by the Clock; owes it the Q1 gas-counterfactual port.
- `cfd-payment` / CfD Visualiser — **shelved 2026-07-09**; two charts queued as ports.
- **Australia** — private development under disclosure embargo (D0), pushes to gitea only. See vault AU spokes.
