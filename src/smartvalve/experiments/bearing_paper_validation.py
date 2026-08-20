"""Independently validate the final bearing-paper artifact manifest."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd
from defusedxml import ElementTree
from defusedxml.common import DefusedXmlException
from pypdf import PdfReader

VALIDATOR_VERSION = "smartvalve-bearing-paper-validator-0.4.1"
CSV_FLOAT_TOLERANCE = 1e-12
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
RAW_METHODS = ("cnn1d", "fft", "stft")
SENSOR_FAMILIES = ("vibration", "motor_current", "fusion")
EXPECTED_INPUTS = {
    "paderborn_summary",
    "sensor_summary",
    "hust_summary",
    "hust_control_summary",
    "hust_influence_summary",
    "raw_summary",
    "paderborn_aggregate",
    "paderborn_bootstrap",
    "sensor_aggregate",
    "sensor_bootstrap",
    "sensor_gap_differences",
    "sensor_score_differences",
    "hust_aggregate",
    "hust_bootstrap",
    "hust_control_aggregate",
    "hust_control_bootstrap",
    "hust_influence_table",
    "raw_aggregate",
    "raw_bootstrap",
    "raw_window_provenance",
    "raw_window_index",
    "raw_extraction_traces",
    "paderborn_validation",
    "sensor_validation",
    "hust_validation",
    "hust_control_validation",
    "hust_influence_validation",
    "raw_validation",
}
SUMMARY_STATUSES = {
    "paderborn_summary": "retrospective_development_not_confirmatory",
    "sensor_summary": "complete_retrospective_neural_sensor_attribution",
    "hust_summary": "one_shot_protocol_prospective_signal_unopened_before_seal",
    "hust_control_summary": "outcome_blind_equal_source_volume_control",
    "hust_influence_summary": "posthoc_no_refit_physical_unit_influence_audit",
    "raw_summary": "complete_retrospective_raw_architecture_sensitivity",
    "raw_window_provenance": "complete_hash_locked_paderborn_raw_window_artifact",
}
TABLE_STEMS = (
    "bearing_table_00_access_contract",
    "bearing_table_01_paderborn_protocols",
    "bearing_table_02_sensor_attribution",
    "bearing_table_03_hust_replication",
    "bearing_table_04_hust_equal_volume_control",
    "bearing_table_05_raw_architectures",
    "bearing_table_s01_sensor_gap_differences",
    "bearing_table_s02_sensor_score_differences",
    "bearing_table_s03_selection_regret",
    "bearing_table_s04_hust_physical_unit_influence",
)
EXPECTED_OUTPUTS = {
    *(f"{stem}.{suffix}" for stem in TABLE_STEMS for suffix in ("csv", "md", "tex")),
    *(
        f"bearing_figure_0{index}_{name}.svg"
        for index, name in enumerate(
            (
                "access_lattice",
                "protocol_profiles",
                "gap_forest",
                "sensor_gaps",
                "hust_equal_volume",
            )
        )
    ),
    *(
        f"bearing_figure_0{index}_{name}.pdf"
        for index, name in enumerate(
            (
                "access_lattice",
                "protocol_profiles",
                "gap_forest",
                "sensor_gaps",
                "hust_equal_volume",
            )
        )
    ),
    "BEARING_FIGURE_CAPTIONS.md",
    "BEARING_TABLE_CAPTIONS.md",
}
EXPECTED_TABLE_ROWS = {
    "bearing_table_00_access_contract.csv": 5,
    "bearing_table_01_paderborn_protocols.csv": 9,
    "bearing_table_02_sensor_attribution.csv": 27,
    "bearing_table_03_hust_replication.csv": 9,
    "bearing_table_04_hust_equal_volume_control.csv": 9,
    "bearing_table_05_raw_architectures.csv": 3,
    "bearing_table_s03_selection_regret.csv": 5,
    "bearing_table_s04_hust_physical_unit_influence.csv": 18,
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def _inside(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"artifact path escapes the project root: {relative}")
    resolved = (root / candidate).resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"artifact path escapes the project root: {relative}") from error
    if not resolved.is_file():
        raise ValueError(f"artifact input is not a file: {relative}")
    return resolved


def _locked_inputs(*, project_root: Path, inputs: Mapping[str, Any]) -> dict[str, Path]:
    if set(inputs) != EXPECTED_INPUTS:
        raise ValueError(
            f"bearing manifest input roles changed: expected {sorted(EXPECTED_INPUTS)}, "
            f"observed {sorted(inputs)}"
        )
    locked: dict[str, Path] = {}
    for role, item in inputs.items():
        if not isinstance(item, Mapping):
            raise ValueError(f"manifest input is not an object: {role}")
        relative = str(item.get("path", ""))
        if Path(relative).suffix.lower() in {".mat", ".npy", ".rar", ".zip", ".part"}:
            raise ValueError(f"raw/archive input is not redistributable: {relative}")
        path = _inside(project_root, relative)
        expected = str(item.get("sha256", ""))
        observed = _sha256_file(path)
        if observed != expected:
            raise ValueError(
                f"manifest input SHA-256 changed for {role}: expected {expected}, "
                f"observed {observed}"
            )
        locked[role] = path
    return locked


def _validate_no_refit_records(paths: Mapping[str, Path]) -> None:
    for role in sorted(name for name in paths if name.endswith("_validation")):
        value = _json_object(paths[role])
        if not str(value.get("status", "")).startswith("passed_independent"):
            raise ValueError(f"{role} is not an independent passing validation")
        if value.get("refit_performed") is not False:
            raise ValueError(f"{role} does not explicitly declare refit_performed=false")


def _validate_summary_outputs(paths: Mapping[str, Path]) -> None:
    for role, expected_status in SUMMARY_STATUSES.items():
        summary_path = paths[role]
        value = _json_object(summary_path)
        if value.get("status") != expected_status:
            raise ValueError(f"{role} completion status changed")
        outputs = value.get("output_sha256")
        if not isinstance(outputs, Mapping) or not outputs:
            raise ValueError(f"{role} has no output hash map")
        for filename, expected in outputs.items():
            artifact = _inside(summary_path.parent, str(filename))
            observed = _sha256_file(artifact)
            if observed != str(expected):
                raise ValueError(f"{role} output SHA-256 changed: {filename}")


def _validate_outputs(*, manifest_directory: Path, outputs: Any) -> dict[str, Path]:
    if not isinstance(outputs, list):
        raise ValueError("bearing manifest output table is not a list")
    by_name: dict[str, Path] = {}
    for item in outputs:
        if not isinstance(item, Mapping):
            raise ValueError("bearing manifest output is not an object")
        name = str(item.get("path", ""))
        if not name or Path(name).name != name or name in by_name:
            raise ValueError(f"bearing manifest output path is unsafe or duplicated: {name}")
        path = (manifest_directory / name).resolve(strict=True)
        if path.parent != manifest_directory:
            raise ValueError(f"bearing manifest output escapes its directory: {name}")
        expected_bytes = int(item.get("bytes", -1))
        if path.stat().st_size != expected_bytes:
            raise ValueError(f"bearing output byte count changed: {name}")
        observed = _sha256_file(path)
        if observed != str(item.get("sha256", "")):
            raise ValueError(f"bearing output SHA-256 changed: {name}")
        by_name[name] = path
    if set(by_name) != EXPECTED_OUTPUTS:
        raise ValueError(
            f"bearing manifest output set changed: expected {sorted(EXPECTED_OUTPUTS)}, "
            f"observed {sorted(by_name)}"
        )
    for name, expected_rows in EXPECTED_TABLE_ROWS.items():
        if len(pd.read_csv(by_name[name])) != expected_rows:
            raise ValueError(f"bearing table row count changed: {name}")
    svg_titles: dict[str, str] = {}
    for name, path in by_name.items():
        if name.endswith(".svg"):
            try:
                root = ElementTree.parse(path).getroot()
            except (ElementTree.ParseError, DefusedXmlException) as error:
                raise ValueError(f"bearing SVG is not valid XML: {name}") from error
            if not root.tag.endswith("svg"):
                raise ValueError(f"bearing SVG root changed: {name}")
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
                raise ValueError(f"bearing SVG title is missing: {name}")
            svg_titles[name] = title
    for name, path in by_name.items():
        if name.endswith(".pdf"):
            try:
                reader = PdfReader(path)
            except Exception as error:
                raise ValueError(f"bearing PDF is unreadable: {name}") from error
            if len(reader.pages) != 1:
                raise ValueError(f"bearing PDF page count changed: {name}")
            metadata = reader.metadata
            if metadata is None:
                raise ValueError(f"bearing PDF metadata is missing: {name}")
            if metadata.get("/CreationDate") != PDF_FIXED_TIMESTAMP:
                raise ValueError(f"bearing PDF creation timestamp changed: {name}")
            if metadata.get("/ModDate") != PDF_FIXED_TIMESTAMP:
                raise ValueError(f"bearing PDF modification timestamp changed: {name}")
            svg_name = f"{Path(name).stem}.svg"
            if metadata.get("/Title") != svg_titles[svg_name]:
                raise ValueError(f"bearing PDF title does not match its SVG source: {name}")
    protocol_svg = by_name["bearing_figure_01_protocol_profiles.svg"].read_text(encoding="utf-8")
    if "stroke-dasharray" not in protocol_svg or "data-marker-shape" not in protocol_svg:
        raise ValueError("protocol figure lacks redundant grayscale encodings")
    for name in (
        "bearing_figure_02_gap_forest.svg",
        "bearing_figure_03_sensor_gaps.svg",
        "bearing_figure_04_hust_equal_volume.svg",
    ):
        if "data-marker-shape" not in by_name[name].read_text(encoding="utf-8"):
            raise ValueError(f"bearing figure lacks a marker-shape channel: {name}")
    return by_name


def _score_range(frame: pd.DataFrame, protocol: str) -> dict[str, float]:
    values = frame.loc[frame["protocol"] == protocol, "pooled_macro_f1"].astype(float)
    if values.empty or not values.notna().all():
        raise ValueError(f"cannot recompute score range for {protocol}")
    return {"minimum": float(values.min()), "maximum": float(values.max())}


def _effect_snapshot(
    frame: pd.DataFrame, *, comparison: str, methods: Iterable[str]
) -> dict[str, Any]:
    method_order = tuple(methods)
    selected = frame.loc[
        (frame["comparison_protocol"] == comparison)
        & (frame["reference_protocol"] == "crossed_holdout")
    ].copy()
    if len(selected) != len(method_order) or set(selected["method"]) != set(method_order):
        raise ValueError(f"effect topology changed for {comparison}")
    selected = selected.set_index("method").loc[list(method_order)]
    effect = selected["effect_comparison_minus_reference"].astype(float)
    lower = selected["bootstrap_lower_95"].astype(float)
    upper = selected["bootstrap_upper_95"].astype(float)
    if not pd.concat((effect, lower, upper), axis=1).notna().all().all():
        raise ValueError(f"effect snapshot contains non-finite values for {comparison}")
    return {
        "effect_minimum": float(effect.min()),
        "effect_median": float(effect.median()),
        "effect_maximum": float(effect.max()),
        "interval_lower_minimum": float(lower.min()),
        "interval_upper_maximum": float(upper.max()),
        "all_interval_lower_limits_above_zero": bool(lower.gt(0).all()),
        "by_method": {
            method: {
                "effect": float(effect.loc[method]),
                "lower_95": float(lower.loc[method]),
                "upper_95": float(upper.loc[method]),
            }
            for method in method_order
        },
    }


def _maximum_score_difference(
    left: pd.DataFrame, right: pd.DataFrame, *, columns: tuple[str, ...]
) -> float:
    names = [*columns, "pooled_macro_f1"]
    left_values = left[names].set_index(list(columns)).sort_index()
    right_values = right[names].set_index(list(columns)).sort_index()
    if (
        not left_values.index.is_unique
        or not right_values.index.is_unique
        or not left_values.index.equals(right_values.index)
    ):
        raise ValueError("cross-summary score topology changed")
    return float(
        (
            left_values["pooled_macro_f1"].astype(float)
            - right_values["pooled_macro_f1"].astype(float)
        )
        .abs()
        .max()
    )


def _influence_snapshot(frame: pd.DataFrame) -> dict[str, Any]:
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
    if (
        set(frame["comparison"].astype(str))
        != {
            "recording_random_minus_crossed",
            "size_matched_shared_access_minus_crossed",
        }
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


def _expected_headlines(frames: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    paderborn = frames["paderborn_aggregate"]
    paderborn_bootstrap = frames["paderborn_bootstrap"]
    sensor = frames["sensor_aggregate"]
    sensor_bootstrap = frames["sensor_bootstrap"]
    hust = frames["hust_aggregate"]
    hust_bootstrap = frames["hust_bootstrap"]
    control = frames["hust_control_aggregate"]
    control_bootstrap = frames["hust_control_bootstrap"]
    influence = frames["hust_influence_table"]
    raw = frames["raw_aggregate"]
    raw_bootstrap = frames["raw_bootstrap"]
    return {
        "paderborn_fusion": {
            "measurement_random_macro_f1": _score_range(paderborn, "measurement_random"),
            "crossed_holdout_macro_f1": _score_range(paderborn, "crossed_holdout"),
            "random_minus_crossed": _effect_snapshot(
                paderborn_bootstrap, comparison="measurement_random", methods=METHODS
            ),
        },
        "paderborn_sensor_views": {
            family: {
                "measurement_random_macro_f1": _score_range(
                    sensor.loc[sensor["feature_family"] == family], "measurement_random"
                ),
                "crossed_holdout_macro_f1": _score_range(
                    sensor.loc[sensor["feature_family"] == family], "crossed_holdout"
                ),
                "random_minus_crossed": _effect_snapshot(
                    sensor_bootstrap.loc[sensor_bootstrap["feature_family"] == family],
                    comparison="measurement_random",
                    methods=METHODS,
                ),
            }
            for family in SENSOR_FAMILIES
        },
        "hust_replication": {
            "recording_random_macro_f1": _score_range(hust, "recording_random"),
            "crossed_holdout_macro_f1": _score_range(hust, "crossed_holdout"),
            "random_minus_crossed": _effect_snapshot(
                hust_bootstrap, comparison="recording_random", methods=METHODS
            ),
        },
        "hust_equal_volume_control": {
            "shared_access_macro_f1": _score_range(control, "size_matched_shared_access"),
            "crossed_holdout_macro_f1": _score_range(control, "crossed_holdout"),
            "shared_minus_crossed": _effect_snapshot(
                control_bootstrap,
                comparison="size_matched_shared_access",
                methods=METHODS,
            ),
        },
        "hust_physical_unit_influence": _influence_snapshot(influence),
        "paderborn_raw_architectures": {
            "measurement_random_macro_f1": _score_range(raw, "measurement_random"),
            "crossed_holdout_macro_f1": _score_range(raw, "crossed_holdout"),
            "random_minus_crossed": _effect_snapshot(
                raw_bootstrap, comparison="measurement_random", methods=RAW_METHODS
            ),
        },
    }


def validate_bearing_paper_artifacts(
    *,
    manifest_path: Path,
    expected_manifest_sha256: str,
    project_root: Path,
    release_input_mode: bool = False,
) -> dict[str, Any]:
    """Recompute the final package decisions without invoking the artifact generator.

    Release-input mode verifies all 28 manifest inputs and recomputes every package decision but
    does not require unrelated outputs merely declared by their parent summaries. Those may be raw
    or bulky files intentionally omitted from the evidence archive.
    """

    root = project_root.resolve(strict=True)
    manifest_path = manifest_path.resolve(strict=True)
    if _sha256_file(manifest_path) != expected_manifest_sha256:
        raise ValueError("bearing artifact manifest SHA-256 changed")
    manifest = _json_object(manifest_path)
    if manifest.get("deterministic") is not True:
        raise ValueError("bearing artifact manifest is not deterministic")
    if not str(manifest.get("generator_version", "")).startswith(
        "smartvalve-bearing-paper-artifacts-"
    ):
        raise ValueError("bearing artifact generator version is not recognized")
    inputs = manifest.get("inputs")
    if not isinstance(inputs, Mapping):
        raise ValueError("bearing artifact manifest input table is not an object")
    locked = _locked_inputs(project_root=root, inputs=inputs)
    _validate_no_refit_records(locked)
    if not release_input_mode:
        _validate_summary_outputs(locked)
    raw_summary = _json_object(locked["raw_summary"])
    if raw_summary.get("inputs_sha256", {}).get("raw_window_summary") != _sha256_file(
        locked["raw_window_provenance"]
    ):
        raise ValueError("raw architecture summary does not consume the locked window artifact")
    outputs = _validate_outputs(
        manifest_directory=manifest_path.parent, outputs=manifest.get("outputs")
    )
    frames = {
        role: pd.read_csv(path)
        for role, path in locked.items()
        if role.endswith("_aggregate") or role.endswith("_bootstrap")
    }
    frames["hust_influence_table"] = pd.read_csv(locked["hust_influence_table"])
    expected_headlines = _expected_headlines(frames)
    decision = manifest.get("decision")
    if not isinstance(decision, Mapping):
        raise ValueError("bearing artifact manifest decision is not an object")
    if decision.get("headline_values") != expected_headlines:
        raise ValueError("bearing artifact headline values do not independently recompute")

    paderborn_effects = expected_headlines["paderborn_fusion"]["random_minus_crossed"]
    hust_effects = expected_headlines["hust_replication"]["random_minus_crossed"]
    control_effects = expected_headlines["hust_equal_volume_control"]["shared_minus_crossed"]
    raw_effects = expected_headlines["paderborn_raw_architectures"]["random_minus_crossed"]
    sensor_summary = _json_object(locked["sensor_summary"])
    influence_summary = _json_object(locked["hust_influence_summary"])
    influence_validation = _json_object(locked["hust_influence_validation"])
    raw_summary_median = float(
        raw_summary["findings"]["median_random_minus_crossed_macro_f1"]
    )
    raw_csv_median = float(raw_effects["effect_median"])
    raw_median_summary_csv_difference = abs(raw_summary_median - raw_csv_median)
    if raw_median_summary_csv_difference > CSV_FLOAT_TOLERANCE:
        raise ValueError("raw median summary and serialized CSV recomputation differ")
    if (
        influence_summary.get("refit_performed") is not False
        or influence_summary.get("p_values_computed") is not False
        or influence_summary.get("primary_endpoints_replaced") is not False
        or influence_validation.get("audit_summary_sha256")
        != _sha256_file(locked["hust_influence_summary"])
        or influence_validation.get("confirmatory_analysis") is not False
        or influence_validation.get("p_values_computed") is not False
    ):
        raise ValueError("HUST influence audit scope or validation linkage changed")
    expected_decisions = {
        "paderborn_all_nine_gap_intervals_above_zero": paderborn_effects[
            "all_interval_lower_limits_above_zero"
        ],
        "hust_all_nine_gap_intervals_above_zero": hust_effects[
            "all_interval_lower_limits_above_zero"
        ],
        "hust_equal_volume_all_nine_intervals_above_zero": control_effects[
            "all_interval_lower_limits_above_zero"
        ],
        "hust_influence_bearing_sign_stable_count": expected_headlines[
            "hust_physical_unit_influence"
        ]["bearing_loo_sign_stable_count"],
        "hust_influence_group_sign_stable_count": expected_headlines[
            "hust_physical_unit_influence"
        ]["group_loo_sign_stable_count"],
        "raw_all_three_gap_intervals_above_zero": raw_effects[
            "all_interval_lower_limits_above_zero"
        ],
        "raw_representation_sensitivity_rule_passed": bool(
            raw_summary["findings"]["representation_sensitivity_rule_passed"]
        ),
        "raw_median_random_minus_crossed_macro_f1": raw_summary_median,
        "sensor_gap_difference_intervals_excluding_zero": int(
            sensor_summary["findings"]["sensor_gap_difference_interval_excludes_zero"]
        ),
        "sensor_score_difference_intervals_excluding_zero": int(
            sensor_summary["findings"]["sensor_score_difference_interval_excludes_zero"]
        ),
        "claim_scope": "protocol_sensitivity_and_access_attribution_not_method_superiority",
    }
    for name, expected in expected_decisions.items():
        if decision.get(name) != expected:
            raise ValueError(f"bearing artifact decision changed: {name}")

    fusion_difference = _maximum_score_difference(
        frames["paderborn_aggregate"],
        frames["sensor_aggregate"].loc[frames["sensor_aggregate"]["feature_family"] == "fusion"],
        columns=("protocol", "method"),
    )
    hust_difference = _maximum_score_difference(
        frames["hust_aggregate"].loc[frames["hust_aggregate"]["protocol"] == "crossed_holdout"],
        frames["hust_control_aggregate"].loc[
            frames["hust_control_aggregate"]["protocol"] == "crossed_holdout"
        ],
        columns=("method",),
    )
    if fusion_difference > 1e-12 or hust_difference > 1e-12:
        raise ValueError("bearing cross-summary scores are inconsistent")
    if decision.get("maximum_paderborn_fusion_cross_summary_difference") != fusion_difference:
        raise ValueError("Paderborn cross-summary difference does not recompute")
    if decision.get("maximum_hust_crossed_primary_control_difference") != hust_difference:
        raise ValueError("HUST cross-summary difference does not recompute")

    result = {
        "status": "passed_independent_bearing_paper_artifact_validation",
        "validator_version": VALIDATOR_VERSION,
        "manifest_sha256": expected_manifest_sha256,
        "input_count": len(locked),
        "output_count": len(outputs),
        "independent_no_refit_validation_count": 6,
        "headline_values_recomputed": True,
        "cross_summary_scores_identical": True,
        "raw_median_summary_csv_difference": raw_median_summary_csv_difference,
        "raw_dataset_files_in_manifest": False,
        "svg_count": sum(name.endswith(".svg") for name in outputs),
        "submission_pdf_count": sum(name.endswith(".pdf") for name in outputs),
        "refit_performed": False,
    }
    if release_input_mode:
        result.update(
            {
                "release_input_mode": True,
                "all_consumed_manifest_inputs_verified": True,
                "unconsumed_parent_summary_outputs_verified": False,
            }
        )
    return result
