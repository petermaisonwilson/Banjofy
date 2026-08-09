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
    base = make_grid(120.0, 4, 24)
    case1 = {
        1: base,
        2: base + np.asarray([0.012, 0.0]),
        3: base + np.asarray([-0.009, 0.0]),
    }
    result1 = analyse_consensus(case1)
    assert result1["recommended_model"] in (1, 2, 3)
    assert result1["consensus_meter"] == "4/4"

    case2 = {
        1: make_grid(130.435, 2, 69),
        2: make_grid(68.182, 4, 40),
        3: make_grid(68.182, 3, 55),
    }
    result2 = analyse_consensus(case2)
    assert result2["recommended_model"] is None
    assert result2["consensus_meter"] == "AMBIGUOUS"
    assert result2["tempo_family_models"] == [2, 3]

    result4 = analyse_consensus(case2, meter_accent_scores={2: 0.51, 3: 0.62})
    assert result4["recommended_model"] == 3
    assert result4["consensus_meter"] == "3/4"
    assert result4["meter_resolution"] == "audio_accent"

    result5 = analyse_consensus(case2, meter_accent_scores={2: 0.54, 3: 0.56})
    assert result5["recommended_model"] is None

    # AC/DC-shaped selection case: same tempo/meter, all good later, but Model 1 is
    # ready from the start while Models 2 and 3 have poor acquisition. Startup audio
    # is supplied independently from the source audio and should break the near tie.
    long_base = make_grid(136.364, 4, 48)
    case6 = {
        1: long_base,
        2: shift_opening_downbeats(long_base, 4, 0.42),
        3: shift_opening_downbeats(long_base, 4, 0.36),
    }
    result6 = analyse_consensus(
        case6,
        meter_accent_scores={1: 0.518, 2: 0.527, 3: 0.520},
        startup_audio_scores={1: 0.92, 2: 0.68, 3: 0.72},
    )
    assert result6["recommended_model"] == 1
    assert result6["consensus_meter"] == "4/4"
    assert result6["selection_reason"] in ("overall_score", "startup_tiebreak")
    assert result6["startup_audio_scores"]["1"] > result6["startup_audio_scores"]["2"]
    assert result6["startup_audio_scores"]["1"] > result6["startup_audio_scores"]["3"]
    by_model = {item["model"]: item for item in result6["models"]}
    assert by_model[1]["startup_quality"] > by_model[2]["startup_quality"]
    assert by_model[1]["startup_quality"] > by_model[3]["startup_quality"]

    print("BN Con Lab009 consensus self-test: passed")


if __name__ == "__main__":
    main()
