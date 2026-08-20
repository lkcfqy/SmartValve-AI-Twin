from __future__ import annotations

import io
import json
from pathlib import Path
from xml.etree import ElementTree

import pandas as pd
import pytest
from pypdf import PdfReader, PdfWriter

from smartvalve.experiments.bearing_paper_artifacts import (
    HUST_PROTOCOLS,
    METHOD_LINE_STYLES,
    METHODS,
    PADERBORN_PROTOCOLS,
    SENSOR_FAMILIES,
    access_contract_table,
    access_lattice_svg,
    deterministic_pdf_from_svg,
    generate,
    hust_control_svg,
    hust_protocol_table,
    load_validation,
    paderborn_protocol_table,
    protocol_profile_svg,
    raw_architecture_table,
    selection_regret_table,
    sensor_attribution_table,
    sensor_gap_svg,
    sha256_file,
)
from smartvalve.experiments.bearing_paper_validation import (
    validate_bearing_paper_artifacts,
)


def _aggregate(protocols: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "protocol": protocol,
                "method": method,
                "pooled_macro_f1": 0.95 - 0.1 * protocol_index - method_index / 100,
            }
            for protocol_index, protocol in enumerate(protocols)
            for method_index, method in enumerate(METHODS)
        ]
    )


def _effects(comparison: str) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "comparison_protocol": comparison,
                "reference_protocol": "crossed_holdout",
                "method": method,
                "metric": "pooled_macro_f1",
                "effect_comparison_minus_reference": 0.3 + index / 100,
                "bootstrap_lower_95": 0.2 + index / 100,
                "bootstrap_upper_95": 0.4 + index / 100,
            }
            for index, method in enumerate(METHODS)
        ]
    )


def _influence_summary() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "comparison": comparison,
                "method": method,
                "full_effect_macro_f1": 0.25,
                "bearing_loo_minimum": 0.17 + method_index / 1000,
                "bearing_loo_median": 0.24,
                "bearing_loo_maximum": 0.28,
                "bearing_loo_positive_count": 15,
                "bearing_loo_sign_stable": True,
                "bearing_maximum_absolute_influence": 0.05,
                "group_loo_minimum": 0.11 + method_index / 1000,
                "group_loo_median": 0.25,
                "group_loo_maximum": 0.32,
                "group_loo_positive_count": 5,
                "group_loo_sign_stable": True,
                "group_maximum_absolute_influence": 0.11,
            }
            for comparison in (
                "recording_random_minus_crossed",
                "size_matched_shared_access_minus_crossed",
            )
            for method_index, method in enumerate(METHODS)
        ]
    )


def test_paderborn_protocol_table_preserves_all_frozen_cells() -> None:
    table = paderborn_protocol_table(
        _aggregate(PADERBORN_PROTOCOLS),
        _effects("measurement_random"),
    )

    assert len(table) == 9
    assert table["Random - crossed"].min() == pytest.approx(0.3)
    assert table["CI95 low"].gt(0).all()


def test_access_contract_and_lattice_cover_all_four_access_codes() -> None:
    table = access_contract_table()
    root = ElementTree.fromstring(access_lattice_svg())

    assert set(table["Access code"]) == {"I+ C+", "I+ C-", "I- C+", "I- C-"}
    assert len(table.loc[table["Protocol family"] == "Crossed holdout"]) == 1
    assert root.tag.endswith("svg")


def test_svg_pdf_export_is_one_page_and_bitwise_deterministic() -> None:
    svg = access_lattice_svg()

    first = deterministic_pdf_from_svg(svg)
    second = deterministic_pdf_from_svg(svg)
    reader = PdfReader(io.BytesIO(first))

    assert first == second
    assert len(reader.pages) == 1
    assert reader.metadata.title == "Physical-access lattice"
    assert reader.metadata.creation_date is not None
    assert reader.metadata.modification_date is not None


def test_svg_pdf_export_rejects_xml_entities() -> None:
    malicious = (
        '<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
        '<svg xmlns="http://www.w3.org/2000/svg"><title>&xxe;</title></svg>'
    )

    with pytest.raises(ValueError, match="malformed SVG"):
        deterministic_pdf_from_svg(malicious)


