# Paderborn raw prediction-topology audit plan

- Plan version: `smartvalve-paderborn-raw-topology-audit-plan-0.1.0`
- Frozen: `2026-08-19T08:44:43Z`
- Freeze state: EXP-456R1 was still running at 160/270 structured fit completions; both raw
  processes were alive and monitored error logs were empty
- Outcome access: no raw/FFT/STFT macro F1, interval, ranking, aggregate table, gate value, or
  checkpoint probability was inspected before this plan
- Role: additional validator-only topology audit; it cannot alter or replace EXP-456R1/457

## Reason for the additional audit

The sealed EXP-457 validator locks all declared outputs and recomputes aggregation, ensembling,
metrics, physical-bearing bootstrap, and the frozen gate without fitting. Its total-row checks do
not, by themselves, prove that every prediction key and physical metadata row is exactly the one
authorized by the 2,319-record feature provenance, EXP-455 four-window index, and each frozen
target fold. This plan closes only that evidentiary gap.

## Immutable inputs

| Input | SHA-256 |
|---|---|
| Raw sensitivity seal | `d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b` |
| EXP-455 raw-window summary | `af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191` |
| Paderborn primary feature/provenance matrix | `c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4` |

Only the five physical-provenance columns are read from the feature matrix. The expected cohort is
also rebuilt from the metadata-only Paderborn inventory and must match those columns row for row.
No feature value is used to define an expected key.

## Frozen implementation

| Role | Path | SHA-256 |
|---|---|---|
| Expected-key and validation core | `src/smartvalve/experiments/paderborn_raw_topology.py` | `b5a48f916e03ba3cc618f0b1f4a49d9c307c511b3d5bcb2b819ec5ec5d7bf3e8` |
| Outcome-blind manifest wrapper | `scripts/paderborn_raw_topology_manifest.py` | `844c29262f241edc2522c35708028db5e74523194096a0b689422d70d1d22f95` |
| Post-fit validator wrapper | `scripts/validate_paderborn_raw_topology.py` | `94660a56e27e348b6aed22312b6cef705a0b4fe18cb0309e74e426e7f94aad7c` |
| Focused tests | `tests/test_paderborn_raw_topology.py` | `a83114dba25e1278f43aa8ef93d05207627108735c537852861ce5ab654f81cc` |

Four focused tests passed before freeze. They cover the complete expected counts, deterministic key
hashes, window-metadata and offset tampering, duplicate observed keys, probability validity, and
the fixed non-increasing learning-rate schedule.

## Pre-outcome expected topology

EXP-476 must generate one manifest before EXP-456R1 completes. It contains no probability,
prediction, model state, score, interval, rank, or gate outcome. It freezes canonical sorted hashes
for exactly:

- 166,968 window-prediction keys;
- 41,742 seed-level recording-prediction keys;
- 13,914 ensemble recording-prediction keys;
- 270 fit keys with source/target/quarantine record and window counts; and
- 270 training-trace identities.

Each prediction key includes its protocol, method, seed where applicable, fold, authoritative row
and window coordinates, filename, bearing, setting, measurement, truth, identity-fold, and 24-cell
identifier. All four windows of a record remain inseparable.

## Post-fit validation rule

After EXP-456R1 writes and hashes its final summary, EXP-477 must:

1. verify the result summary, expected manifest, seal, feature matrix, raw-window summary, and every
   summary-declared result output by SHA-256;
2. compare all five observed key sets byte-semantically with the pre-outcome canonical hashes;
3. reject missing, extra, duplicated, reassigned, or metadata-drifted prediction rows;
4. verify 270 unique lowercase model-state hashes and finite nonnegative fit diagnostics;
5. verify exactly 50 source-loss epochs per trace and a positive, non-increasing learning rate;
6. verify finite bounded probabilities and the normalization error for window, seed-recording, and
   ensemble predictions; and
7. write only topology hashes/counts and numerical-health maxima, with `refit_performed=false`,
   `aggregate_metrics_recomputed=false`, and `gate_outcome_read=false`.

EXP-477 passes only when every expected-key record equals its observed record exactly. If it fails,
the failure is retained and no downstream manuscript or release may be called validated, even if
the original EXP-457 metric recomputation passes. A correction may change only validator code or
expected-key plumbing under an explicit amendment; it may not change any fit, probability,
endpoint, threshold, bootstrap, or advancement rule.

## Non-claims

- This audit is not another experiment and cannot improve a scientific result.
- It does not independently reimplement the neural architectures or optimizer.
- It complements rather than replaces EXP-457's no-refit metric/bootstrap recomputation.
- Passing it does not turn the retrospective raw sensitivity into confirmatory evidence.
