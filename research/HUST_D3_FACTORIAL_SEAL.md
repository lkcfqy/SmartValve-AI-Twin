# HUST D3 factorial external-replication seal

- Seal date: 2026-08-19 (Asia/Shanghai)
- Protocol version: `smartvalve-hust-d3-factorial-0.1.0`
- Status: sealed before MAT download, MAT opening, signal feature extraction, or HUST model fitting
- Dataset: HUST Bearing v3, DOI `10.17632/cbv7jyx4p9.3`, CC BY 4.0
- Official metadata run: `EXP-431-HUST-D3-METADATA`
- Official inventory SHA-256: `471ae25783099779d5d2ecc95f613a8ca2a6cd7614388a8b43ea538c98f3f423`
- Signal access at seal time: 0 MAT files downloaded, 0 MAT files opened, 0 signal bytes read

## Disclosure and evidence status

This is a signal-unopened, protocol-prospective replication, not a literature-outcome-blind test.
Before this seal, the project read Vieira et al. (MSSP 2026, DOI
`10.1016/j.ymssp.2026.114640`), including their bearing-wise HUST results. Their paper does not expose
the outcomes of the exact matched-specification × load XOR-quarantine protocol below, but it does
remove any claim that this is the first bearing-wise HUST evaluation. HUST is untouched by this
project's feature engineering and model fitting at the instant of sealing.

Paderborn EXP-417 and the retrospective EXP-433--438 family informed the question and fixed model
suite. They are development evidence. No Paderborn-driven change is allowed after HUST signals are
opened.

## Primary cohort and physical units

Use only the 45 official recordings with conditions:

- `N`: healthy;
- `I`: inner-race fault;
- `O`: outer-race fault.

For each condition and each specification index 4--8, the code (for example `N4`, `I4`, or `O4`)
denotes one physical bearing measured at 0, 200, and 400 W. Thus the cohort contains:

- 15 physical bearings (`3 classes × 5 specifications`);
- 45 recordings (`15 bearings × 3 loads`);
- five independent physical bearings per class;
- one recording for each bearing/load cell.

The outer identity factor is named `matched_specification_group`, not `bearing_id`: holding index 4,
for example, withholds three different physical bearings (`N4`, `I4`, `O4`) that also share the
6204 specification. The design therefore cannot separate specimen identity from bearing
specification.

The remaining 54 `B`, `IO`, `IB`, and `OB` recordings remain inaccessible in D3. They are not an
open-set stress test unless a later, separately sealed study is performed after the primary paper
decision.

## Immutable signal and feature contract

Each MAT file must contain exactly one eligible real numeric vector after singleton dimensions are
squeezed. The vector must contain exactly 512,000 finite samples (10 seconds at 51,200 Hz). MAT
metadata keys beginning with `__`, scalars, text, structs, object arrays, and shorter arrays are not
eligible. Multiple eligible vectors or a different length cause a retained structural failure; no
variable may be chosen by its downstream score.

Use the complete vector in acquisition order. Split it into ten contiguous, non-overlapping windows
of 51,200 samples (1 second) with starts `0, 51200, ..., 460800`. Do not discard run-up, filter,
resample, overlap, augment, normalize amplitudes, or select a quieter interval.

For each window compute the exact 24-feature `sensor_feature_matrix` contract already frozen for
SmartValve:

`mean`, `std`, `rms`, `minimum`, `maximum`, `peak_to_peak`, `q05`, `q25`, `q50`, `q75`, `q95`,
`iqr`, `mean_absolute`, `skewness`, `excess_kurtosis`, `diff_mean_absolute`, `diff_rms`,
`linear_slope`, `spectral_centroid`, `spectral_bandwidth`, `spectral_entropy`,
`spectral_power_low`, `spectral_power_mid`, and `spectral_power_high`.

This yields exactly 450 optimization rows. Windows are optimization examples only. Every score,
confidence interval, and table must retain the recording and physical-bearing hierarchy.

## Four immutable access protocols

Every protocol produces one out-of-fold probability vector per recording/method/seed after averaging
the ten window probability vectors of that recording. Class prediction is the argmax of the averaged
probabilities in fixed order `N`, `I`, `O`.

1. `recording_random`: five class-stratified recording folds, shuffled with seed `20260819`. All ten
   windows from a recording remain in one fold. This split may share a bearing through its other
   loads but never shares windows or the same recording.
2. `load_holdout`: three folds, each holding all 15 recordings at one load.
3. `matched_specification_holdout`: five folds, each holding all nine recordings from one
   specification group (three physical bearings × three loads).
4. `crossed_holdout`: 15 specification-group × load folds. For held group `b` and load `l`:

