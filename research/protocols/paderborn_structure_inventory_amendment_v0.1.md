# Paderborn first-archive structure-inventory amendment v0.1

- Status: frozen for one K001 key/shape/dtype inventory
- Frozen: 2026-08-18
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Structure probe: `779cf7f2a96e6ef6b5b920360598f5c63f3f1d219ad4ce00876fd589bdede44c`
- Feature-contract predecessor: `paderborn_feature_contract_amendment_v0.3.json`
- Predecessor SHA-256: `1f1ffaf605c8281daef509c5788928c36e1a759ab7fd72ec4743b0007fc7bd99`

## Trigger

The v0.3 feature attempt stopped in K001 because an unspecified
`phase_current_1` length was neither 256,000 nor 256,001. The exception did not
disclose the filename or actual length. No feature artifact, prediction, metric, or
model outcome was emitted. As in the preceding aborted attempt, frozen features may
have been computed transiently for earlier files in memory but were not persisted,
printed, or inspected.

The failed run is immutable evidence:

- `metadata.json`: 11,707 bytes, SHA-256
  `cb3923765cf8948600db59fced19911bc3e4b6cf7dbcf95d5713ba989243345c`
- `stderr.log`: 1,674 bytes, SHA-256
  `1ae8db8b24d1f17cd9e3f79ca14b361a5f78069ce65811669053e4e585b0677b`

## Authorized inventory

One additional extraction of the already accessed `K001.rar` archive is authorized.
The runner must validate its locked size and SHA-256, use the frozen unrar binary,
require the exact 80 predeclared K001 MAT filenames, retain the v0.2 non-MAT
quarantine rule, and delete the temporary tree at completion.

For each of the 80 MAT files, the only authorized emitted fields are filename,
archive-relative path, file byte count, file SHA-256, MATLAB root key, semantic
channel name/path, stored shape, squeezed shape, dtype, and element count. Counts of
identical shape/dtype signatures may be emitted. The MATLAB reader necessarily
loads arrays, but no sample value, value-dependent statistic, feature, prediction,
metric, or model outcome may be computed or emitted.

This inventory is deliberately restricted to K001. Its purpose is to determine the
within-archive acquisition-length contract once, rather than repeatedly changing a
parser after failed feature passes. Results from the other 31 archives remain
unopened by this amendment.

## Frozen implementation

- `scripts/paderborn_archive_structure_inventory.py`: 13,267 bytes, SHA-256
  `f5d0a8f41a447679609fe7594401c1576a57b6aa0f12914e2555fdb2edcb24ed`
- `tests/test_paderborn_archive_structure_inventory.py`: 1,338 bytes, SHA-256
  `1157943fa8ea3accceb20b162a2926d5ce55f2967dea4c1cf89301a3eeda72ca`

Targeted lint and the deterministic signature-summary test passed before this
amendment was frozen.

## Authorization boundary and use of the result

This amendment authorizes no feature extraction and no model operation. After a
successful inventory, one final feature-contract revision may be based only on the
observed key/shape/dtype distribution and the original four-second sampling
contract. It must be documented, tested, hash-frozen, and retain all previously
sealed model choices and statistical endpoints before bulk feature extraction can
resume.

This is a disclosed structure-informed step after aborted in-memory feature
computations but before any feature values or model outcomes were exposed. It is
not strictly pre-data; it remains outcome-blind.
