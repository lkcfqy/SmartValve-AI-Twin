"""Deterministic tables and figures for the bearing-protocol manuscript."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException

GENERATOR_VERSION = "smartvalve-bearing-paper-artifacts-0.9.1"
PDF_FIXED_TIMESTAMP = "D:19700101000000+00'00'"
METHODS = (
    "pirl_ratio",
    "erm",
    "coral",
    "vrex",
    "groupdro",
    "dann",
    "lisa",
    "matchdg",
    "ccdg",
)
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
    "cnn1d": "Raw 1D CNN",
    "fft": "FFT CNN",
    "stft": "STFT CNN",
}
PADERBORN_PROTOCOLS = (
    "measurement_random",
    "setting_holdout",
    "identity_holdout",
    "crossed_holdout",
)
HUST_PROTOCOLS = (
    "recording_random",
    "load_holdout",
    "matched_specification_holdout",
    "crossed_holdout",
)
SENSOR_FAMILIES = ("vibration", "motor_current", "fusion")
COLORS = {
    "pirl_ratio": "#0f766e",
    "erm": "#1d4ed8",
    "coral": "#9333ea",
    "vrex": "#c2410c",
    "groupdro": "#be123c",
    "dann": "#0369a1",
    "lisa": "#4d7c0f",
    "matchdg": "#7c3aed",
    "ccdg": "#b45309",
    "vibration": "#2563eb",
    "motor_current": "#d97706",
    "fusion": "#059669",
    "cnn1d": "#2563eb",
    "fft": "#d97706",
    "stft": "#059669",
}
METHOD_LINE_STYLES = {
    "pirl_ratio": ("", "circle"),
    "erm": ("10 4", "square"),
    "coral": ("3 3", "diamond"),
    "vrex": ("12 4 3 4", "triangle"),
    "groupdro": ("2 3", "circle"),
    "dann": ("8 3 2 3", "square"),
    "lisa": ("14 4", "diamond"),
    "matchdg": ("5 3", "triangle"),
    "ccdg": ("1 3", "square"),
}
SENSOR_MARKERS = {"vibration": "circle", "motor_current": "square", "fusion": "diamond"}
GROUP_MARKERS = {
    "Paderborn fusion": "circle",
    "HUST D3": "square",
    "Raw architectures": "diamond",
}


def sha256_file(path: Path) -> str:
    """Return a streaming SHA-256 digest."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deterministic_pdf_from_svg(svg: str) -> bytes:
    """Render SVG to a one-page vector PDF with normalized document metadata."""

    import cairosvg
    from pypdf import PdfReader, PdfWriter

    try:
        root = ElementTree.fromstring(svg)
    except (ElementTree.ParseError, DefusedXmlException) as error:
        raise ValueError("cannot render malformed SVG") from error
    title = next(
        (
            element.text.strip()
            for element in root.iter()
            if element.tag.rsplit("}", maxsplit=1)[-1] == "title"
            and element.text
            and element.text.strip()
        ),
        None,
    )
    if title is None:
        raise ValueError("SVG requires a non-empty title before PDF export")

    rendered = cairosvg.svg2pdf(bytestring=svg.encode("utf-8"))
    reader = PdfReader(io.BytesIO(rendered))
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    writer.add_metadata(
        {
            "/Creator": GENERATOR_VERSION,
            "/Producer": "CairoSVG 2.9.0 and pypdf 6.16.1",
            "/Title": title,
            "/CreationDate": PDF_FIXED_TIMESTAMP,
            "/ModDate": PDF_FIXED_TIMESTAMP,
        }
    )
    output = io.BytesIO()
    writer.write(output)
    return output.getvalue()


def _verify(path: Path, expected_sha256: str, role: str) -> Path:
    resolved = path.resolve(strict=True)
    observed = sha256_file(resolved)
    if observed != expected_sha256:
        raise ValueError(f"{role} SHA-256 changed: expected {expected_sha256}, observed {observed}")
    return resolved


def _load_json(path: Path, expected_sha256: str, role: str) -> dict[str, Any]:
    resolved = _verify(path, expected_sha256, role)
    value = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{role} must be a JSON object")
    return value


def load_summary(
    directory: Path,
    filename: str,
    expected_sha256: str,
    expected_status: str,
    *,
    verify_all_declared_outputs: bool = True,
) -> tuple[Path, dict[str, Any]]:
    """Load a summary and optionally verify every artifact digest it declares."""

    directory = directory.resolve(strict=True)
    summary_path = directory / filename
    summary = _load_json(summary_path, expected_sha256, filename)
    if summary.get("status") != expected_status:
        raise ValueError(f"{filename} is not a completed paper input")
    output_hashes = summary.get("output_sha256")
    if not isinstance(output_hashes, dict) or not output_hashes:
        raise ValueError(f"{filename} has no locked output map")
    if verify_all_declared_outputs:
        for artifact_name, digest in output_hashes.items():
            _verify(
                directory / str(artifact_name),
                str(digest),
                f"{filename}/{artifact_name}",
            )
    return directory, summary


def load_validation(path: Path, expected_sha256: str) -> dict[str, Any]:
    """Require an independent validation result that did not report a refit."""

    value = _load_json(path, expected_sha256, "independent validation")
    if not str(value.get("status", "")).startswith("passed_independent"):
        raise ValueError("paper input did not pass independent validation")
    if value.get("refit_performed") is not False:
        raise ValueError("paper validation must explicitly declare refit_performed=false")
    return value


def read_locked_csv(
    directory: Path,
    summary: dict[str, Any],
    filename: str,
) -> pd.DataFrame:
    """Read a CSV only when its digest is declared by the parent summary."""

    digest = summary["output_sha256"].get(filename)
    if digest is None:
        raise ValueError(f"summary does not lock {filename}")
    path = _verify(directory / filename, str(digest), filename)
    return pd.read_csv(path)


def _require_axis(frame: pd.DataFrame, column: str, expected: Iterable[str]) -> None:
    observed = set(frame[column].astype(str))
    expected_set = set(expected)
    if observed != expected_set:
        raise ValueError(
            f"{column} axis changed: expected {sorted(expected_set)}, got {sorted(observed)}"
        )


def _effect_rows(
    bootstrap: pd.DataFrame,
    *,
    comparison: str,
    reference: str = "crossed_holdout",
) -> pd.DataFrame:
    rows = bootstrap.loc[
        (bootstrap["comparison_protocol"] == comparison)
        & (bootstrap["reference_protocol"] == reference)
    ].copy()
    _require_axis(rows, "method", METHODS)
    return rows.set_index("method").loc[list(METHODS)].reset_index()


def _protocol_range(frame: pd.DataFrame, protocol: str) -> dict[str, float]:
    values = frame.loc[frame["protocol"] == protocol, "pooled_macro_f1"].astype(float)
    if values.empty or not values.notna().all():
        raise ValueError(f"cannot compute a finite score range for {protocol}")
    return {"minimum": float(values.min()), "maximum": float(values.max())}


def _effect_snapshot(
    frame: pd.DataFrame,
    *,
    comparison: str,
    expected_methods: Iterable[str],
) -> dict[str, Any]:
    methods = tuple(expected_methods)
    selected = frame.loc[
        (frame["comparison_protocol"] == comparison)
        & (frame["reference_protocol"] == "crossed_holdout")
    ].copy()
    _require_axis(selected, "method", methods)
    selected = selected.set_index("method").loc[list(methods)]
    required = (
        "effect_comparison_minus_reference",
        "bootstrap_lower_95",
        "bootstrap_upper_95",
    )
    if not selected.loc[:, required].notna().all().all():
        raise ValueError(f"{comparison} effect snapshot contains non-finite values")
    return {
        "effect_minimum": float(selected[required[0]].min()),
        "effect_median": float(selected[required[0]].median()),
        "effect_maximum": float(selected[required[0]].max()),
        "interval_lower_minimum": float(selected[required[1]].min()),
        "interval_upper_maximum": float(selected[required[2]].max()),
        "all_interval_lower_limits_above_zero": bool(selected[required[1]].gt(0).all()),
        "by_method": {
            method: {
                "effect": float(selected.loc[method, required[0]]),
                "lower_95": float(selected.loc[method, required[1]]),
                "upper_95": float(selected.loc[method, required[2]]),
            }
            for method in methods
        },
    }


