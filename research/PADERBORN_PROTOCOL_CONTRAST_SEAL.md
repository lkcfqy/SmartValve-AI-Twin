# Paderborn protocol-contrast development seal

- Frozen: 2026-08-19 (Asia/Shanghai), before EXP-433 execution
- Status: retrospective D2 development; never confirmatory
- Input: EXP-406 primary feature matrix
- Input SHA-256: `c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4`
- Random seed: `20260819`

## Question

Holding features, labels, model capacity, and evaluation units fixed, how much do reported fault
diagnosis performance and model ranking change as the deployment split moves from shared physical
context to simultaneous unseen bearing identity and operating setting?

This analysis was conceived after Paderborn outcomes were opened. It is a reproducible diagnostic
and a protocol-design input for D3, not a confirmatory test of a newly stated hypothesis.

## Four out-of-fold protocols

Every protocol must produce exactly one prediction for each of the 2,319 eligible pure-class
measurement files.

1. `measurement_random`: six-fold class-stratified shuffled measurement-file CV. A physical bearing
   and operating setting may occur in both source and target. This is the deliberately optimistic
   shared-context comparator, not a deployment-valid estimate.
2. `setting_holdout`: four leave-one-operating-setting-out folds. Bearing identities are shared;
   the setting is unseen.
3. `identity_holdout`: the six predeclared Paderborn identity folds. Settings are shared; held
   bearing identities are unseen.
4. `crossed_holdout`: the 24 predeclared identity-fold × setting folds. Training uses only
   `(not held identity) AND (not held setting)`, testing uses the held-axis intersection, and the
   two XOR cross-arms are quarantined from that fold.

No target record or quarantined cross-arm may enter preprocessing or fitting. Labels may be used
only to define the frozen stratification and identity-fold class balance, train on source rows, and
score completed target predictions.

## Fixed feature and model suite

All 72 EXP-406 main-signal features are retained. No feature selection or target-dependent
normalization is allowed. The seven fixed comparisons are:

- `dummy_prior`: source class-prior dummy classifier;
- `nearest_centroid`: source-only standardization, Euclidean nearest centroid;
- `shrinkage_lda`: source-only standardization, LSQR LDA with automatic shrinkage;
- `logistic_l2`: source-only standardization, L2 logistic regression, `C=1`, LBFGS,
  `max_iter=5000`;
- `linear_svm`: source-only standardization, linear SVM, `C=1`;
- `rbf_svm`: source-only standardization, RBF SVM, `C=1`, `gamma=scale`;
- `extra_trees`: 256 trees, `max_features=sqrt`, `min_samples_leaf=1`, no bootstrap,
  one worker, seed `20260819`.

There is no hyperparameter search. Paired scatter is excluded from this main contrast because
EXP-432 showed large ridge sensitivity; it remains a separately reported development baseline.

## Common evaluation units and estimands

Predictions from all four protocols are mapped to the same 24 identity-fold × setting cells. For
each method and protocol report:

- pooled macro F1, balanced accuracy, and accuracy across all 2,319 out-of-fold predictions;
- mean, median, minimum, and 25th percentile of the 24 cell-level macro F1 values;
- minimum class recall across the pooled confusion matrix;
- method rank under pooled and mean-cell macro F1;
- Kendall rank agreement with `crossed_holdout`;
- paired pooled-macro-F1 differences relative to `crossed_holdout`.

Uncertainty for protocol differences uses 2,000 deterministic paired bootstrap draws. The
resampling unit is physical bearing identity, stratified by the three pure classes. All rows for a
selected identity are duplicated together, and the same draw is applied to both compared
protocols. Intervals are descriptive 2.5/97.5 percentiles; there is no post-hoc significance label.

## Interpretation constraints

- A high random-split score cannot be described as deployment generalization.
- A lower crossed score alone does not prove leakage; it quantifies the consequence of shared
  versus unseen context under this corpus and feature suite.
- Rank reversals are benchmark sensitivity, not proof that any one model is universally superior.
- Window-level sample counts and tests are prohibited; the measurement file is the prediction row
  and bearing identity is the resampling unit.
- Findings may motivate the untouched D3 protocol, but no D2 result may tune the sealed D3 primary
  hypothesis after signal access.

## Fail-closed checks

Execution must stop if the input hash changes, the official 2,319-row index is incomplete, any
protocol misses or duplicates a target row, a source/target overlap occurs, a crossed quarantine
row enters fitting, any source fold loses a class, any output prediction has an unknown class, or
the 24 common evaluation cells do not each contain all three labels.
