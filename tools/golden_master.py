"""Golden-master guard for the site build.

Compares the built site against a captured master. Run before and after any
data or engine change: a data change SHOULD diff, and the diff is the evidence
that the change did what was intended and nothing else.

Why not a byte-diff? Proven 2026-07-15: polars' multi-threaded group_by sums are
non-deterministic in the last float digits — two consecutive builds of UNCHANGED
code differ in breakdown.json. POLARS_MAX_THREADS=1 removes almost all of it,
but a cold-page-cache build still shifted one file once. So: everything non-float
is compared EXACTLY (keys, order, strings, structure); floats are compared with a
1e-9 relative tolerance (~2e-7 pounds on the 227bn total). Any real bug moves a
figure by orders of magnitude more than that.

Usage (from the repo root):
    uv run python tools/golden_master.py capture   # re-baseline
    uv run python tools/golden_master.py check     # compare

`check` leaves the rebuilt site/ in the working tree; `git restore -- site/` if
you did not intend to keep it (site/data is bot-owned — see .githooks/pre-commit).

History: revived 2026-09-01. The only copy lived in ~/Archive with a hardcoded
REPO path to /Users/rjl/Code/web-subsidy-clock, deleted in the AIOS migration —
so the guard the openspec change docs cite as a gate could not run at all. Now
in-repo and path-relative.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GM = Path(__file__).resolve().parent / "golden"
RELTOL = 1e-9

TS = re.compile(r"\d{4}-\d{2}-\d{2}T[\d:.]+\+00:00")
# Fixed 2026-07-15: TS only ever matched the ISO form, so JSON passed (generated_at
# is also in IGNORE_KEYS) while EVERY CSV false-FAILed as soon as the clock minute
# rolled past the capture. The original "PASS 3/3 on unmodified code" was three runs
# inside one minute. Two further now()-derived stamps need pinning, both PURE
# reformats of generated_at (= datetime.now(timezone.utc)) and so carrying no
# data-derived signal:
#   sitedata.py  _attribution() -> "generated 2026-07-10 08:50 UTC" in every CSV
#   sitedata.py  asof           -> "10 July 2026" in site/embed/widget.html
# Pinned narrowly (not a blanket date-pin) so a real figure change still fails the
# text compare.
CSV_TS = re.compile(r"generated \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")
ASOF = re.compile(r'(id="asof">)[^<]*(<)')
IGNORE_KEYS = {"generated_at", "generated"}


def pin(text: str) -> str:
    """Replace clock-derived stamps with a constant so text compares are time-invariant."""
    text = TS.sub("PINNED", text)
    text = CSV_TS.sub("generated PINNED", text)
    return ASOF.sub(r"\1PINNED\2", text)


def _env() -> dict:
    # POLARS_MAX_THREADS=1: multi-threaded group_by sums are non-deterministic
    # (last float digits). PYTHONDONTWRITEBYTECODE + __pycache__ purge: proven
    # 2026-07-15 that a same-size, same-second edit leaves a STALE .pyc and python
    # silently runs code that is not on disk (money.py read 86400 while the
    # interpreter loaded 86401). Fatal for a guard — so never cache.
    return dict(os.environ, POLARS_MAX_THREADS="1", PYTHONDONTWRITEBYTECODE="1")


def build() -> None:
    for pc in REPO.rglob("__pycache__"):
        if ".venv" not in str(pc):
            shutil.rmtree(pc, ignore_errors=True)
    r = subprocess.run(["uv", "run", "python", "-m", "subsidy_engine", "build-site"],
                       cwd=REPO, env=_env(), capture_output=True, text=True)
    if r.returncode != 0:
        print("BUILD FAILED:\n" + r.stderr[-2000:])
        sys.exit(2)


def snapshot() -> dict:
    snap: dict[str, tuple[str, object]] = {}
    data = REPO / "site" / "data"
    for f in sorted(data.rglob("*.json")):
        snap[str(f.relative_to(data))] = ("json", json.loads(f.read_text()))
    for f in sorted(data.rglob("*.csv")):
        snap[str(f.relative_to(data))] = ("text", pin(f.read_text()))
    w = REPO / "site" / "embed" / "widget.html"
    snap[w.name] = ("text", pin(w.read_text()))
    # Share-card TEXT layer (stubs, cards.json manifest, composed card HTML,
    # chart SVG) — the surface site/data alone does not cover. Produced by
    # tools/sharecard_text.py without Playwright/PNG rendering; asof is pinned at
    # source (literal 'PINNED'), so no regex pinning is needed here.
    r = subprocess.run(["uv", "run", "python", str(Path(__file__).parent / "sharecard_text.py")],
                       cwd=REPO, env=_env(), capture_output=True, text=True)
    if r.returncode != 0:
        print("SHARECARD TEXT FAILED:\n" + r.stderr[-2000:])
        sys.exit(2)
    for k, v in json.loads(r.stdout).items():
        snap[f"cards:{k}"] = ("text", v)
    return snap


def diff(a, b, path=""):
    """Yield human-readable differences between two JSON values."""
    if isinstance(a, dict) and isinstance(b, dict):
        if list(a.keys()) != list(b.keys()):
            yield f"{path}: KEYS differ\n    master : {list(a.keys())}\n    current: {list(b.keys())}"
            return
        for k in a:
            if k in IGNORE_KEYS:
                continue
            yield from diff(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            yield f"{path}: LENGTH {len(a)} -> {len(b)}"
            return
        for i, (x, y) in enumerate(zip(a, b)):
            yield from diff(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        if a is None or b is None or a != a or b != b:
            if repr(a) != repr(b):
                yield f"{path}: {a!r} -> {b!r}"
            return
        d = abs(a - b)
        rel = d / abs(a) if a else d
        if rel > RELTOL:
            yield f"{path}: {a!r} -> {b!r}  (rel {rel:.2e}, abs {d:.6f})"
    else:
        if a != b:
            yield f"{path}: {a!r} -> {b!r}"


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    build()
    snap = snapshot()
    GM.mkdir(parents=True, exist_ok=True)
    master_file = GM / "master.json"
    if mode == "capture":
        master_file.write_text(json.dumps(snap))
        print(f"captured {len(snap)} files -> {master_file}")
        return 0
    if not master_file.exists():
        print(f"GOLDEN MASTER: no master at {master_file} — run `capture` first.")
        return 2
    master = json.loads(master_file.read_text())
    if set(master) != set(snap):
        print("GOLDEN MASTER: FAIL — file set changed\n"
              f"  missing: {set(master) - set(snap)}\n  extra: {set(snap) - set(master)}")
        return 1
    problems = []
    for name in sorted(master):
        kind, mval = master[name]
        _, cval = snap[name]
        if kind == "text":
            if mval != cval:
                problems.append(f"{name}: text differs")
        else:
            problems.extend(diff(mval, cval, name))
    if problems:
        print(f"GOLDEN MASTER: FAIL — {len(problems)} difference(s) beyond rel tol {RELTOL:g}:")
        for p in problems[:25]:
            print("  " + p)
        if len(problems) > 25:
            print(f"  ... and {len(problems) - 25} more")
        return 1
    print(f"GOLDEN MASTER: PASS — {len(snap)} files match "
          f"(structure/strings exact; floats within rel {RELTOL:g})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
