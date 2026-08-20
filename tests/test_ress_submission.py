from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path

import pytest

from smartvalve.experiments.ress_submission import (
    AI_DECLARATION_SECTION,
    render_ress_highlights,
    render_ress_materials,
    validate_ress_submission,
)

VALID_COMMIT = "a" * 40
VALID_ARTIFACT_DOI = "https://doi.org/10.5281/zenodo.1234567"
AI_TEXT = (
    "The authors used OpenAI Codex in order to assist with editing; they reviewed and edited "
    "the result and take full responsibility."
)
ARTIFACT_CALLOUTS = (
    "Tables 1 through 6 are cited individually: "
    "Table 1, Table 2, Table 3, Table 4, Table 5, and Table 6. "
    "Figures 1 through 5 are cited individually: "
    "Figure 1, Figure 2, Figure 3, Figure 4, and Figure 5. "
    "Supplementary Table S1, Supplementary Table S2, Supplementary Table S3, and "
    "Supplementary Table S4 are cited."
)


def _abstract(words: int = 120) -> str:
    return " ".join(f"word{index}" for index in range(words))


def _write_package(
    root: Path,
    *,
    abstract_words: int = 120,
    article_title: str = "Physical access changes estimated reliability",
    manuscript_title: str | None = None,
    keywords: str = "bearing diagnosis; reliability; validation protocol",
    highlights: tuple[str, ...] = ("One", "Two", "Three"),
    manuscript_body_words: int = 5_050,
    marker: str = "",
) -> tuple[Path, Path, Path, Path]:
    abstract = _abstract(abstract_words)
    materials = root / "materials.md"
    materials.write_text(
        "# RESS submission materials\n\n"
        f"## Article title\n\n{article_title}\n\n"
        f"## Abstract\n\n{abstract}\n\n"
        f"## Keywords\n\n{keywords}\n\n"
        "## Highlights\n\n"
        + "\n".join(f"- {item}" for item in highlights)
        + "\n\n## Research data statement\n\n"
        "Paderborn and HUST data are cited; raw signals are not redistributed.\n\n"
        "## Code and artifacts\n\n"
        f"https://github.com/lkcfqy/SmartValve-AI-Twin/tree/{VALID_COMMIT}. "
        f"Evidence archive: {VALID_ARTIFACT_DOI}\n\n"
        f"## {AI_DECLARATION_SECTION}\n\n"
        f"{AI_TEXT}\n" + marker,
        encoding="utf-8",
    )
    manuscript = root / "manuscript.md"
    body = "[@Paper] " + ARTIFACT_CALLOUTS + " " + " ".join(
        "evidence" for _ in range(manuscript_body_words)
    )
    manuscript.write_text(
        f"# {manuscript_title or article_title}\n\n"
        f"## Abstract\n\n{abstract}\n\n"
        f"## 1. Introduction\n\n{body}\n\n"
        "## Data availability\n\n"
        "Paderborn and HUST raw signals are not redistributed.\n\n"
        "## Code and artifacts\n\n"
        f"https://github.com/lkcfqy/SmartValve-AI-Twin/tree/{VALID_COMMIT}. "
        f"Evidence archive: {VALID_ARTIFACT_DOI}\n\n"
        "## CRediT authorship contribution statement\n\n"
        "A. Author: Conceptualization, Software, Writing.\n\n"
        "## Funding\n\nThis research received no specific grant.\n\n"
        "## Declaration of competing interest\n\n"
        "The author declares no known competing interest.\n\n"
        f"## {AI_DECLARATION_SECTION}\n\n{AI_TEXT}\n",
        encoding="utf-8",
    )
    bibliography = root / "references.bib"
    bibliography.write_text(
        "@article{Paper,\n"
        "  author = {A. Author},\n"
        "  title = {Evidence},\n"
        "  journal = {Journal},\n"
        "  year = {2026},\n"
        "  doi = {10.1000/evidence}\n"
        "}\n",
        encoding="utf-8",
    )
    highlights_path = root / "submission-highlights.txt"
    highlights_path.write_text(
        "\n".join(f"- {item}" for item in highlights) + "\n",
        encoding="utf-8",
    )
    return materials, manuscript, bibliography, highlights_path


