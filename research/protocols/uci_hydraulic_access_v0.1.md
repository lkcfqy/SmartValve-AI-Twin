# UCI hydraulic target-access audit protocol v0.1

- Status: frozen before any UCI sensor feature or model result was inspected
- Frozen: 2026-08-18
- Dataset DOI: <https://doi.org/10.24432/C5CW21>
- Official archive SHA-256:
  `24128aad2ee45eea7e6b63ebbd9992cdf25d0483a2cebefbfc13bc69079af1f2`
- License: CC BY 4.0
- Protocol role: D1 external development/replication; not the sealed prospective D2 dataset

## Scientific question

Does the Cranfield conclusion about healthy-reference access survive on a different physical
hydraulic rig when the target is valve condition and the context consists of independently varied
cooler, pump, and accumulator conditions?

The result is allowed to contradict the Cranfield result. It is not a test of a new SmartValve
method and cannot be used to claim cross-factory transfer.

## Experimental units and frozen cohort

The archive contains 2,205 complete 60-second load cycles. The primary cohort uses only rows with
`stable == 0`. Valve condition is the diagnostic label with four ordered values:

- `100`: optimal switching;
- `90`: small lag;
- `80`: severe lag; and
- `73`: close to total failure.

The context is `(cooler, pump, accumulator)`, with 3 x 3 x 4 = 36 cells. Every context contains at
least ten cycles for every valve state. Within each exact context/valve cell, cycles are ordered by
their archive row and assigned repetition `1..n`. The confirmatory factorial retains repetitions
`1..10`, producing exactly 1,440 cycles and 360 complete physical blocks. Nine surplus optimal-valve
cycles in one cell are excluded by this pre-result completeness rule.

One complete 60-second cycle is the prediction unit. The physical bootstrap block is
`(cooler, pump, accumulator, repetition)` and carries all four valve states.

## Sensors and frozen features

The primary representation uses the 14 measured physical sensors: six pressures (`PS1..PS6`),
motor power (`EPS1`), two flows (`FS1`, `FS2`), four temperatures (`TS1..TS4`), and vibration
(`VS1`). The derived channels `CE`, `CP`, and `SE` are excluded from the primary analysis and may
appear only in a declared ablation.

For each sensor independently, extract 24 deterministic cycle features:

1. mean, population standard deviation, RMS, minimum, maximum, peak-to-peak;
2. 5th, 25th, 50th, 75th, and 95th percentiles, IQR, mean absolute value;
3. skewness and excess kurtosis, with zero for a constant signal;
4. mean absolute first difference, RMS first difference, and a least-squares slope on time scaled
   to `[-1, 1]`; and
5. DC-removed normalized spectral centroid, spectral bandwidth, spectral entropy, and power
   fractions in normalized frequency bands `[0,0.1)`, `[0.1,0.25)`, and `[0.25,0.5]`.

This gives 336 P0 features. P1 and P2 interleave a delta and relative value for every feature,
giving 672 features. The relative denominator is `abs(reference) + 1e-6`. Non-finite values stop
feature generation; they are not silently replaced at this stage.

## Outer shifts

Hold out one complete level of one context factor and retain all combinations of the other two
factors. This gives ten folds:

- cooler: `3`, `20`, `100`;
- pump leakage: `0`, `1`, `2`; and
- accumulator pressure: `90`, `100`, `115`, `130`.

Every cycle is tested exactly once within each factor axis and therefore appears in three different
axis-specific predictions. Metrics are first computed within folds/axes; duplicated rows are never
treated as additional independent physical samples.

No target valve label selects a feature, estimator, threshold, reference model, or hyperparameter.

## Access protocols

### P0: raw, no target reference

Use the 336 current-cycle features. Neither target-context healthy cycles nor context metadata are
used by the classifier.

### P1: source-only context model

The context metadata are known, but no cycle from the held-out context-factor level is read. Map the
three context variables monotonically to `[0,1]`, expand them to degree-two polynomial terms, and fit
a multi-output ridge model with `alpha=1.0` from source optimal-valve cycles to the healthy feature
vector.

For a source training row of repetition `r`, fit its reference model after excluding all source
optimal-valve rows with repetition `r`. For a target row, fit once using every source optimal-valve
row. This repetition cross-fitting prevents an optimal training row from helping construct its own
reference.

### P2: matched-target context reference

Use a different optimal-valve cycle from the same exact context. The baseline repetition is
`r mod 10 + 1`. P2 reads a target-context healthy trajectory and therefore represents calibration,
not target-free domain generalization.

## Frozen estimator suite

Use the same five classical families and hyperparameters as the Cranfield EXP-020 protocol:

- ExtraTrees;
- balanced multinomial logistic regression;
- balanced RBF-SVM with probability output;
- histogram gradient boosting with balanced sample weights; and
- shrinkage LDA.

Seeds are `[11, 23, 37, 53, 71]`. Preprocessing is fitted on source rows only. No UCI target result
may tune a parameter.

## Metrics and controls

Primary performance metrics are the unweighted mean of ten fold macro F1 values, worst-fold macro
F1, and the unweighted mean fold multiclass Brier score. Also report accuracy, per-axis aggregates,
per-class metrics, ECE, confusion matrices, and every fold separately.

For each held-factor axis, negative controls change one context factor while holding the other two
context factors, valve state, and repetition fixed. Positive controls change valve state while
holding the complete context and repetition fixed. Report factor-specific probability total
variation, fault total variation, and `max context TV / fault TV`. Controls are averaged over axes
only after being computed on nonduplicated matched groups.

## Uncertainty and replication decisions

After the point implementation is frozen, use at least 2,000 paired bootstrap replicates over the
complete four-state physical blocks. Apply identical draws to all protocols and estimators.

- Cranfield C1 is externally replicated only if the P1-P0 macro-F1 interval is wholly below zero.
- Cranfield C2 is externally replicated only if the P2-P0 macro-F1 interval includes zero and the
  P2-P0 Brier interval is wholly above zero.
- Any other outcome is reported as cross-rig heterogeneity, not a failed or excluded experiment.
- A model-independent result requires the same qualitative paired direction in at least three of
  the five estimator families.

No multiplicity claim is made until the multi-dataset primary comparison family is frozen.

## Stop conditions and audit outputs

Stop before model fitting if archive integrity, row counts, stable-factorial completeness, sensor
matrix shapes, feature finiteness, reference separation, or split disjointness fails.

Persist the selected cohort, feature schema and hashes, fold assignments, all probabilities,
reference repetition/access fields, per-seed metrics, and a source fingerprint. Failed and null runs
remain in the experiment ledger.

