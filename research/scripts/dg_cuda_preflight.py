"""Run every frozen neural-DG path briefly on real D0 source data before EXP-340."""

from __future__ import annotations

import argparse
import json
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter

import numpy as np
import torch

from smartvalve.experiments.dg_selection import candidate_grid, candidate_id
from smartvalve.experiments.dg_training import (
    BASELINE_METHODS,
    configuration_record,
    fit_dg_fold,
    predict_dg,
)
from smartvalve.experiments.domain_data import build_cranfield_folds


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    args = parser.parse_args()
    if not args.device.startswith("cuda") or not torch.cuda.is_available():
        raise RuntimeError("formal DG preflight requires CUDA")
    torch.cuda.init()
    fold = build_cranfield_folds()[0]
    results = []
    for method in BASELINE_METHODS:
        config = replace(candidate_grid(method)[0], epochs=3, seed=11)
        torch.cuda.reset_peak_memory_stats(0)
        started = perf_counter()
        fitted = fit_dg_fold(fold, config, device=args.device)
        prediction = predict_dg(fitted, fold.target_features)
        torch.cuda.synchronize(0)
        elapsed = perf_counter() - started
        probability_error = float(
            np.abs(prediction.probabilities.sum(axis=1) - 1.0).max()
        )
        if (
            prediction.logits.shape
            != (len(fold.target_indices), len(fold.label_names))
            or not np.isfinite(prediction.logits).all()
            or
            prediction.probabilities.shape
            != (len(fold.target_indices), len(fold.label_names))
            or not np.isfinite(prediction.probabilities).all()
            or not np.isfinite(prediction.representations).all()
            or probability_error > 1e-6
        ):
            raise ValueError(f"{method} failed the real-fold prediction contract")
        results.append(
            {
                "method": method,
                "candidate_id": candidate_id(config),
                "configuration": configuration_record(config),
                "fit_and_predict_seconds": elapsed,
                "target_rows": len(fold.target_indices),
                "logit_shape": list(prediction.logits.shape),
                "probability_shape": list(prediction.probabilities.shape),
                "representation_shape": list(prediction.representations.shape),
                "maximum_probability_sum_error": probability_error,
                "peak_cuda_memory_bytes": int(torch.cuda.max_memory_allocated(0)),
                "model_state_sha256": fitted.state_sha256,
                "auxiliary_state_sha256": fitted.auxiliary_state_sha256,
                "final_history": fitted.history[-1],
            }
        )
        print(json.dumps(results[-1]), flush=True)
    payload = {
        "schema_version": "smartvalve-dg-cuda-preflight-0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass",
        "purpose": "execution-path preflight; not a performance result",
        "device": args.device,
        "dataset": fold.dataset,
        "fold_id": fold.fold_id,
        "paderborn_archive_contents_opened": False,
        "results": results,
    }
    args.output_directory.mkdir(parents=True, exist_ok=True)
    (args.output_directory / "dg_cuda_preflight.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