def test_ress_validator_accepts_a_complete_package(tmp_path: Path) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)

    result = validate_ress_submission(
        materials_path=materials,
        manuscript_path=manuscript,
        bibliography_path=bibliography,
        highlights_path=highlights,
    )

    assert result["status"] == "passed_ress_text_and_length_constraints"
    assert result["abstract_word_count"] == 120
    assert result["highlight_character_counts"] == [3, 3, 5]
    assert result["standalone_highlights_match"] is True
    assert result["standalone_highlights_filename"] == "submission-highlights.txt"
    assert result["abstract_matches_manuscript"] is True
    assert result["title_matches_manuscript"] is True
    assert result["code_commit_sha"] == VALID_COMMIT
    assert result["artifact_doi"] == VALID_ARTIFACT_DOI
    assert result["bibliography_entry_count"] == 1
    assert result["manuscript_unique_citation_count"] == 1
    assert result["duplicate_bibliography_key_count"] == 0
    assert result["duplicate_bibliography_doi_count"] == 0
    assert result["required_table_figure_callouts_verified"] is True


def _snapshot(methods: tuple[str, ...], *, effect: float = 0.4) -> dict[str, object]:
    return {
        "effect_minimum": effect,
        "effect_median": effect,
        "effect_maximum": effect,
        "interval_lower_minimum": effect - 0.1,
        "interval_upper_maximum": effect + 0.1,
        "all_interval_lower_limits_above_zero": True,
        "by_method": {
            method: {
                "effect": effect,
                "lower_95": effect - 0.1,
                "upper_95": effect + 0.1,
            }
            for method in methods
        },
    }