def _maximum_matching_score_difference(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    index_columns: tuple[str, ...],
    role: str,
) -> float:
    columns = [*index_columns, "pooled_macro_f1"]
    left_scores = left.loc[:, columns].set_index(list(index_columns)).sort_index()
    right_scores = right.loc[:, columns].set_index(list(index_columns)).sort_index()
    if (
        not left_scores.index.is_unique
        or not right_scores.index.is_unique
        or not left_scores.index.equals(right_scores.index)
    ):
        raise ValueError(f"{role} score-cell topology changed")
    difference = (
        left_scores["pooled_macro_f1"].astype(float) - right_scores["pooled_macro_f1"].astype(float)
    ).abs()
    maximum = float(difference.max())
    if not pd.notna(maximum) or maximum > 1e-12:
        raise ValueError(f"{role} scores differ by {maximum}")
    return maximum


def paderborn_protocol_table(
    aggregate: pd.DataFrame,
    bootstrap: pd.DataFrame,
) -> pd.DataFrame:
    """Build the main nine-method/four-protocol Paderborn table."""

    _require_axis(aggregate, "method", METHODS)
    _require_axis(aggregate, "protocol", PADERBORN_PROTOCOLS)
    if len(aggregate) != len(METHODS) * len(PADERBORN_PROTOCOLS):
        raise ValueError("Paderborn aggregate table has duplicate or missing cells")
    scores = aggregate.pivot(index="method", columns="protocol", values="pooled_macro_f1")
    effects = _effect_rows(bootstrap, comparison="measurement_random").set_index("method")
    rows = []
    for method in METHODS:
        rows.append(
            {
                "Method": METHOD_LABELS[method],
                "Random": float(scores.loc[method, "measurement_random"]),
                "Setting holdout": float(scores.loc[method, "setting_holdout"]),
                "Identity holdout": float(scores.loc[method, "identity_holdout"]),
                "Crossed holdout": float(scores.loc[method, "crossed_holdout"]),
                "Random - crossed": float(effects.loc[method, "effect_comparison_minus_reference"]),
                "CI95 low": float(effects.loc[method, "bootstrap_lower_95"]),
                "CI95 high": float(effects.loc[method, "bootstrap_upper_95"]),
            }
        )
    return pd.DataFrame(rows)


def sensor_attribution_table(
    aggregate: pd.DataFrame,
    bootstrap: pd.DataFrame,
) -> pd.DataFrame:
    """Build random/crossed/gap results for each frozen sensor view."""

    _require_axis(aggregate, "feature_family", SENSOR_FAMILIES)
    _require_axis(aggregate, "method", METHODS)
    _require_axis(aggregate, "protocol", PADERBORN_PROTOCOLS)
    random_crossed = bootstrap.loc[
        (bootstrap["comparison_protocol"] == "measurement_random")
        & (bootstrap["reference_protocol"] == "crossed_holdout")
    ]
    rows = []
    for family in SENSOR_FAMILIES:
        family_scores = aggregate.loc[aggregate["feature_family"] == family].pivot(
            index="method", columns="protocol", values="pooled_macro_f1"
        )
        family_effects = random_crossed.loc[random_crossed["feature_family"] == family].set_index(
            "method"
        )
        _require_axis(family_effects.reset_index(), "method", METHODS)
        for method in METHODS:
            rows.append(
                {
                    "Sensor view": family,
                    "Method": METHOD_LABELS[method],
                    "Random": float(family_scores.loc[method, "measurement_random"]),
                    "Crossed": float(family_scores.loc[method, "crossed_holdout"]),
                    "Random - crossed": float(
                        family_effects.loc[method, "effect_comparison_minus_reference"]
                    ),
                    "CI95 low": float(family_effects.loc[method, "bootstrap_lower_95"]),
                    "CI95 high": float(family_effects.loc[method, "bootstrap_upper_95"]),
                }
            )
    return pd.DataFrame(rows)