```text
source      = specification_group != b AND load != l
target      = specification_group == b AND load == l
quarantine  = (specification_group == b) XOR (load == l)
```

Each crossed fold has 24 source recordings, 3 target recordings, and 18 quarantined recordings.
No quarantine window is exposed to preprocessing fitting, model fitting, selection, early stopping,
calibration, or thresholding. Every one of the 45 recordings is targeted exactly once per protocol.

Source environments are load values for all methods and protocols. Window-level paired controls use
only source data:

- nuisance pairs: same physical bearing, different load, same aligned window index;
- fault pairs: different class, same specification group, same load, same aligned window index.

The crossed source therefore has 120 nuisance pairs and 240 fault pairs. Pair counts for every fold
and protocol must be emitted and validated before fitting.

## Frozen methods and computation

Use the exact nine D0/D1-selected configurations and five seeds `11, 23, 37, 53, 71`:

`erm`, `coral`, `vrex`, `groupdro`, `dann`, `lisa`, `matchdg`, `ccdg`, and `pirl_ratio`.

No HUST hyperparameter search, early-stopping change, architecture change, class weighting, feature
selection, calibration, or method deletion is allowed. Apply the existing source-only training
semantics to the 24-dimensional windows. Expected new fits:

```text
(5 recording folds + 3 load folds + 5 specification folds + 15 crossed folds)
× 9 methods × 5 seeds = 1,260 fits
```

All seed probabilities are averaged before record aggregation and scoring. CUDA failure may be
reconciled only with an execution-only amendment that proves the hypothesis, cohort, folds,
features, configurations, seeds, and endpoints are unchanged.

## Primary and secondary endpoints

The inferential row is a recording; the resampling unit is physical bearing ID (`N4`, `I4`, etc.).

Primary protocol endpoint for each method:

```text
recording_random pooled record-level macro F1
minus crossed_holdout pooled record-level macro F1
```

Use 5,000 paired class-stratified bootstrap draws: within each of N/I/O, sample five physical
bearings with replacement and carry all three load recordings and all protocol predictions of each
selected bearing together. Report the estimate and percentile 95% interval for all nine methods.
No window-level interval or seed-as-replicate test is allowed.

Primary ranking endpoint: Kendall tau between the nine-method `recording_random` and
`crossed_holdout` ranks based on pooled record-level macro F1. Ties use average ranks. Report all
method ranks, the maximum absolute rank shift, and the score range under each protocol so that
ceiling compression is visible.

Secondary endpoints, all fully reported:

- pooled balanced accuracy, accuracy, and minimum class recall;
- mean, median, minimum, and q25 of the 15 specification × load cell macro F1 values;
- `load_holdout - crossed` and `matched_specification_holdout - crossed` paired effects;
- method-minus-ERM effects under every protocol;
- per-class confusion matrices at recording level;
- window-to-record disagreement and predictive entropy as diagnostics only;
- fit duration, parameter count, peak CUDA memory, model-state hash, and DANN auxiliary-state hash.

With one record per class in each physical cell, cell macro F1 is deliberately coarse and cannot be
treated as an independent replicate.

## Predeclared replication interpretation

The external protocol-gap pattern is considered descriptively replicated if both conditions hold:

1. at least seven of nine methods have a positive `recording_random - crossed` point estimate; and
2. the median of the nine point estimates is at least 0.15 macro F1.

Ranking instability is considered descriptively replicated if either:

- Kendall tau is below 0.50; or
- at least one method changes by three or more rank positions.

These thresholds are advancement rules, not population-level hypothesis tests. The full estimates
and intervals must be published even if neither rule passes. A leader need not match Paderborn; the
claim concerns protocol sensitivity, not winner replication.

## Integrity, stopping, and one-shot rules

- Before download, hash-lock the official 45-file list, each official file SHA-256, this seal, the
  extraction code, split manifest, selected configurations, and expected key/count manifest.
- Download only the 45 primary MAT files. Verify each official SHA-256 before opening.
- Preserve the first unmodified acquisition/extraction/model run, including all failures.
- Do not inspect plots, descriptive signal statistics, features, labels joined to features, or model
  outcomes until structural validators and expected counts pass.
- No rerun may replace a valid completed model result. A failed run remains in the ledger.
- Stop and write an amendment before proceeding if the MAT structure, sample count, finite-value
  contract, file hash, fold topology, pair topology, model count, or prediction count differs.
- After the one-shot run, an independent script must recompute record aggregation, metrics,
  ranks, bootstrap draws, and all hashes from predictions without fitting models.
- HUST results cannot authorize retrospective tuning on Paderborn or a second HUST attempt.
