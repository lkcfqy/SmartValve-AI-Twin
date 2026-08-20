# Adversarial review of the bearing-protocol paper

- Review date: 2026-08-19 (Asia/Shanghai)
- Review type: internal red-team audit; not a substitute for independent human peer review
- Manuscript: `paper/BEARING_MANUSCRIPT.md`
- Primary question: whether the evidence supports a top-domain-journal protocol/reliability paper

## Executive verdict

The current compact-feature evidence supports a serious protocol paper, not a general machine-
learning algorithm paper. The most defensible contribution is the physical-access estimand:
random/shared-context, one-axis holdout, and simultaneous identity-by-setting holdout are evaluated
on common target records, with both XOR partial-access arms quarantined in the strict protocol.
The score gap reproduces on signal-unopened HUST, survives an equal-source-volume falsification,
and remains positive in every cell of a complete post-hoc single-bearing and matched-group deletion
audit.
Paderborn method ordering and sensor conclusions are access-sensitive; HUST does not reproduce the
directional ranking because its easy protocols saturate.

No internal audit can certify acceptance or replace a mechanical-systems expert, statistician, or
independent reproducer. Raw-architecture sensitivity, final artifacts, public archiving, and human
review remain submission gates.

## Potential rejection arguments

| Reviewer objection | Evidence-based response | Residual status |
|---|---|---|
| “This is merely known bearing leakage.” | Independent-bearing, recording-separated, HUST leakage, representation, sensor-fusion, and factor-shift studies are explicitly credited. The claim is restricted to the joint identity × setting access contract, XOR quarantine, common-target rank/sensor audit, and sealed replication. | High novelty risk remains; no priority language is allowed. |
| “Random and crossed estimate different populations, so the difference is not leakage.” | Agreed. The manuscript calls them different deployment estimands and an access/membership contrast, never a causal leakage amount. | Mitigated by wording; causal interpretation remains prohibited. |
| “Crossed training simply has fewer records.” | The HUST control holds targets, source count (24), class balance, group/load support, and pair budgets fixed. All nine shared-minus-crossed intervals remain above zero. | Source count alone is closed; membership and access remain jointly changed. |
| “Thousands of windows create fake precision.” | Predictions are aggregated to records and intervals resample class-stratified physical bearings. Windows, recordings from one bearing, folds, and seeds are not inferential replicates. A post-hoc no-refit audit retained positive effects in all 18 cells after each single-bearing and each class-balanced matched-group deletion. | Mitigated, not closed; HUST still has only five physical bearings per class, and deletion ranges are not confidence intervals. |
| “Paderborn was analysed after outcomes were known.” | Every Paderborn factorial/sensor/raw claim is labelled retrospective. HUST topology, code, thresholds, expected artifacts, and runtime dependencies were sealed before signal-model outcomes. | Mitigated, not erased. |
| “HUST does not independently identify bearing identity.” | The held specification index contains three class-specific specimens and confounds specimen with specification. The manuscript states this explicitly. | Intrinsic limitation. |
| “The rank headline is driven by ceiling noise.” | Absolute score ranges, ties, every rank shift, and Kendall tau are reported together. HUST's undefined tau and failure to reproduce the directional reversal are headline results. | Mitigated; do not lead with rank reversal alone. |
| “The methods are not faithful reproductions.” | They are controlled mechanism-family implementations with a common backbone, selector, budget, and seeds. Exact reproduction of original architectures is not claimed. | Residual external-validity limitation. |
| “Engineered features predetermine the result.” | Classical and three neural sensor views agree on an access gap. A separately sealed raw/FFT/STFT family is rerunning from scratch and must be reported whether positive or null; interrupted EXP-456 is excluded. | Open until EXP-456R1/457. Four windows remain a bounded sensitivity. |
| “Multiple post-hoc analyses invite selective reporting.” | Dataset roles, seals, amendments, failed runs, full method tables, all intervals, and prohibited claims are retained. The HUST advancement rules were frozen; sensor/raw analyses are labelled retrospective. | Mitigated if the final chronology stays concise. |
| “Percentile intervals are overinterpreted.” | They are described as cohort-conditional descriptive intervals, not hypothesis tests or factory-population guarantees. No seed- or window-level p-values are used. | Mitigated; independent statistical review remains required. |
| “A self-validator is not independent.” | Validators refit no model and recompute topology, aggregation, metrics, ranks, and draws from locked predictions. This catches implementation drift but can share conceptual errors. | Open: clean environment and external reproduction/human review required. |

## Claim stress test

The evidence supports the following bounded statements:

1. all 27 Paderborn compact-feature sensor-by-method and all nine HUST random-minus-crossed
   physical-bearing interval lower limits are positive on the observed cohorts;
2. HUST meets the predeclared protocol-gap rule and its equal-volume control rules out source-
   record count alone;
3. no single observed HUST bearing or class-balanced matched group reverses any of the 18 audited
   protocol effects, in a post-hoc sensitivity analysis;
4. Paderborn method leaders and sensor conclusions depend on the access protocol; and
5. HUST's saturated easy protocols do not support a directional method-order replication.

The evidence does **not** support these statements:

- a causal amount of identity leakage;
- a universal ranking or failure of ERM/CORAL/VREx/GroupDRO/DANN/LISA/MatchDG/CCDG/PIRL;
- state-of-the-art fault diagnosis;
- safety, calibration, or factory-deployment validity;
- cross-dataset superiority of PIRL; or
- priority for bearing-wise, leakage-safe, HUST, multi-sensor, raw, FFT, STFT, or compound-shift
  evaluation.

## Submission decision rule

The work may be called an internally complete **top-domain-journal candidate** only after:

- [ ] EXP-456R1 and EXP-457 finish and the full raw result independently validates;
- [ ] EXP-458--461 regenerate and independently validate the final tables, figures, manifest, and
      empirical-final manuscript from locked inputs;
- [ ] main and clean environments pass Ruff, full tests, and the frozen coverage threshold;
- [ ] every generated figure is visually inspected and every manifest hash is rechecked;
- [ ] an author-approved public commit and archival artifact identifier exist; and
- [ ] a condition-monitoring expert and independent statistician/reproducer review the work.

Even if every item closes, RESS/MSSP/TIM acceptance and venue tier remain external judgments.
