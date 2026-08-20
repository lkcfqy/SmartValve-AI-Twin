# Paderborn feature-contract amendment v0.5

- Status: frozen final full-corpus feature-extraction contract
- Frozen: 2026-08-18
- Supersedes execution authorization in: `paderborn_feature_contract_amendment_v0.4.json`
- Predecessor SHA-256: `fe731f62c37a7730f677d171b36b981590d87ae7307e23116d25074d9ad11a6e`
- Full structure-inventory amendment SHA-256: `d59b33bebf439409d08d581530fe5d14ac344f7bf7d4c64219a51dcb582c0bfc`
- Full structure inventory SHA-256: `da1252d65af1dd99fa3b7cf410317905c62f72668fc0e5f6305c59f208a83895`
- MAT-recovery amendment SHA-256: `bba4325a4a835e5471c7c9f46da4548b27240d14bfe125591224d1a3259dc025`
- MAT-recovery probe SHA-256: `d9e7eebb77ba3647f6e15e2e43ed6cc677a50e2f3e244916f5ffce74e502b437`

## Why v0.5 is necessary

The outcome-blind full-corpus inventory covered every one of the 2,560 locked MAT
members before any persisted feature table, fitted model, prediction, or evaluation
metric was inspected. Of those files, 2,559 parsed structurally and one failed.
Every parsed measurement contained the three declared semantic channels as finite-
unchecked, one-dimensional `float64` arrays with equal within-file lengths. There
were 394 distinct lengths from 249,940 through 299,038 samples: 55 measurements
were shorter than 256,000, 330 equalled 256,000, and 2,174 were longer.

The single parse failure is exactly:

- archive: `KA08.rar`
- member: `KA08/N15_M01_F10_KA08_2.mat`
- bytes: 8,714,872
- SHA-256: `e137cbb2368caa8bd56889eff8609d2569d2c196a85107e16aa4740437f2ccb3`
- SciPy error: `TypeError: Expecting matrix here`

The separately authorized recovery probe confirmed one top-level MATLAB struct with
`whosmat`, then both documented root-isolation strategies (`loadmat` with
`variable_names` and `varmats_from_mat`) failed with the same reader error. It
emitted no signal value, value-dependent statistic, feature, prediction, or model
outcome. Continuing to change parsers after identifying this one corrupt member
would add an implementation-specific exception with no evidence that it recovers an
equivalent record. The frozen rule therefore excludes this exact filename and hash,
and no other measurement.

## Final uniform normalization rule

The official corpus contract describes each synchronized measurement as four
seconds at 64 kHz, giving a nominal 256,000 samples per channel. For each of the
2,559 readable measurements:

1. require exactly the three semantic channels `vibration`, `current_u`, and
   `current_v`;
2. require each channel to be one-dimensional, finite, `float64`-convertible, and
   to have the same stored length within that measurement;
3. require the common length to lie in the outcome-blind observed locked-corpus
   range 249,940 through 299,038;
4. map the complete common-index interval linearly from `[0, n-1]` to exactly
   256,000 equally spaced samples, preserving both endpoints; and
5. compute the unchanged 72 whole-record features on the normalized arrays.

The operation is deterministic `numpy.interp` over normalized index coordinates.
It is identical for every bearing, setting, measurement, label, fold, method, and
seed. It neither crops selectively nor pads with invented constant samples. The
frozen spectral features use normalized digital frequency, so the rule treats the
observed acquisition-length variation as a record-timing nuisance rather than
claiming unavailable fixed-Hz resolution.

The MAT inventory will still contain all 2,560 locked members. The excluded record
will retain its archive/member path, byte count, and SHA-256 with null stored and
retained sample counts. The feature matrices will contain 2,559 measurements:
2,319 pure-class measurements and all 240 compound-label stress measurements.

## Scope and consequences for the evaluation topology

