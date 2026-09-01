# Subsidy Clock — operational state

Read at session start. Update when state changes. Durable knowledge lives in the vault hub `Projects/The Subsidy Clock.md`; this is live working state only.

## Headline figures (always re-read live — these go stale)

- Direct hero (ticking, nominal, renewables-only, measured): **~£105–110bn**
- Combined direct + indirect, real 2024 prices — the public headline, floored to **"over £220 billion"**: **~£223bn**
- ⚠️ Unresolved drift: vault flags a **£228bn vs £223bn** discrepancy (Daily 2026-08-15). £223bn is canonical/floored; £228 appears in some content copy. Settle before quoting to experts.

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
  engine change; `capture` re-baselines. It had been DEAD since the AIOS
  migration — the only copy sat in `~/Archive` hardcoded to the deleted
  `/Users/rjl/Code/web-subsidy-clock` and imported three APIs that no longer
  exist, while the openspec docs cited it as a gate on every engine change.
  Proven to fail on a deliberate £1m perturbation (exit 1), not merely to pass.
- `check` leaves the rebuilt `site/` in the tree — `git restore -- site/` after,
  since `site/data` is bot-owned (`.githooks/pre-commit` blocks committing it).

## Siblings (do not conflate in public copy)

- `uk-subsidy-tracker` — scholarly audit resource, **archived 2026-07-09**, superseded by the Clock; owes it the Q1 gas-counterfactual port.
- `cfd-payment` / CfD Visualiser — **shelved 2026-07-09**; two charts queued as ports.
- **Australia** — private development under disclosure embargo (D0), pushes to gitea only. See vault AU spokes.
