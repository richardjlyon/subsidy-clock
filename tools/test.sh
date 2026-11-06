#!/bin/sh
# The standard test run for the Subsidy Clock website: the same on VM 113 and the Mac Mini.
# Sets up the pinned environment (uv.lock), the Playwright browser the share-card tests use,
# and the pinned model results file, then runs the whole suite. Every test must pass: there are no "known failures".
#
#   tools/test.sh             everyday run (the changelog's DEPLOY-DATE is read as a stand-in date)
#   tools/test.sh --release   release run: also fails while any changelog date is DEPLOY-DATE
set -eu
cd "$(dirname "$0")/.."
uv sync --frozen --quiet
uv run --frozen playwright install chromium >/dev/null
# the model's results file the site is built from (pinned: reference/results_pin.yaml); set
# CLOCK_RESULTS_SOURCE to a URL or path of another clock.json (it must still match the pin)
uv run --frozen python -m clocksite fetch-results ${CLOCK_RESULTS_SOURCE:+--source "$CLOCK_RESULTS_SOURCE"} >/dev/null
exec uv run --frozen pytest -q "$@"
