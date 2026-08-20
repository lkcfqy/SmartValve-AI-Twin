"""Metadata-only expected-key manifest for the one-shot Paderborn evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from smartvalve.data.paderborn import BEARING_METADATA
from smartvalve.data.paderborn_features import (
    expected_measurement_filenames,
    parse_measurement_filename,
    retained_measurement_filenames,
)
from smartvalve.experiments.cranfield_causal_audit import AUDIT_SEEDS
from smartvalve.experiments.dg_expected_manifest import canonical_key_record
from smartvalve.experiments.paderborn_evaluation import METHODS
from smartvalve.experiments.paderborn_partitions import build_paderborn_partitions

MANIFEST_VERSION = "paderborn-prospective-expected-key-manifest-0.2.0"
KEY_SCHEMAS = {
    "training_models": ("dataset", "method", "seed", "fold_id"),
    "target_predictions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "environment_id",
        "block_id",
        "bearing_code",
        "setting_code",
        "measurement_index",
        "truth",
    ),
    "compound_predictions": (
        "dataset",
        "method",
        "seed",
        "fold_id",
        "row_index",
        "filename",
        "bearing_code",
        "setting_code",
        "measurement_index",
    ),
    "fold_metrics": ("dataset", "method", "seed", "fold_id"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def metadata_only_indices() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Recreate full/primary row identities without opening archive members."""

    metadata = {bearing.code: bearing for bearing in BEARING_METADATA}
    rows = []
    retained = set(retained_measurement_filenames())
    for full_row_index, filename in enumerate(expected_measurement_filenames()):
        if filename not in retained:
            continue
        key = parse_measurement_filename(filename)
        bearing = metadata[key.bearing_code]
        rows.append(
            {
                "full_row_index": full_row_index,
                "filename": filename,
                "bearing_code": key.bearing_code,
                "setting_code": key.setting_code,
                "measurement_index": key.measurement_index,
                "truth": bearing.primary_label,
            }
        )
    full = pd.DataFrame(rows)
    primary = full.loc[full["truth"] != "compound"].reset_index(drop=True)
    compound = full.loc[full["truth"] == "compound"].reset_index(drop=True)
    if len(full) != 2_559 or len(primary) != 2_319 or len(compound) != 240:
        raise ValueError("metadata-only Paderborn cohort counts changed")
    return primary, compound


def build_expected_paderborn_manifest(
    *,
    protocol_document: str,
    protocol_document_sha256: str,
    split_manifest: str,
    split_manifest_sha256: str,
    model_fold_manifest: str,
    model_fold_manifest_sha256: str,
    feature_contract_amendment: str,
    feature_contract_amendment_sha256: str,
    feature_validation: str,
    feature_validation_sha256: str,
    methods: tuple[str, ...] = METHODS,
    seeds: tuple[int, ...] = AUDIT_SEEDS,
) -> dict[str, Any]:
    primary, compound = metadata_only_indices()
    partitions = build_paderborn_partitions(primary)
    rows: dict[str, list[tuple[Any, ...]]] = {name: [] for name in KEY_SCHEMAS}
    fold_records = []
    for partition in partitions:
        fold_records.append(
            {
                "fold_id": partition.fold_id,
                "source_rows": len(partition.source_indices),
                "target_rows": len(partition.target_indices),
                "quarantine_rows": len(partition.quarantine_indices),
                "compound_rows_per_model": len(compound),
            }
        )
        for method in methods:
            for seed in seeds:
                model_key = ("paderborn", method, int(seed), partition.fold_id)
                rows["training_models"].append(model_key)
                rows["fold_metrics"].append(model_key)
                rows["target_predictions"].extend(
                    (
                        *model_key,
                        int(row_index),
                        str(primary.iloc[row_index]["setting_code"]),
                        "|".join(
                            str(primary.iloc[row_index][column])
                            for column in (
                                "bearing_code",
                                "setting_code",
                                "measurement_index",
                            )
                        ),
                        str(primary.iloc[row_index]["bearing_code"]),
                        str(primary.iloc[row_index]["setting_code"]),
                        int(primary.iloc[row_index]["measurement_index"]),
                        str(primary.iloc[row_index]["truth"]),
                    )
                    for row_index in partition.target_indices
                )
                compound_key = (
                    "paderborn_compound",
                    method,
                    int(seed),
                    partition.fold_id,
                )
                rows["compound_predictions"].extend(
                    (
                        *compound_key,
                        int(record.full_row_index),
                        str(record.filename),
                        str(record.bearing_code),
                        str(record.setting_code),
                        int(record.measurement_index),
                    )
                    for record in compound.itertuples(index=False)
                )
    return {
        "manifest_version": MANIFEST_VERSION,
        "role": (
            "metadata-only expected Paderborn topology; contains no signal feature, "
            "model score, prediction or outcome"
        ),
        "input": {
            "protocol_document": protocol_document,
            "protocol_document_sha256": protocol_document_sha256,
            "split_manifest": split_manifest,
            "split_manifest_sha256": split_manifest_sha256,
            "model_fold_manifest": model_fold_manifest,
            "model_fold_manifest_sha256": model_fold_manifest_sha256,
            "feature_contract_amendment": feature_contract_amendment,
            "feature_contract_amendment_sha256": feature_contract_amendment_sha256,
            "feature_validation": feature_validation,
            "feature_validation_sha256": feature_validation_sha256,
            "paderborn_archive_contents_opened_before_manifest": True,
            "structural_exclusion_informed": True,
            "signal_features_used_to_define_topology": False,
            "model_outcomes_inspected_before_manifest": False,
        },
        "configuration": {
            "methods": list(methods),
            "seeds": [int(seed) for seed in seeds],
            "outer_folds": len(partitions),
            "primary_measurements": len(primary),
            "compound_measurements": len(compound),
            "compound_forced_ground_truth_defined": False,
        },
        "folds": fold_records,
        "expected_key_sets": {
            name: canonical_key_record(values, KEY_SCHEMAS[name]) for name, values in rows.items()
        },
    }


