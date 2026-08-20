from __future__ import annotations

import json
from hashlib import sha256
from xml.etree import ElementTree

import pytest

from smartvalve.experiments.paper_artifacts import (
    _heat_color,
    _provenance_path,
    _svg_document,
    _svg_text,
    _write_table,
    format_interval,
    load_locked_json,
)


def test_provenance_path_is_relative_inside_project(tmp_path) -> None:
    input_path = tmp_path / "runs" / "metrics.json"

    assert _provenance_path(input_path, tmp_path) == "runs/metrics.json"


def test_format_interval_uses_point_and_percentile_limits() -> None:
    result = format_interval(
        {
            "point_estimate": 0.123456,
            "ci95_low": 0.1,
            "ci95_high": 0.2,
        }
    )

    assert result == "0.1235 [0.1000, 0.2000]"


def test_locked_json_rejects_changed_input(tmp_path) -> None:
    path = tmp_path / "metrics.json"
    path.write_text(json.dumps({"answer": 42}), encoding="utf-8")
    digest = sha256(path.read_bytes()).hexdigest()

    assert load_locked_json(path, digest) == {"answer": 42}
    with pytest.raises(ValueError, match="locked paper input mismatch"):
        load_locked_json(path, "0" * 64)


def test_svg_document_is_valid_xml_and_escapes_text() -> None:
    document = _svg_document(
        100,
        80,
        "A & B",
        [_svg_text(10, 20, "x < y")],
    )

    root = ElementTree.fromstring(document)

    assert root.tag.endswith("svg")
    assert "A &amp; B" in document
    assert "x &lt; y" in document
    assert _heat_color(0.0) == "#fee2e2"
    assert _heat_color(1.0) == "#dbeafe"


def test_table_writer_emits_csv_markdown_and_latex(tmp_path) -> None:
    _write_table(
        tmp_path,
        "result",
        ["Protocol", "Mean"],
        [["P0_raw", "0.5 ± 0.1"]],
    )

    assert (tmp_path / "result.csv").read_text(encoding="utf-8").splitlines() == [
        "Protocol,Mean",
        "P0_raw,0.5 ± 0.1",
    ]
    assert "| P0_raw | 0.5 ± 0.1 |" in (tmp_path / "result.md").read_text(
        encoding="utf-8"
    )
    latex = (tmp_path / "result.tex").read_text(encoding="utf-8")
    assert r"P0\_raw" in latex
    assert r"0.5 $\pm$ 0.1" in latex
