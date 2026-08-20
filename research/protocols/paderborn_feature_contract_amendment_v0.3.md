# Paderborn feature-contract amendment v0.3

- Status: frozen for outcome-blind bulk feature extraction
- Frozen: 2026-08-18
- Supersedes execution authorization in: `paderborn_feature_contract_amendment_v0.2.json`
- Predecessor SHA-256: `64230ca30dff300ff14286b21f23ab784cb1fa793516f53a3eb4e829b6e58ae9`
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Successful structure probe: `779cf7f2a96e6ef6b5b920360598f5c63f3f1d219ad4ce00876fd589bdede44c`

## Trigger and access accounting

The v0.2 bulk attempt passed archive integrity and exact MAT-inventory validation for
the first archive, quarantined its regular non-MAT files, then stopped while parsing
a measurement whose `phase_current_1` did not contain exactly 256,001 stored
samples. The exception disclosed neither the filename nor the actual length. It
emitted no feature value, feature statistic, prediction, model metric, or model
outcome, and wrote no feature artifact.

Because measurements are processed sequentially in memory, the attempt may have
transiently computed the frozen 72 features for measurements preceding the failure.
Those values were neither persisted nor printed nor inspected. This fact is
disclosed rather than treating the failed run as pre-feature. No model was fitted
and no target result was available.

The failed run is immutable evidence:

- `metadata.json`: 11,665 bytes, SHA-256
  `c36c685ea804d3a320e149859c1d7e6b55fca355ab7f8577a30258dae4d1ee23`
- `stderr.log`: 1,665 bytes, SHA-256
  `f8a9dde4f0ca3996250d776b722811ac245b23995fed4310b1389a52ca92e81a`

## Frozen length-normalization rule

Each selected channel must be one-dimensional, finite, and contain exactly either
256,000 or 256,001 stored samples. In both cases the parser retains exactly the
first 256,000 samples. Thus a 256,000-sample record is unchanged and a
256,001-sample record loses only its final inclusive endpoint. Every other length
is rejected.

The two-element allowed set was frozen after observing only that one unspecified
current channel did not equal 256,001, without learning its actual length. The rule
therefore follows the original four-second, 64-kHz contract and the already observed
single optional endpoint; it is not fitted to a disclosed failing length, filename,
label, bearing, operating condition, signal value, feature, or result.

The v0.2 non-MAT quarantine rule remains unchanged. The representation remains the
same 72 features; all splits, methods, hyperparameters, seeds, endpoints, and
statistical tests remain unchanged.

## Frozen revised artifacts

- Successful structure-probe `metadata.json`: 11,533 bytes, SHA-256
  `e2732717aebd7bd1fb1a5b95d7812fb25636517226243eca345adeae2df43e78`
- `src/smartvalve/data/paderborn_features.py`: 4,174 bytes, SHA-256
  `477970c99170b45256196430b09807d37c043379b82576147a62fb2ce2269bda`
- `src/smartvalve/data/paderborn_mat.py`: 7,122 bytes, SHA-256
  `07ab9b5c4a4ecdbee597bf6b5dc03d8ced93e24df91960e330310af828a72ab8`
- `src/smartvalve/experiments/paderborn_feature_run.py`: 27,027 bytes,
  SHA-256 `f40a0647901eba13631c614ced94961f27b4abe9f9989672a8934553b42ea9c8`
- `tests/test_paderborn_features.py`: 2,433 bytes, SHA-256
  `1853da59462bfef56cef269a724ae0b93d65308a8be2f0c8cd09d2e002765aa6`
- `tests/test_paderborn_mat.py`: 4,824 bytes, SHA-256
  `83286457632a942e629371249a9752af3d442e00364ec69513d65f21d4f69fa8`
- `tests/test_paderborn_feature_run.py`: 9,669 bytes, SHA-256
  `3e59e20022a34eb1ea77c646a700d4f0897edf5f7e69f629561e0b85eb0b2fcd`

Targeted lint and all 19 feature/parser/probe tests passed before v0.3 was frozen.

## Authorization boundary and prospectivity

This amendment authorizes the same 32 locked archives, 2,560 exact MAT members,
non-MAT quarantine records, and frozen 72-feature computation. It does not authorize
model fitting, prediction, metric computation, target-guided reselection, or model
outcome access.

This is a disclosed structure-informed amendment made after an aborted in-memory
feature pass but before any feature value or model outcome was exposed. The feature
pipeline is no longer strictly pre-feature in execution history; the length policy,
model comparison, and evaluation remain outcome-blind. The paper must state that
distinction.
