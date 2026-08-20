# Cranfield estimator and environment-probe protocol v0.1

- Status: frozen before EXP-020 results
- Frozen: 2026-08-17
- Outer folds: six motion-specific leave-one-load-out folds
- Seeds: `[11, 23, 37, 53, 71]`
- Primary representation: P0 raw features
- Calibration comparator: P2 matched-target healthy reference

## Fixed estimator suite

No held-out target result selects hyperparameters.

1. `extra_trees`: the frozen 500-tree configuration used in EXP-010.
2. `logistic`: median imputation, standard scaling, logistic regression with `C=1.0`, balanced class
   weights, and `max_iter=5000`.
3. `rbf_svm`: median imputation, standard scaling, RBF SVC with `C=1.0`, `gamma='scale'`, balanced
   class weights, and probability output enabled.
4. `hist_gradient_boosting`: median imputation, 200 iterations, learning rate `0.05`, at most 15 leaf
   nodes, and L2 regularization `1.0`; balanced sample weights are fitted from source labels.
5. `shrinkage_lda`: median imputation, standard scaling, LSQR LDA with automatic shrinkage.

Report macro F1, worst-fold macro F1, Brier score, nuisance/fault TV, control ratio, and all six fold
results. A finding is model-independent only if the same qualitative worst-fold failure appears in
at least three estimator families.

## Environment-prediction probe

For P0 and P2 separately, predict load class within each motion. Hold out one repetition index at a
time, so every test fold contains all three loads and fault states and no repetition index appears in
training. Use the frozen ExtraTrees configuration and five seeds. Report load macro F1 and confusion
matrices. High load predictability is diagnostic evidence that the representation retains nuisance
information; it is not proof that the fault classifier uses that information causally.