def test_sensor_table_and_figure_use_all_three_views() -> None:
    aggregate = pd.concat(
        [
            _aggregate(PADERBORN_PROTOCOLS).assign(feature_family=family)
            for family in SENSOR_FAMILIES
        ],
        ignore_index=True,
    )
    bootstrap = pd.concat(
        [
            _effects("measurement_random").assign(feature_family=family)
            for family in SENSOR_FAMILIES
        ],
        ignore_index=True,
    )

    table = sensor_attribution_table(aggregate, bootstrap)
    svg = sensor_gap_svg(bootstrap)
    root = ElementTree.fromstring(svg)

    assert len(table) == 27
    assert set(table["Sensor view"]) == set(SENSOR_FAMILIES)
    assert root.tag.endswith("svg")
    assert 'data-marker-shape="circle"' in svg
    assert 'data-marker-shape="square"' in svg
    assert 'data-marker-shape="diamond"' in svg


def test_hust_primary_and_control_tables_are_distinct_designs() -> None:
    primary = _aggregate(HUST_PROTOCOLS)
    primary_effects = _effects("recording_random")
    control_protocols = ("size_matched_shared_access", "crossed_holdout")
    control = _aggregate(control_protocols)
    control_effects = _effects("size_matched_shared_access")

    primary_table = hust_protocol_table(
        primary,
        primary_effects,
        comparison_protocol="recording_random",
        include_four_protocols=True,
    )
    control_table = hust_protocol_table(
        control,
        control_effects,
        comparison_protocol="size_matched_shared_access",
        include_four_protocols=False,
    )
    svg = hust_control_svg(primary_effects, control_effects)
    root = ElementTree.fromstring(svg)

    assert "Matched-spec holdout" in primary_table
    assert "Matched-spec holdout" not in control_table
    assert len(primary_table) == len(control_table) == 9
    assert root.tag.endswith("svg")
    assert 'data-marker-shape="circle"' in svg
    assert 'data-marker-shape="square"' in svg


def test_raw_architecture_table_and_protocol_profile_are_valid() -> None:
    raw_models = ("cnn1d", "fft", "stft")
    aggregate = pd.DataFrame(
        [
            {
                "protocol": protocol,
                "method": model,
                "pooled_macro_f1": 0.9 - protocol_index * 0.4 - model_index / 100,
            }
            for protocol_index, protocol in enumerate(("measurement_random", "crossed_holdout"))
            for model_index, model in enumerate(raw_models)
        ]
    )
    effects = pd.DataFrame(
        [
            {
                "comparison_protocol": "measurement_random",
                "reference_protocol": "crossed_holdout",
                "method": model,
                "effect_comparison_minus_reference": 0.4,
                "bootstrap_lower_95": 0.3,
                "bootstrap_upper_95": 0.5,
            }
            for model in raw_models
        ]
    )

    raw_table = raw_architecture_table(aggregate, effects)
    profile_svg = protocol_profile_svg(_aggregate(PADERBORN_PROTOCOLS))
    profile_root = ElementTree.fromstring(profile_svg)

    assert len(raw_table) == 3
    assert raw_table["CI95 low"].gt(0).all()
    assert profile_root.tag.endswith("svg")
    assert "stroke-dasharray" in profile_svg
    assert 'data-marker-shape="triangle"' in profile_svg
    assert len(set(METHOD_LINE_STYLES.values())) == len(METHOD_LINE_STYLES)
    assert METHOD_LINE_STYLES["groupdro"][1] != METHOD_LINE_STYLES["ccdg"][1]