def test_ress_materials_render_from_hash_locked_headline_values(tmp_path: Path) -> None:
    methods = tuple(f"method-{index}" for index in range(9))
    range_value = {"minimum": 0.36, "maximum": 0.96}
    view = {
        "measurement_random_macro_f1": range_value,
        "crossed_holdout_macro_f1": {"minimum": 0.36, "maximum": 0.40},
        "random_minus_crossed": _snapshot(methods),
    }
    manifest = {
        "generator_version": "smartvalve-bearing-paper-artifacts-test",
        "deterministic": True,
        "decision": {
            "raw_representation_sensitivity_rule_passed": True,
            "headline_values": {
                "paderborn_fusion": view,
                "paderborn_sensor_views": {
                    family: view for family in ("vibration", "motor_current", "fusion")
                },
                "paderborn_raw_architectures": {
                    **view,
                    "random_minus_crossed": _snapshot(("cnn1d", "fft", "stft")),
                },
                "hust_replication": {
                    "recording_random_macro_f1": {"minimum": 1.0, "maximum": 1.0},
                    "crossed_holdout_macro_f1": {"minimum": 0.747, "maximum": 0.774},
                    "random_minus_crossed": _snapshot(methods, effect=0.226),
                },
                "hust_equal_volume_control": {
                    "shared_access_macro_f1": {"minimum": 1.0, "maximum": 1.0},
                    "crossed_holdout_macro_f1": {"minimum": 0.747, "maximum": 0.774},
                    "shared_minus_crossed": _snapshot(methods, effect=0.226),
                },
                "hust_physical_unit_influence": {
                    "method_comparison_count": 18,
                    "bearing_loo_sign_stable_count": 18,
                    "group_loo_sign_stable_count": 18,
                    "minimum_bearing_loo_effect": 0.1745457916203188,
                    "minimum_group_loo_effect": 0.11223443223443219,
                    "maximum_bearing_absolute_influence": 0.05148467432950199,
                    "maximum_group_absolute_influence": 0.1137960337153886,
                    "posthoc_sensitivity_not_confirmatory": True,
                },
            }
        },
    }
    manifest_path = tmp_path / "bearing_artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    digest = sha256(manifest_path.read_bytes()).hexdigest()

    rendered = render_ress_materials(
        artifact_manifest_path=manifest_path,
        expected_manifest_sha256=digest,
        human_review_confirmed=True,
        code_commit_sha=VALID_COMMIT,
        artifact_doi=VALID_ARTIFACT_DOI,
    )

    assert "0.360–0.960 versus 0.360–0.400 crossed" in rendered
    assert "27/27 method-view intervals" in rendered
    assert "3/3 lower limits" in rendered
    assert "median gap was 0.226" in rendered
    materials = tmp_path / "materials-rendered.md"
    materials.write_text(rendered, encoding="utf-8")
    highlights = tmp_path / "submission-highlights.txt"
    highlights.write_text(render_ress_highlights(rendered), encoding="utf-8")
    abstract = rendered.split("## Abstract\n\n", 1)[1].split("\n\n## Keywords", 1)[0]
    ai_text = rendered.split(f"## {AI_DECLARATION_SECTION}\n\n", 1)[1].strip()
    manuscript = tmp_path / "manuscript-rendered.md"
    manuscript.write_text(
        "# Physical Access Changes Estimated Bearing-Diagnosis Reliability: A Crossed "
        "Identity--Condition Audit with Sealed Replication\n\n"
        f"## Abstract\n\n{abstract}\n\n"
        "## 1. Introduction\n\n"
        + "[@Paper] "
        + ARTIFACT_CALLOUTS
        + " "
        + " ".join("evidence" for _ in range(5_050))
        + "\n\n## Data availability\n\n"
        "Paderborn and HUST raw signals are not redistributed.\n\n"
        "## Code and artifacts\n\n"
        f"https://github.com/lkcfqy/SmartValve-AI-Twin/tree/{VALID_COMMIT}. "
        f"Evidence archive: {VALID_ARTIFACT_DOI}\n\n"
        "## CRediT authorship contribution statement\n\n"
        "A. Author: Conceptualization, Software, Writing.\n\n"
        "## Funding\n\nThis research received no specific grant.\n\n"
        "## Declaration of competing interest\n\n"
        "The author declares no known competing interest.\n\n"
        f"## {AI_DECLARATION_SECTION}\n\n{ai_text}\n",
        encoding="utf-8",
    )
    bibliography = tmp_path / "references.bib"
    bibliography.write_text(
        "@article{Paper, title={Evidence}, year={2026}, doi={10.1000/evidence}}\n",
        encoding="utf-8",
    )
    result = validate_ress_submission(
        materials_path=materials,
        manuscript_path=manuscript,
        bibliography_path=bibliography,
        highlights_path=highlights,
    )
    assert result["abstract_word_count"] <= 200


def test_ress_materials_require_explicit_human_review(tmp_path: Path) -> None:
    manifest_path = tmp_path / "bearing_artifact_manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")
    digest = sha256(manifest_path.read_bytes()).hexdigest()

    with pytest.raises(ValueError, match="explicit confirmation"):
        render_ress_materials(
            artifact_manifest_path=manifest_path,
            expected_manifest_sha256=digest,
            human_review_confirmed=False,
            code_commit_sha=VALID_COMMIT,
            artifact_doi=VALID_ARTIFACT_DOI,
        )


@pytest.mark.parametrize(
    ("commit", "doi", "message"),
    [
        ("0" * 40, VALID_ARTIFACT_DOI, "concrete lowercase Git commit"),
        (VALID_COMMIT, "https://example.com/archive", "https://doi.org artifact identifier"),
    ],
)
def test_ress_materials_require_concrete_release_identifiers(
    tmp_path: Path, commit: str, doi: str, message: str
) -> None:
    manifest_path = tmp_path / "bearing_artifact_manifest.json"
    manifest_path.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        render_ress_materials(
            artifact_manifest_path=manifest_path,
            expected_manifest_sha256=sha256(manifest_path.read_bytes()).hexdigest(),
            human_review_confirmed=True,
            code_commit_sha=commit,
            artifact_doi=doi,
        )


