# Methods scaffold

> **Historical scope notice.** This file preserves the detailed Cranfield-only audit. The current
> headline design is `MULTIRIG_METHODS.md`; do not use this scaffold alone to describe the final
> three-rig paper.

This document is section-ready source material. Protocol documents under `research/protocols/` are
the authority if wording here is ambiguous.

## Study design and data

The study uses the Cranfield Real Linear Actuator Rig dataset, released under CC BY 4.0
[@RuizCarcel2018; @CranfieldData2018]. The apparatus is an electromechanical ball-screw actuator,
not a water valve. The analyzed factorial grid contains two motion profiles (`trap`, `sin`), three
loads (-40, 20, and 40 kgf), three configured states (`normal`, `lack_of_lubrication`, and
`backlash`), and ten repetitions per cell. This gives 180 complete trials. Each trial contains 2,000
samples acquired at 25 Hz.

The complete trial is the prediction unit. The physical resampling unit is the
`(motion, load, repetition)` block containing all three configured states. Time samples and windows
within a trial are never treated as independent observations.

For each motion separately, one complete load is held out and the other two loads train the model.
The six outer folds therefore contain 60 training and 30 test trials each. The held-out load cannot
select a feature, model, hyperparameter, threshold, or label. Table 1 in `generated/table_01_dataset.*`
summarizes the design.

## Trial-level features

For each trial, 136 fixed features summarize motor current, command-position error, absolute error,
velocity, absolute velocity, direction-specific motion, and position travel bins. The feature
families include percentiles, means, standard deviations, root-mean-square values,
opening-versus-closing differences, and current-error correlation. Feature extraction is fixed by
`_raw_features` in `cranfield_benchmark.py`.

P0 uses the 136 raw features. P1 and P2 use 272 features: for every raw feature `x_j` and healthy
reference `r_j`, they include

```text
delta_j    = x_j - r_j
relative_j = (x_j - r_j) / (abs(r_j) + 1e-6).
```

No raw feature was non-finite. Any non-finite transformed value would be converted to missing and
imputed by a median fitted on source training trials only.

## Target-information access ladder

Table 2 in `generated/table_02_protocol_access.*` is the canonical access declaration.

- **P0 — raw/no target reference.** The model reads only the current trial's raw features and no
  healthy target trajectory. This is the strict target-free condition.
- **P1 — source-linear healthy reference.** The mean healthy feature vector at each of the two
  source loads defines a line evaluated at the known target load. A healthy source row is omitted
  from its own load mean when constructing its training reference. No target-load trajectory is
  read; extrapolation is allowed.
- **P2 — matched-target healthy reference.** Each trial is compared with a different normal
  repetition from the same motion and load, using the deterministic rotation `r -> r mod 10 + 1`.
  P2 reads a target-condition healthy trajectory but no target fault label. It is calibration or
  adaptation, not pure domain generalization.

## Primary classifier and estimator-family audit

The frozen primary classifier is a train-only median imputer followed by ExtraTrees with 500 trees,
minimum leaf size 2, square-root feature sampling, balanced class weights, and random seeds 11, 23,
37, 53, and 71. Each seed is evaluated on the same six physical folds.

The estimator-family falsification repeats P0 and P2 with fixed, untuned logistic regression,
RBF-SVM, histogram gradient boosting, and shrinkage LDA settings in addition to ExtraTrees. All
scaling, imputation, and balanced weighting are fitted on source trials only. A worst-fold failure is
called model-independent only if the same P0 fold has accuracy at or below 1/3 for all five seeds in
at least three estimator families. Exact configurations are frozen in
`research/protocols/cranfield_baselines_v0.1.md`.

## Metrics and matched controls

We report accuracy, macro F1, worst-fold macro F1, ten-bin expected calibration error, and the
multiclass Brier score

```text
Brier = mean_i sum_k (p_ik - 1[y_i = k])^2.
```

For two predicted class distributions `p` and `q`, total variation is

```text
TV(p, q) = 0.5 * sum_k abs(p_k - q_k).
```

The negative control averages pairwise TV across loads while holding motion, configured state, and
repetition fixed. The positive control averages pairwise TV across configured states while holding
motion, load, and repetition fixed. Their ratio is

```text
control ratio = nuisance TV / fault TV,
```

where lower values indicate the desired ordering. Matched repetitions provide experimental groups,
not individual counterfactuals. A protocol triggers the frozen falsification rule if this ratio is at
least one or if any balanced three-class fold has accuracy at or below 1/3 without explicit
abstention.

## Physical-block uncertainty

Point estimates average each metric over the five frozen seeds. Bootstrap intervals quantify
physical-block uncertainty conditional on that seed ensemble; seeds are not treated as independent
physical samples.

For performance metrics, each of the six motion/load strata resamples ten
`(motion, load, repetition)` blocks with replacement. Each block carries all three states. For
control metrics, repetition indices are resampled within motion and carried across all loads and
states, preserving the matching topology. The same draw is applied to P0, P1, and P2. We use 2,000
replicates, seed 20260817, and percentile limits at 2.5% and 97.5%. A paired difference is described
as statistically resolved only when its interval excludes zero; no multiplicity correction is
claimed.

## Selective prediction

EXP-012 is post-EXP-010 exploratory. Its base is the frozen P0 ExtraTrees classifier. Four policies
are evaluated without target labels:

1. accept all predictions;
2. form source-to-source out-of-load conformal scores `1 - p(true class)` and accept only singleton
   prediction sets at alpha 0.10;
3. accept only when the known target load is no more than one source-load span outside the source
   interval; and
4. require both the singleton set and metadata support.

The support rule is an engineering envelope, not a distribution-free method. We report coverage,
selective accuracy, accepted errors, error-detection recall, correct-prediction rejection, and macro
F1 with abstention counted as an error. A zero-error accepted set is never interpreted without its
coverage.

## Repetition-disjoint environment probe

The diagnostic asks whether load remains predictable from P0 or P2 features. Within each motion,
one repetition index is held out at a time, so all three loads and states are present but repetition
identity is disjoint. For P2, the held-out repetition is never used as its healthy reference.
ExtraTrees predicts the three load classes over ten repetition folds and five seeds. High load macro
F1 diagnoses retained nuisance information; it does not prove that the fault classifier uses load or
identify a causal path.
