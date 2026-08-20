"""Render an outcome-complete bearing manuscript while preserving human-owned holds."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from smartvalve.experiments.ress_submission import render_ress_headline_content

RENDERER_VERSION = "smartvalve-bearing-manuscript-renderer-0.2.0"
MARKER_PREFIX = "SMARTVALVE_EMPIRICAL_FINAL"
BLOCKS = (
    "WORKING_NOTICE",
    "ABSTRACT",
    "RAW_RESULTS",
    "SYNTHESIS",
    "DISCUSSION_ACCESS",
    "REPRESENTATION_LIMITATION",
    "CONCLUSION",
)
RAW_METHOD_ORDER = ("cnn1d", "fft", "stft")
RAW_METHOD_LABELS = {
    "cnn1d": "raw 1D CNN",
    "fft": "log-FFT CNN",
    "stft": "log-STFT CNN",
}
FORBIDDEN_RENDERED_MARKERS = (
    MARKER_PREFIX,
    "Submission hold",
    "raw sensitivity in progress",
    "pending raw-architecture validation",
    "remaining empirical hold",
    "{{",
    "}}",
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _word_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+(?:[’'-][A-Za-z0-9]+)*", text))


def _replace_block(text: str, name: str, replacement: str) -> str:
    start = f"<!-- {MARKER_PREFIX}:{name}:START -->"
    end = f"<!-- {MARKER_PREFIX}:{name}:END -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"manuscript template must contain exactly one {name} marker pair")
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.DOTALL)
    rendered, count = pattern.subn(replacement.strip(), text, count=1)
    if count != 1:
        raise ValueError(f"manuscript template {name} block could not be replaced")
    return rendered


def _raw_details(headline: dict[str, Any]) -> tuple[str, int, bool, float]:
    snapshot = headline["raw_effect_snapshot"]
    by_method = snapshot["by_method"]
    details = []
    for method in RAW_METHOD_ORDER:
        item = by_method[method]
        details.append(
            f"{RAW_METHOD_LABELS[method]} {float(item['effect']):.6f} "
            f"[{float(item['lower_95']):.6f}, {float(item['upper_95']):.6f}]"
        )
    return (
        "; ".join(details),
        int(headline["raw_positive_interval_count"]),
        bool(headline["raw_representation_sensitivity_rule_passed"]),
        float(snapshot["effect_median"]),
    )


def render_empirical_final_manuscript(
    *,
    template_path: Path,
    artifact_manifest_path: Path,
    expected_manifest_sha256: str,
) -> tuple[str, dict[str, Any]]:
    """Replace all empirical holds from one independently validated artifact manifest."""

    template = template_path.resolve(strict=True)
    manifest = artifact_manifest_path.resolve(strict=True)
    headline = render_ress_headline_content(
        artifact_manifest_path=manifest,
        expected_manifest_sha256=expected_manifest_sha256,
    )
    raw_details, raw_positive, raw_rule, raw_median = _raw_details(headline)
    rule_phrase = "passed" if raw_rule else "did not pass"
    extension_phrase = (
        "extends the observed access-gap conclusion beyond the compact statistic family"
        if raw_rule
        else "does not support a uniform extension of the access-gap conclusion beyond the "
        "compact statistic family"
    )
    total_positive = (
        int(headline["sensor_positive_interval_count"])
        + int(headline["hust_positive_interval_count"])
        + raw_positive
    )
    influence_count = int(headline["hust_influence_method_comparison_count"])
    influence_bearing_stable = int(headline["hust_influence_bearing_stable_count"])
    influence_group_stable = int(headline["hust_influence_group_stable_count"])
    influence_min_bearing = float(headline["hust_influence_minimum_bearing_loo_effect"])
    influence_min_group = float(headline["hust_influence_minimum_group_loo_effect"])
    influence_max_bearing = float(
        headline["hust_influence_maximum_bearing_absolute_change"]
    )
    influence_max_group = float(headline["hust_influence_maximum_group_absolute_change"])
    influence_text = (
        "A post-hoc no-refit HUST influence audit retained positive effects in "
        f"{influence_bearing_stable}/{influence_count} method-comparison cells under "
        "leave-one-bearing-out deletion and "
        f"{influence_group_stable}/{influence_count} under class-balanced "
        "leave-one-specification-group-out deletion. The minimum deleted-sample effects were "
        f"{influence_min_bearing:.6f} and {influence_min_group:.6f}, respectively; maximum "
        "absolute changes from the full-cohort effects were "
        f"{influence_max_bearing:.6f} and {influence_max_group:.6f}. Supplementary Table S4 "
        "reports every cell. These deletion ranges are sensitivity diagnostics, not confidence "
        "intervals or independent replicates."
    )

    raw_results = (
        "The separately sealed family completed all 270 fixed fits, and EXP-457 independently "
        "recomputed its topology, predictions, recording aggregation, metrics, and 2,000-draw "
        "physical-bearing intervals without model refitting. Measurement-random macro F1 ranged "
        f"{headline['raw_random_score_range']}, compared with "
        f"{headline['raw_crossed_score_range']} under strict crossed access. Random-minus-crossed "
        f"effects and 95% intervals were {raw_details}. Thus {raw_positive}/3 interval lower "
        f"limits exceeded zero and the median effect was {raw_median:.6f}. The frozen sensitivity "
        f"rule {rule_phrase}; it required positive effects and positive interval lower limits for "
        "all three architectures and a median effect of at least 0.15. Table 6 reports the "
        "complete per-architecture result, and Figure 3 places the effects beside the "
        "compact-feature Paderborn and sealed HUST contrasts. This retrospective sensitivity can "
        "bound only the "
        "representation objection; it does not transfer the nine-method ranking result to these "
        "CNNs."
    )
    synthesis = (
        "### 4.4 Cross-dataset synthesis\n\n"
        f"Across the complete final family, {total_positive}/39 random-minus-crossed "
        "physical-bearing interval lower limits were positive: 27 Paderborn sensor-by-method "
        f"contrasts, nine sealed HUST method contrasts, and {raw_positive}/3 raw-architecture "
        f"contrasts. The frozen raw sensitivity rule {rule_phrase} and therefore "
        f"{extension_phrase}. Paderborn demonstrates leader instability under all three compact "
        "sensor views and shows that vibration is materially stronger than fusion under crossed "
        "access despite fusion's higher random scores. HUST replicates the score gap but not the "
        "directional ranking because its easy protocols saturate. The equal-source-volume "
        "falsification excludes source-record count as a sufficient explanation for the HUST "
        f"effect. {influence_text} These results support an access-validity conclusion across "
        "the stated finite "
        "cohorts, not a causal leakage amount or a population-wide method ordering."
    )
    discussion_access = (
        "The most stable finding is not that one learning mechanism wins, but that the stated "
        "deployment access materially changes diagnostic performance. On Paderborn, every neural "
        "method lost at least 0.561 macro F1 with fusion features, at least 0.293 with vibration, "
        "and at least 0.298 with motor current when moving from measurement-random to simultaneous "
        "unseen identity and setting. On HUST, every method lost 0.226--0.253 recording-level "
        f"macro F1. In the final 39-contrast family, {total_positive} physical-bearing interval "
        "lower limits were positive: all 36 compact-feature Paderborn/HUST contrasts and "
        f"{raw_positive}/3 raw-architecture contrasts. The raw rule {rule_phrase}; accordingly it "
        f"{extension_phrase}."
    )
    if raw_rule:
        representation_interpretation = (
            "The passing raw/FFT/STFT sensitivity reduces the risk that the access effect is only "
            "an artifact of the shared 24-statistic representation."
        )
    else:
        representation_interpretation = (
            "Because the raw/FFT/STFT sensitivity did not pass its frozen rule, representation "
            "dependence remains a material limitation and the compact-feature conclusion must not "
            "be generalized to raw encoders."
        )
    representation_limitation = (
        "Both corpora are controlled public test rigs rather than prospectively sampled factories. "
        f"{representation_interpretation} The sensitivity itself is retrospective, uses only four "
        "fixed windows per Paderborn record and three compact CNN families, and does not exhaust "
        "transformers, self-supervised encoders, current-specific demodulation, or architecture "
        "search. The nine shared mechanism implementations isolate inductive-bias families under "
        "one compact backbone; they are not exact reproductions of every original architecture and "
        "search space."
    )
    conclusion = (
        "The evidence supports a protocol paper rather than an algorithm paper. Simultaneously "
        "withholding physical identity and operating setting reveals substantial diagnostic "
        "degradation on both Paderborn development data and a sealed HUST replication; a one-axis "
        "load holdout can remain perfect while that double-unseen target fails. The same HUST gap "
        "survives an equal-source-volume control, so training-record count is not a sufficient "
        "explanation. Paderborn further shows that method and sensor conclusions can reverse under "
        "access, whereas HUST's ceiling prevents a meaningful external leaderboard. The sealed "
        f"raw/FFT/STFT sensitivity {rule_phrase} its frozen rule and {extension_phrase}. The final "
        f"HUST deletion audit was sign-stable in {influence_bearing_stable}/{influence_count} "
        "bearing-deletion and "
        f"{influence_group_stable}/{influence_count} group-deletion cells, but remains post hoc. "
        "The final "
        "claim is therefore bounded to access-explicit reliability estimation on the observed "
        "physical cohorts, not state-of-the-art classification, causal leakage, or deployment "
        "safety."
    )

    rendered = template.read_text(encoding="utf-8")
    replacements = {
        "WORKING_NOTICE": "",
        "ABSTRACT": str(headline["abstract"]),
        "RAW_RESULTS": raw_results,
        "SYNTHESIS": synthesis,
        "DISCUSSION_ACCESS": discussion_access,
        "REPRESENTATION_LIMITATION": representation_limitation,
        "CONCLUSION": conclusion,
    }
    for name in BLOCKS:
        rendered = _replace_block(rendered, name, replacements[name])
    rendered = rendered.replace("\r\n", "\n").rstrip() + "\n"

    forbidden = [marker for marker in FORBIDDEN_RENDERED_MARKERS if marker in rendered]
    if forbidden:
        raise ValueError(f"rendered empirical manuscript retains forbidden markers: {forbidden}")
    for callout in ("Table 6", "Figure 3", "Supplementary Table S4"):
        if re.search(rf"\b{re.escape(callout)}\b", rendered) is None:
            raise ValueError(f"rendered empirical manuscript lacks {callout}")
    words = _word_count(rendered)
    if not 5_000 <= words <= 13_000:
        raise ValueError(f"rendered empirical manuscript has {words} words")
    human_action_count = rendered.casefold().count("author action required")
    if human_action_count < 3:
        raise ValueError("empirical renderer must preserve the human-owned disclosure holds")

    report = {
        "status": "rendered_empirical_final_human_fields_pending",
        "renderer_version": RENDERER_VERSION,
        "template_path": template.as_posix(),
        "template_sha256": _sha256_file(template),
        "artifact_manifest_path": manifest.as_posix(),
        "artifact_manifest_sha256": expected_manifest_sha256,
        "rendered_sha256": _sha256_text(rendered),
        "word_count": words,
        "raw_positive_interval_count": raw_positive,
        "raw_representation_sensitivity_rule_passed": raw_rule,
        "final_positive_interval_count": total_positive,
        "final_contrast_count": 39,
        "hust_influence_method_comparison_count": influence_count,
        "hust_influence_bearing_stable_count": influence_bearing_stable,
        "hust_influence_group_stable_count": influence_group_stable,
        "hust_influence_minimum_bearing_loo_effect": influence_min_bearing,
        "hust_influence_minimum_group_loo_effect": influence_min_group,
        "hust_influence_maximum_bearing_absolute_change": influence_max_bearing,
        "hust_influence_maximum_group_absolute_change": influence_max_group,
        "table_6_figure_3_and_supplementary_table_s4_cited": True,
        "human_action_marker_count": human_action_count,
        "submission_ready": False,
    }
    return rendered, report
