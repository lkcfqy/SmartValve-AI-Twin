# Paderborn single-MAT recovery probe amendment v0.1

- Status: frozen for one exact value-blind recovery probe
- Frozen: 2026-08-18
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Full structure inventory: `da1252d65af1dd99fa3b7cf410317905c62f72668fc0e5f6305c59f208a83895`
- Full structure-inventory amendment: `d59b33bebf439409d08d581530fe5d14ac344f7bf7d4c64219a51dcb582c0bfc`

## Trigger and exact target

The complete 2,560-file structural inventory parsed 2,559 files and isolated one
failure: `KA08/N15_M01_F10_KA08_2.mat`, 8,714,872 bytes, SHA-256
`e137cbb2368caa8bd56889eff8609d2569d2c196a85107e16aa4740437f2ccb3`.
SciPy's normal whole-file reader raised `TypeError: Expecting matrix here`. No signal
value, statistic, feature, prediction, metric, or model outcome was emitted.

## Frozen recovery strategies

Exactly two documented SciPy paths are authorized:

1. `loadmat(..., variable_names=[filename_stem], simplify_cells=True)`, which asks
   SciPy to skip unrelated top-level variables.
2. `varmats_from_mat`, which copies top-level variables into independent in-memory
   MAT streams without interpreting their payload, followed by ordinary `loadmat`
   on the single stream whose name equals the filename stem.

The default compressed-data integrity check remains enabled. No option that relaxes
corruption checks is authorized. `whosmat` may emit top-level variable names,
shapes, and MATLAB classes. A successful strategy may emit only the same root key,
semantic names/paths, shapes, dtypes, and element counts used by the structural
inventory. If both strategies succeed, their structures must be exactly equal.

The probe must exact-extract only the two frozen candidate paths for this file from
the locked KA08 archive, validate its byte count and SHA-256, and delete the
temporary copy. It must not list the archive, compute features, repair or rewrite
the MAT, or run a model.

These strategies follow the SciPy public documentation for `loadmat` and
`varmats_from_mat`; they change read scope, not array values.

## Frozen implementation

- Full inventory `metadata.json`: 12,124 bytes, SHA-256
  `6716c15a5ed891590f341d79eef5c01d362906f12b6fe808b41b64f229d8849b`
- Full inventory output: 4,073,292 bytes, SHA-256
  `da1252d65af1dd99fa3b7cf410317905c62f72668fc0e5f6305c59f208a83895`
- `scripts/paderborn_mat_recovery_probe.py`: 13,077 bytes, SHA-256
  `1fbb99115a89deb5fda2c9b5791f74c46718948e963d7635786443b4b49322ee`
- `tests/test_paderborn_mat_recovery_probe.py`: 1,153 bytes, SHA-256
  `d085290eb2f8e312c0a360b9c2282da0b719c13c712ff2c64f1385da0bbcbfa8`

Targeted lint and a synthetic two-top-level-variable equivalence test passed before
this amendment was frozen.

## Authorization boundary

This probe authorizes no production parser change. If neither strategy succeeds,
the file remains structurally unreadable and any exclusion must be separately
frozen. If a strategy succeeds, production use requires a separate parser amendment
and tests proving that the recovered structure/value path is identical to the
ordinary path on readable files. Model fitting and outcome access remain forbidden.

This is a disclosed structure-informed recovery step; it remains outcome-blind.
