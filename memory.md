# Subsidy Clock — operational state

Read at session start. Update when state changes. Durable knowledge lives in the vault hub `Projects/The Subsidy Clock.md`; this is live working state only.

## Headline figures (always re-read live — these go stale)

- Direct hero (ticking, nominal, renewables-only, measured): **~£105–110bn**
- Combined direct + indirect, real 2024 prices — the public headline, floored to **"over £220 billion"**: **~£223bn**
- ⚠️ Unresolved drift: vault flags a **£228bn vs £223bn** discrepancy (Daily 2026-08-15). £223bn is canonical/floored; £228 appears in some content copy. Settle before quoting to experts.

## Open correspondence (Aug 2026)

- **Gordon Hughes (gordon.hughes@cantab.net) + John Constable (john.constable@ref.org.uk)** — both replied warmly 14–15 Aug to Richard's collaboration offer. Hughes & Moroney put UK subsidies at £274bn (2025 prices, 2005–25) via an independent route; the Clock's bottom-up ~£223bn lands nearby. The Clock caught REF's constraints double-count, which Constable acknowledged in writing. Offer: reconcile the two reconstructions, Clock as public front-end for REF's numbers, share the engine. **Hughes cannot travel — his wife is disabled** (per his 14 Aug email) — so propose a call/video, not a table. Reply drafted; awaiting Richard's approval.
- **Robert Eldred (roberteldred@gmail.com)** — asked (6 Aug) for embed restyle: transparent bg, red #D0001B counter, dark-mode variant, "As of [date]" on new line. **Already shipped 14 Aug (commit a3d3c27).** SUBCLK-4 can close once he's told the URLs are live.
- **BP Jones (bobpjones5@gmail.com)** — corrections-form report (6 Aug): Goole's Fields windfarm (SE of Drax, M62/M18) appears missing. Verify whether intentional gap (SUBCLK-3).

## Standing data obligation

- **Annual data refresh overdue.** DUKES 1.3 (July) not ingested — share-of-bill denominator running stale on the live site. Other seven upstream series cluster Jan–Mar. Full table: vault `Tasks/Subsidy Clock — annual data refresh`.

## Siblings (do not conflate in public copy)

- `uk-subsidy-tracker` — scholarly audit resource, **archived 2026-07-09**, superseded by the Clock; owes it the Q1 gas-counterfactual port.
- `cfd-payment` / CfD Visualiser — **shelved 2026-07-09**; two charts queued as ports.
- **Australia** — private development under disclosure embargo (D0), pushes to gitea only. See vault AU spokes.
