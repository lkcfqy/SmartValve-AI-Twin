from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

from smartvalve.config import project_root

REQUIRED_DOCUMENTS = {
    "BEARING_DISCUSSION.md",
    "BEARING_MANUSCRIPT.md",
    "BEARING_METHODS.md",
    "BEARING_RESULTS.md",
    "README.md",
    "SUBMISSION_STRATEGY.md",
    "TITLE_ABSTRACT.md",
    "METHODS.md",
    "RESULTS.md",
    "MANUSCRIPT_OUTLINE.md",
    "RELATED_WORK.md",
    "NOVELTY_MATRIX.md",
    "REPRODUCIBILITY.md",
    "RESS_SUBMISSION_PACKET.md",
    "references.bib",
}


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_manuscript_starter_documents_are_complete() -> None:
    paper = project_root() / "paper"

    present_documents = {path.name for path in paper.iterdir() if path.is_file()}
    assert present_documents >= REQUIRED_DOCUMENTS
    for filename in REQUIRED_DOCUMENTS:
        assert (paper / filename).stat().st_size > 100


def test_integrated_bearing_manuscript_has_no_section_scaffolding() -> None:
    manuscript = (project_root() / "paper" / "BEARING_MANUSCRIPT.md").read_text(encoding="utf-8")

    assert len(manuscript.split()) >= 7_000
    assert all(f"## {section}." in manuscript for section in range(1, 7))
    for obsolete in (
        "folded into this file",
        "Results are embargoed here",
        "Discussion is outcome-conditioned. It will",
        "The conclusion will be written",
        "chance approximately 0.0023",
    ):
        assert obsolete not in manuscript


def test_bearing_reidentification_baseline_is_not_mislabeled_as_chance() -> None:
    paper = project_root() / "paper"
    for filename in ("BEARING_MANUSCRIPT.md", "BEARING_RESULTS.md"):
        text = (paper / filename).read_text(encoding="utf-8")
        assert "chance approximately 0.0023" not in text
        assert "dummy-prior baseline had macro F1 0.002300" in text
        assert "1/29 = 0.034483" in text


def test_generated_paper_manifest_matches_inputs_and_outputs() -> None:
    root = project_root()
    generated = root / "paper" / "generated"
    manifest_names = {"artifact_manifest.json", "multirig_artifact_manifest.json"}
    manifests = [
        json.loads((generated / name).read_text(encoding="utf-8"))
        for name in sorted(manifest_names)
    ]

    declared_outputs: set[str] = set()
    for manifest in manifests:
        assert manifest["deterministic"] is True
        for item in manifest["inputs"].values():
            relative = item["path"]
            assert not relative.startswith("/")
            assert not re.match(r"^[A-Za-z]:[\\/]", relative)
            path = root / relative
            assert path.is_file()
            assert _digest(path) == item["sha256"]

        manifest_outputs = {item["path"] for item in manifest["outputs"]}
        assert not declared_outputs.intersection(manifest_outputs)
        declared_outputs.update(manifest_outputs)
        for item in manifest["outputs"]:
            path = generated / item["path"]
            assert path.stat().st_size == item["bytes"]
            assert _digest(path) == item["sha256"]
            if path.suffix == ".svg":
                assert ElementTree.parse(path).getroot().tag.endswith("svg")

    actual_outputs = {
        path.name
        for path in generated.iterdir()
        if path.is_file() and path.name not in manifest_names
    }
    assert declared_outputs == actual_outputs

    multirig = manifests[1]
    assert multirig["decision"]["family_size"] == 6
    assert multirig["decision"]["positive_test_count"] == 1
    assert multirig["decision"]["internal_multi_dataset_evidence_gate_passed"] is False


def test_all_markdown_citations_have_bibtex_entries() -> None:
    paper = project_root() / "paper"
    bibtex = (paper / "references.bib").read_text(encoding="utf-8")
    parsed_bibtex_keys = re.findall(r"@[A-Za-z]+\s*\{\s*([^,\s]+)", bibtex)
    bibtex_keys = set(parsed_bibtex_keys)
    cited_keys: set[str] = set()
    for path in paper.glob("*.md"):
        cited_keys.update(
            re.findall(
                r"(?<![A-Za-z0-9_])@([A-Za-z][A-Za-z0-9_:-]+)",
                path.read_text(encoding="utf-8"),
            )
        )

    assert cited_keys
    assert len(parsed_bibtex_keys) == len(bibtex_keys)
    assert cited_keys <= bibtex_keys


def test_integrated_manuscript_cites_closest_protocol_work_and_dois_are_unique() -> None:
    paper = project_root() / "paper"
    manuscript = (paper / "BEARING_MANUSCRIPT.md").read_text(encoding="utf-8")
    bibliography = (paper / "references.bib").read_text(encoding="utf-8")
    cited_keys = set(
        re.findall(r"(?<![A-Za-z0-9_])@([A-Za-z][A-Za-z0-9_:-]+)", manuscript)
    )
    closest_protocol_work = {
        "Hendriks2022",
        "Abburi2023",
        "Matania2024",
        "Wheat2024",
        "Knap2026",
        "Vieira2026",
        "Kaya2026",
        "Panic2027",
        "Alsafari2026",
        "Sun2026LeakageResistant",
        "Mannone2026VibFM",
        "LiZhang2026FSMSN",
        "Spirto2026",
    }
    dois = [
        value.strip().casefold()
        for value in re.findall(r'(?i)\bdoi\s*=\s*[{"]([^}"]+)[}"]', bibliography)
    ]

    assert closest_protocol_work <= cited_keys
    assert len(dois) == len(set(dois))


def test_external_review_packet_has_unique_checks_and_current_artifact_topology() -> None:
    packet = (project_root() / "research" / "EXTERNAL_REVIEW_PACKET.md").read_text(
        encoding="utf-8"
    )
    check_ids = re.findall(r"(?m)^\| ([DSR]\d+) \|", packet)

    assert check_ids
    assert len(check_ids) == len(set(check_ids))
    assert "Regenerate all 42 final paper artifacts" in packet
    assert "all 39 final paper artifacts" not in packet
    assert all(label in packet for label in ("EXP-459", "EXP-461", "EXP-463"))
