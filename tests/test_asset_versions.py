"""Every local script and stylesheet a page loads carries ?v=<its content hash> (tools/asset_versions.py),
so a changed file is never served from a visitor's cache (2 Nov 2026)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_page_references_its_scripts_and_styles_by_content_hash():
    r = subprocess.run([sys.executable, str(ROOT / "tools" / "asset_versions.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
