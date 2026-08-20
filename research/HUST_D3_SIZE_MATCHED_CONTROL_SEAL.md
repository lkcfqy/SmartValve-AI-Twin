# HUST D3 equal-source-volume access-control seal

- Seal date: 2026-08-19 (Asia/Shanghai)
- Protocol version: `smartvalve-hust-d3-size-matched-control-0.1.0`
- Status: frozen while the primary EXP-445 model run was still in progress and before any HUST
  probability, predicted class, score, confusion matrix, protocol effect, method rank, bootstrap
  result, or replication-gate result was read by the investigator
- Evidence tier: outcome-blind auxiliary control; HUST signals and engineered features had already
  been accessed for the primary sealed experiment, so this is not a signal-unopened test
- Purpose: separate the crossed protocol's access restriction from its smaller source-record count

## Motivation and non-replacement rule

The primary crossed protocol uses 24 source recordings, while easier protocols use more source
records. A reviewer could therefore attribute a random/crossed gap to training volume rather than
access to the target identity or setting. This auxiliary control does not replace, revise, or
reinterpret the sealed primary HUST endpoints. It adds a same-target, equal-source-volume
comparison after the valid primary run and its independent validator complete.

No result from this control may replace EXP-445, authorize a HUST hyperparameter change, or be
reported without the complete primary four-protocol result.

## Immutable target and source construction

For every one of the 15 `specification_group × load_w` target cells, retain the exact three target
recordings and 30 target windows used by `crossed_holdout`.

Let held specification group be `g`, held load be `l`, and `next(g)` be the cyclic successor in
the ordered group list `[4, 5, 6, 7, 8]`, with `next(8) = 4`.

The strict crossed source is:

```text
specification_group != g AND load_w != l
```

The equal-volume shared-access source is:

```text
(specification_group == g XOR load_w == l)
OR
(specification_group == next(g) AND load_w != l)
```

Thus every control fold contains:

- 24 source recordings / 240 source windows;
- 3 target recordings / 30 target windows; and
- 18 inaccessible recordings / 180 inaccessible windows.

The source includes the target physical bearings at their other two loads and the target load on
the other four specification groups, but never includes an exact target recording. The six cyclic-
anchor recordings complete the source to the strict crossed volume.

The following properties are immutable and validated for every fold:

- eight source recordings per class (80 windows per class);
- all five specification groups and all three loads represented in the source;
- the same target rows as the corresponding strict crossed fold;
- 120 aligned-window nuisance pairs and 240 aligned-window fault pairs, exactly matching the
  primary crossed pair budget; and
- every one of the 450 windows targeted exactly once across the 15 folds.

This design matches source quantity, class balance, environment support, and paired-control counts.
It does not make the two source sets identical in all other respects and therefore is a strong
falsification control, not a causal identification experiment.

## Frozen models and computation

Use the exact nine configurations and five seeds from the primary HUST execution:

`erm`, `coral`, `vrex`, `groupdro`, `dann`, `lisa`, `matchdg`, `ccdg`, `pirl_ratio`;
seeds `11, 23, 37, 53, 71`.

No search, feature change, normalization change, stopping change, class weighting, calibration, or
target-guided selection is allowed. Expected new fits:

```text
15 target cells × 9 methods × 5 seeds = 675 fits
```

The control may start only after:

1. EXP-445 exits successfully;
2. all primary output hashes and expected counts pass; and
3. the independent primary no-refit validator exits successfully.

The control runner must consume the validated primary `crossed_holdout` recording predictions
directly; it must not refit or reconstruct the primary models.

## Endpoints and interpretation

The primary auxiliary effect for every method is:

```text
size_matched_shared_access pooled recording macro F1
minus crossed_holdout pooled recording macro F1
```

Use the same 5,000 class-stratified physical-bearing bootstrap draws as the primary HUST analysis.
Report all nine estimates and intervals.

The access effect is descriptively supported if both conditions hold:

1. at least seven of nine point estimates are positive; and
2. the median of the nine point estimates is at least 0.10 macro F1.

Rank instability is descriptively supported if the shared/crossed pooled-macro-F1 Kendall tau is
below 0.50 or at least one method moves by three or more ranks. These are advancement rules, not
population-level hypothesis tests. All metrics, ranks, intervals, failures, and null results must be
reported regardless of the rules.

## Expected output topology

| Artifact family | Expected rows/items |
|---|---:|
| fits | 675 |
| DANN auxiliary states | 75 |
| seed-window predictions | 20,250 |
| seed-ensemble window predictions | 4,050 |
| size-matched recording predictions | 405 |
| combined shared/crossed recording predictions | 810 |
| aggregate method/protocol metrics | 18 |
| physical-cell metrics | 270 |
| rank concordances | 2 |
| bootstrap summaries | 9 |
| bootstrap effect draws | 45,000 |
| bootstrap draw-plan rows | 5,000 |
| rank-shift rows | 18 |
| confusion-count rows | 162 |
| recording-diagnostic rows | 18 |

## Frozen new code

This control inherits every source and runtime dependency frozen by the HUST expected manifest,
execution seal, execution amendment 001, and runtime dependency addendum 002. The following new
files are additionally frozen:

| File | SHA-256 |
|---|---|
| `src/smartvalve/experiments/hust_size_matched_control.py` | `91ca1fcf2a1bdeb812e7f1e0feb74e3e376d0856171a8804a79c2980fb8b01fd` |
| `scripts/hust_d3_size_matched_control.py` | `c7d6f114b6264076b191e77ef2ae8a591ae372f7b072893bb1bf433e224cbf0d` |
| `tests/test_hust_size_matched_control.py` | `3e92e8084e2cada1d9ff71244cfc66c7fb9b5befa751371eaad79515ed1ce848` |

Pre-seal checks passed for the new files: Ruff check, Ruff format, and three focused topology,
model-fold, aggregation, rank, and physical-bootstrap tests. The complete HUST-focused test set
passed 12 tests with no failure.

## Integrity and stopping rules

- Reverify the three new hashes and every inherited runtime lock immediately before execution.
- Do not edit the frozen files after this seal. Any mismatch is a retained failed preflight.
- Preserve the first unmodified control run, including checkpoints and failures.
- Do not inspect primary HUST outcome content before the control starts. Process exit status, file
  existence, expected counts, and hashes may be machine-validated without displaying scores.
- Stop if target identity, target count, source count, class balance, load/group support, pair
  counts, configuration identity, seed set, prediction count, or primary hashes differ.
- Independently recompute aggregation, metrics, ranks, bootstrap draws, and hashes without fitting
  after the control completes.
- Never describe the result as isolating leakage causally; it tests whether the observed access
  effect survives a predeclared equal-volume source construction.