def hust_protocol_table(
    aggregate: pd.DataFrame,
    bootstrap: pd.DataFrame,
    *,
    comparison_protocol: str,
    include_four_protocols: bool,
) -> pd.DataFrame:
    """Build either the HUST replication table or its equal-volume control."""

    _require_axis(aggregate, "method", METHODS)
    effects = _effect_rows(bootstrap, comparison=comparison_protocol).set_index("method")
    scores = aggregate.pivot(index="method", columns="protocol", values="pooled_macro_f1")
    if include_four_protocols:
        _require_axis(aggregate, "protocol", HUST_PROTOCOLS)
    else:
        _require_axis(aggregate, "protocol", (comparison_protocol, "crossed_holdout"))
    rows = []
    for method in METHODS:
        row: dict[str, Any] = {
            "Method": METHOD_LABELS[method],
            "Accessible": float(scores.loc[method, comparison_protocol]),
        }
        if include_four_protocols:
            row.update(
                {
                    "Load holdout": float(scores.loc[method, "load_holdout"]),
                    "Matched-spec holdout": float(
                        scores.loc[method, "matched_specification_holdout"]
                    ),
                }
            )
        row.update(
            {
                "Crossed": float(scores.loc[method, "crossed_holdout"]),
                "Accessible - crossed": float(
                    effects.loc[method, "effect_comparison_minus_reference"]
                ),
                "CI95 low": float(effects.loc[method, "bootstrap_lower_95"]),
                "CI95 high": float(effects.loc[method, "bootstrap_upper_95"]),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def raw_architecture_table(
    aggregate: pd.DataFrame,
    bootstrap: pd.DataFrame,
) -> pd.DataFrame:
    """Build the three-architecture random-versus-crossed sensitivity table."""

    raw_models = ("cnn1d", "fft", "stft")
    _require_axis(aggregate, "method", raw_models)
    _require_axis(aggregate, "protocol", ("measurement_random", "crossed_holdout"))
    scores = aggregate.pivot(index="method", columns="protocol", values="pooled_macro_f1")
    effects = bootstrap.loc[
        (bootstrap["comparison_protocol"] == "measurement_random")
        & (bootstrap["reference_protocol"] == "crossed_holdout")
    ].set_index("method")
    _require_axis(effects.reset_index(), "method", raw_models)
    return pd.DataFrame(
        [
            {
                "Architecture": METHOD_LABELS[model],
                "Random": float(scores.loc[model, "measurement_random"]),
                "Crossed": float(scores.loc[model, "crossed_holdout"]),
                "Random - crossed": float(effects.loc[model, "effect_comparison_minus_reference"]),
                "CI95 low": float(effects.loc[model, "bootstrap_lower_95"]),
                "CI95 high": float(effects.loc[model, "bootstrap_upper_95"]),
            }
            for model in raw_models
        ]
    )


def _selection_regret_row(
    aggregate: pd.DataFrame,
    *,
    study_view: str,
    accessible_protocol: str,
    expected_methods: Iterable[str],
) -> dict[str, Any]:
    """Quantify crossed-score regret among accessible-protocol empirical leaders."""

    method_order = tuple(expected_methods)
    _require_axis(aggregate, "method", method_order)
    protocols = (accessible_protocol, "crossed_holdout")
    selected = aggregate.loc[aggregate["protocol"].isin(protocols)].copy()
    _require_axis(selected, "protocol", protocols)
    if len(selected) != len(method_order) * len(protocols):
        raise ValueError(f"{study_view} selection-regret cells are duplicated or missing")
    scores = selected.pivot(index="method", columns="protocol", values="pooled_macro_f1")
    accessible = scores[accessible_protocol]
    crossed = scores["crossed_holdout"]
    accessible_best = float(accessible.max())
    crossed_best = float(crossed.max())
    tolerance = 1e-12
    accessible_leaders = tuple(
        method
        for method in method_order
        if abs(float(accessible.loc[method]) - accessible_best) <= tolerance
    )
    crossed_leaders = tuple(
        method
        for method in method_order
        if abs(float(crossed.loc[method]) - crossed_best) <= tolerance
    )
    leader_crossed_scores = [float(crossed.loc[method]) for method in accessible_leaders]
    regrets = [crossed_best - score for score in leader_crossed_scores]
    return {
        "Study view": study_view,
        "Accessible protocol": accessible_protocol,
        "Accessible-optimal method(s)": "; ".join(
            METHOD_LABELS[method] for method in accessible_leaders
        ),
        "Accessible leader count": len(accessible_leaders),
        "Crossed-optimal method(s)": "; ".join(METHOD_LABELS[method] for method in crossed_leaders),
        "Best crossed F1": crossed_best,
        "Accessible-leader crossed F1 min": min(leader_crossed_scores),
        "Accessible-leader crossed F1 max": max(leader_crossed_scores),
        "Crossed regret min": min(regrets),
        "Crossed regret max": max(regrets),
    }


def selection_regret_table(
    sensor_aggregate: pd.DataFrame,
    hust_aggregate: pd.DataFrame,
    raw_aggregate: pd.DataFrame,
) -> pd.DataFrame:
    """Build finite-cohort selection regret for sensor, dataset, and raw-model views."""

    _require_axis(sensor_aggregate, "feature_family", SENSOR_FAMILIES)
    rows = [
        _selection_regret_row(
            sensor_aggregate.loc[sensor_aggregate["feature_family"] == family],
            study_view=f"Paderborn {family.replace('_', ' ')}",
            accessible_protocol="measurement_random",
            expected_methods=METHODS,
        )
        for family in SENSOR_FAMILIES
    ]
    rows.append(
        _selection_regret_row(
            hust_aggregate,
            study_view="HUST D3",
            accessible_protocol="recording_random",
            expected_methods=METHODS,
        )
    )
    rows.append(
        _selection_regret_row(
            raw_aggregate,
            study_view="Paderborn raw architectures",
            accessible_protocol="measurement_random",
            expected_methods=("cnn1d", "fft", "stft"),
        )
    )
    return pd.DataFrame(rows)


def access_contract_table() -> pd.DataFrame:
    """Describe the physical information granted by each evaluation protocol."""

    return pd.DataFrame(
        [
            {
                "Design": "Paderborn / HUST",
                "Protocol family": "Random record holdout",
                "Target identity in source": "may be",
                "Target condition in source": "may be",
                "Target-cell siblings in source": "may be",
                "XOR cross-arms in source": "yes",
                "Access code": "I+ C+",
            },
            {
                "Design": "Paderborn / HUST",
                "Protocol family": "Condition holdout",
                "Target identity in source": "yes",
                "Target condition in source": "no",
                "Target-cell siblings in source": "no",
                "XOR cross-arms in source": "identity arm",
                "Access code": "I+ C-",
            },
            {
                "Design": "Paderborn / HUST",
                "Protocol family": "Identity/specification holdout",
                "Target identity in source": "no",
                "Target condition in source": "yes",
                "Target-cell siblings in source": "no",
                "XOR cross-arms in source": "condition arm",
                "Access code": "I- C+",
            },
            {
                "Design": "Paderborn / HUST",
                "Protocol family": "Crossed holdout",
                "Target identity in source": "no",
                "Target condition in source": "no",
                "Target-cell siblings in source": "no",
                "XOR cross-arms in source": "quarantined",
                "Access code": "I- C-",
            },
            {
                "Design": "HUST equal-volume control",
                "Protocol family": "Size-matched shared access",
                "Target identity in source": "yes",
                "Target condition in source": "yes",
                "Target-cell siblings in source": "no",
                "XOR cross-arms in source": "yes",
                "Access code": "I+ C+",
            },
        ]
    )


def _format_cell(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _latex_escape(value: Any) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
    }
    return "".join(replacements.get(character, character) for character in str(value))


def write_table(frame: pd.DataFrame, stem: Path) -> list[Path]:
    """Write one deterministic table in CSV, Markdown, and LaTeX forms."""

    csv_path = stem.with_suffix(".csv")
    md_path = stem.with_suffix(".md")
    tex_path = stem.with_suffix(".tex")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(frame.columns)
        writer.writerows(
            [_format_cell(value) for value in row]
            for row in frame.itertuples(index=False, name=None)
        )
    headers = [str(column).replace("|", "\\|") for column in frame.columns]
    markdown = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in frame.itertuples(index=False, name=None):
        markdown.append(
            "| " + " | ".join(_format_cell(value).replace("|", "\\|") for value in row) + " |"
        )
    md_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")
    columns = "l" + "r" * (len(headers) - 1)
    latex = [
        f"\\begin{{tabular}}{{{columns}}}",
        "\\hline",
        " & ".join(_latex_escape(value) for value in frame.columns) + r" \\",
        "\\hline",
    ]
    latex.extend(
        " & ".join(_latex_escape(_format_cell(value)) for value in row) + r" \\"
        for row in frame.itertuples(index=False, name=None)
    )
    latex.extend(("\\hline", "\\end{tabular}"))
    tex_path.write_text("\n".join(latex) + "\n", encoding="utf-8")
    return [csv_path, md_path, tex_path]


def _svg_document(width: int, height: int, title: str, body: list[str]) -> str:
    return (
        "\n".join(
            [
                '<?xml version="1.0" encoding="UTF-8"?>',
                (
                    f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
                    f'height="{height}" viewBox="0 0 {width} {height}" role="img">'
                ),
                f"<title>{html.escape(title)}</title>",
                '<rect width="100%" height="100%" fill="#ffffff"/>',
                '<g font-family="Arial, Helvetica, sans-serif">',
                *body,
                "</g>",
                "</svg>",
            ]
        )
        + "\n"
    )


def _text(
    x: float,
    y: float,
    value: str,
    *,
    size: int = 13,
    anchor: str = "start",
    weight: int = 400,
    fill: str = "#0f172a",
) -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}">'
        f"{html.escape(value)}</text>"
    )


def _marker_svg(shape: str, x: float, y: float, color: str, *, size: float = 5.0) -> str:
    """Render a marker with a shape channel that survives grayscale reproduction."""

    common = f'fill="{color}" data-marker-shape="{shape}"'
    if shape == "circle":
        return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}" {common}/>'
    if shape == "square":
        return (
            f'<rect x="{x - size:.1f}" y="{y - size:.1f}" width="{2 * size:.1f}" '
            f'height="{2 * size:.1f}" {common}/>'
        )
    if shape == "diamond":
        points = (
            f"{x:.1f},{y - size:.1f} {x + size:.1f},{y:.1f} "
            f"{x:.1f},{y + size:.1f} {x - size:.1f},{y:.1f}"
        )
        return f'<polygon points="{points}" {common}/>'
    if shape == "triangle":
        points = (
            f"{x:.1f},{y - size:.1f} {x + size:.1f},{y + size:.1f} {x - size:.1f},{y + size:.1f}"
        )
        return f'<polygon points="{points}" {common}/>'
    raise ValueError(f"unsupported marker shape: {shape}")


