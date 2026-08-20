# Selective physical-block bootstrap — frozen v0.1

- Drafted: 2026-08-18
- Frozen: 2026-08-18
- Status: execution authorized only for the exact hash-locked EXP-342 artifacts below
- Development datasets: D0 Cranfield and D1 UCI Hydraulic
- D2 state: archive contents remain unopened

The formal bootstrap must run before D2 activation, but its D0/D1 results cannot alter the already
locked method configurations or score/threshold rules. Execution is authorized only for:

- EXP-342 metrics SHA-256
  `4caa1e4bb2a07b98be6af2752a0b310f751b8bd0f7fda34b03578ebfbd9983e6`;
- target predictions SHA-256
  `43b8522d57ba3a814158be06b7d3b478b6ee3174639e78ed3fc364a772cbeebf`;
- selection decisions SHA-256
  `e49b97f1f63c3d754d1f970a17ba0f9b797cc2841d65e4ef3117b0d54aa99649`;
- outcome-blind expected-manifest SHA-256
  `75af0e966a342b5dbdf245ba78fd34d67da393f6793a6ab75d9d6b61018a45de`; and
- independent EXP-342 validation SHA-256
  `e7ee4d41688d5195478b1c609eaf684156f45c3a3aa7b9c944a13b97bdd013d5`.

The validation status is `passed_against_outcome_blind_selective_manifest`, all 130 final-model
state hashes reproduced exactly, the maximum reference probability difference was zero, and the
maximum probability-sum error was `1.3783574104309082e-07`. Paderborn archive contents were not
opened. Any byte change to an authorized input or this protocol invalidates execution.

## Physical resampling unit and pairing

The unit is one complete physical repetition block containing every fault class measured under one
operating environment. For Cranfield this is `motion | load | repetition`; for UCI it is
`cooler | pump | accumulator | repetition`. Within each operating-environment stratum, draw the
observed number of blocks with replacement. A selected block carries all of its class rows, outer
fold appearances, methods and five model seeds. The identical draw is therefore applied to PIRL
and tuned ERM, and model seeds are averaged inside each physical draw rather than counted as
independent experiments.

Use 2,000 replicates and root seed `20260818`. Spawn deterministic dataset-specific streams and
retain every selected block ID and draw slot. No measurement row is resampled independently.

## Frozen development endpoints

Only the individual-network risk envelope at 50% nominal source-selected coverage is
confirmatory. The paired effects use signs for which positive favors PIRL:

1. `PIRL - ERM` in five-seed-mean worst outer-fold macro F1; and
2. `ERM - PIRL` in five-seed-mean selective risk pooled over the frozen target folds.

Worst outer-fold means the minimum over three held loads for D0 and ten held context levels for
D1. Selective risk is computed for each model seed and then averaged across the five paired seeds.
If a bootstrap draw gives a method/seed no accepted target row, its selective risk is conservatively
set to one rather than dropped. Minimum practical effects are 0.01 absolute macro F1 and 0.01
absolute selective-risk reduction.

For each method and effect retain the point estimate, bootstrap mean, bootstrap standard error and
2.5%/97.5% percentile interval. The two-sided bootstrap tail diagnostic is
`2 * min(P*(effect <= 0), P*(effect >= 0))` with an add-one numerator and denominator correction,
capped at one. It is explicitly an empirical paired-bootstrap tail diagnostic, not an exact
randomization-test p-value.

## Multiplicity and D2 extension

The planned confirmatory family has six tests: the two endpoints on D0, D1 and prospective D2.
Holm correction is implemented and tested now, but is not applied to a partial D0/D1 family. After
the one-shot D2 run, apply it once to all six frozen p-values. No endpoint can be added or removed
based on significance. A practically positive result requires the point effect to meet 0.01 and
the percentile interval lower bound to exceed zero; multiplicity-adjusted inference is reported
separately.

For D2, the resampling unit changes to bearing identity stratified by the three pure classes, with
each identity carrying all settings and repetitions. The D2 closed-set endpoint is minimum held-
setting macro F1 rather than the descriptive minimum of all 24 identity/setting folds. That
extension must be tested on synthetic fixtures and inserted in the final Paderborn protocol before
archive contents are opened.

## Integrity gates

- The formal runner must verify this frozen protocol by SHA-256, verify the independent validation
  artifact by SHA-256 and passed status, and require that its recorded prediction/decision hashes
  equal the two requested inputs before reading either Parquet file.
- The formal runner must reject any replicate count other than 2,000 or root seed other than
  `20260818`.
- Input target predictions and long-form decisions must have identical dataset/method/seed/fold/
  row keys and identical environment, block, truth, prediction and correctness fields.
- Exactly PIRL, tuned ERM and seeds 11, 23, 37, 53 and 71 are accepted.
- Only score `risk_envelope`, nominal source coverage 0.5 and individual seeds enter the primary
  bootstrap; ensemble sentinel seed `-1` and all secondary scores are excluded.
- A physical block must map to exactly one environment, and every stratum needs at least two
  blocks.
- Store the full metric tensor and complete block draw plan as Parquet with row counts, byte counts
  and SHA-256; the summary JSON records every input and output hash.
