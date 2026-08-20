# Paderborn D2 execution amendment v0.1

- Status: frozen before any Paderborn D2 model fit or model-outcome access
- Frozen: 2026-08-18
- Original prospective protocol SHA-256: `13dd812dbdc756ba5e4ad4997f1828a681b9cbbd68536dea8b167a051ddcef33`
- Original final seal SHA-256: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Final feature-contract amendment SHA-256: `439582a767b41cbba3679902174a5e81cf8fe764a8d276fba98b62bc81480149`
- Feature-run metrics SHA-256: `4425947919dc8e6730c7cf83dc8e33a8b58a64e07d777cd14527806667663de2`
- Independent feature validation SHA-256: `4bda1dd3e1588b1762f93472aa8601cd90a60690ba9c2449916c80746a055326`

## Purpose

This amendment changes only the Paderborn measurement topology forced by the
outcome-blind structural findings documented in feature-contract amendment v0.5.
It does not change a method, selected configuration, seed, outer split definition,
inner split rule, feature definition, training objective, stopping rule, selective
score, coverage, endpoint, effect-size threshold, confidence interval, hypothesis
test, or multiplicity family frozen in the original protocol.

The exact locked file `N15_M01_F10_KA08_2.mat` (8,714,872 bytes; SHA-256
`e137cbb2368caa8bd56889eff8609d2569d2c196a85107e16aa4740437f2ccb3`)
is structurally unreadable by the frozen SciPy reader and both separately authorized
root-isolation recovery strategies. It is the sole exclusion. The feature artifacts
contain 2,559 readable measurements and passed an independent pre-model validation:
2,319 pure-class measurements, 240 compound stress measurements, 72 finite features,
24 folds, and target coverage exactly once for every retained pure measurement.

## Frozen amended outer topology

The outer design remains the complete product of six predeclared bearing-identity
folds and four official operating settings. Source is still the complement of both
held axes, target is still their intersection, and both cross arms remain quarantined.
The one missing key changes only the affected row counts:

- Identity folds 0--4 with held setting `N15_M01_F10`: 1,440 source, 100 target,
  779 quarantine.
- Identity folds 0--4 with any other held setting: 1,439 source, 100 target,
  780 quarantine.
- Identity fold 5 with held setting `N15_M01_F10`: 1,500 source, 79 target,
  740 quarantine.
- Identity fold 5 with any other held setting: 1,500 source, 80 target,
  739 quarantine.

Every retained pure measurement is target in exactly one fold. Fault-pair strata
remain balanced at 900 source-local pairs per fold. Nuisance-pair counts are derived
deterministically from retained source rows; no signal feature or outcome selects a
pair.

## Frozen amended base-evaluation cardinalities

The base comparison remains nine methods, five seeds, and 24 outer folds:

- fitted models and fold-metric rows: **1,080**;
- closed-set target predictions: **104,355**;
- unlabeled compound predictions: **259,200**.

The selected PIRL-ratio and eight baseline configurations remain byte-bound to the
original seal. Compound samples still have no forced single-class ground truth and
no compound accuracy may be reported.

## Frozen amended selective-evaluation cardinalities

The selective comparison remains PIRL-ratio versus same-architecture ERM, five
individual seeds, one five-seed ensemble, three source-only inner partitions, the
same scores, and source coverages 0.5, 0.7, and 0.9:

- inner training models: **720**;
- source OOF individual predictions: **347,850**;
- target individual predictions: **23,190**;
- compound individual predictions: **57,600**;
- source OOF ensemble predictions: **69,570**;
- target ensemble predictions: **4,638**;
- compound ensemble predictions: **11,520**;
- policies and policy-metric rows: **5,760** each;
- beta selections: **288**;
- ranking metrics: **1,920**;
- target selection decisions: **556,560**;
- compound decisions: **1,382,400**;
- compound policy metrics: **5,760**.

All thresholds and risk-envelope beta selections remain source-OOF-only. Target and
compound scores cannot influence fitting, stopping, configuration selection, beta,
or thresholds.

## Statistical analysis and claims

The original cluster-aware bootstrap, paired comparison direction, practical
thresholds, and confirmatory-family rules remain frozen. The bearing identity stays
the cluster unit. The single structural exclusion is disclosed in the cohort flow
and sensitivity discussion; it is not imputed and no replacement observation is
introduced. A positive claim still requires the originally frozen practical and
uncertainty criteria. Null or adverse external results must be reported as such.

## Authorization boundary

This document authorizes regeneration of metadata/structure-informed split, model-
fold, base expected-key, and selective expected-key manifests for the exact retained
cohort. It does not itself authorize model fitting. A machine-readable execution
seal must bind this document, the original seal, the feature amendment, feature
metrics, independent validation, regenerated manifests, evaluator source, tests,
and exact D0/D1 configuration identifiers. Only that sealed bundle may authorize
the one-shot D2 run.

At freeze time, the Paderborn archives and feature values had been processed as
documented, but no Paderborn model had been fitted, no prediction existed, no model
metric had been computed, and no model outcome had been inspected. The topology
change is structural rather than performance-guided.
