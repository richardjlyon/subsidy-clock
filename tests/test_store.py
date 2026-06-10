import json
from datetime import date

import polars as pl

from subsidy_engine.store import SnapshotStore


def df(rows):
    return pl.DataFrame(rows)


def test_write_and_latest_roundtrip(tmp_path):
    store = SnapshotStore(tmp_path)
    d = df([{"date": date(2026, 1, 1), "cost_gbp": 100.0}])
    store.write("cfd", "generation", d, source_url="https://example.org", date_col="date")
    out = store.latest("cfd", "generation")
    assert out.to_dicts() == d.to_dicts()


def test_manifest_provenance(tmp_path):
    store = SnapshotStore(tmp_path)
    d = df([{"date": date(2026, 1, 1), "cost_gbp": 100.0}])
    snap_dir = store.write("cfd", "generation", d, source_url="https://example.org", date_col="date")
    manifest = json.loads((snap_dir / "manifest.json").read_text())
    assert manifest["source_url"] == "https://example.org"
    assert manifest["row_count"] == 1
    assert "retrieved_at" in manifest and "sha256" in manifest


def test_append_only_growth_is_not_a_restatement(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("cfd", "generation", df([{"date": date(2026, 1, 1), "cost_gbp": 100.0}]),
                source_url="u", date_col="date")
    store.write("cfd", "generation", df([{"date": date(2026, 1, 1), "cost_gbp": 100.0},
                                          {"date": date(2026, 1, 2), "cost_gbp": 50.0}]),
                source_url="u", date_col="date")
    assert store.restatements("cfd", "generation") == []


def test_changed_history_is_a_restatement(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("cfd", "generation", df([{"date": date(2026, 1, 1), "cost_gbp": 100.0}]),
                source_url="u", date_col="date")
    store.write("cfd", "generation", df([{"date": date(2026, 1, 1), "cost_gbp": 999.0}]),
                source_url="u", date_col="date")
    events = store.restatements("cfd", "generation")
    assert len(events) == 1
    # both versions still on disk (immutable history)
    versions = list((tmp_path / "raw" / "cfd" / "generation" / "full").iterdir())
    assert len(versions) == 2


def test_partitioned_write_and_read_all(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("constraints", "daily", df([{"date": date(2026, 1, 1), "cost_gbp": 1.0}]),
                source_url="u", partition="2026-01-01")
    store.write("constraints", "daily", df([{"date": date(2026, 1, 2), "cost_gbp": 2.0}]),
                source_url="u", partition="2026-01-02")
    out = store.read_all_partitions("constraints", "daily").sort("date")
    assert out["cost_gbp"].to_list() == [1.0, 2.0]


def test_partition_refetch_with_change_logs_restatement(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("constraints", "daily", df([{"date": date(2026, 1, 1), "cost_gbp": 1.0}]),
                source_url="u", partition="2026-01-01")
    store.write("constraints", "daily", df([{"date": date(2026, 1, 1), "cost_gbp": 9.0}]),
                source_url="u", partition="2026-01-01")
    assert len(store.restatements("constraints", "daily")) == 1
    # read_all_partitions returns the latest version of the partition
    assert store.read_all_partitions("constraints", "daily")["cost_gbp"].to_list() == [9.0]


def test_freshness_reports_latest_manifest(tmp_path):
    store = SnapshotStore(tmp_path)
    store.write("cfd", "generation", df([{"date": date(2026, 1, 1), "cost_gbp": 1.0}]),
                source_url="u", date_col="date")
    fresh = store.freshness("cfd", "generation")
    assert fresh["row_count"] == 1
    assert "retrieved_at" in fresh


def test_latest_missing_table_returns_none(tmp_path):
    store = SnapshotStore(tmp_path)
    assert store.latest("nope", "nothing") is None
    assert store.freshness("nope", "nothing") is None
