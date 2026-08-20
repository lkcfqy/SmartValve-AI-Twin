#!/usr/bin/env python3
"""Run the frozen Knap-style raw/FFT/STFT Paderborn protocol sensitivity."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from pathlib import Path
from typing import Any

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset

from smartvalve.experiments.paderborn_domain import validate_paderborn_feature_frame
from smartvalve.experiments.paderborn_partitions import PADERBORN_LABELS
from smartvalve.experiments.paderborn_protocol_contrast import (
    PROBABILITY_COLUMNS,
    attach_common_cells,
    build_protocol_splits,
    ensemble_seed_predictions,
    score_oof_predictions,
)
from smartvalve.experiments.paderborn_raw_sensitivity import (
    BATCH_SIZE,
    EPOCHS,
    RAW_MODELS,
    RAW_PROTOCOLS,
    RAW_SEEDS,
    RAW_SENSITIVITY_VERSION,
    WINDOW_SIZE,
    WINDOWS_PER_RECORD,
    aggregate_raw_window_predictions,
    build_raw_sensitivity_model,
    paired_raw_protocol_bootstrap,
    raw_sensitivity_gate,
)

RUN_VERSION = f"{RAW_SENSITIVITY_VERSION}-training-0.1.0"
BOOTSTRAP_DRAWS = 2_000


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected: str, role: str) -> str:
    if not path.is_file():
        raise FileNotFoundError(path)
    observed = _sha256(path)
    if observed != expected:
        raise ValueError(f"{role} SHA-256 changed: expected {expected}, observed {observed}")
    return observed


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, frame: pd.DataFrame) -> None:
    frame.to_csv(path, index=False, float_format="%.12g")


def _state_sha256(model: nn.Module) -> str:
    digest = hashlib.sha256()
    for name, tensor in sorted(model.state_dict().items()):
        digest.update(name.encode("utf-8"))
        values = tensor.detach().cpu().contiguous().numpy()
        digest.update(str(values.dtype).encode("utf-8"))
        digest.update(np.asarray(values.shape, dtype=np.int64).tobytes())
        digest.update(values.tobytes())
    return digest.hexdigest()


def _seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    torch.use_deterministic_algorithms(True)


class RawWindowDataset(Dataset[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]):
    """Lazy memory-mapped view with per-window standardization."""

    def __init__(
        self,
        window_path: Path,
        rows: pd.DataFrame,
        labels: np.ndarray,
    ) -> None:
        self.windows = np.load(window_path, mmap_mode="r")
        self.window_rows = rows["window_row_index"].to_numpy(dtype=np.int64)
        self.labels = np.asarray(labels, dtype=np.int64)
        if len(self.window_rows) != len(self.labels):
            raise ValueError("raw sensitivity window rows and labels differ")

    def __len__(self) -> int:
        return len(self.window_rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        values = np.asarray(self.windows[self.window_rows[index]], dtype=np.float32).copy()
        values -= values.mean(dtype=np.float64)
        values /= values.std(dtype=np.float64) + 1e-8
        return (
            torch.from_numpy(values[None, :]),
            torch.tensor(self.labels[index], dtype=torch.long),
            torch.tensor(self.window_rows[index], dtype=torch.long),
        )


def _loader(
    dataset: RawWindowDataset,
    *,
    shuffle: bool,
    seed: int,
    batch_size: int,
) -> DataLoader[tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    generator = torch.Generator()
    generator.manual_seed(seed)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0,
        pin_memory=True,
        generator=generator,
    )


def _fit_predict(
    *,
    model_name: str,
    seed: int,
    train_dataset: RawWindowDataset,
    target_dataset: RawWindowDataset,
    device: torch.device,
    epochs: int,
    batch_size: int,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any], dict[str, Any]]:
    _seed_everything(seed)
    if device.type == "cuda":
        torch.cuda.init()
        torch.cuda.reset_peak_memory_stats(device)
    model = build_raw_sensitivity_model(model_name).to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=0.001,
        weight_decay=0.0001,
    )
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=0.5,
        patience=3,
    )
    criterion = nn.CrossEntropyLoss()
    train_loader = _loader(
        train_dataset,
        shuffle=True,
        seed=seed,
        batch_size=batch_size,
    )
    started = time.perf_counter()
    epoch_trace = []
    for epoch in range(1, epochs + 1):
        model.train()
        loss_total = 0.0
        example_count = 0
        for inputs, labels, _ in train_loader:
            inputs = inputs.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            logits = model(inputs)
            loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            optimizer.step()
            loss_total += float(loss.detach().cpu()) * len(labels)
            example_count += len(labels)
        mean_loss = loss_total / example_count
        scheduler.step(mean_loss)
        epoch_trace.append(
            {
                "epoch": epoch,
                "source_training_loss": mean_loss,
                "learning_rate": float(optimizer.param_groups[0]["lr"]),
            }
        )

    target_loader = _loader(
        target_dataset,
        shuffle=False,
        seed=seed,
        batch_size=batch_size,
    )
    model.eval()
    probability_blocks = []
    window_rows = []
    with torch.no_grad():
        for inputs, _, batch_window_rows in target_loader:
            logits = model(inputs.to(device, non_blocking=True))
            probability_blocks.append(torch.softmax(logits, dim=1).cpu().numpy())
            window_rows.append(batch_window_rows.numpy())
    duration = time.perf_counter() - started
    probabilities = np.concatenate(probability_blocks).astype(np.float64, copy=False)
    target_window_rows = np.concatenate(window_rows).astype(np.int64, copy=False)
    diagnostics = {
        "duration_seconds": duration,
        "parameter_count": sum(parameter.numel() for parameter in model.parameters()),
        "model_state_sha256": _state_sha256(model),
        "peak_cuda_memory_bytes": (
            int(torch.cuda.max_memory_allocated(device)) if device.type == "cuda" else 0
        ),
    }
    trace = {
        "model": model_name,
        "seed": seed,
        "epochs": epoch_trace,
    }
    del model, optimizer, scheduler
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return probabilities, target_window_rows, diagnostics, trace


def run_sensitivity(
    *,
    raw_window_directory: Path,
    raw_window_summary_sha256: str,
    features_path: Path,
    features_sha256: str,
    seal_path: Path,
    seal_sha256: str,
    output_directory: Path,
    device_name: str,
    epochs: int,
    batch_size: int,
    bootstrap_draws: int,
) -> dict[str, Any]:
    """Fit the frozen two-protocol, three-architecture, three-seed family."""

    if (epochs, batch_size, bootstrap_draws) != (EPOCHS, BATCH_SIZE, BOOTSTRAP_DRAWS):
        raise ValueError("raw sensitivity runtime changes a frozen design constant")
    _verify(seal_path, seal_sha256, "raw sensitivity seal")
    summary_path = raw_window_directory / "raw_window_summary.json"
    _verify(summary_path, raw_window_summary_sha256, "raw window summary")
    raw_summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if raw_summary.get("status") != "complete_hash_locked_paderborn_raw_window_artifact":
        raise ValueError("raw sensitivity window artifact is incomplete")
    for filename, expected in raw_summary.get("output_sha256", {}).items():
        _verify(raw_window_directory / filename, str(expected), f"raw window {filename}")
    _verify(features_path, features_sha256, "Paderborn primary feature matrix")
    frame = attach_common_cells(pd.read_parquet(features_path).reset_index(drop=True))
    validate_paderborn_feature_frame(frame)
    window_index = pd.read_parquet(raw_window_directory / "window_index.parquet")
    windows_path = raw_window_directory / "vibration_windows.npy"
    windows = np.load(windows_path, mmap_mode="r")
    if windows.shape != (len(frame) * WINDOWS_PER_RECORD, WINDOW_SIZE):
        raise ValueError("raw sensitivity window array shape changed")
    if (
        len(window_index) != len(windows)
        or set(window_index["row_index"].astype(int)) != set(range(len(frame)))
        or not window_index.groupby("row_index", observed=True)
        .size()
        .eq(WINDOWS_PER_RECORD)
        .all()
    ):
        raise ValueError("raw sensitivity window index changed")
    del windows
    output_directory.mkdir(parents=True, exist_ok=True)
    if any(output_directory.iterdir()):
        raise ValueError("raw sensitivity output directory must be empty")
    device = torch.device(device_name)
    if device.type == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("raw sensitivity requested CUDA but CUDA is unavailable")
    label_lookup = {label: index for index, label in enumerate(PADERBORN_LABELS)}
    splits = build_protocol_splits(frame)
    prediction_frames = []
    fit_records = []
    traces = []
    completed = 0
    expected_fit_count = sum(len(splits[protocol]) for protocol in RAW_PROTOCOLS) * len(
        RAW_MODELS
    ) * len(RAW_SEEDS)
    metadata_columns = [
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
        "identity_fold_id",
        "evaluation_cell",
    ]

    for protocol in RAW_PROTOCOLS:
        for method in RAW_MODELS:
            for split in splits[protocol]:
                source_rows = window_index.loc[
                    window_index["row_index"].isin(split.source_indices)
                ].sort_values("window_row_index", kind="stable")
                target_rows = window_index.loc[
                    window_index["row_index"].isin(split.target_indices)
                ].sort_values("window_row_index", kind="stable")
                if window_index["row_index"].isin(split.quarantine_indices).loc[
                    source_rows.index
                ].any():
                    raise ValueError("raw sensitivity source contains a quarantine row")
                source_labels = (
                    frame.iloc[source_rows["row_index"].to_numpy(dtype=int)]["truth"]
                    .map(label_lookup)
                    .to_numpy(dtype=np.int64)
                )
                target_labels = (
                    frame.iloc[target_rows["row_index"].to_numpy(dtype=int)]["truth"]
                    .map(label_lookup)
                    .to_numpy(dtype=np.int64)
                )
                train_dataset = RawWindowDataset(windows_path, source_rows, source_labels)
                target_dataset = RawWindowDataset(windows_path, target_rows, target_labels)
                for seed in RAW_SEEDS:
                    probabilities, target_window_rows, diagnostics, trace = _fit_predict(
                        model_name=method,
                        seed=seed,
                        train_dataset=train_dataset,
                        target_dataset=target_dataset,
                        device=device,
                        epochs=epochs,
                        batch_size=batch_size,
                    )
                    if not np.array_equal(
                        target_window_rows,
                        target_rows["window_row_index"].to_numpy(dtype=np.int64),
                    ):
                        raise ValueError("raw sensitivity target prediction order changed")
                    target = target_rows.loc[
                        :, ["window_row_index", "row_index", "window_index"]
                    ].reset_index(drop=True)
                    physical = frame.iloc[target["row_index"].to_numpy(dtype=int)].loc[
                        :, metadata_columns
                    ].reset_index(drop=True)
                    prediction = pd.concat((target, physical), axis=1)
                    prediction.insert(0, "fold_id", split.fold_id)
                    prediction.insert(0, "seed", seed)
                    prediction.insert(0, "method", method)
                    prediction.insert(0, "protocol", protocol)
                    for column_index, column in enumerate(PROBABILITY_COLUMNS):
                        prediction[column] = probabilities[:, column_index]
                    prediction_frames.append(prediction)
                    completed += 1
                    fit_records.append(
                        {
                            "protocol": protocol,
                            "method": method,
                            "seed": seed,
                            "fold_id": split.fold_id,
                            "source_record_count": len(split.source_indices),
                            "source_window_count": len(source_rows),
                            "target_record_count": len(split.target_indices),
                            "target_window_count": len(target_rows),
                            "quarantine_record_count": len(split.quarantine_indices),
                            **diagnostics,
                        }
                    )
                    trace.update({"protocol": protocol, "fold_id": split.fold_id})
                    traces.append(trace)
                    print(
                        json.dumps(
                            {
                                "event": "raw_architecture_fit_complete",
                                "completed": completed,
                                "expected": expected_fit_count,
                                **fit_records[-1],
                            },
                            sort_keys=True,
                        ),
                        flush=True,
                    )
            checkpoint = pd.concat(prediction_frames, ignore_index=True)
            checkpoint.to_parquet(
                output_directory / f"checkpoint_through_{protocol}_{method}.parquet",
                index=False,
            )
            _write_csv(output_directory / "checkpoint_fit_log.csv", pd.DataFrame(fit_records))
            _write_json(output_directory / "checkpoint_training_traces.json", traces)

    if completed != expected_fit_count:
        raise ValueError("raw architecture sensitivity fit family is incomplete")
    window_predictions = pd.concat(prediction_frames, ignore_index=True).sort_values(
        ["protocol", "method", "seed", "row_index", "window_index"],
        kind="stable",
    )
    seed_recordings = aggregate_raw_window_predictions(window_predictions)
    ensemble = ensemble_seed_predictions(seed_recordings, expected_seeds=RAW_SEEDS)
    aggregate, cells = score_oof_predictions(ensemble)
    bootstrap, bootstrap_draw_rows, bootstrap_plan = paired_raw_protocol_bootstrap(
        ensemble,
        draws=bootstrap_draws,
    )
    findings = dict(raw_sensitivity_gate(bootstrap))
    tables = {
        "fit_log.csv": pd.DataFrame(fit_records),
        "seed_recording_predictions.parquet": seed_recordings,
        "ensemble_recording_predictions.parquet": ensemble,
        "aggregate_metrics.csv": aggregate,
        "cell_metrics.csv": cells,
        "bootstrap_summary.csv": bootstrap,
        "bootstrap_draws.csv": bootstrap_draw_rows,
        "bootstrap_draw_plan.csv": bootstrap_plan,
    }
    window_predictions.to_parquet(output_directory / "window_predictions.parquet", index=False)
    for filename, value in tables.items():
        path = output_directory / filename
        if path.suffix == ".parquet":
            value.to_parquet(path, index=False)
        else:
            _write_csv(path, value)
    _write_json(output_directory / "training_traces.json", traces)
    output_names = ["window_predictions.parquet", "training_traces.json", *tables]
    output_hashes = {
        filename: _sha256(output_directory / filename) for filename in sorted(output_names)
    }
    summary = {
        "run_version": RUN_VERSION,
        "status": "complete_retrospective_raw_architecture_sensitivity",
        "seal_sha256": seal_sha256,
        "inputs_sha256": {
            "raw_window_summary": raw_window_summary_sha256,
            "features": features_sha256,
        },
        "design": {
            "upstream_reference": "Knap2026 pdm-bench",
            "models": list(RAW_MODELS),
            "protocols": list(RAW_PROTOCOLS),
            "seeds": list(RAW_SEEDS),
            "record_count": len(frame),
            "windows_per_record": WINDOWS_PER_RECORD,
            "window_size": WINDOW_SIZE,
            "epochs": epochs,
            "batch_size": batch_size,
            "fit_count": completed,
            "bootstrap_draws": bootstrap_draws,
            "bootstrap_unit": "bearing_code_stratified_by_truth",
            "configuration_search": "none",
        },
        "findings": findings,
        "integrity": {
            "window_prediction_rows": len(window_predictions),
            "seed_recording_prediction_rows": len(seed_recordings),
            "ensemble_recording_prediction_rows": len(ensemble),
            "maximum_probability_sum_error": float(
                np.max(
                    np.abs(
                        ensemble.loc[:, PROBABILITY_COLUMNS].to_numpy(dtype=float).sum(axis=1)
                        - 1.0
                    )
                )
            ),
        },
        "output_sha256": output_hashes,
    }
    _write_json(output_directory / "raw_architecture_sensitivity_summary.json", summary)
    print(json.dumps(findings, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-window-dir", type=Path, required=True)
    parser.add_argument("--raw-window-summary-sha256", required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--features-sha256", required=True)
    parser.add_argument("--seal", type=Path, required=True)
    parser.add_argument("--seal-sha256", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=EPOCHS)
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--bootstrap-draws", type=int, default=BOOTSTRAP_DRAWS)
    return parser


def main() -> int:
    arguments = build_parser().parse_args()
    run_sensitivity(
        raw_window_directory=arguments.raw_window_dir,
        raw_window_summary_sha256=arguments.raw_window_summary_sha256,
        features_path=arguments.features,
        features_sha256=arguments.features_sha256,
        seal_path=arguments.seal,
        seal_sha256=arguments.seal_sha256,
        output_directory=arguments.output_dir,
        device_name=arguments.device,
        epochs=arguments.epochs,
        batch_size=arguments.batch_size,
        bootstrap_draws=arguments.bootstrap_draws,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