def access_lattice_svg() -> str:
    """Render the two-axis physical-access contract behind the protocols."""

    width, height = 1120, 650
    left, top = 205.0, 135.0
    cell_width, cell_height = 405.0, 195.0
    body = [
        '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" '
        'refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#64748b"/>'
        "</marker></defs>",
        _text(34, 38, "Physical-access lattice", size=24, weight=700),
        _text(
            34,
            64,
            "Each split estimates a different deployment question; I/C denote source access.",
            fill="#475569",
        ),
        _text(
            left + cell_width,
            101,
            "Target condition represented in source?",
            anchor="middle",
            weight=700,
        ),
        _text(left + cell_width / 2, 124, "No", anchor="middle", fill="#64748b"),
        _text(left + 3 * cell_width / 2, 124, "Yes", anchor="middle", fill="#64748b"),
        (
            f'<text x="52" y="{top + cell_height:.1f}" text-anchor="middle" '
            'font-family="Arial, Helvetica, sans-serif" font-size="13" font-weight="700" '
            'fill="#0f172a" transform="rotate(-90 52 '
            f'{top + cell_height:.1f})">Target identity/specification represented in source?'
            "</text>"
        ),
        _text(178, top + cell_height / 2, "No", anchor="end", fill="#64748b"),
        _text(178, top + 3 * cell_height / 2, "Yes", anchor="end", fill="#64748b"),
    ]
    centers = {
        "crossed": (left + cell_width / 2, top + cell_height / 2),
        "identity": (left + 3 * cell_width / 2, top + cell_height / 2),
        "condition": (left + cell_width / 2, top + 3 * cell_height / 2),
        "shared": (left + 3 * cell_width / 2, top + 3 * cell_height / 2),
    }
    for start, end in (
        ("crossed", "identity"),
        ("crossed", "condition"),
        ("identity", "shared"),
        ("condition", "shared"),
    ):
        x1, y1 = centers[start]
        x2, y2 = centers[end]
        body.append(
            f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            'stroke="#64748b" stroke-width="2" marker-end="url(#arrow)"/>'
        )
    boxes = (
        (
            left + 15,
            top + 15,
            "#fff1f2",
            "Crossed holdout",
            "I- C-",
            "Both physical axes are unseen",
            "Both XOR cross-arms quarantined",
        ),
        (
            left + cell_width + 15,
            top + 15,
            "#fefce8",
            "Identity/specification holdout",
            "I- C+",
            "Target identity is unseen",
            "Target condition remains accessible",
        ),
        (
            left + 15,
            top + cell_height + 15,
            "#eff6ff",
            "Condition holdout",
            "I+ C-",
            "Target condition is unseen",
            "Target identity remains accessible",
        ),
        (
            left + cell_width + 15,
            top + cell_height + 15,
            "#f0fdf4",
            "Random record holdout",
            "I+ C+",
            "Both axes may remain accessible",
            "Target records/windows are still held out",
        ),
    )
    for x_value, y_value, fill, title, code, line_one, line_two in boxes:
        body.extend(
            [
                f'<rect x="{x_value:.1f}" y="{y_value:.1f}" width="375" height="165" '
                f'rx="12" fill="{fill}" stroke="#94a3b8"/>',
                _text(x_value + 18, y_value + 34, title, size=16, weight=700),
                _text(x_value + 357, y_value + 34, code, anchor="end", weight=700),
                _text(x_value + 18, y_value + 70, line_one, fill="#334155"),
                _text(x_value + 18, y_value + 96, line_two, fill="#334155"),
            ]
        )
        if code == "I+ C+":
            body.append(
                _text(
                    x_value + 18,
                    y_value + 132,
                    "HUST control: equal source volume, XOR access, no target-cell siblings",
                    size=11,
                    fill="#166534",
                )
            )
    body.extend(
        [
            _text(205, 590, "Less source access", weight=700, fill="#64748b"),
            '<line x1="350" y1="586" x2="900" y2="586" stroke="#64748b" '
            'stroke-width="2" marker-end="url(#arrow)"/>',
            _text(915, 590, "More source access", weight=700, fill="#64748b"),
            _text(
                205,
                625,
                "Access concerns source data only; no target labels enter fitting or selection.",
                fill="#475569",
            ),
        ]
    )
    return _svg_document(width, height, "Physical-access lattice", body)


def protocol_profile_svg(aggregate: pd.DataFrame) -> str:
    """Plot nine method profiles across the four Paderborn protocols."""

    _require_axis(aggregate, "method", METHODS)
    _require_axis(aggregate, "protocol", PADERBORN_PROTOCOLS)
    scores = aggregate.pivot(index="method", columns="protocol", values="pooled_macro_f1")
    width, height = 1100, 650
    left, right, top, bottom = 95.0, 790.0, 75.0, 545.0
    x_values = {
        protocol: left + index * (right - left) / 3
        for index, protocol in enumerate(PADERBORN_PROTOCOLS)
    }

    def y(value: float) -> float:
        return bottom - float(value) * (bottom - top)

    body = [
        _text(32, 36, "Paderborn protocol sensitivity", size=23, weight=700),
        _text(32, 58, "Pooled macro F1; identical models and features", fill="#475569"),
    ]
    for tick in (0.0, 0.2, 0.4, 0.6, 0.8, 1.0):
        y_tick = y(tick)
        body.extend(
            [
                f'<line x1="{left}" y1="{y_tick:.1f}" x2="{right}" y2="{y_tick:.1f}" '
                'stroke="#e2e8f0"/>',
                _text(left - 12, y_tick + 4, f"{tick:.1f}", anchor="end", fill="#64748b"),
            ]
        )
    labels = {
        "measurement_random": "Random",
        "setting_holdout": "Setting",
        "identity_holdout": "Identity",
        "crossed_holdout": "Crossed",
    }
    for protocol in PADERBORN_PROTOCOLS:
        body.append(_text(x_values[protocol], bottom + 28, labels[protocol], anchor="middle"))
    for index, method in enumerate(METHODS):
        points = [
            (x_values[protocol], y(scores.loc[method, protocol]))
            for protocol in PADERBORN_PROTOCOLS
        ]
        color = COLORS[method]
        dash_pattern, marker_shape = METHOD_LINE_STYLES[method]
        dash_attribute = f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        body.append(
            '<polyline fill="none" stroke="{}" stroke-width="2.5"{} points="{}"/>'.format(
                color,
                dash_attribute,
                " ".join(f"{x:.1f},{point_y:.1f}" for x, point_y in points),
            )
        )
        body.extend(_marker_svg(marker_shape, x, point_y, color, size=4) for x, point_y in points)
        legend_y = 95 + index * 42
        body.extend(
            [
                f'<line x1="835" y1="{legend_y}" x2="870" y2="{legend_y}" '
                f'stroke="{color}" stroke-width="3"{dash_attribute}/>',
                _marker_svg(marker_shape, 852.5, legend_y, color, size=4),
                _text(882, legend_y + 4, METHOD_LABELS[method]),
            ]
        )
    return _svg_document(width, height, "Paderborn protocol sensitivity", body)


