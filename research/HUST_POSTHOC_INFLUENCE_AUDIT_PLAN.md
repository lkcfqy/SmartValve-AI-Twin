# HUST post-hoc physical-unit influence audit plan

- Frozen: 2026-08-19T04:10:19Z
- Analysis version: `smartvalve-hust-physical-unit-influence-audit-0.1.0`
- Evidence role: post-hoc sensitivity analysis; not a confirmatory endpoint or hypothesis test
- Model refitting: prohibited
- P values or multiplicity-adjusted claims: prohibited
- Reporting rule: every method, comparison, deletion, null result, and sign reversal is retained

## Timing and disclosure

The primary HUST protocol effects, their equal-volume control, and their broad conclusions were
known before this plan. The investigator also inspected the prediction-table schema and three
example rows while designing the topology checks. No leave-one-bearing-out or
leave-one-specification-group-out effect had been computed when this document and the implementation
hashes below were frozen. This audit therefore cannot strengthen the prospective status of EXP-445
and must always be labelled post hoc.

The audit was added to answer one bounded reviewer question: can the observed recording-level macro
F1 contrasts be made non-positive merely by removing one of the 15 physical bearings or one of the
five class-balanced matched-specification groups? It does not estimate a factory population, create
additional independent bearings, or replace the physical-bearing bootstrap.

## Locked validated inputs

| Input | SHA-256 |
|---|---|
| EXP-445 primary summary | `3f721ff50cc72b845d5ce16a3c7ef987ae5c33cb0d69bfab0804a9be38b5d61a` |
| EXP-445 recording predictions | `ed9527d7d34b436a15b2c4c959e2f0d2732ac8314651ab778d8de46db679c608` |
| EXP-447 independent primary validation | `ba9ceee356fe8cc04ddfe1a28f6e46038fd0c60c4ea374df196400b22fdf6c6a` |
| EXP-449 equal-volume summary | `23b898440a6a09c4efd21ea6e9faec16ca637989a5310e4fa69f8067f5e4833c` |
| EXP-449 combined recording predictions | `1309bf86c871779fc015079f0ff6f967f06501f5139ef223c7518ccc28d76957` |
| EXP-450B independent equal-volume validation | `b7e13cf20ff51d06690e56b0f1d45102ecba23dc0df56ad4a7790e4c5d263abe` |

Both validators must declare `passed_independent_no_refit_recomputation`,
`refit_performed=false`, and the exact corresponding outcome-summary hash. The equal-volume crossed
predictions must be byte-value identical to the primary crossed predictions after sorting by method
and filename.

## Fixed estimands and deletions

For all nine methods in their frozen order, recompute these two full-data contrasts:

1. `recording_random - crossed_holdout` pooled recording-level macro F1;
2. `size_matched_shared_access - crossed_holdout` pooled recording-level macro F1.

For each method and comparison, perform both deletion audits without refitting:

1. remove one physical `bearing_code` and all three of its load recordings from both protocol
   predictions, producing 15 effects on 42 remaining recordings;
2. remove one `specification_group` and its three class-specific physical bearings at all three
   loads from both protocol predictions, producing five class-balanced effects on 36 remaining
   recordings.

Macro F1 uses the fixed class order `healthy`, `inner`, `outer` and zero for an undefined class F1.
Strict sign stability means every deletion effect is greater than zero; zero is not positive. For
each method/comparison, report the full effect, deletion minimum/median/maximum, positive-deletion
count, strict sign-stability flag, and maximum absolute change from the full effect.

The fixed topology is 18 full effects, 270 leave-one-bearing rows, 90 leave-one-group rows, and 18
summary rows. No method, comparison, bearing, group, or result may be suppressed. The final paper
package must carry this complete audit as Supplementary Table S4 and describe it as a sensitivity
analysis regardless of whether any sign-stability flag fails.

## Interpretation limits

- A stable sign shows only that no single observed deletion reverses that observed contrast.
- An unstable sign does not invalidate EXP-445; it identifies dependence on a physical unit.
- Deletion ranges are not confidence intervals and cannot be described as 95% intervals.
- The 15 bearings and five specification groups are not interchangeable population samples.
- No deletion row is an independent replicate, and no p value is computed.
- The primary predeclared bootstrap intervals and advancement rules remain unchanged.

## Frozen implementation

| File | SHA-256 |
|---|---|
| `src/smartvalve/experiments/hust_influence_audit.py` | `cd8780024e3bac467daf2e6783f8920f4d2e6bbdb940f4048756aa0b37f1cd9d` |
| `src/smartvalve/experiments/hust_influence_validation.py` | `c2e37a5f35ebec6edb48aa32a940b2c8d1e023d361b5d663c8b2efcb5283154e` |
| `scripts/hust_influence_audit.py` | `13fd9d77a1a7aaba213fe6d3909cdc488d94ddc42d3a87165b335812c7dbbf1b` |
| `scripts/validate_hust_influence_audit.py` | `1cb7fa4d43b90e3a79d7841f0d35b68749a46f372d797d5332b5cff624d52328` |
| `tests/test_hust_influence_audit.py` | `7e69ffd3dec683711db8d4e77a6d44c947f449b3e2a0cebd8ee00bb2b560ea2b` |

Six synthetic tests passed before real-data execution. They cover the complete deletion topology,
hash-locked output generation, crossed-prediction drift, validation/summary linkage, independent
manual-F1 recomputation, and a hash-consistent numeric tamper. Targeted Ruff passed.

## Stopping and validation

Stop and retain the failed run if an input or implementation hash changes, a validator does not
lock its supplied summary, the 45-recording/15-bearing/five-group hierarchy changes, a protocol or
method key is missing, crossed predictions differ, or an output is non-finite. Do not repair a real
result after inspection by changing a deletion rule.

After the one-shot audit, a separate validator must recompute macro F1 manually from confusion
counts, independently regenerate all 396 reported effect rows, compare every categorical field and
numeric value, and verify the complete input/output hash graph. The validator may not import or call
the producer's computation function.
