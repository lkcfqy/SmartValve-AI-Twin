from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from smartvalve.experiments.recorded_run import (
    _replace_run_directory,
    _safe_slug,
    run_recorded_experiment,
)


def test_safe_slug_and_run_directory_replacement(tmp_path: Path) -> None:
    assert _safe_slug("Cranfield: baseline / seed 42") == "cranfield-baseline-seed-42"
    assert _replace_run_directory(("tool", "{run_dir}/out"), tmp_path) == [
        "tool",
        f"{tmp_path}/out",
    ]


def test_recorded_experiment_preserves_success_evidence(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    source_root.mkdir()
    (source_root / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    script = (
        "from pathlib import Path; import sys; "
        "Path(sys.argv[1]).write_text('result', encoding='utf-8'); print('completed')"
    )
    exit_code, run_directory = run_recorded_experiment(
        experiment_id="EXP-TEST-OK",
        name="successful run",
        description="exercise the provenance recorder",
        command=(sys.executable, "-c", script, "{run_dir}/outputs/result.txt"),
        output_root=tmp_path / "runs",
        root=source_root,
    )

    assert exit_code == 0
    assert (run_directory / "stdout.log").read_text(encoding="utf-8") == "completed\n"
    assert (run_directory / "outputs" / "result.txt").read_text(encoding="utf-8") == "result"
    metadata = json.loads((run_directory / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "complete"
    assert metadata["exit_code"] == 0
    assert any(item["path"] == "outputs/result.txt" for item in metadata["output_files"])
    assert metadata["repository"]["source_fingerprint"]["file_count"] > 0
    assert metadata["repository"]["source_fingerprint"]["discovery"] == "filesystem_fallback"
    assert metadata["repository"]["commit"] is None
    assert metadata["repository"]["branch"] is None


def test_recorded_experiment_retains_failed_run(tmp_path: Path) -> None:
    exit_code, run_directory = run_recorded_experiment(
        experiment_id="EXP-TEST-FAIL",
        name="failed run",
        description="a failed command must still have evidence",
        command=(sys.executable, "-c", "raise SystemExit(7)"),
        output_root=tmp_path,
    )

    assert exit_code == 7
    metadata = json.loads((run_directory / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["status"] == "failed"
    assert metadata["exit_code"] == 7


def test_recorded_experiment_rejects_invalid_id(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="experiment ID"):
        run_recorded_experiment(
            experiment_id="bad id",
            name="invalid",
            description="invalid ID",
            command=(sys.executable, "-c", "print('never')"),
            output_root=tmp_path,
        )