The exclusion removes one pure outer-race measurement (`KA08`, setting
`N15_M01_F10`, repetition 2). It was determined solely by file readability, not by
its signal values, features, label difficulty, prediction, or model outcome. The
24 double-unseen folds remain the exact six-identity-by-four-setting product. Their
row counts become data-dependent only through this declared missing key, and every
retained pure-class measurement remains target exactly once. The model count stays
1,080. The target-prediction count must be amended from 104,400 to 104,355; the
compound-prediction count stays 259,200.

This amendment authorizes only feature extraction and its structural audit. A
separate execution amendment and regenerated metadata-only topology manifests are
required before fitting any D2 model. No old manifest may be silently reused.

## Frozen implementation artifacts

- structure-probe `metadata.json`: 11,533 bytes, SHA-256
  `e2732717aebd7bd1fb1a5b95d7812fb25636517226243eca345adeae2df43e78`
- full structure-inventory `metadata.json`: 12,124 bytes, SHA-256
  `6716c15a5ed891590f341d79eef5c01d362906f12b6fe808b41b64f229d8849b`
- MAT-recovery-probe `metadata.json`: 11,633 bytes, SHA-256
  `256696afcde0b0a50cdd79757f59520be67ded0027dac6a93401844b551a4132`
- `src/smartvalve/data/paderborn_features.py`: 4,436 bytes, SHA-256
  `ef6b78e6daff233c607e118bb56e5e96c291018f2a0a6844cc83fc6c69091e63`
- `src/smartvalve/data/paderborn_mat.py`: 8,926 bytes, SHA-256
  `1c858ef261a1a38f956742365a50e78a66b8f486905994c411c9117b90c7f728`
- `src/smartvalve/experiments/paderborn_feature_run.py`: 31,589 bytes,
  SHA-256 `e88cc5aa8a78d18a47c1deab04b2634a3d2ce9c45bd02555213bda55bd0643cd`
- `src/smartvalve/experiments/paderborn_partitions.py`: 9,395 bytes,
  SHA-256 `b5e3b663dd6181a505c4c4710862e313087010b557f018e565ff4e8b7e7481bf`
- `src/smartvalve/experiments/paderborn_domain.py`: 5,949 bytes, SHA-256
  `41e070c236a5000f63fc6bafb2a765dd00d53a51a0a5722fba8673ebf3b46aee`
- `tests/test_paderborn_features.py`: 2,684 bytes, SHA-256
  `77af5bfdf7a2ed8ccdca7ff4d44d22ad4c8a37369c71c2f5d6e973f11b7062f3`
- `tests/test_paderborn_mat.py`: 5,963 bytes, SHA-256
  `374b7ce2d3400efffc7d4fadfbf2575479584ba3740d42af5f9637121ff8ae08`
- `tests/test_paderborn_feature_run.py`: 12,743 bytes, SHA-256
  `2411522836c623d33d5d2fccf9053efcece60d03925bdf256950f38ea64414f6`
- `tests/test_paderborn_partitions.py`: 5,900 bytes, SHA-256
  `a917e7c83e48c912936b22c2d9c6e0b61c738119460a55369ad34ec5d27a06ee`
- `tests/test_paderborn_domain.py`: 3,663 bytes, SHA-256
  `acad8ce02104f3014e30f233adcccde8426c86ad7f58496db7d4fc3a5e5bfd15`

Targeted lint and all 25 feature/parser/partition/domain tests passed before this
document was frozen.

## Prospectivity attestation

The normalization and exclusion decisions use only official nominal timing,
locked file identity, names, bytes, hashes, MATLAB structure, shapes, dtypes, and
reader success/failure. Earlier aborted runs transiently computed some features in
memory, but no feature table was written or inspected. No persisted feature value,
prediction, metric, or model outcome informed this rule. This is an outcome-blind,
structure-informed amendment rather than a claim that no signal reader was ever
invoked. The amendment chain and the single exclusion must be disclosed in any
paper or artifact report.