def run_manifest(
    *,
    protocol_document: Path,
    expected_protocol_sha256: str,
    split_manifest: Path,
    expected_split_manifest_sha256: str,
    model_fold_manifest: Path,
    expected_model_fold_manifest_sha256: str,
    feature_contract_amendment: Path,
    expected_feature_contract_amendment_sha256: str,
    feature_validation: Path,
    expected_feature_validation_sha256: str,
    output: Path,
) -> dict[str, Any]:
    paths = {
        "protocol_document": protocol_document.resolve(strict=True),
        "split_manifest": split_manifest.resolve(strict=True),
        "model_fold_manifest": model_fold_manifest.resolve(strict=True),
        "feature_contract_amendment": feature_contract_amendment.resolve(strict=True),
        "feature_validation": feature_validation.resolve(strict=True),
    }
    expected = {
        "protocol_document": expected_protocol_sha256,
        "split_manifest": expected_split_manifest_sha256,
        "model_fold_manifest": expected_model_fold_manifest_sha256,
        "feature_contract_amendment": expected_feature_contract_amendment_sha256,
        "feature_validation": expected_feature_validation_sha256,
    }
    for name, path in paths.items():
        if _sha256(path) != expected[name]:
            raise ValueError(f"Paderborn expected-manifest input changed: {name}")
    protocol_text = paths["protocol_document"].read_text(encoding="utf-8")
    for value in ("frozen", "1,080", "104,355", "259,200"):
        if value not in protocol_text:
            raise ValueError(f"Paderborn protocol does not freeze {value}")
    amendment = json.loads(paths["feature_contract_amendment"].read_text(encoding="utf-8"))
    if amendment.get("status") != "authorized_outcome_blind_bulk_feature_extraction":
        raise ValueError("Paderborn feature amendment is not outcome-blind authorization")
    validation = json.loads(paths["feature_validation"].read_text(encoding="utf-8"))
    if validation.get("status") != "passed_before_paderborn_model_outcome_access":
        raise ValueError("Paderborn feature artifacts were not independently validated")
    split = json.loads(paths["split_manifest"].read_text(encoding="utf-8"))
    split_seal = split.get("seal", {})
    if (
        split_seal.get("signal_features_used_to_define_partitions") is not False
        or split_seal.get("model_outcomes_inspected") is not False
    ):
        raise ValueError("Paderborn split manifest crossed the outcome boundary")
    model_folds = json.loads(paths["model_fold_manifest"].read_text(encoding="utf-8"))
    if (
        model_folds.get("signal_features_used_to_define_folds") is not False
        or model_folds.get("model_outcomes_inspected") is not False
    ):
        raise ValueError("Paderborn model-fold manifest crossed the outcome boundary")
    manifest = build_expected_paderborn_manifest(
        protocol_document=str(paths["protocol_document"]),
        protocol_document_sha256=expected_protocol_sha256,
        split_manifest=str(paths["split_manifest"]),
        split_manifest_sha256=expected_split_manifest_sha256,
        model_fold_manifest=str(paths["model_fold_manifest"]),
        model_fold_manifest_sha256=expected_model_fold_manifest_sha256,
        feature_contract_amendment=str(paths["feature_contract_amendment"]),
        feature_contract_amendment_sha256=(expected_feature_contract_amendment_sha256),
        feature_validation=str(paths["feature_validation"]),
        feature_validation_sha256=expected_feature_validation_sha256,
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
    parser.add_argument("--protocol-document", type=Path, required=True)
    parser.add_argument("--protocol-sha256", required=True)
    parser.add_argument("--split-manifest", type=Path, required=True)
    parser.add_argument("--split-manifest-sha256", required=True)
    parser.add_argument("--model-fold-manifest", type=Path, required=True)
    parser.add_argument("--model-fold-manifest-sha256", required=True)
    parser.add_argument("--feature-contract-amendment", type=Path, required=True)
    parser.add_argument("--feature-contract-amendment-sha256", required=True)
    parser.add_argument("--feature-validation", type=Path, required=True)
    parser.add_argument("--feature-validation-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_manifest(
        protocol_document=args.protocol_document,
        expected_protocol_sha256=args.protocol_sha256,
        split_manifest=args.split_manifest,
        expected_split_manifest_sha256=args.split_manifest_sha256,
        model_fold_manifest=args.model_fold_manifest,
        expected_model_fold_manifest_sha256=args.model_fold_manifest_sha256,
        feature_contract_amendment=args.feature_contract_amendment,
        expected_feature_contract_amendment_sha256=(args.feature_contract_amendment_sha256),
        feature_validation=args.feature_validation,
        expected_feature_validation_sha256=args.feature_validation_sha256,
        output=args.output,
    )
    print(json.dumps(result["expected_key_sets"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
