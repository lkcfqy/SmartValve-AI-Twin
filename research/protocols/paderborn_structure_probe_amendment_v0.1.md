# Paderborn sealed structure-probe amendment v0.1

- Status: frozen for one same-member structure rerun
- Frozen: 2026-08-18
- Original prospective seal: `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- Triggering run: `EXP-375-PADERBORN-PROBE__20260818T131002.236178Z__sealed-single-mat-structure-probe`

## Trigger and observed information

The first protocol-authorized probe opened only `K001.rar`, attempted only the two
frozen exact paths for `N15_M07_F10_K001_1.mat`, and extracted one temporary copy of
that file without listing the archive. The run stopped because the structure
inspector incorrectly enforced the prospective assumption that every selected
channel contains exactly 256,000 samples. The exception established only that
`phase_current_1` did not satisfy that assumed length. It did not disclose the
actual length, any sample value, any value-derived statistic, any feature, or any
model outcome. The temporary file was deleted by the probe's temporary-directory
context.

The failed run is immutable evidence:

- `metadata.json`: 11,104 bytes, SHA-256
  `72022435187abcfda5fbe250770f01a872ff32b88ae1b12e9542699f3d5219b3`
- `stderr.log`: 1,241 bytes, SHA-256
  `8acf7c9fba9da73079515f2944efc53bfb3263dab946c8cae888fa9fcd9fa539`

## Narrow correction

The structure-only inspector now reports semantic path, stored shape, squeezed
shape, dtype, and element count without accepting or rejecting a length. The
value-bearing parser and the 72-feature extractor remain strict at 256,000 samples,
so the correction cannot silently admit an incompatible measurement into model
training. Tests explicitly verify that an unexpected length is reportable by the
inspector but rejected by the value parser.

The rerun also requires this amendment and its SHA-256 on the command line. It
validates the original seal, the failed-run records, this protocol, the two modified
source/test pairs, the fixed RAR reader, the archive lock, and the K001 archive
before extraction.

Frozen revised artifacts before the rerun:

- `src/smartvalve/data/paderborn_mat.py`: 6,917 bytes, SHA-256
  `ea58fc7cf50151730e444c40b90b546dbce2f7578e793f293f97630473eaa325`
- `src/smartvalve/experiments/paderborn_structure_probe.py`: 15,505 bytes,
  SHA-256 `0a7ae25c0d6faa72b66ec234a4671164172772b8428c083476466a67fba4b857`
- `tests/test_paderborn_mat.py`: 4,194 bytes, SHA-256
  `125b730af7cc21712fdd71d00725b89dd284099876cd997ee4863f6fddabf509`
- `tests/test_paderborn_structure_probe.py`: 8,946 bytes, SHA-256
  `8d0e589ddddbd165e69f9cbd133de1059b082065e6d8c351a8ca53940071f2ee`

Targeted lint and all ten parser/probe tests passed before this amendment was
frozen.

## Authorization

Exactly one additional extraction of the same `N15_M07_F10_K001_1.mat` member from
the same `K001.rar` archive is authorized. The only permitted outputs are keys,
semantic paths, shapes, dtypes, byte hashes, byte counts, and access attestations.
No value-dependent check, feature computation, bulk extraction, model fitting,
target-label analysis, or model-outcome access is authorized by this amendment.

Bulk extraction remains forbidden after a successful rerun until the observed
structure is reconciled with a separately recorded feature-contract amendment and
that amendment passes tests and an independent integrity gate. A failed rerun does
not widen the authorization.

## Prospectivity classification

This is a disclosed, structure-only, pre-feature and pre-outcome amendment. It does
not preserve the stronger claim that no Paderborn archive had ever been opened;
that claim ended at the first probe. It does preserve outcome-blindness for feature
design, model selection, and evaluation because no signal statistic, feature,
label-conditioned result, prediction, or metric has been observed.
