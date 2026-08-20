# Paderborn compound row-index reconciliation — v0.1

- Written: 2026-08-18, after EXP-417 completed and EXP-418 failed.
- Status: narrow post-outcome structural-validation amendment.
- Scope: artifact-key validation only; no model, prediction, score, threshold, label, metric,
  statistical endpoint, or manuscript claim may change under this amendment.

## Trigger and disclosure

EXP-417 completed all 1,080 frozen fits and wrote the sealed base artifacts. The first independent
validator, EXP-418, stopped with
`Paderborn artifact key set differs: compound_predictions`. The failed run is retained. Before this
amendment was written, no D2 performance field was printed, summarized, compared, or interpreted by
the operator. Model outcomes existed on disk, so this is explicitly a post-outcome amendment rather
than a prospective one.

The failure is confined to the metadata-only `row_index` coordinate for the unlabeled compound
stress set. The other compound identity fields are filename, bearing code, setting code, and
measurement index; the compound artifact intentionally contains no truth, correctness, component,
damage extent, or damage origin.

## Root cause

The frozen expected-manifest generator enumerates all 2,560 locked MAT filenames and then removes
the one structurally unreadable file, preserving its original enumeration as `full_row_index`.
The feature extractor removes that same file and resets the retained 2,559-row feature table to a
compact zero-based index. The evaluator correctly uses the compact feature-table index so that a
prediction row addresses the exact matrix row used for inference.

The excluded file is `N15_M01_F10_KA08_2.mat` at original index 1001. Every compound measurement
occurs later: the first compound filename has original index 1440 and compact index 1439. Therefore
all 240 compound measurements have:

`manifest_original_row_index = evaluator_compact_row_index + 1`.

Before defining this amendment, a metadata-only forensic comparison established all of the
following:

1. EXP-417 contains exactly 259,200 compound rows and 240 unique compound filenames.
2. Actual compound row indices are exactly 1439 through 1678 and equal the row positions in the
   independently validated EXP-406 feature matrix.
3. The actual compound key-set SHA-256 is
   `e20f4566200fb9fa8e4bfa982701fcd956295444f04f48ea0293771b12c508b4`.
4. Mapping only `row_index` through the frozen original-to-compact filename map yields key-set
   SHA-256 `247fd2e09827f781533d36137697b4567b397c485b72e2db770801c6f324a7be`,
   exactly the EXP-410 sealed-manifest value.
5. No filename, bearing code, setting code, measurement index, method, seed, fold, count, or artifact
   byte is changed by the mapping.

## Authorized validation rule

The reconciliation validator may replace `row_index` only while computing the expected-key hash
for compound artifacts. It must derive the mapping from:

- the exact EXP-406 feature matrix and its SHA-256;
- `expected_measurement_filenames()`;
- the frozen singleton structural-exclusion tuple; and
- the exact sealed expected manifest.

It must prove that the retained feature filenames equal the original expected filename sequence
with exactly the frozen exclusion removed, that the actual compact indices equal feature-table row
positions, and that the mapped key record equals the sealed manifest exactly. A hard-coded blanket
offset without these predicates is forbidden.

All non-compound key sets must match the sealed manifest without transformation. The original
validator's artifact hashes, counts, probability normalization, confidence, argmax, correctness,
representation normalization, no-forced-compound-outcome, and access-attestation checks remain
mandatory. The validated artifacts remain byte-identical to EXP-417.

The same deterministic mapping may later be applied to the three compound key families in the
already sealed selective manifest (`compound_predictions`,
`compound_ensemble_predictions`, and `compound_decisions`) if and only if the unmodified selective
validator first fails on this same coordinate defect and every other validation condition passes.

## Prohibited actions

- no EXP-417 retraining or prediction regeneration;
- no editing of EXP-406, EXP-410, EXP-411, EXP-416, EXP-417, or EXP-418 artifacts;
- no target-guided method, hyperparameter, feature, fold, beta, score, threshold, or endpoint
  change;
- no reinterpretation of a failed statistical gate; and
- no concealment of EXP-418 or this post-outcome amendment.