def gap_forest_svg(frames: list[tuple[str, pd.DataFrame]]) -> str:
    """Plot locked random-access minus crossed gaps and physical-unit intervals."""

    rows: list[dict[str, Any]] = []
    for group, frame in frames:
        for record in frame.itertuples(index=False):
            rows.append(
                {
                    "group": group,
                    "method": str(record.method),
                    "effect": float(record.effect_comparison_minus_reference),
                    "low": float(record.bootstrap_lower_95),
                    "high": float(record.bootstrap_upper_95),
                }
            )
    width = 1120
    row_height = 29
    top = 82
    height = top + len(rows) * row_height + 80
    plot_left, plot_right = 470.0, 1060.0
    lower = min(0.0, min(row["low"] for row in rows))
    upper = max(row["high"] for row in rows)
    margin = max(0.02, (upper - lower) * 0.05)
    lower -= margin
    upper += margin

    def x(value: float) -> float:
        return plot_left + (float(value) - lower) / (upper - lower) * (plot_right - plot_left)

    body = [
        _text(30, 34, "Accessible-split optimism", size=23, weight=700),
        _text(
            30,
            57,
            "Macro-F1 difference (accessible random/shared access minus strict crossed); "
            "95% physical-unit bootstrap CI",
            fill="#475569",
        ),
        f'<line x1="{x(0):.1f}" y1="70" x2="{x(0):.1f}" y2="{height - 55}" '
        'stroke="#334155" stroke-width="1.5"/>',
    ]
    previous_group = None
    palette = {
        "Paderborn fusion": "#2563eb",
        "HUST D3": "#059669",
        "Raw architectures": "#d97706",
    }
    for index, row in enumerate(rows):
        y_value = top + index * row_height
        if row["group"] != previous_group:
            if previous_group is not None:
                body.append(
                    f'<line x1="30" y1="{y_value - 16}" x2="{plot_right}" y2="{y_value - 16}" '
                    'stroke="#e2e8f0"/>'
                )
            previous_group = row["group"]
        label = f"{row['group']} - {METHOD_LABELS[row['method']]}"
        color = palette.get(str(row["group"]), "#475569")
        marker_shape = GROUP_MARKERS.get(str(row["group"]), "triangle")
        body.extend(
            [
                _text(30, y_value + 4, label),
                f'<line x1="{x(row["low"]):.1f}" y1="{y_value}" '
                f'x2="{x(row["high"]):.1f}" y2="{y_value}" stroke="{color}" '
                'stroke-width="3" stroke-linecap="round"/>',
                _marker_svg(marker_shape, x(row["effect"]), y_value, color),
            ]
        )
    axis_y = height - 42
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        value = lower + fraction * (upper - lower)
        body.append(_text(x(value), axis_y + 24, f"{value:.2f}", anchor="middle", fill="#64748b"))
    body.append(
        f'<line x1="{plot_left}" y1="{axis_y}" x2="{plot_right}" y2="{axis_y}" stroke="#64748b"/>'
    )
    return _svg_document(width, height, "Accessible-split optimism", body)


def sensor_gap_svg(bootstrap: pd.DataFrame) -> str:
    """Plot random-minus-crossed gaps for all methods and sensor views."""

    selected = bootstrap.loc[
        (bootstrap["comparison_protocol"] == "measurement_random")
        & (bootstrap["reference_protocol"] == "crossed_holdout")
    ]
    width, height = 1160, 610
    left, right, top, bottom = 105.0, 1080.0, 85.0, 505.0
    x_step = (right - left) / len(METHODS)
    maximum = max(0.5, float(selected["bootstrap_upper_95"].max()) * 1.05)

    def y(value: float) -> float:
        return bottom - float(value) / maximum * (bottom - top)

    body = [
        _text(30, 34, "Sensor-view protocol gaps", size=23, weight=700),
        _text(
            30, 57, "Random minus crossed macro F1; shared bearing bootstrap plan", fill="#475569"
        ),
    ]
    for tick in (0.0, maximum / 4, maximum / 2, 3 * maximum / 4, maximum):
        y_tick = y(tick)
        body.extend(
            [
                f'<line x1="{left}" y1="{y_tick:.1f}" x2="{right}" '
                f'y2="{y_tick:.1f}" stroke="#e2e8f0"/>',
                _text(left - 10, y_tick + 4, f"{tick:.2f}", anchor="end", fill="#64748b"),
            ]
        )
    offsets = {"vibration": -10, "motor_current": 0, "fusion": 10}
    for method_index, method in enumerate(METHODS):
        center = left + (method_index + 0.5) * x_step
        body.append(_text(center, bottom + 28, METHOD_LABELS[method], anchor="middle", size=11))
        for family in SENSOR_FAMILIES:
            record = selected.loc[
                (selected["feature_family"] == family) & (selected["method"] == method)
            ]
            if len(record) != 1:
                raise ValueError("sensor gap figure loses a family/method cell")
            item = record.iloc[0]
            x_value = center + offsets[family]
            color = COLORS[family]
            marker_shape = SENSOR_MARKERS[family]
            body.extend(
                [
                    f'<line x1="{x_value:.1f}" y1="{y(item["bootstrap_lower_95"]):.1f}" '
                    f'x2="{x_value:.1f}" y2="{y(item["bootstrap_upper_95"]):.1f}" '
                    f'stroke="{color}" stroke-width="2"/>',
                    _marker_svg(
                        marker_shape,
                        x_value,
                        y(item["effect_comparison_minus_reference"]),
                        color,
                        size=4,
                    ),
                ]
            )
    for index, family in enumerate(SENSOR_FAMILIES):
        legend_x = 385 + index * 190
        body.extend(
            [
                _marker_svg(SENSOR_MARKERS[family], legend_x, 565, COLORS[family]),
                _text(legend_x + 12, 569, family.replace("_", " ").title()),
            ]
        )
    return _svg_document(width, height, "Sensor-view protocol gaps", body)


def hust_control_svg(primary: pd.DataFrame, control: pd.DataFrame) -> str:
    """Compare HUST random-access and equal-volume access-control effects."""

    primary = _effect_rows(primary, comparison="recording_random").set_index("method")
    control = _effect_rows(control, comparison="size_matched_shared_access").set_index("method")
    width, height = 1050, 570
    left, right, top, bottom = 110.0, 970.0, 80.0, 475.0
    x_step = (right - left) / len(METHODS)
    maximum = (
        max(float(primary["bootstrap_upper_95"].max()), float(control["bootstrap_upper_95"].max()))
        * 1.08
    )

    def y(value: float) -> float:
        return bottom - float(value) / maximum * (bottom - top)

    body = [
        _text(30, 34, "HUST equal-volume access control", size=23, weight=700),
        _text(
            30,
            57,
            "Accessible minus crossed macro F1; identical targets and 24 source "
            "recordings per fold",
            fill="#475569",
        ),
    ]
    for tick in (0.0, maximum / 4, maximum / 2, 3 * maximum / 4, maximum):
        y_tick = y(tick)
        body.extend(
            [
                f'<line x1="{left}" y1="{y_tick:.1f}" x2="{right}" '
                f'y2="{y_tick:.1f}" stroke="#e2e8f0"/>',
                _text(left - 10, y_tick + 4, f"{tick:.2f}", anchor="end", fill="#64748b"),
            ]
        )
    for index, method in enumerate(METHODS):
        center = left + (index + 0.5) * x_step
        body.append(_text(center, bottom + 28, METHOD_LABELS[method], anchor="middle", size=11))
        for offset, frame, color, marker_shape in (
            (-6, primary, "#2563eb", "circle"),
            (6, control, "#d97706", "square"),
        ):
            item = frame.loc[method]
            x_value = center + offset
            body.extend(
                [
                    f'<line x1="{x_value:.1f}" y1="{y(item["bootstrap_lower_95"]):.1f}" '
                    f'x2="{x_value:.1f}" y2="{y(item["bootstrap_upper_95"]):.1f}" '
                    f'stroke="{color}" stroke-width="2"/>',
                    _marker_svg(
                        marker_shape,
                        x_value,
                        y(item["effect_comparison_minus_reference"]),
                        color,
                        size=4,
                    ),
                ]
            )
    body.extend(
        [
            _marker_svg("circle", 390, 535, "#2563eb"),
            _text(403, 539, "Primary random access"),
            _marker_svg("square", 610, 535, "#d97706"),
            _text(623, 539, "Equal-volume shared access"),
        ]
    )
    return _svg_document(width, height, "HUST equal-volume access control", body)


def _provenance_path(path: Path, project_root: Path) -> str:
    resolved = path.resolve(strict=True)
    try:
        return resolved.relative_to(project_root.resolve(strict=True)).as_posix()
    except ValueError as exc:
        raise ValueError(f"paper input is outside the project root: {resolved}") from exc


def _manifest_input(path: Path, project_root: Path) -> dict[str, Any]:
    return {
        "path": _provenance_path(path, project_root),
        "sha256": sha256_file(path.resolve(strict=True)),
    }


