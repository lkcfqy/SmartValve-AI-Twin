# Cranfield source-only selective-prediction protocol v0.1

- Status: exploratory protocol frozen after EXP-010 and before EXP-012 results
- Frozen: 2026-08-17
- Primary representation: P0 raw features, with no target healthy trajectory
- Seeds: `[11, 23, 37, 53, 71]`

EXP-010 already revealed the `trap/-40` failure, so this experiment is explicitly post-result and
cannot be presented as a confirmatory pre-registration.

## Outer prediction protocol

Retain the six motion-specific leave-one-load-out folds and the frozen ExtraTrees estimator. No
target fault label selects a threshold, model, feature, or gate.

## Selection policies

1. `none`: accept every prediction.
2. `source_ood_conformal`: build source out-of-load probabilities by training on each one of the two
   source loads and predicting the other. Use nonconformity `1 - p(true class)` and the finite-sample
   90% conformal quantile. The final two-source model emits a label only when its conformal prediction
   set is a singleton.
3. `metadata_support`: target load metadata are allowed, but target trajectories and labels are not.
   Let `span = max(source_load)-min(source_load)` and let `distance` be zero inside the source load
   interval or the distance to its closest edge outside. Accept when `distance/span <= 1.0`.
4. `hybrid`: require both singleton conformal output and metadata support.

The `distance/span` threshold and conformal alpha `0.10` are frozen here and cannot be changed after
target results are read. The metadata gate is a transparent support-envelope baseline, not a claim
of distribution-free coverage.

## Metrics

- coverage and abstention rate;
- selective accuracy and accepted error count;
- macro F1 with abstention counted as an error;
- error-detection recall (fraction of base-classifier errors rejected);
- correct-prediction rejection rate;
- worst-fold coverage, selective accuracy, and accepted error count.

A method is not called safe when it obtains high selective accuracy by zero coverage. Fold-level
results and the full coverage-risk curve remain visible.
