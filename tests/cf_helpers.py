"""Test helper: an engine no-net-zero cost series in the shape reference.load_model_pin returns."""


def cf_series(values: dict[int, float], *, low: dict | None = None, high: dict | None = None,
              version: str = "test") -> dict:
    last = max(values)
    return {"years": dict(values), "low": dict(low or values), "high": dict(high or values),
            "carry_forward_from": last, "carry_index": "CPIH", "rule": "carry by CPIH",
            "method": "test", "source_ids": ["test"], "engine_version": version}


def indexed(base: float, idx: dict[int, float], base_idx: float) -> dict[int, float]:
    """A series equal to the old CPIH-carried scalar baseline, to keep worked examples intact."""
    return {y: base * i / base_idx for y, i in idx.items()}
