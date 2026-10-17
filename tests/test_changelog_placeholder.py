"""Guard: the DEPLOY-DATE placeholder must never be merged, built or deployed.

The REF-removal changelog entry carries the date placeholder DEPLOY-DATE until
Richard approves the release; the real date goes in as the last commit. These
tests are RED while the placeholder is in, on purpose: the branch cannot be
merged or built by accident.
"""
import json
from pathlib import Path

import pytest

from subsidy_engine import sitedata

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "DEPLOY-DATE"


@pytest.mark.parametrize("rel", ["changelog.jsonl",
                                 "site/data/changelog.json",
                                 "site/data/changelog.csv"])
def test_no_deploy_date_placeholder_in_changelog(rel):
    p = ROOT / rel
    if not p.is_file():
        pytest.skip(f"{rel} not present")
    assert PLACEHOLDER not in p.read_text(encoding="utf-8"), (
        f"{rel} still contains the {PLACEHOLDER} placeholder; "
        "put the real date in before merging")


def _entry(date):
    return json.dumps({"date": date, "kind": "change", "figure": "x",
                       "figure_label": "X", "was": "a", "now": "b",
                       "cause": ["c"]})


def test_load_changelog_rejects_placeholder_date(tmp_path):
    p = tmp_path / "changelog.jsonl"
    p.write_text(_entry(PLACEHOLDER) + "\n")
    with pytest.raises(ValueError, match="changelog entry has placeholder date "
                                         "DEPLOY-DATE; put the real date in before merging"):
        sitedata.load_changelog(p)


@pytest.mark.parametrize("bad", ["17 Oct 2026", "2026-13-01", "2026-10-1", "TBC"])
def test_load_changelog_rejects_non_iso_date(tmp_path, bad):
    p = tmp_path / "changelog.jsonl"
    p.write_text(_entry(bad) + "\n")
    with pytest.raises(ValueError, match="date"):
        sitedata.load_changelog(p)


def test_load_changelog_accepts_iso_date(tmp_path):
    p = tmp_path / "changelog.jsonl"
    p.write_text(_entry("2026-10-17") + "\n")
    assert sitedata.load_changelog(p)[0]["date"] == "2026-10-17"
