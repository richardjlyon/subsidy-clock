"""Shared test setup.

Release date (Richard, 2 Nov 2026). A changelog entry carries the DEPLOY-DATE placeholder until
Richard sets the release date (the day the new version goes live). The build itself still refuses
the placeholder (sitedata._check_changelog_date), so nothing can be built or deployed undated.

Everyday test runs read the repository's own changelog with a stand-in date, so the placeholder no
longer shows up as failures that hide real ones. The placeholder checks (tests marked `release`)
run at release:

    uv run pytest --release     # also turns the stand-in off: every test sees the real file
"""
from __future__ import annotations

from pathlib import Path

import pytest

from clocksite import results, sitedata

ROOT = Path(__file__).resolve().parent.parent
REPO_CHANGELOG = (ROOT / "changelog.jsonl").resolve()
STAND_IN_DATE = "2099-12-31"


def pytest_addoption(parser):
    parser.addoption("--release", action="store_true",
                     help="release checks: the changelog must carry real dates (no DEPLOY-DATE)")


def pytest_configure(config):
    config.addinivalue_line("markers", "release: runs only with --release (release checks)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--release"):
        return
    skip = pytest.mark.skip(reason="release check: run with --release")
    for item in items:
        if "release" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _repo_changelog_stand_in_date(request, monkeypatch, tmp_path_factory):
    """Outside --release, the repository's own changelog.jsonl is read with the placeholder
    replaced by a stand-in date. Any other file is read as it is, so the guard's own tests
    still see the placeholder rejected."""
    if request.config.getoption("--release"):
        return
    original = sitedata.load_changelog

    def load(path):
        p = Path(path)
        if (p if p.is_absolute() else ROOT / p).resolve() == REPO_CHANGELOG:
            text = REPO_CHANGELOG.read_text(encoding="utf-8")
            if sitedata.CHANGELOG_DATE_PLACEHOLDER in text:
                stand_in = tmp_path_factory.mktemp("changelog") / "changelog.jsonl"
                stand_in.write_text(text.replace(f'"date": "{sitedata.CHANGELOG_DATE_PLACEHOLDER}"',
                                                 f'"date": "{STAND_IN_DATE}"'), encoding="utf-8")
                return original(stand_in)
        return original(path)

    monkeypatch.setattr(sitedata, "load_changelog", load)


@pytest.fixture(scope="session")
def real_results():
    """The model's real results file, as the site reads it: results/clock.json, fetched by
    tools/test.sh (`python -m clocksite fetch-results`) and checked against the pin."""
    path = ROOT / "results" / results.FILE
    if not path.is_file():
        pytest.fail(f"{path} is missing: run `uv run python -m clocksite fetch-results` (tools/test.sh does)")
    return results.read(path, results.load_pin(ROOT))
