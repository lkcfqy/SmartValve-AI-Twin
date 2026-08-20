# Paderborn raw-sensitivity validator amendment 001

- Amendment ID: `PADERBORN-RAW-VALIDATOR-AMENDMENT-001`
- Frozen: 2026-08-19 10:58 UTC, while EXP-456R1 remained running at 237/270 fits
- Outcome access at freeze: no raw/FFT/STFT probability, prediction, score, interval, model-state
  value, or advancement-gate outcome was read
- Scope: validator-only hardening; the producer, source data, windows, folds, architectures,
  optimisation, seeds, endpoints, bootstrap plan, thresholds, and reporting rule are unchanged

## Reason

The sealed validator version 0.1.0 performed a no-refit recomputation, but imported the producer's
window aggregation, seed ensembling, scoring, physical-bearing bootstrap, and gate functions. That
was adequate for detecting artifact drift, but a shared calculation defect could make producer and
validator agree. The original seal explicitly permits a documented validator-only correction that
does not alter a fit, probability, endpoint, threshold, or gate.

## Superseding validation contract

Validator 0.2.0 uses a separately implemented calculation module that imports none of the producer
raw-sensitivity or protocol-scoring modules. It independently:

1. averages exactly four probability vectors per recording and seed;
2. averages exactly seeds 41, 42, and 43 per protocol, architecture, and recording;
3. recomputes pooled metrics and all 24 common physical-cell metrics;
4. rebuilds 2,000 paired class-stratified physical-bearing bootstrap draws from seed 20,260,818;
5. reapplies the three-positive-effects, three-positive-lower-limits, and median-at-least-0.15 rule;
6. requires the exact ten-file producer output inventory and all frozen design constants; and
7. binds the result to the frozen feature and raw-window summary hashes supplied literally by the
   already armed watcher.

EXP-477 remains a separate outcome-blind exact-key validator. It checks all 166,968 window keys,
41,742 seed-recording keys, 13,914 ensemble-recording keys, 270 fits, 270 training traces, physical
metadata, probability health, and the precomputed expected topology without reading the gate.

## Locked implementation

| Role | Path | SHA-256 |
|---|---|---|
| independent calculations | `src/smartvalve/experiments/paderborn_raw_validation.py` | `d053dc678cd382c603e071e2b1f2a9c0b50ce3beaae8d7e20b63b1bbb5db2a17` |
| validator CLI | `scripts/validate_paderborn_raw_architecture_sensitivity.py` | `9ae4cd837d9f2383b5bc36f29c4038c096907e9606f6e866018744962cfa7acf` |
| focused tests | `tests/test_paderborn_raw_validation.py` | `39ccea346159ff89c4626bc12e7cce978391073b63389ec3923162f624ff5192` |
| armed validator/topology watcher | `artifacts/research/launch/run_EXP457_after_EXP456R1.sh` | `face67956d43593334792df162bb0c76b26aacfa1a4279280bf112c32cb4285c` |

Focused Ruff passed. Twelve raw-sensitivity, independent-validator, and exact-topology tests passed
with zero failures, errors, or skips before this amendment was frozen. A recorded focused preflight
and the final full-suite EXP-461Q/461V quality gates remain required; neither may be replaced by this
document.

## Interpretation boundary

This amendment strengthens error detection only. It cannot improve an observed effect, rescue a
failed gate, authorize tuning, or convert the retrospective sensitivity into confirmatory evidence.
Every validated positive, null, or adverse result must still be reported.
