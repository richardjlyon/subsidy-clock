<!-- Reviewed with Richard, 6 Nov 2026 (aios-harness#88) -->

# web-subsidy-clock

The public face of the bill already paid: a live, sourced count of what renewable electricity subsidies have cost Britain since 2002, at subsidyclock.co.uk. Trust first, the book a distant second. Every figure stands up to a hostile expert, and a first-time visitor sees within seconds how big the bill is and that they pay it. (Richard, 6 Nov 2026)

- **Who it is for, first:** journalists and MPs who quote it. The public's sharing and the experts' checking serve that.
- **This repository is the website only.** The sums are `/srv/aios/projects/model-bill-already-paid`; the site builds from its `results/clock.json`, pinned in `reference/results_pin.yaml`. A figure is fixed there, never here.

## Rules (Richard, 6 Nov 2026)

- Every figure says which money it is in: 2024 pounds, or cash as paid at the time.
- Any change to a published figure gets an entry in `changelog.jsonl` in the same commit.
- The book is named only on the About page.
- No tone of complaint. A sharp line is a quotation from someone else, never our own accusation. Never the word "ideology".
- Pushing to GitHub `richardjlyon/subsidy-clock` publishes: only on Richard's say-so, each time.
- This repository is public. Anything not for the public (correspondence, strategy, unpublished findings) goes in `private/`, its own private repo on Gitea `rjl/web-subsidy-clock-private`, never on GitHub.

## Commands

- All tests: `tools/test.sh` (every test must pass). One file: `tools/test.sh tests/test_build_site.py`. Before a release: `tools/test.sh --release`.
- Run Python here: `uv run --frozen python`

## How it goes live

- GitHub `richardjlyon/subsidy-clock` `master` is what is live. Its robot (`.github/workflows/update.yml`) commits there every morning, then publishes `site/` to Cloudflare Pages. Gitea `rjl/web-subsidy-clock` (`origin` here) follows it: fetch GitHub `master` before any commit, and keep the two the same.
- `data/`, `site/data/`, `site/share/`, `site/s/`, `site/embed/` and `site/index.html` are the robot's; the pre-commit hook refuses them in a hand-made commit. A hand edit to `site/index.html` needs `git commit --no-verify`.
- `deploy.yml` should publish a hand-made `site/` change pushed to `master`, but did not start on 6 Nov (aios-harness#142): check the run.

## Misleading places

- `AGENTS.md` and `memory.md` are old notes from before 6 Nov (Plane, `~/AIOS` paths, the vault as the record). Not instructions; this file governs.
- `private/history/vault-2026-11-06/` holds the old vault notes word for word: as found, not all rulings confirmed.

## Outside this folder

- Open work: GitHub `richardjlyon/aios-harness` issues labelled `subsidy-clock`; never on the public repository.
- Rulings for the Clock release: `/srv/aios/projects/report-series/clock-alignment/decisions.md`
