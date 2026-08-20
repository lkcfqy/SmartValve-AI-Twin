# Cranfield intervention audit protocol v0.1

- Status: pre-registered before new audit results
- Frozen: 2026-08-17
- Dataset DOI: <https://doi.org/10.17862/cranfield.rd.5097649>
- License: CC BY 4.0

## Experimental units

The dataset contains 180 complete 25 Hz trials:

- motions: `trap`, `sin`;
- loads: `-40`, `20`, `40` kgf;
- states: `normal`, `lack_of_lubrication`, `backlash`;
- repetitions: `1..10`;
- samples per trial: 2,000.

The complete trial is the minimum split unit. The paired bootstrap block is
`(motion, load_kg, repetition)` and contains all three states. Samples within a trial are not treated
as independent observations.

## Outer evaluation

For each motion, hold out one entire load and train on the other two loads. This produces six outer
folds, each with 60 training and 30 test trials. The held-out fold is used exactly once per frozen
configuration. It cannot be used to choose hyperparameters or a decision threshold.

Motion-specific models are the primary analysis. A cross-motion analysis may be added under a new
protocol version because motion is a distinct intervention rather than a minor nuisance variable.

## Reference-access protocols

### P0: raw_no_target_reference

Use the interpretable raw distribution and travel-bin features from the current trial. No healthy
trial from the target load is available. This is the strictest domain-generalization setting.

### P1: source_healthy_reference

Construct the healthy reference using only normal trials from the two training loads of the current
outer fold. The target load value may be known, but no target-load trajectory may be read. Any
load-conditioned prediction of a healthy feature is fitted on source healthy trials only. Training
rows use leave-one-trial-out healthy estimates where applicable.

### P2: matched_target_healthy_reference

Compare each current trial with a different normal repetition from the same motion and load. This is
the checked-in SmartValve assumption and represents deployment with target-condition calibration.
The target healthy trace is an explicit input resource and is not described as pure DG.

## Controls

Negative control:

- change load while holding motion, configured fault state, and repetition index fixed;
- the diagnostic label remains fixed within the documented operating envelope;
- quantify total-variation or Jensen-Shannon distance between predicted class distributions.

Positive control:

- change fault state while holding motion, load, and repetition index fixed;
- predicted class distributions should separate;
- quantify the same distance family used for the negative control.

The repetition index provides a matched experimental grouping, not an individual counterfactual;
unobserved run noise is not assumed identical across loads.

## Estimators and seeds

The reproduction run uses the checked-in ExtraTrees configuration and seed `42`. Audit runs use
seeds `[11, 23, 37, 53, 71]`. New estimators receive an inner source-only selection protocol before
their outer results are inspected.

## Metrics and uncertainty

Primary:

- macro F1;
- worst-fold macro F1;
- multiclass Brier score;
- nuisance sensitivity;
- fault sensitivity;
- control ratio.

Secondary:

- accuracy, per-class precision/recall/F1, confusion matrix;
- 10-bin ECE, maximum calibration error, and mean confidence;
- environment-prediction probe, reported as diagnostic evidence rather than proof of shortcut use.

Confidence intervals use at least 2,000 deterministic block-bootstrap resamples after the metric
implementation is frozen. Exploratory runs may use fewer resamples and must be labeled exploratory.

## Missing values and transformations

- Non-finite extracted features are documented by name and count before imputation.
- Imputation statistics, scaling, and calibration are fitted on training data only.
- No test-load statistic is used in P0 or P1.
- P2 may read the declared matched healthy reference, but not target fault labels.

## Falsification and stopping

A claimed mechanism-sensitive model fails the negative-control audit if its diagnostic distribution
changes more across label-preserving loads than across configured fault states, or if its worst fold
is indistinguishable from chance without an explicit abstention. This threshold is a falsification
criterion, not a universal definition of causality.

All deviations from this document require a new protocol version and a ledger entry made before the
corresponding result is interpreted as confirmatory.