def test_selection_regret_preserves_unique_leaders_and_accessible_ties() -> None:
    sensor = pd.concat(
        [
            _aggregate(PADERBORN_PROTOCOLS).assign(feature_family=family)
            for family in SENSOR_FAMILIES
        ],
        ignore_index=True,
    )
    hust = _aggregate(HUST_PROTOCOLS)
    hust.loc[hust["protocol"] == "recording_random", "pooled_macro_f1"] = 1.0
    raw_models = ("cnn1d", "fft", "stft")
    raw = pd.DataFrame(
        [
            {
                "protocol": protocol,
                "method": model,
                "pooled_macro_f1": score,
            }
            for protocol, values in (
                ("measurement_random", (0.95, 0.90, 0.85)),
                ("crossed_holdout", (0.60, 0.75, 0.65)),
            )
            for model, score in zip(raw_models, values, strict=True)
        ]
    )

    table = selection_regret_table(sensor, hust, raw)
    raw_row = table.loc[table["Study view"] == "Paderborn raw architectures"].iloc[0]
    hust_row = table.loc[table["Study view"] == "HUST D3"].iloc[0]

    assert len(table) == 5
    assert raw_row["Accessible-optimal method(s)"] == "Raw 1D CNN"
    assert raw_row["Crossed-optimal method(s)"] == "FFT CNN"
    assert raw_row["Crossed regret min"] == pytest.approx(0.15)
    assert raw_row["Crossed regret max"] == pytest.approx(0.15)
    assert hust_row["Accessible leader count"] == len(METHODS)
    assert hust_row["Crossed regret min"] == pytest.approx(0.0)
    assert hust_row["Crossed regret max"] > 0.0


def test_protocol_table_rejects_missing_method() -> None:
    aggregate = _aggregate(PADERBORN_PROTOCOLS)

    with pytest.raises(ValueError, match="method axis changed"):
        paderborn_protocol_table(
            aggregate.loc[aggregate["method"] != "ccdg"],
            _effects("measurement_random"),
        )


def test_validation_requires_an_explicit_no_refit_declaration(tmp_path: Path) -> None:
    path = tmp_path / "validation.json"
    path.write_text(
        json.dumps({"status": "passed_independent_no_refit_recomputation"}) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="explicitly declare refit_performed=false"):
        load_validation(path, sha256_file(path))


def _write_summary(
    directory: Path,
    filename: str,
    status: str,
    frames: dict[str, pd.DataFrame],
    *,
    findings: dict[str, object] | None = None,
) -> str:
    directory.mkdir()
    output_hashes = {}
    for artifact_name, frame in frames.items():
        path = directory / artifact_name
        frame.to_csv(path, index=False)
        output_hashes[artifact_name] = sha256_file(path)
    summary = {
        "status": status,
        "output_sha256": output_hashes,
        "findings": findings or {},
    }
    summary_path = directory / filename
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return sha256_file(summary_path)


