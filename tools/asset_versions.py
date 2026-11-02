"""Stamp every local script and stylesheet reference in site/ with ?v=<content hash>.

Browsers keep site scripts and stylesheets for hours. A reference whose ?v= is the file's own content hash
gets a new address whenever the file changes, so visitors always load the current file (2 Nov 2026: the
hand-kept app.js?v= token was not updated, and visitors saw the old clock). Vendored files keep their
pinned ?v=<version>.

    uv run python tools/asset_versions.py           # rewrite the pages
    uv run python tools/asset_versions.py --check   # exit 1 if any reference is stale (tests run this)
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
REF = re.compile(r'((?:src|href)=")([^"#:?]+\.(?:js|css))(\?v=[^"]*)?(")')


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def _target(page: Path, ref: str) -> Path:
    return (SITE / ref.lstrip("/")) if ref.startswith("/") else (page.parent / ref)


def stamp(page: Path) -> tuple[str, list[str]]:
    """The page with every local reference stamped, and the references that were stale."""
    text = page.read_text()
    stale: list[str] = []

    def sub(m: re.Match) -> str:
        ref = m.group(2)
        if "assets/vendor/" in ref:
            return m.group(0)
        target = _target(page, ref)
        if not target.is_file():
            raise FileNotFoundError(f"{page.relative_to(SITE)}: {ref} does not exist")
        want = f"?v={_hash(target)}"
        if (m.group(3) or "") != want:
            stale.append(ref)
        return f"{m.group(1)}{ref}{want}{m.group(4)}"

    return REF.sub(sub, text), stale


def pages() -> list[Path]:
    # share stubs carry no assets; frozen papers (site/papers) must stay byte-for-byte as published
    return sorted(p for p in SITE.rglob("*.html")
                  if "/s/" not in p.as_posix() and "/papers/" not in p.as_posix())


def main(argv: list[str]) -> int:
    check = "--check" in argv
    bad = []
    for page in pages():
        new, stale = stamp(page)
        if stale:
            bad.append(f"{page.relative_to(SITE)}: {', '.join(sorted(set(stale)))}")
            if not check:
                page.write_text(new)
    if check and bad:
        print("stale ?v= on:\n  " + "\n  ".join(bad) + "\nrun: uv run python tools/asset_versions.py")
        return 1
    if not check:
        print(f"stamped {len(bad)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
