# Paderborn feature-contract amendment v0.1

- Status: frozen for outcome-blind bulk feature extraction
- Frozen: 2026-08-18
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Successful structure probe: `779cf7f2a96e6ef6b5b920360598f5c63f3f1d219ad4ce00876fd589bdede44c`

## Authorized structural observation

The amendment-gated probe of the predeclared
`K001/N15_M07_F10_K001_1.mat` member reported the three frozen semantic
channels (`vibration_1`, `phase_current_1`, and `phase_current_2`) as one-dimensional
`float64` arrays of 256,001 elements each. It emitted no signal values or
value-derived statistics and computed no features or model outcomes. The successful
probe output is 3,884 bytes with SHA-256
`779cf7f2a96e6ef6b5b920360598f5c63f3f1d219ad4ce00876fd589bdede44c`.

## Frozen endpoint policy

Each stored channel must contain exactly 256,001 finite samples. The parser retains
the first 256,000 samples and discards the final sample, yielding the half-open
four-second interval `[0, 4s)` at 64 kHz. This deterministic endpoint rule is
identical for every channel, measurement, bearing, operating condition, class, and
fold. It was chosen from shape and sampling-duration information only, before any
feature, prediction, or model metric was observed.

The frozen representation remains the same 72 whole-measurement features: the 24
predeclared sensor statistics independently applied to vibration, current-U, and
current-V. No feature name, hyperparameter, model configuration, split, endpoint,
seed, comparison method, or statistical test is changed by this amendment.

## Integrity and failure behavior

The value parser rejects any channel that is not one-dimensional with exactly
256,001 stored samples, rejects non-finite values, and passes exactly 256,000 values
to the unchanged feature extractor. The feature extractor independently requires
exactly 256,000 finite values per channel. The bulk runner independently validates
the successful probe's three channel names, shapes, counts, and dtypes before it
opens another archive.

For every archive, the runner verifies the archive-lock size and SHA-256, extracts
into a temporary directory, rejects links, special files, non-MAT files, duplicate
filenames, missing files, extra files, cross-bearing files, and escaped paths, then
deletes the temporary tree after producing the feature and member-inventory rows.
Any deviation aborts the run without authorizing model fitting.

## Frozen revised artifacts

- Successful probe `metadata.json`: 11,533 bytes, SHA-256
  `e2732717aebd7bd1fb1a5b95d7812fb25636517226243eca345adeae2df43e78`
- `src/smartvalve/data/paderborn_features.py`: 4,055 bytes, SHA-256
  `0610d1e79ef7228eba6194e4e629897bc45158b5625ef3fe99536391c71dbba1`
- `src/smartvalve/data/paderborn_mat.py`: 7,095 bytes, SHA-256
  `4592a6d0f88890526d96a463327268e857c9f650ca516cc34c20457f9585aa4c`
- `src/smartvalve/experiments/paderborn_feature_run.py`: 24,036 bytes,
  SHA-256 `3b898455b1081a650880be24db7e2219b72d326a0bbe8958c0e6be824c7caf3c`
- `tests/test_paderborn_features.py`: 2,433 bytes, SHA-256
  `1853da59462bfef56cef269a724ae0b93d65308a8be2f0c8cd09d2e002765aa6`
- `tests/test_paderborn_mat.py`: 4,298 bytes, SHA-256
  `0b48675b723e7b1c1a7c10a2d1e3d4233cbe5d815230f28c69206f59572f3bc8`
- `tests/test_paderborn_feature_run.py`: 7,897 bytes, SHA-256
  `48cb2ad56b3d49ffd139a3df83cc4dc82e1000a7607f9a53b6f5e25c4bebe04a`

Targeted lint and all 18 feature/parser/probe tests passed before this amendment
was frozen.

## Authorization boundary

This amendment authorizes integrity-checked extraction of exactly the 32 locked
archives and computation of the frozen features for exactly 2,560 expected MAT
measurements. It authorizes the predeclared descriptive bearing and operating
metadata needed to construct the already frozen folds. It does not authorize model
fitting, prediction, metric computation, target-guided reselection, changing the
endpoint policy after seeing extracted values, or inspecting any Paderborn model
outcome.

A completed feature run must emit hashes and row counts for the full matrix, the
pure-class matrix, the MAT inventory, and extraction traces, and must attest that no
model was fitted. Only a separately validated completed feature artifact may be
passed to the already sealed one-shot evaluator.

## Prospectivity classification

This is a disclosed structure-informed, pre-feature and pre-outcome amendment. The
endpoint decision is not strictly pre-data because one authorized array shape was
observed, but it remains outcome-blind and label-independent. Claims and the paper
must describe this distinction explicitly.
