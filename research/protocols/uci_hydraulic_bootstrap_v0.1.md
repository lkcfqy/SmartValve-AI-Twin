# UCI hydraulic paired physical-block bootstrap protocol v0.1

- Status: frozen before the EXP-110 point estimates were available
- Frozen: 2026-08-18
- Input protocol: `research/protocols/uci_hydraulic_access_v0.1.md`
- Planned input: the immutable full prediction record from EXP-110
- Replicates: 2,000
- RNG seed: 20,260,818
- Interval: paired percentile 95% confidence interval

## Estimand and physical unit

The resampling unit is the complete four-valve-state block
`(cooler, pump, accumulator, repetition)`. Model seeds are averaged within each bootstrap
replicate and are not treated as physical replicates. Every bootstrap draw is shared by P0, P1,
P2 and all five estimator families so that protocol and estimator contrasts remain paired.

Each estimator family is reported separately. A qualitative access result is called
model-independent only when at least three of the five frozen families satisfy the pre-specified
paired-interval rule. No pooled row-level confidence interval is permitted.

## Performance resampling

Within each of the 36 exact context cells, sample its ten complete four-state blocks with
replacement. Retain ten draws per cell. Use the same sampled cohort for all ten held-level folds.
This stratification preserves every context level and the frozen fold sizes while allowing a
physical block, not an individual state or prediction row, to repeat.

For every estimator/protocol/seed, recompute the unweighted mean of ten fold accuracies, macro F1
scores and multiclass Brier scores; the minimum fold macro F1; and the unweighted mean of the three
axis ECE values. Average each metric over the five frozen model seeds only after it is recomputed
within a draw.

## Probability-response control resampling

The matched probability controls require a different topology from performance. For each held
factor axis and each fixed combination of the other two context factors, sample ten repetition
indices with replacement and apply the same indices to every level of the held factor. This
preserves nuisance pairs that vary one context factor while holding the other context factors,
valve state, and sampled repetition fixed. It also preserves the four-state fault pairs within
every exact context.

For each axis, recompute mean context total variation, mean fault total variation and their ratio.
Then report maximum context TV, mean fault TV and maximum control ratio across the three axes. The
performance and control streams use deterministically separated RNG streams; both are paired
across protocols and estimators.

## Frozen comparisons and decisions

For each estimator, form paired replicate differences for `P1-P0`, `P2-P0`, and `P2-P1`.

- Cranfield conclusion C1 is externally replicated by an estimator only if the 95% interval for
  P1-P0 mean-fold macro F1 is wholly below zero.
- Cranfield conclusion C2 is externally replicated by an estimator only if the P2-P0 mean-fold
  macro-F1 interval includes zero and the P2-P0 mean-fold multiclass-Brier interval is wholly above
  zero.
- Either conclusion is model-independent on UCI only if at least three of five estimator families
  satisfy its rule.
- Any other result is cross-rig or cross-model heterogeneity and remains in the paper.

These are replication decisions for the access audit, not efficacy tests of the future SmartValve
method. Multiplicity correction for the later multi-dataset primary method comparisons will be
frozen separately before those comparisons are run.

## Integrity gates

The run must stop before resampling unless the record contains exactly 324,000 rows: 1,440 cycles
times three factor axes, three protocols, five estimators and five seeds. Within every
estimator/protocol/seed/axis cell, each frozen cycle must occur exactly once and its held level must
match its context value. Probabilities must be finite and sum to one. P0/P1 must have no baseline
repetition; P2 must use exactly `repetition mod 10 + 1`, never the current repetition.

Persist the input SHA-256, all replicate-level metrics, interval summaries, replication decisions,
command, environment and source fingerprint. A failed validation is recorded as a failed run and
must not be repaired by editing the prediction record.
