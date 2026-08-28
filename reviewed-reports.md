# Reviewed reports (not corrections)

Reports reviewed and judged **not** a data error — scope/methodology questions that
don't belong in `corrections.jsonl` (confirmed errors only). Logged here for the record.

---

## 2026-08-14 — REF constraint totals attacked as unreliable source

- **Reviewed:** 2026-08-14
- **Page:** https://subsidyclock.co.uk/methodology (curtailment section)
- **Reporter:** Not stated (comment criticism)
- **Claim:** "The source for some of the data is the Renewable Energy Foundation, a
  notorious RE-hating group of bigots. It is not an official source, and anything that
  quotes it is unreliable."
- **Verdict:** Reviewed, not a correction. Ad hominem, and factually confused about
  what REF's constraint database is.
  - REF's constraint totals are a tabulation of Elexon Balancing Mechanism bid-acceptance
    data — the official settlement records of the GB grid. The underlying source IS official.
  - The Clock independently reconstructs the same figures bid-by-bid from Elexon's own API
    (back to 28 Dec 2024); REF totals are used only for history before the backfill window,
    and the methodology page states the same accepted-bid method REF uses.
  - If biased, the figures err against the site's argument: bilateral trades outside the BM
    are excluded, so the totals are a stated lower bound.
- **Action:** Reply drafted for Richard to post.

## 2026-06-22 — Local distribution-mains reinforcement omitted

- **Reviewed:** 2026-06-22
- **Data version reported against:** 2026-06-21T07:11:55.354702+00:00
- **Page:** https://subsidyclock.co.uk/methodology
- **Reporter:** Steve Redfern
- **Claim:** Cost of upgrading the local electricity mains (thicker cables, excavation,
  ~£4,500/house × ~30m homes) isn't in the figures; notes David Turver acknowledged the
  same omission in his Eigen Values article comments.
- **Verdict:** Reviewed, not a correction. Out of scope by design.
  - Local distribution-network (DUoS) reinforcement is **demand-driven** — heat pumps and
    EVs raising household peak load — i.e. a cost of electrifying heat/transport, not a
    subsidy to renewable generation.
  - The Clock counts **transmission** (TNUoS) uplift because that reinforcement is
    generation-driven (connecting remote wind); local distribution is the opposite.
  - Funded through regulated network charges (Ofgem RIIO-ED price controls), not a subsidy
    mechanism.
- **Action:** Replied to reporter. Optional follow-up — add a line to the methodology
  "what is not included" list documenting the DUoS-reinforcement exclusion (not yet done).
