# Paderborn multi-sensor protocol audit seal

- Seal date: 2026-08-19 (Asia/Shanghai)
- Status: frozen retrospective sensitivity analysis; never confirmatory D2 or prospective D3
- Design version: `smartvalve-paderborn-sensor-protocol-audit-0.1.0`
- Input: EXP-406 `primary_feature_matrix.parquet`
- Input SHA-256: `c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4`
- Rows: 2,319 complete pure-class measurements after the frozen KA08 structural exclusion
- Target access: scoring only after source-only fitting; crossed XOR arms are unavailable

This seal was written after EXP-433--435 and after reading Wheat et al. (2024) and Vieira et al.
(2026). It is therefore a post-outcome Paderborn analysis. Its purpose is attribution and stress
testing, not conversion of a retrospective result into a confirmatory one.

## Prior-art boundary and motivating question

Wheat et al. demonstrate bearing-identity leakage using vibration and explicitly leave open whether
current and voltage measurements exhibit the same phenomenon. Vieira et al. compare time,
frequency, and envelope representations of vibration and show that invalid access can change the
apparent best representation. Neither reviewed work reports a Paderborn comparison of vibration,
motor current, and fused sensing under the same random, setting, identity, and crossed-access
protocols, nor the induced ranking of a controlled industrial DG suite.

The allowed question is therefore:

> How do sensor family and access protocol jointly change fault performance, physical-bearing
> re-identification, and method ranking on this observed Paderborn cohort?

This is not a claim that a performance gap estimates a causal amount of leakage. Training-set
composition differs across deployment protocols, so protocol effects describe operational
estimands. Cross-setting bearing re-identification is a shortcut diagnostic, not proof that the
fault classifier uses the decoded identity.

## Immutable feature families

Feature order is inherited from EXP-406. No feature is recomputed, selected, or standardized before
the source-only pipeline.

| Family | Included prefixes | Count |
|---|---|---:|
| `vibration` | `vibration__*` | 24 |
| `motor_current` | `current_u__*`, then `current_v__*` | 48 |
| `fusion` | all three channel blocks in EXP-406 order | 72 |

There is no single-phase current subgroup, per-feature screening, learned fusion gate, or target-
informed normalization in this audit.

## Immutable access protocols

Use the exact EXP-433/434B row topology and random seed `20260819`:

1. `measurement_random`: six stratified measurement folds;
2. `setting_holdout`: four operating-setting folds;
3. `identity_holdout`: six frozen physical-identity groups;
4. `crossed_holdout`: 24 identity-group × setting targets, with both XOR arms quarantined.

All protocols generate one out-of-fold prediction for every measurement, method, and applicable
seed. The common evaluation topology remains the same 24 identity-group × setting cells.

## Phase A: frozen classical audit

Run all three feature families with all seven untuned EXP-433 classifiers:

`dummy_prior`, `nearest_centroid`, `shrinkage_lda`, `logistic_l2`, `linear_svm`, `rbf_svm`, and
`extra_trees`.

For every family/method/protocol report pooled macro F1, balanced accuracy, accuracy, minimum class
recall, mean/median/minimum/q25 cell macro F1, and within-family ranks. Report all pairwise protocol
Kendall correlations.

Primary descriptive contrast: `measurement_random - crossed_holdout` pooled macro F1. Use 2,000
class-stratified physical-bearing bootstrap draws with one shared draw plan across sensor families.
Report the three predeclared difference-in-differences for every non-dummy and dummy method:

- `(vibration gap) - (motor_current gap)`;
- `(fusion gap) - (vibration gap)`;
- `(fusion gap) - (motor_current gap)`.

Intervals are descriptive 2.5/97.5 percentiles. No family-wise significance claim is allowed.

Secondary shortcut diagnostic: train each same fixed classifier to predict exact `bearing_code`
from three settings and evaluate on the fourth, rotating through all four held settings. Report
pooled 29-class macro F1, accuracy, balanced accuracy, and minimum class recall for every feature
family. Measurement windows remain dependent observations; this diagnostic receives no
measurement-level confidence interval.

## Phase B: frozen neural/DG audit

Run all three feature families with the exact nine D0/D1-selected configurations and seeds
`11, 23, 37, 53, 71`:

`erm`, `coral`, `vrex`, `groupdro`, `dann`, `lisa`, `matchdg`, `ccdg`, and `pirl_ratio`.

The 72-feature `fusion` predictions may be imported only from EXP-434B after exact SHA-256 and
topology validation. The `vibration` and `motor_current` families must be newly fit under all four
protocols, giving `40 × 9 × 5 = 1,800` fits per new family and 3,600 new fits total. Hyperparameters,
epochs, early-stopping semantics, source environments, pair construction, and seeds cannot change
with feature family.

Report the same pooled/cell metrics, physical-bearing bootstrap, protocol rank concordance, and
sensor difference-in-differences as Phase A. The frozen ranking endpoint is pooled macro F1; mean
cell macro F1 is secondary. Any ceiling compression must be reported beside ordinal rank changes.

## Fixed interpretation rules

- A smaller current gap than vibration gap does not prove that current is identity-free.
- High bearing-code re-identification shows decodable identity information, not causal classifier
  reliance.
- Fusion exceeding both unimodal families under a leaked protocol but not crossed access is a
  shortcut-risk pattern, not evidence that fusion is generally harmful.
- Method rank changes are properties of this finite cohort, feature contract, and selector.
- The dummy model is retained in every table and excluded only from prose about trainable methods.
- No sensor family, method, seed, fold, or metric may be omitted because its result is inconvenient.
- Phase A outcomes may not determine whether Phase B is run; Phase B is mandatory under this seal.
- All code failures, reconciliation changes, artifact hashes, durations, and CUDA memory statistics
  must be retained in the experiment ledger.

## Advancement condition

This audit strengthens the paper only if all planned artifacts validate independently and the final
manuscript positions the result relative to Wheat and Vieira without a priority claim. Regardless of
direction, the complete sensor-family result advances to the paper. It cannot replace the unopened
HUST factorial D3 replication.