@pytest.mark.parametrize(
    ("old", "new", "message"),
    [
        (VALID_COMMIT, "b" * 40, "does not contain the submission commit"),
        (VALID_ARTIFACT_DOI, "https://doi.org/10.5281/zenodo.7654321", "artifact DOI"),
        (AI_TEXT, f"{AI_TEXT} Changed.", "AI declarations differ"),
    ],
)
def test_ress_validator_rejects_manuscript_release_or_declaration_drift(
    tmp_path: Path, old: str, new: str, message: str
) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    manuscript.write_text(
        manuscript.read_text(encoding="utf-8").replace(old, new),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


def test_ress_validator_rejects_a_citation_in_the_abstract(tmp_path: Path) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    for path in (materials, manuscript):
        text = path.read_text(encoding="utf-8").replace("word0", "word0 [@Paper]", 1)
        path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="must not contain citations or links"):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


def test_ress_validator_rejects_missing_bibtex_entry(tmp_path: Path) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    manuscript.write_text(
        manuscript.read_text(encoding="utf-8").replace("[@Paper]", "[@Missing]", 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="citations lack BibTeX entries.*Missing"):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


def test_ress_validator_rejects_missing_final_figure_callout(tmp_path: Path) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    manuscript.write_text(
        manuscript.read_text(encoding="utf-8").replace("Figure 3", "the third figure", 1),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="table/figure callouts.*Figure 3"):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


def test_ress_validator_rejects_title_drift(tmp_path: Path) -> None:
    materials, manuscript, bibliography, highlights = _write_package(
        tmp_path,
        manuscript_title="A different manuscript title",
    )

    with pytest.raises(ValueError, match="article titles differ"):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


def test_ress_validator_rejects_standalone_highlights_drift(tmp_path: Path) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    highlights.write_text("- One\n- Two\n- Changed\n", encoding="utf-8")

    with pytest.raises(ValueError, match="standalone highlights differ"):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


def test_ress_validator_requires_highlights_in_editable_named_file(
    tmp_path: Path,
) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    unnamed = tmp_path / "separate-file.md"
    unnamed.write_text(highlights.read_text(encoding="utf-8"), encoding="utf-8")

    with pytest.raises(ValueError) as raised:
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=unnamed,
        )
    assert "editable .txt file" in str(raised.value)
    assert "filename must contain 'highlights'" in str(raised.value)


@pytest.mark.parametrize("target", ("materials", "manuscript"))
def test_ress_validator_rejects_duplicate_sections(tmp_path: Path, target: str) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    path = materials if target == "materials" else manuscript
    path.write_text(
        path.read_text(encoding="utf-8") + "\n## Abstract\n\nConflicting duplicate.\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=rf"{target}.*duplicate sections"):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


@pytest.mark.parametrize(
    ("extra_entry", "message"),
    [
        (
            "@article{Paper, title={Duplicate key}, year={2026}}\n",
            "duplicate keys",
        ),
        (
            "@article{Other, title={Duplicate DOI}, year={2026}, "
            "doi={10.1000/evidence}}\n",
            "duplicate DOI values",
        ),
    ],
)
def test_ress_validator_rejects_bibliography_duplicates(
    tmp_path: Path, extra_entry: str, message: str
) -> None:
    materials, manuscript, bibliography, highlights = _write_package(tmp_path)
    bibliography.write_text(
        bibliography.read_text(encoding="utf-8") + extra_entry,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"abstract_words": 201}, "abstract must contain 100-200 words"),
        (
            {"keywords": "one; two; three; four; five; six; seven; eight"},
            "keywords must contain 1-7",
        ),
        ({"highlights": ("One", "Two")}, "highlights must contain 3-5"),
        ({"highlights": ("x" * 86, "Two", "Three")}, "exceeds 85 characters"),
        ({"manuscript_body_words": 13_050}, "manuscript must contain 5,000-13,000"),
        ({"marker": "\nTODO replace this\n"}, "TODO/TBD"),
    ],
)
def test_ress_validator_rejects_submission_blockers(
    tmp_path: Path,
    arguments: dict[str, object],
    message: str,
) -> None:
    materials, manuscript, bibliography, highlights = _write_package(
        tmp_path, **arguments
    )

    with pytest.raises(ValueError, match=message):
        validate_ress_submission(
            materials_path=materials,
            manuscript_path=manuscript,
            bibliography_path=bibliography,
            highlights_path=highlights,
        )
