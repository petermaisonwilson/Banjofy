from __future__ import annotations

import numpy as np

from consensus import analyse_consensus


def make_grid(bpm: float, meter: int, bars: int, offset: float = 0.0) -> np.ndarray:
    interval = 60.0 / bpm
    rows = []
    for index in range(bars * meter):
        rows.append((offset + index * interval, (index % meter) + 1))
    return np.asarray(rows, dtype=float)


def shift_opening_downbeats(data: np.ndarray, bars: int, shift_s: float) -> np.ndarray:
    out = data.copy()
    numbers = np.rint(out[:, 1]).astype(int)
    downbeat_indices = np.flatnonzero(numbers == 1)[:bars]
    out[downbeat_indices, 0] += shift_s
    out = out[np.argsort(out[:, 0])]
    return out


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

    # Case 2: Tennessee-Waltz-shaped tempo disagreement. Models 2 and 3 agree on
    # tempo while Model 1 is the outlier. With no extra audio evidence, 4/4 vs 3/4
    # must remain unresolved.
    case2 = {
        1: make_grid(130.435, 2, 69),
        2: make_grid(68.182, 4, 40),
        3: make_grid(68.182, 3, 55),
    }
    result2 = analyse_consensus(case2)
    assert result2["recommended_model"] is None
    assert result2["consensus_meter"] == "AMBIGUOUS"
    assert result2["tempo_family_models"] == [2, 3]
    assert result2["meter_votes"] == {3: 1, 4: 1}
    assert result2["meter_resolution"] == "ambiguous"

    # Case 3: two models agree closely and a third is shifted well off the beat.
    case3 = {
        1: base,
        2: base + np.asarray([0.015, 0.0]),
        3: base + np.asarray([0.24, 0.0]),
    }
    result3 = analyse_consensus(case3)
    assert result3["recommended_model"] in (1, 2)

    # Case 4: same tied meter situation, but independent source-audio analysis says
    # Model 3's proposed Beat-1 positions are materially more accented. Only then is
    # the tie allowed to resolve to 3/4.
    result4 = analyse_consensus(case2, meter_accent_scores={2: 0.51, 3: 0.62})
    assert result4["recommended_model"] == 3
    assert result4["consensus_meter"] == "3/4"
    assert result4["meter_resolution"] == "audio_accent"
    assert result4["confidence"] == "medium"

    # Case 5: a tiny accent advantage is not enough to manufacture certainty.
    result5 = analyse_consensus(case2, meter_accent_scores={2: 0.54, 3: 0.56})
    assert result5["recommended_model"] is None
    assert result5["consensus_meter"] == "AMBIGUOUS"

    # Case 6: all models agree on tempo/meter and become identical later, but Models
    # 2 and 3 have phase-shifted downbeats in their first four bars. The model that is
    # locked from the beginning must win even though whole-song agreement is similar.
    long_base = make_grid(136.364, 4, 48)
    case6 = {
        1: long_base,
        2: shift_opening_downbeats(long_base, 4, 0.42),
        3: shift_opening_downbeats(long_base, 4, 0.36),
    }
    result6 = analyse_consensus(case6, meter_accent_scores={1: 0.52, 2: 0.53, 3: 0.52})
    assert result6["recommended_model"] == 1
    assert result6["consensus_meter"] == "4/4"
    assert result6["startup_lock_scores"]["1"] > result6["startup_lock_scores"]["2"]
    assert result6["startup_lock_scores"]["1"] > result6["startup_lock_scores"]["3"]

    print("BN Con Lab009 consensus self-test: passed")


if __name__ == "__main__":
    main()
