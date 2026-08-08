from __future__ import annotations

import numpy as np

from consensus import analyse_consensus


def make_grid(bpm: float, meter: int, bars: int, offset: float = 0.0) -> np.ndarray:
    interval = 60.0 / bpm
    rows = []
    for index in range(bars * meter):
        rows.append((offset + index * interval, (index % meter) + 1))
    return np.asarray(rows, dtype=float)


def main() -> None:
    # Case 1: three models agree on a stable 4/4 performance.
    base = make_grid(120.0, 4, 24)
    case1 = {
        1: base,
        2: base + np.asarray([0.012, 0.0]),
        3: base + np.asarray([-0.009, 0.0]),
    }
    result1 = analyse_consensus(case1)
    assert result1["recommended_model"] in (1, 2, 3)
    assert result1["consensus_meter"] == "4/4"
    assert result1["confidence"] in ("medium", "high")

    # Case 2: Tennessee-Waltz-shaped disagreement. Models 2 and 3 agree exactly
    # on the musical pulse while Model 1 is the tempo outlier. Meter remains
    # unresolved between the surviving 4/4 and 3/4 candidates, so the engine must
    # reject Model 1 and explicitly refuse to invent a meter winner.
    case2 = {
        1: make_grid(130.435, 2, 69),
        2: make_grid(68.182, 4, 40),
        3: make_grid(68.182, 3, 55),
    }
    result2 = analyse_consensus(case2)
    assert result2["confidence"] == "low"
    assert result2["recommended_model"] is None
    assert result2["consensus_meter"] == "AMBIGUOUS"
    assert result2["tempo_family_models"] == [2, 3]
    assert result2["meter_votes"] == {3: 1, 4: 1}

    # Case 3: two models agree closely and a third is shifted well off the beat.
    case3 = {
        1: base,
        2: base + np.asarray([0.015, 0.0]),
        3: base + np.asarray([0.24, 0.0]),
    }
    result3 = analyse_consensus(case3)
    assert result3["recommended_model"] in (1, 2)

    print("BN Con Lab009 consensus self-test: passed")


if __name__ == "__main__":
    main()
