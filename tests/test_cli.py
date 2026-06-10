import subprocess
import sys


def test_cli_help():
    out = subprocess.run(
        [sys.executable, "-m", "subsidy_engine", "--help"],
        capture_output=True, text=True,
    )
    assert out.returncode == 0
    for cmd in ("update", "backfill-constraints", "build-site"):
        assert cmd in out.stdout
