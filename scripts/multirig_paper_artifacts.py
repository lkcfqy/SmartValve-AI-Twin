"""Generate deterministic multi-rig manuscript tables and a six-test forest plot."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from numbers import Real
from pathlib import Path
from typing import Any

import pandas as pd

GENERATOR_VERSION = "smartvalve-multirig-paper-artifacts-0.1.0"
METHOD_LABELS = {
    "pirl_ratio": "PIRL (ratio)",
    "erm": "ERM",
    "coral": "CORAL",
    "vrex": "VREx",
    "groupdro": "GroupDRO",
    "dann": "DANN",
    "lisa": "LISA",
    "matchdg": "MatchDG",
    "ccdg": "CCDG",
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(path: Path, expected_sha256: str) -> dict[str, Any]:
    path = path.resolve(strict=True)
    if _sha256(path) != expected_sha256:
        raise ValueError(f"paper-artifact input hash changed: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("paper-artifact input must be a JSON object")
    return value


def _provenance_path(path: Path, project_root: Path) -> str:
    try:
        return path.resolve(strict=True).relative_to(project_root.resolve(strict=True)).as_posix()
    except ValueError as exc:
        raise ValueError(f"paper-artifact input is outside the project root: {path}") from exc


def _summary_cell(summary: dict[str, Any]) -> str:
    return f"{float(summary['mean']):.4f} ± {float(summary['sample_std']):.4f}"


def _markdown_cell(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, Real):
        return f"{float(value):.6f}"
    return str(value)


def _write_table(frame: pd.DataFrame, stem: Path) -> list[Path]:
    csv_path = stem.with_suffix(".csv")
    md_path = stem.with_suffix(".md")
    tex_path = stem.with_suffix(".tex")
    frame.to_csv(csv_path, index=False)
    headers = [str(column).replace("|", "\\|") for column in frame.columns]
    markdown_rows = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for values in frame.itertuples(index=False, name=None):
        markdown_rows.append(
            "| "
            + " | ".join(_markdown_cell(value).replace("|", "\\|") for value in values)
            + " |"
        )
    md_path.write_text("\n".join(markdown_rows) + "\n", encoding="utf-8")
    tex_path.write_text(
        frame.to_latex(index=False, escape=True, float_format="%.6f") + "\n",
        encoding="utf-8",
    )
    return [csv_path, md_path, tex_path]


def _closed_set_table(base: dict[str, Any]) -> pd.DataFrame:
    fields = {
        "pooled_macro_f1": "Pooled macro F1",
        "minimum_setting_macro_f1": "Minimum-setting macro F1",
        "minimum_identity_setting_fold_macro_f1": "Minimum identity-setting F1",
        "pooled_multiclass_brier": "Multiclass Brier",
        "pooled_ece_10_bin": "ECE (10-bin)",
    }
    rows = []
    for method, label in METHOD_LABELS.items():
        summary = base["method_summaries"][method]
        rows.append(
            {
                "Method": label,
                **{column: _summary_cell(summary[field]) for field, column in fields.items()},
            }
        )
    return pd.DataFrame(rows)


def _selective_table(selective: dict[str, Any]) -> pd.DataFrame:
    summary = selective["headline_risk_envelope_summary"]["paderborn"]
    rows = []
    for method in ("erm", "pirl_ratio"):
        record = summary[method]["0.5"]
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Target coverage": float(record["mean_target_coverage"]),
                "Selective risk": float(record["mean_selective_risk"]),
                "Effective accuracy": float(record["mean_effective_accuracy"]),
                "Macro F1 (abstention=error)": float(
                    record["mean_macro_f1_abstention_as_error"]
                ),
                "Minimum environment coverage": float(
                    record["minimum_environment_coverage"]
                ),
                "Zero-coverage groups": int(record["zero_coverage_groups"]),
            }
        )
    return pd.DataFrame(rows)


def _confirmatory_table(family: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for record in family["tests"]:
        rows.append(
            {
                "Dataset": str(record["dataset"]),
                "Endpoint": str(record["endpoint_role"]),
                "Effect (positive=PIRL)": float(record["point_estimate"]),
                "CI95 low": float(record["ci95_low"]),
                "CI95 high": float(record["ci95_high"]),
                "Raw p": float(record["raw_two_sided_tail_p"]),
                "Holm p": float(record["holm_adjusted_p"]),
                "Confirmatory positive": bool(record["confirmatory_positive"]),
            }
        )
    frame = pd.DataFrame(rows)
    if len(frame) != 6 or int(frame["Confirmatory positive"].sum()) != 1:
        raise ValueError("six-test paper table differs from the locked family")
    return frame


def _x(value: float, *, left: float, width: float) -> float:
    minimum, maximum = -0.08, 0.09
    return left + (value - minimum) / (maximum - minimum) * width


def _forest_svg(frame: pd.DataFrame) -> str:
    width = 1040
    height = 560
    plot_left = 430.0
    plot_width = 540.0
    top = 86.0
    row_height = 62.0
    zero_x = _x(0.0, left=plot_left, width=plot_width)
    neg_threshold = _x(-0.01, left=plot_left, width=plot_width)
    pos_threshold = _x(0.01, left=plot_left, width=plot_width)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Inter,Arial,sans-serif;fill:#16202a}'
        '.title{font-size:23px;font-weight:700}.sub{font-size:13px;fill:#52606d}'
        '.label{font-size:14px}.tick{font-size:12px;fill:#52606d}</style>',
        '<text x="32" y="36" class="title">Frozen six-test confirmatory family</text>',
        '<text x="32" y="59" class="sub">Point effects and 95% physical-unit bootstrap '
        'intervals; positive favors PIRL</text>',
        f'<rect x="{neg_threshold:.2f}" y="72" width="{pos_threshold-neg_threshold:.2f}" '
        'height="390" fill="#f4f6f8"/>',
        f'<line x1="{zero_x:.2f}" y1="72" x2="{zero_x:.2f}" y2="462" '
        'stroke="#29323c" stroke-width="1.5"/>',
        f'<line x1="{neg_threshold:.2f}" y1="72" x2="{neg_threshold:.2f}" y2="462" '
        'stroke="#b8c2cc" stroke-dasharray="5 5"/>',
        f'<line x1="{pos_threshold:.2f}" y1="72" x2="{pos_threshold:.2f}" y2="462" '
        'stroke="#b8c2cc" stroke-dasharray="5 5"/>',
    ]
    endpoint_labels = {
        "minimum_environment_macro_f1": "minimum-environment macro F1",
        "selective_risk_at_source_50pct": "selective risk at source 50%",
    }
    dataset_labels = {
        "cranfield": "Cranfield",
        "uci_hydraulic": "UCI Hydraulic",
        "paderborn": "Paderborn",
    }
    for index, record in frame.iterrows():
        y = top + index * row_height
        dataset = dataset_labels[str(record["Dataset"])]
        endpoint = endpoint_labels[str(record["Endpoint"])]
        low = _x(float(record["CI95 low"]), left=plot_left, width=plot_width)
        high = _x(float(record["CI95 high"]), left=plot_left, width=plot_width)
        point = _x(float(record["Effect (positive=PIRL)"]), left=plot_left, width=plot_width)
        positive = bool(record["Confirmatory positive"])
        color = "#087e8b" if positive else "#5b6770"
        parts.extend(
            [
                f'<text x="32" y="{y+5:.2f}" class="label">'
                f'{html.escape(dataset)} — {html.escape(endpoint)}</text>',
                f'<line x1="{low:.2f}" y1="{y:.2f}" x2="{high:.2f}" y2="{y:.2f}" '
                f'stroke="{color}" stroke-width="4" stroke-linecap="round"/>',
                f'<line x1="{low:.2f}" y1="{y-7:.2f}" x2="{low:.2f}" y2="{y+7:.2f}" '
                f'stroke="{color}" stroke-width="2"/>',
                f'<line x1="{high:.2f}" y1="{y-7:.2f}" x2="{high:.2f}" y2="{y+7:.2f}" '
                f'stroke="{color}" stroke-width="2"/>',
                f'<circle cx="{point:.2f}" cy="{y:.2f}" r="7" fill="{color}"/>',
            ]
        )
        if positive:
            parts.append(
                f'<text x="980" y="{y+5:.2f}" text-anchor="end" class="tick" '
                'fill="#087e8b">Holm-positive</text>'
            )
    axis_y = 486.0
    for tick in (-0.08, -0.04, 0.0, 0.04, 0.08):
        x_pos = _x(tick, left=plot_left, width=plot_width)
        parts.extend(
            [
                f'<line x1="{x_pos:.2f}" y1="{axis_y-5:.2f}" x2="{x_pos:.2f}" '
                f'y2="{axis_y+5:.2f}" stroke="#52606d"/>',
                f'<text x="{x_pos:.2f}" y="{axis_y+25:.2f}" text-anchor="middle" '
                f'class="tick">{tick:+.2f}</text>',
            ]
        )
    parts.extend(
        [
            f'<line x1="{plot_left:.2f}" y1="{axis_y:.2f}" '
            f'x2="{plot_left+plot_width:.2f}" y2="{axis_y:.2f}" stroke="#52606d"/>',
            '<text x="700" y="540" text-anchor="middle" class="sub">Effect size</text>',
            '</svg>',
        ]
    )
    return "\n".join(parts) + "\n"


def generate(
    *,
    base_metrics: Path,
    base_sha256: str,
    selective_metrics: Path,
    selective_sha256: str,
    bootstrap_metrics: Path,
    bootstrap_sha256: str,
    family_metrics: Path,
    family_sha256: str,
    output_directory: Path,
    project_root: Path,
) -> dict[str, Any]:
    base = _load(base_metrics, base_sha256)
    selective = _load(selective_metrics, selective_sha256)
    bootstrap = _load(bootstrap_metrics, bootstrap_sha256)
    family = _load(family_metrics, family_sha256)
    if (
        base.get("status") != "one_shot_paderborn_prospective_evaluation_complete"
        or selective.get("status")
        != "sealed_paderborn_source_oof_selective_evaluation_complete"
        or bootstrap.get("bootstrap_version")
        != "paderborn-paired-bearing-cluster-bootstrap-0.2.0"
        or family.get("summary", {}).get("family_size") != 6
    ):
        raise ValueError("multi-rig paper inputs are not the final validated package")
    output_directory.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    generated.extend(
        _write_table(
            _closed_set_table(base),
            output_directory / "table_08_paderborn_closed_set",
        )
    )
    generated.extend(
        _write_table(
            _selective_table(selective),
            output_directory / "table_09_paderborn_selective",
        )
    )
    confirmatory = _confirmatory_table(family)
    generated.extend(
        _write_table(
            confirmatory,
            output_directory / "table_10_confirmatory_family",
        )
    )
    figure_path = output_directory / "figure_05_confirmatory_forest.svg"
    figure_path.write_text(_forest_svg(confirmatory), encoding="utf-8")
    generated.append(figure_path)
    captions_path = output_directory / "MULTIRIG_FIGURE_CAPTIONS.md"
    captions_path.write_text(
        "# Multi-rig figure caption\n\n"
        "**Figure 5. Frozen six-test confirmatory family.** Points are paired effects, with "
        "positive values favoring PIRL; horizontal lines are 95% percentile intervals from "
        "physical-unit bootstrap replicates. Dashed lines mark ±0.01 practical thresholds. "
        "Only UCI Hydraulic selective risk is both practically positive and Holm-significant.\n",
        encoding="utf-8",
    )
    generated.append(captions_path)
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "inputs": {
            "base_metrics": {
                "path": _provenance_path(base_metrics, project_root),
                "sha256": base_sha256,
            },
            "selective_metrics": {
                "path": _provenance_path(selective_metrics, project_root),
                "sha256": selective_sha256,
            },
            "bootstrap_metrics": {
                "path": _provenance_path(bootstrap_metrics, project_root),
                "sha256": bootstrap_sha256,
            },
            "family_metrics": {
                "path": _provenance_path(family_metrics, project_root),
                "sha256": family_sha256,
            },
        },
        "decision": family["summary"],
        "outputs": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(generated)
        ],
        "deterministic": True,
        "notes": [
            "All numerical artifacts are derived from four SHA-256-locked JSON inputs.",
            "The manifest excludes its own digest.",
        ],
    }
    manifest_path = output_directory / "multirig_artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-metrics", type=Path, required=True)
    parser.add_argument("--base-sha256", required=True)
    parser.add_argument("--selective-metrics", type=Path, required=True)
    parser.add_argument("--selective-sha256", required=True)
    parser.add_argument("--bootstrap-metrics", type=Path, required=True)
    parser.add_argument("--bootstrap-sha256", required=True)
    parser.add_argument("--family-metrics", type=Path, required=True)
    parser.add_argument("--family-sha256", required=True)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = generate(
        base_metrics=args.base_metrics,
        base_sha256=args.base_sha256,
        selective_metrics=args.selective_metrics,
        selective_sha256=args.selective_sha256,
        bootstrap_metrics=args.bootstrap_metrics,
        bootstrap_sha256=args.bootstrap_sha256,
        family_metrics=args.family_metrics,
        family_sha256=args.family_sha256,
        output_directory=args.output_directory,
        project_root=args.project_root,
    )
    print(json.dumps(result["decision"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
