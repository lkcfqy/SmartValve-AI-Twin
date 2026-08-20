"""Validate the journal-facing RESS submission text before packaging."""

from __future__ import annotations

import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

VALIDATOR_VERSION = "smartvalve-ress-submission-validator-0.9.0"
AI_DECLARATION_SECTION = (
    "Declaration of generative AI and AI-assisted technologies in the manuscript "
    "preparation process"
)
REQUIRED_MATERIAL_SECTIONS = (
    "Article title",
    "Abstract",
    "Keywords",
    "Highlights",
    "Research data statement",
    "Code and artifacts",
    AI_DECLARATION_SECTION,
)
REQUIRED_MANUSCRIPT_CALLOUTS = (
    *(f"Table {index}" for index in range(1, 7)),
    *(f"Figure {index}" for index in range(1, 6)),
    *(f"Supplementary Table S{index}" for index in range(1, 5)),
)
FORBIDDEN_MARKERS = (
    "{{",
    "}}",
    "submission hold",
    "working manuscript",
    "raw sensitivity in progress",
    "insert only after",
    "not yet submission text",
    "author action required",
    "must accompany submission",
)


def _sections(text: str) -> dict[str, str]:
    matches = list(re.finditer(r"(?m)^## ([^\n]+)\s*$", text))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections[match.group(1).strip()] = text[match.end() : end].strip()
    return sections


def _section_names(text: str) -> list[str]:
    return [item.strip() for item in re.findall(r"(?m)^## ([^\n]+)\s*$", text)]


def _duplicate_names(names: list[str]) -> list[str]:
    normalized = [item.casefold() for item in names]
    return sorted(
        {names[index] for index, item in enumerate(normalized) if normalized.count(item) > 1},
        key=str.casefold,
    )


def _h1_titles(text: str) -> list[str]:
    return [item.strip() for item in re.findall(r"(?m)^# (?!#)([^\n]+)\s*$", text)]


def _normalized(text: str) -> str:
    return " ".join(text.split())


def _normalized_title(text: str) -> str:
    return _normalized(text).replace("--", "–").replace("—", "–")


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[’'-][A-Za-z0-9]+)*", text))


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bibtex_keys(text: str) -> list[str]:
    return re.findall(r"@[A-Za-z]+\s*\{\s*([^,\s]+)", text)


def _manuscript_citations(text: str) -> list[str]:
    return re.findall(r"(?<![A-Za-z0-9_])@([A-Za-z][A-Za-z0-9_:-]+)", text)


def _bibtex_dois(text: str) -> list[str]:
    return [
        value.strip().casefold()
        for value in re.findall(
            r'(?i)\bdoi\s*=\s*[{"]([^}"]+)[}"]',
            text,
        )
    ]


def _score_range(value: Any) -> str:
    if not isinstance(value, dict):
        raise ValueError("headline score range is not an object")
    minimum = float(value["minimum"])
    maximum = float(value["maximum"])
    if minimum == maximum:
        return f"{minimum:.3f}"
    return f"{minimum:.3f}–{maximum:.3f}"


def _positive_interval_count(snapshot: Any) -> int:
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("by_method"), dict):
        raise ValueError("headline effect snapshot is not an object")
    return sum(float(item["lower_95"]) > 0 for item in snapshot["by_method"].values())


def _validated_hust_influence_snapshot(value: Any) -> dict[str, Any]:
    """Validate the post-hoc physical-unit sensitivity headline before rendering it."""

    if not isinstance(value, dict):
        raise ValueError("HUST physical-unit influence headline is not an object")
    required = {
        "method_comparison_count",
        "bearing_loo_sign_stable_count",
        "group_loo_sign_stable_count",
        "minimum_bearing_loo_effect",
        "minimum_group_loo_effect",
        "maximum_bearing_absolute_influence",
        "maximum_group_absolute_influence",
        "posthoc_sensitivity_not_confirmatory",
    }
    if not required.issubset(value):
        raise ValueError("HUST physical-unit influence headline is incomplete")
    count = int(value["method_comparison_count"])
    bearing_stable = int(value["bearing_loo_sign_stable_count"])
    group_stable = int(value["group_loo_sign_stable_count"])
    numeric_names = (
        "minimum_bearing_loo_effect",
        "minimum_group_loo_effect",
        "maximum_bearing_absolute_influence",
        "maximum_group_absolute_influence",
    )
    numeric = {name: float(value[name]) for name in numeric_names}
    if count != 18 or not 0 <= bearing_stable <= count or not 0 <= group_stable <= count:
        raise ValueError("HUST physical-unit influence counts changed")
    if not all(math.isfinite(item) and item >= 0 for item in numeric.values()):
        raise ValueError("HUST physical-unit influence values are not finite nonnegative numbers")
    if value["posthoc_sensitivity_not_confirmatory"] is not True:
        raise ValueError("HUST physical-unit influence audit lost its post-hoc scope")
    return {
        "method_comparison_count": count,
        "bearing_loo_sign_stable_count": bearing_stable,
        "group_loo_sign_stable_count": group_stable,
        **numeric,
        "posthoc_sensitivity_not_confirmatory": True,
    }