def hust_influence_snapshot(frame: pd.DataFrame) -> dict[str, Any]:
    """Summarize the complete post-hoc HUST deletion audit without hiding unstable rows."""

    required = {
        "comparison",
        "method",
        "bearing_loo_minimum",
        "bearing_loo_sign_stable",
        "bearing_maximum_absolute_influence",
        "group_loo_minimum",
        "group_loo_sign_stable",
        "group_maximum_absolute_influence",
    }
    if not required.issubset(frame.columns) or len(frame) != 18:
        raise ValueError("HUST influence summary topology changed")
    expected_comparisons = {
        "recording_random_minus_crossed",
        "size_matched_shared_access_minus_crossed",
    }
    if (
        set(frame["comparison"].astype(str)) != expected_comparisons
        or set(frame["method"].astype(str)) != set(METHODS)
        or frame.duplicated(["comparison", "method"]).any()
    ):
        raise ValueError("HUST influence comparison/method keys changed")
    bearing_stable = frame["bearing_loo_sign_stable"].astype(bool)
    group_stable = frame["group_loo_sign_stable"].astype(bool)
    return {
        "method_comparison_count": int(len(frame)),
        "bearing_loo_sign_stable_count": int(bearing_stable.sum()),
        "group_loo_sign_stable_count": int(group_stable.sum()),
        "minimum_bearing_loo_effect": float(frame["bearing_loo_minimum"].min()),
        "minimum_group_loo_effect": float(frame["group_loo_minimum"].min()),
        "maximum_bearing_absolute_influence": float(
            frame["bearing_maximum_absolute_influence"].max()
        ),
        "maximum_group_absolute_influence": float(
            frame["group_maximum_absolute_influence"].max()
        ),
        "posthoc_sensitivity_not_confirmatory": True,
    }


