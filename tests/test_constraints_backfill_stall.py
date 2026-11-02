"""The backward constraints backfill must not stall silently (t_17a1158f, 19 Oct 2026).

Since the fix 5 guard, a day on which Elexon returns no bids in any settlement period is
not stored. The daily workflow (update.yml, "Extend constraints history backwards") asks
for the 7 days before the earliest stored day. If Elexon answers none of the 7, nothing is
stored, the earliest stored day does not move, and the next run asks for the same window.
These tests drive that step with an Elexon stub (no network) that returns nothing.
"""
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from subsidy_engine import __main__ as entry
from subsidy_engine.store import SnapshotStore
from subsidy_engine_uk import elexon

EARLIEST = date(2023, 8, 18)


def _seed(root: Path) -> SnapshotStore:
    store = SnapshotStore(root / "data")
    store.write("constraints", "daily",
                pl.DataFrame({"date": [EARLIEST], "bmu": ["T_W-1"], "lead_party": ["W"],
                              "volume_mwh": [-1.0], "cost_gbp": [1.0e6]}),
                source_url="u", partition=EARLIEST.isoformat())
    return store


def _silent_elexon(monkeypatch, asked: list[str]):
    def get_json(path, client):
        asked.append(path)
        return {"data": []}
    monkeypatch.setattr(elexon, "get_json", get_json)
    monkeypatch.setattr(elexon, "wind_bmu_map", lambda client: {"T_W-1": "W"})


def _workflow_window(store: SnapshotStore) -> tuple[str, str]:
    # update.yml: EARLIEST = first stored partition; START = EARLIEST - 7; END = EARLIEST - 1
    earliest = date.fromisoformat(sorted(store.partitions("constraints", "daily"))[0])
    return ((earliest - timedelta(days=7)).isoformat(),
            (earliest - timedelta(days=1)).isoformat())


def _daily_run(root: Path, store: SnapshotStore) -> tuple[tuple[str, str], int]:
    start, end = _workflow_window(store)
    rc = entry.main(["--root", str(root), "backfill-constraints",
                     "--start", start, "--end", end])
    return (start, end), rc


def test_an_empty_elexon_week_asks_for_the_same_window_on_every_run(tmp_path, monkeypatch):
    # reproduces the stall itself: passes on master, and must keep passing (the fix reports
    # the stall; it does not skip the window or store invented zero days)
    asked: list[str] = []
    _silent_elexon(monkeypatch, asked)
    store = _seed(tmp_path)
    first, _ = _daily_run(tmp_path, store)
    second, _ = _daily_run(tmp_path, store)
    assert first == second == ("2023-08-11", "2023-08-17")
    assert store.partitions("constraints", "daily") == [EARLIEST.isoformat()]
    assert len(asked) == 2 * 7 * 50  # every period of every day, asked twice


def test_an_empty_elexon_week_is_reported_naming_the_window(tmp_path, monkeypatch, capsys):
    # red on origin/master e54d1dfe: the command prints nothing and returns 0
    _silent_elexon(monkeypatch, [])
    store = _seed(tmp_path)
    _daily_run(tmp_path, store)
    out = capsys.readouterr()
    said = out.out + out.err
    assert "2023-08-11" in said and "2023-08-17" in said
    assert "no bids" in said.lower()


# ---- 0176 option C, built (aios-harness#57; Richard, 23 Oct and 2 Nov 2026) ----

def test_a_stalled_week_exits_with_the_stall_code(tmp_path, monkeypatch):
    """The command exits 3 on an empty week so the daily workflow can build, deploy and then turn red."""
    _silent_elexon(monkeypatch, [])
    _, rc = _daily_run(tmp_path, _seed(tmp_path))
    assert rc == entry_stall_code()


def entry_stall_code():
    from subsidy_engine_uk import cli
    return cli.BACKFILL_STALLED


def test_nothing_is_asked_before_elexons_first_day(tmp_path, monkeypatch, capsys):
    """Elexon's settlement stack starts on 6 Nov 2015 (checked against the API, 2 Nov 2026). A window wholly
    before it asks nothing and is not a stall; a window across it is cut to start there."""
    asked: list[str] = []
    _silent_elexon(monkeypatch, asked)
    rc = entry.main(["--root", str(tmp_path), "backfill-constraints",
                     "--start", "2015-10-25", "--end", "2015-10-31"])
    assert rc == 0 and asked == []
    assert "6 November 2015" in capsys.readouterr().out
    assert elexon.STACK_FIRST_DAY == date(2015, 11, 6)
    entry.main(["--root", str(tmp_path), "backfill-constraints",
                "--start", "2015-11-01", "--end", "2015-11-07"])
    days = {p.split("/")[-2] for p in asked}
    assert days == {"2015-11-06", "2015-11-07"}
