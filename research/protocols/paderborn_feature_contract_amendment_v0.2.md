# Paderborn feature-contract amendment v0.2

- Status: frozen for outcome-blind bulk feature extraction
- Frozen: 2026-08-18
- Supersedes execution authorization in: `paderborn_feature_contract_amendment_v0.1.json`
- Predecessor SHA-256: `c2676ca76e8fd95e707f23df0e5f0a3ab1970de8ee0360d0e85f7dc8926301c0`
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Successful structure probe: `779cf7f2a96e6ef6b5b920360598f5c63f3f1d219ad4ce00876fd589bdede44c`

## Trigger

The first v0.1 bulk feature attempt stopped on the first archive before parsing a
MAT file because the extracted tree contained at least one regular non-MAT file.
The exception disclosed no filename, path, size, content, sample value, feature, or
model outcome. No feature artifact was written. The temporary extraction tree was
deleted automatically.

The failed run is retained as immutable evidence:

- `metadata.json`: 11,669 bytes, SHA-256
  `7ef14e13c49b75b130e50c9f057861f66644a05755ddf4eb3b16f49f8f224a20`
- `stderr.log`: 1,023 bytes, SHA-256
  `4420cda0582afce9ed7bb0dd40dce9614ee5f6471f3783202d95ba147aee8fb0`

## Frozen non-MAT quarantine rule

The exact predeclared set of 80 canonical MAT filenames remains mandatory in every
bearing archive. A missing MAT, extra MAT, duplicate MAT basename, cross-bearing
MAT, invalid measurement name, path escape, link, or special file still aborts the
run.

Additional regular non-MAT files are now quarantined: the runner records only their
archive-relative path, byte count, SHA-256, and the fixed handling label
`quarantined_not_parsed_not_used`. It does not parse them or use their content,
filename, count, size, or hash in feature extraction, split construction, model
selection, fitting, prediction, or statistical analysis. This rule was frozen after
learning only that an unspecified regular non-MAT file exists, so it cannot be
tailored to a particular filename or payload.

The completed run must write a separate `quarantined_non_mat.json` artifact and
attest that quarantined files were not used. The exact MAT member inventory and all
v0.1 endpoint/feature rules remain unchanged: three 256,001-element `float64`
channels, retain the first 256,000 samples, discard the final endpoint, and compute
the same 72 features.

## Frozen revised artifacts

- Successful structure-probe `metadata.json`: 11,533 bytes, SHA-256
  `e2732717aebd7bd1fb1a5b95d7812fb25636517226243eca345adeae2df43e78`
- `src/smartvalve/data/paderborn_features.py`: 4,055 bytes, SHA-256
  `0610d1e79ef7228eba6194e4e629897bc45158b5625ef3fe99536391c71dbba1`
- `src/smartvalve/data/paderborn_mat.py`: 7,095 bytes, SHA-256
  `4592a6d0f88890526d96a463327268e857c9f650ca516cc34c20457f9585aa4c`
- `src/smartvalve/experiments/paderborn_feature_run.py`: 26,811 bytes,
  SHA-256 `bdd24d936b8a167092a353a1cf7d21335aae3a6fece1aef9425e0ed9647df536`
- `tests/test_paderborn_features.py`: 2,433 bytes, SHA-256
  `1853da59462bfef56cef269a724ae0b93d65308a8be2f0c8cd09d2e002765aa6`
- `tests/test_paderborn_mat.py`: 4,298 bytes, SHA-256
  `0b48675b723e7b1c1a7c10a2d1e3d4233cbe5d815230f28c69206f59572f3bc8`
- `tests/test_paderborn_feature_run.py`: 9,421 bytes, SHA-256
  `972d8b88c5d176cabd57e23487c12a29515b6e840a74f860a3303e4ba9363fb5`

Targeted lint and all 18 feature/parser/probe tests passed before v0.2 was frozen.

## Authorization boundary and prospectivity

This amendment authorizes the same 32 locked archives, 2,560 expected MAT files,
and 72-feature computation as v0.1, plus hash-only quarantine records for regular
non-MAT files. It does not authorize model fitting, prediction, metric computation,
target-guided reselection, or model-outcome access.

This is a disclosed archive-topology-informed, pre-feature and pre-outcome
amendment. It does not restore the stronger pre-data claim, but it preserves
outcome-blindness: no signal statistic, feature, prediction, model metric, or
label-conditioned result informed the quarantine policy.