def generate(
    *,
    paderborn_directory: Path,
    paderborn_summary_sha256: str,
    paderborn_validation: Path,
    paderborn_validation_sha256: str,
    sensor_directory: Path,
    sensor_summary_sha256: str,
    sensor_validation: Path,
    sensor_validation_sha256: str,
    hust_directory: Path,
    hust_summary_sha256: str,
    hust_validation: Path,
    hust_validation_sha256: str,
    hust_control_directory: Path,
    hust_control_summary_sha256: str,
    hust_control_validation: Path,
    hust_control_validation_sha256: str,
    hust_influence_directory: Path,
    hust_influence_summary_sha256: str,
    hust_influence_validation: Path,
    hust_influence_validation_sha256: str,
    raw_directory: Path,
    raw_summary_sha256: str,
    raw_window_directory: Path,
    raw_window_summary_sha256: str,
    raw_validation: Path,
    raw_validation_sha256: str,
    output_directory: Path,
    project_root: Path,
    release_input_mode: bool = False,
) -> dict[str, Any]:
    """Generate the complete hash-locked bearing manuscript artifact package.

    Release-input mode permits parent summaries to declare unconsumed raw or bulky outputs that
    are intentionally absent from the raw-data-free evidence archive. Summary bytes, every
    consumed CSV/provenance input, and all independent validations remain hash-locked.
    """

    verify_all_declared_outputs = not release_input_mode

    paderborn_directory, paderborn = load_summary(
        paderborn_directory,
        "neural_protocol_contrast_summary.json",
        paderborn_summary_sha256,
        "retrospective_development_not_confirmatory",
        verify_all_declared_outputs=verify_all_declared_outputs,
    )
    sensor_directory, sensor = load_summary(
        sensor_directory,
        "neural_sensor_attribution_summary.json",
        sensor_summary_sha256,
        "complete_retrospective_neural_sensor_attribution",
        verify_all_declared_outputs=verify_all_declared_outputs,
    )
    hust_directory, hust = load_summary(
        hust_directory,
        "hust_d3_summary.json",
        hust_summary_sha256,
        "one_shot_protocol_prospective_signal_unopened_before_seal",
        verify_all_declared_outputs=verify_all_declared_outputs,
    )
    hust_control_directory, hust_control = load_summary(
        hust_control_directory,
        "hust_d3_size_matched_summary.json",
        hust_control_summary_sha256,
        "outcome_blind_equal_source_volume_control",
        verify_all_declared_outputs=verify_all_declared_outputs,
    )
    hust_influence_directory, hust_influence = load_summary(
        hust_influence_directory,
        "hust_influence_audit_summary.json",
        hust_influence_summary_sha256,
        "posthoc_no_refit_physical_unit_influence_audit",
        verify_all_declared_outputs=verify_all_declared_outputs,
    )
    raw_directory, raw = load_summary(
        raw_directory,
        "raw_architecture_sensitivity_summary.json",
        raw_summary_sha256,
        "complete_retrospective_raw_architecture_sensitivity",
        verify_all_declared_outputs=verify_all_declared_outputs,
    )
    raw_window_directory, raw_window = load_summary(
        raw_window_directory,
        "raw_window_summary.json",
        raw_window_summary_sha256,
        "complete_hash_locked_paderborn_raw_window_artifact",
        verify_all_declared_outputs=verify_all_declared_outputs,
    )
    for artifact_name in ("window_index.parquet", "extraction_traces.json"):
        expected = raw_window["output_sha256"].get(artifact_name)
        if expected is None:
            raise ValueError(f"raw window summary does not lock {artifact_name}")
        _verify(
            raw_window_directory / artifact_name,
            str(expected),
            f"raw_window_summary.json/{artifact_name}",
        )
    if raw.get("inputs_sha256", {}).get("raw_window_summary") != raw_window_summary_sha256:
        raise ValueError("raw architecture summary does not consume the supplied window artifact")
    validations = {
        "paderborn_validation": (paderborn_validation, paderborn_validation_sha256),
        "sensor_validation": (sensor_validation, sensor_validation_sha256),
        "hust_validation": (hust_validation, hust_validation_sha256),
        "hust_control_validation": (
            hust_control_validation,
            hust_control_validation_sha256,
        ),
        "hust_influence_validation": (
            hust_influence_validation,
            hust_influence_validation_sha256,
        ),
        "raw_validation": (raw_validation, raw_validation_sha256),
    }
    for path, digest in validations.values():
        load_validation(path, digest)
    influence_validation = _load_json(
        hust_influence_validation,
        hust_influence_validation_sha256,
        "HUST influence independent validation",
    )
    if (
        influence_validation.get("audit_summary_sha256") != hust_influence_summary_sha256
        or influence_validation.get("confirmatory_analysis") is not False
        or influence_validation.get("p_values_computed") is not False
    ):
        raise ValueError("HUST influence validation scope or summary linkage changed")

    paderborn_aggregate = read_locked_csv(paderborn_directory, paderborn, "aggregate_metrics.csv")
    paderborn_bootstrap = read_locked_csv(paderborn_directory, paderborn, "bootstrap_summary.csv")
    sensor_aggregate = read_locked_csv(sensor_directory, sensor, "aggregate_metrics.csv")
    sensor_bootstrap = read_locked_csv(sensor_directory, sensor, "bootstrap_summary.csv")
    sensor_gap_differences = read_locked_csv(sensor_directory, sensor, "sensor_gap_differences.csv")
    sensor_score_differences = read_locked_csv(
        sensor_directory, sensor, "sensor_score_differences.csv"
    )
    hust_aggregate = read_locked_csv(hust_directory, hust, "aggregate_metrics.csv")
    hust_bootstrap = read_locked_csv(hust_directory, hust, "bootstrap_summary.csv")
    control_aggregate = read_locked_csv(
        hust_control_directory, hust_control, "aggregate_metrics.csv"
    )
    control_bootstrap = read_locked_csv(
        hust_control_directory, hust_control, "bootstrap_summary.csv"
    )
    hust_influence_table = read_locked_csv(
        hust_influence_directory, hust_influence, "hust_influence_summary.csv"
    )
    raw_aggregate = read_locked_csv(raw_directory, raw, "aggregate_metrics.csv")
    raw_bootstrap = read_locked_csv(raw_directory, raw, "bootstrap_summary.csv")
    fusion_score_difference = _maximum_matching_score_difference(
        paderborn_aggregate,
        sensor_aggregate.loc[sensor_aggregate["feature_family"] == "fusion"],
        index_columns=("protocol", "method"),
        role="Paderborn fusion summary cross-check",
    )
    hust_crossed_score_difference = _maximum_matching_score_difference(
        hust_aggregate.loc[hust_aggregate["protocol"] == "crossed_holdout"],
        control_aggregate.loc[control_aggregate["protocol"] == "crossed_holdout"],
        index_columns=("method",),
        role="HUST primary/control crossed-result reuse",
    )

    output_directory.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    generated.extend(
        write_table(
            access_contract_table(),
            output_directory / "bearing_table_00_access_contract",
        )
    )
    generated.extend(
        write_table(
            paderborn_protocol_table(paderborn_aggregate, paderborn_bootstrap),
            output_directory / "bearing_table_01_paderborn_protocols",
        )
    )
    generated.extend(
        write_table(
            sensor_attribution_table(sensor_aggregate, sensor_bootstrap),
            output_directory / "bearing_table_02_sensor_attribution",
        )
    )
    generated.extend(
        write_table(
            hust_protocol_table(
                hust_aggregate,
                hust_bootstrap,
                comparison_protocol="recording_random",
                include_four_protocols=True,
            ),
            output_directory / "bearing_table_03_hust_replication",
        )
    )
    generated.extend(
        write_table(
            hust_protocol_table(
                control_aggregate,
                control_bootstrap,
                comparison_protocol="size_matched_shared_access",
                include_four_protocols=False,
            ),
            output_directory / "bearing_table_04_hust_equal_volume_control",
        )
    )
    generated.extend(
        write_table(
            raw_architecture_table(raw_aggregate, raw_bootstrap),
            output_directory / "bearing_table_05_raw_architectures",
        )
    )
    generated.extend(
        write_table(
            sensor_gap_differences,
            output_directory / "bearing_table_s01_sensor_gap_differences",
        )
    )
    generated.extend(
        write_table(
            sensor_score_differences,
            output_directory / "bearing_table_s02_sensor_score_differences",
        )
    )
    generated.extend(
        write_table(
            selection_regret_table(sensor_aggregate, hust_aggregate, raw_aggregate),
            output_directory / "bearing_table_s03_selection_regret",
        )
    )
    generated.extend(
        write_table(
            hust_influence_table,
            output_directory / "bearing_table_s04_hust_physical_unit_influence",
        )
    )

    figures = {
        "bearing_figure_00_access_lattice.svg": access_lattice_svg(),
        "bearing_figure_01_protocol_profiles.svg": protocol_profile_svg(paderborn_aggregate),
        "bearing_figure_02_gap_forest.svg": gap_forest_svg(
            [
                (
                    "Paderborn fusion",
                    _effect_rows(paderborn_bootstrap, comparison="measurement_random"),
                ),
                (
                    "HUST D3",
                    _effect_rows(hust_bootstrap, comparison="recording_random"),
                ),
                (
                    "Raw architectures",
                    raw_bootstrap.loc[
                        (raw_bootstrap["comparison_protocol"] == "measurement_random")
                        & (raw_bootstrap["reference_protocol"] == "crossed_holdout")
                    ].copy(),
                ),
            ]
        ),
        "bearing_figure_03_sensor_gaps.svg": sensor_gap_svg(sensor_bootstrap),
        "bearing_figure_04_hust_equal_volume.svg": hust_control_svg(
            hust_bootstrap, control_bootstrap
        ),
    }
    for filename, content in figures.items():
        path = output_directory / filename
        path.write_text(content, encoding="utf-8")
        generated.append(path)
        pdf_path = path.with_suffix(".pdf")
        pdf_path.write_bytes(deterministic_pdf_from_svg(content))
        generated.append(pdf_path)

    captions_path = output_directory / "BEARING_FIGURE_CAPTIONS.md"
    captions_path.write_text(
        "# Bearing manuscript figure captions\n\n"
        "**Figure 1. Physical-access lattice.** The four protocol families form a "
        "two-axis access design: target physical identity/specification and target operating "
        "condition may each be represented or excluded from source data. The strict crossed "
        "protocol excludes both axes and quarantines both XOR cross-arms; all protocols withhold "
        "target records and labels.\n\n"
        "**Figure 2. Paderborn protocol sensitivity.** Pooled macro F1 for nine frozen "
        "methods under measurement-random, setting-held-out, identity-held-out, and "
        "simultaneously crossed identity-by-setting evaluation. All points use identical "
        "features, configurations, and seed ensembles. Methods are redundantly encoded by "
        "color, line dash, and marker shape for grayscale reproduction.\n\n"
        "**Figure 3. Accessible-split optimism across datasets and architectures.** Points "
        "are accessible-minus-crossed macro-F1 effects; horizontal lines are 95% percentile "
        "intervals from paired physical-bearing bootstrap resamples. Dataset/architecture "
        "groups use both color and marker shape.\n\n"
        "**Figure 4. Sensor-view protocol gaps.** Random-minus-crossed effects for vibration, "
        "motor-current, and fused feature families using one shared bearing bootstrap plan; "
        "sensor views use both color and marker shape.\n\n"
        "**Figure 5. HUST equal-volume access control.** The primary random-access effect is "
        "compared with a sealed control that holds target recordings and source-record count "
        "fixed while changing only which source recordings are accessible. Circle and square "
        "markers distinguish the two access designs independently of color.\n",
        encoding="utf-8",
    )
    generated.append(captions_path)

    table_captions_path = output_directory / "BEARING_TABLE_CAPTIONS.md"
    table_captions_path.write_text(
        "# Bearing manuscript table captions\n\n"
        "**Table 1. Physical-access contract.** Source, target, quarantine, and deployment "
        "semantics for the four protocol families. Identity denotes physical bearing identity "
        "on Paderborn and the matched-specification proxy on HUST.\n\n"
        "**Table 2. Paderborn fusion-feature protocol audit.** Pooled recording-level macro F1 "
        "for nine frozen methods under four access protocols, with random-minus-crossed effects "
        "and 95% physical-bearing percentile intervals.\n\n"
        "**Table 3. Paderborn sensor-view attribution.** Random and crossed pooled macro F1 and "
        "paired protocol gaps for vibration, motor-current, and fused features on the same 2,319 "
        "target records and 2,000 bearing-bootstrap draws.\n\n"
        "**Table 4. Sealed HUST replication.** Pooled recording-level macro F1 under recording-"
        "random, load-held-out, matched-specification-held-out, and strict crossed access, with "
        "5,000-draw physical-bearing intervals.\n\n"
        "**Table 5. HUST equal-source-volume control.** Shared-access and strict-crossed scores "
        "on identical targets with 24 source recordings in each arm; intervals resample physical "
        "bearings.\n\n"
        "**Table 6. Paderborn raw-architecture sensitivity.** Random and crossed pooled macro F1 "
        "for sealed raw-1D, log-FFT, and log-STFT CNNs, with 2,000-draw physical-bearing "
        "intervals.\n\n"
        "**Supplementary Table S1. Paired sensor-gap differences.** Differences between sensor "
        "families in random-minus-crossed macro F1 under one shared bearing-bootstrap plan.\n\n"
        "**Supplementary Table S2. Paired crossed-score differences.** Sensor-family differences "
        "in absolute crossed-holdout macro F1 under the shared bearing-bootstrap plan.\n\n"
        "**Supplementary Table S3. Finite-cohort model-selection regret.** Best crossed macro F1 "
        "minus the crossed score of every accessible-protocol empirical leader. Minimum and "
        "maximum regret are both reported when the accessible protocol has tied leaders.\n\n"
        "**Supplementary Table S4. Post-hoc HUST physical-unit influence audit.** Full, "
        "leave-one-bearing-out, and class-balanced leave-one-specification-group-out protocol "
        "effects for all nine methods and both access comparisons. Deletion ranges are "
        "sensitivity diagnostics, not confidence intervals or independent replicates.\n",
        encoding="utf-8",
    )
    generated.append(table_captions_path)

    summary_paths = {
        "paderborn_summary": paderborn_directory / "neural_protocol_contrast_summary.json",
        "sensor_summary": sensor_directory / "neural_sensor_attribution_summary.json",
        "hust_summary": hust_directory / "hust_d3_summary.json",
        "hust_control_summary": hust_control_directory / "hust_d3_size_matched_summary.json",
        "hust_influence_summary": hust_influence_directory
        / "hust_influence_audit_summary.json",
        "raw_summary": raw_directory / "raw_architecture_sensitivity_summary.json",
    }
    csv_paths = {
        "paderborn_aggregate": paderborn_directory / "aggregate_metrics.csv",
        "paderborn_bootstrap": paderborn_directory / "bootstrap_summary.csv",
        "sensor_aggregate": sensor_directory / "aggregate_metrics.csv",
        "sensor_bootstrap": sensor_directory / "bootstrap_summary.csv",
        "sensor_gap_differences": sensor_directory / "sensor_gap_differences.csv",
        "sensor_score_differences": sensor_directory / "sensor_score_differences.csv",
        "hust_aggregate": hust_directory / "aggregate_metrics.csv",
        "hust_bootstrap": hust_directory / "bootstrap_summary.csv",
        "hust_control_aggregate": hust_control_directory / "aggregate_metrics.csv",
        "hust_control_bootstrap": hust_control_directory / "bootstrap_summary.csv",
        "hust_influence_table": hust_influence_directory / "hust_influence_summary.csv",
        "raw_aggregate": raw_directory / "aggregate_metrics.csv",
        "raw_bootstrap": raw_directory / "bootstrap_summary.csv",
    }
    raw_window_paths = {
        "raw_window_provenance": raw_window_directory / "raw_window_summary.json",
        "raw_window_index": raw_window_directory / "window_index.parquet",
        "raw_extraction_traces": raw_window_directory / "extraction_traces.json",
    }
    paderborn_effects = _effect_rows(paderborn_bootstrap, comparison="measurement_random")
    hust_effects = _effect_rows(hust_bootstrap, comparison="recording_random")
    control_effects = _effect_rows(control_bootstrap, comparison="size_matched_shared_access")
    raw_effects = raw_bootstrap.loc[
        (raw_bootstrap["comparison_protocol"] == "measurement_random")
        & (raw_bootstrap["reference_protocol"] == "crossed_holdout")
    ]
    headline_values = {
        "paderborn_fusion": {
            "measurement_random_macro_f1": _protocol_range(
                paderborn_aggregate, "measurement_random"
            ),
            "crossed_holdout_macro_f1": _protocol_range(paderborn_aggregate, "crossed_holdout"),
            "random_minus_crossed": _effect_snapshot(
                paderborn_bootstrap,
                comparison="measurement_random",
                expected_methods=METHODS,
            ),
        },
        "paderborn_sensor_views": {
            family: {
                "measurement_random_macro_f1": _protocol_range(
                    sensor_aggregate.loc[sensor_aggregate["feature_family"] == family],
                    "measurement_random",
                ),
                "crossed_holdout_macro_f1": _protocol_range(
                    sensor_aggregate.loc[sensor_aggregate["feature_family"] == family],
                    "crossed_holdout",
                ),
                "random_minus_crossed": _effect_snapshot(
                    sensor_bootstrap.loc[sensor_bootstrap["feature_family"] == family],
                    comparison="measurement_random",
                    expected_methods=METHODS,
                ),
            }
            for family in SENSOR_FAMILIES
        },
        "hust_replication": {
            "recording_random_macro_f1": _protocol_range(hust_aggregate, "recording_random"),
            "crossed_holdout_macro_f1": _protocol_range(hust_aggregate, "crossed_holdout"),
            "random_minus_crossed": _effect_snapshot(
                hust_bootstrap,
                comparison="recording_random",
                expected_methods=METHODS,
            ),
        },
        "hust_equal_volume_control": {
            "shared_access_macro_f1": _protocol_range(
                control_aggregate, "size_matched_shared_access"
            ),
            "crossed_holdout_macro_f1": _protocol_range(control_aggregate, "crossed_holdout"),
            "shared_minus_crossed": _effect_snapshot(
                control_bootstrap,
                comparison="size_matched_shared_access",
                expected_methods=METHODS,
            ),
        },
        "hust_physical_unit_influence": hust_influence_snapshot(hust_influence_table),
        "paderborn_raw_architectures": {
            "measurement_random_macro_f1": _protocol_range(raw_aggregate, "measurement_random"),
            "crossed_holdout_macro_f1": _protocol_range(raw_aggregate, "crossed_holdout"),
            "random_minus_crossed": _effect_snapshot(
                raw_bootstrap,
                comparison="measurement_random",
                expected_methods=("cnn1d", "fft", "stft"),
            ),
        },
    }
    decision = {
        "paderborn_all_nine_gap_intervals_above_zero": bool(
            paderborn_effects["bootstrap_lower_95"].gt(0).all()
        ),
        "hust_all_nine_gap_intervals_above_zero": bool(
            hust_effects["bootstrap_lower_95"].gt(0).all()
        ),
        "hust_equal_volume_all_nine_intervals_above_zero": bool(
            control_effects["bootstrap_lower_95"].gt(0).all()
        ),
        "hust_influence_bearing_sign_stable_count": int(
            headline_values["hust_physical_unit_influence"][
                "bearing_loo_sign_stable_count"
            ]
        ),
        "hust_influence_group_sign_stable_count": int(
            headline_values["hust_physical_unit_influence"]["group_loo_sign_stable_count"]
        ),
        "raw_all_three_gap_intervals_above_zero": bool(
            raw_effects["bootstrap_lower_95"].gt(0).all()
        ),
        "raw_representation_sensitivity_rule_passed": bool(
            raw["findings"]["representation_sensitivity_rule_passed"]
        ),
        "raw_median_random_minus_crossed_macro_f1": float(
            raw["findings"]["median_random_minus_crossed_macro_f1"]
        ),
        "sensor_gap_difference_intervals_excluding_zero": int(
            sensor["findings"]["sensor_gap_difference_interval_excludes_zero"]
        ),
        "sensor_score_difference_intervals_excluding_zero": int(
            sensor["findings"]["sensor_score_difference_interval_excludes_zero"]
        ),
        "claim_scope": "protocol_sensitivity_and_access_attribution_not_method_superiority",
        "headline_values": headline_values,
        "maximum_paderborn_fusion_cross_summary_difference": fusion_score_difference,
        "maximum_hust_crossed_primary_control_difference": hust_crossed_score_difference,
    }
    inputs = {
        name: _manifest_input(path, project_root)
        for name, path in {**summary_paths, **csv_paths, **raw_window_paths}.items()
    }
    inputs.update(
        {name: _manifest_input(path, project_root) for name, (path, _) in validations.items()}
    )
    manifest = {
        "generator_version": GENERATOR_VERSION,
        "inputs": inputs,
        "decision": decision,
        "outputs": [
            {
                "path": path.name,
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(generated)
        ],
        "deterministic": True,
        "notes": [
            "Every numerical input is SHA-256 locked by both the CLI and its parent summary.",
            "All five model-result families and the post-hoc HUST influence audit passed "
            "independent no-refit validation.",
            "The raw-window provenance, row index, and extraction traces are included; the "
            "license-restricted NPY signal array is hash-locked but not redistributed.",
            "Selection regret is a finite-cohort descriptive range when accessible leaders tie.",
            "HUST deletion ranges are post-hoc influence diagnostics, not confidence intervals.",
            "Each audit-source SVG has a vector-PDF submission export with normalized metadata.",
            "The manifest excludes its own digest.",
        ],
    }
    manifest_path = output_directory / "bearing_artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return manifest
