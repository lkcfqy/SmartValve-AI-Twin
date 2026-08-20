# Multi-rig methods

## Study roles and information boundary

The study uses a development/validation split at the dataset level.

| Role | Dataset | Physical unit | Use in method development |
|---|---|---|---|
| D0 | Cranfield linear actuator | complete repetition/state block | method design and source-only selection |
| D1 | UCI Hydraulic condition monitoring | complete physical cycle/block | external development and selection |
| D2 | Paderborn Bearing DataCenter | bearing identity | sealed prospective validation only |

PIRL, the comparison methods, hyperparameter grids, seeds, endpoints, practical threshold,
resampling unit, and multiplicity rule were fixed using D0/D1 before model outcomes from D2 were
inspected. D2 is therefore a prospective test for the frozen candidate, not another tuning dataset.
After D2 was opened, no method or hyperparameter was reselected.

All headline models operate in the P0 regime: training, model selection, rejector selection, and
threshold selection use source-domain data only. Target labels, target trajectories, and target
performance are absent from those selectors. Earlier P1/P2 healthy-reference experiments remain
access-audit controls and are not pooled with the P0 headline results.

## Frozen candidate and comparators

The candidate is PIRL v0.2, a compact multilayer perceptron with a source-only fault/context
response-ratio term and an anti-collapse margin. Its frozen configuration uses a 64-dimensional
representation, ratio weight 1.0, margin 0.5, hidden dimension 128, AdamW learning rate 0.001,
weight decay 0.0001, and 300 epochs. EXP-330 selected this configuration from source-only inner
partitions on D0/D1.

The final comparison contains nine methods under the same feature inputs, outer folds, five seeds,
and source-only model-selection discipline:

- PIRL;
- identical-backbone ERM;
- CORAL;
- VREx;
- GroupDRO;
- DANN;
- LISA;
- MatchDG; and
- CCDG.

The locked D0/D1 ablation compares full PIRL, ratio-only, margin-only, and identical-backbone ERM.
It is an attribution test, not an additional opportunity to tune the final D2 method.

## Paderborn cohort and preprocessing

The official archive inventory contained 2,560 canonical MAT measurements. The frozen primary
cohort expected 2,320 measurements from 29 single-condition bearing identities across four
operating settings and 20 measurements per bearing/setting. Three additional compound-damage
bearing identities contributed 240 secondary rows.

One primary file, `N15_M01_F10_KA08_2.mat`, was structurally unreadable by the pinned parser. It was
excluded under the pre-outcome structural-failure amendment; no value was imputed and no neighboring
measurement was substituted. The retained primary cohort therefore contains 2,319 measurements,
with 79 rather than 80 measurements for KA08. All 240 compound rows remain available for secondary
diagnostics.

Three four-second, 64 kHz main signals are used: synchronous vibration, current phase U, and current
phase V. Twenty-four deterministic whole-trajectory statistics are computed independently for each
channel, producing 72 features per measurement. Speed, torque, force, temperature, labels, and
target outcomes are excluded from classifier features. Feature extraction is one record per full
trajectory; no overlapping windows are treated as independent samples.

The primary model design has 24 frozen folds. Source, target, and cross-arm quarantine identities
are materialized separately, and quarantine rows are physically absent from the training view.
Every retained primary measurement is target exactly once except for the predeclared structural
exclusion.

## Source-only selection and final evaluation

Each method is selected on source-only inner partitions. The final model is then refit on the
complete permitted source view and evaluated once on its held-out target view. Five fixed seeds are
used. The Paderborn base run contains 9 × 5 × 24 = 1,080 final models, 104,355 primary target rows,
and 259,200 compound-target rows.

Closed-set descriptive metrics are pooled macro F1, minimum-setting macro F1, minimum
identity-setting-fold macro F1, multiclass Brier score, and 10-bin expected calibration error.
The confirmatory closed-set endpoint is the paired difference in minimum-setting macro F1,
PIRL minus ERM.

## Selective prediction

The selective comparison is restricted to PIRL and identical-backbone ERM. Out-of-fold source
predictions select the risk-envelope parameter and the score threshold. Nominal source coverages
of 50%, 70%, and 90% are retained, with an explicit source-environment coverage floor. No target
row is available to parameter, score, or threshold selection.

The confirmatory selective endpoint uses the source-selected nominal 50% policy. The effect is
defined as ERM selective risk minus PIRL selective risk, so positive values favor PIRL. Descriptive
unweighted fold means and pooled physical-unit inference are reported separately because their
weighting estimands differ.

## Physical-unit uncertainty and multiplicity

Each dataset uses 2,000 paired bootstrap replicates with a fixed RNG seed and the physical unit
appropriate to its design. Method predictions stay paired inside every draw.

- Cranfield resamples complete repetition/state blocks within its frozen design.
- UCI resamples complete hydraulic physical blocks within the balanced frozen cohort.
- Paderborn resamples 29 bearing identities stratified by truth class; all setting/measurement rows
  belonging to a sampled identity are retained together. KA08 contributes its observed 79 rows.

For each of three datasets, the family contains two tests: minimum-environment macro F1 and
selective risk at source 50% coverage. A dataset-endpoint is confirmatory-positive only when all
three conditions hold: point effect at least 0.01, 95% percentile interval lower bound above zero,
and Holm-adjusted two-sided p at most 0.05. The internal multi-dataset gate additionally requires a
positive endpoint on at least two datasets and no materially harmful endpoint whose interval
excludes zero. Subset replacement and pooled post-hoc tests are prohibited.

## Disclosed structural reconciliation

The numerical model outputs were not rerun or modified during reconciliation.

1. The original base and selective validators expected archive-manifest row indices, whereas the
   feature/evaluation path used compact retained-row indices after excluding the unreadable file.
   Because that exclusion precedes all compound rows, each compound index differed by exactly one.
   A frozen mapping restored the original coordinate system; key sets then matched exactly.
2. The original bootstrap assertion still required 2,320 primary rows. The reconciled wrapper
   accepted the already documented 2,319-row cohort, preserved the 29-bearing class-stratified
   design, and performed no imputation.
3. The original six-test assembler rejected the reconciled bootstrap version string. The final
   wrapper accepted version 0.2 and the 2,319 count while leaving the six family members, effects,
   p-values, and Holm algorithm unchanged.

Both failed unmodified attempts and successful reconciled validations are retained. The exact
protocol and source hashes are recorded in `research/D2_FINAL_DECISION.md` and
`research/EXPERIMENT_LEDGER.md`.

## Compute environment

Experiments ran under WSL2 Ubuntu 24.04 with Python 3.12.3, 16 logical CPUs, approximately 15 GiB
WSL memory, and an RTX 3080 with 10,240 MiB VRAM. The compact neural models fit this hardware; no
H100/H200-class accelerator is required to reproduce the reported work.
