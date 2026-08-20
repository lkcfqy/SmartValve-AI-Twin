# Paderborn full-corpus structure-inventory amendment v0.2

- Status: frozen for one 32-archive key/shape/dtype inventory
- Frozen: 2026-08-18
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Structure probe: `779cf7f2a96e6ef6b5b920360598f5c63f3f1d219ad4ce00876fd589bdede44c`
- Feature-contract predecessor: `paderborn_feature_contract_amendment_v0.4.json`
- Predecessor SHA-256: `fe731f62c37a7730f677d171b36b981590d87ae7307e23116d25074d9ad11a6e`

## Trigger and access accounting

The v0.4 feature attempt fully processed K001 in memory, then stopped while parsing
a K002 channel containing fewer than 256,000 samples. It wrote no feature matrix,
prediction, metric, or model outcome. K001 feature values were necessarily computed
transiently before the failure but were not persisted, printed, or inspected. The
exception disclosed neither the failing filename nor actual length.

The failure proves that K001 alone does not characterize acquisition-length
variation. Further threshold guesses are forbidden. A full structural inventory is
required before one final normalization decision.

The failed run is immutable evidence:

- `metadata.json`: 11,746 bytes, SHA-256
  `cd9bd8e903701b043f4ae262e9793eae52ca116f5f73b66a96e48c0d25ae87ea`
- `stderr.log`: 1,788 bytes, SHA-256
  `0520ab97dd097c12816b8b19df33f30c0c46e2024b548e437f0909a3f71886fd`

## Authorized inventory

Exactly one structural pass over all 32 locked archives and all 2,560 predeclared
MAT measurements is authorized. Each archive must match its locked size and
SHA-256, use the frozen unrar binary, contain the exact 80 expected MAT basenames,
and apply the frozen non-MAT quarantine policy. Temporary extraction trees must be
deleted after each archive.

For every MAT file, the only authorized emitted fields are archive, filename,
archive-relative path, file byte count, file SHA-256, MATLAB root key, semantic
channel name/path, stored/squeezed shape, dtype, and element count. Counts of exact
shape/dtype signatures may be emitted. The reader necessarily loads arrays, but it
must compute no signal statistic, feature, prediction, metric, or model outcome.

The pass may emit archive-level progress containing only archive name/index and MAT
count. It may hash and record quarantined regular non-MAT files but must never parse
or use them.

## Frozen implementation

- `scripts/paderborn_archive_structure_inventory.py`: 14,679 bytes, SHA-256
  `9fb297b584bdfaa72fb61ee757330000003328dbdd3ac349c486e5eaa377f341`
- `tests/test_paderborn_archive_structure_inventory.py`: 1,338 bytes, SHA-256
  `1157943fa8ea3accceb20b162a2926d5ce55f2967dea4c1cf89301a3eeda72ca`

Targeted lint and the deterministic signature-summary test passed before v0.2 was
frozen.

## Authorization boundary and use of results

This amendment authorizes no feature computation and no model operation. After a
successful full inventory, exactly one final normalization contract may be based on
the corpus-wide shape/dtype distribution and the original four-second/64-kHz
intent. It must be documented, tested, hash-frozen, preserve all sealed model and
statistical choices, and pass integrity gates before feature extraction resumes.

This is a disclosed full-corpus structure-informed step after aborted transient
feature computations but before any persisted feature value or model outcome was
exposed. It is not pre-data; it remains outcome-blind.