def _load_bearing_artifact_manifest(
    artifact_manifest_path: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    path = artifact_manifest_path.resolve(strict=True)
    observed = _sha256_file(path)
    if observed != expected_manifest_sha256:
        raise ValueError(
            f"bearing artifact manifest SHA-256 changed: expected {expected_manifest_sha256}, "
            f"observed {observed}"
        )
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("deterministic") is not True:
        raise ValueError("bearing artifact manifest is not deterministic")
    if not str(manifest.get("generator_version", "")).startswith(
        "smartvalve-bearing-paper-artifacts-"
    ):
        raise ValueError("bearing artifact manifest generator is not recognized")
    decision = manifest.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("bearing artifact manifest has no decision object")
    if not isinstance(decision.get("headline_values"), dict):
        raise ValueError("bearing artifact manifest has no headline values")
    return manifest


def render_ress_headline_content(
    *,
    artifact_manifest_path: Path,
    expected_manifest_sha256: str,
) -> dict[str, Any]:
    """Render outcome-complete headline text without asserting human submission approval."""

    manifest = _load_bearing_artifact_manifest(
        artifact_manifest_path,
        expected_manifest_sha256,
    )
    decision = manifest["decision"]
    values = decision["headline_values"]
    paderborn = values["paderborn_fusion"]
    sensors = values["paderborn_sensor_views"]
    raw = values["paderborn_raw_architectures"]
    hust = values["hust_replication"]
    control = values["hust_equal_volume_control"]
    influence = _validated_hust_influence_snapshot(values["hust_physical_unit_influence"])
    paderborn_count = _positive_interval_count(paderborn["random_minus_crossed"])
    sensor_count = sum(
        _positive_interval_count(item["random_minus_crossed"]) for item in sensors.values()
    )
    raw_snapshot = raw["random_minus_crossed"]
    raw_by_method = raw_snapshot.get("by_method")
    if not isinstance(raw_by_method, dict) or set(raw_by_method) != {"cnn1d", "fft", "stft"}:
        raise ValueError("raw headline values do not contain exactly cnn1d, fft, and stft")
    raw_count = _positive_interval_count(raw_snapshot)
    hust_count = _positive_interval_count(hust["random_minus_crossed"])
    control_count = _positive_interval_count(control["shared_minus_crossed"])
    paderborn_random = _score_range(paderborn["measurement_random_macro_f1"])
    paderborn_crossed = _score_range(paderborn["crossed_holdout_macro_f1"])
    raw_random = _score_range(raw["measurement_random_macro_f1"])
    raw_crossed = _score_range(raw["crossed_holdout_macro_f1"])
    hust_random = _score_range(hust["recording_random_macro_f1"])
    hust_crossed = _score_range(hust["crossed_holdout_macro_f1"])
    hust_median = float(hust["random_minus_crossed"]["effect_median"])
    raw_rule = decision.get("raw_representation_sensitivity_rule_passed")
    if not isinstance(raw_rule, bool):
        raise ValueError("bearing artifact manifest lacks the raw sensitivity rule decision")
    abstract = (
        "Validation access determines which deployment population a bearing-diagnosis score "
        "represents. We evaluated identical Paderborn records, frozen configurations, nine "
        "domain-generalization mechanisms, and seeds under measurement-random, setting-held-out, "
        "identity-held-out, and crossed identity-by-setting protocols. The crossed protocol "
        "quarantined both partial-access arms, and uncertainty resampled physical bearings. With "
        f"fused features, random macro F1 was {paderborn_random} versus {paderborn_crossed} "
        f"crossed; {paderborn_count}/9 "
        "paired interval lower limits exceeded zero. Across vibration, motor-current, and fusion "
        f"views, {sensor_count}/27 method-view intervals had positive lower limits. Sealed raw, "
        f"FFT, and STFT CNN gaps were {float(raw_snapshot['effect_minimum']):.3f}–"
        f"{float(raw_snapshot['effect_maximum']):.3f}; {raw_count}/3 lower limits exceeded zero. "
        "Accessible and crossed protocols selected different Paderborn leaders. "
        "A signal-unopened HUST replication scored "
        f"{hust_random} under random access versus {hust_crossed} crossed; {hust_count}/9 lower "
        f"limits exceeded zero and the median gap was {hust_median:.3f}. "
        f"An equal-source-volume control retained {control_count}/9 positive intervals, ruling out "
        "source-record count alone. HUST's ceiling prevented directional rank replication. "
        "Physical access therefore materially changes estimated diagnostic reliability and "
        "finite-cohort model choice. We contribute an access-explicit evaluation and replication "
        "protocol, not a new classifier or causal leakage estimate."
    )
    if not 100 <= _word_count(abstract) <= 200:
        raise ValueError(f"rendered abstract has {_word_count(abstract)} words")
    highlights = (
        "Crossed validation jointly withholds bearing identity and operating condition",
        "Both partial-access arms are quarantined from fitting and model selection",
        f"All {sensor_count} Paderborn method-sensor gaps have positive bearing intervals",
        f"A sealed HUST replication retained {control_count}/9 gaps at equal source volume",
        "Raw, FFT, and STFT CNNs test dependence on compact feature engineering",
    )
    if any(len(item) > 85 for item in highlights):
        raise ValueError("rendered highlight exceeds 85 characters")
    return {
        "abstract": abstract,
        "highlights": highlights,
        "paderborn_positive_interval_count": paderborn_count,
        "sensor_positive_interval_count": sensor_count,
        "raw_positive_interval_count": raw_count,
        "hust_positive_interval_count": hust_count,
        "control_positive_interval_count": control_count,
        "raw_random_score_range": raw_random,
        "raw_crossed_score_range": raw_crossed,
        "raw_effect_snapshot": raw_snapshot,
        "raw_representation_sensitivity_rule_passed": raw_rule,
        "hust_influence_snapshot": influence,
        "hust_influence_method_comparison_count": influence["method_comparison_count"],
        "hust_influence_bearing_stable_count": influence[
            "bearing_loo_sign_stable_count"
        ],
        "hust_influence_group_stable_count": influence["group_loo_sign_stable_count"],
        "hust_influence_minimum_bearing_loo_effect": influence[
            "minimum_bearing_loo_effect"
        ],
        "hust_influence_minimum_group_loo_effect": influence[
            "minimum_group_loo_effect"
        ],
        "hust_influence_maximum_bearing_absolute_change": influence[
            "maximum_bearing_absolute_influence"
        ],
        "hust_influence_maximum_group_absolute_change": influence[
            "maximum_group_absolute_influence"
        ],
    }


def render_ress_materials(
    *,
    artifact_manifest_path: Path,
    expected_manifest_sha256: str,
    human_review_confirmed: bool,
    code_commit_sha: str,
    artifact_doi: str,
) -> str:
    """Render factual RESS-facing text from the final hash-locked artifact manifest."""

    if not human_review_confirmed:
        raise ValueError(
            "RESS materials require explicit confirmation that the human authors reviewed "
            "the analyses, citations, visualizations, and final text"
        )
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", code_commit_sha) or not set(
        code_commit_sha
    ) - {"0"}:
        raise ValueError("RESS materials require a concrete lowercase Git commit SHA")
    if not re.fullmatch(r"https://doi\.org/10\.\d{4,9}/\S+", artifact_doi):
        raise ValueError("RESS materials require a concrete https://doi.org artifact identifier")

    headline = render_ress_headline_content(
        artifact_manifest_path=artifact_manifest_path,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    abstract = headline["abstract"]
    highlights = headline["highlights"]
    return (
        "# RESS submission materials\n\n"
        "## Article title\n\n"
        "Physical Access Changes Estimated Bearing-Diagnosis Reliability: A Crossed "
        "Identity–Condition Audit with Sealed Replication\n\n"
        f"## Abstract\n\n{abstract}\n\n"
        "## Keywords\n\n"
        "bearing fault diagnosis; validation protocol; data leakage; domain generalization; "
        "physical-unit bootstrap; reliability estimation\n\n"
        "## Highlights\n\n"
        + "\n".join(f"- {item}" for item in highlights)
        + "\n\n## Research data statement\n\n"
        "Paderborn bearing data are available from the Paderborn Bearing Data Center under its "
        "academic non-commercial licence. HUST Bearing v3 is available from Mendeley Data under "
        "CC BY 4.0 (DOI 10.17632/cbv7jyx4p9.3). Raw signals are not redistributed; derived "
        "artifacts remain subject to the source dataset licences and are not relicensed by the "
        "repository software licence.\n\n"
        "## Code and artifacts\n\n"
        "The exact code revision is available at "
        f"https://github.com/lkcfqy/SmartValve-AI-Twin/tree/{code_commit_sha}. A deterministic "
        f"evidence archive is available at {artifact_doi}; no raw dataset signal is included in "
        "the archive.\n\n"
        f"## {AI_DECLARATION_SECTION}\n\n"
        "During the preparation of this work, the authors used OpenAI Codex in order to assist "
        "with software implementation, tests, experiment orchestration, documentation, and "
        "language editing. After using this tool, the authors reviewed and edited the content as "
        "needed and take full responsibility for the content of the published article.\n"
    )


def render_ress_highlights(materials: str) -> str:
    """Render the journal's separate editable highlights file from submission text."""

    highlight_lines = [
        line.strip()
        for line in _sections(materials).get("Highlights", "").splitlines()
        if line.strip()
    ]
    if any(not line.startswith("- ") for line in highlight_lines):
        raise ValueError("RESS highlights contain non-bullet text")
    highlights = [line[2:].strip() for line in highlight_lines]
    if not 3 <= len(highlights) <= 5:
        raise ValueError(
            f"RESS highlights require 3-5 bullets, observed {len(highlights)}"
        )
    if any(not item for item in highlights):
        raise ValueError("RESS highlights contain an empty bullet")
    if any(len(item) > 85 for item in highlights):
        raise ValueError("RESS highlight exceeds 85 characters")
    return "\n".join(f"- {item}" for item in highlights) + "\n"


def _placeholder_errors(text: str, role: str) -> list[str]:
    lowered = text.casefold()
    errors = [
        f"{role} contains forbidden marker: {marker}"
        for marker in FORBIDDEN_MARKERS
        if marker in lowered
    ]
    if re.search(r"(?i)(?:^|\W)(?:TODO|TBD)(?:$|\W)", text):
        errors.append(f"{role} contains TODO/TBD")
    return errors


def validate_ress_submission(
    *,
    materials_path: Path,
    manuscript_path: Path,
    bibliography_path: Path,
    highlights_path: Path,
) -> dict[str, Any]:
    """Enforce the current RESS abstract, keyword, highlight, and package constraints."""

    materials = materials_path.resolve(strict=True).read_text(encoding="utf-8")
    manuscript = manuscript_path.resolve(strict=True).read_text(encoding="utf-8")
    bibliography = bibliography_path.resolve(strict=True)
    bibliography_text = bibliography.read_text(encoding="utf-8")
    highlights_file = highlights_path.resolve(strict=True)
    standalone_highlights_text = highlights_file.read_text(encoding="utf-8")
    material_section_names = _section_names(materials)
    manuscript_section_names = _section_names(manuscript)
    sections = _sections(materials)
    errors = _placeholder_errors(materials, "submission materials")
    errors.extend(_placeholder_errors(manuscript, "manuscript"))
    duplicate_material_sections = _duplicate_names(material_section_names)
    if duplicate_material_sections:
        errors.append(
            "submission materials contain duplicate sections: "
            f"{duplicate_material_sections}"
        )
    duplicate_manuscript_sections = _duplicate_names(manuscript_section_names)
    if duplicate_manuscript_sections:
        errors.append(
            f"manuscript contains duplicate sections: {duplicate_manuscript_sections}"
        )

    parsed_bibtex_keys = _bibtex_keys(bibliography_text)
    bibtex_keys = set(parsed_bibtex_keys)
    if not parsed_bibtex_keys:
        errors.append("bibliography contains no BibTeX entries")
    duplicate_bibtex_keys = sorted(
        key for key in bibtex_keys if parsed_bibtex_keys.count(key) > 1
    )
    if duplicate_bibtex_keys:
        errors.append(f"bibliography contains duplicate keys: {duplicate_bibtex_keys}")
    manuscript_citations = _manuscript_citations(manuscript)
    cited_keys = set(manuscript_citations)
    if not cited_keys:
        errors.append("manuscript contains no bibliography citations")
    missing_citations = sorted(cited_keys - bibtex_keys)
    if missing_citations:
        errors.append(f"manuscript citations lack BibTeX entries: {missing_citations}")
    parsed_dois = _bibtex_dois(bibliography_text)
    duplicate_dois = sorted(doi for doi in set(parsed_dois) if parsed_dois.count(doi) > 1)
    if duplicate_dois:
        errors.append(f"bibliography contains duplicate DOI values: {duplicate_dois}")

    missing = [name for name in REQUIRED_MATERIAL_SECTIONS if not sections.get(name)]
    if missing:
        errors.append(f"submission materials lack required sections: {missing}")

    title_raw = sections.get("Article title", "")
    title = _normalized(title_raw)
    title_paragraphs = [item for item in re.split(r"\n\s*\n", title_raw) if item.strip()]
    if not title or len(title_paragraphs) != 1:
        errors.append("article title must be one non-empty paragraph")

    abstract_raw = sections.get("Abstract", "")
    abstract = _normalized(abstract_raw)
    abstract_words = _word_count(abstract)
    if not 100 <= abstract_words <= 200:
        errors.append(f"abstract must contain 100-200 words, observed {abstract_words}")
    if len([item for item in re.split(r"\n\s*\n", abstract_raw) if item.strip()]) != 1:
        errors.append("abstract must be one paragraph")
    if "[@" in abstract or "http://" in abstract or "https://" in abstract:
        errors.append("abstract must not contain citations or links")

    keyword_text = _normalized(sections.get("Keywords", ""))
    keywords = [item.strip() for item in keyword_text.split(";") if item.strip()]
    if not 1 <= len(keywords) <= 7:
        errors.append(
            f"keywords must contain 1-7 semicolon-separated items, observed {len(keywords)}"
        )
    if len({item.casefold() for item in keywords}) != len(keywords):
        errors.append("keywords contain duplicates")

    highlight_lines = [
        line.strip() for line in sections.get("Highlights", "").splitlines() if line.strip()
    ]
    if any(not line.startswith("- ") for line in highlight_lines):
        errors.append("highlights section contains non-bullet text")
    highlights = [line[2:].strip() for line in highlight_lines if line.startswith("- ")]
    if not 3 <= len(highlights) <= 5:
        errors.append(f"highlights must contain 3-5 bullets, observed {len(highlights)}")
    highlight_lengths = [len(item) for item in highlights]
    for index, length in enumerate(highlight_lengths, start=1):
        if not highlights[index - 1]:
            errors.append(f"highlight {index} is empty")
        if length > 85:
            errors.append(f"highlight {index} exceeds 85 characters: {length}")
    if highlights_file.suffix.casefold() != ".txt":
        errors.append("standalone highlights must be an editable .txt file")
    if "highlight" not in highlights_file.stem.casefold():
        errors.append("standalone highlights filename must contain 'highlights'")
    standalone_lines = [
        line.strip() for line in standalone_highlights_text.splitlines() if line.strip()
    ]
    if any(not line.startswith("- ") for line in standalone_lines):
        errors.append("standalone highlights contain non-bullet text")
    standalone_highlights = [
        line[2:].strip() for line in standalone_lines if line.startswith("- ")
    ]
    if standalone_highlights != highlights:
        errors.append("standalone highlights differ from submission-material highlights")

    manuscript_sections = _sections(manuscript)
    manuscript_titles = _h1_titles(manuscript)
    if len(manuscript_titles) != 1:
        errors.append(
            "manuscript must contain exactly one H1 article title, "
            f"observed {len(manuscript_titles)}"
        )
    elif _normalized_title(manuscript_titles[0]) != _normalized_title(title):
        errors.append("submission-material and manuscript article titles differ")
    manuscript_abstract = _normalized(manuscript_sections.get("Abstract", ""))
    if manuscript_abstract != abstract:
        errors.append("manuscript and submission-material abstracts differ")
    manuscript_words = _word_count(manuscript)
    if not 5_000 <= manuscript_words <= 13_000:
        errors.append(f"manuscript must contain 5,000-13,000 words, observed {manuscript_words}")
    required_manuscript_sections = (
        "Data availability",
        "Code and artifacts",
        "CRediT authorship contribution statement",
        "Funding",
        "Declaration of competing interest",
        AI_DECLARATION_SECTION,
    )
    missing_manuscript_sections = [
        name for name in required_manuscript_sections if not manuscript_sections.get(name)
    ]
    if missing_manuscript_sections:
        errors.append(
            f"manuscript lacks required disclosure sections: {missing_manuscript_sections}"
        )
    missing_callouts = [
        label
        for label in REQUIRED_MANUSCRIPT_CALLOUTS
        if re.search(rf"\b{re.escape(label)}\b", manuscript) is None
    ]
    if missing_callouts:
        errors.append(f"manuscript lacks required table/figure callouts: {missing_callouts}")

    data_statement = sections.get("Research data statement", "")
    if not all(token in data_statement for token in ("Paderborn", "HUST", "not redistributed")):
        errors.append(
            "research data statement must name both datasets and the redistribution limit"
        )
    manuscript_data_statement = manuscript_sections.get("Data availability", "")
    if not all(
        token in manuscript_data_statement for token in ("Paderborn", "HUST", "not redistributed")
    ):
        errors.append(
            "manuscript data statement must name both datasets and the redistribution limit"
        )
    code_statement = sections.get("Code and artifacts", "")
    commit_match = re.search(
        r"https://github\.com/lkcfqy/SmartValve-AI-Twin/tree/"
        r"([0-9a-f]{40}|[0-9a-f]{64})(?:\s|[.,;)]|$)",
        code_statement,
    )
    if commit_match is None or not set(commit_match.group(1)) - {"0"}:
        errors.append("code statement lacks a concrete project commit URL")
    artifact_doi_match = re.search(
        r"https://doi\.org/10\.\d{4,9}/[^\s,;]+",
        code_statement,
    )
    if artifact_doi_match is None:
        errors.append("code statement lacks a persistent artifact DOI")
    manuscript_code_statement = manuscript_sections.get("Code and artifacts", "")
    if commit_match is not None and commit_match.group(1) not in manuscript_code_statement:
        errors.append("manuscript code statement does not contain the submission commit")
    if artifact_doi_match is not None:
        artifact_doi = artifact_doi_match.group(0).rstrip(".)")
        if artifact_doi not in manuscript_code_statement:
            errors.append("manuscript code statement does not contain the artifact DOI")
    ai_statement = sections.get(AI_DECLARATION_SECTION, "")
    ai_required_phrases = (
        "OpenAI Codex",
        "in order to",
        "reviewed and edited",
        "full responsibility",
    )
    if not all(phrase in ai_statement for phrase in ai_required_phrases):
        errors.append(
            "AI declaration must identify the tool, purpose, human review, and responsibility"
        )
    manuscript_ai_statement = manuscript_sections.get(AI_DECLARATION_SECTION, "")
    if _normalized(manuscript_ai_statement) != _normalized(ai_statement):
        errors.append("manuscript and submission-material AI declarations differ")

    if errors:
        raise ValueError("RESS submission validation failed:\n- " + "\n- ".join(errors))
    return {
        "status": "passed_ress_text_and_length_constraints",
        "validator_version": VALIDATOR_VERSION,
        "abstract_word_count": abstract_words,
        "keyword_count": len(keywords),
        "highlight_count": len(highlights),
        "highlight_character_counts": highlight_lengths,
        "standalone_highlights_filename": highlights_file.name,
        "standalone_highlights_sha256": _sha256_file(highlights_file),
        "standalone_highlights_match": True,
        "manuscript_word_count": manuscript_words,
        "abstract_matches_manuscript": True,
        "title_matches_manuscript": True,
        "duplicate_material_section_count": 0,
        "duplicate_manuscript_section_count": 0,
        "forbidden_markers_present": False,
        "code_commit_sha": commit_match.group(1),
        "artifact_doi": artifact_doi_match.group(0).rstrip(".)"),
        "bibliography_sha256": _sha256_file(bibliography),
        "bibliography_entry_count": len(parsed_bibtex_keys),
        "manuscript_citation_occurrence_count": len(manuscript_citations),
        "manuscript_unique_citation_count": len(cited_keys),
        "uncited_bibliography_entry_count": len(bibtex_keys - cited_keys),
        "duplicate_bibliography_key_count": 0,
        "duplicate_bibliography_doi_count": 0,
        "required_table_figure_callouts_verified": True,
    }