def _write_validation(directory: Path, name: str) -> tuple[Path, str]:
    path = directory / f"{name}_validation.json"
    path.write_text(
        json.dumps(
            {
                "status": "passed_independent_no_refit_recomputation",
                "refit_performed": False,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path, sha256_file(path)


def _write_raw_window_summary(directory: Path) -> str:
    directory.mkdir()
    outputs = {
        "vibration_windows.npy": b"raw signal placeholder for digest verification\n",
        "window_index.parquet": b"locked window index\n",
        "extraction_traces.json": b"{}\n",
    }
    for filename, content in outputs.items():
        (directory / filename).write_bytes(content)
    summary = {
        "status": "complete_hash_locked_paderborn_raw_window_artifact",
        "output_sha256": {
            filename: sha256_file(directory / filename) for filename in sorted(outputs)
        },
    }
    path = directory / "raw_window_summary.json"
    path.write_text(json.dumps(summary, sort_keys=True) + "\n", encoding="utf-8")
    return sha256_file(path)


def test_generate_builds_one_hash_locked_disjoint_package(tmp_path: Path) -> None:
    paderborn_dir = tmp_path / "paderborn"
    paderborn_sha = _write_summary(
        paderborn_dir,
        "neural_protocol_contrast_summary.json",
        "retrospective_development_not_confirmatory",
        {
            "aggregate_metrics.csv": _aggregate(PADERBORN_PROTOCOLS),
            "bootstrap_summary.csv": _effects("measurement_random"),
        },
    )
    sensor_dir = tmp_path / "sensor"
    sensor_aggregate = pd.concat(
        [
            _aggregate(PADERBORN_PROTOCOLS).assign(feature_family=family)
            for family in SENSOR_FAMILIES
        ],
        ignore_index=True,
    )
    sensor_effects = pd.concat(
        [
            _effects("measurement_random").assign(feature_family=family)
            for family in SENSOR_FAMILIES
        ],
        ignore_index=True,
    )
    difference = pd.DataFrame(
        {
            "left_feature_family": ["vibration"],
            "right_feature_family": ["fusion"],
            "effect_left_minus_right": [0.1],
            "bootstrap_lower_95": [0.01],
            "bootstrap_upper_95": [0.2],
        }
    )
    sensor_sha = _write_summary(
        sensor_dir,
        "neural_sensor_attribution_summary.json",
        "complete_retrospective_neural_sensor_attribution",
        {
            "aggregate_metrics.csv": sensor_aggregate,
            "bootstrap_summary.csv": sensor_effects,
            "sensor_gap_differences.csv": difference,
            "sensor_score_differences.csv": difference,
        },
        findings={
            "sensor_gap_difference_interval_excludes_zero": 1,
            "sensor_score_difference_interval_excludes_zero": 1,
        },
    )
    hust_dir = tmp_path / "hust"
    hust_aggregate = _aggregate(HUST_PROTOCOLS)
    hust_sha = _write_summary(
        hust_dir,
        "hust_d3_summary.json",
        "one_shot_protocol_prospective_signal_unopened_before_seal",
        {
            "aggregate_metrics.csv": hust_aggregate,
            "bootstrap_summary.csv": _effects("recording_random"),
        },
    )
    control_dir = tmp_path / "control"
    control_aggregate = _aggregate(("size_matched_shared_access", "crossed_holdout"))
    crossed_scores = hust_aggregate.loc[hust_aggregate["protocol"] == "crossed_holdout"].set_index(
        "method"
    )["pooled_macro_f1"]
    crossed_mask = control_aggregate["protocol"] == "crossed_holdout"
    control_aggregate.loc[crossed_mask, "pooled_macro_f1"] = control_aggregate.loc[
        crossed_mask, "method"
    ].map(crossed_scores)
    control_sha = _write_summary(
        control_dir,
        "hust_d3_size_matched_summary.json",
        "outcome_blind_equal_source_volume_control",
        {
            "aggregate_metrics.csv": control_aggregate,
            "bootstrap_summary.csv": _effects("size_matched_shared_access"),
        },
    )
    influence_dir = tmp_path / "influence"
    influence_sha = _write_summary(
        influence_dir,
        "hust_influence_audit_summary.json",
        "posthoc_no_refit_physical_unit_influence_audit",
        {"hust_influence_summary.csv": _influence_summary()},
    )
    influence_summary_path = influence_dir / "hust_influence_audit_summary.json"
    influence_summary_value = json.loads(
        influence_summary_path.read_text(encoding="utf-8")
    )
    influence_summary_value.update(
        {
            "refit_performed": False,
            "p_values_computed": False,
            "primary_endpoints_replaced": False,
        }
    )
    influence_summary_path.write_text(
        json.dumps(influence_summary_value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    influence_sha = sha256_file(influence_summary_path)
    raw_window_dir = tmp_path / "raw-window"
    raw_window_sha = _write_raw_window_summary(raw_window_dir)
    raw_dir = tmp_path / "raw"
    raw_models = ("cnn1d", "fft", "stft")
    raw_aggregate = pd.DataFrame(
        [
            {
                "protocol": protocol,
                "method": model,
                "pooled_macro_f1": 0.9 - protocol_index * 0.4,
            }
            for protocol_index, protocol in enumerate(("measurement_random", "crossed_holdout"))
            for model in raw_models
        ]
    )
    raw_effects = pd.DataFrame(
        [
            {
                "comparison_protocol": "measurement_random",
                "reference_protocol": "crossed_holdout",
                "method": model,
                "effect_comparison_minus_reference": 0.4,
                "bootstrap_lower_95": 0.3,
                "bootstrap_upper_95": 0.5,
            }
            for model in raw_models
        ]
    )
    raw_sha = _write_summary(
        raw_dir,
        "raw_architecture_sensitivity_summary.json",
        "complete_retrospective_raw_architecture_sensitivity",
        {
            "aggregate_metrics.csv": raw_aggregate,
            "bootstrap_summary.csv": raw_effects,
        },
        findings={
            "representation_sensitivity_rule_passed": True,
            "median_random_minus_crossed_macro_f1": 0.4,
        },
    )
    raw_summary_path = raw_dir / "raw_architecture_sensitivity_summary.json"
    raw_summary = json.loads(raw_summary_path.read_text(encoding="utf-8"))
    raw_summary["inputs_sha256"] = {"raw_window_summary": raw_window_sha}
    raw_summary_path.write_text(
        json.dumps(raw_summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raw_sha = sha256_file(raw_summary_path)
    validations = {
        name: _write_validation(tmp_path, name)
        for name in ("paderborn", "sensor", "hust", "control", "raw")
    }
    influence_validation_path = tmp_path / "influence_validation.json"
    influence_validation_path.write_text(
        json.dumps(
            {
                "status": (
                    "passed_independent_no_refit_hust_physical_unit_"
                    "influence_validation"
                ),
                "refit_performed": False,
                "confirmatory_analysis": False,
                "p_values_computed": False,
                "audit_summary_sha256": influence_sha,
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    validations["influence"] = (
        influence_validation_path,
        sha256_file(influence_validation_path),
    )
    output = tmp_path / "generated"

    def generate_package(
        output_directory: Path, *, release_input_mode: bool = False
    ) -> dict[str, object]:
        return generate(
            paderborn_directory=paderborn_dir,
            paderborn_summary_sha256=paderborn_sha,
            paderborn_validation=validations["paderborn"][0],
            paderborn_validation_sha256=validations["paderborn"][1],
            sensor_directory=sensor_dir,
            sensor_summary_sha256=sensor_sha,
            sensor_validation=validations["sensor"][0],
            sensor_validation_sha256=validations["sensor"][1],
            hust_directory=hust_dir,
            hust_summary_sha256=hust_sha,
            hust_validation=validations["hust"][0],
            hust_validation_sha256=validations["hust"][1],
            hust_control_directory=control_dir,
            hust_control_summary_sha256=control_sha,
            hust_control_validation=validations["control"][0],
            hust_control_validation_sha256=validations["control"][1],
            hust_influence_directory=influence_dir,
            hust_influence_summary_sha256=influence_sha,
            hust_influence_validation=validations["influence"][0],
            hust_influence_validation_sha256=validations["influence"][1],
            raw_directory=raw_dir,
            raw_summary_sha256=raw_sha,
            raw_window_directory=raw_window_dir,
            raw_window_summary_sha256=raw_window_sha,
            raw_validation=validations["raw"][0],
            raw_validation_sha256=validations["raw"][1],
            output_directory=output_directory,
            project_root=tmp_path,
            release_input_mode=release_input_mode,
        )

    manifest = generate_package(output)

    assert manifest["deterministic"] is True
    assert manifest["decision"]["paderborn_all_nine_gap_intervals_above_zero"]
    assert manifest["decision"]["raw_all_three_gap_intervals_above_zero"]
    assert manifest["decision"]["raw_representation_sensitivity_rule_passed"]
    assert manifest["decision"]["maximum_paderborn_fusion_cross_summary_difference"] == 0.0
    assert manifest["decision"]["maximum_hust_crossed_primary_control_difference"] == 0.0
    headlines = manifest["decision"]["headline_values"]
    paderborn_random = headlines["paderborn_fusion"]["measurement_random_macro_f1"]
    assert paderborn_random["minimum"] == pytest.approx(0.87)
    assert paderborn_random["maximum"] == pytest.approx(0.95)
    assert set(headlines["paderborn_sensor_views"]) == set(SENSOR_FAMILIES)
    assert all(
        item["random_minus_crossed"]["all_interval_lower_limits_above_zero"]
        for item in headlines["paderborn_sensor_views"].values()
    )
    raw_snapshot = headlines["paderborn_raw_architectures"]["random_minus_crossed"]
    assert raw_snapshot["effect_median"] == pytest.approx(0.4)
    assert raw_snapshot["all_interval_lower_limits_above_zero"] is True
    assert set(raw_snapshot["by_method"]) == {"cnn1d", "fft", "stft"}
    influence_snapshot = headlines["hust_physical_unit_influence"]
    assert influence_snapshot["bearing_loo_sign_stable_count"] == 18
    assert influence_snapshot["group_loo_sign_stable_count"] == 18
    assert influence_snapshot["minimum_bearing_loo_effect"] == pytest.approx(0.17)
    assert len(manifest["outputs"]) == 42
    output_names = {item["path"] for item in manifest["outputs"]}
    assert "bearing_table_00_access_contract.csv" in output_names
    assert "bearing_table_s03_selection_regret.csv" in output_names
    assert "bearing_table_s04_hust_physical_unit_influence.csv" in output_names
    assert "bearing_figure_00_access_lattice.svg" in output_names
    assert "bearing_figure_00_access_lattice.pdf" in output_names
    assert "raw_window_provenance" in manifest["inputs"]
    assert "raw_window_index" in manifest["inputs"]
    assert not any(item["path"].endswith(".npy") for item in manifest["inputs"].values())
    captions = (output / "BEARING_FIGURE_CAPTIONS.md").read_text(encoding="utf-8")
    assert "Figure 0." not in captions
    assert all(f"Figure {number}." in captions for number in range(1, 6))
    table_captions = (output / "BEARING_TABLE_CAPTIONS.md").read_text(encoding="utf-8")
    assert all(f"Table {number}." in table_captions for number in range(1, 7))
    assert all(f"Table S{number}." in table_captions for number in range(1, 5))
    for svg_path in output.glob("*.svg"):
        assert not set("–—‑−") & set(svg_path.read_text(encoding="utf-8"))
    for item in manifest["outputs"]:
        artifact = output / item["path"]
        assert artifact.stat().st_size == item["bytes"]
        assert sha256_file(artifact) == item["sha256"]
    manifest_path = output / "bearing_artifact_manifest.json"
    assert manifest_path.is_file()
    validation = validate_bearing_paper_artifacts(
        manifest_path=manifest_path,
        expected_manifest_sha256=sha256_file(manifest_path),
        project_root=tmp_path,
    )
    assert validation["status"] == "passed_independent_bearing_paper_artifact_validation"
    assert validation["input_count"] == 28
    assert validation["output_count"] == 42
    assert validation["independent_no_refit_validation_count"] == 6
    assert validation["submission_pdf_count"] == 5
    assert validation["refit_performed"] is False

    raw_signal_path = raw_window_dir / "vibration_windows.npy"
    raw_signal_bytes = raw_signal_path.read_bytes()
    raw_signal_path.unlink()
    with pytest.raises(FileNotFoundError):
        generate_package(tmp_path / "strict-missing-raw")
    release_output = tmp_path / "release-generated"
    release_manifest = generate_package(release_output, release_input_mode=True)
    assert release_manifest == manifest
    assert sha256_file(release_output / "bearing_artifact_manifest.json") == sha256_file(
        manifest_path
    )
    release_validation = validate_bearing_paper_artifacts(
        manifest_path=release_output / "bearing_artifact_manifest.json",
        expected_manifest_sha256=sha256_file(manifest_path),
        project_root=tmp_path,
        release_input_mode=True,
    )
    assert release_validation["release_input_mode"] is True
    assert release_validation["all_consumed_manifest_inputs_verified"] is True
    assert release_validation["unconsumed_parent_summary_outputs_verified"] is False
    raw_index_path = raw_window_dir / "window_index.parquet"
    raw_index_bytes = raw_index_path.read_bytes()
    raw_index_path.unlink()
    with pytest.raises(FileNotFoundError):
        generate_package(tmp_path / "release-missing-consumed", release_input_mode=True)
    raw_index_path.write_bytes(raw_index_bytes)
    raw_signal_path.write_bytes(raw_signal_bytes)

    raw_summary_path = tmp_path / manifest["inputs"]["raw_summary"]["path"]
    original_raw_summary = raw_summary_path.read_bytes()
    original_raw_input = dict(manifest["inputs"]["raw_summary"])
    original_raw_decision = manifest["decision"][
        "raw_median_random_minus_crossed_macro_f1"
    ]
    raw_summary_value = json.loads(original_raw_summary)
    near_csv_value = 0.4 + 5e-13
    raw_summary_value["findings"]["median_random_minus_crossed_macro_f1"] = near_csv_value
    raw_summary_path.write_text(
        json.dumps(raw_summary_value, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest["inputs"]["raw_summary"].update(
        {
            "bytes": raw_summary_path.stat().st_size,
            "sha256": sha256_file(raw_summary_path),
        }
    )
    manifest["decision"]["raw_median_random_minus_crossed_macro_f1"] = near_csv_value
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    tolerant_validation = validate_bearing_paper_artifacts(
        manifest_path=manifest_path,
        expected_manifest_sha256=sha256_file(manifest_path),
        project_root=tmp_path,
    )
    assert tolerant_validation["raw_median_summary_csv_difference"] == pytest.approx(5e-13)

    raw_summary_value["findings"]["median_random_minus_crossed_macro_f1"] = 0.400001
    raw_summary_path.write_text(
        json.dumps(raw_summary_value, sort_keys=True) + "\n", encoding="utf-8"
    )
    manifest["inputs"]["raw_summary"].update(
        {
            "bytes": raw_summary_path.stat().st_size,
            "sha256": sha256_file(raw_summary_path),
        }
    )
    manifest["decision"]["raw_median_random_minus_crossed_macro_f1"] = 0.400001
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="raw median summary and serialized CSV"):
        validate_bearing_paper_artifacts(
            manifest_path=manifest_path,
            expected_manifest_sha256=sha256_file(manifest_path),
            project_root=tmp_path,
        )

    raw_summary_path.write_bytes(original_raw_summary)
    manifest["inputs"]["raw_summary"] = original_raw_input
    manifest["decision"][
        "raw_median_random_minus_crossed_macro_f1"
    ] = original_raw_decision
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    first_output = output / manifest["outputs"][0]["path"]
    original_first_output = first_output.read_bytes()
    first_output.write_bytes(original_first_output + b"tamper")
    with pytest.raises(ValueError, match="byte count changed"):
        validate_bearing_paper_artifacts(
            manifest_path=manifest_path,
            expected_manifest_sha256=sha256_file(manifest_path),
            project_root=tmp_path,
        )

    first_output.write_bytes(original_first_output)
    pdf_path = output / "bearing_figure_00_access_lattice.pdf"
    original_pdf = pdf_path.read_bytes()
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(pdf_path))
    writer.add_metadata({"/CreationDate": "D:20260819000000+00'00'"})
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    pdf_record = next(item for item in manifest["outputs"] if item["path"] == pdf_path.name)
    pdf_record["bytes"] = pdf_path.stat().st_size
    pdf_record["sha256"] = sha256_file(pdf_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="creation timestamp changed"):
        validate_bearing_paper_artifacts(
            manifest_path=manifest_path,
            expected_manifest_sha256=sha256_file(manifest_path),
            project_root=tmp_path,
        )

    pdf_path.write_bytes(original_pdf)
    writer = PdfWriter()
    writer.clone_document_from_reader(PdfReader(pdf_path))
    writer.add_metadata({"/Title": "Mismatched figure"})
    with pdf_path.open("wb") as handle:
        writer.write(handle)
    pdf_record["bytes"] = pdf_path.stat().st_size
    pdf_record["sha256"] = sha256_file(pdf_path)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="title does not match"):
        validate_bearing_paper_artifacts(
            manifest_path=manifest_path,
            expected_manifest_sha256=sha256_file(manifest_path),
            project_root=tmp_path,
        )
