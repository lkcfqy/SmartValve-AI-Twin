from __future__ import annotations

import runpy
from pathlib import Path

import numpy as np
from scipy.io import savemat

from smartvalve.data.paderborn_features import SAMPLES_PER_MAIN_SIGNAL

_SCRIPT = runpy.run_path(
    str(Path(__file__).parents[1] / "scripts" / "paderborn_mat_recovery_probe.py")
)
load_with_variable_names = _SCRIPT["load_with_variable_names"]
load_with_split_root = _SCRIPT["load_with_split_root"]


def test_documented_recovery_paths_return_identical_root_structure(tmp_path: Path) -> None:
    path = tmp_path / "N15_M01_F10_KA08_2.mat"
    values = np.arange(SAMPLES_PER_MAIN_SIGNAL, dtype=np.float64)
    root = {
        "Y": [
            {"Name": "vibration_1", "Data": values},
            {"Name": "phase_current_1", "Data": values},
            {"Name": "phase_current_2", "Data": values},
        ]
    }
    savemat(path, {path.stem: root, "unrelated": np.arange(3)})

    direct = load_with_variable_names(path)
    split, variable_names = load_with_split_root(path)

    assert direct == split
    assert set(variable_names) == {path.stem, "unrelated"}
    assert direct["values_or_statistics_emitted"] is False
