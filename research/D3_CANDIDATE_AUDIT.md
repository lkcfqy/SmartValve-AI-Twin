# D3 candidate audit: HUST Bearing v3

- Candidate status: metadata-only, **not sealed and not authorized for signal access**
- Official dataset: `10.17632/cbv7jyx4p9.3`
- Official page: <https://data.mendeley.com/datasets/cbv7jyx4p9/3>
- License: CC BY 4.0
- Metadata run: `EXP-431-HUST-D3-METADATA`
- Inventory schema: `smartvalve-hust-d3-metadata-inventory-0.1.0`

## Prior-use disclosure discovered before signal access

The literature audit found Vieira et al. (MSSP 2026, DOI
`10.1016/j.ymssp.2026.114640`) before any HUST MAT signal was downloaded or opened. Their current
v5 article treats `N4`, `I4`, and analogous codes as distinct physical bearing IDs, uses all three
loads per bearing, and reports bearing-wise HUST results. This resolves the narrow metadata question
of whether the files represent physical bearings, but it also removes several possible novelty
claims:

- HUST cannot be presented as a previously unused leakage benchmark;
- bearing-wise HUST evaluation and shallow-versus-deep comparison are prior art;
- the future D3 run will be *protocol-prospective and signal-unopened*, not literature-outcome-blind.

The still-unobserved endpoint is narrower: simultaneous exclusion of a matched bearing-specification
group and one load, with both XOR cross-arms quarantined, followed by the already frozen method-rank
and physical-unit reliability audit. No HUST result from that factorial protocol was found in the
documented search.

## Outcome-blind inventory result

EXP-431 queried only the public Mendeley folder/file metadata endpoints. It did not request a MAT
download URL, open a MAT file, read a signal value, compute a feature, or fit a model.

- official MAT files: 99;
- official MAT bytes: 671,364,479;
- canonical inventory SHA-256:
  `471ae25783099779d5d2ecc95f613a8ca2a6cd7614388a8b43ea538c98f3f423`;
- MAT files downloaded/opened: 0/0;
- signal bytes read: 0;
- inventory artifact SHA-256:
  `98283df45832cf5504403d1d7573cd0f03e11b91161b944f91ff124075209713`;
- candidate split artifact SHA-256:
  `a4b7c9b40670da7260952a47b6c41a119d71533a87624f2ce37bcf321b6266dd`;
- metadata summary SHA-256:
  `5678f37b4b2e5373600d4559dd239bb7ea74eac2ba59230cefa06fcdcdabc449`.

## Candidate primary closed-set cohort

Use the three fault-location-compatible conditions present for every bearing specification:

- `N`: healthy;
- `I`: inner-race fault; and
- `O`: outer-race fault.

Cross five bearing specifications (`6204`--`6208`, encoded 4--8) with three loads (0, 200, and
400 W). Each class/specification code (for example, `N4`, `I4`, or `O4`) denotes a distinct
physical bearing measured at every load. This yields 45 complete recordings from 15 physical
bearings and 15 candidate outer folds.

For held matched specification group `b` and load `l`:

```text
source      = bearing_specification_group != b AND load != l
target      = bearing_specification_group == b AND load == l
quarantine  = (bearing_specification_group == b) XOR (load == l)
```

Each fold has 24 source recordings, 3 target recordings, and 18 quarantined recordings. The three
target recordings come from three distinct physical bearings (one per class) that share a bearing
specification. At the record level, the source topology has 12 same-class/bearing cross-load
nuisance pairs and 24 same-specification/load cross-class fault pairs.

## Candidate open-set stress cohort

Reserve `B`, `IO`, `IB`, and `OB` rather than forcing them into the N/I/O closed set. The official
inventory contains 54 such recordings. Their use, scoring rule, and allowable training exposure
remain unfrozen; they are not available for opportunistic method selection.

## Main limitations to resolve before sealing

- The proposed outer identity fold is a *matched specification group*: it simultaneously withholds
  three physical bearings and their common 6204--6208 specification. It cannot isolate a pure
  specimen-identity effect from a specification/model effect. Paper terminology must say this
  explicitly rather than calling the axis a single held bearing ID.
- There is one full recording per condition/type/load cell. Windows may supply optimization
  examples but cannot be treated as independent test replications.
- The primary target contains only three recordings per outer fold. Inference must aggregate at
  recording/type level and intervals will be wide.
- The v3 repository has 99 records. The original data note describes 30 prototype bearings and
  90 recordings, while Vieira et al.'s v5 paper describes 33 bearings and the v3 inventory includes
  99 recordings. The three additional bearing IDs/version change must be reconciled before the
  feature seal.
- Exact MAT variables, usable steady-state interval, window boundaries, and run-up treatment remain
  unknown because signal files have correctly not been opened.
- Existing HUST outcome values in Vieira et al. are now known. They may be used only to establish
  prior-art boundaries, never to tune SmartValve's HUST cohort, hypotheses, features, thresholds,
  models, or pass/fail rules.

## Authorization boundary

Metadata suitability is necessary but not sufficient. Signal download or opening requires the
complete v0.3 hypothesis, protocol, feature, model-selection, inference, expected-manifest, and
execution seal described in `research/V03_CONTRIBUTION_DECISION.md`.
