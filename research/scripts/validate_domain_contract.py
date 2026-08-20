"""Validate and summarize the D0/D1 source-only fold and intervention-pair contract."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from smartvalve.experiments.domain_data import (
    SourceOnlyFold,
    build_cranfield_folds,
    build_uci_folds,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _fold_summary(fold: SourceOnlyFold) -> dict[str, Any]:
    source_labels, source_counts = np.unique(fold.source_labels, return_counts=True)
    target_labels, target_counts = np.unique(fold.target_labels, return_counts=True)
    return {
        "fold_id": fold.fold_id,
        "held_factor": fold.held_factor,
        "held_level": fold.held_level,
        "source_rows": len(fold.source_indices),
        "target_rows": len(fold.target_indices),
        "source_environments": len(set(fold.source_environments)),
        "target_environments": len(set(fold.target_environments)),
        "source_label_counts": {
            fold.label_names[int(label)]: int(count)
            for label, count in zip(source_labels, source_counts, strict=True)
        },
        "target_label_counts": {
            fold.label_names[int(label)]: int(count)
            for label, count in zip(target_labels, target_counts, strict=True)
        },
        "nuisance_pairs": len(fold.nuisance_pairs),
        "fault_pairs": len(fold.fault_pairs),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uci-feature-matrix", type=Path, required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    args = parser.parse_args()

    cranfield = build_cranfield_folds()
    uci = build_uci_folds(args.uci_feature_matrix)
    payload = {
        "schema_version": "smartvalve-domain-contract-0.1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "access_tier": "P0 source-only",
        "paderborn_archive_contents_opened": False,
        "datasets": {
            "cranfield": {
                "rows": len(cranfield[0].features),
                "feature_count": cranfield[0].features.shape[1],
                "label_names": list(cranfield[0].label_names),
                "folds": [_fold_summary(fold) for fold in cranfield],
            },
            "uci_hydraulic": {
                "feature_matrix_path": str(args.uci_feature_matrix.resolve()),
                "feature_matrix_sha256": _sha256(args.uci_feature_matrix),
                "rows": len(uci[0].features),
                "feature_count": uci[0].features.shape[1],
                "label_names": list(uci[0].label_names),
                "folds": [_fold_summary(fold) for fold in uci],
            },
        },
    }
    args.output_directory.mkdir(parents=True, exist_ok=True)
    (args.output_directory / "domain_contract.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
