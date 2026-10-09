# Annual direct subsidy 2025, and "set to rise significantly" — claim check

Date: 2026-10-08. For RJL only; figures marked [RL calculation] are ours.

## 1. Does the Clock show annual direct / indirect totals?

Checked against the rendered live page (headless Chromium, innerText), 8 Oct 2026.

- **No £bn-a-year figure for the direct or the indirect layer is shown anywhere.**
- What it shows instead: per-second rates (direct £380.76/s, indirect £304.85/s, real terms);
  a combined "£1.8bn every month"; per household £746.07/yr; per MWh £79.01; "this year £16.6bn
  since 1 January"; constraints alone get "£350.2m per year at current run-rate".
- The "By year" switch on the trend chart gives annual bars **by scheme**, in 2024 prices, with
  values only in hover tooltips. No layer totals. 2025 and 2026 bars omit RO, FiT, CCL, ETS and
  TNUoS (annual schemes not yet reported), so the 2025 bar understates the year by roughly £10bn.
- Implied (not shown) [RL calculation]: direct run-rate £380.76/s × 1 year = £12.0bn/yr real;
  indirect £304.85/s = £9.6bn/yr real. Matches `totals.json` runrate_per_year (£12.04bn, £9.61bn).

## 2. Direct subsidy, 2025 [RL calculation]

Clock convention: RO and FiT by scheme year starting April 2025; CfD and constraints calendar 2025.
Cash as paid.

| Scheme | 2025 | Source |
|---|---|---|
| Renewables Obligation (SY24, Apr 25–Mar 26) | £8.01bn | Ofgem total obligation 119,412,356 ROCs (10 Sep 2026) × buy-out £67.06. Method check: same sum for SY23 gives £7.74bn vs Ofgem's stated £7.70bn |
| Feed-in Tariffs (FIT Yr 16, Apr 25–Mar 26) | £1.97bn | Ofgem FIT Quarterly Reports 61–64, generation + export payments: £563.2m + £576.5m + £454.8m + £375.6m |
| CfD renewables (cal. 2025) | £2.64bn | Clock combined-annual.csv (LCCC) |
| Constraint payments (cal. 2025) | £0.40bn | Clock combined-annual.csv (Elexon) |
| **Total** | **£13.0bn** | ≈ £12.5bn in 2024 prices (CPIH 132.9/138.0) |

2024 on the same basis: £12.3bn. Change: +6% cash.
Cross-check: OBR outturn-estimate RO 2025-26 £8.20bn; Ofgem's own forecast scheme value £8.7bn
(on forecast supply). So £8.0bn is the low end. RO SY24 is not yet in Ofgem's annual report
(due ~Mar 2027); FiT SY16 report not yet out — both figures provisional.

## 3. "Set to rise significantly" — OBR, EFO March 2026, receipts table 3.20 (£bn, cash)

| | 24-25 | 25-26 | 26-27 | 27-28 | 28-29 | 29-30 | 30-31 |
|---|---|---|---|---|---|---|---|
| Renewables obligation | 7.77 | 8.20 | 8.33 | 6.59 | 6.66 | 6.54 | 6.40 |
| Contracts for difference | 2.27 | 2.77 | 2.73 | 3.04 | 3.33 | 3.92 | 5.15 |
| Capacity market | 0* | 1.64 | 2.91 | 3.81 | 3.81 | 3.93 | 4.37 |
| Green gas levy | 0* | 0.06 | 0.09 | 0.16 | 0.20 | 0.22 | 0.23 |
| Warm home discount | 0.48 | 0.83 | 1.18 | 0.97 | 0.97 | 0.97 | 0.97 |
| Sizewell C RAB levy | 0 | 0.49 | 0.70 | 0.80 | 0.99 | 1.16 | 1.40 |
| **Environmental levies** | 10.52 | 13.99 | 15.94 | 15.36 | 15.95 | 16.74 | 18.51 |

*OBR note 1: ONS outturn excludes capacity market and green gas; including them 2024-25 would
have been £1.3bn and £0.01bn higher. CfD 2030-31 includes £0.98bn for Hinkley Point C (table 3.21).

Verdict:
- **True of the levy total, overstated in the usual form.** £10.5bn → £18.5bn (+76%) compares an
  outturn missing the capacity market with a forecast that includes it. Like-for-like +56%
  (£11.8bn → £18.5bn); from 2025-26, +32%. All cash, not real.
- **False of renewable-generator subsidy through 2030-31.** RO + CfD: £11.0bn (25-26) → £11.5bn
  (30-31), +5% cash; excluding Hinkley, −4%. RO falls £1.8bn as accreditations run off from 2027;
  CfD rises £2.4bn.
- The rise is the **capacity market (+£2.7bn), Sizewell C (+£0.9bn) and Hinkley (+£1.0bn)**.
  The Clock counts the capacity market as indirect, at 100%.
- Beyond the horizon: OBR's CfD line includes AR7 only partly; most AR7 offshore wind (8.4 GW,
  £91.20/MWh 2024 prices) delivers 2028-31, plus Hinkley's full years. A post-2030 rise is
  plausible but no official number exists for it. Do not quote AR7 "total value of applications"
  (£7.4bn in 2032-33) as cost: it is all bids at administrative strike price, not awards.

Safe sentence: "The OBR expects levies on energy bills to rise from £14.0bn in 2025-26 to
£18.5bn in 2030-31 in cash terms. Most of that is the capacity market and new nuclear; payments
under the two main renewable schemes stay near £11bn as the Renewables Obligation winds down
and Contracts for Difference grow."

## Knock-on

`richardlyon/reports/no1-price-of-support/report.typ` line ~504 says the levies "rise by
three-quarters in six years: from £10.5bn in 2024-25 to £18.5bn in 2030-31" and sets this
against the renewables bill. Same definitional break; needs the like-for-like wording above.
