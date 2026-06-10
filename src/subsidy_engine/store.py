"""Versioned Parquet snapshot store with provenance (spec F-4) and
restatement logging (spec F-5). Nothing is ever deleted."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import polars as pl


def _canonical_hash(df: pl.DataFrame) -> str:
    canon = df.sort(by=df.columns) if df.height else df
    return hashlib.sha256(canon.write_csv().encode()).hexdigest()


class SnapshotStore:
    def __init__(self, root: Path | str):
        self.root = Path(root)

    def _partition_dir(self, scheme: str, table: str, partition: str) -> Path:
        return self.root / "raw" / scheme / table / partition

    def _versions(self, scheme: str, table: str, partition: str) -> list[Path]:
        pdir = self._partition_dir(scheme, table, partition)
        if not pdir.is_dir():
            return []
        return sorted(p for p in pdir.iterdir() if (p / "manifest.json").is_file())

    def write(
        self,
        scheme: str,
        table: str,
        df: pl.DataFrame,
        *,
        source_url: str,
        partition: str = "full",
        date_col: str | None = None,
        source_date: str | None = None,
    ) -> Path:
        retrieved_at = datetime.now(timezone.utc)
        prev = self._versions(scheme, table, partition)
        version = retrieved_at.strftime("%Y%m%dT%H%M%S.%f")
        snap_dir = self._partition_dir(scheme, table, partition) / version
        while snap_dir.exists():  # same-microsecond collision in tests
            time.sleep(0.001)
            version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%f")
            snap_dir = self._partition_dir(scheme, table, partition) / version
        snap_dir.mkdir(parents=True)
        df.write_parquet(snap_dir / "data.parquet")
        manifest = {
            "scheme": scheme,
            "table": table,
            "partition": partition,
            "source_url": source_url,
            "source_date": source_date,
            "retrieved_at": retrieved_at.isoformat(),
            "row_count": df.height,
            "sha256": _canonical_hash(df),
        }
        (snap_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
        if prev:
            self._check_restatement(scheme, table, prev[-1], snap_dir, df, date_col, manifest)
        return snap_dir

    def _check_restatement(
        self,
        scheme: str,
        table: str,
        prev_dir: Path,
        new_dir: Path,
        new_df: pl.DataFrame,
        date_col: str | None,
        manifest: dict,
    ) -> None:
        prev_df = pl.read_parquet(prev_dir / "data.parquet")
        if date_col is not None and date_col in prev_df.columns and prev_df.height:
            # Full-snapshot mode: growth is expected; only compare overlap.
            cutoff = prev_df[date_col].max()
            new_overlap = new_df.filter(pl.col(date_col) <= cutoff)
            changed = _canonical_hash(new_overlap) != _canonical_hash(prev_df)
        else:
            changed = _canonical_hash(new_df) != _canonical_hash(prev_df)
        if changed:
            event = {
                "detected_at": manifest["retrieved_at"],
                "partition": manifest["partition"],
                "previous_version": prev_dir.name,
                "new_version": new_dir.name,
            }
            log = self.root / "raw" / scheme / table / "restatements.jsonl"
            with log.open("a") as fh:
                fh.write(json.dumps(event) + "\n")

    def restatements(self, scheme: str, table: str) -> list[dict]:
        log = self.root / "raw" / scheme / table / "restatements.jsonl"
        if not log.is_file():
            return []
        return [json.loads(line) for line in log.read_text().splitlines() if line.strip()]

    def latest(self, scheme: str, table: str, partition: str = "full") -> pl.DataFrame | None:
        versions = self._versions(scheme, table, partition)
        if not versions:
            return None
        return pl.read_parquet(versions[-1] / "data.parquet")

    def read_all_partitions(self, scheme: str, table: str) -> pl.DataFrame | None:
        tdir = self.root / "raw" / scheme / table
        if not tdir.is_dir():
            return None
        frames = []
        for pdir in sorted(p for p in tdir.iterdir() if p.is_dir()):
            versions = self._versions(scheme, table, pdir.name)
            if versions:
                frames.append(pl.read_parquet(versions[-1] / "data.parquet"))
        if not frames:
            return None
        return pl.concat(frames)

    def freshness(self, scheme: str, table: str) -> dict | None:
        tdir = self.root / "raw" / scheme / table
        if not tdir.is_dir():
            return None
        manifests = []
        for pdir in (p for p in tdir.iterdir() if p.is_dir()):
            versions = self._versions(scheme, table, pdir.name)
            if versions:
                manifests.append(json.loads((versions[-1] / "manifest.json").read_text()))
        if not manifests:
            return None
        return max(manifests, key=lambda m: m["retrieved_at"])
