"""Generate deterministic SmartValve manuscript tables and SVG figures."""

from __future__ import annotations

import argparse
import csv
import html
import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from smartvalve.config import project_root

GENERATOR_VERSION = "smartvalve-paper-artifacts-0.1.0"
LEGACY_TABLE_STEMS = (
    "table_01_dataset",
    "table_02_protocol_access",
    "table_03_primary_bootstrap",
    "table_04_paired_differences",
    "table_05_selective_prediction",
    "table_06_estimator_suite",
    "table_07_environment_probe",
    "claim_to_field_map",
)
LEGACY_OUTPUT_NAMES = {
    "FIGURE_CAPTIONS.md",
    "figure_01_protocol_uncertainty.svg",
    "figure_02_estimator_fold_heatmap.svg",
    "figure_03_selective_tradeoff.svg",
    "figure_04_environment_probe.svg",
    *(
        f"{stem}.{suffix}"
        for stem in LEGACY_TABLE_STEMS
        for suffix in ("csv", "md", "tex")
    ),
}
PROTOCOLS = ("P0", "P1", "P2")
REPRESENTATIONS = ("P0", "P2")
ESTIMATORS = (
    "extra_trees",
    "logistic",
    "rbf_svm",
    "hist_gradient_boosting",
    "shrinkage_lda",
)
POLICIES = (
    "none",
    "source_ood_conformal",
    "metadata_support",
    "hybrid",
)
DEFAULT_INPUTS = {
    "EXP-010": Path(
        "artifacts/research/runs/"
        "EXP-010__20260817T151800.153926Z__reference-audit-v0-1-1-final/"
        "outputs/metrics.json"
    ),
    "EXP-011": Path(
        "artifacts/research/runs/"
        "EXP-011__20260817T154730.546117Z__paired-physical-block-bootstrap/"
        "outputs/metrics.json"
    ),
    "EXP-012": Path(
        "artifacts/research/runs/"
        "EXP-012__20260817T155423.605523Z__source-only-selective-prediction/"
        "outputs/metrics.json"
    ),
    "EXP-020": Path(
        "artifacts/research/runs/"
        "EXP-020__20260817T160115.245489Z__classical-baselines-and-environment-probe/"
        "outputs/metrics.json"
    ),
}
EXPECTED_SHA256 = {
    "EXP-010": "e1fe3e26e883d2275678232c117dba00483c31fd834784fb84001d061400315b",
    "EXP-011": "09a404d5f4b9b760d86f791abd3f2e68024634b53205ebdb56f64fc784eb7c2e",
    "EXP-012": "5cbcc74c6de756fe52af81c6a22694e4a9ef379946e453ca2988c895c9c9b340",
    "EXP-020": "f4b120824d8c39ffd555282d793dc018e7c0597381f1d17e1e2851f33eeb0150",
}
COLORS = {
    "P0": "#2563eb",
    "P1": "#d97706",
    "P2": "#059669",
    "none": "#64748b",
    "source_ood_conformal": "#7c3aed",
    "metadata_support": "#0284c7",
    "hybrid": "#dc2626",
}


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_locked_json(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Load one result only if it matches the frozen digest."""

    actual = _sha256(path)
    if actual != expected_sha256:
        raise ValueError(
            f"locked paper input mismatch for {path}: expected {expected_sha256}, got {actual}"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _provenance_path(path: Path, root: Path) -> str:
    """Return a checkout-independent path when the input lives below ``root``."""

    resolved = path.resolve()
    try:
        return resolved.relative_to(root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _load_inputs(
    paths: dict[str, Path], *, root: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    values = {}
    provenance = {}
    for experiment_id, path in paths.items():
        resolved = path.resolve()
        values[experiment_id] = load_locked_json(
            resolved, EXPECTED_SHA256[experiment_id]
        )
        provenance[experiment_id] = {
            "path": _provenance_path(resolved, root),
            "sha256": EXPECTED_SHA256[experiment_id],
        }
    return values, provenance


def format_interval(item: dict[str, float], digits: int = 4) -> str:
    return (
        f"{item['point_estimate']:.{digits}f} "
        f"[{item['ci95_low']:.{digits}f}, {item['ci95_high']:.{digits}f}]"
    )


def _format_mean(item: dict[str, float], digits: int = 4) -> str:
    return f"{item['mean']:.{digits}f} ± {item['sample_std']:.{digits}f}"


def _write_text(path: Path, value: str) -> None:
    path.write_text(value.rstrip() + "\n", encoding="utf-8")


def _markdown_table(headers: list[str], rows: list[list[Any]]) -> str:
    safe_headers = [str(item).replace("|", "\\|") for item in headers]
    lines = [
        "| " + " | ".join(safe_headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        values = [str(item).replace("|", "\\|") for item in row]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def _latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "±": r"$\pm$",
    }
    return "".join(replacements.get(character, character) for character in text)


def _latex_table(headers: list[str], rows: list[list[Any]]) -> str:
    columns = "l" + "r" * (len(headers) - 1)
    lines = [
        f"\\begin{{tabular}}{{{columns}}}",
        "\\hline",
        " & ".join(_latex_escape(item) for item in headers) + r" \\",
        "\\hline",
    ]
    lines.extend(
        " & ".join(_latex_escape(item) for item in row) + r" \\" for row in rows
    )
    lines.extend(("\\hline", "\\end{tabular}"))
    return "\n".join(lines)


def _write_table(
    output_directory: Path,
    stem: str,
    headers: list[str],
    rows: list[list[Any]],
) -> None:
    with (output_directory / f"{stem}.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)
    _write_text(output_directory / f"{stem}.md", _markdown_table(headers, rows))
    _write_text(output_directory / f"{stem}.tex", _latex_table(headers, rows))


def _svg_text(
    x: float,
    y: float,
    value: str,
    *,
    size: int = 14,
    anchor: str = "start",
    weight: int = 400,
    fill: str = "#0f172a",
    rotate: int | None = None,
) -> str:
    transform = f' transform="rotate({rotate} {x} {y})"' if rotate is not None else ""
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}"{transform}>'
        f"{html.escape(value)}</text>"
    )


def _svg_document(width: int, height: int, title: str, body: list[str]) -> str:
    return "\n".join(
        [
            '<?xml version="1.0" encoding="UTF-8"?>',
            (
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                f'height="{height}" viewBox="0 0 {width} {height}" role="img" '
                f'aria-labelledby="title desc">'
            ),
            f'<title id="title">{html.escape(title)}</title>',
            (
                '<desc id="desc">Generated deterministically from locked SmartValve '
                "experiment metrics.</desc>"
            ),
            '<rect width="100%" height="100%" fill="#ffffff"/>',
            '<g font-family="Arial, Helvetica, sans-serif">',
            *body,
            "</g>",
            "</svg>",
        ]
    )


def _axis_panel(
    body: list[str],
    *,
    x0: float,
    x1: float,
    y0: float,
    y1: float,
    low: float,
    high: float,
    ticks: list[float],
    label: str,
) -> Any:
    body.append(
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#334155"/>'
    )
    body.append(
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#334155"/>'
    )

    def map_y(value: float) -> float:
        return y1 - (value - low) / (high - low) * (y1 - y0)

    for tick in ticks:
        y = map_y(tick)
        body.append(
            f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" '
            'stroke="#e2e8f0" stroke-width="1"/>'
        )
        body.append(_svg_text(x0 - 10, y + 5, f"{tick:.2f}", anchor="end", size=12))
    body.append(
        _svg_text(x0 - 52, (y0 + y1) / 2, label, anchor="middle", size=13, rotate=-90)
    )
    return map_y


def _figure_protocol_uncertainty(exp011: dict[str, Any]) -> str:
    body: list[str] = [
        _svg_text(
            500,
            32,
            "Reference access changes average and calibration risk",
            anchor="middle",
            size=20,
            weight=700,
        ),
        _svg_text(
            500,
            54,
            "Point estimates and paired physical-block 95% percentile intervals",
            anchor="middle",
            size=13,
            fill="#475569",
        ),
    ]
    left_y = _axis_panel(
        body,
        x0=75,
        x1=465,
        y0=85,
        y1=420,
        low=0.70,
        high=0.92,
        ticks=[0.70, 0.75, 0.80, 0.85, 0.90],
        label="Macro F1",
    )
    right_y = _axis_panel(
        body,
        x0=580,
        x1=970,
        y0=85,
        y1=420,
        low=0.15,
        high=0.46,
        ticks=[0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45],
        label="Multiclass Brier (lower is better)",
    )
    body.extend(
        (
            _svg_text(270, 78, "Fault classification", anchor="middle", size=15, weight=600),
            _svg_text(775, 78, "Probability quality", anchor="middle", size=15, weight=600),
        )
    )
    x_left = {"P0": 155, "P1": 270, "P2": 385}
    x_right = {"P0": 660, "P1": 775, "P2": 890}
    for protocol in PROTOCOLS:
        color = COLORS[protocol]
        for metric, x, map_y in (
            ("macro_f1", x_left[protocol], left_y),
            ("multiclass_brier", x_right[protocol], right_y),
        ):
            item = exp011["results"][protocol][metric]
            low = map_y(item["ci95_low"])
            high = map_y(item["ci95_high"])
            point = map_y(item["point_estimate"])
            body.append(
                f'<line x1="{x}" y1="{low:.2f}" x2="{x}" y2="{high:.2f}" '
                f'stroke="{color}" stroke-width="4"/>'
            )
            body.append(
                f'<line x1="{x - 8}" y1="{low:.2f}" x2="{x + 8}" y2="{low:.2f}" '
                f'stroke="{color}" stroke-width="3"/>'
            )
            body.append(
                f'<line x1="{x - 8}" y1="{high:.2f}" x2="{x + 8}" y2="{high:.2f}" '
                f'stroke="{color}" stroke-width="3"/>'
            )
            body.append(
                f'<circle cx="{x}" cy="{point:.2f}" r="7" fill="{color}" '
                'stroke="#ffffff" stroke-width="2"/>'
            )
        body.append(_svg_text(x_left[protocol], 445, protocol, anchor="middle", weight=700))
        body.append(_svg_text(x_right[protocol], 445, protocol, anchor="middle", weight=700))
    labels = {
        "P0": "no target trace",
        "P1": "source-linear reference",
        "P2": "matched target reference",
    }
    for index, protocol in enumerate(PROTOCOLS):
        x = 180 + index * 275
        body.append(f'<circle cx="{x}" cy="485" r="6" fill="{COLORS[protocol]}"/>')
        body.append(_svg_text(x + 12, 490, f"{protocol}: {labels[protocol]}", size=12))
    return _svg_document(1040, 515, "Reference-access bootstrap intervals", body)


def _heat_color(value: float) -> str:
    bounded = max(0.0, min(1.0, value))
    low = (254, 226, 226)
    high = (219, 234, 254)
    channels = [
        round(left + bounded * (right - left))
        for left, right in zip(low, high, strict=True)
    ]
    return "#" + "".join(f"{channel:02x}" for channel in channels)


def _figure_estimator_heatmap(exp020: dict[str, Any]) -> str:
    body: list[str] = [
        _svg_text(
            575,
            34,
            "P0 fold macro F1 depends strongly on estimator and motion",
            anchor="middle",
            size=20,
            weight=700,
        ),
        _svg_text(
            575,
            56,
            "Five-seed means; outlined cell is at balanced-chance failure level",
            anchor="middle",
            size=13,
            fill="#475569",
        ),
    ]
    x0, y0 = 260, 115
    cell_w, cell_h = 135, 65
    folds = [
        ("trap", -40),
        ("trap", 20),
        ("trap", 40),
        ("sin", -40),
        ("sin", 20),
        ("sin", 40),
    ]
    friendly = {
        "extra_trees": "ExtraTrees",
        "logistic": "Logistic",
        "rbf_svm": "RBF-SVM",
        "hist_gradient_boosting": "HistGradientBoosting",
        "shrinkage_lda": "Shrinkage LDA",
    }
    for column, (motion, load_kg) in enumerate(folds):
        label = f"{motion} / {load_kg} kg"
        body.append(
            _svg_text(
                x0 + column * cell_w + cell_w / 2,
                y0 - 18,
                label,
                anchor="middle",
                size=12,
                weight=600,
            )
        )
    p0 = exp020["fault_classification"]["results"]["P0"]
    for row, estimator_name in enumerate(ESTIMATORS):
        body.append(
            _svg_text(
                x0 - 16,
                y0 + row * cell_h + cell_h / 2 + 5,
                friendly[estimator_name],
                anchor="end",
                size=13,
                weight=600,
            )
        )
        summary_folds = {
            (item["motion"], int(item["held_out_load_kg"])): item
            for item in p0[estimator_name]["summary"]["folds"]
        }
        for column, fold in enumerate(folds):
            value = summary_folds[fold]["macro_f1"]["mean"]
            x = x0 + column * cell_w
            y = y0 + row * cell_h
            stroke = "#991b1b" if value <= 1.0 / 6.0 + 1e-12 else "#ffffff"
            width = 4 if value <= 1.0 / 6.0 + 1e-12 else 2
            body.append(
                f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" '
                f'fill="{_heat_color(value)}" stroke="{stroke}" stroke-width="{width}"/>'
            )
            body.append(
                _svg_text(
                    x + cell_w / 2,
                    y + cell_h / 2 + 6,
                    f"{value:.3f}",
                    anchor="middle",
                    size=15,
                    weight=700,
                )
            )
    legend_y = 465
    for index, value in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
        x = 360 + index * 90
        body.append(
            f'<rect x="{x}" y="{legend_y}" width="90" height="20" '
            f'fill="{_heat_color(value)}" stroke="#ffffff"/>'
        )
        body.append(_svg_text(x, legend_y + 38, f"{value:.2f}", size=11))
    body.append(_svg_text(800, legend_y + 18, "higher macro F1", size=12, fill="#475569"))
    return _svg_document(1150, 535, "P0 estimator-by-fold macro F1 heatmap", body)


def _figure_selective_tradeoff(exp012: dict[str, Any]) -> str:
    body: list[str] = [
        _svg_text(
            450,
            34,
            "Safe failure handling requires an explicit coverage trade-off",
            anchor="middle",
            size=20,
            weight=700,
        ),
        _svg_text(
            450,
            56,
            "Five-seed mean coverage versus accepted-set error",
            anchor="middle",
            size=13,
            fill="#475569",
        ),
    ]
    x0, x1, y0, y1 = 90, 820, 90, 475
    body.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#334155"/>')
    body.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#334155"/>')

    def map_x(value: float) -> float:
        return x0 + value * (x1 - x0)

    def map_y(value: float) -> float:
        return y1 - value / 0.18 * (y1 - y0)

    for tick in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        x = map_x(tick)
        body.append(f'<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="#e2e8f0"/>')
        body.append(_svg_text(x, y1 + 24, f"{tick:.1f}", anchor="middle", size=12))
    for tick in (0.0, 0.05, 0.10, 0.15):
        y = map_y(tick)
        body.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#e2e8f0"/>')
        body.append(_svg_text(x0 - 10, y + 5, f"{tick:.2f}", anchor="end", size=12))
    body.append(_svg_text((x0 + x1) / 2, 525, "Coverage", anchor="middle", size=14, weight=600))
    body.append(
        _svg_text(
            34,
            (y0 + y1) / 2,
            "Selective error",
            anchor="middle",
            size=14,
            weight=600,
            rotate=-90,
        )
    )
    offsets = {
        "none": (-150, -18),
        "source_ood_conformal": (-150, -18),
        "metadata_support": (18, -8),
        "hybrid": (18, -8),
    }
    names = {
        "none": "No rejection",
        "source_ood_conformal": "Source-LOO conformal",
        "metadata_support": "Metadata support",
        "hybrid": "Hybrid (exploratory)",
    }
    for policy in POLICIES:
        summary = exp012["results"][policy]["summary"]
        coverage = summary["coverage"]["mean"]
        risk = 1.0 - summary["selective_accuracy"]["mean"]
        errors = summary["accepted_errors"]["mean"]
        x, y = map_x(coverage), map_y(risk)
        body.append(
            f'<circle cx="{x}" cy="{y}" r="11" fill="{COLORS[policy]}" '
            'stroke="#ffffff" stroke-width="3"/>'
        )
        dx, dy = offsets[policy]
        body.append(_svg_text(x + dx, y + dy, names[policy], size=12, weight=700))
        body.append(
            _svg_text(
                x + dx,
                y + dy + 17,
                f"accepted errors: {errors:.1f}",
                size=11,
                fill="#475569",
            )
        )
    body.append(
        _svg_text(
            450,
            555,
            "Observed points only; source calibration does not guarantee shifted-target risk.",
            anchor="middle",
            size=12,
            fill="#991b1b",
            weight=600,
        )
    )
    return _svg_document(900, 580, "Selective prediction coverage-risk trade-off", body)


def _figure_environment_probe(exp020: dict[str, Any]) -> str:
    body: list[str] = [
        _svg_text(
            390,
            34,
            "Operating load remains decodable from both representations",
            anchor="middle",
            size=20,
            weight=700,
        ),
        _svg_text(
            390,
            56,
            "Repetition-disjoint ExtraTrees load probe; mean ± sample SD",
            anchor="middle",
            size=13,
            fill="#475569",
        ),
    ]
    x0, x1, y0, y1 = 100, 730, 90, 420
    body.append(f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#334155"/>')
    body.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#334155"/>')

    def map_y(value: float) -> float:
        return y1 - (value - 0.80) / 0.20 * (y1 - y0)

    for tick in (0.80, 0.85, 0.90, 0.95, 1.00):
        y = map_y(tick)
        body.append(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="#e2e8f0"/>')
        body.append(_svg_text(x0 - 10, y + 5, f"{tick:.2f}", anchor="end", size=12))
    body.append(
        _svg_text(
            38,
            255,
            "Load macro F1",
            anchor="middle",
            size=14,
            weight=600,
            rotate=-90,
        )
    )
    x_positions = {"P0": 270, "P2": 540}
    for representation in REPRESENTATIONS:
        item = exp020["environment_probe"]["results"][representation]["summary"][
            "macro_f1"
        ]
        x = x_positions[representation]
        top = map_y(item["mean"])
        body.append(
            f'<rect x="{x - 70}" y="{top}" width="140" height="{y1 - top}" '
            f'fill="{COLORS[representation]}" opacity="0.88"/>'
        )
        low = map_y(item["mean"] - item["sample_std"])
        high = map_y(min(1.0, item["mean"] + item["sample_std"]))
        body.append(
            f'<line x1="{x}" y1="{low}" x2="{x}" y2="{high}" '
            'stroke="#0f172a" stroke-width="3"/>'
        )
        body.append(f'<line x1="{x - 10}" y1="{low}" x2="{x + 10}" y2="{low}" stroke="#0f172a"/>')
        body.append(f'<line x1="{x - 10}" y1="{high}" x2="{x + 10}" y2="{high}" stroke="#0f172a"/>')
        body.append(
            _svg_text(
                x,
                top - 12,
                _format_mean(item),
                anchor="middle",
                size=13,
                weight=700,
            )
        )
        label = "Raw P0" if representation == "P0" else "Matched-reference P2"
        body.append(_svg_text(x, y1 + 28, label, anchor="middle", size=14, weight=600))
    body.append(
        _svg_text(
            390,
            490,
            "Decodability is a nuisance-retention diagnostic, not proof of causal classifier use.",
            anchor="middle",
            size=12,
            fill="#475569",
        )
    )
    return _svg_document(780, 515, "Operating-environment prediction probe", body)


def _protocol_rows() -> list[list[Any]]:
    return [
        [
            "P0",
            "raw features",
            "none",
            "no",
            "no",
            "strict target-free baseline",
        ],
        [
            "P1",
            "delta + relative features",
            "linear healthy reference from two source loads",
            "no",
            "no",
            "source-only extrapolation",
        ],
        [
            "P2",
            "delta + relative features",
            "different healthy repetition at held-out load",
            "yes",
            "no",
            "target-condition calibration; not pure DG",
        ],
    ]


def _write_tables(output_directory: Path, values: dict[str, Any]) -> None:
    exp010 = values["EXP-010"]
    exp011 = values["EXP-011"]
    exp012 = values["EXP-012"]
    exp020 = values["EXP-020"]
    dataset = exp010["dataset"]
    _write_table(
        output_directory,
        "table_01_dataset",
        ["Item", "Value"],
        [
            ["Dataset", dataset["name"]],
            ["Physical rigs", 1],
            ["Analyzed trials", dataset["trials"]],
            ["Motions", ", ".join(dataset["motions"])],
            ["Loads (kgf)", ", ".join(str(item) for item in dataset["loads_kgf"])],
            ["Classes", ", ".join(dataset["classes"])],
            ["Repetitions per cell", dataset["repetitions_per_cell"]],
            ["Outer folds", "6 motion-specific leave-one-load-out folds"],
            ["Train/test trials per fold", "60 / 30"],
            ["License", dataset["license"]],
        ],
    )
    _write_table(
        output_directory,
        "table_02_protocol_access",
        [
            "Protocol",
            "Features",
            "Healthy reference",
            "Target trajectory",
            "Target labels",
            "Deployment interpretation",
        ],
        _protocol_rows(),
    )
    bootstrap_rows = []
    for protocol in PROTOCOLS:
        result = exp011["results"][protocol]
        bootstrap_rows.append(
            [
                protocol,
                format_interval(result["macro_f1"]),
                format_interval(result["worst_fold_macro_f1"]),
                format_interval(result["multiclass_brier"]),
                format_interval(result["control_ratio"]),
                f"{result['chance_failure_probability']:.3f}",
            ]
        )
    _write_table(
        output_directory,
        "table_03_primary_bootstrap",
        [
            "Protocol",
            "Macro F1 [95% CI]",
            "Worst-fold F1 [95% CI]",
            "Brier [95% CI]",
            "Control ratio [95% CI]",
            "P(chance failure)",
        ],
        bootstrap_rows,
    )
    paired_rows = []
    for comparison in ("P1_minus_P0", "P2_minus_P0"):
        for metric in ("macro_f1", "multiclass_brier", "control_ratio"):
            item = exp011["paired_comparisons"][comparison][metric]
            paired_rows.append(
                [
                    comparison.replace("_", " "),
                    metric,
                    format_interval(item),
                    "yes" if item["resolved_away_from_zero"] else "no",
                ]
            )
    _write_table(
        output_directory,
        "table_04_paired_differences",
        ["Comparison", "Metric", "Difference [95% CI]", "Resolved from zero"],
        paired_rows,
    )
    selective_rows = []
    for policy in POLICIES:
        summary = exp012["results"][policy]["summary"]
        selective_rows.append(
            [
                policy,
                _format_mean(summary["coverage"]),
                _format_mean(summary["selective_accuracy"]),
                _format_mean(summary["macro_f1_abstention_as_error"]),
                _format_mean(summary["error_detection_recall"]),
                _format_mean(summary["accepted_errors"], digits=1),
                _format_mean(summary["trap_minus40_accepted_errors"], digits=1),
            ]
        )
    _write_table(
        output_directory,
        "table_05_selective_prediction",
        [
            "Policy",
            "Coverage",
            "Selective accuracy",
            "F1 (abstention=error)",
            "Error recall",
            "Accepted errors",
            "trap/-40 errors",
        ],
        selective_rows,
    )
    estimator_rows = []
    fault_results = exp020["fault_classification"]["results"]
    for representation in REPRESENTATIONS:
        for estimator_name in ESTIMATORS:
            summary = fault_results[representation][estimator_name]["summary"]
            estimator_rows.append(
                [
                    representation,
                    estimator_name,
                    _format_mean(summary["macro_f1"]),
                    _format_mean(summary["worst_fold_macro_f1"]),
                    _format_mean(summary["multiclass_brier"]),
                    _format_mean(summary["control_ratio"]),
                ]
            )
    _write_table(
        output_directory,
        "table_06_estimator_suite",
        [
            "Representation",
            "Estimator",
            "Macro F1",
            "Worst-fold F1",
            "Brier",
            "Control ratio",
        ],
        estimator_rows,
    )
    probe_rows = []
    for representation in REPRESENTATIONS:
        summary = exp020["environment_probe"]["results"][representation]["summary"]
        probe_rows.append(
            [
                representation,
                _format_mean(summary["macro_f1"]),
                _format_mean(summary["per_motion"]["trap"]["macro_f1"]),
                _format_mean(summary["per_motion"]["sin"]["macro_f1"]),
                "no",
            ]
        )
    _write_table(
        output_directory,
        "table_07_environment_probe",
        [
            "Representation",
            "Load macro F1",
            "trap macro F1",
            "sin macro F1",
            "Held-out repetition used as reference",
        ],
        probe_rows,
    )


def _write_figures(output_directory: Path, values: dict[str, Any]) -> None:
    figures = {
        "figure_01_protocol_uncertainty.svg": _figure_protocol_uncertainty(
            values["EXP-011"]
        ),
        "figure_02_estimator_fold_heatmap.svg": _figure_estimator_heatmap(
            values["EXP-020"]
        ),
        "figure_03_selective_tradeoff.svg": _figure_selective_tradeoff(
            values["EXP-012"]
        ),
        "figure_04_environment_probe.svg": _figure_environment_probe(
            values["EXP-020"]
        ),
    }
    for filename, content in figures.items():
        _write_text(output_directory / filename, content)


def _write_captions(output_directory: Path) -> None:
    captions = """# Figure captions

1. **Reference-access uncertainty.** Macro-F1 and multiclass Brier point estimates with 95% paired
   physical-block bootstrap percentile intervals (2,000 replicates). P2 uses a healthy trajectory at
   the held-out load and is target-condition calibration, not pure domain generalization.
2. **Estimator-by-environment falsification.** Five-seed P0 macro-F1 means for the fixed classical
   estimator suite. The outlined `trap/-40` ExtraTrees cell is at the frozen balanced-chance failure
   level; the other four families do not reproduce that catastrophic value.
3. **Selective coverage–risk trade-off.** Mean coverage against accepted-set error for four frozen
   EXP-012 policies. The hybrid point is post-EXP-010 exploratory. Source-to-source conformal
   calibration supplies no shifted-target guarantee.
4. **Environment-prediction probe.** Load macro-F1 under repetition-disjoint evaluation. P2 never
   reads the held-out repetition as its healthy reference. Decodability diagnoses retained nuisance
   information but not causal use by the fault classifier.
"""
    _write_text(output_directory / "FIGURE_CAPTIONS.md", captions)


def _write_field_map(output_directory: Path) -> None:
    rows = [
        ["C1 P1 macro-F1 harm", "EXP-011", "paired_comparisons.P1_minus_P0.macro_f1"],
        ["C2 P2 macro-F1 difference", "EXP-011", "paired_comparisons.P2_minus_P0.macro_f1"],
        ["C2 P2 Brier harm", "EXP-011", "paired_comparisons.P2_minus_P0.multiclass_brier"],
        ["C3 chance failure", "EXP-011", "results.<P0|P1|P2>.chance_failure_probability"],
        ["C4 model-independence failure", "EXP-020", "fault_classification.model_independence"],
        ["C5/C6 load decodability", "EXP-020", "environment_probe.results.<P0|P2>.summary"],
        ["C7 conformal accepted errors", "EXP-012", "results.source_ood_conformal.summary"],
        ["C8 hybrid coverage/errors", "EXP-012", "results.hybrid.summary"],
    ]
    _write_table(
        output_directory,
        "claim_to_field_map",
        ["Claim", "Experiment", "JSON field"],
        rows,
    )


def generate_artifacts(
    output_directory: Path,
    *,
    input_paths: dict[str, Path] | None = None,
) -> dict[str, Any]:
    root = project_root()
    paths = {
        experiment_id: (
            path if path.is_absolute() else root / path
        )
        for experiment_id, path in (input_paths or DEFAULT_INPUTS).items()
    }
    values, provenance = _load_inputs(paths, root=root)
    output_directory.mkdir(parents=True, exist_ok=True)
    _write_tables(output_directory, values)
    _write_figures(output_directory, values)
    _write_captions(output_directory)
    _write_field_map(output_directory)
    output_files = [
        {
            "path": path.name,
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(output_directory.iterdir())
        if path.is_file() and path.name in LEGACY_OUTPUT_NAMES
    ]
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "inputs": provenance,
        "outputs": output_files,
        "deterministic": True,
        "notes": [
            "No result value is manually entered into a generated table or figure.",
            "The manifest excludes its own digest.",
        ],
    }
    (output_directory / "artifact_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-directory", type=Path, required=True)
    parser.add_argument("--exp010-metrics", type=Path, default=DEFAULT_INPUTS["EXP-010"])
    parser.add_argument("--exp011-metrics", type=Path, default=DEFAULT_INPUTS["EXP-011"])
    parser.add_argument("--exp012-metrics", type=Path, default=DEFAULT_INPUTS["EXP-012"])
    parser.add_argument("--exp020-metrics", type=Path, default=DEFAULT_INPUTS["EXP-020"])
    args = parser.parse_args()
    manifest = generate_artifacts(
        args.output_directory,
        input_paths={
            "EXP-010": args.exp010_metrics,
            "EXP-011": args.exp011_metrics,
            "EXP-012": args.exp012_metrics,
            "EXP-020": args.exp020_metrics,
        },
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
