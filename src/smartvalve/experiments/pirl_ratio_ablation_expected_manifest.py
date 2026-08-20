"""Outcome-blind expected-key manifest for the frozen PIRL ratio ablation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)
from smartvalve.experiments.pirl_ratio_ablation import (
    ABLATION_ARMS,
    REFERENCE_HASHES,
    _load_reference,
)

MANIFEST_VERSION = "pirl-ratio-ablation-expected-key-manifest-0.1.0"
KEY_SCHEMAS = {
    "training_models": ("dataset", "method", "seed", "fold_id"),
    "target_predictions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_expected_ablation_manifest(
    datasets: dict[str, list[SourceOnlyFold]],
    *,
    uci_feature_matrix: str,
    uci_feature_matrix_sha256: str,
    protocol_document: str,
    protocol_document_sha256: str,
    reference_directory: str,
    arms: tuple[str, ...] = ABLATION_ARMS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> dict[str, Any]:
    """Enumerate model and prediction identities without fitting or scoring."""

    if set(datasets) != {"cranfield", "uci_hydraulic"}:
        raise ValueError("ablation manifest requires exactly Cranfield and UCI Hydraulic")
    if len(arms) != len(set(arms)) or not arms:
        raise ValueError("ablation manifest arms must be unique and non-empty")
    if len(seeds) != len(set(seeds)) or not seeds:
        raise ValueError("ablation manifest seeds must be unique and non-empty")
    model_keys = []
    prediction_keys = []
    fold_records = []
    for dataset, folds in datasets.items():
        if not folds:
            raise ValueError(f"ablation manifest dataset {dataset} has no folds")
        for fold in folds:
            fold.validate()
            if fold.dataset != dataset:
                raise ValueError("ablation manifest fold is assigned to the wrong dataset")
            fold_records.append(
                {
                    "dataset": dataset,
                    "fold_id": fold.fold_id,
                    "source_rows": len(fold.source_indices),
                    "target_rows": len(fold.target_indices),
                }
            )
            for arm in arms:
                for seed in seeds:
                    group = (dataset, arm, int(seed), fold.fold_id)
                    model_keys.append(group)
                    prediction_keys.extend(
                        (*group, int(row_index))
                        for row_index in fold.target_indices
                    )
    return {
        "manifest_version": MANIFEST_VERSION,
        "role": (
            "outcome-blind expected PIRL-ratio ablation topology; contains no "
            "model score, prediction or component result"
        ),
        "input": {
            "uci_feature_matrix": uci_feature_matrix,
            "uci_feature_matrix_sha256": uci_feature_matrix_sha256,
            "protocol_document": protocol_document,
            "protocol_document_sha256": protocol_document_sha256,
            "reference_directory": reference_directory,
            "reference_hashes": REFERENCE_HASHES,
            "paderborn_archive_contents_opened": False,
        },
        "configuration": {
            "arms": list(arms),
            "seeds": [int(seed) for seed in seeds],
            "epochs": 300,
        },
        "folds": fold_records,
        "expected_key_sets": {
            "training_models": canonical_key_record(
                model_keys, KEY_SCHEMAS["training_models"]
            ),
            "target_predictions": canonical_key_record(
                prediction_keys, KEY_SCHEMAS["target_predictions"]
            ),
        },
    }


def run_manifest(
    *,
    uci_feature_matrix: Path,
    expected_uci_feature_matrix_sha256: str,
    protocol_document: Path,
    expected_protocol_sha256: str,
    reference_directory: Path,
    output: Path,
) -> dict[str, Any]:
    uci_feature_matrix = uci_feature_matrix.resolve(strict=True)
    protocol_document = protocol_document.resolve(strict=True)
    reference_directory = reference_directory.resolve(strict=True)
    if _sha256(uci_feature_matrix) != expected_uci_feature_matrix_sha256:
        raise ValueError("UCI feature matrix hash differs from the frozen ablation input")
    if _sha256(protocol_document) != expected_protocol_sha256:
        raise ValueError("PIRL ratio ablation protocol hash differs")
    protocol_text = protocol_document.read_text(encoding="utf-8")
    for value in (
        expected_uci_feature_matrix_sha256,
        "195 model keys",
        "67,500",
    ):
        if value not in protocol_text:
            raise ValueError(f"PIRL ratio ablation protocol does not freeze {value}")
    _load_reference(reference_directory)
    manifest = build_expected_ablation_manifest(
        {
            "cranfield": build_cranfield_folds(),
            "uci_hydraulic": build_uci_folds(uci_feature_matrix),
        },
        uci_feature_matrix=str(uci_feature_matrix),
        uci_feature_matrix_sha256=expected_uci_feature_matrix_sha256,
        protocol_document=str(protocol_document),
        protocol_document_sha256=expected_protocol_sha256,
        reference_directory=str(reference_directory),
    )
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uci-feature-matrix", type=Path, required=True)
    parser.add_argument("--uci-feature-matrix-sha256", required=True)
    parser.add_argument("--protocol-document", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--reference-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_manifest(
        uci_feature_matrix=args.uci_feature_matrix,
        expected_uci_feature_matrix_sha256=args.uci_feature_matrix_sha256,
        protocol_document=args.protocol_document,
        expected_protocol_sha256=args.protocol_sha256,
        reference_directory=args.reference_directory,
        output=args.output,
    )
    print(json.dumps(result["expected_key_sets"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
