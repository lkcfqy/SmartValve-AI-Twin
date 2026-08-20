# Paderborn full-corpus structure-inventory amendment v0.3

- Status: frozen for one fault-tolerant 32-archive structure inventory
- Frozen: 2026-08-18
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Structure probe: `779cf7f2a96e6ef6b5b920360598f5c63f3f1d219ad4ce00876fd589bdede44c`
- Feature-contract predecessor: `paderborn_feature_contract_amendment_v0.4.json`
- Predecessor SHA-256: `fe731f62c37a7730f677d171b36b981590d87ae7307e23116d25074d9ad11a6e`

## Trigger

The v0.2 full structure inventory completed 12 archives (960 MAT files) and stopped
inside KA08 when SciPy raised `TypeError: Expecting matrix here` for one unspecified
MAT file. No signal value, statistic, feature, prediction, metric, or model outcome
was emitted. No partial inventory artifact was written, although archive-level
progress was logged.

The failed run is immutable evidence:

- `metadata.json`: 11,942 bytes, SHA-256
  `bc3d87eaeea67c83f907fe1667cc620bb65b964f6cc92c27bf9d79f58df83d93`
- `stderr.log`: 2,343 bytes, SHA-256
  `1c9431d55288ed4bd5ef14d13c1a1238a0935b44a465adce4dfb8d164eb0f2d1`

## Narrow fault-tolerance amendment

The same complete 32-archive structural pass is authorized. For an individual MAT
that the structure reader cannot parse, the inventory must record its archive,
filename, member path, byte count, SHA-256, fixed status `parse_failed`, exception
type, and exception message, then continue to the next exact predeclared MAT. A
successfully parsed record must carry fixed status `parsed` and the previously
authorized key/shape/dtype fields.

Continuing the inventory does not authorize excluding or repairing a failed file,
nor does it authorize an alternate parser. It only creates the complete evidence
needed to decide a corpus policy after every locked file has been accounted for.
The run must report parsed and failed counts summing to exactly 2,560.

All v0.2 archive-lock, exact-MAT inventory, non-MAT quarantine, temporary deletion,
and no-feature/no-model constraints remain unchanged.

## Frozen implementation

- `scripts/paderborn_archive_structure_inventory.py`: 15,965 bytes, SHA-256
  `bb18cfcc63bbebf14cb394995984eaa469ed59765fe7dc293214c3eef7df4248`
- `tests/test_paderborn_archive_structure_inventory.py`: 1,599 bytes, SHA-256
  `0cb113357fdf80d559424897ebd90ecf2b6d596856e3d8ecc54fa80c62d2e426`

Targeted lint and the signature-summary test, including exclusion of a synthetic
parse-failure record from shape counts, passed before v0.3 was frozen.

## Authorization boundary

This amendment authorizes structural parse-status/error reporting only. It
authorizes no feature computation, repair, exclusion, model fitting, prediction,
metric calculation, or model-outcome access. After completion, any parser or corpus
change must be separately justified using only structural evidence and frozen
before inspecting features or outcomes.

This remains an outcome-blind, full-corpus structure-informed step after aborted
transient feature computations. It is not pre-data and will be disclosed as such.
