**To:** david_turver@hotmail.com
**Subject:** Re: Subsidy Clock Feedback

---

Hi David,

Thank you again for the workbooks — they've made a real difference, and I wanted to show you exactly what I've done with them before I put your name to any of it. Nothing here is set in stone; if I've got something wrong, I'd rather fix it now than credit you for work you'd dispute.

**What your data changed**

- **Recipients, by station.** Using your CfD asset short-names, the "largest recipients" table now groups by physical station rather than by contract — so Walney Extension's phases (and the like) collapse into one line you can expand to see the individual contracts. That was your point about phased wind farms looking like duplicates.
- **RO generators, named.** Your per-station ROC workbooks let me put named RO recipients into that table for the first time (on a buy-out basis) — Drax now sits at the top. I kept Ofgem's official recycle-inclusive scheme value (~£74.6bn) as the headline, because it's the full consumer cost, and used your buy-out reconstruction as a like-for-like cross-check. Bottom-up it lands around £60bn, which reconciles cleanly with the headline once recycle value and the earliest scheme years are accounted for. If you think the headline basis should change, I'm very open to that conversation.
- **TNUoS.** I've replaced my cruder estimates with your NESO charging-statement figures for 2013/14 through 2024/25. One thing worth flagging: your "fiscal year ended March" rows map to my calendar year of the period start (so FYE-March-2023 = my 2022), and on that mapping your numbers reproduced my three independent NESO anchor years *exactly* — which is what gave me the confidence to adopt the rest.

**What I held back, and why**

- **BSUoS / balancing costs.** Here I hit a genuine definitional fork and decided not to splice your series in until I've agreed it with you. Your "balancing costs" appear to be NESO's balancing-actions measure, which excludes National Grid's own internal/admin costs (~£130m/yr — it's the gap between your £869m for 2013-14 and the NAO's £1,002m for the same year). My earlier years use the NAO's "Figure 9" basis (total recovered through BSUoS, *including* those internal costs). Both are legitimate; they just draw the boundary differently, and mixing them mid-series would create an artificial step. Which definition would you standardise on? Whatever I pick, I'd want the whole series — baseline included — on the same ruler.
- **Earliest years.** TNUoS before 2013 and BSUoS 2006–2010 stay caveated for now — your data doesn't reach back that far and the NAO report only gives those as an unlabelled chart.

**The annual refresh question**

I looked at automating the newer ROC certificates from the Ofgem SharePoint gallery you use, but it's behind a sign-in wall for me, so I can't script it. My plan is simply to re-ingest your workbooks whenever you refresh them. (For the RO headline it doesn't actually matter much — it's recycle-inclusive, which is an annual settlement, so more frequent issuance data wouldn't move it anyway.) How do you keep yours current?

**Have a look?**

Everything above is live:

- Recipients table (CfD grouping + named RO): https://subsidyclock.co.uk
- Methodology, with the TNUoS/BSUoS source notes and caveats: https://subsidyclock.co.uk/methodology.html

If you're happy it's faithful to your work, I'll add a proper credit on the About page pointing to RER / Eigen Values. And do push back on anything that looks off.

Best,
Richard
