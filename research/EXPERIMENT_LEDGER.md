# Experiment ledger

This file is the human-readable, append-only interpretation layer. Machine-readable evidence lives
under `artifacts/research/runs/`. Failed, null, and superseded runs remain listed.

## EXP-000 — checkout and environment fingerprint

- Status: complete
- Date: 2026-08-17
- Source commit: `0dc184370e37833c74f32c529a7ef30d5df351ce`
- Checkout: `/home/fqy/lkcproject/SmartValve-AI-Twin`
- OS: WSL2, Ubuntu 24.04.4 LTS, Linux 6.18.33.2-microsoft-standard-WSL2
- Python: 3.12.3
- CPU allocation: 16 logical CPUs
- WSL memory: 15 GiB; swap: 4 GiB
- GPU: NVIDIA GeForce RTX 3080, 10,240 MiB, driver 610.74
- Storage at start: 922 GiB available on `/dev/sdd`
- System packages added: `python3-pip`, `python3-venv`, `make`
- Python environment: created at `.venv` from `build-requirements.lock` and
  `requirements-ci.lock`, then installed editable without resolving new dependencies.
- Installation note: locked `build==1.5.1` was yanked upstream for breaking-change concerns; the
  exact locked artifact installed successfully and is retained for reproduction.
- Interpretation: the checkout was clean and the target parent directory was empty before cloning.
  No pre-existing project data were overwritten.

## EXP-001 — locked-environment quality baseline

- Status: complete
- Date: 2026-08-17
- Source commit: `0dc184370e37833c74f32c529a7ef30d5df351ce` plus the uncommitted research
  instrumentation recorded in each run's `metadata.json`.
- Lint run: `EXP-001-LINT__20260817T145414.483821Z__locked-lint-baseline`
  - Command result: exit code 0; `All checks passed!`
  - Duration: 0.013205 seconds.
- Test run: `EXP-001-TEST__20260817T145421.866516Z__locked-test-baseline`
  - Command result: exit code 0; 37 passed, 3 skipped.
  - Duration: 18.156761 seconds (pytest reported 17.47 seconds).
  - Coverage: 79.07% over 2,045 statements, above the required 75% threshold.
- Interpretation: the locked Python 3.12 environment is internally consistent before data or model
  experiments. The three skips are retained in the recorded pytest log and are not silently counted
  as passes.

### Post-experiment regression gate

- Lint run: `EXP-001-FINAL-LINT__20260817T152241.914083Z__final-research-lint` — exit 0,
  all checks passed.
- Test run: `EXP-001-FINAL-TEST__20260817T152249.126265Z__final-research-test-baseline` —
  exit 0, 48 passed in 18.33 seconds, no skips, total coverage 84.90% (2,047 statements, 309
  missing) against the 75% gate.
- The previously skipped real Cranfield and SKAB tests ran after EXP-002 populated verified data.

## EXP-002 — public input acquisition and integrity verification

- Status: complete after two retained failed attempts and one verified recovery.
- Date: 2026-08-17
- Failed run 1: `EXP-002__20260817T145620.356100Z__public-data-sync`
  - Exit code 1: HTTP 429 from the legacy Cranfield `/bitstreams/<id>/download` route.
  - Diagnosis: the migrated route returned the DSpace HTML application rather than MATLAB bytes.
- Failed run 2: `EXP-002__20260817T150058.780486Z__public-data-sync-retry`
  - Exit code 1: the three corrected Cranfield REST downloads succeeded, then GitHub Raw returned
    HTTP 429 for SKAB because the anonymous shared egress IP was rate-limited.
- Recovery run: `EXP-002-SKAB-CACHE__20260817T150413.992207Z__skab-git-fallback-cache`
  - The official `waico/SKAB` Git repository was checked out at
    `b2c0d46c2971dcbfe71e26087b6d231998bb91c2`.
  - `data/valve1/1.csv` matched the locked SHA-256
    `fe4493bf805baef4e6dfb864094275d8cc2ea80a16b3735e2752b18b6aefd812` before caching.
- Successful validation run: `EXP-002__20260817T150422.021578Z__verified-public-data-cache`
  - Exit code 0; all four inputs matched both the locked byte counts and SHA-256 values.
- Engineering correction: Cranfield URLs now use the official DSpace REST `content` endpoint, the
  SKAB URL is commit-pinned, and downloads are checked against immutable sizes and hashes before
  atomic replacement. Three focused integrity tests cover success, rejection, and cache reuse.
- Interpretation: the first two failures were upstream route/rate-limit failures, not experimental
  exclusions. They remain available as machine-readable negative records.

## EXP-003 — checked-in Cranfield benchmark reproduction

- Status: complete
- Date: 2026-08-17
- Run: `EXP-003__20260817T150435.961604Z__cranfield-checked-in-reproduction`
- Exit code: 0; duration recorded in the run metadata.
- Result: 180 out-of-domain predictions over six motion-specific leave-one-load-out folds;
  accuracy 0.8722 and macro-F1 0.8736.
- Reproduction comparison:
  - `records.csv` is byte-for-byte identical to the checked-in artifact, SHA-256
    `cac17bae5b011ac32c6a7391996822c6650c8df118d5cdf3ee96f6e01dd9ff96`.
  - `model_card.md` is byte-for-byte identical, SHA-256
    `80671ad5300cf3789fa538ced9fe4fe64210688e47991c27e20fb4e1311ca8c3`.
  - `metrics.json` differs only in `generated_at`; every dataset, environment, protocol, fold, and
    aggregate field is identical.
- Interpretation: the published development baseline is exactly reproducible in the new locked WSL
  environment. It remains a P2 matched-target-reference result, not a no-target-calibration domain
  generalization claim.

## EXP-010 — healthy-reference access and causal negative-control audit

- Status: complete; all protocols falsified by the pre-registered worst-fold stopping rule.
- Date: 2026-08-17
- Equivalence run: `EXP-010-P2-CHECK__20260817T151115.500615Z__p2-implementation-equivalence`
  - P2 with the original seed 42 reproduced accuracy `0.872222`, macro-F1 `0.873587`, and all six
    fold accuracies from EXP-003 exactly.
- Superseded report run: `EXP-010__20260817T151154.359231Z__reference-access-causal-audit`
  - Predictions are valid, but the report incorrectly used only the control-ratio half of the
    two-part falsification rule. It is retained and must not be cited as the final interpretation.
- Corrected diagnostic rerun:
  `EXP-010__20260817T151535.278479Z__reference-audit-corrected-stopping-rule`
  - Categorical predictions were identical to the superseded run. Parallel tree-vote reduction
    produced only `3.33e-16` maximum probability tail variation.
- Final run: `EXP-010__20260817T151800.153926Z__reference-audit-v0-1-1-final`
  - Audit version: `cranfield-reference-audit-0.1.1`.
  - Exit code 0; duration 74.332680 seconds; 90 fitted models, 2,700 recorded OOD predictions.
  - Seeds: `11, 23, 37, 53, 71`; probabilities serialized at 12 decimal places.
  - Raw non-finite feature values: 0.
  - Metrics SHA-256: `e1fe3e26e883d2275678232c117dba00483c31fd834784fb84001d061400315b`.
  - Records SHA-256: `8225d752057a66d1af7065d3ca602bff511a133183e770036243136b21cfebc2`.

### Five-seed point estimates (mean ± sample standard deviation)

| Protocol | Macro-F1 | Worst-fold F1 | Brier | Nuisance TV | Fault TV | Control ratio |
|---|---:|---:|---:|---:|---:|---:|
| P0 raw, no target reference | 0.8548 ± 0.0060 | 0.1667 ± 0.0000 | 0.2087 ± 0.0049 | 0.2879 ± 0.0060 | 0.6573 ± 0.0050 | 0.4381 ± 0.0124 |
| P1 source-linear healthy reference | 0.7523 ± 0.0066 | 0.1667 ± 0.0000 | 0.4169 ± 0.0039 | 0.4320 ± 0.0037 | 0.4863 ± 0.0033 | 0.8884 ± 0.0086 |
| P2 matched-target healthy reference | 0.8699 ± 0.0033 | 0.1667 ± 0.0000 | 0.2462 ± 0.0054 | 0.2943 ± 0.0024 | 0.7043 ± 0.0042 | 0.4179 ± 0.0056 |

### Interpretation frozen after the final run

- P2 minus P0 macro-F1 is only `+0.015107`, while P2 requires a healthy trajectory from the target
  load and has a worse Brier score by `+0.037464` (lower is better).
- P1 minus P0 macro-F1 is `-0.102478`; two-source-load linear healthy extrapolation increases
  nuisance TV by `+0.144103` and reduces fault TV by `-0.171025`.
- The control-ratio criterion passes for every seed and protocol (`ratio < 1`), but the second
  stopping rule fails for every seed and protocol: the `trap/-40` fold has accuracy exactly `1/3`
  and macro-F1 exactly `1/6`.
- The failure is deterministic at the class level. P0 and P2 predict `normal` for all 30
  `trap/-40` trials; P1 predicts `lack_of_lubrication` for all 30.
- All sinusoidal folds are perfect for P0; P1's extrapolated reference additionally collapses the
  `sin/-40` fold to mean accuracy `0.3733` and macro-F1 `0.2425`.
- Conclusion: target-matched calibration produces a small average classification gain but does not
  repair the safety-critical low-load trapezoidal failure. A simple source-only linear reference is
  actively harmful under extrapolation. This is a useful falsification result and a concrete basis
  for the next mechanism-aware/abstaining method; it is not evidence of solved causal invariance.

## Pending runs

- EXP-012: completed below; retained here to preserve the original queue.
- EXP-020: completed below; retained here to preserve the original queue.

## EXP-011 — paired physical-block bootstrap

- Status: complete
- Date: 2026-08-17
- Protocol: `research/protocols/cranfield_bootstrap_v0.1.md`
- Final run: `EXP-011__20260817T154730.546117Z__paired-physical-block-bootstrap`
- Configuration: 2,000 deterministic replicates, RNG seed `20260817`, paired across protocols and
  seeds. Performance resampling is stratified by motion/load; control resampling synchronizes
  repetition draws across loads.
- Input records SHA-256:
  `8225d752057a66d1af7065d3ca602bff511a133183e770036243136b21cfebc2`.
- Replicate table SHA-256:
  `041c19087db5ecd255dcc9203cdd9ba0426bc5af346719847e744c3cccf6c0f3`.

### Point estimate and 95% percentile interval

| Protocol | Macro-F1 | Worst-fold F1 | Brier | Control ratio |
|---|---:|---:|---:|---:|
| P0 | 0.8548 [0.8397, 0.8710] | 0.1667 [0.1667, 0.1667] | 0.2087 [0.1971, 0.2210] | 0.4381 [0.4147, 0.4660] |
| P1 | 0.7523 [0.7321, 0.7733] | 0.1667 [0.1667, 0.1667] | 0.4169 [0.4019, 0.4331] | 0.8884 [0.8345, 0.9511] |
| P2 | 0.8699 [0.8505, 0.8857] | 0.1667 [0.1667, 0.1667] | 0.2462 [0.2337, 0.2593] | 0.4179 [0.3927, 0.4462] |

### Paired conclusions

- P1-P0 macro-F1: `-0.1025 [-0.1116, -0.0901]`; resolved below zero.
- P2-P0 macro-F1: `+0.0151 [-0.0069, +0.0373]`; not resolved away from zero.
- P2-P0 Brier: `+0.0375 [+0.0281, +0.0475]`; P2 is resolved as worse calibrated by this score.
- P2-P0 control ratio: `-0.0202 [-0.0528, +0.0101]`; not resolved away from zero.
- The bootstrap probability that the worst-fold accuracy is at or below balanced chance is `1.0`
  for P0, P1, and P2.
- Interpretation: target-condition healthy calibration has no statistically resolved macro-F1 or
  control-ratio advantage over raw P0, while its Brier score is reliably worse. Source-linear
  healthy extrapolation is reliably harmful. The low-load trapezoidal collapse is not a fragile
  repetition-sampling artifact.

### Implementation audit

- Initial DataFrame smoke run was correct but too slow.
- The tensorized implementation was compared on the same 20 bootstrap draws; all metrics matched
  with maximum absolute numerical difference `4.44e-16` before the 2,000-replicate run.

## EXP-012 — source-only selective prediction

- Status: complete; exploratory because its design followed the EXP-010 failure analysis.
- Date: 2026-08-17
- Protocol: `research/protocols/cranfield_selective_v0.1.md`
- Final run:
  `EXP-012__20260817T155423.605523Z__source-only-selective-prediction`
- Exit code 0; duration 66.651858 seconds.
- Base equivalence: all 900 P0 predictions and serialized class probabilities reproduced the final
  EXP-010 records exactly; maximum absolute probability difference `0.0`.
- Input reference SHA-256:
  `8225d752057a66d1af7065d3ca602bff511a133183e770036243136b21cfebc2`.
- Output records SHA-256:
  `b119688462bd6d417eea3bf179d8d680a902956aace939977fbd5cc065f1127b`.
- Coverage-risk curve SHA-256:
  `1b2ce144a27168ae1abcc8b298407c0a42df19245d13c1b6418d8f013bcdfc32`.
- Metrics SHA-256:
  `5cbcc74c6de756fe52af81c6a22694e4a9ef379946e453ca2988c895c9c9b340`.

### Five-seed point estimates (mean ± sample standard deviation)

| Policy | Coverage | Selective accuracy | F1, abstention=error | Error recall | Accepted errors | `trap/-40` errors |
|---|---:|---:|---:|---:|---:|---:|
| No rejection | 1.0000 ± 0.0000 | 0.8511 ± 0.0061 | 0.8548 ± 0.0060 | 0.0000 ± 0.0000 | 26.8 ± 1.1 | 20.0 ± 0.0 |
| Source-LOO conformal | 0.7967 ± 0.0108 | 0.8605 ± 0.0019 | 0.7567 ± 0.0086 | 0.2527 ± 0.0316 | 20.0 ± 0.0 | 20.0 ± 0.0 |
| Metadata support | 0.6667 ± 0.0000 | 0.9433 ± 0.0091 | 0.7541 ± 0.0075 | 0.7473 ± 0.0316 | 6.8 ± 1.1 | 0.0 ± 0.0 |
| Hybrid | 0.4633 ± 0.0108 | 1.0000 ± 0.0000 | 0.6243 ± 0.0109 | 1.0000 ± 0.0000 | 0.0 ± 0.0 | 0.0 ± 0.0 |

### Interpretation and claim boundary

- Source-to-source conformal calibration alone does not recognize the observed safety-critical
  extrapolation: it accepts all 20 P0 errors in `trap/-40` for every seed.
- The metadata-support policy rejects both `motion/-40` folds because `-40 kg` lies three
  source-span units outside the `[20, 40] kg` training envelope. It therefore removes the known
  `trap/-40` errors, but also rejects all correct `sin/-40` predictions.
- The hybrid accepts about 46.3% of predictions and has zero accepted errors on this finite dataset.
  This is an exploratory empirical result, not a target-domain conformal coverage guarantee.
- The hybrid was designed after observing EXP-010, the support threshold is an engineering rule,
  and all evidence comes from one rig. It needs prospective validation on a new asset or load grid
  before any safety or generalization claim.

## EXP-020 — classical estimator suite and environment-prediction probe

- Status: complete; the pre-specified model-independence criterion was not met.
- Date: 2026-08-18 (Asia/Shanghai; run directory uses a UTC timestamp)
- Protocol: `research/protocols/cranfield_baselines_v0.1.md`
- Final run:
  `EXP-020__20260817T160115.245489Z__classical-baselines-and-environment-probe`
- Exit code 0; duration 232.857987 seconds; 500 fitted models, 9,000 fault-classification
  predictions, and 1,800 environment-probe predictions.
- Base equivalence: all 1,800 P0/P2 ExtraTrees predictions and serialized probabilities reproduced
  EXP-010 exactly; maximum absolute probability difference `0.0`.
- Fault records SHA-256:
  `ca2bbedb1aee42ecb199076c0ba66f38886e9fb8cd0dceb3ca879bda82004e80`.
- Probe records SHA-256:
  `ffb0d3e3dea1da2216e1540820e959beaa27f205a03349a32793953d09511f43`.
- Metrics SHA-256:
  `f4b120824d8c39ffd555282d793dc018e7c0597381f1d17e1e2851f33eeb0150`.
- The 60 stderr warnings are the expected scikit-learn 1.9 deprecation warning for the frozen
  `SVC(probability=True)` setting: one warning for each P0/P2 RBF-SVM outer-fold fit. There are no
  convergence, numerical, or execution errors.

### Fault classification (five-seed mean ± sample standard deviation)

| Representation | Estimator | Macro-F1 | Worst-fold F1 | Brier | Control ratio |
|---|---|---:|---:|---:|---:|
| P0 | ExtraTrees | 0.8548 ± 0.0060 | 0.1667 ± 0.0000 | 0.2087 ± 0.0049 | 0.4381 ± 0.0124 |
| P0 | Logistic | 0.8482 ± 0.0000 | 0.5556 ± 0.0000 | 0.2366 ± 0.0000 | 0.2537 ± 0.0000 |
| P0 | RBF-SVM | 0.8850 ± 0.0000 | 0.5556 ± 0.0000 | 0.2487 ± 0.0015 | 0.4590 ± 0.0042 |
| P0 | HistGradientBoosting | 0.7833 ± 0.0000 | 0.4573 ± 0.0000 | 0.3272 ± 0.0000 | 0.4776 ± 0.0000 |
| P0 | Shrinkage LDA | 0.8273 ± 0.0000 | 0.4779 ± 0.0000 | 0.3414 ± 0.0000 | 0.2723 ± 0.0000 |
| P2 | ExtraTrees | 0.8699 ± 0.0033 | 0.1667 ± 0.0000 | 0.2462 ± 0.0054 | 0.4179 ± 0.0056 |
| P2 | Logistic | 0.8993 ± 0.0000 | 0.5308 ± 0.0000 | 0.1711 ± 0.0000 | 0.2003 ± 0.0000 |
| P2 | RBF-SVM | 0.9102 ± 0.0000 | 0.5411 ± 0.0000 | 0.1861 ± 0.0014 | 0.3292 ± 0.0027 |
| P2 | HistGradientBoosting | 0.8554 ± 0.0000 | 0.5244 ± 0.0000 | 0.3072 ± 0.0000 | 0.4650 ± 0.0000 |
| P2 | Shrinkage LDA | 0.8695 ± 0.0000 | 0.1667 ± 0.0000 | 0.2630 ± 0.0000 | 0.2874 ± 0.0000 |

### Environment probe and interpretation

- P0 load-prediction macro-F1 is `1.0000 ± 0.0000` overall and separately for both motions.
- P2 load-prediction macro-F1 is `0.9034 ± 0.0050`: `0.9075 ± 0.0063` for trapezoidal and
  `0.9000 ± 0.0077` for sinusoidal motion.
- No held-out repetition was used as a P2 healthy reference. Thus the load-prediction result is not
  caused by direct repetition leakage, although P2 necessarily uses known load to select a
  same-load healthy trajectory.
- Only P0 ExtraTrees reproduces a chance-level-or-worse `trap/-40` fold for every seed. Logistic,
  RBF-SVM, HistGradientBoosting, and shrinkage LDA do not. The frozen requirement of at least three
  estimator families therefore fails, and the catastrophic fold cannot be claimed as
  model-independent.
- All five P0 estimator families nevertheless have imperfect trapezoidal worst folds, while the raw
  representation makes operating load perfectly decodable by the frozen probe. This supports a
  narrower claim of strong nuisance retention and estimator-dependent extrapolation behavior, not
  a universal low-load collapse or causal shortcut attribution.

## EXP-PAPER-001/002 — locked manuscript artifacts

- Status: complete; EXP-PAPER-001 is superseded only because its manifest stored workstation-
  specific absolute input paths. Its numerical tables and figures remain valid.
- Date: 2026-08-18 (Asia/Shanghai; run directories use UTC timestamps)
- Superseded run:
  `EXP-PAPER-001__20260817T161753.304054Z__locked-manuscript-artifacts`.
- Final run:
  `EXP-PAPER-002__20260817T162148.031122Z__final-locked-manuscript-artifacts`.
- Locked inputs: the exact EXP-010, EXP-011, EXP-012, and EXP-020 metric files listed in
  `paper/README.md`; generation stops on any SHA-256 mismatch.
- Outputs: seven tables in CSV/Markdown/LaTeX, four SVG figures, captions, a claim-to-field map, and
  a manifest with byte counts and SHA-256 values.
- Final artifact-manifest SHA-256:
  `8647cbebaa00b6f616af28a2d0d2f846ae86d4d4d50905d12646a109cab619ed`.
- The separately generated `paper/generated/` directory is byte-for-byte identical to the formal
  EXP-PAPER-002 output, including its manifest.
- All four SVGs were parsed as XML and rendered to exact-size PNGs for visual inspection. Titles,
  axes, error bars, legends, heatmap labels, point annotations, and plot boundaries were readable
  without clipping or overlap.
- Interpretation: all manuscript numbers and plots are derived from immutable JSON inputs rather
  than manual transcription. Project-relative provenance paths make the final manifest stable
  across checkout locations.

## EXP-PAPER-FINAL — manuscript-start quality gate

- Status: complete
- Date: 2026-08-18 (Asia/Shanghai; run directories use UTC timestamps)
- Lint run:
  `EXP-PAPER-FINAL-LINT__20260817T162803.522236Z__manuscript-package-lint` — exit 0;
  `All checks passed!` over `src`, `tests`, and `dashboard`.
- Regression run:
  `EXP-PAPER-FINAL-TEST__20260817T162809.790438Z__manuscript-package-test` — exit 0;
  68 passed in 11.11 seconds, with no skips.
- Explicit coverage run:
  `EXP-PAPER-FINAL-COVERAGE__20260817T162855.850982Z__manuscript-package-coverage` — exit 0;
  68 passed in 19.76 seconds; 84.90% total coverage over 2,047 statements, above the frozen 75%
  threshold.
- Source fingerprint shared by all three runs:
  `dbcac441337c83e58b1d199b66d5a1fa62c38a772e653faa0dd34d00b5987b76` over 163 source files;
  Git diff SHA-256 `580f1dc2d92d43daf273d60ff619fe828671be4a7fa1e93e19896ceb2f613568`.
- The only warning is the expected scikit-learn 1.9 deprecation notice for the frozen
  `SVC(probability=True)` smoke test; no convergence, integrity, citation, or artifact mismatch was
  reported.
- Post-documentation seal:
  `EXP-PAPER-SEAL__20260817T163040.084299Z__final-paper-ready-seal` — exit 0; 68 passed in 19.83
  seconds, 84.90% coverage, with SVG parsing and the finalized citation/artifact tests included.
  Its 163-file source fingerprint is
  `86b1c13d9ccd372d1f3443bb83ac3ee3317d758d407b721ce1961fcb09a96e28`.
- Gate decision: the evidence and manuscript starter package are ready for drafting. This is not a
  submission, deployment, independent-asset, or novelty-acceptance gate.

## EXP-100/110-FEATURES — frozen UCI hydraulic acquisition and feature cohort

- Status: complete; classifier audit remains a separately recorded run.
- Date: 2026-08-18
- Official acquisition:
  EXP-100-UCI-DOWNLOAD__20260818T025729.220303Z__official-uci-hydraulic-candidate —
  exit 0 in 5.613521 seconds.
- Official archive: 76,601,704 bytes; SHA-256
  24128aad2ee45eea7e6b63ebbd9992cdf25d0483a2cebefbfc13bc69079af1f2.
- Frozen feature run:
  EXP-110-UCI-FEATURES__20260818T030851.015050Z__frozen-physical-sensor-features —
  exit 0 in 19.777881 seconds.
- Cohort: 1,440 stable cycles, 36 exact operating contexts, 360 complete four-valve-state
  repetition blocks, 14 physical sensors and 336 deterministic features.
- Feature matrix: 3,415,814 bytes; SHA-256
  4359ce099e421cc9e55c65115d39f4a4c0463255f72f834a49d802fa6a038516.
- Interpretation: the cohort and feature representation were frozen before the estimator audit.
  The archive hash, feature matrix and audit protocol are independent evidence layers.

## EXP-110-AUDIT/IDENTITY — full UCI access audit and record cross-check

- Status: complete frozen point-estimate audit plus exact pre-bootstrap identity validation.
- Date: 2026-08-18.
- Audit run:
  `EXP-110-UCI-AUDIT__20260818T030934.359923Z__frozen-access-estimator-audit` — exit 0 in
  22,822.619193 seconds.
- Design: five estimator families, P0/P1/P2 access protocols, five model seeds and ten
  held-context-level folds. The 750 fitted models emit 324,000 row-level target predictions because
  every physical cycle is held out once along each of the three context axes.
- Records/metrics/report SHA-256 values are
  `315d3da4dd386d3d4353fdf270f61035a64f94184d6c9c7f812821ad47b1a894`,
  `16551d2d585745c5581957c385c51e86adcb678f7aa1d9b8b0c271c9e482dfa4` and
  `b58986ca50a77e29fc847f42bd4a815bcb70aad29ad4d7360386f5ea5c7eda9d`.
- The P0 mean-fold macro-F1 point estimates range from 0.6116 for RBF SVM to 0.9183 for
  ExtraTrees. P1 is lower than P0 for every estimator. P2 is a separately labeled target-calibration
  regime and cannot be counted as source-only DG.
- Audit source fingerprint:
  `a874efeab4d198cd0db2baabe3062c837395c58a35f5809f355b30893a299dca` over 169 files.
- Identity run:
  `EXP-110-IDENTITY__20260818T090439.928592Z__bootstrap-identity-point-crosscheck` — exit 0 in
  2.610997 seconds.
- All 600 estimator/protocol/seed/metric values reconstructed from the record table match the audit
  JSON within tolerance `1e-10`; maximum absolute difference is
  `8.881784197001252e-16`. Identity artifact SHA-256:
  `fa4ae029f7c062c6d13ad2b437be6cc2f4cd73a0f9b164a704e77134ccf3c5fd`.
- The completed audit contains only the documented scikit-learn 1.9 SVC probability deprecation;
  its exit status and artifact integrity are clean.

## EXP-111 — frozen UCI paired physical-block bootstrap

- Status: complete external-development uncertainty result.
- Date: 2026-08-18.
- Run:
  `EXP-111-UCI-BOOTSTRAP__20260818T090501.201288Z__frozen-paired-physical-block-bootstrap` — exit
  0 in 356.558806 seconds.
- Protocol: 2,000 replicates with RNG seed 20260818. Performance draws are stratified within each
  exact context; matched-control repetition draws are synchronized across levels of the tested
  factor. Model seeds are averaged and are never resampled as physical replicates.
- The source-derived P1 reference harms mean-fold macro F1 for all five estimators with intervals
  excluding zero, so the predeclared C1 model-independence criterion passes 5/5. The predeclared C2
  statement that matched-target P2 has no F1 gain and worse Brier is supported by 0/5 estimators and
  is rejected as a model-independent replication claim.
- This heterogeneity sharpens the access result: source-linear reference construction is reliably
  harmful on this rig, while reading a target healthy cycle can materially help and therefore must
  remain labeled target calibration rather than pure DG.
- Replicate/metrics/report SHA-256 values are
  `46e8d896deb18ba619a2ff2d971ec3f838d82848063e58a932751483498ebccb`,
  `d3e71c5ae314f15a42ea397323b8d65842fdc6b0a62587d42f54d8f1c00e0c46` and
  `d55f8e798629dda904e5ee948278667d9efebb6ee7f71b3a6356f75d476fb4a7`.
- The retained replicate table has 30,000 rows. Audit and bootstrap used the same record bytes, as
  enforced by EXP-110-IDENTITY.
- Bootstrap source fingerprint:
  `83df6d4a2e24cc49a4a11eb992813bf06472acf429b1fbef3b1ecb5af0895005` over 239 files.
- These are access-audit results, not the PIRL-versus-ERM confirmatory family. Paderborn archive
  contents remained unopened.

## EXP-200/201 — sealed Paderborn prospective acquisition

- Status: complete; archive contents remain sealed.
- Date: 2026-08-18
- Acquisition run:
  EXP-200-PADERBORN-LOCK__20260818T051530.141110Z__sealed-official-archive-acquisition —
  exit 0 in 822.654150 seconds.
- Acquired all 32 official bearing archives under the academic CC BY-NC 4.0 boundary. Total
  archive bytes: 5,357,708,539.
- Lock manifest SHA-256:
  aadfde07c8b23764208794b0165ac6fe5a90a97345bfa368c01eb047dbedc3d2.
- Independent full-cache verification:
  EXP-201-PADERBORN-VERIFY__20260818T052829.541442Z__independent-full-lock-verification —
  exit 0 in 11.409955 seconds; all 32 archives and 5,357,708,539 bytes matched the lock.
- Prospective seal at both runs: archive_contents_opened=false,
  signal_features_computed=false, and model_outcomes_inspected=false.
- Interpretation: byte acquisition does not authorize data inspection. D2 may be opened only after
  the exact method, baselines, splits, hyperparameters, metrics and statistical decisions are
  frozen.

## EXP-300/302 — RTX 3080 PyTorch/CUDA research environment

- Status: complete after two retained initialization-order failures.
- Date: 2026-08-18
- Environment: PyTorch 2.13.0+cu130, compiled CUDA 13.0, cuDNN 9.20.0, driver 610.74,
  RTX 3080 10,240 MiB and compute capability 8.6.
- EXP-300-GPU-ENV__20260818T053530.458309Z__rtx3080-pytorch-cuda-determinism failed
  before tensor execution because memory statistics received an uninitialized device object.
- EXP-301-GPU-ENV__20260818T053605.670125Z__rtx3080-pytorch-cuda-determinism-fixed-device-in
  retained the failure after changing the device argument but still preceding context
  initialization.
- Final run:
  EXP-302-GPU-ENV__20260818T053640.978428Z__rtx3080-pytorch-cuda-determinism-initialized —
  exit 0 in 4.246452 seconds.
- Both reconstructed CUDA logits and gradients were bit-for-bit identical. CPU-GPU maximum
  absolute logit error was 1.1920928955078125e-07; maximum gradient error was
  3.725290298461914e-09; every frozen numerical check passed.
- GPU result SHA-256:
  5b6c661f16cb43c3d2a6338ed46b0504119f0ede244f1aac0aa528c24786342f.
  Exact package inventory SHA-256:
  ea629673ba09c1396c928f69ecaddd9b13455a4613cf56d030fe614127e72284.
- Interpretation: the local GPU is validated for deterministic compact-model development. The
  microbenchmark is a feasibility record, not a paper performance claim.

## EXP-310 — unified D0/D1 source-only domain contract

- Status: complete
- Date: 2026-08-18
- Run:
  EXP-310-DOMAIN-CONTRACT__20260818T054305.026903Z__audited-d0-d1-source-only-pair-topology
  — exit 0 in 8.612502 seconds.
- Contract output SHA-256:
  b4284c90e91b8b8df9f7b571c44fd8ca1a809f60b3701c318076217ce2e76473.
- D0: 180 rows, 136 features and three global leave-one-load-out folds. Every fold has 120 source
  rows, 60 target rows, 60 source nuisance pairs and 120 source fault pairs.
- D1: 1,440 rows, 336 features and ten leave-one-factor-level-out folds. Cooler/pump folds each
  have 960 source rows, 480 target rows, 480 nuisance pairs and 1,440 fault pairs. Accumulator
  folds each have 1,080 source rows, 360 target rows, 1,080 nuisance pairs and 1,620 fault pairs.
- All pair coordinates are source-local; validation rejects target overlap, incomplete partitions,
  nonfinite features, label-changing nuisance pairs and same-label fault pairs.
- Paderborn archive contents remained unopened.

## EXP-320 — frozen D0/D1 PIRL-SORE initial screen

- Status: complete; descriptive efficacy gate passed, mechanism attribution unresolved at this
  point and delegated to the prospectively frozen EXP-321 ablation.
- Date: 2026-08-18
- Run:
  EXP-320-PIRL-SCREEN__20260818T054905.652647Z__frozen-d0-d1-pirl-sore-versus-erm-screen
  — exit 0 in 875.837577 seconds.
- Protocol: research/protocols/pirl_sore_screen_v0.1.md.
- Design: identical-backbone ERM versus full PIRL-SORE; 300 epochs, five paired seeds, three
  Cranfield outer folds and ten UCI outer folds. All 130 models completed.
- Prediction artifact: 45,000 rows, 10,418,567 bytes; SHA-256
  a80a93ef58aef8a135fe53dde3ed00a6255b350c3d766d5236e7e9555e02fa13.
- Training traces: 130 model histories, 704,418 bytes; SHA-256
  c0f0002b577e446e3f7a38cb5296d55bd02a31591de7c7f404e88691c2ad2302.
- Metrics SHA-256:
  2909e32f19aa4b9beb5c28da821c1fd3e8b4e6670691eb64e03a21a5c9182ebf.

### Five-seed mean ± sample standard deviation

| Dataset | Method | Mean-fold macro F1 | Worst-fold macro F1 | Brier | AURC | Source representation ratio |
|---|---|---:|---:|---:|---:|---:|
| Cranfield | ERM | 0.8403 ± 0.0220 | 0.7449 ± 0.0445 | 0.2466 ± 0.0344 | 0.0467 ± 0.0197 | 0.00113 ± 0.00009 |
| Cranfield | PIRL-SORE | 0.8366 ± 0.0250 | 0.7411 ± 0.0416 | 0.2517 ± 0.0306 | 0.0472 ± 0.0160 | 0.00164 ± 0.00007 |
| UCI | ERM | 0.6831 ± 0.0067 | 0.1043 ± 0.0051 | 0.4375 ± 0.0070 | 0.1382 ± 0.0063 | 0.02104 ± 0.00130 |
| UCI | PIRL-SORE | 0.6962 ± 0.0075 | 0.1093 ± 0.0068 | 0.4212 ± 0.0045 | 0.1224 ± 0.0057 | 0.05449 ± 0.00350 |

### Paired descriptive effects and interpretation

- On UCI, PIRL-SORE minus ERM was +0.01311 mean-fold macro F1, +0.00497 worst-fold macro F1,
  -0.01629 Brier and -0.01577 AURC. On Cranfield it was -0.00376 mean-fold macro F1 and
  -0.00378 worst-fold macro F1.
- Therefore the frozen screening gate passed: worst-fold macro F1 improved on UCI and the
  Cranfield mean-fold regression was smaller than 0.02.
- The mechanism evidence contradicted the intended explanation. UCI source representation-response
  ratio increased by 0.03345 and the probability-response ratio increased by 0.03614. Cranfield
  ratios also increased.
- The intervention hinge was positive at the first recorded epoch for all 130 models but exactly
  zero at the final epoch for all 130. This means the performance comparison cannot identify
  whether early intervention shaping or the persistent worst-environment term caused the gain.
- Compute remained small: maximum allocated CUDA memory was 72,202,240 bytes on UCI and 67,749,376
  bytes on Cranfield. The local RTX 3080 is not a limiting factor for this experiment class.
- Claim boundary: this is a reason to continue controlled development, not evidence that the
  proposed intervention mechanism works and not a top-tier-ready result.

## EXP-321 — frozen PIRL component-attribution ablation

- Status: complete; the current saturating intervention hinge was rejected as the headline
  mechanism by the pre-specified rule.
- Date: 2026-08-18
- Run:
  EXP-321-PIRL-ABLATION__20260818T060549.112136Z__frozen-component-attribution-worst-versus-interv
  — exit 0 in 807.279471 seconds.
- Protocol: research/protocols/pirl_component_ablation_v0.1.md.
- Locked reference: EXP-320 metrics, predictions and training traces were verified against their
  frozen SHA-256 values before fitting any ablation model.
- New arms: worst_erm and pirl_only; 300 epochs, five paired seeds and the same 13 outer folds.
  All 130 new models completed.
- Prediction artifact: 45,000 rows; SHA-256
  e1fd4c0bec37326db32b48bda4ea80a222d6852953e657c847ca84b5ce167048.
- Training-trace SHA-256:
  a9e76a3dba8ec572a586586d1586d7d38bce776b81f6f3fa94a7c0a9dc564c8a.
- Metrics SHA-256:
  bb0f8d2a99b7e906a37ed54c78880d6f1557925042b7b187130ca25c5f91f24c.

### Five-seed mean ± sample standard deviation

| Dataset | Method | Mean-fold macro F1 | Worst-fold macro F1 | Brier | AURC | Source representation ratio |
|---|---|---:|---:|---:|---:|---:|
| Cranfield | worst_erm | 0.8360 ± 0.0233 | 0.7411 ± 0.0416 | 0.2548 ± 0.0358 | 0.0499 ± 0.0192 | 0.00127 ± 0.00012 |
| Cranfield | pirl_only | 0.8387 ± 0.0206 | 0.7553 ± 0.0220 | 0.2415 ± 0.0315 | 0.0441 ± 0.0144 | 0.00177 ± 0.00006 |
| UCI | worst_erm | 0.6861 ± 0.0082 | 0.1077 ± 0.0054 | 0.4328 ± 0.0115 | 0.1328 ± 0.0108 | 0.05024 ± 0.00380 |
| UCI | pirl_only | 0.7027 ± 0.0089 | 0.1051 ± 0.0019 | 0.4150 ± 0.0086 | 0.1252 ± 0.0136 | 0.03378 ± 0.00534 |

### Attribution decision

- Relative to locked ERM, pirl_only changed UCI mean-fold macro F1 by +0.01952, worst-fold F1 by
  +0.00082, Brier by -0.02248 and AURC by -0.01304. On Cranfield it changed mean-fold macro F1
  by -0.00158, worst-fold F1 by +0.01042, Brier by -0.00512 and AURC by -0.00259.
- worst_erm recovered only 22.9% of the full model's UCI mean-F1 gain; pirl_only recovered 148.9%.
  The gain is therefore not primarily attributable to the worst-environment term.
- Nevertheless, pirl_only increased the source representation-response ratio by +0.00064 on
  Cranfield and +0.01274 on UCI. It failed the frozen requirement to lower this ratio on both
  development datasets.
- Automatic decision:
  current_intervention_hinge_mechanistically_supported=false and
  headline_current_hinge_rejected=true.
- Interpretation: early hinge activation appears to improve optimization and generalization, but
  the measured final representation moves opposite to the stated mechanism. The result is useful
  development evidence but cannot support a causal-invariance or intervention-separation claim.
  A non-saturating replacement must receive a new protocol and be selected without D2 access.

## EXP-311 — metadata-only prospective Paderborn split manifest

- Status: complete; this is a candidate manifest and does not authorize D2 execution.
- Date: 2026-08-18
- Run:
  `EXP-311-PADERBORN-SPLIT__20260818T065237.888546Z__metadata-only-prospective-split-manifest`
  — exit 0 in 0.459354 seconds.
- Scope: official metadata only. Archive contents were not opened, signal features were not
  computed, and model outcomes were not inspected.
- Closed-set cohort: 29 pure-class assets (6 healthy, 12 outer-ring, 11 inner-ring). KB23, KB24
  and KB27 remain excluded from fitting/accuracy and reserved for a compound/open-set abstention
  stress test.
- Candidate structure: six disjoint identity folds crossed with the four official operating
  settings, giving 24 strict double-unseen folds. Each target is the held-identity/held-setting
  intersection; source training excludes both the held identities and the complete held setting.
- Balance audit: one healthy and two outer-ring assets per identity fold; two inner-ring assets in
  five folds and one in the sixth. Every fold contains both artificial and real damage origins.
- Validation: 9 focused Paderborn metadata/split tests passed, and Ruff reported no violations.
- Manifest SHA-256:
  `b5ff36988d70ccff22bfccc8b7108d1ad778616a4b5ebf79ffa9e3c2c278f7e7`.
- Source fingerprint:
  `c0a30186f7bab04f1e8c0c8d3845417d2cc8b361b95dafa857bb6c0c71676e58` over 206 files.
- Interpretation: the split identities can no longer be adjusted after seeing D2 outcomes. The
  preprocessing, method/baseline configurations, statistics, multiplicity rule and final seal
  still have to be frozen on D0/D1 before any archive extraction.

## EXP-312 — metadata-only Paderborn partition and pair topology

- Status: complete; still not D2 execution authorization.
- Date: 2026-08-18
- Run:
  `EXP-312-PADERBORN-TOPOLOGY__20260818T070514.746259Z__metadata-only-source-target-quarantine-pairs`
  — exit 0 in 3.8095 seconds.
- Input: the complete synthetic 2,320-row pure-class measurement index implied by the official
  identity, setting and repetition metadata. No signal value or archive member was read.
- Partition result: all 24 identity/setting folds passed disjoint source/target/quarantine checks.
  Folds 0–4 contain 1,440/100/780 rows; fold 5 contains 1,500/80/740 rows. Every closed-set
  measurement is target exactly once across the 24 folds.
- Nuisance pairs: 1,440 per fold for folds 0–4 and 1,500 for fold 5, always the same
  identity/measurement under two source settings.
- Fault pairs: 900 per fold, exactly 300 each for healthy–outer, healthy–inner and outer–inner.
  Deterministic identity rotation prevents the larger outer/inner asset product from silently
  changing the response estimand.
- Validation: 12 combined Paderborn metadata/split/partition tests passed; Ruff passed.
- Manifest SHA-256:
  `d80ebf54e00499569e7773ad13b1ef72e52bfca7b95e1a525711c86bcc027a68`.
- Source fingerprint:
  `d2ac6752f168fae3954fe8de7d486790efc782a33532c0812f7996021aadf00a` over 212 files.
- Seal state: archive_contents_opened=false, signal_features_computed=false,
  model_outcomes_inspected=false.

## EXP-315 — metadata-only Paderborn bearing-cluster bootstrap contract

- Status: complete synthetic statistical-path validation; not D2 execution authorization.
- Date: 2026-08-18.
- Run:
  `EXP-315-PADERBORN-BOOTSTRAP__20260818T081854.840149Z__synthetic-bearing-cluster-bootstrap-contract`
  — exit 0 in 2.800395 seconds; stderr was empty.
- The confirmatory resampling unit is one complete bearing identity, stratified within healthy,
  outer-ring and inner-ring classes. Every draw broadcasts one identity weight to all four
  settings and all 20 repetitions; measurements are never treated as independent replicates.
- The implementation validates the exact 29-bearing/2,320-measurement pure cohort, official label
  map, frozen 24-fold target membership, method/seed completeness and decision/prediction metadata
  parity before forming a tensor.
- The primary efficacy endpoint is the minimum of four pooled setting-level macro-F1 values. The
  24 individual identity/setting-fold minima remain descriptive and cannot replace that endpoint.
- Four full-schema synthetic tests passed, covering point effects, paired seed handling,
  within-class identity draws, whole-bearing weight broadcast, corrupted-label rejection, and
  retained draw/metric artifacts. Stdout SHA-256:
  `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830`.
- Implementation SHA-256:
  `b1dc71ff0065ef26c6d399bbf358e35dba20b95b3d99f63d63e64531c9336923`;
  test SHA-256:
  `b709bd9f746bf5b0bb6c5c3e8c279f3dce6901fabeffa508880ca43205c98713`.
- Recorded source fingerprint:
  `c636dc079904c37d111202c491aa57adff696fbf0e6b87b8bcfa777d637682ee` over 233 files.
- Seal state remained unchanged: no Paderborn archive member was listed, extracted or opened.

## EXP-315B — global Paderborn measurement-coordinate contract

- Status: complete synthetic provenance hardening; not D2 execution authorization.
- Date: 2026-08-18.
- Run:
  `EXP-315B-PADERBORN-BOOTSTRAP__20260818T084257.728574Z__global-measurement-coordinate-contract`
  — exit 0 in 3.037594 seconds; all five focused tests passed and stderr was empty.
- Beyond the exact official measurement-key set, every target artifact must now use a unique
  global 0-based `row_index` covering 0 through 2,319. Reusing fold-local coordinates is rejected.
  Every `block_id` must also equal its canonical bearing/setting/measurement key.
- Updated implementation/test SHA-256 values are
  `bb61b60f0e2ddb7828bc553b27993e13defba1b45b78f4605c70cf5636efab93` and
  `0afff7aef1a2273146c562c54254170b7cd66f008ed7122113d37a27ee1833ac`;
  stdout SHA-256:
  `4d2df7a96ce4a667da3ccf295f2d16c728a65ed0e861a3baa919f7bb469b02b5`.
- Recorded source fingerprint:
  `dc989f989648398cc6665fa762304109bf535a6ae9071f5be9ac010526387508` over 239 files.
- Paderborn archives remained unopened.

## EXP-345 — post-bearing-bootstrap full quality gate

- Status: complete; implementation integrity only, not a performance result.
- Date: 2026-08-18.
- Formal lint:
  `EXP-345-LINT__20260818T082025.232007Z__post-bearing-bootstrap-full-lint` — exit 0;
  stdout SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal regression:
  `EXP-345-TEST__20260818T082029.627610Z__post-bearing-bootstrap-full-regression` — exit 0 in
  46.261929 seconds; all 180 collected tests passed. The sole warning remains the documented
  scikit-learn 1.9 SVC probability deprecation. Stdout SHA-256:
  `8a72eb6e3296f15b4f452e87d33b29dc49a9c9fd03fcfbc18307cd2f8cd946e6`.
- Both runs used source fingerprint
  `f0520cdd50aaddad75388300732ef900391de044d7874ac0adf37c8c8933aece` over 233 files.
- D2 seal state remained unchanged: no archive member was listed, extracted or opened.

## EXP-346 — frozen six-test confirmatory-family assembly contract

- Status: complete synthetic statistical-contract validation; no model outcome was used.
- Date: 2026-08-18.
- Run:
  `EXP-346-CONFIRMATORY__20260818T082513.753545Z__frozen-six-test-holm-assembly-contract`
  — exit 0 in 1.800455 seconds; all three focused tests passed and stderr was empty.
- The family contains exactly two endpoints for each of Cranfield, UCI Hydraulic and Paderborn.
  All six raw two-sided add-one bootstrap tail values enter one stable Holm step-down correction.
- A dataset/endpoint cell is confirmatory-positive only when its signed PIRL effect is at least
  0.01, its percentile interval lower bound is above zero and its Holm-adjusted p-value is at most
  0.05. The output also discloses materially harmful cells; no subset or pooled replacement is
  permitted.
- Both input JSON files must match final-seal SHA-256 values. The assembler additionally rejects
  changed bootstrap version, replicate count, seed, method/seed set, coverage score/level, D2
  resampling unit, class stratification or physical cohort counts.
- Implementation SHA-256:
  `aed9aa9c6bdf66a1a87dcabcc5a940fb006ebaeb11b18c220507bd7f1dc8dc19`;
  test SHA-256:
  `8a9b2e8abab6d5201bb5276872f577180c94195ec1962d873793b42e94b76a2d`;
  stdout SHA-256:
  `cf426ab35f3b06fccef8290fde5325d90af130a79da1d1752031518df77c4236`.
- Recorded source fingerprint:
  `6a316ca9b3ce35a3dfacba6c56fb52488b078149e4ac6c6d160bbe6ab1950001` over 235 files.
- Paderborn archives remained unopened.

## EXP-347 — full regression and line-coverage gate

- Status: complete implementation gate; not a model-performance result.
- Date: 2026-08-18.
- Run:
  `EXP-347-COVERAGE__20260818T082558.770960Z__research-pipeline-full-coverage-gate`
  — exit 0 in 88.025597 seconds.
- All 183 collected tests passed. Aggregate measured line coverage was 76.90% over 4,614
  statements, above the prospectively enforced 75% minimum. The Paderborn bearing bootstrap and
  six-test family modules reached 85% and 78%, respectively.
- The sole warning remains the documented scikit-learn 1.9 SVC probability deprecation; it does
  not change the currently frozen estimator implementation.
- Stdout/coverage-report SHA-256:
  `b2c7f614cfc1f4daf43dc7174cf804c3f8a5d6fad5c013347d79a1158d8d4698`.
- Recorded source fingerprint:
  `268a83f8c0fb9ea7acd1cb753406d3058fe8e4ea07791a1a70651894d127f1bb` over 235 files.
- Paderborn archives remained unopened.

## EXP-348 — DG expected-manifest and validator quality gate

- Status: complete implementation integrity gate; EXP-340 performance remains uninspected.
- Date: 2026-08-18.
- Formal lint:
  `EXP-348-LINT__20260818T083715.754219Z__post-dg-manifest-validator-full-lint` — exit 0;
  stdout SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal regression:
  `EXP-348-TEST__20260818T083721.878685Z__post-dg-manifest-validator-full-regression` — exit 0
  in 44.582417 seconds; all 189 collected tests passed. The sole warning remains the documented
  scikit-learn 1.9 SVC probability deprecation. Stdout SHA-256:
  `09fe13184e7e63ad85daffcd25ebe8d894b19113b2d6d310596adf14b7f7c5ec`.
- The post-run validator recomputes every frozen selection, canonical key-set and physical
  provenance hash; verifies artifact byte counts/SHA-256 values; checks all tuning/final model and
  DANN discriminator hashes; and reconstructs probabilities from logits, predictions from
  argmax, correctness, confidence and unit representation norms.
- Validator/test SHA-256 values are
  `7e040ffbdb6e02e185c4ce17ada9acc18d3b623b916b26ba9f438738d2eb016a` and
  `508ee13a91d8c715b09d46e1fb1410ba8be693f5f6472e2f8c101ed5fab25c7b`.
- Both formal runs used source fingerprint
  `c452a169c8cd2d4dc13debf557fff5c7371e353de5c899325cb17152777a822f` over 239 files.
- Paderborn archive contents remained unopened.

## EXP-349 — frozen multi-dataset evidence gate

- Status: complete pre-outcome statistical decision contract; no model outcome was used.
- Date: 2026-08-18.
- Run:
  `EXP-349-CONFIRMATORY-GATE__20260818T084029.381275Z__frozen-multi-dataset-evidence-gate`
  — exit 0 in 2.257578 seconds; all three focused tests passed and stderr was empty.
- The existing internal top-tier evidence rule is now executable: at least two of Cranfield, UCI
  Hydraulic and Paderborn must each have at least one confirmatory-positive primary endpoint, and
  no dataset may contain a signed effect of -0.01 or worse whose 95% interval lies below zero.
- A confirmatory-positive endpoint still requires the full EXP-346 cell rule: signed effect at
  least +0.01, lower 95% percentile bound above zero and Holm-adjusted p at most 0.05 across all
  six tests. This gate cannot substitute an uncorrected or pooled result.
- Updated implementation/test SHA-256 values are
  `359708ef6a318da401de4a3af603ebab9601e07542f4760fc6f29ea432191ef1` and
  `e87e63511be85a9af9c24654162c1faf025a06f81185a1099e6e69e954be55a8`;
  stdout SHA-256 remains
  `cf426ab35f3b06fccef8290fde5325d90af130a79da1d1752031518df77c4236`.
- Recorded source fingerprint:
  `1fa191859be8f81a33e95e5f7244c4ae8ecbc496397a7c033679cf58028c95e2` over 239 files.
- Paderborn archives remained unopened.

## EXP-349B — multi-dataset pass and material-harm veto branches

- Status: complete branch-completeness validation; no model outcome was used.
- Date: 2026-08-18.
- Run:
  `EXP-349B-CONFIRMATORY-GATE__20260818T084130.005288Z__multi-dataset-pass-and-harm-veto-contract`
  — exit 0 in 1.906915 seconds; all four focused tests passed and stderr was empty.
- A synthetic family with corrected positive endpoints on two distinct datasets passes the
  internal multi-dataset evidence gate. Adding a -0.02 Paderborn effect with a wholly negative
  interval vetoes the gate, even though two other datasets remain positive.
- Updated test SHA-256:
  `25ceb3985623ea5635db3d6f29264c59fdd26992096bebc49261e4cfeb4f2539`;
  stdout SHA-256:
  `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830`.
- Recorded source fingerprint:
  `57bda9ecce13bafb35abde89b1fa11e8ceda6cb83b2b1a7c8d0a7b3bba529c1e` over 239 files.
- Paderborn archives remained unopened.

## EXP-350 — pre-outcome statistical-contract full quality gate

- Status: complete implementation integrity gate; no new performance outcome was inspected.
- Date: 2026-08-18.
- Formal lint:
  `EXP-350-LINT__20260818T084424.422950Z__pre-outcome-statistical-contract-full-lint` — exit 0;
  stdout SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal regression:
  `EXP-350-TEST__20260818T084430.321572Z__pre-outcome-statistical-contract-full-regression` —
  exit 0 in 45.122487 seconds; all 191 collected tests passed. The sole warning remains the
  documented scikit-learn 1.9 SVC probability deprecation. Stdout SHA-256:
  `83ec5c0c9c4a0f44cafea17c5ce71e32b7de9f1f263a7a9dbe5a82999384cd9d`.
- Both formal runs used source fingerprint
  `de068f74d239b8e76630c38f6f76123c092e2270679cf213da5169b93a432aad` over 239 files.
- Paderborn archive contents remained unopened.

## EXP-351 — retained DG-validator coverage failure

- Status: failed as designed by the 75% hard gate; retained rather than hidden.
- Date: 2026-08-18.
- Run:
  `EXP-351-COVERAGE__20260818T084642.588835Z__post-dg-validator-full-coverage-gate` — exit 1.
- All 191 tests passed, but aggregate line coverage fell to 74.04% after adding the large DG
  artifact validator. The validator itself was only 31% covered, so the prior 76.90% project
  result could no longer support the current tree.
- Failure-report SHA-256:
  `6bc0b8fadfb931754f9f63d9d4bb53d771c6943ce956fd368b8b48f8e3a0440b`.
- Remediation rule: exercise a complete artifact-validation success path; do not omit the new
  module or lower the threshold.

## EXP-352 — end-to-end DG-validator coverage recovery

- Status: complete; the unchanged 75% hard gate is restored.
- Date: 2026-08-18.
- Run:
  `EXP-352-COVERAGE__20260818T085020.423837Z__dg-validator-end-to-end-coverage-recovery` — exit 0
  in 83.145465 seconds.
- All 192 tests passed. Aggregate coverage reached 77.08% over 5,039 statements; the DG artifact
  validator rose from 31% to 78% coverage.
- The added end-to-end fixture constructs and validates a coherent eight-method package with 88
  candidate summaries, 352 tuning traces, 16 recomputed outer choices, 80 final model traces, 160
  paired predictions, exact artifact hashes, normalized softmax probabilities and unit-norm
  representations. No production module was excluded from coverage to obtain the recovery.
- Test SHA-256:
  `25e43d5ed7023f717f0bff480119aa797566771f9dd89a4371c5ed17f9d05288`;
  stdout/coverage SHA-256:
  `eda17fecec8d83252681f3f08a5e174f6161ee56ebb8999ba4978c4f666f0a61`.
- Recorded source fingerprint:
  `b70348c6c207b6fc31265edfa7ef33b14827e7564bafece80b1e544394b6e773` over 239 files.
- Paderborn archives remained unopened.

## EXP-353 — balanced D2 pair-topology equivalence

- Status: complete synthetic contract validation; no D2 signal or model outcome was accessed.
- Date: 2026-08-18.
- Run:
  `EXP-353-D2-PAIR-EQUIVALENCE__20260818T085948.418189Z__balanced-d2-pair-topology-equivalence`
  — exit 0 in 8.762842 seconds; all four focused partition tests passed and stderr was empty.
- The new test constructs balanced synthetic intervention blocks with one row per fault class and
  compares the D2 nuisance/fault pair rules with the generic D0/D1 all-pairs constructor as
  undirected multisets. Multiplicity is retained, so duplicate or omitted pairs cannot pass merely
  because the unique pair sets agree.
- The first assertion draft compared oriented arrays and failed because equivalent nuisance pairs
  could reverse their left/right order under lexical setting sorting. The corrected scientific
  contract compares undirected pair multiplicity; the failure was not hidden by changing the pair
  implementation.
- Test SHA-256:
  `a65647e3127ced33f0f28239aee051d2565f38c4eda25e517d3d37600f3d8a5d`;
  stdout SHA-256:
  `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830`.
- Recorded source fingerprint:
  `17c28c2e681b6bae7e5b76573577ca33ac8469d20ada45d33cee31c8c6226f34` over 239 files.
- Paderborn archive contents remained unopened.

## EXP-354 — post-equivalence and baseline-provenance quality gate

- Status: complete implementation and paper-integrity gate; not a model-performance result.
- Date: 2026-08-18.
- Formal lint:
  `EXP-354-LINT__20260818T090126.467770Z__post-pair-literature-full-lint` — exit 0;
  stdout SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal regression and coverage:
  `EXP-354-COVERAGE__20260818T090133.027063Z__post-pair-literature-full-coverage` — exit 0 in
  104.992934 seconds; all 193 collected tests passed and aggregate line coverage remained 77.08%
  over 5,039 statements, above the unchanged 75% hard gate.
- The paper-package tests confirm that every Markdown citation, including all frozen neural
  comparators, has a unique BibTeX entry. The related-work text explicitly distinguishes original
  target-access DANN/Deep-CORAL protocols from SmartValve's source-only adaptations and discloses
  the LISA, MatchDG and CCDG implementation boundaries.
- Related-work/BibTeX/search-log SHA-256 values are
  `e50a3e15e42c8b1f2d45a7d4dbcf16e757da281f15c4b766b847840fac51a565`,
  `442d7d2c42d864301605d03b7f6c880cf2f8f55c81576b2d2111fb1ee267e21b` and
  `e8458a1585490e276b9291140eca16e7990750ae0c447bab184626e6322c0bc0`.
- Coverage stdout SHA-256:
  `5a2ff21a00b36122ce618d600259bed6572865752e248812904e5abb9061efb8`.
- Both formal runs used source fingerprint
  `4c59a74548a4178ba682783296890928d9e8f6f079a069a362eec33db425ee9c` over 239 files.
- The sole warning remains the documented scikit-learn 1.9 SVC probability deprecation.
- Paderborn archive contents remained unopened.

## EXP-355/356 — prospective D2 final-seal contract and quality gate

- Status: complete pre-outcome implementation contract; the actual final seal is intentionally not
  generated because EXP-340, source-selective, bootstrap and ablation hashes remain pending.
- Date: 2026-08-18.
- Formal seal lint:
  `EXP-355-SEAL-LINT__20260818T091747.624968Z__prospective-seal-contract-lint` — exit 0;
  stdout SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal focused tests:
  `EXP-355-SEAL-TEST__20260818T091747.454457Z__prospective-seal-contract-tests` — exit 0; all
  four tests passed and stderr was empty; stdout SHA-256
  `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830`.
- The builder binds 25 distinct required evidence roles by project-relative path, byte count and
  SHA-256; all nine method configurations; seeds 11/23/37/53/71; the exact six-test Holm family;
  frozen Paderborn and source-selective protocols; and a deterministic execution-source tree. It
  rejects digest drift, path reuse, missing roles, draft protocols, altered pre-outcome flags and an
  incomplete official archive inventory.
- The output authorizes only the protocol-governed single-MAT key/shape/dtype probe. It records that
  bulk extraction requires a successful probe and that target-outcome-guided reselection is
  forbidden.
- A read-only call against the real lock JSON confirmed exactly 32 official archive names,
  5,357,708,539 declared bytes and `archive_contents_opened=false`; it did not list, extract or read
  any archive member.
- Implementation/test SHA-256 values are
  `e4e423e77e51800924b983c5a33832a766df44862d762eaeffa5f1866b1429c8` and
  `6eed802670f39696eec819f62736a8a98c25deed4e53e0c9185965daa33e9ea3`.
- Full gate:
  `EXP-356-COVERAGE__20260818T091756.215569Z__prospective-seal-full-coverage-gate` — exit 0 in
  75.011547 seconds. All 197 tests passed; aggregate coverage was 77.26% over 5,197 statements and
  the new seal module reached 83%, above the unchanged 75% project threshold. Stdout SHA-256:
  `879fed9a8e5aed9e1dc5811e2218dccf84385ca4f9d57a47baf33d1fb74e2424`.
- An earlier ad hoc module-only coverage invocation hit NumPy's double-import guard during test
  collection. The canonical full-project coverage command above passed without omitting the module;
  no threshold or source set was changed in response.
- EXP-356 source fingerprint:
  `aae34823f441b9b65d2f9d047c4496a21048801ae55e0aadfbfe38a22f9666d8` over 241 files.
- Paderborn archive contents remained unopened.

## EXP-357/358 — value-blind single-MAT structure-probe contract

- Status: complete synthetic access-boundary validation; no Paderborn archive member was opened.
- Date: 2026-08-18.
- Formal lint:
  `EXP-357-PROBE-LINT__20260818T092432.504931Z__value-blind-mat-structure-probe-lint` — exit 0;
  stdout SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal focused tests:
  `EXP-357-PROBE-TEST__20260818T092432.511787Z__value-blind-mat-structure-probe-tests` — exit 0;
  all five tests passed; stdout SHA-256
  `4d2df7a96ce4a667da3ccf295f2d16c728a65ed0e861a3baa919f7bb469b02b5`.
- The initial structure path is now independent of `load_main_channels`. It emits only the canonical
  filename/root key, semantic channel names and paths, stored/squeezed shapes, original dtypes and
  sample counts. It explicitly records that the MAT reader loaded arrays but no value-dependent
  validation was performed and no values or statistics were emitted.
- A synthetic MAT with a NaN in a main channel passes the structure probe, while the full parser
  rejects the same file as non-finite. This is an executable separation between the one-file
  nesting probe and later numerical extraction.
- Parser/test SHA-256 values are
  `6581607f41ead0a769b80ee42fb5e71d41f205eba830ff1b2078299d1839b424` and
  `5320eaa03b0c57ec7021157bd0b023bed9086a29bc18d936c83a48f7a3c893ce`.
- Full gate:
  `EXP-358-COVERAGE__20260818T092440.758692Z__value-blind-probe-full-coverage-gate` — exit 0 in
  76.005008 seconds. All 198 tests passed; aggregate coverage was 77.29% over 5,218 statements and
  the Paderborn MAT module reached 84%. Stdout SHA-256:
  `68c1e191e9c9c3508ef267fc79e7d2120b8d203567a4635549092625ec407941`.
- EXP-358 source fingerprint:
  `163e570e9a37874f87e8f1c6198e6b0fffe0d2b77e5d09fe5ec46e3ec3be389c` over 241 files.
- Paderborn archive contents remained unopened.

## EXP-359–362 — frozen local RAR reader and isolated upstream-fixture validation

- Status: complete toolchain-readiness evidence only; no Paderborn archive path was supplied to
  the reader and no Paderborn member was listed, extracted or opened.
- Date: 2026-08-18.
- Two failed installation attempts are retained. `EXP-359-UNRAR` failed because `apt-get
  download` percent-encoded the Debian epoch in the filename; stderr SHA-256
  `462c1edb0380e98f234451bc627f177736f5389971072fc8dc1cbb18d3f391d3`.
  `EXP-359B-UNRAR` fixed that assumption but failed because the package installs
  `usr/bin/unrar-nonfree`, not `usr/bin/unrar`; stderr SHA-256
  `20db3efbcec2fc45e5282aa25a0aa5eeb357ebfce728593d4e2a231235823bde`.
  Neither failure received an archive path.
- The corrected run
  `EXP-359C-UNRAR__20260818T093144.494065Z__frozen-local-rar-toolchain-package-path` completed in
  0.443542 seconds. It hash-locked Ubuntu noble multiverse package `unrar=1:7.0.7-1build1`
  (177,964 bytes, SHA-256
  `3d05dd213babf0b8b9082a9a7d8663d35d85449b95b8593a4acb52598759e9a6`) and its local
  `unrar-nonfree` binary (376,144 bytes, SHA-256
  `c02de05961b3d6f2a6309b4c40faaaad7891b1a44acdf0f57b882cf2b3612c26`). The binary reported
  `UNRAR 7.00`; toolchain-manifest/stdout SHA-256:
  `cf9996a90ab1ea661c7d45638296ce4b903d895d333a0eab463f317987076ac9`.
- The executable validator pins the official libarchive fixture
  `libarchive/test/test_read_format_rar.rar.uu` to upstream commit
  `34c4a536a88d5114cfab7ca9bff48c0d235fd53a`. The uuencoded input is 505 bytes with SHA-256
  `d1e75b4120995bce82fc4e72ebf8b80d18ea69fa34ac62de383b8393f92afa09`; decoding must yield
  a 336-byte RAR with SHA-256
  `d421b86f6290aefad61b2a36737253b2b30fe27c156bd95abfc230f24fe0307e`.
- Formal validator lint and five focused tests passed in `EXP-360-RAR-LINT` and
  `EXP-360-RAR-TEST`; stdout SHA-256 values are
  `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` and
  `4d2df7a96ce4a667da3ccf295f2d16c728a65ed0e861a3baa919f7bb469b02b5`.
- The isolated execution
  `EXP-361-RAR-FIXTURE__20260818T093849.329890Z__frozen-unrar-non-paderborn-fixture-validation`
  passed CRC testing and extraction. The exact five-entry topology contains two 20-byte regular
  files, two directories and one contained `testlink -> test.txt` symbolic link. Both file
  payloads have SHA-256
  `5a5f16e01faf8adf92eb4499a2d3e93010c4b41dbb7f698f4a8466d9f58e6dd2`; unexpected entries,
  changed types, changed payloads and escaping links are rejected. Validation artifact/stdout
  SHA-256:
  `b97e0b95c2219c7b2ae38b14a784c9bea215f35232ddcd31e87087041afef0ff`.
- Installer, validator and validator-test SHA-256 values are
  `25ea0c8c04512a6a06fd7a621c3b5ceb3e40e63158ccebbace89e81872e1bb0c`,
  `de7d4127b1053069eb4e18de8cdb9cd3c2c0a4b808a19bf6a771b7d3f43a88bc` and
  `3c2c3e8b2fb432aa25d8bc77ee5daf29e4542f47d0485372a62c87ea12319170`.
- Full-tree `EXP-362-LINT` passed. `EXP-362-COVERAGE` passed all 203 tests in 75.83493 seconds;
  aggregate coverage was 76.56% over 5,371 statements with the unchanged 75% hard gate and no new
  module omitted. Lint and coverage stdout SHA-256 values are
  `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18` and
  `590c7a0e2cbaeeaa8143fc87b6833edbf2ae322f8dc3e638fbf5c13f9697b15a`.
- EXP-360–362 used source fingerprint
  `d4ae70fce737dda0f5a30bd077e65da9b9d4989d44cb3f9b942fd7a616333bf5` over 244 files.
- This proves only that the pinned local reader can faithfully handle a known RAR fixture. It does
  not authorize D2 access; the prospective final seal and one-file structure-probe gate still
  control first access.

## EXP-343 — pre-freeze expanded research-pipeline quality gate

- Status: complete; implementation integrity only, not a performance result.
- Date: 2026-08-18.
- Added scope since EXP-341: paired stratified physical-block bootstrap with full draw retention;
  frozen same-architecture ERM/ratio-only/margin-only PIRL v0.2 ablation; quarantine-safe
  Paderborn model folds; and a semantic `Name`/`Data` MAT parser tested without D2 access.
- Formal lint:
  `EXP-343-LINT__20260818T080858.037256Z__pre-freeze-full-lint` — exit 0 in 0.021209 seconds;
  stdout SHA-256 `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal regression:
  `EXP-343-TEST__20260818T080905.358233Z__pre-freeze-full-regression` — exit 0 in
  43.49264 seconds; all 176 collected tests passed. The sole warning is the previously documented
  scikit-learn 1.9 SVC probability deprecation. Stdout SHA-256:
  `b2d8153b6c648d9f6685988efdb523db43638847cdc9f9841b2414d5b59a0602`.
- Both formal runs used source fingerprint
  `1ddc37e413de82af7abc9a1de4adcc09ef88d1f94be861f42e26f5e73cd55857` over 231 files and git-diff
  SHA-256 `3a2bf57312efe90a39f455724066a3df2c5ea505f0588bd92fed7f7d14252ab2`.
- D2 seal state remained unchanged: no archive member listing, extraction, MAT load, signal
  feature computation or model outcome inspection occurred.

## EXP-330 — PIRL v0.2 source-only configuration selection

- Status: complete; both prospectively frozen development gates passed, so the candidate advances
  to the strong-baseline stage. This is not yet a statistical or D2 result.
- Date: 2026-08-18
- Run:
  `EXP-330-PIRL-RATIO-SELECT__20260818T062351.285563Z__source-only-nonsaturating-ratio-selection-and-ev`
  — exit 0 in 3,995.009148 seconds; stderr was empty.
- Protocol: `research/protocols/pirl_ratio_selection_v0.2.md`.
- Selection: 12 candidates, 13 D0/D1 outer folds and four source-only inner partitions produced
  624 fitted models. The common modal tie was resolved prospectively in favor of
  `r64_l1p0_m0p5`: representation 64, response-ratio weight 1.0, fault margin 0.5, hidden
  dimension 128, AdamW learning rate 0.001, weight decay 0.0001 and 300 epochs.
- Final development evaluation: five paired seeds over 3 Cranfield plus 10 UCI outer folds, 65
  models and 22,500 target prediction rows.
- Artifact validation: 156 candidate summaries, 13 outer selections, normalized dataset-specific
  probabilities and unit-norm 64-dimensional representations all passed. Maximum probability-sum
  error was `1.79e-7`; maximum representation-norm error was `2.38e-7`.
- Metrics SHA-256:
  `90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7`.
- Predictions SHA-256:
  `a32e0b8bfa7d8a522fa7e26bb26e2ac6f4113d32e5a3589f2b5c106e6f69ed22`.
- Tuning traces SHA-256:
  `a2eff73fc2b84de1c551bb022c75ca4d700defeacb034a0d830d9dbb2e35724f`.
- Final traces SHA-256:
  `d84aca64c937ffce91d608f8b0b2dd90eaf621785ef927404a895c84b465834d`.
- Run source fingerprint:
  `a3cba1a40072641389d2292f5dbed655a37891f6b507270e22a3a8ed13115d7f`
  over 198 files.

### Five-seed mean results and paired changes from hash-locked EXP-320 ERM

| Dataset | Mean-fold F1 | Δ mean F1 | Worst-fold F1 | Δ worst F1 | Brier | Δ Brier | Rep. ratio | Δ rep. ratio | Prob. ratio | Δ prob. ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Cranfield | 0.84005 | -0.00028 | 0.76093 | +0.01601 | 0.24055 | -0.00606 | 0.000666 | -0.000459 | 0.001554 | -0.001532 |
| UCI | 0.72435 | +0.04122 | 0.10433 | +0.00001 | 0.40020 | -0.03732 | 0.013227 | -0.007811 | 0.029514 | -0.000466 |

### Frozen gate decision and claim boundary

- Representation-response ratios are lower in mean on both D0 and D1.
- Probability-response ratios are lower in mean on both D0 and D1. The UCI mean reduction is
  small and the five paired seed differences range from -0.00520 to +0.00350; this heterogeneity
  cannot be hidden by the binary gate result.
- Efficacy passes because Cranfield worst-fold F1 changes by +0.01601 and UCI mean-fold F1 does not
  regress (it changes by +0.04122). UCI worst-fold F1 is essentially unchanged at +0.0000067.
- Automatic fields: mechanism_gate_passed=true, efficacy_gate_passed=true and
  advance_to_strong_baselines=true.
- Interpretation: v0.2 corrects the direction of the measured mechanism and is promising enough
  for a fair strong-baseline comparison. Five model seeds are not physical replicates, no paired
  block interval has yet been computed, and the result does not authorize opening Paderborn.

## EXP-313 — metadata-only Paderborn main-signal feature schema

- Status: complete candidate schema; final D2 seal is still pending.
- Date: 2026-08-18
- Run:
  `EXP-313-PADERBORN-FEATURE-SCHEMA__20260818T070817.812677Z__metadata-only-main-signal-feature-contract`
  — exit 0 in 4.408674 seconds.
- Expected inventory: 2,560 canonical MAT filenames overall and 2,320 in the pure-class cohort;
  filename parsing round-trips setting, bearing identity and measurement index and rejects
  noncanonical or unknown keys.
- Candidate primary signals: synchronous vibration, current phase U and current phase V, each
  exactly 256,000 samples (64 kHz for four seconds). Support channels such as speed, torque, force
  and temperature are excluded from classifier input.
- Candidate representation: the 24 D1 whole-trajectory statistics applied independently to the
  three main channels, giving 72 features and no segmented-window pseudo-replication.
- Validation: four synthetic-signal filename/shape/finiteness/schema tests passed; Ruff passed.
- Manifest SHA-256:
  `39237803a8a41e77981a0b98ce089d77d87fca2cca8a30f97fd692d54264ee3f`.
- Source fingerprint:
  `2d49254a05420b67bcd893add2c98ce5babdf99d1309997b67df85480130a683` over 215 files.
- Seal state: archive_contents_opened=false, signal_features_computed=false,
  model_outcomes_inspected=false.

## EXP-338 — outcome-blind neural-DG expected-topology manifest

- Status: complete prospective integrity manifest; contains no candidate score, target prediction
  or model-performance result.
- Date: 2026-08-18.
- Run:
  `EXP-338-DG-MANIFEST__20260818T083150.944218Z__outcome-blind-neural-dg-expected-topology`
  — exit 0 in 13.110739 seconds.
- EXP-340 had begun producing progress-only inner-fit events, but had emitted neither candidate
  metrics nor any final target fit when this manifest was generated. The manifest is derived only
  from the already frozen grids, folds, inner partitions, methods, seeds and target provenance;
  it cannot alter the selection rule or outcome.
- The UCI feature input was hash-locked at
  `4359ce099e421cc9e55c65115d39f4a4c0463255f72f834a49d802fa6a038516`.
- Exact expected counts and canonical key-set hashes are: 572 candidate rows
  (`86e0ff6730d6e62cdcf7d6feaaf966263268dadafd12cfc3f6a3feeb9bf1a7ad`), 2,288 tuning models
  (`22e2c3fc6fb804879d842b69175e6d5ecf4f37c7e6183c8559fc8777988a67c6`), 104 outer choices
  (`503d5fd222730bb309522e3d54a476b500d502aa4ede1b704b514dbd5d5b7f77`), 520 final models
  (`d6c2d866bc265f8f7639b7de097ed153fdefa44255101a9528d1a13c29380c2d`) and 180,000 target
  predictions (`1806655e869f850a3d6173f36ffb1aa4fbc603656df98412d44fadb452ab238e`).
- The 4,500 method/seed-independent physical target rows have provenance hash
  `28199a35952c4baf028bd6680dc8092675b2b1f254a372c1883e35ab00826810`.
- Manifest SHA-256:
  `79e68f95e9a5d88921fa79c1d50f34aa84db5c156a5e6c5ba516520c97faa862`;
  stdout SHA-256:
  `59b886798680a58616e48ee8e08ce95d4f7b10d31d0700be18d87b7ea723d0c2`.
- Generator/test SHA-256 values are
  `132882dd8e679b5720f0284b45039a7f26101a78ebed5eeb2d78dee08f9ee364` and
  `0b5e2fa0d4d5bd229d4050ee74e15f0466ba3d79e6d12b829e28844992003236`;
  three focused tests passed before the formal run.
- Recorded source fingerprint:
  `3d84fa8558cf1ab18667f5ba92dc7ced4a27eaeb7024a142cc1f8307e258b33d` over 237 files.
- Paderborn archive contents remained unopened.

## EXP-339 — all-method real-fold CUDA preflight

- Status: complete; execution-path check only, not a performance experiment.
- Date: 2026-08-18
- Run:
  `EXP-339-DG-CUDA-PREFLIGHT__20260818T072907.583430Z__all-method-real-fold-cuda-preflight`
  — exit 0 in 9.45701 seconds; stderr was empty.
- Every frozen method path—ERM, CORAL, VREx, GroupDRO, DANN, LISA, MatchDG and CCDG—ran for
  three epochs on one real Cranfield source fold using CUDA.
- All methods emitted finite logits, normalized probabilities and finite representations with the
  expected shapes. Maximum probability-sum error was `1.19e-7`.
- Peak allocated CUDA memory across methods was 68,168,192 bytes, well inside the RTX 3080
  capacity. DANN also emitted a non-null discriminator-state hash; other methods did not.
- Preflight artifact SHA-256:
  `3f59ea4524760f28fcec98ab5cd089ed294493e9d9a2b5c5fff27d698c7c112e`.
- Source fingerprint:
  `0d093546de8e5447fca8c15dc5dd99c7b3a93acb9ba5bdf575ba7be2b57e780a`
  over 215 files.
- Paderborn archive contents remained unopened.
- Post-preflight quality gate used source fingerprint
  `2cf375756decb9855e2105ae7cdedeea90897c9d9c09ad9614335e79ab61b1f6` over 215 files:
  `EXP-339-LINT__20260818T072950.551092Z__pre-exp340-full-lint` passed, and
  `EXP-339-TEST__20260818T072951.422251Z__pre-exp340-full-regression` passed all 151 tests. The
  only warning is the already documented scikit-learn 1.9 SVC probability deprecation.

## EXP-341 — source-OOF selective pipeline pre-EXP-340 quality gate

- Status: historical implementation gate; the later formal EXP-342 run and validation are recorded
  below.
- Date: 2026-08-18.
- Scope: PIRL versus identical-backbone tuned ERM, with strictly source-OOF rejector selection,
  source-selected 50%/70%/90% coverage thresholds, a 25% minimum source-environment coverage
  floor, seven individual-network scores and five fixed-ensemble scores.
- Risk-envelope beta candidates are 0, 0.1, 0.25, 0.5 and 1.0; selection minimizes
  worst-source-environment AURC, then pooled source AURC, then beta. Target rows are structurally
  absent from the selector.
- Every future final refit must reproduce the locked model-state hash exactly and its target
  probabilities within absolute tolerance `2e-6`. OOF/target row topology, normalized
  probabilities, finite scores and row-level physical block identities are mandatory gates.
- The target-label permutation safeguard, target zero-coverage disclosure, error-detection
  ranking metrics, per-environment/per-class reporting, and fixed five-seed Jensen-Shannon
  disagreement path are tested.
- Formal lint:
  `EXP-341-LINT__20260818T074922.514745Z__selective-pipeline-full-lint` — exit 0 in
  0.013596 seconds; stdout SHA-256
  `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Formal full regression:
  `EXP-341-TEST__20260818T074929.551530Z__selective-pipeline-full-regression` — exit 0 in
  32.508976 seconds; all 161 collected tests passed. The only warning remains the documented
  scikit-learn 1.9 SVC probability deprecation. Stdout SHA-256:
  `51f7bcfeaa0fbd945812e758ab4aff31dabea7e9ba0d5f555b3f54b5c5f15fb1`.
- Both quality runs used source fingerprint
  `e2a5de6089cb449dac3d4e3f123ff6e5608c5cb669eb20bae86779a3a78215bd` over 220 files and git-diff
  SHA-256 `3a2bf57312efe90a39f455724066a3df2c5ea505f0588bd92fed7f7d14252ab2`.
- Protocol state at this historical gate was draft. It was subsequently frozen as
  `research/protocols/source_selective_evaluation_v0.1.md` with SHA-256
  `67288f53f1e68e36901216de3e3b6fc17a50e55f6882dd567b4498930ffc6ae6`.
  Paderborn archive contents remained unopened.

## EXP-314 — metadata-only quarantine-safe Paderborn model folds

- Status: complete synthetic schema validation; not D2 execution authorization.
- Date: 2026-08-18.
- Run:
  `EXP-314-PADERBORN-DOMAIN__20260818T080441.023133Z__metadata-only-quarantine-safe-model-folds`
  — exit 0 in 5.834995 seconds.
- The 2,320-row pure-class metadata inventory plus 72 deterministic synthetic feature columns was
  converted into all 24 prospective model folds. No archive member or signal value was read.
- Each trainer view contains source plus target only; the two cross-arm quarantine partitions are
  physically absent from its feature, label, environment and block arrays. Full-index source,
  target and quarantine provenance remains attached for audit.
- Folds 0–4 expose 1,440 source plus 100 target rows and exclude 780 quarantine rows. Fold 5
  exposes 1,500 source plus 80 target rows and excludes 740. Every source view has three settings,
  every target view the single held setting, source coordinates are local, and all pair indices
  remain source-only.
- All 2,320 measurements are target exactly once across the 24 folds; minimum and maximum target
  count are both one. The focused Paderborn domain/partition/split/feature suite passed all 14
  tests and Ruff passed.
- Manifest SHA-256:
  `35cbbdedd23ba688a051b2d453e75f33ea5966481966b3780c4d9194db989422` (13,858 bytes).
- Source fingerprint:
  `80c50197831b81a521eae1a081b63c7f1233afe227cc898f85fd8cb759f10086` over 229 files.
- Seal state: archive_contents_opened=false, signal_features_computed=false,
  model_outcomes_inspected=false.

## EXP-340 — frozen source-only neural-DG selection and independent validation

- Status: complete and passed the pre-run outcome-blind EXP-338 manifest.
- Date: 2026-08-18.
- Main run:
  `EXP-340-DG-SELECT__20260818T073103.881960Z__frozen-source-only-neural-dg-selection`
  — exit 0 in 10,310.096401 seconds.
- Validator:
  `EXP-340-VALIDATE__20260818T101131.084837Z__manifest-locked-neural-dg-artifact-validation`
  — exit 0 in 4.726280 seconds; validation SHA-256
  `f24815fac5af7fb1409a223670ebb96eace55f1f962b086689c48caf81bae031`.
- Exact validated topology: 572 candidate rows, 2,288 tuning fits, 104 outer choices, 520 final
  fits, 180,000 target predictions and 4,500 method-independent physical target rows. Maximum
  probability-sum, softmax and representation-norm errors were respectively `1.378e-7`,
  `1.256e-7` and `1.300e-7`.
- Metrics SHA-256:
  `7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b`;
  predictions SHA-256:
  `7691980fbd47a209d79629c65bb3490ffc866645eec48f4c07509535fdfbe2d6`.
- Selected configurations: ERM `erm_r64`, CORAL `coral_r64_w1p0`, VREx `vrex_r32_w0p1`,
  GroupDRO `groupdro_r64_q1p0`, DANN `dann_r64_w1p0`, LISA `lisa_r64_w1p0`, MatchDG
  `matchdg_r64_w1p0`, and CCDG `ccdg_r64_w1p0`.
- Best mean-fold macro F1 among these baselines was CORAL `0.840899` on Cranfield and MatchDG
  `0.732869` on UCI. The frozen PIRL result was `0.840046` and `0.724352`, respectively; PIRL is
  competitive but is not the best closed-set method on either dataset.
- Paderborn archive contents remained unopened.

## EXP-341A/B/C and EXP-363 — selective pre-run integrity gates

- The first formal EXP-341 preflight failed and is retained. It exposed a real interface mismatch:
  code used `environments` while `SourceOnlyFold` defines `environment_ids`. No model outcome was
  produced.
- After fixing the interface and its test fixture, EXP-341B passed with artifact SHA-256
  `8227754e6548c61f55119170f42624cb16a12eac049facc6c2e3b85bfbf188a6`: 130 locked
  method/seed/fold groups, 45,000 target rows and exact reference topology.
- EXP-341C generated the outcome-blind expected manifest before selective refitting. Manifest
  SHA-256 is `75af0e966a342b5dbdf245ba78fd34d67da393f6793a6ab75d9d6b61018a45de`.
  It freezes 104,400 source-OOF rows, 45,000 target rows, 20,880 source-ensemble rows, 9,000
  target-ensemble rows, 3,120 policies, 156 beta choices, 1,080,000 decisions, 650 training fits
  and 130 reference crosschecks.
- The first full coverage gate EXP-363 failed at 73.42% despite all 236 tests passing. The threshold
  was not lowered. After adding meaningful Paderborn orchestration and integrity tests,
  EXP-363B passed 239 tests at 75.23% coverage over 6,359 statements; full Ruff also passed.

## EXP-342 — frozen source-OOF selective evaluation and validator

- Status: complete and independently validated against EXP-341C.
- Main run:
  `EXP-342-SELECTIVE__20260818T102548.578731Z__frozen-source-oof-selective-refit`
  — exit 0 in 2,535.083739 seconds.
- Validator:
  `EXP-342-VALIDATE__20260818T110500.835779Z__manifest-locked-selective-artifact-validation`
  — exit 0 in 12.286525 seconds. Validation SHA-256:
  `e7ee4d41688d5195478b1c609eaf684156f45c3a3aa7b9c944a13b97bdd013d5`.
- Metrics SHA-256:
  `4caa1e4bb2a07b98be6af2752a0b310f751b8bd0f7fda34b03578ebfbd9983e6`;
  target-prediction SHA-256:
  `43b8522d57ba3a814158be06b7d3b478b6ee3174639e78ed3fc364a772cbeebf`;
  decision SHA-256:
  `e49b97f1f63c3d754d1f970a17ba0f9b797cc2841d65e4ef3117b0d54aa99649`.
- All 130 final model hashes reproduced the frozen references exactly; maximum reference
  probability difference was zero and maximum probability-sum error was `1.3784e-7`.
- At the individual-network risk envelope with nominal 50% source coverage, mean target selective
  risk was ERM/PIRL `0.01350/0.01217` on Cranfield and `0.14338/0.14057` on UCI. These unweighted
  fold means are descriptive only; physical-block inference is EXP-344.
- Several target groups had zero minimum environment coverage, and one UCI PIRL group had
  selective risk one. The experiment does not support a generic safety or universal reliability
  claim.
- Paderborn archive contents remained unopened.

## EXP-344 — frozen paired physical-block bootstrap

- Status: complete after the frozen v0.1 protocol, hash authorization, full Ruff and all 241 tests
  passed. Run:
  `EXP-344-BOOTSTRAP__20260818T111000.613209Z__frozen-selective-physical-block-bootstrap`
  — exit 0 in 21.636474 seconds.
- Protocol SHA-256:
  `90415d2b9be45560d61e61e090164c09890f53a6e1f3a33ba2255597338501bb`.
  Metrics SHA-256:
  `cfcaf5a16e8d30a4b52a0a6bcb6237fe3dff8b1fe416d5e8e8ac1dafe503e246`.
- The full 2,000-replicate metric tensor has 8,000 rows, SHA-256
  `078052d19f95bab0f155b43905f971fa48908ebebe35ff50ff6232bae81cb55a`; the 840,000-row
  stratified draw plan has SHA-256
  `ea25eb43b59a45a551eb08e8912708bb1cc8b114ce1ae41d34b484bc1e4ac07f`.
- Cranfield PIRL-minus-ERM worst-fold macro F1 was `0.007785`, 95% percentile CI
  `[-0.016053, 0.031119]`; ERM-minus-PIRL 50%-policy selective risk was `-0.000174`, CI
  `[-0.007159, 0.006241]`. Neither meets the frozen practical/inferential rule.
- UCI PIRL-minus-ERM worst-fold macro F1 was `0.000860`, CI `[0, 0.002473]`, below the 0.01
  practical threshold. UCI ERM-minus-PIRL selective risk was `0.044069`, CI
  `[0.038991, 0.049302]`, two-sided add-one bootstrap tail diagnostic `0.0009995`; this is the only
  D0/D1 endpoint that meets both the 0.01 practical threshold and a positive percentile interval.
- Holm adjustment remains deferred until the frozen D2 endpoints complete the six-test family.

## EXP-345/347 — outcome-blind component ablation and validation

- EXP-345 generated a pre-run manifest with SHA-256
  `6480cabdfdf65057422d0eb052688ca14dec07df31fce98547dad3ff8f9f291a`, exactly 195 model
  keys (`a4dfcc49b0fe7ed247f0fd04755cac3217ca88e15813565c8f3632b185b95694`) and 67,500
  prediction keys (`8fa0f1813781933909da10f974db9262ff754a089065cdfc22277fb808fb4411`).
- Full-project Ruff and all 245 tests passed before fitting. EXP-347 then completed all 195 frozen
  models in 1,353.875732 seconds:
  `EXP-347-RATIO-ABLATION__20260818T111725.704616Z__frozen-component-attribution`.
- Independent validator
  `EXP-347-VALIDATE__20260818T113826.737517Z__manifest-locked-ratio-ablation-artifact-validati`
  passed in 3.587679 seconds. Validation SHA-256:
  `14b0eeeaf8f23f9b35c2721304252e55f242165f76f5491f380315cbfc3b9a30`;
  metrics SHA-256:
  `b7edab2bf7d1703008c93805af90627cba4a63478c468101e183cf7178d2e8a7`.
- All 65 ratio-only model states are byte-identical to the locked full model, and all 65
  margin-only states are byte-identical to same-architecture ERM. Consequently every reported
  full-versus-ratio-only and margin-only-versus-ERM metric is exactly equal.
- Attribution result: the anti-collapse margin had no observable optimization effect in D0/D1;
  all observed PIRL differences arise from the nuisance/fault response-ratio term. The frozen full
  configuration is retained for D2, but the paper must not claim independent margin efficacy.
- Paderborn archive contents remained unopened throughout.

## EXP-374/378/400/403 — sealed D2 access and complete structure audit

- Status: complete with one retained structural failure; no outcome-dependent exclusion.
- EXP-374 created the final 31-role pre-D2 prospective seal in 0.652840 seconds. Seal SHA-256:
  `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`.
- EXP-378 repeated the amendment-gated probe of the same permitted MAT structure in 0.959435
  seconds.
- EXP-400 inventoried all 2,560 canonical MAT members in 176.173127 seconds. Exactly one file was
  unreadable by the pinned parser: `N15_M01_F10_KA08_2.mat`, archive identity KA08, original
  manifest row 1001.
- EXP-403 reproduced and isolated that root-level failure in 1.950112 seconds. The exclusion is
  structural, not based on a feature, label outcome, or model score. No imputation or substitute
  measurement was authorized.
- The retained cohort contains 2,559 total measurements: 2,319 primary single-condition rows and
  240 compound-condition rows.

## EXP-404–407 — final Paderborn v0.5 feature artifact

- Status: complete and independently validated.
- EXP-404 Ruff passed in 0.009302 seconds. EXP-405 completed the targeted v0.5 tests in 18.561999
  seconds.
- EXP-406 generated one 72-feature row per retained four-second measurement from vibration and two
  current channels in 501.039894 seconds. No segmented windows were promoted to independent rows.
- Feature-contract SHA-256:
  `439582a767b41cbba3679902174a5e81cf8fe764a8d276fba98b62bc81480149`.
- Metrics SHA-256:
  `4425947919dc8e6730c7cf83dc8e33a8b58a64e07d777cd14527806667663de2`.
- Feature-matrix SHA-256:
  `9d9a6d0d48cc590ec842006a779454d76ad299072978e0d0b094b138ddf56d29`.
- EXP-407 independently validated schema, coordinates, counts, finiteness, and provenance in
  4.842476 seconds. Validation SHA-256:
  `4bda1dd3e1588b1762f93472aa8601cd90a60690ba9c2449916c80746a055326`.

## EXP-408–416 — structural-exclusion amendment and final execution seal

- Status: complete; model outcomes remained unopened until EXP-417.
- EXP-408 and EXP-409 regenerated the split and fold manifests for the exact 2,319-row primary
  cohort in 3.275268 and 4.850040 seconds.
- EXP-410 froze the base expected topology in 37.165987 seconds; manifest SHA-256
  `db0c1e417892e72b2f0065cfcec1611787b7a2d2f3b8b1c05a2b2ed2aed7c04e`.
- EXP-411 froze the selective expected topology in 22.026155 seconds; manifest SHA-256
  `aa73cf687ec7ba3a0a88b1c4e4a57c176d62f1c8cb77a6627073c6fbd08c0a43`.
- EXP-412 full Ruff passed in 0.021605 seconds.
- EXP-413 ran all tests but achieved only 74.60% coverage, below the unchanged 75% authorization
  threshold. It is recorded as a failed quality criterion even though its process metadata did not
  clearly encode that semantic failure.
- After adding an authorization-path test rather than lowering the threshold, EXP-414 passed in
  303.797572 seconds at exactly 75.00% coverage. EXP-415 final Ruff passed in 0.012112 seconds.
- EXP-416 sealed all post-feature/pre-model code, protocols, inputs, expected manifests, and
  environment roles in 0.436261 seconds. Execution-seal SHA-256:
  `e87ceabf74aa86e41a616fe3f796738d122542412b71ae75aade07644679560b`.

## EXP-417/418/418B — one-shot Paderborn nine-method evaluation

- Status: model run complete; original validator failed on a coordinate-system mismatch; the
  disclosed coordinate reconciliation passed without changing outputs.
- EXP-417 completed in 2,679.226456 seconds: nine methods × five seeds × 24 folds = 1,080 final
  models, 104,355 primary target predictions, and 259,200 compound predictions.
- Metrics SHA-256:
  `167d2e04bede2dfbd5b37eb6c63bbef8b51b6c3c58d8f68624fca3cf64fa1c95`.
- Primary prediction SHA-256:
  `5e3801e9df4636f180e85ccde060fade77422dfbcb65d5699bf7a93a49d9b400`.
- Compound prediction SHA-256:
  `9ed1414d7d5c2482f59a407e55956a94c145f2e0dd7871c177e38194fd99c6a3`.

### Five-seed Paderborn descriptive results

| Method | Pooled macro F1 | Minimum-setting macro F1 | Minimum identity-setting F1 | Brier | ECE |
|---|---:|---:|---:|---:|---:|
| PIRL | 0.382868 | 0.318539 | 0.068664 | 0.944178 | 0.415825 |
| ERM | 0.369505 | 0.297618 | 0.032047 | 0.950419 | 0.438491 |
| MatchDG | 0.395157 | 0.2966 | 0.0668 | 0.9278 | 0.4074 |
| CCDG | 0.3737 | 0.308246 | 0.0313 | 0.9501 | 0.4346 |

- MatchDG, not PIRL, has the highest pooled macro F1. PIRL has the highest descriptive
  minimum-setting macro F1. Its five seed-wise differences from ERM range from -0.007323 to
  +0.057573.
- EXP-418 failed after 6.114353 seconds only because compound expected keys retained original
  archive row indices while the feature/evaluation path used compact post-exclusion indices. Every
  compound row differed by exactly +1 when mapped back to the original coordinate system because
  the sole exclusion precedes the compound cohort.
- Reconciliation protocol/source/specification SHA-256 values are respectively
  `72702a2d66e01dafe5a911d503364cc7b888f69d4f1cb118e675883d73f4cddd`,
  `9535cfadf5204759f94a345574fae56618d8b23902dc308644643bade8e9c4de`, and
  `39b13483e6a9bc7dfeccfb1895726971295106fbd88c1e68a94eed304391c7db`.
- EXP-418B passed in 24.003911 seconds. Validation SHA-256:
  `b14fcb57598ae3f4c7d03fba28c87f4ae2dc47f6a30dd8085d61a3bc0b80d6b3`.
  Maximum probability-sum error was `1.42e-7`; no prediction file was edited or regenerated.

## EXP-419/420/420B — sealed Paderborn source-OOF selective evaluation

- Status: complete; original validator exposed the same compound coordinate mismatch; the bounded
  reconciliation passed.
- EXP-419 completed 720 inner models in 1,680.133448 seconds. Metrics SHA-256:
  `234a9b3f3d2809be7d5f670dfb752248596d0d8c1171cc47434aa96ea92247aa`.
- Selection-decision SHA-256:
  `8b1ea27ff1317d2fc2bfc502fdffd8d5895dc27670208d0f104e4d0de32f92e7`.
- At nominal 50% source coverage, descriptive unweighted fold summaries were ERM/PIRL risk
  `0.614684/0.611661`, target coverage `0.708244/0.717568`, and effective accuracy
  `0.295410/0.278209`. ERM/PIRL had 0/3 zero-coverage target groups.
- EXP-420 failed in 5.991061 seconds on compound row indices and no outcome metric. Reconciliation
  source/addendum SHA-256 values are
  `b64118ce6bc8a3644b41d401949556765fe8d6b06eace00312f0a24e22027057` and
  `18eed62a32c5156a3d883909a6caf8a2ebe54010b8bb13eabc5d7bc8bf9816ba`.
- EXP-420B passed in 45.004359 seconds. Validation SHA-256:
  `7a57d075056778e39d0ff847c8a8944c97c65fa2bb90804558babae30ef3a75d`.
  Ensemble reconstruction maximum difference was zero, base projections matched exactly, and
  target rows remained unavailable to selection.

## EXP-421/421B — paired Paderborn bearing-identity bootstrap

- Status: reconciled frozen inference complete.
- EXP-421 failed in 1.760183 seconds before statistics because its unchanged pre-exclusion assertion
  required 2,320 rows.
- The reconciliation retained 29 truth-stratified bearing identities and the same paired 2,000-draw
  design. KA08 contributes its 79 observed rows; every other identity contributes 80. There is no
  imputation.
- Protocol/wrapper/specification SHA-256 values are
  `c1e01dcf46ef18aca241eb86b7fae2c28906a7b5cd3b45b4f5e540d362e98887`,
  `f1eb02f8af89f9b0e05aa77f9fb09c58d35fe369fc554f451aa9b07c32a15645`, and
  `9b1879e7cfbed63bb77c34d5896f03d9ca541bfa01e172925e5620161d60f547`.
- EXP-421B completed in 8.075501 seconds. Metrics SHA-256:
  `465cfe62da9b60c75484992b6b0d2b13cb97197f5e9b390955086160986b69f8`.
- The 4,000-row metric tensor SHA-256 is
  `00beae8fbb4493d3207a0794654e04aa2a71b742cd82324fd1707b898b2b9ce9`;
  the 58,000-row draw-plan SHA-256 is
  `7c114b3911c598185c9e87e73a69ea3d12b5cfa6f8e071da5e421a6a4a64527f`.
- Closed-set PIRL-minus-ERM minimum-setting macro F1: `+0.020921`, interval
  `[-0.045959, 0.081241]`, raw p `0.692654`; not confirmatory-positive.
- Selective ERM-minus-PIRL risk: `-0.031777`, interval `[-0.070919, 0.007151]`, raw p
  `0.097951`; not confirmatory-positive and not resolved material harm.

## EXP-422/422B — frozen six-test Holm family

- Status: final family complete after a version/count acceptance reconciliation.
- EXP-422 failed in 1.369200 seconds before Holm assembly because it rejected the reconciled
  bootstrap version string.
- Protocol/wrapper/specification SHA-256 values are
  `2f294ac79ca3736b2603a279676170fc0d28949bbe81c15a8be74f78fd0ecce3`,
  `a1e1af9f3816149b213778bf7ced4d7f34d22fed7fdb031da4be866839af1351`, and
  `89b50273e460942bd0dded3cb8f34b1c30c83b19e4de18d09a57298b8e4e9948`.
- EXP-422B completed in 1.403359 seconds. It accepted only bootstrap version 0.2 and count 2,319;
  the six family members, effects, raw p-values, and Holm implementation were unchanged.
- Metrics SHA-256:
  `0143b1e6703a1941f636001b298ce29837386258127068e715fe4ffe73854476`.
- Confirmatory-test table SHA-256:
  `cf874d47a905991d63e97d9f5571835180d7cdd0256a3042e8cae434cf4ee355`.
- Exactly one test is positive: UCI selective risk, Holm p
  `0.005997001499250375`. The other five are null under the frozen practical/interval/Holm rule.
- No endpoint meets the frozen material-harm rule.
- `datasets_with_confirmatory_improvement=["uci_hydraulic"]` and
  `internal_multi_dataset_evidence_gate_passed=false`.
- Final interpretation: the sealed evaluation rejects a broad multi-dataset PIRL-superiority claim.
  It supports a mixed-result prospective audit, not a top-tier algorithmic efficacy claim.

## EXP-423/423B/423C/423D/423E — final multi-rig manuscript artifacts

- EXP-423 is a retained failed run: pandas requested the optional `tabulate` package while writing
  Markdown. No scientific input or result was affected.
- EXP-423B replaced that optional dependency with a deterministic internal Markdown writer and
  completed. EXP-423C added publication-readable display precision while retaining full numeric
  CSV precision.
- EXP-423D made provenance paths project-relative but exposed that the legacy generator inventoried
  all pre-existing files, causing the two manifests to overlap.
- The legacy generator was bounded to its own fixed outputs. EXP-423E then regenerated both
  packages in one command with disjoint manifests and completed successfully.
- Final legacy manifest SHA-256 remains byte-identical to EXP-PAPER-002:
  `8647cbebaa00b6f616af28a2d0d2f846ae86d4d4d50905d12646a109cab619ed`.
- Final multi-rig manifest SHA-256:
  `bceeefe1a555e1997189dadc734c9a5e7dd770b72871c488ce254c490a1ec9a6`.
- Multi-rig generator SHA-256:
  `9bf93a52169eb7136a8c72fe7f38dec01a95e747bed83385e40d760a0a966f80`.
- Outputs are three tables in CSV/Markdown/LaTeX, one SVG forest plot, captions, and a portable
  manifest. The SVG was rendered to a 1,100 × 520 PNG and inspected for labels, intervals, zero
  line, ±0.01 thresholds, and the sole Holm-positive annotation; no clipping or overlap was found.
- Focused paper-package and artifact tests passed eight of eight after the two-manifest update.

## EXP-424/425 — final multi-rig quality gate

- Status: complete; implementation/reproduction gate passed at the exact coverage boundary. This
  does not change the failed scientific efficacy gate.
- Ruff run:
  `EXP-424-FINAL-MULTIRIG-LINT__20260818T165600.820930Z__final-multirig-paper-and-research-lint`
  — exit 0 in 0.010822 seconds; `All checks passed!` over `src`, `tests`, `dashboard`, and `scripts`.
- Ruff stdout SHA-256:
  `82b3e6a6c090a57601d22943bd23fca9218d1031dbe5a7b754092f9a156b4f18`.
- Full regression/coverage run:
  `EXP-425-FINAL-MULTIRIG-COVERAGE__20260818T165612.354515Z__final-multirig-full-regression-and-coverage`
  — exit 0 in 280.400890 seconds.
- All 269 collected tests passed; there were no skips and stderr was empty. The single warning is
  the already documented scikit-learn 1.9 deprecation of `SVC(probability=True)`.
- Coverage: 8,164 statements, 2,041 missing, exactly 75.00%; the unchanged 75% threshold passed but
  has no safety margin.
- Coverage stdout SHA-256:
  `ccc9d9e5cd9bcf71a24f9154c5af42f60032fdf35ffe74d5dde0f14f417d4c7a`.
- Both runs used source fingerprint
  `d248a7fe3ffd1c29f291c65a9d269257a0a74f95efb2b86db1d685b8bb116ee6` over 324 files and
  git-diff SHA-256
  `711428da4a312dcb5fb62ff215acbd0e593498bc2097fc4c088474a16aee43d0`.
- Final distinction: the code, artifact, and reproduction gates pass; the frozen multi-dataset
  PIRL efficacy gate remains failed. Neither result is allowed to overwrite the other.

## EXP-426 — final current-scope paper integrity

- Status: complete.
- Run:
  `EXP-426-FINAL-PAPER-INTEGRITY__20260818T170240.951132Z__final-current-scope-paper-package-integrity`
  — exit 0 in 0.644652 seconds.
- All eight focused tests passed: required current manuscript documents, BibTeX citation coverage,
  disjoint legacy/multi-rig manifest ownership, project-relative input provenance, locked input and
  output hashes, SVG parsing, exact six-test family size, single-positive count, and failed internal
  evidence gate.
- Stdout SHA-256:
  `06955fb47f16312e5d13266c774a2aa4648c46e423cbe6564a92e25b68e39131`.
- Source fingerprint before this append-only ledger interpretation:
  `b877a2583dfa83842c69845c3bb6949dc05f1fc8151a084601324d72a81615ab` over 324 files.

## EXP-430 — retrospective v0.3 failure and paired-scatter audit

- Status: complete; development-only and prohibited from confirmatory use.
- Run:
  `EXP-430-V03-FAILURE-AUDIT__20260818T173236.006825Z__retrospective-multirig-failure-and-paired-scatte`
  — exit 0 in 57.652831 seconds.
- Five inputs were hash-locked: EXP-330 PIRL predictions, EXP-340 neural predictions, EXP-417
  Paderborn predictions, EXP-110 UCI features, and EXP-406 Paderborn primary features.
- All 511 non-empty equal-weight subsets of nine methods were evaluated on each of D0/D1/D2.
  Best single cross-dataset mean minimum-fold macro F1: MatchDG `0.328445`. Best subset:
  MatchDG+PIRL `0.336756`. Simple averaging did not eliminate the tail failure.
- Every frozen neural method had UCI `cooler=100` as its worst fold with five-seed ensemble macro
  F1 `0.104299`. Paderborn worst folds remained identity/setting failures, often near zero.
- The fixed `ridge=1e-3`, `k=4` paired-scatter baseline produced pooled/minimum-fold macro F1 of
  `0.633637/0.471795` on Cranfield, `0.856507/0.282259` on UCI, and
  `0.417349/0.124661` on Paderborn. Follow-up probes showed material ridge sensitivity; no
  target-selected setting is promoted as frozen or confirmatory.
- Output SHA-256 values: failure summary
  `1874c3e4ffe2cfc1214b46b48e351159e494f58dbe0e2ec8d9705d59a8dd143f`;
  method/fold metrics
  `a35c96deeb59a376a9d7dcc2a4dfa5f6ff718c84a008cecbb97b6af1dbd2b47c`;
  subset grid
  `29b6f15dda1b2db6e90795da12bcc59ca491fb89ae3170212621efe52e1313d7`;
  paired-scatter probe
  `177628e0c8f62fc3bb2cc4421c9987bb3411111966904c08ec9fe28326a86601`;
  blend grid
  `98d2ad6ac8872e7646af2f292acaea2a2d30b8f5e0f7c74d654648c2845518c9`.

## EXP-431 — outcome-blind HUST D3 metadata inventory

- Status: complete metadata audit; candidate not sealed; signal access remains unauthorized.
- Run:
  `EXP-431-HUST-D3-METADATA__20260818T174037.770049Z__outcome-blind-hust-v3-d3-metadata-inventory`
  — exit 0 in 3.491463 seconds.
- Queried the official Mendeley v3 public metadata endpoints only. MAT files downloaded/opened:
  `0/0`; signal bytes read: `0`.
- Verified 99 unique MAT filenames totaling 671,364,479 bytes and the official CC BY 4.0 record.
  Canonical official inventory SHA-256:
  `471ae25783099779d5d2ecc95f613a8ca2a6cd7614388a8b43ea538c98f3f423`.
- Candidate primary cohort: N/I/O × five bearing specifications × three loads = 45 recordings;
  15 crossed bearing-type/load folds, each with 24 source, 3 target, and 18 quarantined records.
  The remaining 54 B/IO/IB/OB records are reserved as an unfrozen open-set stress cohort.
- Output SHA-256 values: inventory CSV
  `98283df45832cf5504403d1d7573cd0f03e11b91161b944f91ff124075209713`;
  candidate split topology
  `a4b7c9b40670da7260952a47b6c41a119d71533a87624f2ce37bcf321b6266dd`;
  metadata summary
  `5678f37b4b2e5373600d4559dd239bb7ea74eac2ba59230cefa06fcdcdabc449`.

## EXP-432 — retrospective paired-scatter stability audit

- Status: complete; development-only and prohibited from confirmatory use.
- Run:
  `EXP-432-PAIRED-SCATTER-STABILITY__20260818T174456.324512Z__retrospective-paired-scatter-ridge-stability-aud`
  — exit 0 in 84.447559 seconds.
- Repeated the EXP-430 audit and added a predeclared `k=4` ridge grid from `1e-6` through `1.0`.
  The best cross-dataset mean minimum-fold macro F1 was `0.437534` at `ridge=3e-3`, but the same
  statistic ranged from `0.216823` to `0.437534` across the grid.
- Paderborn minimum-fold macro F1 remained between `0.077441` and `0.166667`. The apparent
  stability improvement therefore does not repair the physical-identity/setting tail failure.
- Scientific decision: paired scatter remains an explicitly labelled comparison baseline. It is
  not the v0.3 contribution, no target-selected ridge is allowed in D3, and its instability is a
  reported negative result rather than a tuning opportunity.
- Output SHA-256 values: ridge-sensitivity table
  `e3c31607f80585881458d1cb59cd77539bd337c69845dfc274e769426aa67f7a`;
  failure summary
  `040ce7c6e1fbc7ec20b927bee265d573680d0d21eacdcf0e6d9fd3725a1ddd31`;
  method/fold metrics
  `a35c96deeb59a376a9d7dcc2a4dfa5f6ff718c84a008cecbb97b6af1dbd2b47c`;
  subset grid
  `29b6f15dda1b2db6e90795da12bcc59ca491fb89ae3170212621efe52e1313d7`;
  paired-scatter probe
  `177628e0c8f62fc3bb2cc4421c9987bb3411111966904c08ec9fe28326a86601`;
  blend grid
  `98d2ad6ac8872e7646af2f292acaea2a2d30b8f5e0f7c74d654648c2845518c9`.

## EXP-433 — retrospective four-protocol classical audit

- Status: complete; D2 development-only and not confirmatory.
- Run:
  `EXP-433-PADERBORN-PROTOCOL-CONTRAST__20260818T175516.802906Z__retrospective-four-protocol-physical-unit-audit`
  — exit 0 in 38.435361 seconds; stderr empty.
- Seven fixed classical models produced one out-of-fold prediction per each of 2,319 records under
  measurement-random, setting-holdout, identity-holdout, and crossed-holdout access. All protocols
  were scored on the same 24 identity-fold × setting cells.
- ExtraTrees remained the pooled leader under all four protocols, so no classical champion reversal
  is claimed. Its pooled macro F1 was `0.998389` under measurement-random and `0.544720` under
  crossed holdout; paired bearing-bootstrap difference `+0.453670`, descriptive 95% interval
  `[0.332442, 0.596978]`.
- ExtraTrees minimum-cell macro F1 fell from `0.983323` to `0.164103`. Seven-method pooled-rank
  Kendall agreement between measurement-random and crossed was `0.523810`.
- Summary SHA-256:
  `8fd225b9b44316acbf6be89ef49d29ae92890df1a27ee33004d633e252b6e6cf`;
  aggregate metrics:
  `cbca923ef6bc2563d37a6cbd20542bf9e6c6f2a0a5beed0b22b9d7c557aab4cb`;
  seed-independent prediction artifact:
  `1cfa977620c34c28625cb2e132d68cb7f280aa2efff542af8835aa0bb21dd024`;
  bootstrap summary:
  `7c22115bd4e4964cfc67d03ab95f4ccc041de571918c7a94812789f9d880bc90`.

## EXP-434/434B — frozen nine-method neural protocol audit

- EXP-434 is a retained pre-fit failure. It exited 1 in 14.558580 seconds because the new process
  called the CUDA peak-memory reset before explicitly initializing the CUDA context. No model fit,
  checkpoint, prediction, or scientific outcome was produced. Stderr SHA-256:
  `a4a207ffe837135f355e85aef74f576a93c1970df07e9f8412fdc327423b5eee`.
- The reconciliation added the same explicit `torch.cuda.init()` used by EXP-417. Focused lint and
  all 17 protocol tests passed before the rerun.
- EXP-434B run:
  `EXP-434B-PADERBORN-NEURAL-PROTOCOL__20260818T180706.816990Z__frozen-nine-method-four-protocol-neural-audit`
  — exit 0 in 1,767.457374 seconds; stderr empty.
- It completed 720 new GPU fits (three protocols × 16 folds × nine methods × five seeds) and
  imported the hash-locked 1,080 EXP-417 crossed fits. The final artifact has 417,420 seed-level
  predictions, 180 complete protocol/method/seed groups, and maximum probability-sum error
  `1.3784e-7`.
- Measurement-random pooled macro F1 ranged from `0.964534` to `0.987148`; crossed holdout ranged
  from `0.360074` to `0.403121`. Every method's random-minus-crossed bearing-bootstrap interval
  excluded zero; effects ranged from `+0.561413` to `+0.627074`.
- Neural leaders changed with access: CCDG led measurement-random (`0.987148`), PIRL-ratio led
  setting-holdout (`0.724324`), and MatchDG led identity-only (`0.448653`) and crossed
  (`0.403121`). MatchDG ranked 9th/1st and CCDG 1st/9th under random/crossed pooled macro F1.
- Nine-method pooled-rank Kendall agreement with crossed was `-0.555556` for measurement-random,
  `0.333333` for setting-only, and `-0.277778` for identity-only. The random comparison is also a
  ceiling regime, so its ordinal reversal must be reported with the narrow score spread.
- Summary SHA-256:
  `0a717c6bc1e4d94182b11f91502397d32a3816d86931ed5369316714a2a13a9e`;
  seed predictions:
  `0f3b3767699b3c6205db5546537881bbe7045a70d14a7f0d2b9990c3f1a34c8f`;
  five-seed ensembles:
  `dc04dee764e5152b334e0f6fb262197336ce50f7739910365486523325492ed5`;
  aggregate metrics:
  `79e6954e7dd8562a29e5221b06fe4251862f8a798de92b5eaa05861832536495`;
  rank shifts:
  `dcc0e0acd4f546098aeea98fcdbd9aca604617dc684082962c59ad4318638479`;
  bootstrap summary:
  `b628602a9bce911b76e1f0c5501834ff8f82b987c921832afc5943196a67339e`.

## EXP-435 — independent neural protocol artifact validation

- Status: complete; validation passed.
- Run:
  `EXP-435-PROTOCOL-ARTIFACT-VALIDATION__20260818T184035.459458Z__independent-neural-protocol-artifact-recomputati`
  — exit 0 in 5.762041 seconds; stderr empty.
- Independently locked every declared artifact, checked 720 unique model states and exactly 80
  DANN auxiliary states, recomputed five-seed probability means, and recovered all 36 complete
  protocol/method ensembles.
- EXP-417 crossed-import maximum probability difference: `0`; three-checkpoint versus final
  maximum probability difference: `0`; independent ensemble mean difference: `0`.
- Maximum independent differences were `4.9944e-13` for aggregate/cell metrics,
  `4.4443e-13` for rank concordance, and below `1e-12` for bootstrap estimates/quantiles.
- Validation JSON and stdout SHA-256:
  `f6669e3fcf75cc6655a10598e50f1db9bc1714f7fbd8b04d6466e07fc1ddd7dc`.

## EXP-436/437 — sealed classical sensor audit and independent validation

- EXP-436 run:
  `EXP-436-PADERBORN-SENSOR-CLASSICAL__20260818T185857.314696Z__sealed-classical-multisensor-protocol-audit`
  — exit 0 in 122.973431 seconds; summary SHA-256
  `fe12ce9d8380274d0485a9c0577c502bb53c424fa7428641e7f27f94a5e8b6f2`.
- Cross-setting 29-bearing re-identification macro F1 was `0.603389` for vibration/linear-SVM,
  `0.511639` for motor-current/ExtraTrees, and `0.696992` for fusion/ExtraTrees, compared with
  chance approximately `0.0023`.
- ExtraTrees random/crossed fault macro F1 was `0.990864/0.598245` for vibration,
  `0.982279/0.382770` for motor current, and `0.998389/0.544720` for fusion. The paired
  vibration-minus-current protocol-gap contrast was `-0.206891`, physical-bearing interval
  `[-0.345241, -0.052394]`.
- EXP-437 independent no-refit run:
  `EXP-437-PADERBORN-SENSOR-VALIDATION__20260818T190256.821084Z__independent-sensor-artifact-recomputation`
  — exit 0 in 12.137644 seconds; validation SHA-256
  `17777e4813042d32baf7d4930747dd1a9cc77708de78643bd0f0a69e0624fb64`.

## EXP-438 — sealed Paderborn vibration neural audit

- Run:
  `EXP-438-PADERBORN-NEURAL-VIBRATION__20260818T190705.935218Z__sealed-neural-vibration-four-protocol-audit`
  — exit 0 in 4,136.117463 seconds; stderr empty.
- Completed all 1,800 fits across nine methods, four protocols, and five seeds. Random macro F1
  ranged `0.878226--0.942579`; crossed macro F1 ranged `0.504998--0.584793`.
- All nine random-minus-crossed bearing-bootstrap intervals had positive lower limits; effects
  ranged `+0.293433--+0.429867`. CCDG led random access and MatchDG led crossed access;
  random/crossed Kendall tau was `-0.388889`, with MatchDG moving from ninth to first.
- Summary SHA-256:
  `e30592e1b0f7b94c012f99c10a2f5374907a3fa76fd5d3f6773796f47eeeb5fb`.

## EXP-439 through EXP-444B — HUST expected topology, acquisition, features, and sealing

- EXP-439 is a retained command-quoting failure: `--output-dir` lost its argument before the
  metadata-only script ran. Exit 2 in 3.317396 seconds; stderr SHA-256
  `90deb76c7de826bb5fa721e796e69a6305decb81b74e8c412bd68a24b28bf75c`.
- EXP-439B completed the signal-unopened expected topology in 6.131226 seconds. Expected-manifest
  SHA-256: `1067cb8a8459f933cbda063d2bcd026accf25c49e12dd66c10154833a1361e9b`.
- EXP-440 acquired the 45 sealed primary MAT files, 309 MB total, in 172.814227 seconds. Acquisition
  summary SHA-256: `41cdda49338cd30e21920a3f549ef62a214863e94e6da50b7238ecdaf9456e75`.
- EXP-441 produced the frozen 450-row, 24-feature structural matrix in 5.517692 seconds. Feature
  summary SHA-256: `c17f2f8be3b8e9661b3c79a4944221f63d74631f4dc778e57f3b6bc560f80f71`;
  matrix SHA-256: `8dd2ede963a7f5b26c30c868c28ed11c21572d16617436b5cbb21255b8200f6d`.
- EXP-442 is a retained pre-model sealing failure: the validator incorrectly required `row_index`
  inside the feature matrix. Exit 1 in 2.951910 seconds; stderr SHA-256
  `1564a78488f67fabc50a51e38ea93a8240474c8a913e6aa7556ff361725a3399`.
- Amendment 001 moved `row_index` to an explicitly hashed companion artifact without changing a
  signal, feature, split, configuration, method, or interpretation rule. EXP-442B then sealed the
  execution contract in 3.210532 seconds; seal SHA-256
  `ea64a99c20780ed4b2ffbe8d5c4b09ba4871ecbaa5911c43e7eca5b4fb20c9da`.
- EXP-442C and EXP-443 locked and reverified the explicit transitive runtime dependencies before
  model fitting; both exited 0. EXP-444 is a retained preflight failure because it still expected
  the pre-amendment sealer hash. EXP-444B used the amendment-aware manifest and passed in
  0.158825 seconds. No model fit occurred in any failed run.

## EXP-445/447 — sealed HUST primary replication and independent validation

- EXP-445 run:
  `EXP-445-HUST-D3-NEURAL__20260818T201519.078287Z__sealed-one-shot-four-protocol-external-replicati`
  — exit 0 in 2,763.058028 seconds; stderr empty; all 1,260 fits completed.
- Every method scored `1.000000` under recording-random and load-holdout access. Crossed macro F1
  ranged `0.746795--0.773970`; all nine random-minus-crossed intervals excluded zero and the median
  effect was `0.226030`. The frozen protocol-gap rule passed 9/9.
- The rank rule mechanically passed through a four-position shift, but random ranks were completely
  tied and Kendall tau undefined. This is not treated as a directional winner-reversal replication.
- Summary SHA-256:
  `3f721ff50cc72b845d5ce16a3c7ef987ae5c33cb0d69bfab0804a9be38b5d61a`.
- EXP-447 independently recomputed all counts, probabilities, record aggregation, metrics, ranks,
  bootstrap results, confusion counts, and diagnostics without fitting. Exit 0 in 7.639935 seconds;
  maximum numeric difference below `5e-13`; validation SHA-256
  `ba9ceee356fe8cc04ddfe1a28f6e46038fd0c60c4ea374df196400b22fdf6c6a`.

## EXP-446/448/449 — outcome-blind equal-source-volume HUST control

- EXP-446 locked the control implementation before the primary HUST outcome was read. The control
  seal SHA-256 is `d13b040a5653492199af19b52dd6f31a4c5462dbce48eb4f3316924e014b3076`.
  EXP-448 reverified both inherited and control-specific runtime hashes immediately before fitting;
  both runs exited 0.
- EXP-449 run:
  `EXP-449-HUST-D3-SIZE-MATCHED__20260818T210049.008798Z__sealed-equal-volume-access-control`
  — exit 0 in 1,679.904282 seconds; stderr empty; all 675 fits completed.
- With identical targets and 24 source recordings per fold in both arms, all nine methods scored
  `1.000000` under shared access versus `0.746795--0.773970` under strict crossed access. Every
  shared-minus-crossed interval excluded zero; the median effect was `0.226030`, so the frozen
  7/9-and-0.10 rule passed. Source-record count alone is not a sufficient explanation.
- Summary SHA-256:
  `23b898440a6a09c4efd21ea6e9faec16ca637989a5310e4fa69f8067f5e4833c`.

## EXP-450/450B — equal-volume validator failure and validator-only reconciliation

- EXP-450 is retained as a failed validator run. All artifact comparisons had completed, but exact
  Python dictionary equality treated two independently obtained undefined Kendall correlations
  (`NaN`) as unequal. Exit 1 in 4.633431 seconds; stderr SHA-256
  `644424190e113e396f5608ef6ef12c8e2ccb0a33a6a80778b5f98d2919a47b9c`.
- Validator version 0.1.1 changed only findings comparison: keys and booleans remain exact, two
  `NaN` values are equivalent, and finite serialization drift is capped at `1e-12`. New focused
  tests cover accepted round-off and rejection of structural, boolean, finite, and one-sided-NaN
  changes. No producer, fit, prediction, summary, gate, or frozen control dependency changed.
- EXP-450B run:
  `EXP-450B-HUST-D3-SIZE-MATCHED-VALIDATION__20260818T213134.678697Z__tolerant-independent-no-refit-equal-volume-valid`
  — exit 0 in 5.304429 seconds; refit false. Every expected count and artifact reproduced, maximum
  numeric difference below `5e-13`, and findings numeric difference exactly zero. Validation
  SHA-256: `b7e13cf20ff51d06690e56b0f1d45102ecba23dc0df56ad4a7790e4c5d263abe`.

## EXP-451 — sealed Paderborn motor-current neural audit

- Run:
  `EXP-451-PADERBORN-NEURAL-CURRENT__20260818T212905.928682Z__sealed-neural-motor-current-four-protocol-audit`
  — exit 0 in 4,228.351352 seconds; stderr empty.
- Completed all 1,800 frozen fits across nine methods, four protocols, and five seeds, yielding
  417,420 seed-level predictions and 180 complete protocol/method/seed groups. Maximum probability-
  sum error was `1.3970e-7`.
- Measurement-random pooled macro F1 ranged `0.730703--0.894312`; crossed performance ranged
  `0.369564--0.432645`. All nine random-minus-crossed bearing-bootstrap intervals had positive
  lower limits; effects ranged `+0.298059--+0.518701`.
- DANN led random access; MatchDG moved from ninth under random access to first under crossed
  access. Random/crossed pooled-rank Kendall tau was `-0.333333`.
- Summary SHA-256:
  `47ce349cc8ab633d51384614310bc926bcff7a8b5f294f2e91318a9765e51e46`;
  aggregate metrics:
  `f3f405487e837d887305d2e72fce7f79129a8ac3a3a2b37fa9b0df8aab67fa93`;
  bootstrap summary:
  `505ee02d19b36e716205fe482602ec5996423d598b994be90d0d1849c27323fa`.

## EXP-452/453 — combined neural sensor attribution and independent validation

- EXP-452 run:
  `EXP-452-PADERBORN-NEURAL-SENSOR-ATTRIBUTION__20260818T223740.164619Z__combined-three-sensor-neural-attribution`
  — exit 0 in 23.807387 seconds; stderr empty. It combined 250,452 five-seed ensemble rows after
  verifying all three source summaries, artifacts, configurations, target rows, and shared
  2,000-draw physical-bearing plan. Source-artifact recomputation differed by at most `5.1e-13`.
- Every one of the 27 sensor-by-method random-minus-crossed intervals had a positive lower limit.
  Fusion-minus-vibration gap differences were `+0.175224--+0.267980` and excluded zero for all
  nine methods. Fusion-minus-current gaps were positive for all nine and excluded zero for six;
  vibration-minus-current excluded zero for none.
- Vibration crossed scores exceeded fusion for all nine methods, with eight intervals excluding
  zero; vibration exceeded current for all nine, with five excluding zero. MatchDG led crossed
  access for every sensor family. These are paired descriptive sensor contrasts, not causal feature
  attributions.
- EXP-452 summary SHA-256:
  `72f1bbca7ae6fa2e50f105ff699a2022b7705ca8cda0dd2ea43c341edb8b23ea`;
  combined ensemble:
  `3ae66e00f93383b5eea875e77543464a4d768a2dfc04ba24666ed37881d6b8fa`;
  gap differences:
  `1dd90e0f6c90ef5f68b285ed2cc31e9318ada6115bb30dfd7b1791dadeb17755`;
  absolute score differences:
  `43e7144c70418a7e3e94f0f06f67cfebb8a9ed720d48ea14aac0ed671820ce22`.
- EXP-453 run:
  `EXP-453-PADERBORN-NEURAL-SENSOR-VALIDATION__20260818T223826.374149Z__independent-no-refit-three-sensor-validation`
  — exit 0 in 21.977660 seconds; stderr empty; refit false. It independently reproduced all 12
  derived artifacts with maximum numerical difference `5.0005e-13`. Validation SHA-256:
  `acb71e10125a710681ae3fc8fee72ee7f691947d21932955af753a5d5301c5cc`.

## EXP-454/455 — sealed raw-architecture design and hash-locked windows

- EXP-454 locked the retrospective raw/FFT/STFT design and implementation before any raw model
  outcome. Run:
  `EXP-454-PADERBORN-RAW-SEAL__20260818T215422.648902Z__retrospective-raw-architecture-code-and-design-l`
  — exit 0. Seal SHA-256:
  `d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b`.
- EXP-455 run:
  `EXP-455-PADERBORN-RAW-WINDOWS__20260818T222514.301091Z__hash-locked-four-window-vibration-artifact`
  — exit 0 in 199.584624 seconds; stderr empty. All 29 primary archives and sealed MAT-member
  hashes were checked before extracting four fixed 8,192-sample vibration windows per retained
  record.
- The final float32 array has shape `9,276 x 8,192`, the index has exactly 2,319 records and four
  unique window positions per record, and no window-row key is duplicated. Every summary-declared
  digest was independently checked.
- Summary SHA-256:
  `af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191`;
  window array:
  `5768f08e9b20d5f521c5efb6e7b23ffe4d18b926caecbe399640e84c83aeeb7f`;
  window index:
  `cfcea11bcd2edeb37f465125555c612a202a66c7035d177715459081d65eeec5`.

## Documentation correction — EXP-436 re-identification comparator

- A 2026-08-19 manuscript audit found that the EXP-436 ledger entry and two working paper files
  called macro F1 `0.0023` “chance.” The locked metric row shows that `0.00229980882839` is the
  observed macro F1 of the explicit `dummy_prior` classifier, which always predicts one class.
- For 29 balanced identity classes, uniform chance accuracy and balanced accuracy are
  `1/29 = 0.0344827586207`; macro F1 depends on the prediction rule and is not generally identical
  to that value. The manuscript now reports both the measured dummy-prior macro F1 (`0.002300`) and
  the balanced-chance accuracy (`0.034483`).
- No prediction, metric, artifact, hash, or empirical conclusion changed. The original ledger text
  remains above so that the correction is append-only rather than silently rewritten.

## EXP-456A — explicit no-refit Paderborn protocol validation

- The final paper-artifact gate requires every validator to declare `refit_performed: false`
  explicitly. EXP-435 performed no fit but predated that machine-readable field, so validator
  version 0.1.1 adds only the declaration and repeats the same locked recomputation.
- Run:
  `EXP-456A-PADERBORN-PROTOCOL-VALIDATION__20260818T232953.691340Z__explicit-no-refit-neural-protocol-validation`
  — exit 0 in 6.363932 seconds; stderr empty; `refit_performed` false.
- All 720 model states, 80 DANN auxiliary states, 417,420 seed predictions, 83,484 ensemble rows,
  metrics, ranks, checkpoints, crossed imports, and 2,000-draw bearing-bootstrap summaries passed
  the unchanged recomputation. No producer or numerical artifact was modified.
- Validation JSON and stdout SHA-256:
  `03428d40112509c08ffe11bf56ca172a6975b5570d653bc5ac1fbf5a0ece8099`.

## EXP-456 interruption and EXP-456R1 from-scratch recovery

- EXP-456 run:
  `EXP-456-PADERBORN-RAW-ARCHITECTURES__20260818T223720.239397Z__sealed-raw-fft-stft-protocol-sensitivity`.
  At `2026-08-19T02:12:05Z`, its metadata still said `running`, but no recorded-run or training
  process existed, stderr was empty, and no final summary existed. The last outcome-blind progress
  event was fit 79/270. Only the 54-fit measurement-random architecture-boundary checkpoint was
  durable. No performance value was inspected.
- The interruption is classified only as external process/session loss because the retained files
  cannot support a narrower cause. All partial EXP-456 outputs are excluded from paper evidence;
  neither predictions nor checkpoints are reused. The full incident policy is in
  `research/EXPERIMENT_INCIDENTS.md`.
- All ten locked implementation hashes and the seal SHA-256
  `d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b` were rechecked unchanged.
- EXP-456R1 started at `2026-08-19T02:13:56.938756Z` as an exact 270-fit rerun from fit one:
  `EXP-456R1-PADERBORN-RAW-ARCHITECTURES__20260819T021356.938756Z__sealed-raw-fft-stft-protocol-sensitivity-rerun1`.
  A hidden Windows host process holds the WSL recorded-run parent and GPU child independently of
  the interactive terminal. At this ledger update, both processes were alive, stderr was empty,
  and no intermediate performance outcome had been inspected.
- A second hidden host process runs an outcome-blind handoff watcher. It polls only EXP-456R1's
  terminal status and process presence. It starts formal EXP-457 independent no-refit validation
  only after `status=complete`; any failed/interrupted/stale state stops the handoff and leaves an
  error log. It does not parse or report performance values.
- At `2026-08-19T03:00:29Z`, a third hidden host process started the downstream EXP-458/EXP-459
  handoff watcher. Before launch, its shell syntax passed and all nine frozen Paderborn, sensor,
  HUST, equal-volume-control, and raw-window input hashes matched their hard-coded values. The
  watcher waits for exactly one completed EXP-457 run, then generates the deterministic 25-input,
  39-output bearing-paper artifact package and runs its independent no-refit/tamper validation.
  Any absent input, hash mismatch, non-complete predecessor, or artifact-validation failure stops
  the chain. At launch, both watcher logs and the EXP-456R1 stderr log were empty; EXP-456R1 had
  completed 14/270 fits, and no intermediate performance outcome had been inspected.
- At `2026-08-19T03:28:46Z`, a fourth hidden host process started the EXP-460/EXP-461 manuscript
  handoff watcher. It waits for exactly one completed EXP-459, requires the independent artifact
  validation status, `refit_performed: false`, and matching artifact-manifest hash, and also locks
  the working manuscript template to SHA-256
  `3b3e483cfe50136e892eccc9e0ac86235ca6210033453f174a17e1714169b2d6`.
  EXP-460 will render the empirical-final manuscript from the validated headline values whether
  the raw rule passes or fails while retaining human-owned authorship/funding/conflict holds.
  EXP-461 will independently recheck its abstract, per-architecture effects and intervals, rule
  wording, all 14 table/figure callouts, final contrast counts, template/manifest/output hashes,
  and explicit `submission_ready: false` without invoking the renderer or fitting a model. The
  watcher shell syntax and 33 targeted manuscript/submission/release tests passed before launch;
  both watcher logs were empty. EXP-456R1 had completed 25/270 fits, stderr was empty, and no
  intermediate performance outcome had been inspected.
- At `2026-08-19T03:47:57Z`, a fifth hidden host process (Windows PID 12624; WSL watcher PID
  919816) started the EXP-462/EXP-463 technical-release handoff. The release implementation was
  upgraded to version `smartvalve-bearing-evidence-release-0.6.0` after an audit found that the
  archive builder required EXP-461's independent manuscript validation but did not yet require or
  retain EXP-459's independent 25-input/39-output paper-artifact validation. The corrected builder
  now rejects a missing or changed EXP-459 status, no-refit flag, manifest hash, topology counts,
  SVG/PDF counts, or raw-data exclusion flag and stores that validation as a named archive member.
  Eight release tests, including independent artifact-validation and empirical-manuscript tamper
  cases, passed; targeted Ruff, watcher shell syntax, template hash, and `git diff --check` also
  passed. Watcher SHA-256 is
  `129dd2cdc2f777a124dcf1ba065ba7e091c7aa4a34bc524641e985a269103584`; both watcher logs were
  empty after launch. It waits for exactly one completed EXP-461, rechecks EXP-458 through EXP-461
  status and hashes, builds the deterministic raw-data-free candidate archive as EXP-462, and then
  independently reopens and validates every member and both validation-chain flags as EXP-463. The
  archive remains explicitly `submission_ready: false`; the watcher performs no upload, DOI mint,
  authorship declaration, or human approval. EXP-456R1 had completed 32/270 fits, stderr was empty,
  and no intermediate performance outcome had been inspected.
- At `2026-08-19T03:59:19Z`, the source state containing the corrected release chain passed all 366
  tests in 195.28 seconds. The independent coverage invocation passed the same 366 tests in 448.27
  seconds and measured 77.87% over 11,236 statements against the unchanged 75% gate. Full-source
  Ruff and Bandit passed, both `requirements.lock` and `requirements-ci.lock` had zero known
  `pip-audit` findings, and `git diff --check` was clean. The sole warning was the already recorded
  scikit-learn 1.9 SVC probability deprecation. EXP-456R1 remained alive at 38/270 fits with empty
  stderr; all four downstream watchers were alive and no intermediate performance outcome had been
  inspected. These are local regression gates, not a fabricated clean-clone or external-review
  signoff.

## EXP-464/464R1/465 — post-hoc HUST physical-unit influence audit

- The plan was frozen at `2026-08-19T04:10:19Z`, after the primary HUST and equal-volume outcomes
  were known but before any deletion effect was computed. Plan SHA-256:
  `f634654938c4cf2f7ef34493b02e6ee51bb4714818d5ceacbe7ad31a81b5fc30`. It prohibits refitting,
  p-values, confirmatory promotion, and result suppression.
- EXP-464 is a retained mechanical failure. An unquoted recorded-run placeholder was transformed
  by PowerShell, so `--output-directory` lacked an argument; exit 2 in 1.345256 seconds. It produced
  no scientific output and no influence result was inspected.
- EXP-464R1 repeated the exact frozen inputs and implementation with literal placeholder quoting:
  `EXP-464R1-HUST-PHYSICAL-UNIT-INFLUENCE__20260819T041145.489149Z__frozen-posthoc-bearing-and-group-deletion-audit-`.
  Exit 0 in 3.598796 seconds; stderr empty; refit false. It retained 18 full effects, 270
  leave-one-bearing effects, 90 class-balanced leave-one-specification-group effects, and all 18
  method-by-comparison summaries.
- Effects remained positive in 18/18 cells under both deletion schemes. The minimum bearing- and
  group-deletion effects were `0.1745457916203188` and `0.11223443223443219`; maximum absolute
  changes from the full effects were `0.05148467432950199` and `0.1137960337153886`. These are
  post-hoc sensitivity ranges, not confidence intervals or new independent replicates.
- Audit summary SHA-256:
  `431e580c9ee2d3489980fd4edad31151f97eeff343656473d1df8504c2406e18`; complete summary-table
  SHA-256: `e54923458dadf48d7a3d7e2abf90fb009acceaeba1e823474045b1c90497aab3`.
- EXP-465 independently recomputed manual classwise macro F1 and all 396 reported rows without
  importing the producer computation or fitting a model. Exit 0 in 0.900044 seconds; maximum
  numeric difference below `4.8e-13`; validation SHA-256:
  `dfb88a40883c71059eab856bfc6e25247192431b83a66ebbdc6f1bbccd0e587a`.
- The validated audit is mandatory Supplementary Table S4. Its addition expands the final
  paper-artifact topology from 25 inputs/39 outputs to 28 inputs/42 outputs and the manuscript
  callout gate from 14 to 15. Forty-seven targeted artifact, manuscript, RESS, release, and paper-
  package tests plus targeted Ruff passed after integration.
- The three not-yet-triggered downstream watchers were then stopped by exact PID and relaunched so
  no shell retained the superseded topology. New Windows host/WSL watcher PIDs are respectively
  `5468/933534` for EXP-458/459, `8228/933531` for EXP-460/461, and `12892/933544` for EXP-462/463.
  Watcher SHA-256 values are `352dab43cb4c9bdda59b64d06d2e9bf4acd574adfc35cab40655e912c483f8ac`,
  `f84d211e6da60e9dd0747f84d852e626cdaf55adb7578d299263c3acc9fb29a8`, and
  `3915e7864af6ab701cb8e6158ff608aef02229e133548d38eff0b123d7929d63`.
  All three shell syntax checks passed and all six watcher logs were empty after restart. EXP-456R1
  and its unchanged EXP-457 watcher remained alive; at that check it had completed 50/270 fits with
  empty stderr and no intermediate performance result had been inspected.
- The post-integration full regression collected and passed 373 tests with the one previously
  documented scikit-learn 1.9 SVC probability deprecation warning. Full-source Ruff, the
  medium/high-severity Bandit gate, and `git diff --check` passed. A default low-severity Bandit
  scan reports 15 pre-existing subprocess/archive or token-name findings and no medium/high issue;
  it is not misreported as a zero-finding scan. The final coverage and clean-environment runs remain
  scheduled after EXP-456R1 through EXP-463 complete.

## Final local-quality evidence inserted before release

- A release-chain audit found that EXP-462 would otherwise archive source, tests, and dependency
  locks without a hash-linked transcript proving that the final post-manuscript source actually ran
  those gates. `final_quality_gate.py` now fixes seven commands: full Ruff, pytest with JUnit,
  coverage with JSON and a 75% floor, medium/high Bandit, runtime-lock audit, CI-lock audit, and
  `git diff --check`. It retains every stdout/stderr digest and requires zero failures, errors, or
  skips and at least 379 collected tests.
- `final_quality_validation.py` independently verifies the command order, log byte counts and
  hashes, JUnit totals, coverage JSON, and all scope declarations. A hash-consistent low-coverage
  edit and a hash-consistent human-review overclaim are rejected in synthetic tests. Neither stage
  claims a clean checkout, independent reproduction, human review, or submission readiness.
- The EXP-462 builder is now version `smartvalve-bearing-evidence-release-0.8.0`. It refuses to
  build without completed EXP-461Q/461V evidence, expands every quality-log hash into the archive,
  and marks the independent final-local-quality validation as a required third validation-chain
  flag. The archive validator rechecks that flag and every included byte.
- Twenty focused final-quality/release/review-packet tests passed; targeted Ruff, watcher shell
  syntax, and `git diff --check` passed. The complete suite currently collects 379 tests.
- The not-yet-triggered release watcher was stopped by exact WSL PID `933544` and relaunched with
  the new chain as Windows host PID `15240`, WSL watcher PID `939366`, and script SHA-256
  `88f4d47142a0ac322488536ddd1dfe78a073b6cb818e75b4d6b8df1d5ad26aa2`.
  Both release-watcher logs were empty after restart. EXP-456R1 and the EXP-457/458--461 watchers
  were untouched; EXP-456R1 was alive at 56/270 fits with empty stderr and no intermediate
  performance outcome inspected.

## 2026-08-19 final-quality hardening and exact-axis literature refresh

- The 379-test source state first passed the complete suite with no failures or skips and only the
  previously registered scikit-learn 1.9 SVC probability deprecation. Full Ruff and
  `git diff --check` passed, but the deliberately separate medium/high Bandit invocation correctly
  found two B314 findings in the new JUnit readers: both the quality-gate producer and independent
  validator used the standard-library XML parser. This finding was not suppressed as a false
  positive.
- Both readers now use the already locked `defusedxml==0.7.1` dependency. A new adversarial JUnit
  fixture proves that both code paths reject XML entity expansion with `EntitiesForbidden`.
  The minimum final-gate floor and downstream release watcher were raised from 379 to 380 tests.
  Twenty-one focused quality/release/package tests and then all 380 collected tests passed without
  failures or skips; the same single deprecation warning remains.
- The exact current source also passed full Ruff, medium/high Bandit with no findings,
  `git diff --check`, and both locked dependency audits with zero known vulnerabilities. A separate
  path-based coverage preflight reran all 380 tests and measured `77.94%` over 11,820 statements,
  above the unchanged 75% floor. These are local preflight facts; EXP-461Q/461V still rerun and hash
  every formal final-quality output after the empirical manuscript exists, and neither preflight
  claims a clean checkout or independent reproduction.
- A primary-source exact-axis search added two claim-boundary citations. Li and Zhang's Research
  Square v1 establishes adjacent consumer-GPU, recording-grouped, bearing-disjoint Paderborn STFT
  evaluation; Spirto et al.'s *Structural Health Monitoring* article establishes Hong--Thuan HUST
  Bearing load transfer while nominal bearing specifications remain shared. The manuscript now
  prohibits first/lightweight/bearing-disjoint-STFT and first-HUST-load-transfer claims. Neither
  paper exposes the frozen target-free identity × setting intersection with both XOR arms
  quarantined; this search result is recorded as an absence in the query set, not a priority proof.
- The literature edit changed `paper/BEARING_MANUSCRIPT.md` to SHA-256
  `2cab0c44e4d9f38236ea57adbca6ba0f07e3c7e2c9683190d80abb015611c9fb`. The not-yet-triggered
  EXP-460/461 watcher was stopped by exact WSL PID `933531`, updated to that hash, and relaunched as
  Windows PID `18284` / WSL PID `944481`; watcher SHA-256 is
  `aca1c2dc2a752c2213026ef5c9f4e72283e2fe3b2eec34862122ba84f7f93b95`.
  The release watcher was likewise stopped by exact WSL PID `939366` so it could consume the new
  380-test floor, then relaunched as Windows PID `16348` / WSL PID `944548`; watcher SHA-256 is
  `e2b78882876a9fecc7a58946767300add1b9b16311505c40730793b8327438d2`.
  Both shell syntax checks passed. At the last structural check EXP-456R1 remained alive at 62/270
  fits with zero stderr bytes, all downstream watchers were alive, and no intermediate performance
  result had been inspected.

## EXP-466 — retained resource-isolation preflight failure

- EXP-466 attempted an end-to-end execution of the seven-check gate before the empirical
  manuscript, solely to exercise subprocess/JUnit/report integration. Ruff and the first complete
  380-test JUnit stage finished, but the coverage rerun opened a second CUDA process while sealed
  EXP-456R1 was active. At `2026-08-19T05:15:42Z`, total reported GPU memory use was 7,186/10,240
  MiB; the exact preflight coverage child PID `950397` was terminated to restore exclusive
  experimental GPU use.
- The producer completed its failure path correctly: coverage exit `-15`, no coverage JSON, failed
  quality summary SHA-256 `f2399c0f808282390220c3efdf091b58881cef9c69eed639790adf963292011c`,
  and recorded-run terminal status `failed`/exit 1 after 368.566195 seconds. This is not final-
  quality evidence and is retained rather than deleted or rerun concurrently.
- EXP-456R1 stayed alive and advanced to 69/270 fits with zero stderr bytes. No scientific outcome
  was inspected. The optional overlap can affect wall-clock duration only for the involved fits;
  duration is excluded from architecture-efficiency claims, and the frozen score/bootstrap
  endpoints, inputs, model code, seeds, and running process were not changed. All CUDA-capable
  regression work is now deferred until EXP-456R1/457 finish.

## EXP-467--470 — dependency-lock and clean-install hardening

- A clean-reproduction audit found that `requirements-ci.lock` had been compiled from only the
  development and security extras even though research modules collected by the full suite import
  PyTorch. It also found that the clean protocol did not install `build-requirements.lock` or sync
  the hash-locked public fixtures before pytest, while CI linted only selected directories, used the
  ambiguous `--cov=smartvalve` target, and audited only the runtime lock. Consequently the stated
  clean-checkout/zero-skip path was not executable as written; no such claim is retained.
- An isolated `pip-tools==7.6.1` environment regenerated `requirements-ci.lock` from the dev,
  security, and research extras against the official PyTorch CPU index. The resulting 2,394-line
  lock has SHA-256 `6accf7867646fd287091b637b9042e6e3093f8ee181844534540bd607e8f837e`, pins
  `torch==2.13.0+cpu`, and contains no CUDA, NVIDIA, or Triton package. A separate 2,107-line Ubuntu
  full-refit lock has SHA-256 `7c044177fc692d638c79315995d1ae54d41c5239dbb2c32e53b7524c2a5f9161`,
  pins `torch==2.13.0`, and explicitly locks the CUDA 13 stack. The unchanged runtime-lock hash is
  `499422838b2ecacb3fa709d484e9f340ee90b2399e35724f68107fc072919d29`.
- A first default-PyPI audit of the CPU local-version wheel returned zero but printed that PyTorch
  was skipped. That output was not promoted as a pass. Strict OSV collection was then validated for
  the CPU lock, while strict PyPI collection was retained for the two ordinary-PyPI locks. Formal
  EXP-467, EXP-468, and EXP-469 each exited zero with the complete message `No known
  vulnerabilities found` and no unaudited dependency. Their metadata SHA-256 values are
  `eb711b8c82316a2750f51570fb3066f8cf2a1d128baf2a6b2049462222c9075a`,
  `69419a185c62304388b684a834c358bbfc1e7a4480b1d2ddce345c6c3299873f`, and
  `f575766e90174b581153f9ddfa06075ffa7fbf794cc1563ad63de27a06f9ad5d`.
- EXP-470 ignored the installed environment and performed a hash-required, no-install resolution
  of every CPU-CI dependency. Exit zero; the retained `Would install` record selects
  `torch-2.13.0+cpu` and contains no CUDA/NVIDIA package. Metadata SHA-256 is
  `c9eb87579f3794e98c08fdaa17d2d37b13c493eee5fa4a8c5899d922064cd46c`; stdout SHA-256 is
  `dc90791930ca495dbf38ab9035fd2c8ac1f07b0af9cac78c7d087ccdcf2f5917`.
- The final local gate is now version `smartvalve-final-local-quality-gate-0.2.0` and fixes eight
  commands, adding a strict GPU-research lock audit. The deterministic release builder is version
  `smartvalve-bearing-evidence-release-0.9.0`, requires the eight-check validation, and archives all
  three application-environment locks. Code SHA-256 values are
  `9260a414422bcf181fe3d1ffc2be8ccd7a0e54357dd71715e9f5dedf8e6e5c8d` for the gate and
  `0acf92b1c89d9aa7d4775481af05db50da62b5d75fc5e6f22ec0e2227444fd49` for the builder.
- CI now installs the CPU lock, syncs all five public fixtures into a cache outside the checkout,
  asserts every source hash, enforces zero JUnit skips, lints the full tree, measures the explicit
  source path, strictly audits all three locks, and runs `git diff --check`. The clean protocol uses
  the same separation and creates a distinct GPU environment only for optional full refitting.
  Full-source Ruff, medium/high Bandit, Python byte-compilation, watcher shell syntax, and
  `git diff --check` passed; no pytest invocation was started while the sealed CUDA job remained
  active.
- The not-yet-triggered release watcher was stopped at exact WSL PID `944548` and relaunched hidden
  as Windows PID `11724` / WSL PID `966192`. Watcher SHA-256 is
  `acedd40a8dbed4bb335562a381f244ede66c6051a4bde6a6a4700b14fcac0c44`; both watcher logs were
  empty after restart. At `2026-08-19T06:03:56Z`, EXP-456R1 was the sole CUDA client, alive at
  87/270 outcome-blind progress records with zero stderr bytes; all four downstream watchers were
  alive and no intermediate performance result had been inspected.

## EXP-467B/471A--J/472/472R1/473 — isolated CPU reproduction preflight

- Extending strict collection to the build toolchain found that the historical lock used yanked
  `build 1.5.1`, did not pin pip, and carried `setuptools 82.0.1` with `PYSEC-2026-3447`. That
  direct audit exited one and was not promoted. The corrected input fixes non-yanked `build 1.5.0`,
  `pip 26.1.2`, and `setuptools 84.0.0`; build-lock SHA-256 is
  `cebcd0cd7d596fcb8ff769fc7852aff1c274267ab9c790ba76f01c5db09ab1b7`. EXP-467B then strictly
  audited runtime plus build with exit zero and no finding; metadata SHA-256 is
  `eb25c0a65cf2c756c9cd6878abce033372099675db1831718eb406873bb85478`.
- EXP-471A through EXP-471F created `/tmp/smartvalve-cpu-repro.EPRaB3/venv`, installed the
  hash-locked build and CPU-CI environments, installed a non-editable project wheel, validated the
  CPU runtime, and passed `pip check`. All six exited zero in respectively 2.615023, 5.540133,
  129.861410, 1.360174, 1.390522, and 0.381959 seconds. The validation reports metadata and runtime
  `torch==2.13.0+cpu`, `compiled_cuda_version=null`, and `cuda_available=false`; no CUDA client was
  created. EXP-471A--F metadata SHA-256 values in order are
  `650c3701f3fada16e36fe90c71300de08f7af902e4abe8701759487cbd6e52e8`,
  `0fa781420551c5932d90f32cb6006fc4772ee9a9d9c0d20e5126c25178542a35`,
  `89279cb781157cc626cd426e0d73144d469f04bbc8b8841e855521e541595aa7`,
  `cc88360c5094a5ad97957ee92ab05259b0ad25ee7e3384999e87f3bb2658d981`,
  `438648887bc16b04b88a73fbff7fce298546d83b2f9532001d931630f3d1080e`, and
  `26c9d9073110b9e57dc9cd6b669cf43a47501effc0de22232ee3f1e2edeb0104`.
- EXP-471G retained a real clean-cache acquisition failure: exit one after 21.433860 seconds due to
  `ssl.SSLEOFError`/`URLError` before the UCI download. Metadata SHA-256 is
  `b4abf65b42326ca2a755507c8ebf4f040fd01a2660cfb28bdfaefe1f3dfa9fe8`. The downloader now uses
  three bounded HTTPS attempts, linear backoff, atomic part-file replacement, and final byte/hash
  rejection while preserving a final bad part for diagnosis. Four new retry/configuration test
  cases were added; implementation SHA-256 is
  `a53b993dfda6da2e930dd587e49e622d70b443acb664a69ecc84fb80a93035b3`.
- EXP-471H force-reinstalled the retry-hardened non-editable wheel. EXP-471I then completed the
  public sync in 6.324830 seconds, and EXP-471J separately required all five fixtures to have exact
  declared bytes and SHA-256 values. All three exited zero; metadata SHA-256 values are
  `9720f496d8cf98962b73ea34ceaf676e7bcda967273718c88b0d9373ce13edda`,
  `2a1de7681d01fc7c2b5b561d01d1e2b05faad42ce3c7abc034248863c6751793`, and
  `4d0300db92645947fc849f4016ccf8cc75dc2cd627677b04f48914811720b165`.
- EXP-472 deliberately ran the complete suite rather than stopping after the first error. It
  retained one failure out of 384: the old test incorrectly required an environment-configured
  cache directory to be literally named `external`, although the clean protocol intentionally
  uses an outside-cache name. Metadata SHA-256 is
  `d0b2e75b0fc5fd7d6af72e4527ed24fff81744ecc6ae04b760cb799b02c2eb67`.
  The corrected assertion checks the intended safety property: the cache may not equal or descend
  from `data/generated`.
- EXP-472R1 reran all 384 tests from scratch in the isolated CPU environment. Exit zero in
  209.089501 seconds; 384 tests, zero failures/errors/skips. JUnit SHA-256 is
  `b3ad82e9c6e27ad5f1171ceec52892e2eecfd62fcff1c34ec022e14d8eac1247`; metadata SHA-256 is
  `2ab0652205dcdcd4ea9cd6cd5c12f0544f19be6918b900b1af94d9c7b862628f`. The retained warnings are
  the known scikit-learn SVC deprecation and a CPU-only notice that the sealed raw-training helper's
  `pin_memory=true` has no accelerator; the seal-locked running source was not edited to suppress
  the latter.
- EXP-473 repeated all 384 tests under explicit `--cov=src/smartvalve` instrumentation. Exit zero
  in 469.750577 seconds; zero failures/errors/skips and `77.95036299172716%` coverage over 11,846
  statements. JUnit, coverage JSON, and metadata SHA-256 values are
  `2c73d4b51dfa99d5ac81a90b073df56bc13890dc07559206f8b2e60c0ef80785`,
  `206eae1aadcdfbd11ee4f336760d88190bacec6f23f44c2cc4468f5a1f86a675`, and
  `7a28aeeeae3f1c89156e25479065d95c9c5d315a13481671ec1cb2763e900aa6`.
  These runs prove an isolated CPU-environment preflight against the current dirty source tree;
  they explicitly do not claim a detached clean checkout or independent external reproduction.
- The current source also passes full-tree Ruff, medium/high Bandit, strict build/runtime, CPU-CI,
  and GPU-research audits with no skipped dependency, plus `git diff --check`. The final gate remains
  eight commands but its runtime check now includes the build lock; current gate SHA-256 is
  `c90e0ce488fe772c6578285e7575e8afb5005ed93085c0b231e900a5f6173817`.
  The release watcher floor was raised from 380 to 384, syntax-checked, and restarted hidden as
  Windows PID `8188` / WSL PID `976832`; watcher SHA-256 is
  `6a696418d5debd983ae34e8b657760e6de9b8deb51f4b5fa7756941b3b6e8e87`, with both logs empty.
- EXP-474 then exercised the post-documentation paper-package, deterministic release, eight-check
  quality, empirical manuscript, RESS packet, retry, and public-data tests in the isolated CPU
  environment. Exit zero; 55/55 tests and zero failures/errors/skips. JUnit SHA-256 is
  `530b9b41041985115f7daa2f04ed0f0a04d631da9e0549f58c58256991007bfd`; metadata SHA-256 is
  `66222a6ab44a12d4c2a1daca02368d93d23ea7adf9c4e3ab475c37a9a8a9e738`.
- EXP-475 compared every installed distribution with the normalized union of the build and CPU-CI
  locks. Exit zero: 120 locked packages, 121 installed, with the sole allowed extra being the
  non-editable `smartvalve-ai-twin` wheel; zero missing, unexpected, or version-mismatched package.
  Validator, stdout, and metadata SHA-256 values are
  `d8ccbab8c64163585f42128f2da437c9e68f6c85b2a028cf0f4f7ee5bf4e175f`,
  `061a0ac9e912b3bdbcc7a7a1fde0454afd75976209150af968a39c5fce0a5486`, and
  `5a07f2f07d62e9a55ac78e1f9c6868d292a8255f9a5b7db7ba703e8aee74a168`. CI now explicitly creates
  a fresh `.venv` before installing or validating locks, so runner-global packages cannot pollute
  that parity check.
- At `2026-08-19T06:35:06Z`, EXP-456R1 remained the sole CUDA client and had produced 99/270
  outcome-blind progress records with zero stderr bytes. All four downstream watchers were alive;
  no intermediate scientific performance result had been inspected.

## Checkout-external CI and clean-reproduction products

- A final contamination audit distinguished an empty Git status from a checkout that also contains
  ignored execution products. CI and the independent clean-reproduction protocol now create their
  CPU virtual environment, public-data cache, JUnit XML, coverage data, command logs, and evidence
  hashes under the runner/reproduction temporary root rather than under the source checkout.
  Python bytecode generation and pytest's cache provider are disabled for the quality run. The
  existing local EXP-461Q gate remains intentionally separate and continues to make no clean-clone
  claim.
- CI still installs the exact hash-locked build and CPU-CI environments, validates installed-lock
  parity and the CPU-only PyTorch contract, synchronizes and validates all five public fixtures,
  requires zero JUnit skips and at least 75% source-path coverage, strictly audits the build/runtime,
  CPU-CI, and GPU-research locks, and ends with both `git diff --check` and an empty porcelain status.
  The clean protocol now records separate stdout/stderr files for every equivalent check, asserts
  at least 384 tests with zero failures/errors/skips, records the exact coverage percentage, and
  hashes the resulting record set outside the checkout.
- The updated CI YAML parsed successfully with PyYAML, full-tree Ruff and `git diff --check` passed,
  and CPU-only pytest collection with its cache provider disabled retained the exact 384-test
  topology. Seventeen focused final-quality, external-artifact, and cache-scope tests passed in the
  isolated CPU environment. No second CUDA client was created. CI and clean-protocol SHA-256 values
  are `d2f14ae545119b88f4edcbd5922e639c1072a6d5dceb24e017b71cde46552076` and
  `616748004ebdefc9b25d43e2172584285539d3fb471fd16375f517ee4adb5c02`.
- At the post-check structural poll, EXP-456R1 was the sole CUDA client at 104/270 outcome-blind
  progress records; its stderr and all four watcher error logs were empty, all six expected
  processes were alive, and no intermediate scientific performance result had been inspected.
- A separate local Compose preflight was attempted without starting or changing any service. WSL
  reported no integrated `docker` command; the Windows Docker 29.6.1 client was present, but its
  Desktop Linux engine pipe did not exist. Therefore neither Compose validation nor an image build
  is claimed locally. The GitHub workflow retains both as mandatory CI checks, and Docker Desktop
  was deliberately not started while the sealed GPU experiment was active.
- A read-only public-commit boundary audit found 323 untracked, non-ignored files totalling
  3,116,361 bytes. Their extensions were limited to Python, Markdown, JSON, TeX, CSV, SVG, one lock,
  and one BibTeX database; the largest item was the 159,516-byte research dependency lock. No model
  weight, downloaded signal, compressed dataset, or other binary appeared in that candidate set.
  The local virtual environment, timestamped runs/launch logs, Paderborn RAR/parts, and downloaded
  MAT/CSV/ZIP fixtures were all confirmed ignored. A filename-only scan of the candidate set found
  no `.env`, credential/secret-key filename, AWS access-key form, GitHub token form, OpenAI-style
  secret-key form, or PEM private-key header. This is a bounded preflight, not authorization to add,
  commit, publish, or replace a dedicated repository secret scan.

## Exact orchestration-source retention in the evidence archive

- The public-boundary audit identified that the five exact shell launchers for EXP-456R1 and the
  EXP-457--463 handoff chain lived beside ignored runtime logs. Although the ledger and recorded-run
  metadata retained commands, the launchers themselves would not have entered either a public
  commit or the deterministic paper-evidence archive.
- The ignore rule now excludes every launch-directory product by default but re-includes exactly
  `run_*.sh`; all ten stdout/stderr logs remain ignored. Release version
  `smartvalve-bearing-evidence-release-0.9.1` adds the five launchers to its reproduction-source
  glob, without editing any live launcher or scientific implementation. Their SHA-256 values are
  `a9db53211667e94b4c96fa25604a74cf58034cc77629c10482293c6feffcc8b4`,
  `34fbd0c596d540bb879836b6f404b1451778ebe3df97158a7362a4cdeaafb68b`,
  `352dab43cb4c9bdda59b64d06d2e9bf4acd574adfc35cab40655e912c483f8ac`,
  `aca1c2dc2a752c2213026ef5c9f4e72283e2fe3b2eec34862122ba84f7f93b95`,
  and `6a696418d5debd983ae34e8b657760e6de9b8deb51f4b5fa7756941b3b6e8e87` in execution order.
- Sixteen focused deterministic-release and paper-package tests passed in the CPU-only environment;
  targeted Ruff and `git diff --check` also passed. The builder, release-test, and ignore-file
  SHA-256 values are `289eb7a24dfcd9346d7cc4a9e9ce9ea92dda9564d5775acf570f575abfa48f21`,
  `573650ddb6716fd3a61f680d861d9812de48e2a747e8d820d08d44c8026327cf`,
  and `e17621f1855c0bc7e724e9e77ccd25852124781ba885b0d98ebfa0a7eafb45c9`.

## Outcome-blind raw-protocol code audit during EXP-456R1

- A read-only review of the sealed training and inference path confirmed that each raw window uses
  only its own mean and standard deviation; all optimizer, scheduler, and epoch decisions use source
  training loss; the target-loader label is discarded by the inference loop; and no validation,
  early stopping, hyperparameter choice, or architecture selection reads a target outcome.
- The split implementation validates that source, target, and quarantine partition every record
  exactly once. For crossed access it independently reconstructs source as neither held axis,
  target as the held identity--setting intersection, and quarantine as the XOR partial-access arms.
  Every protocol targets every measurement record exactly once. Four window probabilities are
  averaged before seed ensembling, and the paired uncertainty calculation resamples physical
  bearing codes within class rather than windows, epochs, folds, or seeds.
- Eleven CPU-only execution-seal, Paderborn-partition, and raw-sensitivity tests passed. The only
  warning was the expected CPU notice that the immutable GPU-oriented loader's `pin_memory=true`
  has no accelerator; no sealed file was edited to suppress it. The audit did not inspect any
  intermediate score, probability, interval, or scientific finding from EXP-456R1.

## Synthetic visual preflight of the five final-figure layouts

- The five PDF layouts were generated from the bearing-artifact test fixture, not from scientific
  results, rendered through Poppler at 180 dpi, and inspected page by page. All were single-page
  vector PDFs with readable titles, axes, legends, and labels and no observed clipping, overlap,
  missing glyph, or broken geometry. This is only an early layout/style check; the real EXP-458
  figures and all numerical/table correspondences still require fresh visual review.
- The first inspection found one grayscale ambiguity in the protocol-profile legend: GroupDRO and
  CCDG both combined a dotted line with a circular marker and therefore depended mainly on color.
  Generator `smartvalve-bearing-paper-artifacts-0.9.1` changes only CCDG's marker to a square and
  adds regression assertions that all nine line-dash/marker pairs are unique and those two methods
  have distinct marker channels. No value, interval, order, label, protocol, or sealed file changed.
- All 11 bearing-artifact tests passed after regeneration; each of the five latest PDFs was rendered
  again, and a separate grayscale rendering of the protocol profile retained distinguishable legend
  encodings for all nine methods. Full-tree Ruff and `git diff --check` passed. Generator and test
  SHA-256 values are `89b9979a2d7f82e431468e61169fb81473ed0402b2fd4974f86934750ce63689`
  and `98917cc5ca2b9d181ed15944996acd3932801f4c8e650af807088daba4410a96`.
- A same-operation PDF portability check then found a Unicode em dash in the forest-plot row labels.
  It was replaced by an ASCII hyphen, and the existing generation test now rejects any en dash, em
  dash, non-breaking hyphen, or mathematical minus in every generated SVG. The 11 tests, Ruff, and
  diff check passed again; all five newest PDFs remained one page after Poppler rerendering, and the
  changed forest plot had no visual regression. Superseding generator and test SHA-256 values are
  `0c011a6dadd19e8a89d8d7f5a50612c9b5fb9a86cbea1b5df8e587e512265dac` and
  `63e8d982e5110451e4e6ab817431fc65317edfa0f441c620243d67509facfe40`.
- An optional, non-gating `ruff format --check .` audit reported that 121 historical Python files
  would be mechanically reformatted and 112 were already formatted. The formal quality contract is
  `ruff check .`, which passes; formatting is not silently recast as that lint pass. No bulk rewrite
  was performed because the proposed set includes seal-locked and already executed experiment code,
  whose byte hashes and provenance take precedence over cosmetic normalization.

## Checkout-pristine build staging and local package-build preflight

- A local `python -m build --no-isolation` preflight completed for both distribution formats. The
  402,588-byte wheel and 430,006-byte source archive have SHA-256 values
  `d1451d2ee303291bab72e3b01315583e57228572fe97fb68aedecf1fc5f541ce` and
  `737c744972bf33b42d114319c8eec8deea383b2d5b65839d0a1bf4022e118020`. Inspection confirmed that
  the wheel contains the paper-artifact generator, deterministic evidence-release builder, final
  quality gate, and RESS submission helper. A Windows-to-WSL shell-variable quoting mistake caused
  the two products to be emitted at the repository root rather than the intended temporary output
  directory; neither overwrote an existing path, and both were moved verbatim to
  `/tmp/smartvalve-build-preflight.lL70Fy`. This is a local buildability preflight, not a
  clean-checkout or published-package claim.
- That preflight also demonstrated that even a successful direct source-tree build creates ignored
  build metadata in the checkout. CI and the independent reproduction protocol therefore now use
  `git archive` on the exact tested commit, extract it into an external temporary build-source
  directory, and install from that external copy. The virtual environment, public inputs, JUnit,
  coverage data, logs, evidence hashes, distributions, and build metadata consequently remain
  outside the checkout, allowing the final empty-status assertion to detect actual source changes.
- PyYAML structural assertions located the real `verify` job and `Install locked dependencies`
  step, confirmed the external build-source environment and `git archive --format=tar HEAD`
  contract, and passed the extracted install block through `bash -n` with pipeline failure
  propagation enabled. The matching clean-protocol contract, full-tree Ruff, and
  `git diff --check` also passed. Superseding CI and clean-protocol SHA-256 values are
  `6697b27774142b52b3930bc0a6e11893955622bd96479c7547faf2a7eb48518e` and
  `c9448a7a3bb78ba740bc07980d98780dda07221ff02070ee3ca52313c3c2c5a0`. Because the intended public
  state is still an uncommitted working tree, installing the updated tree through `git archive` is
  intentionally deferred until an author-approved commit exists; the present evidence is static
  validation, not a clean-detached-checkout execution claim.
- At `2026-08-19T07:10:37Z`, EXP-456R1 had emitted 113/270 structured
  `raw_architecture_fit_complete` events. It remained the sole CUDA client; the raw parent, trainer,
  and four downstream watchers were all alive, raw and watcher error logs totalled zero bytes, and
  the GPU reported 81% utilization, 7,001/10,240 MiB memory, and 70 degrees C. No intermediate
  score, probability, interval, prediction, or scientific finding was inspected.

## Current-tree quality reruns and negative submission-scaffold preflight

- At `2026-08-19T07:20:10Z`, the isolated CPU environment completed the then-current 384-test tree
  with zero failures, errors, or skips in 471.97 seconds. Explicit source-path coverage remained
  `77.95036299172716%` over 11,846 statements. JUnit and coverage-JSON SHA-256 values are
  `c6a87345bd8e6b6b08b7f1cda240c74f6f88b77cf446d4728fe30b08ff1267d1` and
  `e33c089c897d476e69d4fe9850a77117295badb42112d53834a2c4881b06cc2c`. The only warnings were the
  retained scikit-learn SVC probability deprecation in a frozen legacy baseline and the expected
  no-accelerator `pin_memory` notice from the seal-locked raw unit test.
- A package-boundary regression test was then added. At `2026-08-19T07:29:41Z`, all 385 tests
  passed from scratch with zero failures, errors, or skips in 462.58 seconds and the same
  `77.95036299172716%` coverage over 11,846 statements. Its JUnit and coverage-JSON SHA-256 values
  are `0e5081a9d5d17dac4ea252bc426fbdebd1de120cdbc148b2916777e163425ff9` and
  `484d67da1612804928e726b1dcc00a2d377e3980caf9841c084cc3c45f348900`. Subsequent edits were
  confined to package/container metadata, CI/reproduction count assertions, documentation, and the
  matching static regression assertions; that targeted test, full-tree Ruff, YAML/install-shell
  static validation, and `git diff --check` passed afterward. The final recorded quality gate and
  clean detached reproduction remain mandatory.
- At `2026-08-19T07:14:57Z`, passing the working `RESS_SUBMISSION_PACKET.md` scaffold directly to
  the final RESS validator exited one with 18 explicit blockers. These included the intentional
  submission-hold markers, absent generated final sections, unfinished raw Table 6/Figure 3
  callouts, and missing human-approved commit, DOI, and AI declaration. Empty stdout and retained
  stderr have SHA-256 values `e3b0c44298fc1c149afbf4c8996fb934ca495991b7852b855` and
  `4f9ef91d2dde2e645ca6f1c155102fea24373f8a283eeb1f07f39a65adc50fb2`. This was a negative
  interface preflight demonstrating that a scaffold cannot be misrepresented as final submission
  materials; no fabricated author identity, DOI, or human-review confirmation was supplied.

## Distribution-license and container-context hardening

- Read-only inspection of the first local wheel/sdist preflight found that neither distribution
  contained the existing seal-locked `THIRD_PARTY_NOTICES.md`. The packaging metadata now lists
  both `LICENSE` and `THIRD_PARTY_NOTICES.md` under `project.license-files`. The declared
  build-backend floor was raised from `setuptools>=69` to `setuptools>=77`, matching upstream's
  documented first support for PEP 639 SPDX expressions and `project.license-files`; the audited
  build lock remains pinned at setuptools 84.0.0 and was not upgraded.
- A fresh non-ignored working-tree staging copy outside the repository built version 0.6.0 without
  isolation at `2026-08-19T07:31:13Z`. The 403,988-byte wheel and 430,124-byte sdist have SHA-256
  values `72545574441053fdaea57bbcb6dccae69d0d0ae4699e49b92396b882757eeb0d` and
  `8a16627a0abb2a525410abfd476f874f67c2666e73520abe93663732a9fef3b3`. Build stdout and stderr
  hashes are `06ffc0e70bc09c445f9bb01aeebd7ad3077ce5aee05c7a98e5020e642b72fb95` and
  `807e97125a07cf58c76bef6d9db88eabace05a8d396c6082665436b821e3923f`; stderr contained only the
  build frontend's five progress lines and no warning or error.
- Both distributions contain exactly one third-party-notice member. The source, wheel member, and
  sdist member independently hash to
  `c041cd33035298b03a0af72eff40762a76b5e2fbcaa3d9718f613c11c3b572f2`. Filename audits found
  zero raw-data/model/archive extensions, external-data directories, research-run directories,
  absolute paths, or parent-traversal members. A no-dependency install into an external target
  imported `smartvalve` from that target, reported version 0.6.0, and exposed exactly `LICENSE` and
  `THIRD_PARTY_NOTICES.md` under dist-info licenses. Install stdout/stderr hashes are
  `9f0afb76395de9ad8013502bf05035cddf950b99368456332d94cb1bd5839389` and the empty-file hash
  `e3b0c44298fc1c149afbf4c8996fb934ca495991b7852b855`.
- Static container review found that the builder did not copy the newly declared license files and
  that the root Compose context would have admitted the 1,606,675,017-byte
  `artifacts/research` tree, including restricted experimental payloads, plus the 1,095,143-byte
  external-code mirror. The Dockerfile now copies both license files before building, while
  `.dockerignore` excludes `artifacts/research/` and `artifacts/external/`. A regression test locks
  all four packaging/container conditions. This is a source/context hardening pass only: Docker
  Desktop's Linux engine remained unavailable, so no local Compose or image-build pass is claimed.
- Current SHA-256 values for `pyproject.toml`, `Dockerfile`, `.dockerignore`, the packaging test, CI,
  clean protocol, readiness checklist, and paper reproducibility statement are respectively
  `e487f36a0a49a6fca1df21c64924739a59e0181a486a6734ae5488f3ba09273f`,
  `38eda6660b829e9835f3465c76f6ccd6adc617b7e505c9d583785fb5112e87c3`,
  `acd5797a0900667ad3ae0edf1c05ea4158f7c7d7ebebfa56fedd6e4fda394274`,
  `a80d6d601e63d964187b85010509f29fbee86442932df74785da2f381cb73e1f`,
  `87e927c450dbdbd917a8fba171521a166692a8c81b8368ee36447a01b4f1bd4b`,
  `ef2117fc2bc77bc7f9d9616b0a8f6add4e41546e01bb1f49f901c13fe1626a09`,
  `7936fcb013248e6df30e331621e8c670deece7e31481469d2a66050ef3631bd5`, and
  `9bd78393119b511766ead5f60437ef59ce651f00b2eda10ff7f6933fdf422550`. CI and the future clean
  reproduction now require at least 385 tests; the already running final-quality watcher retains
  its predeclared 384 floor but will record the actual current topology rather than modifying its
  live launcher.
- At `2026-08-19T07:32:02Z`, EXP-456R1 reached 121/270 structured completion events. All six
  expected processes remained alive, the raw and watcher error logs were empty, and the sole CUDA
  client reported 82% utilization, 7,007/10,240 MiB memory, and 71 degrees C. No intermediate
  scientific outcome was inspected.

### Empty-file hash transcription correction

- The immediately preceding RESS negative-preflight and wheel-install paragraphs each abbreviated
  the empty stdout/stderr SHA-256 incorrectly during ledger transcription. The exact empty-file
  SHA-256 in both cases is
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. The retained non-empty
  stderr/stdout hashes, exit statuses, and all underlying files are unchanged.

## Positive-control-qualified public secret scan

- No dedicated secret scanner was installed in WSL. Official release assets were downloaded only
  under `/tmp` and checked against their published checksum files. Gitleaks 8.29.1's Linux-x64
  archive matched SHA-256 `e4eb209d04e20339d77122a3bdf9cd41351255cfb27ebcb75e85325e04f88924`;
  its extracted binary hashes to
  `2d248645545650fa16eaa61424c86bd2d22646a7205a06b5942d86e8a48c0dd1`. However, it returned exit
  zero and an empty report for a synthetic canonical GitHub-PAT control. Its empty JSON report,
  stdout, and stderr SHA-256 values are
  `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`,
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, and
  `25364d5f63b8f83106bf81fef88deba6a5192a44f9fc165f55c2ba7647b3b593`. Version 8.29.1 was
  therefore rejected rather than used to generate a misleading clean result.
- Gitleaks 8.18.4 was selected as the explicitly reported working control version. Its official
  Linux-x64 archive matched SHA-256
  `ba6dbb656933921c775ee5a2d1c13a91046e7952e9d919f9bac4cec61d628e7d`, and the extracted binary
  hashes to `46a05260e7cce527f132cb618de59d22262b8b5eb47f66c288447b95c7a98b7e`. The same synthetic input
  returned the expected exit one with exactly one redacted `github-pat` finding. Report, empty
  stdout, and stderr SHA-256 values are
  `0398a2bae69926e1cc3270f81b2912e4938579a233dc1ec35b06e2e4e7603662`,
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, and
  `d6b1ed30c2fa1747d9a9070d2297deb9eb864d25f40ffcbb77348405c9538ee8`. The synthetic token and
  all scanner binaries/reports remained outside the repository.
- A fresh candidate tree built from the exact union of cached and non-ignored untracked files held
  431 files and 6,850,168 bytes. The qualified scanner returned exit zero with zero findings.
  Redacted JSON report, empty stdout, and stderr SHA-256 values are
  `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`,
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, and
  `edd8f1a9ec3ee54620456a30b43f83ce2fe7189748a6dd2e948fbec485d84403`. A separate Git-mode scan
  covered all three existing commits and also returned exit zero with zero findings; its report,
  empty stdout, and stderr hashes are the same empty-report hash,
  `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`, and
  `b9c46e84a690e158d6a1514b9861ebff4f1857a2cd4152decc10e24c2d794457`.
- This is a bounded scanner preflight, not proof that no credential can exist and not permission to
  publish. It must be repeated against the exact author-approved commit and release archive. The
  readiness checklist now records that distinction and has superseding SHA-256
  `9999de0bb7da52d1b67c4cac7e5c7d1f3f86339c25d720d0491ad07f41627338`.
- At `2026-08-19T07:37:30Z`, EXP-456R1 reached 123/270 structured completion events. All six
  expected processes remained alive and all raw/watcher error logs remained empty; no intermediate
  scientific outcome was inspected.

## Engine-free Compose overlay validation

- Windows Docker Compose v5.3.0 successfully parsed the WSL project through its UNC path without
  connecting to or starting Docker Desktop. Base `compose.yaml` passed `config --quiet`; the
  base-plus-TLS overlay also passed. An intentionally incomplete base-plus-SSO attempt using the
  checked-in `.env.example` stopped on the required blank OIDC cookie secret, confirming that the
  production guard is active rather than silently substituting an empty credential.
- The operational full stack (`compose.yaml` + `compose.tls.yaml` + `compose.sso.yaml`) then passed
  `config --quiet` with explicit process-local `ci-only` client ID, client secret, and cookie-secret
  values. No `.env` file was written, no service or image was created, and no real credential was
  used. The workflow now makes base, TLS, and full-SSO configuration validation mandatory before
  its existing image build. PyYAML semantic checks and `bash -n` passed for that exact CI block;
  full-tree Ruff and `git diff --check` also passed.
- Superseding CI and readiness-checklist SHA-256 values at `2026-08-19T07:40:05Z` are
  `403aef4667681f95f4c813560cb7fad8b33f7b8f307aaeab0b633622be646528` and
  `1ee84cdc8572799d09c860cd6e4720c4927bdc569bba6cd83820ea627a959508`. The local image-build gate
  remains open until a Linux engine is available; the Compose pass is not presented as an image
  build or runtime smoke test.
- At the same poll, EXP-456R1 remained at 123/270 structured completion events with all six
  processes alive and all error logs empty. No intermediate scientific result was inspected.

## Bibliography DOI resolution and registered-metadata audit

- A no-body HTTP audit parsed 28 unique DOI fields with zero duplicates from
  `paper/references.bib`. All 28 redirected away from doi.org to a registered publication/data
  domain: 24 ended with HTTP 200, three with 202, and one SAGE landing page returned 403 after an
  unambiguous 302 resolver redirect. There were zero unresolved identifiers. The temporary audit
  script and complete resolution report have SHA-256 values
  `1be6054b527f4e2b9eab44cc2f92cf72a89315f9fa64812d4c4ec63aaaf985b8` and
  `35b3d081a312f1596c77144f3c28064f0ae45b18d3702a311ceb53692d2f36b6`.
- A first CSL content-negotiation comparison incorrectly truncated BibTeX titles containing nested
  braces such as `{CORAL}`, `{CWRU}`, and `{HUST}`; another request received a transient Crossref
  429. These were audit-tool failures, not bibliography mismatches. The temporary parser was fixed
  to consume the complete single-line braced value, concurrency was reduced, and bounded 429
  retries were added before repeating the entire comparison.
- The corrected audit received HTTP 200 CSL metadata for all 28 identifiers. Twenty-seven titles
  and all 28 publication years matched immediately. The sole real discrepancy was the Mendeley
  Data citation's abbreviated title, `{HUST} Bearing`, versus its registered title, `HUST bearing:
  a practical dataset for ball bearing fault diagnosis`. Only that BibTeX title was expanded; DOI,
  authors, version, year, publisher, citation key, and manuscript text were unchanged. The final
  rerun passed 28/28 title and 28/28 year comparisons with zero transport errors.
- Final bibliography, corrected metadata-audit script, and final CSL report SHA-256 values are
  `65eb7b9958366ee12cb11e44fe3fb1ce7ae8d1cc92024ac9afd346c9c6bdf857`,
  `91c0ec3d5811dde74630df0c7232eab6b3c1f1786e112157e93f37b3f50b970c`, and
  `baa2ff8921aee78e5e830408efd229f5b110eca50eecf4e052ffc9a5d2879a78`. Thirty-two focused paper,
  RESS-submission, and deterministic-release tests passed afterward; full-tree Ruff and
  `git diff --check` also passed. The superseding readiness-checklist SHA-256 is
  `50e9f1206d0d069c2c9497fa28afea9f880ee5cdd11097b74f2fc52cd49d62af`.
- Resolver and metadata agreement cannot establish that every paper supports every prose claim.
  Final author-by-author reference and claim verification therefore remains an explicit human
  submission hold. At `2026-08-19T07:44:48Z`, EXP-456R1 reached 125/270 structured completion
  events; all six expected processes remained alive, all error logs remained empty, and no
  intermediate scientific outcome was inspected.

## Internal RESS DOCX layout preflight and OOXML audit

- A style-driven internal layout preflight was generated from `paper/BEARING_MANUSCRIPT.md`
  (SHA-256 `2cab0c44e4d9f38236ea57adbca6ba0f07e3c7e2c9683190d80abb015611c9fb`) with the
  `narrative_proposal` design preset and `memo_masthead` first-page pattern. The builder, output,
  and all audit evidence remained outside the repository under a temporary Windows directory; no
  DOCX was represented as an author-approved or venue-ready submission artifact. The final builder
  SHA-256 is `3cfa6d1ff57c8e8f85421ef4c4adfe58b10f32140ad36fe66355262a9db7f42c`.
- The 66,684-byte working DOCX contains 189 package-level paragraphs, including 52 true Heading
  paragraphs, 21 real list-style paragraphs, five tables, and one explicit working-status callout.
  Its SHA-256 is `73d012ea194f8f4c2ed09f9350dc9ef6b6c2629a4a8f8554994198a57ad0bf0d`.
  The packaged style linter found 34 direct run-formatting instances, down from 546 in the first
  draft, 318 direct paragraph-formatting instances, and zero heading-like paragraphs outside true
  heading styles. The final style report SHA-256 is
  `ef8a355f5d2037a1c4215628f6cbd8fb4bde86eb4ef409520a33f3bc2ca0a561`.
- The first custom OOXML audit correctly remained failed while its own implementation was reviewed:
  it treated explicit `w:b w:val="0"` values as bold, compared case-sensitive built-in heading
  names, read numbering identifiers from child elements instead of attributes, and expected an
  unrepresentable quarter-point font size. That retained failed report hashes to
  `9a3b6bdff0c7e8d732ff1f09f6cd76c4a012342834bb82850358c0cffd0f6d33`. The audit was corrected,
  and the table text styles were set to a representable 8.5 points before the DOCX was regenerated.
- The corrected OOXML audit returned zero failures. It verified one portrait US-Letter section with
  one-inch margins and a different first page; Calibri style tokens; 13/23/16 Heading 1/2/3
  paragraphs with no hierarchy jump; all 21 list paragraphs backed by decimal or bullet numbering;
  and five 9,360-DXA fixed-layout tables with a 120-DXA indent, exact grid/cell width agreement, no
  fixed row heights, and repeating first rows. It also found zero macros, comments, tracked changes,
  drawings, external relationships, unresolved placeholders, Codex directives, or local paths. The
  corrected audit script and passing report SHA-256 values are
  `d619ed5e52ffce4be81800d7725261011735599600aefae1e1a16a340fa8766f` and
  `e0000678b3d7228b21063885e65b6ee5589c5887186f6c141136271627655fe7`.
- The required final render attempt returned exit one before producing a PDF or page images because
  no LibreOffice `soffice` executable was available (`FileNotFoundError: [WinError 2]`). Microsoft
  Word was also absent from the accessible desktop-app inventory. This is therefore a structural
  preflight only: page-by-page visual QA, final venue-template generation, and inspection of the
  final empirical figures remain explicitly open.
- At `2026-08-19T08:01:34Z`, the sealed EXP-456R1 run reached 135/270 structured completion events.
  Both raw-training processes and all four registered downstream watcher processes remained alive,
  raw-run error logs remained empty, and the GPU reported 75% utilization, 4,364/10,240 MiB used,
  and 70 degrees C. No intermediate scientific outcome was inspected.
- Repository-wide Ruff and `git diff --check` passed after the readiness record was updated. The
  superseding paper-readiness checklist SHA-256 is
  `7750b3afd18f4d447d930658d970813b9fa5ffbd48b4e377fe7618311a6e3ed8`.
- Fifty-four focused manuscript, paper-artifact, RESS-submission, package, and release tests passed
  with zero failures, errors, or skips in 1.701 seconds. The external JUnit XML SHA-256 is
  `4995ee5dca55a55074e7b584815d86774d52b9b016cb623efd4c25dbcc5e93b0`.

## Recent-work citation-context spot audit

- A primary-source spot audit rechecked the frozen manuscript's highest-risk recent-work sentences.
  Panić et al.'s RESS record supports the more-than-600,000-evaluation, task-pipeline, and cross-
  collection reversal statements. Vieira et al.'s author v5 supports the four-dataset scope,
  bearing-wise design, fixed-model leakage tests, and representation/model sensitivity statements.
  Kaya and Jobani's open full text supports the separate measurement, condition, and bearing-code
  evaluations and explicitly leaves combined bearing-code/condition holdout as future work. Knap et
  al.'s PHM record and pinned repository support the six fixed, recording-separated scenarios and
  the separate raw/FFT/STFT operating-condition and bearing-instance tasks.
- Wan et al.'s March-2026 PI-FSL paper was screened as a newly surfaced compound-shift neighbour.
  Its combined machine--operation target is a Bosch tool-wear task with labelled few-shot target
  support; its HUST and Paderborn bearing scenarios are single-axis two-way five-shot transfers. It
  therefore does not replace the current closest target-free physical-identity × setting access
  comparators. The hash-locked manuscript was not edited, and the full bounded decision was appended
  to `research/LITERATURE_SEARCH_LOG.md`, SHA-256
  `0eb89cbc7ab2016268d65ea32731b50e29c973bf5cdf46f176066d57afcbb7dc`.
- This was a bounded spot audit rather than author-by-author semantic verification. Final human
  reading and a submission-day citation-forward search remain open. At `2026-08-19T08:09:23Z`,
  EXP-456R1 reached 140/270 structured completion events; both raw processes remained alive, raw
  error logs remained empty, and the GPU reported 72% utilization, 4,354/10,240 MiB used, and 69
  degrees C. No intermediate scientific outcome was inspected.
- `git diff --check` passed after recording the audit. The superseding paper-readiness checklist
  SHA-256 is `e842dfee6ded5b49c2b102984ee1e23d36ca0b38d68e386f3d5e300b3d4eca9e`.

## EXP-474 expanded static-security scope correction and post-fix preflight

- A claim audit found that earlier ledger/reproducibility prose called Bandit "full-source" even
  though the exact command scanned only `src/`. The first genuinely expanded command,
  `.venv/bin/bandit -q -r src scripts research/scripts -ll`, returned exit one. It exposed two
  medium-severity B310 findings: `scripts/acquire_hust_d3_primary.py:60` and
  `scripts/hust_d3_metadata_inventory.py:50`. This is a real retained failure in the research
  record; it was not reclassified as a harmless pass. The interactive first-run output was not
  captured as a machine-readable file, and the retained summary explicitly records that evidence
  limitation.
- Neither finding was suppressed. Both network helpers now parse the URL before access, require
  HTTPS, require the exact `data.mendeley.com` hostname, reject embedded usernames/passwords, and
  use the already hash-locked `requests` dependency with bounded timeouts and HTTP-status checks.
  Five hostile URL families (`file:`, HTTP, hostname suffix confusion, userinfo host confusion, and
  credentials on the allowed host) are rejected by both helpers, while exact Mendeley HTTPS URLs
  are accepted. No dependency-lock or scientific-data semantic change was required.
- The first focused-test implementation incorrectly tried to import the top-level `scripts/`
  directory as a Python package and stopped during collection with `ModuleNotFoundError: scripts`.
  That test-harness failure is retained rather than hidden. The test now loads the two executable
  scripts with `runpy.run_path`; application code was not weakened to accommodate the test.
- The exact expanded Bandit topology is now enforced in CI, the Makefile, EXP-461Q's final-quality
  command map, and the clean-reproduction protocol. The deterministic release defaults now include
  `research/scripts/*.py`, and a release test specifically verifies that
  `research/scripts/validate_paderborn_split_manifest.py` enters the source set.
- The recorded post-fix Bandit 1.9.4 run exited zero. Its JSON reports 42,855 lines of code, zero
  medium/high findings, 25 low-severity detections, seven pre-existing explicitly skipped tests,
  and an empty result set at the `-ll` threshold. Report SHA-256 is
  `092e8b025f895bf9d1e9473e0851eb5937088ca3c8165287b9f54e5ba2664f40`.
  Twenty-one focused final-quality, URL-security, and release tests then passed with zero failures,
  errors, or skips in 0.760 seconds; JUnit SHA-256 is
  `f62e9bbff539809b5bbbe4dc66adb6fe42f955e2e82a6bd6a9a83697512e59bd`. Full-tree Ruff 0.15.21
  returned an empty JSON result (SHA-256
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`), CI YAML parsed, and
  `git diff --check` passed.
- The retained EXP-474 directory is
  `artifacts/research/runs/EXP-474-EXPANDED-STATIC-SECURITY-PREFLIGHT__20260819T081739Z__postfix`.
  Its structured summary and README SHA-256 values are
  `312b887969599cc1406b4a3ed7e0bba88573214eeb9ac3ac3333504770d5ca12` and
  `51f35856c9711765e3572680490a5efba144adca9aebae27ae04b8ac4965749b`. The two fixed network
  scripts hash to `c5fa987cfda194373e309a8f12e5d8caf1c6278ec040a287fac721b6b7fd95bd` and
  `cd2c15b8041ed88a67a598206ddee615f9d1cf08bc5cffff91cd5d1d5e831bb4`; final-quality and release
  modules hash to `7f92334518f5d66233db868a94fe84902460915c2c9f55c148630629a8d06368` and
  `368ccc7b06ac26d79caf7ba3324dadb3f62a33bd6580eefac671ed56b70c21f2`.
- The scope correction was appended, rather than silently rewriting prior historical test records,
  to `paper/REPRODUCIBILITY.md`; its new SHA-256 is
  `f2ebfb8746b04586eae07399fc5c62c1b8c3d68caa48658ce087485cfa569080`. The readiness row now calls
  this an expanded application/project-script preflight and hashes to
  `eba0bbdb9e4914b79d1f0f3268d80280805abc02d05eadc2b02fa8eb5e9ae4e0`. EXP-474 remains a local
  preflight, not formal EXP-461Q/461V, a clean-checkout reproduction, external review, or submission
  readiness.
- At `2026-08-19T08:19:30Z`, outcome-blind monitoring showed EXP-456R1 at 145/270 structured
  completion events. Both raw processes and all four registered downstream watchers were alive,
  raw/watcher error logs remained empty, and the GPU reported 70% utilization, 4,446/10,240 MiB
  used, and 69 degrees C. No intermediate scientific outcome was inspected.

## EXP-474R1 redirect-hardened security supersession

- A behavior-level follow-up found that EXP-474's entry-URL validation was necessary but
  incomplete: the live Mendeley file endpoint returned HTTP 302 to
  `prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com`, while `requests` follows
  redirects automatically unless told otherwise. The complete EXP-474 directory and hashes remain
  unchanged as the intermediate record. EXP-474R1 supersedes only its security-completeness claim.
- The download path now passes `allow_redirects=False`, permits at most one manual hop, and validates
  HTTPS, exact hostname, port 443/default, and absent URL credentials separately for the Mendeley
  entry and exact observed S3 storage host. Missing locations, additional hops, unallowlisted hosts,
  non-2xx terminal statuses, and malformed ports fail closed. The metadata API now disables and
  rejects every redirect. No `nosec` or Bandit exclusion was added.
- An end-to-end streamed-header probe invoked the production helper against the first sealed HUST
  file URL. It exited zero, manually reached the exact allow-listed S3 object with status 200, and
  returned a final Requests response with `history_length=0`, confirming that Requests' automatic
  redirect chain was disabled. The response was closed without iterating or writing the signal
  payload. The retained probe SHA-256 is
  `3ca53384a2868a3af48fdf806e4149cc7912270ee8a7fa6a92d19278f9a9b001`.
- The hardened test family adds port rejection, exact-storage-host acceptance, evil redirect
  rejection before a second request, explicit `allow_redirects=False` assertions on both hops, and
  metadata redirect rejection. The final focused run passed 26/26 tests with zero failures, errors,
  or skips in 0.723 seconds; JUnit SHA-256 is
  `b338ae22f012c0b7046afeef0bb92eb016a45e3a005b6021bd2740b352cceead`.
- Expanded Bandit 1.9.4 again exited zero. Its JSON records 42,912 lines, zero medium/high findings,
  25 low-severity detections, seven pre-existing explicitly skipped tests, and an empty `-ll`
  result set; SHA-256 is
  `661adfc34c68d551a38b4cad6132681c7b4a3156a55fba4c1ebec85e3c937a7b`. Full-tree Ruff returned an
  empty JSON result with SHA-256
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; CI YAML parsing and
  `git diff --check` passed.
- The final acquisition helper, metadata helper, and redirect test SHA-256 values are
  `e24fa282a86b9c1565cc4e8f43a85bfbd78d7cde5b57ac86950b564c15445f40`,
  `1714393a03b5ddf8bf55d92beb50e03c8d6a53258b3026e66936fb88e9e5916f`, and
  `261cb4930fc1eb979bd7e88adc973990b3e996ef0696cf99591d8ef780ac37a5`. The retained R1 summary and
  README hash to `edd9f759f169933abb665317d70fe394bc6fcef013974581ec798f7f56d4b44b` and
  `bda2c2bc0cc0aa539b855ea409c3b9bf6145db5585e14dbde5d10810aca40242`.
- The append-only reproducibility correction now hashes to
  `f07ee5e1fc66c9db0dd9f5e1e5a04d909d3d2e95bbc344905fb99e51c5120cbd`; the superseding readiness
  checklist hashes to `cb0d41be2c68694592efd49439763b7755dd3943f40a3edfdebaeba5e8f378bd`.
  EXP-474R1 remains a local preflight, not formal EXP-461Q/461V, a clean-checkout reproduction,
  external review, or submission readiness.
- At `2026-08-19T08:27:25Z`, EXP-456R1 reached 150/270 structured completion events. Both raw
  processes and all four registered downstream watchers were alive, all monitored error logs were
  empty, and the GPU reported 76% utilization, 4,377/10,240 MiB used, and 67 degrees C. The raw
  protocol seal and working manuscript retained their expected SHA-256 values
  `d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b` and
  `2cab0c44e4d9f38236ea57adbca6ba0f07e3c7e2c9683190d80abb015611c9fb`; no intermediate scientific
  outcome was inspected.

## EXP-476/477 pre-outcome raw prediction-topology audit and release integration

- While EXP-456R1 was still running at 160/270 structured completion events, a no-outcome audit
  identified a remaining evidence-topology gap: EXP-457 independently recomputes aggregation,
  physical-bearing bootstrap, metrics, and the sealed gate, but total-row checks alone do not bind
  every prediction row to the authoritative 2,319-record cohort, the four EXP-455 windows, and its
  frozen target fold. No checkpoint probability, aggregate, score, interval, rank, or gate value
  was inspected before defining the additional validator.
- `research/PADERBORN_RAW_TOPOLOGY_AUDIT_PLAN.md` was frozen at
  `2026-08-19T08:44:43Z`, SHA-256
  `d83ef59c4648899fc1f5d7cb187be92758f8e797ce66a53c17cffbae2bf6fb4a`. It locks the feature,
  raw-window, and raw-seal inputs and freezes the implementation/test hashes. It explicitly limits
  EXP-477 to expected-key, physical-metadata, training-diagnostic, and probability-health checks;
  the validator cannot refit, recompute aggregate metrics, or read the scientific gate.
- EXP-476 completed before EXP-456R1. The retained directory is
  `artifacts/research/runs/EXP-476-PADERBORN-RAW-TOPOLOGY-MANIFEST__20260819T084548.389414Z__outcome-blind-exact-raw-prediction-key-manifest`.
  Its outcome-blind manifest SHA-256 is
  `440b6e9f3a5c156a3b022a7ea8a5667de33c8bc954c3223f73df5be53f622607`; metadata SHA-256 is
  `9876546deb35623baf617a3ccffb5e8bb306281b34ed598bd15157f7f9e5d992`. The manifest freezes
  exactly 166,968 window-prediction keys, 41,742 seed-recording keys, 13,914 ensemble-recording
  keys, 270 fit keys, and 270 trace identities. Their canonical SHA-256 values are respectively
  `dbf1a2921b0b2578eb9941e5a736c1fc7acb06b0d4ec143a190ca14924c280c9`,
  `3210779f5d0a35897a0d4879953d88a9ff14409057eb59bcc1e6d447c892b2d0`,
  `49da2482574de5c17b69dbef1b5a203d503c972cc8c006a8d820c91c6adb5434`,
  `21ef6c8826f90d4d2784b7c06a662885c87b940c50bbbad86e290477927db9c8`, and
  `f46303ef6b30576c8221531c4a3a450c08b167f34edeed82e6f778188ad16505`.
- The EXP-457 watcher now runs EXP-477 immediately after the sealed metric validator. EXP-458/459
  are blocked until both validators complete and until EXP-477 reports the exact five counts,
  `refit_performed=false`, `aggregate_metrics_recomputed=false`, and
  `gate_outcome_read=false`. The deterministic release was advanced to version 0.10.0; it now
  verifies, includes, and independently rehashes both the EXP-476 manifest and EXP-477 validation.
  The release module, CLI, test, and three modified watcher SHA-256 values are
  `65e0745be392932be34fb22d9bd5a21bdf8582700fc45ed93df54e7129c2a315`,
  `0176f8c0d99cf648faef35aa9eabd1daae97a1a92390f4b3523c66bc39666bb3`,
  `15d77584671031c149f32d540ea85311cb7d33ace2a9f8fac47e93fb47a35dc2`,
  `6f060600da277f97ba5782e58a4b882617e2ec479aad9df29aa1ceae05fabdc7`,
  `f0a40663437ef7a02801c5f74796328d58981957dede20911e6961adba7251e3`, and
  `f3820b9787c98bf40ed776fc7e3c0391c6145361a82b06010efde9c781c6c826`.
- The three affected waiting-only watcher processes were deliberately stopped while their scripts
  were patched. The sealed recorded-run and raw-training PIDs `888545` and `888570` were not
  stopped, signalled, restarted, or edited. After Ruff, focused release tests, and all four Bash
  syntax checks passed, the watchers were restarted as PIDs `1032129`, `1032137`, and `1032148`;
  the unchanged manuscript watcher remained PID `944481`. At `2026-08-19T08:55:37Z`, all four
  watchers and both raw processes were alive, all three restarted watcher error logs were empty,
  and the GPU reported 63% utilization, 4,512/10,240 MiB used, and 65 degrees C.
- EXP-478 retained a CPU-only, `CUDA_VISIBLE_DEVICES`-empty integration preflight over the four
  frozen topology tests and ten deterministic-release tests. All 14 tests passed with zero
  failures, errors, or skips in 21.692 seconds. The run metadata and JUnit SHA-256 values are
  `059600d63c5c2809c77308fff1b903e031639773aa746db0e77d6a73a7d01af6` and
  `c194bf6333e87cb23cf673b5a94cd1ee784e9dd9e0a756645f6c88fb7beb1950`. Full-tree Ruff, Bash
  syntax checks, and `git diff --check` also exited zero. Updated readiness, reproducibility, and
  external-review packet SHA-256 values are
  `19be84471479439b7fab29e55bcaacba6b457b7f0ad9a2c4803acd97c1f31da3`,
  `2ad8991211c981e577be03bc41e7999c9f7e9efb1304bc0f8ef525a98e3b96d6`, and
  `6304822aa7460adf8557007317a15797a172ee7c2b9767d12a603770be895b7f`.
- At `2026-08-19T08:54:50Z`, outcome-blind monitoring showed EXP-456R1 at 166/270 structured
  completion events with zero monitored errors and both raw processes alive. EXP-476 and EXP-478
  are audit/preflight evidence only. EXP-477 remains pending until the producer has written and
  hash-locked its final outputs, and none of these records imply that the raw scientific gate,
  final manuscript, clean reproduction, human review, or submission-readiness gate has passed.
- A subsequent no-cache, bytecode-disabled `pytest --collect-only` completed without collection
  errors and enumerated 397 tests in 3.72 seconds. This records the current topology only; it is not
  relabelled as a 397-test pass, and full execution remains assigned to the formal downstream
  quality gate.

## EXP-475 RESS submission-text integrity preflight

- A requirement-by-requirement audit of the journal-facing validator found two package-integrity
  gaps. The submission-material title was not compared with the manuscript title, and `_sections`
  would silently retain the last occurrence of a duplicate level-two section. Both behaviors could
  allow an internally inconsistent upload package even while abstract, commit, DOI, and AI
  declaration checks passed.
- Validator version `smartvalve-ress-submission-validator-0.8.0` now requires exactly one manuscript
  H1 title and equality with the submission-material article title. Normalization is intentionally
  limited to whitespace and the Markdown `--` versus typographic en/em-dash representation. It
  separately rejects duplicate level-two headings in both documents before parsing their content.
  Existing keyword-count, highlight-count/length, and 5,000--13,000 validator-word constraints now
  have explicit negative tests as well.
- The focused RESS, empirical-manuscript, and deterministic-release family passed 37/37 tests with
  zero failures, errors, or skips in 0.767 seconds. JUnit SHA-256 is
  `347abebaac3f9114e7164e39ff29490d9f7597924963d524e0456bd7a0bfa40c`. Full-tree Ruff returned an
  empty JSON report with SHA-256
  `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`; `git diff --check` passed.
- Expanded Bandit 1.9.4 exited zero over 42,948 lines with zero medium/high findings and an empty
  result set at the `-ll` threshold. Its JSON SHA-256 is
  `628d7d19377513a6dc3cdf535cf89bb48245e8ea578f6401c3bbc6534ac84d21`. Final validator and test
  source SHA-256 values are `3f0e40913f6abf4f56778e9fb1a591e66a054aa40287c2f950d58349e4018ff0`
  and `3dc47bd735cfca1f1e476b4199d415da65433e4cb30b9dc752201ccd01838b22`.
- A current official-source check used the directly readable RESS journal page and Elsevier data
  policy. The journal page continued to place automatic fault detection/diagnosis, data analysis,
  uncertainty, and substantive complex-system reliability problems within scope. Direct navigation
  to the official Guide for Authors at `2026-08-19T08:32:52Z` presented a CAPTCHA. It was neither
  solved nor bypassed. Therefore the existing automated format checks remain a local preflight and
  submission-day human line-by-line verification remains open.
- The retained EXP-475 summary and README hash to
  `3fbc38596872547f3b9eb70bd5d2725cb2c3a3539a18996fea0a2bba73895835` and
  `65a2ca114579ac88a32e560c552ce3dd8ebd215f14d9d18faec1eb21a88a5990`. Updated submission strategy,
  reproducibility record, and readiness checklist SHA-256 values are
  `139eeae3677174745a1f3949d0a892cc029ee3cafcad2780f867bc63e32a17d2`,
  `5f9152b9e429b557ad81ebfcddb7724b62ae00e4cb8048f1f63ecdb9f6218f47`, and
  `dcd09ed6e00c5b235a7db759ade39a3cbbb96b5b965b224644f566a9cf00ac4a`.
  EXP-475 does not claim a final empirical manuscript, human review, clean reproduction, or
  submission readiness.
- At `2026-08-19T08:37:01Z`, outcome-blind monitoring showed EXP-456R1 at 156/270 structured
  completion events. Both raw processes and all four downstream watchers were alive, monitored
  error logs remained empty, and the GPU reported 74% utilization, 4,428/10,240 MiB used, and 67
  degrees C. The raw seal and locked working manuscript retained SHA-256 values
  `d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b` and
  `2cab0c44e4d9f38236ea57adbca6ba0f07e3c7e2c9683190d80abb015611c9fb`; no intermediate scientific
  outcome was inspected.

## EXP-479--481 RESS working-PDF, editable-Highlights, and full-regression preflight

- A submission-boundary audit added deterministic Markdown/BibTeX-to-PDF rendering without
  changing the hash-locked working manuscript or any empirical result. Renderer version
  `smartvalve-ress-pdf-renderer-0.1.1` embeds DejaVu fonts, fixes PDF metadata, renders numbered
  citations/tables/lists, rejects final-mode hold markers, and requires exactly five one-page main
  figure PDFs in final mode. Working mode applies an explicit `WORKING PREFLIGHT - NOT FOR
  SUBMISSION` watermark and cannot return `submission_ready=true`.
- All four visual iterations are retained. EXP-479 exposed literal H4 Markdown, a truncated long
  header, excessive justified spacing, and weak reference separation. EXP-479R1 corrected those
  items but page-by-page inspection found a body/heading baseline collision and two adjacent
  reference entries without enough visible separation. EXP-479R2 corrected heading/reference
  spacing; its full 19-page inspection then exposed indented Markdown continuation lines detached
  from numbered items. EXP-479R3 joined those continuations inside their list items and added a
  regression test. The four run-metadata SHA-256 values are
  `89ac410b97b9025a208dbc9c9df2f412c337e957196ffed443bccc9fcf5588db`,
  `66590438b65026911b3486f1e22f285b5db5bed95f8f796379b3f5eb94072c1f`,
  `be8fe145faad2766d7022857f19c1a0c727a209e0b7d5240ed89b747e038f434`, and
  `3f58c1b66d62d70576a41f3d46fd3b70becb2ed347b835705d37aad0549a8b1d`.
- The superseding watermarked PDF is 127,721 bytes and 19 A4 pages. pypdf reports zero blank pages,
  9,078 manuscript words, 28 cited references from 43 bibliography entries, zero main-figure PDFs,
  and five expected working/final hold markers. Poppler independently reports 19 unencrypted,
  unrotated A4 pages and fixed 2000-01-01 metadata. All 19 rendered PNG pages were inspected after
  EXP-479R3; headings, multiline lists, tables, margins, footers, and references were readable with
  no observed clipping or collision. This is agent visual preflight only: the report deliberately
  retains `human_visual_review_complete=false`, `machine_render_complete=false`, and
  `submission_ready=false`. PDF and report SHA-256 values are
  `968f6c9a56d0207c7d38d7994d5430561d8811d8cba2e983fd4558492755fea3` and
  `7c4e4ef9f89b3893f87e530238c9b5625348eb40e113e550c4579de9a69c05fb`.
- A secondary cached copy of the journal guide exposed an upload requirement not covered by
  validator 0.8.0: Highlights must be supplied as a separate editable file. Because the directly
  requested official Guide remained behind a CAPTCHA, this remains a local preflight pending a
  submission-day official human check. Validator 0.9.0 now generates a separately named
  `*highlights*.txt`, requires `.txt`, three-to-five ordered bullets of at most 85 characters, and
  exact equality with the submission-material Highlights section. Drift, non-bullet text, an
  unsuitable extension, or a filename without `highlights` fails closed. Renderer, validator,
  generator CLI, validator CLI, and the two test files hash to
  `5a19e4e172ec13a6ba356d7c35bc44bc0a00823135c9d7fdc49265e346a5d921`,
  `a59aa2d62b63be8d58011e315ec4977ababc23f5d8cb38e8baa37c947f4e467b`,
  `07cd2d7c40e40ab65b5f493794615ca231be460cd02c6d0f710ff6aab0a88993`,
  `06f70725836e7c3e06a6e65efe192c170cbd8b37077a2db8e4bdfd610e0822b8`,
  `c003b5871a6ba2f045c65dacde630915e86cb2e244c7a33adb3df4242be7c9be`, and
  `d47a3ab77f66203650fb1904eaecbb2c0c681e983a6351048e0cb4fcd1a76c4f`.
- The first recorded EXP-480 test command exited four before collection because PowerShell rewrote
  the unquoted literal `{run_dir}` into encoded-command arguments. Its failed metadata SHA-256 is
  `9ca036f7e6d0710aa523674ed659362267262ee0ae1fcb92bd0ff981529a7ea1`; it is retained and not
  reclassified as a test failure or deleted. EXP-480R1 quoted the placeholder and passed 28/28
  PDF/submission tests with zero failures, errors, or skips. Its JUnit and metadata SHA-256 values
  are `bbfa685aeb119d9812aaa9b192ecbfb639c9a66ac20e2ce8ee98304e8a5e7a6b` and
  `c0f89972206a0e644cac9d23481b3575d5c78fe5db8fc3d6682a890b32a64bbf`.
- EXP-481 then ran the complete project suite with CUDA hidden, checkout bytecode disabled, and the
  pytest cache provider disabled. All 414 tests passed with zero failures, errors, or skips in
  228.094 seconds. The only warnings were the documented scikit-learn SVC future deprecation and
  the expected no-accelerator `pin_memory` warning in a CPU raw-training unit test. JUnit and run-
  metadata SHA-256 values are `7f16f77c5520b70eaa3035c85b50e38aa64a5f5af2b8bb9ca8bd543f89d9691a`
  and `b47b9384cd3c59846a8608d29b38416b3518d7a3e94f67876ed1594aae19471f`.
- EXP-482 reran the expanded `src scripts research/scripts` Bandit 1.9.4 gate after the new PDF and
  Highlights code. It exited zero over 44,422 lines with zero medium/high findings, 25 retained
  low-severity detections, seven pre-existing explicit skips, zero `nosec` annotations, no scan
  errors, and an empty result set at `-ll`. Report and metadata SHA-256 values are
  `1948852283e18f5753c7361e649b979818ab507575238b6a0dd5cd1562f5f4dc` and
  `cfd527fea7dc75913f062de0808356e9131776dbe2261bf9e08cd5268596b873`.
- EXP-483 independently reran the current 414-test topology under path-based coverage with CUDA
  hidden and checkout-local bytecode/cache disabled. JUnit reports 414 tests, zero failures,
  errors, or skips, and 484.740 seconds. Coverage records 9,757 covered and 2,779 missed statements
  out of 12,536, or `77.83184428844926%`, passing the unchanged 75% floor. JUnit, coverage JSON,
  and metadata SHA-256 values are
  `0023071ba3be1a4d6514d2e831346bc4c24a5ec3b038fd82d722d9891c8f3270`,
  `e56bd04eaabf97a3d17131c33294d4c3b0d040259ec794f301d1ca0010f08689`, and
  `b564b16ce384fa5797599baa7965ce64f3c50e8b4125b0e8e4106cd6fbc1b8e4`.
  This supersedes the current dirty-tree coverage number only; it does not replace the earlier
  isolated CPU-environment evidence or the downstream formal/clean gates. The superseding
  readiness and reproducibility SHA-256 values are
  `bc9c69a41e77b9527ee38976543b17871452d86e029ccc9e32ba2944474275bf` and
  `8919e215e38878b0397a4fba58387dcc254b700481c41b6a236823494cc33d08`.
- A final-mode test gap remained after EXP-483: rejection of fewer than five figure PDFs was
  covered, but the successful five-figure assembly path was not. EXP-484 added only a synthetic
  text-figure test fixture, not empirical data. Two final-mode renders with exactly five one-page
  A4 PDFs were byte-identical; the report set `main_figure_pdf_count=5` and
  `machine_render_complete=true` while correctly retaining
  `human_visual_review_complete=false` and `submission_ready=false`. All five PDF tests passed.
  JUnit, metadata, and test-source SHA-256 values are
  `209e8798dcc70526b8675bf23e2bd6f712a9f51c75ca418eb66892d018c8d52e`,
  `30d8af67bc1410558b04effd2e3c8de61718ba4210a26c9d733f32cd8516df8c`, and
  `2410827919fe649e9c52c852602279c5d24f282b04947455b20f19c0a8950f3f`.
- Because EXP-484 increased collection by one, EXP-485 reran a single unified CPU-only topology
  rather than calling the earlier full run plus one focused test a unified pass. All 415 tests
  passed with zero failures, errors, or skips in 223.642 seconds. The two documented warnings were
  unchanged. JUnit and metadata SHA-256 values are
  `112da86f4ae522c82a4a563ef040a1c4470937227d7ee61d2885e483308856f4` and
  `efae0a61933f1a7b3c45d9bbca7d0c40d6d020e3bbcabd47deaa93054ef3555f`.
  The production source did not change after EXP-483; nevertheless final post-raw coverage remains
  mandatory. Superseding readiness, reproducibility, and RESS packet SHA-256 values are
  `feb03fb5ffd5eaa7b42d2801c61ed759a995b768e597626ff0cbe26bd3b0684e`,
  `7ec3d73b2e50b7b8ef6ba538bd397913ac99ced342e239519931601d31ea7640`, and
  `329795a66c93e394234330729867d29e2eb4768e17354d6981e265d5c40b7f81`.
- EXP-486 rerendered the complete locked 9,078-word working manuscript and 43-entry bibliography
  into an independent recorded-run output path. Its PDF SHA-256 is exactly
  `968f6c9a56d0207c7d38d7994d5430561d8811d8cba2e983fd4558492755fea3`, byte-for-byte equal to the
  separately produced and visually inspected EXP-479R3 working PDF. Because the PDFs are
  identical, no new visual iteration was inferred from the changed path. Rerender report and
  metadata SHA-256 values are `13bb9ce74051e1b157b9b977fdb4933df21a540f064a3d41a9c4a1c4c156226d`
  and `5adf43895ac4044269fe5e8d58931f641a3eae0559afa1aab87d825016e22e34`.
- Local `output/` manuscript renders and `tmp/` visual-QA pages are now excluded from both Git and
  Docker contexts; the recorded run outputs and append-only ledger remain the evidence layer.
  `git check-ignore -v` confirmed both paths, and `git diff --check` remained clean. `.gitignore`,
  `.dockerignore`, and the updated paper-package README SHA-256 values are
  `2f102b4a9cef87b1d8732b50ae4115a9d6577e986de95b17031d2689e3109ded`,
  `007866056af419ab04edbbcde0a36be3fdc3f1bdf597149d30bccefad444b443`, and
  `bb8d0e3ab69ca6cc15d99ae5202f297fdef2cf8eb2d2bdbd83c991ffbb2b4779`.
- At `2026-08-19T09:58:52Z`, outcome-blind monitoring showed EXP-456R1 at 203/270 structured
  completion events with zero monitored errors and both raw processes alive. The raw seal, locked
  working manuscript, raw-window summary, feature matrix, topology plan, and expected topology
  manifest retained their previously recorded SHA-256 values. All four downstream watcher error
  logs were empty. No intermediate raw performance outcome was inspected.
- Updated readiness, external-review, and reproducibility records hash to
  `69a6d381e973b2e766dc7c3ffc78fb8ed7b0a3a3039020db475f09a6455276f8`,
  `7269c553e7da0f65d5651139558e6aea610b6966c3a55a2fc339fa4372f8add1`, and
  `e6532851e644933efa87a3954663c26b48e1c5db29cb603d5dbcba7db978dddc`.
  Full-tree Ruff and `git diff --check` both exited zero after the recorded preflights and
  documentation updates.
  At `2026-08-19T09:35:27Z`, outcome-blind monitoring showed EXP-456R1 at 190/270 structured
  completion events, with zero monitored errors and both raw processes alive. None of EXP-479--481
  reads an intermediate raw performance outcome or closes the raw, final-figure, human-field,
  clean-reproduction, external-review, public-archive, or submission-readiness gates.

## EXP-487 DOCX renderer-availability recheck

- At `2026-08-19T10:05:34Z`, the exact internal layout-preflight DOCX was located at its retained
  Windows temporary path. Its size remained 66,684 bytes and its SHA-256 remained
  `73d012ea194f8f4c2ed09f9350dc9ef6b6c2629a4a8f8554994198a57ad0bf0d`, matching the earlier
  structural-audit record. The file was not copied into the repository and was not modified.
- A read-only rerender was attempted with the authoritative bundled document Python runtime and
  the packaged `render_docx.py` renderer (SHA-256
  `b54a58a3c81380dc1155bf45e05bac03600f6f0908527c44197dce7f8887049d`). The command exited one
  before conversion with `FileNotFoundError: [WinError 2]`; both `soffice` and `winword` remained
  unavailable, and the render directory contained zero files. No page image or PDF was produced.
- This independently reproduces the earlier environment limitation rather than closing it. The
  DOCX remains a machine-structural preflight only; page-by-page DOCX visual QA and any final Word
  deliverable remain open. The deterministic 19-page RESS working PDF is a separate artifact and
  does not retroactively validate the DOCX layout.
- At `2026-08-19T10:03:18Z`, outcome-blind monitoring showed EXP-456R1 at 206/270 structured
  completion events with zero monitored errors and both raw processes alive. No intermediate raw
  performance outcome was inspected.

## EXP-488/489 ordered-figure PDF identity and independent preflight validation

- Renderer 0.1.2 now records the ordered path, SHA-256, and byte count for every appended main-
  figure PDF. It rejects duplicate paths and independently named files with duplicate content,
  preventing a five-file count from standing in for five distinct validated figures. Renderer and
  updated PDF-test SHA-256 values are
  `be5a3029437af110bec2d07180efa58b7e6d00ebc302865c216d2fbc1aff96b8` and
  `4762430621fdf16fd738c3cb71d9cc23e2a2d6cee19e80ad9c6f89b9c5f7a105`.
- EXP-488 passed all seven PDF-renderer tests with zero failures, errors, or skips. The tests cover
  bytewise deterministic working/final renders, successful five-figure assembly, explicit
  non-submission flags, ordered figure records, and duplicate path/content rejection. JUnit and
  metadata SHA-256 values are
  `1252ad310dbfa80362e3e497e6553e6e80e7d268914ace6c3828955a4e5a2df0` and
  `2377db28174f338cc4ba3ee3f260c19d4fbeebccec2c2661115ca6db836daac5`.
- A separate validator 0.1.0 was added without calling the PDF renderer. It hash-locks the PDF,
  report, empirical manuscript, bibliography, 42-output artifact manifest, artifact validation,
  manuscript validation, and release validation. It verifies the five exact vector-PDF artifact
  identities and one-page topology, the appended page order through their extracted titles,
  deterministic producer metadata, zero blank pages, the working watermark, and false human-
  review/submission-ready flags. Validator module, CLI, and test SHA-256 values are
  `e584669d04ef6aae80bf8ce14db9aae86d4d889b4acd4ba489def18bed8f1e6f`,
  `c7abf92aedc06ecc7af91c0ecb65d7d75035fbc905268348c85e0ebb85eeb5fa`, and
  `78a19c443f0280e6c99356f7e448fdb14b5f2c2646ec69a76ecc14674cbb83bf`.
- EXP-489 passed the combined seven renderer and three independent-validator tests: 10 tests, zero
  failures, errors, or skips. The negative paths alter the report's figure order and the upstream
  artifact-validation output count while updating their outer expected hashes; both still fail on
  semantic identity. JUnit and metadata SHA-256 values are
  `340129d7024fc6a52d3d687a20224ff8572725769eba159070a9aa42980d6916` and
  `f555305b80d184ca5589438afb4bb19eed36329bfa33c033c2621d98802b4cb2`.
- The hash-locked `run_EXP490_EXP491_after_EXP463.sh` watcher (SHA-256
  `4dbc6101eeb2b8305bee572599fc35e2f3513a1654c15d1797904ec19ce6ca86`) is armed and alive. It
  will only render the watermarked empirical PDF after EXP-463 independently validates the
  deterministic release, then run the new PDF validator as EXP-491. It does not create a final
  non-watermarked upload or claim human visual review.
- At `2026-08-19T10:15:31Z`, outcome-blind monitoring showed EXP-456R1 at 213/270 structured
  completion events with zero monitored errors and both raw processes alive. No intermediate raw
  performance outcome was inspected.

### EXP-489R1 validator-independence amendment

- Review of validator 0.1.0 found that it imported the producer's `RENDERER_VERSION` constant.
  Although it did not call the renderer, a producer version change would therefore silently change
  the validator's accepted version. Validator 0.1.1 instead freezes
  `smartvalve-ress-pdf-renderer-0.1.2` as an independent literal. No PDF, scientific result, or
  acceptance rule changed. The superseding validator-module SHA-256 is
  `95d18be6a785f7482a3f4d10d747a0823d70d684b8f16dde907419c2ff681f8a`.
- EXP-489R1 reran all 10 renderer/validator tests after the amendment; all passed with zero
  failures, errors, or skips. JUnit and metadata SHA-256 values are
  `57f81f65cd704236ab0ac169e0b64f538c3d6c7a40918df45a4bac01f2171ce3` and
  `9478fc04ee7c94d43c410dbdc8343e09b29f48ee0f9348b2ff98be8c4316885b`.
- EXP-489R2 added a real subprocess invocation of `scripts/validate_ress_pdf.py`, passing every
  locked input and expected digest through the same CLI used by the post-release watcher and
  comparing its stdout with the written JSON. All 11 combined tests passed with zero failures,
  errors, or skips. JUnit, metadata, and superseding validator-test SHA-256 values are
  `630fe8e3c859eb18c66ead483036b6e5bcee6f0289fbea900d2e6e34c1ab5d06`,
  `dedc5592b9abcecee4e08160ed7dc22f620b3d4be2c3f9402c179bc9783b2c50`, and
  `a69a0e07be0d558e6019c4dd8054e091a8b2cd153954ab29e5cd781d52437192`.

### EXP-489R3 release-to-live-source binding amendment

- A second review found that requiring EXP-463 did not alone prove that the live renderer and
  validator invoked after release construction still matched the archived source. Validator
  0.2.0 therefore also hash-locks the EXP-462 release manifest, requires EXP-463's declared
  manifest digest to match it, and verifies the live identities of `ress_pdf.py`,
  `ress_pdf_validation.py`, `render_ress_pdf.py`, and `validate_ress_pdf.py` against the release
  file records before accepting the PDF. A negative test changes a release source digest while
  consistently updating the surrounding manifest and validation hashes; semantic source binding
  still rejects it.
- EXP-489R3 passed all 12 renderer, core-validator, failure-path, and real-CLI tests with zero
  failures, errors, or skips. JUnit and metadata SHA-256 values are
  `4d479975e6e70816b3bf710b6fef52749393abf0c355bd2c87191abc5948f5ee` and
  `34570eff74a3c362c76b7fa77aa9c128a4375dcecc1d9244e54315b6bfb64dc1`.
  Superseding validator-module, validator-CLI, test, and watcher SHA-256 values are
  `22c696b036bb8cab6b74e4d1a128f7354516d5f9b218b655f2d27b9d9572c20e`,
  `752eb8d4a6eebe8e0508934fc4fa11aa93d7639cb22da7d8dc8b5807eb97d1df`,
  `eab01dba9833938906a0b0fd68cf4cd9677769cb43d53bdbb78e5bfb6f49fd27`, and
  `a18c3f98372d36dc4b1cc25ed5f7b0ef09542071124b35178eb33a7119e8ee1d`.
- The earlier post-release watcher process was stopped before it had observed any predecessor and
  restarted from the superseding script. The replacement process is alive, its error log is
  empty, and no scientific output or completed run was deleted or rewritten.

### EXP-489R4 launcher-level source-binding amendment

- Validator-level self-checking alone could still be weakened by a changed live validator.
  Therefore the post-release watcher now performs a separate standard-library SHA-256 and byte-
  count comparison for the renderer module, validator module, renderer CLI, and validator CLI
  against the independently validated release manifest before it invokes any project PDF code.
  The release topology test requires all four literal source identities and the fail-closed check
  in the watcher.
- EXP-489R4 passed the seven renderer tests, five validator tests, and strengthened release-
  topology test: 13 tests, zero failures, errors, or skips. JUnit and metadata SHA-256 values are
  `d1ea9d710475f37377829e938ed84469d05694f484ae1e8af211acae944ed7cd` and
  `72cd6200cd3e5145095c25529fe6199adae2a14e765d651f648f0b0e38ab4962`.
  Superseding watcher and release-test SHA-256 values are
  `ab955352fd12758a4b4293771475c8af5b3298a426e3621a4d9366cffbc3b593` and
  `8a3905682f2e9b8b7bcb26c98b329da8a432ce487a3bedb5965e0c7cac712700`.
- The waiting watcher was again restarted before observing any predecessor so the alive process
  uses the superseding source-bound script. Its error log remains empty.

### EXP-492R2 unified release-bound regression

- The release-source drift test increased collection from 421 to 422, so EXP-492R2 reran the
  complete current CPU-only topology rather than combining the preceding 421-test run with a
  focused pass. All 422 tests passed with zero failures, errors, or skips in 225.829 seconds.
  JUnit and metadata SHA-256 values are
  `19f961631062dd8eb165d4406e05357aee29d386997f62f81b19199dcd23c06f` and
  `476e4ea555ea102810bb3f8824d4d88d7691535e9ede80ffd276ba9a55d54dd5`.
  Full-tree Ruff and `git diff --check` remained clean. Formal post-empirical coverage and quality
  validation remain assigned to EXP-461Q/461V.

## EXP-493 public-release submission-map and privacy boundary

- Release 0.11.0 adds `paper/RESS_SUBMISSION_PACKET.md` to the public technical evidence archive
  so the upload map and bounded cover-letter scaffold accompany the reproducibility evidence. It
  explicitly prohibits `paper/RESS_HUMAN_SUBMISSION_FIELDS.md`: the completed record may contain
  legal names, institutional contact details, postal information, ORCIDs, approval references,
  and signatures that do not belong in the public archive. The release manifest and independent
  validator both report `human_submission_fields_included=false`, and the downstream PDF gate
  requires the same field.
- EXP-493 passed all bearing-release, PDF-renderer, and PDF-validator tests: 24 tests, zero
  failures, errors, or skips in 3.254 seconds. The suite includes build-time rejection of the human
  fields document and downstream rejection if a release manifest claims it is present. JUnit and
  metadata SHA-256 values are
  `7e86f602313b6f7fe08c5a1157c47eeae15f0153b64f586f1309714719dc1d91` and
  `73e61e608731066bd09987c7bc27fd6106d23d0fdf1269747280e6163d74a39f`.
- Release module, downstream PDF validator, release test, PDF-validator test, and superseding
  watcher SHA-256 values are
  `ba59b87400ba949c0d969f0296058763e8abd1f1f107f5baec4ef1b87e389eb9`,
  `6d44852a3e06619acbe0e7e42ab8019c1a340635dff92c425d4ace97b4c7b096`,
  `972192c18ce3a65e63e33c8b4ae182f2532f351e17b0f67fae4c69bdb7b992ff`,
  `7b2c057d9c746489d2e4a12c4ca612b1366beba251c3bb980e48cbe2bd80e230`, and
  `a4954134f1970da35a39762c77036ac7413567ce0bb934efdbac87f3ea73eb26`.
  The waiting watcher was restarted before predecessor observation and its error log remains empty.
- The two privacy-boundary tests increased collection from 422 to 424. EXP-493R1 therefore reran
  the complete current CPU-only topology: all 424 tests passed with zero failures, errors, or skips
  in 227.654 seconds. JUnit and metadata SHA-256 values are
  `5d57b85b7c01a6b0c11117b230ab624397628e652c3620e012d6d51d25e918a0` and
  `c7a6e07794e6427459a66dfb05794f53a4444a3c3f3316e68a4856de0a0d437a`.
  Full-tree Ruff and `git diff --check` remained clean.

## EXP-494 expanded static-security preflight

- The post-PDF/release tree was rescanned with Bandit 1.9.4 at medium/high severity across `src`,
  `scripts`, and `research/scripts`. The command exited zero over 44,785 lines with zero medium or
  high findings, zero scan errors, zero `nosec` annotations, 25 retained low-severity detections,
  and seven previously documented explicit skips. The result array is empty at the enforced
  severity threshold.
- Bandit JSON and recorded-run metadata SHA-256 values are
  `121cc780794b858ee274c9dbebacdc58e03069f34a92e17c67d6bba6ed4ef33b` and
  `bb55520f0eebdd45698905af213d7a21cc947941fec59e1eb190fa7e2c227690`.
  EXP-461Q/461V must still rerun and independently validate the same security gate after the final
  empirical manuscript is generated.

## EXP-495 clean-reproduction exact-topology amendment

- The clean protocol's legacy `tests >= 385` assertion was too weak after collection reached 424:
  a reproducer could omit dozens of released tests and still satisfy that lower bound. The revised
  protocol requires `SMARTVALVE_EXPECTED_TEST_COUNT` from the hash-locked EXP-461V validation and
  exact equality with the independently observed JUnit count. It also writes the clean archive-
  validation JSON under the external reproduction records directory rather than into the detached
  checkout.
- The release-topology test now rejects the obsolete lower bound and requires the exact-count
  environment variable, equality assertion, and external validation-output path. The focused test
  passed with zero failures, errors, or skips. JUnit, metadata, protocol, and superseding test SHA-
  256 values are
  `48bd88fb132fe53dc33787d7e37259f39c853276716ad1d1e4905c89f39e8663`,
  `cda5ee97738b811fa5ea5274e0fd79e05b327502db2fb7cfa3d67a6962b992c7`,
  `7b4e3082a94afb3f80c927fd3f87c6a1f1caf934258de0bb753a804687e6c29c`, and
  `66df329e866d8839f7cb29879edafc9d7ef7622bb959904a9b4c84cfae4d595e`.

## EXP-492/492R1 unified 421-test integration regression

- EXP-492 deliberately ran the entire current CPU-only topology rather than inferring project
  compatibility from the 11 focused PDF tests. It collected all 421 tests and retained one real
  integration failure: the release test still asserted that exactly five `run_*.sh` launchers
  existed, while the new post-release PDF watcher correctly increased that topology to six. JUnit
  reports 421 tests, one failure, zero errors, and zero skips in 224.207 seconds. JUnit and failed-
  run metadata SHA-256 values are
  `9752b920cb20f40922e332569a91b7be7ed538df29f61976f4a812859838354b` and
  `d5bd964b9f78034de83738ac4fc211f684fb8c2577405fbe6eca90922c7b1de2`.
- The release test was strengthened instead of merely changing `5` to `6`: it now requires the
  exact set of raw execution, metric/topology validation, artifact validation, manuscript
  validation, release validation, and post-release PDF-validation launchers. Its SHA-256 is
  `fcd229c393c2cd0e12cf8928be8d6ddadb630486c9426f35296757e1bbc43bdc`; the focused corrected
  test passed before the unified rerun.
- EXP-492R1 reran the same unified 421-test topology. All 421 tests passed with zero failures,
  errors, or skips in 221.778 seconds. JUnit and metadata SHA-256 values are
  `000956b87ef9be4b364064621f9b29a98204511daaa53d27f81d87cb8d17bd67` and
  `c56c5ddab59c1c47799780015f3b2f9b9123526035dd9ebd559258dd029777b7`.
  Full-tree Ruff and `git diff --check` also exited zero. This is a current dirty-working-tree
  preflight; EXP-461Q/461V still must rerun the formal quality and coverage gates after the
  empirical manuscript validates.

## EXP-495A external-review exact-topology alignment

- The external-review packet's clean-reproduction request R6 now mirrors the fail-closed
  EXP-495 contract: an independent reproducer must observe exactly the hash-locked EXP-461V test
  count, not merely meet or exceed a historical lower bound. This is a documentation alignment;
  it does not inspect, alter, or make any claim about the still-sealed EXP-456R1 scientific
  outcome.
- The aligned external-review packet SHA-256 is
  `926a98a3c240c70188d40255b46f2ecc5f8fc3fee30eeab7f666edba7a131f05`.
  Full-tree Ruff and `git diff --check` both exited zero after the amendment; the EXP-495 focused
  release-topology test remains the executable enforcement of the exact-count contract.

## EXP-496/496R1 outcome-blind independent raw-validator amendment preflight

- A code audit while EXP-456R1 remained sealed found that validator 0.1.0 reused the producer's
  aggregation, scoring, physical-bearing bootstrap, and gate functions. It was no-refit, but a
  shared implementation error could make both sides agree. Amendment 001 therefore replaces those
  calculations with a separate module that imports neither producer calculation module. It also
  requires the exact ten-output inventory, every frozen design constant, and the literal feature
  and raw-window summary hashes. No producer, fit, probability, endpoint, threshold, bootstrap
  seed, or advancement rule changed, and no raw result was read.
- EXP-496 is retained as a command-layer failure: unquoted `{run_dir}` was tokenized by the Windows
  PowerShell boundary into an encoded-command fragment, so pytest exited 4 before collection.
  Failed-run metadata and stderr SHA-256 values are
  `aaa3cc334fefd72651b2e699178bf7df1ba3dd2135ce248a67d4dc7645f0fb59` and
  `84473e8c0977700c8c20c6e35e82cabd0e81cc3ddd81683ab779a3ee1c742deb`.
- EXP-496R1 quoted the placeholder without changing the test family. All 23 independent-validator,
  raw producer, expected-topology, and release tests passed with zero failures, errors, or skips in
  21.141 seconds. JUnit and metadata SHA-256 values are
  `da7e1d756a4393901e1f74452b73f8e1ee9dd66e04a69a36ac2b3ca55b5fa7f8` and
  `34cb821219127e29af7de539ba64bcd4588fda30d0b6fd78a3c05f394a21a020`.
- Amendment, independent-calculation module, validator CLI, focused test, and armed-watcher SHA-256
  values are
  `56d7cd6ca743130978445aa84ffd60ccd3420c6bc07a0063968845f50f447603`,
  `d053dc678cd382c603e071e2b1f2a9c0b50ce3beaae8d7e20b63b1bbb5db2a17`,
  `9ae4cd837d9f2383b5bc36f29c4038c096907e9606f6e866018744962cfa7acf`,
  `39ccea346159ff89c4626bc12e7cce978391073b63389ec3923162f624ff5192`, and
  `face67956d43593334792df162bb0c76b26aacfa1a4279280bf112c32cb4285c`.
  The amendment is included in release 0.11.0's public documents. The EXP-457 watcher was stopped
  and restarted before observing a predecessor; the replacement process is alive, its error log
  is empty, and EXP-456R1 continued uninterrupted.

## EXP-497 unified independent-validator regression

- The independent raw-validator amendment added three tests to the complete project topology.
  EXP-497 therefore reran the whole CPU-only suite rather than inferring compatibility from the
  23 focused tests. All 427 tests passed with zero failures, errors, or skips in 227.549 seconds.
- JUnit and metadata SHA-256 values are
  `bc172c2cc6304d3d07e413bd211a2c2b52153721b27da3ddd96dcd673afc8fd0` and
  `9bcd21e84ed8d87811f4ffd87b910cc75c1c8cdc715ddec91ecf437e3183d437`.
  Full-tree Ruff and `git diff --check` also exited zero. This remains an outcome-blind dirty-
  working-tree preflight; it neither reads EXP-456R1 findings nor replaces the post-empirical
  EXP-461Q/461V coverage, security, and independent quality validation.

## EXP-498 fail-closed independent-validator artifact authorization

- The artifact watcher previously accepted any no-refit validation whose status began with
  `passed_independent`. It now refuses to start EXP-458 unless EXP-457 declares the separately
  implemented calculation version 0.2.0, `shared_producer_calculation_code=false`, the exact module
  and CLI hashes from amendment 001, the frozen feature and raw-window hashes, 270 fits, and the
  exact 166,968/41,742/13,914 prediction row counts. EXP-477's outcome-blind exact-key authorization
  remains an additional, separate requirement. No performance value is read by this handoff.
- All 11 release and launcher-topology tests passed with zero failures, errors, or skips in 0.498
  seconds; Bash syntax, Ruff, and `git diff --check` also passed. JUnit and metadata SHA-256 values
  are `a19ebe833afe363520484b6f4663a28d91240064747f152b8a6703ef18b49439` and
  `00cc4d7cc928535226dcbcf1c05dd12d042a6fc29b793ebda669fb501fad38cf`.
- Superseding artifact-watcher and release-test SHA-256 values are
  `23b1e9bb73622ad6359a444bbcba1f6cbc4d4ef628986fedc54acdc554edb7b2` and
  `41ea2873c64996df9dcb44a368d35fd52a0a90356f9080987634a365db39eac1`.
  The earlier EXP-458 watcher was stopped and replaced before EXP-457 existed; the replacement is
  alive, its error log is empty, and the raw fit continued uninterrupted.

## EXP-499 exact final-quality topology preflight

- The final local quality gate still allowed `tests >= 384`, a historical floor that could miss
  deletion or non-collection of many current tests. Gate 0.3.0, independent validator 0.2.0, the
  release builder, and the armed EXP-462 watcher now require exact equality with the 427 tests
  observed by outcome-blind unified EXP-497, plus zero failures, errors, and skips. Any subsequent
  test addition must trigger an explicit topology revision rather than silently passing a lower
  bound.
- All 17 final-quality and release tests passed with zero failures, errors, or skips in 0.546
  seconds; focused Ruff, Bash syntax, and `git diff --check` also passed. JUnit and metadata SHA-256
  values are `4f2ec5ecd132c139fb61b96383f64a3af3cdd1073291e850cca4aacdaf545132` and
  `119faa2cc7116a0e45fd75f509f7e2b99c0cd8f2f4a1a755489d4ef8cbef51bb`.
- Final-quality gate, independent validator, runner CLI, release module, armed watcher, quality
  test, and release-test SHA-256 values are
  `2a283f07e1a6fcb3ec38f3426495e5ca47547e74c913bf3b9c349270151076fb`,
  `879d673794d4172a3390d1465e22e1f30704e730be5603fde7a917623d6f7e31`,
  `a894b31e8054c58d38d0f46b24448ee8164b5a18099c7210be665f1c0fe788c8`,
  `5128f76c9a7e3d1e63d79534cd7bd84533406d2d13d02356ccd1792e52cdc035`,
  `4c962d32e6994c18188121f85100610f6225dd7ce4275d333676888184f37ae8`,
  `8b02a7337e55001f9c357afe9d54a5bccd6a849fc04d9ca121b56ff6e12a6840`, and
  `7747135bad95d4fab1dd980766a2edd0a4d81eaf532eb1f680cda77bb691bb29`.
  The predecessor-waiting watcher was replaced before EXP-461 existed; its error log is empty and
  no scientific run was interrupted.

## EXP-456R1/457/477 sealed raw-architecture sensitivity and dual validation

- EXP-456R1 repeated all 270 frozen fits from scratch after the externally interrupted EXP-456 and
  completed in 37,678.059 seconds. It retained 166,968 window predictions, 41,742 seed-recording
  predictions, 13,914 ensemble predictions, 270 fit records, and 270 training traces. Metadata and
  scientific-summary SHA-256 values are
  `c9cfcd54c14605636364ddf2c0dc7528aaa4b384fa8988ce76d902da8741be42` and
  `5781106c9b192df2943a2deff1ab62473aa29916843c6df78a67bf189278ee7f`.
- Measurement-random versus strict-crossed pooled macro F1 was `0.916449/0.553336` for raw 1D CNN,
  `0.699044/0.528329` for log-FFT CNN, and `0.745986/0.540319` for log-STFT CNN. Paired
  random-minus-crossed physical-bearing effects and 95% intervals were `0.363114`
  `[0.273491, 0.452966]`, `0.170716` `[0.102734, 0.239182]`, and `0.205668`
  `[0.143039, 0.268069]`. All three lower limits were positive and the median effect was
  `0.205668`, so the frozen 3/3 and median-at-least-0.15 rule passed.
- EXP-457 independently recomputed aggregation, probabilities, 24 cells, macro F1, the fixed
  2,000-draw physical-bearing bootstrap, and the advancement rule without importing producer
  calculations or refitting. It matched all 270 fits and all three prediction topologies, with
  maximum numeric disagreement below `5e-13`. Metadata and validation SHA-256 values are
  `1af172cbae588e305dae6aa0aa6495ed22ec963a6e2397726f04772945805bd2` and
  `822f6c504b66c6398c56b6480bc1139a068b1fd7d3457918799865deca0858b0`.
- EXP-477 separately matched every prediction, fit, and trace key against the pre-outcome EXP-476
  topology manifest and read neither scores nor the gate. Metadata and validation SHA-256 values
  are `2b17fe4d048d5923822e88e0d6db4ec350a2f3c0297a2a49d7cd491e025190c4` and
  `3e3f9f4886e650b50c8d3bc914b6a4cd711e24ef8b41c556cf8eb583772139e6`.

## EXP-458/459/459R1 final bearing-paper artifact chain

- EXP-458 consumed 28 hash-locked inputs and produced the exact 42-output paper topology: six
  main tables, four supplementary tables, five SVG sources, five normalized one-page vector PDFs,
  captions, submission text, and the relative-path manifest. Metadata and manifest SHA-256 values
  are `4fa164b107054fb7870d517df552d2e6a0e3be9f2eeaa0ee5cddefd9dc3c53b5` and
  `4abf54dbdb8dd89c0f998ac8e96dc59d51734d28ee5e96f55c1dc15197b4aec7`.
- EXP-459 is retained as a validator-only failure caused by exact comparison of a full-precision
  raw median with its 12-decimal CSV serialization. The absolute difference was
  `6.494804694057166e-14`; the scientific result and frozen gate were unchanged. The incident is
  recorded in `research/EXPERIMENT_INCIDENTS.md`.
- Validator 0.4.1 keeps the gate on the full-precision value, requires the independently recomputed
  CSV difference to be at most `1e-12`, and rejects larger drift. EXP-459R1 passed without refit,
  verified 28 inputs, 42 outputs, five SVGs, five PDFs, zero raw dataset files, and the recorded
  precision difference. Metadata and validation SHA-256 values are
  `0ff10c766f340bcf8f850a690089bf8f7fdc8f5085f9a4b70ef13c8f7d5255e2` and
  `425c0c4861aaee9c6c004c121b0334d5345c34e1e75cdb40adc440f810b8243d`.

## EXP-460/461 empirical manuscript generation and independent claim audit

- EXP-460 replaced the seven bounded empirical holds in the integrated template from the validated
  manifest. The resulting 9,369-word manuscript reports all three raw effects, Table 6, Figure 3,
  all 39 positive final contrasts, the failed directional HUST rank replication, and every human
  hold. Manuscript, render-report, and metadata SHA-256 values are
  `784392b35d9c8a69c9554e01c6ed5b936a75716c276a8a7aca47244f6a44532f`,
  `6be06d6ddd920ebd1ea744395d68570a53a22968bc807c64becde05e43200d3a`, and
  `adc4a060e1f980376665d57f171d0a2564f5cc704ca2fcd5f69e8b973d100a29`.
- EXP-461 independently checked every upstream hash, all raw values and intervals, 39/39 contrast
  wording, callouts, abstract, limitations, word count, and three retained human marker families.
  It passed with `submission_ready=false`. Metadata and validation SHA-256 values are
  `4f58f4ece48c5530ccfd843eeb173909741f93442850482cb947743da30411c1` and
  `d77dac66e0a34c0f9c4f087bd3a14a11f06782f0a43e48fa7e9c6073ff794f35`.

## EXP-461Q/461V final local quality gate

- EXP-461Q completed the fixed eight-check post-empirical gate in 737.944 seconds. Ruff, exact
  427-test JUnit topology, a second path-based coverage run, expanded-scope medium/high Bandit,
  runtime/build, CPU-CI and GPU-research lock audits, and `git diff --check` all exited zero. JUnit
  reports 427 tests, zero failures, errors, or skips; coverage is `78.1152647975078%`.
- EXP-461V independently checked every normalized command, log hash, JUnit count, coverage JSON,
  and scope-limiting flag. It verified 8/8 checks and 427/427 tests while retaining
  `clean_checkout_claimed=false`, `independent_reproduction_claimed=false`,
  `human_review_claimed=false`, and `submission_ready=false`.
- Quality-summary, quality-validation, EXP-461Q metadata, and EXP-461V metadata SHA-256 values are
  `85c0abbae5cf0dcc00b82f7d9c0e40568ec1f4aebf1e13870a4943dd8458553f`,
  `c633cd17aab4941ec71d453704de634aa7680ccca2162bbab1ddc24be8428707`,
  `f533e6395b330ec415f1767af44193566a3df148fa85d0f2e7a22062f5ee924e`, and
  `6c5dccf7000526d4e318a1b3b9a4c8ba0f006afe02ef860ae8d5fe84acaeeba5`.

## EXP-462/463 deterministic technical evidence archive

- EXP-462 built release 0.11.0 with 453 files and 86,262,209 uncompressed bytes. It includes all
  four independent validation families, the pre-outcome raw topology manifest, reproduction
  source, quality logs, manuscript, artifacts, code, tests, locks, and audit documents. It excludes
  raw dataset files and the personal human-submission record and keeps
  `technical_manuscript_submission_ready=false`.
- EXP-463 independently reopened the compressed archive, verified all 453 member hashes and
  normalized metadata, and confirmed every prohibited-data and validation-chain flag. Archive,
  release-manifest, release-validation, EXP-462 metadata, and EXP-463 metadata SHA-256 values are
  `8662556ce19c2be8a9403ad8a51f9e2d73e9ac95433094d13ddf5e9ea5d66e46`,
  `75ea915a426d31ff9916695fffa82db78ff91cd66e7a8466c5f791ea6d255582`,
  `f15ee5c4b7eaf6a0a854eca85aa9288099227bf37653f8dc80633d35e69d4797`,
  `0f96c0a8e28819d1a3049ff1e6ecc1ef5a054b7821839a9f981bff846b59ecc7`, and
  `818ac44659ae37d906d59512d8cb8a9bda038240177bd4b85c70d3f1ec585f75`.

## EXP-490/491 empirical five-figure PDF and visual preflight

- EXP-490 deterministically rendered the validated 9,369-word manuscript, 43-entry bibliography,
  and five ordered vector figures into a 24-page working PDF. The report records zero blank pages,
  28 cited references, the visible working-preflight watermark, and
  `human_visual_review_complete=false` / `submission_ready=false`.
- EXP-491 independently bound the PDF and report to the artifact manifest, manuscript and artifact
  validations, four release-bound live PDF sources, release manifest/validation, and all five
  ordered figure titles and hashes. It validated 24 pages and five figures without rendering or
  fitting.
- PDF, report, validation, EXP-490 metadata, and EXP-491 metadata SHA-256 values are
  `c041274804f7818b97f002d47ccde97baf23e67c42d6ad4506d89b73daf4b463`,
  `2039f73fa0a18ab534edb067dd62c1b00ae0fcd3ff228dca46c1e56a1e981583`,
  `09ff92a7473a05c83f7673eb19eb52efb2f8459153639c97f12d6ef8bc263939`,
  `fc9b81e8ac3f14165bc7c60cad362c7f306ddb9367733bad3d2f2b4de5e755f3`, and
  `867a8e32a3655faa4b3d803c912ac2f8ce8e84137abadcce738736a8858df4b9`.
- All 24 manuscript pages and all five standalone figures then passed an agent visual preflight for
  ordering, legibility, clipping, collisions, glyphs, tables, footers, watermarks, axes, legends,
  and redundant encodings. Targeted crops resolved two thumbnail-scale false alarms on pages 6 and
  12. The bounded review is recorded in `research/BEARING_VISUAL_QA.md` and is not a human-review or
  submission-readiness claim.

## EXP-507--513 release-0.11.1 amendment, quality, archive, and PDF chain

- EXP-507 focused the release amendment 001 correction: release version 0.11.1 and the explicit
  document allow-list require both `research/BEARING_RELEASE_AMENDMENT_001.md` and
  `research/BEARING_VISUAL_QA.md`. All 11 release tests, focused Ruff, formatting, and
  `git diff --check` passed without a model fit.
- EXP-508 reran the exact eight-check local quality topology after that amendment. All 427 tests
  passed with zero failures, errors, or skips, coverage was `78.11526479750779%`, expanded Bandit
  returned no medium/high findings, all three strict dependency-lock audits exited zero, and the
  diff check was clean. EXP-509 independently rehashed every output and verified 8/8 commands,
  427/427 tests, zero skips, and the same coverage while keeping all clean/external/human/submission
  claims false. Summary and validation SHA-256 values are
  `f001d3276a957058579c239ee4921158da65ec4a6e8066cede63dc6c31f1f9ac` and
  `807f9c7f793d5d1298252abbd3b02ee201be0de9fdd0e7f5daa3a58beb51698b`.
- EXP-510 built the deterministic 0.11.1 archive with 455 files. EXP-511 reopened it and verified
  every member hash, normalized metadata, both amendment documents, raw-data exclusion, human-field
  exclusion, and all four independent validation families. Archive, manifest, and validation
  SHA-256 values are
  `b12b4210e031031da28e2689f8da56b9c19408dca5ad0421fa6c196358ce4327`,
  `db4281c4d04e68caf42c99d72fcca166d6d5722ae69d5828961b753f6569e930`, and
  `205e7690b66ad3a2de1f556ddf5f3fae841145cac72530bac547927cfdf0cc91`.
- EXP-512 rerendered the unchanged manuscript and figures. Its PDF remained byte-identical to the
  inspected artifact at
  `c041274804f7818b97f002d47ccde97baf23e67c42d6ad4506d89b73daf4b463`;
  the new report SHA-256 is
  `21fcdfd54ef6c00fff3e96d43cc92bd88684dae2e2ae9a4e8726e54d43b5d5e4`.
  EXP-513 independently bound that 24-page/five-figure working PDF to the 0.11.1 release; its
  validation SHA-256 is
  `78dcd25d9ff21b25723ca2e3fa6de1b0e2da5e666a37e6bac6cf0692164acfd9`.

## EXP-514 retained archive-source clean-reproduction failure

- EXP-514 began from the independently validated immutable 0.11.1 archive rather than the
  development checkout. It performed two external extractions with equal source-tree hashes,
  created a fresh CPython 3.12 virtual environment, installed both lock sets with hashes, installed
  the package without editable mode, passed CPU-only and installed-lock validation, downloaded all
  five public fixtures into a fresh outside-checkout cache, froze the environment, and passed Ruff.
- The first complete pytest pass then retained 427 tests, seven failures, zero errors, and zero
  skips. The seven failures exposed missing release-source support files and two install-topology
  assumptions; they did not compare or invalidate any scientific output. The run stopped before
  coverage by design and remains `failed_supplementary_archive_source_clean_reproduction`.
- The exact failure inventory, integrity decision, and bounded recovery are append-only in
  `research/EXPERIMENT_INCIDENTS.md` and `research/BEARING_RELEASE_AMENDMENT_002.md`. JUnit,
  reproduction-summary, and metadata SHA-256 values are
  `04d5f4f67cce3da809ba9f19ca010a133842b4e9829e12b21f47c86a6e50c011`,
  `45c7c2db613c916addc09b987420897b7ed7f5cda2a5e00dd552f24d4964d563`, and
  `e56bae8e29fda946c4c00583224a2d3e6a0615d7724e46e019e0f61a2f659dda`.

## Release amendment 002 and EXP-515 structural preflight

- Release 0.11.2 adds Docker/CI support, all six paper support documents required by the exact
  suite, 42 checked-in `paper/generated` files, their eight hash-locked metric inputs, and checked-
  in benchmark/validation fixtures. The recorder now uses a bounded filesystem fallback without
  Git metadata, and the PDF validator resolves live sources through the explicit project root.
  Existing tests were strengthened without increasing or weakening the 427-test topology.
- The 34 tests spanning all seven EXP-514 failure sites passed in the development tree. EXP-515
  then built a deliberately non-public 531-file 0.11.2 structural preflight with superseded
  EXP-508/509 quality evidence. Its inventory contained every required correction and all eight
  generated-package inputs. After extraction and a non-editable reinstall into the disposable
  clean environment, the same 34-test family passed. This preflight is not the final release and
  must never be published as one.
- Preflight archive, manifest, and metadata SHA-256 values are
  `6b6f8831068527afb853a9a9664b9e08f2ece51c39bb2dec81406082bebfd857`,
  `9b5d7061dc1c7e326b0990427a5020c73234b06b7f2bb470c5665e3e3eeb4374`, and
  `567edebeb6e4e148f08b1835554fff7180823840f25ef525cb1b2e6aaafdb33e`.

## EXP-516/517 post-correction local quality validation

- EXP-516 reran the complete fixed eight-check topology after amendment 002. All 427 tests passed
  with zero failures, errors, or skips; coverage was `78.16118753400171%`; expanded Bandit and the
  runtime/build, CPU-CI, and GPU-research strict audits all exited zero; and `git diff --check` was
  clean. The quality-summary SHA-256 is
  `84d724b9b0887f1ef75025e541e68f6e39d826b015279b71901f62a0deed3403`.
- EXP-517 independently verified all eight normalized commands, every log hash, the 427-test JUnit
  topology, zero skips, and the coverage JSON. Its validation SHA-256 is
  `87519c2a87783e03730a91da4e20161cca66436b685d2839bd3061e059c2f7c4`.
  Both reports explicitly deny a clean checkout, third-party reproduction, human review, and
  submission readiness.
- These two runs precede this append-only record freeze. A final post-record-freeze local gate and
  independent validation must supersede them as the quality inputs to the publishable 0.11.2
  archive; the archive manifest and its external validator are authoritative for those final
  input identities.

## EXP-518/519 post-freeze local quality pair

- EXP-518 executed the exact eight-check topology after the amendment-002 record freeze. All 427
  tests passed with zero failures, errors, or skips; path coverage was
  `78.16118753400171%`; Ruff, expanded medium/high Bandit, runtime/build, CPU-CI and GPU-research
  strict audits, and `git diff --check` all exited zero. The quality-summary and recorded metadata
  SHA-256 values are `919f88939c2c27ba99d8635d774df6f4c31f17c56ce0c0c24ccb2e14b81e5729`
  and `872ed9956986a588fcce6dd48b3368151989c3402fa673a8603429aedc7a6fb3`.
- EXP-519 independently rehashed every log, reparsed JUnit and coverage, and verified the eight
  normalized commands, 427/427 topology, zero skips, and scope-limiting claim flags. Validation
  and metadata SHA-256 values are
  `bd057e4fea03f68b5b3cffa117091bdcc6cda5631ec53fb1f9fb8dbe69b53ca7` and
  `bf5d1f56b7c43d5b1da427ff3077b4957c9f4203a36f6cdffb60e6d196917fa9`.

## EXP-520--523 release-0.11.2 archive and PDF chain

- EXP-520 built the 531-file, 93,161,346-byte deterministic 0.11.2 archive from EXP-518/519.
  Archive, external manifest, and metadata SHA-256 values are
  `7dc8b4fa4dc73acfdd7808c47f0d99dd3aa8a1c30e49acd59c1650157305d7b4`,
  `fcaee684f81947b361a7ba842d470098371a2f6db027378c18d0831a1d0a54a1`, and
  `b535a345fe8c9cfe4e825e8a78ef17280e50cfe20daeb3c392f2c13d554d447a`.
- EXP-521 independently reopened the archive, verified 531/531 members and normalized metadata,
  and confirmed exclusion of raw data and human submission fields. Validation and metadata
  SHA-256 values are `d18ca4b07b4c075db8c8fe5eb5ed7cb0d4a007a1282f9d052499bc4d59d706c9`
  and `ad5f887df7435ba8c17857aa511854ab167213b5b1a1436a95eca5b1a0c74dd7`.
- EXP-522 rerendered the 24-page/five-figure watermarked empirical PDF. The PDF remained
  byte-identical at `c041274804f7818b97f002d47ccde97baf23e67c42d6ad4506d89b73daf4b463`;
  report and metadata SHA-256 values are
  `5b152cc640d1c3b2898a5f7f9b36062e2b605b6667841f550331b43895c575a9` and
  `c2e5a9bed69f8109bf6f3b2c8e33ec1067a9774b61a0da651b480080626a31e8`.
- EXP-523 independently bound the PDF to the 0.11.2 archive and all upstream validators, with 24
  pages and five ordered figure titles. Validation and metadata SHA-256 values are
  `61d2bbe31fbfca4e709c60e0cae4a03f14ab8baee2a077f00636f752cf5e2796` and
  `3fe2bd383f60a08c5da071bc1d9bcca441be2a10c015c965bc69ed1618c4c911`.

## EXP-524 retained 0.11.2 artifact-reproduction boundary failure

- EXP-524 began from the validated 0.11.2 archive, matched two extractions, created a fresh Python
  3.12 virtual environment, installed both locks with hashes and the project non-editably, passed
  CPU/installed-lock checks, and freshly acquired all five public fixtures. Ruff, 427/427 tests,
  `78.07569752078962%` coverage, Bandit, all three strict dependency audits, archive reopening, and
  released final-quality validation exited zero.
- Step 20 failed because the general artifact validator required `vibration_windows.npy`, an
  unconsumed raw signal output deliberately excluded from the raw-data-free archive. The failure
  and bounded recovery are recorded in `research/EXPERIMENT_INCIDENTS.md` and
  `research/BEARING_RELEASE_AMENDMENT_003.md`. EXP-524 remains failed; its passing prefix is not a
  complete reproduction. Failed summary, JUnit, stderr, and metadata SHA-256 values are
  `227331201e73b71803c74149ceb6a3bb025c2648e6297a5700f674a737976887`,
  `74b0a8de97d19dfc856cbf30f4dcf945cf36138ddc48f785a7d246224d8ef6ad`,
  `bcffb2cbe1747a0d05f718680ed05fa7dc43a6d0e205bebead3711b01de8e18b`, and
  `950c9655c7fe7de95700fb700af3e7ab614140faecadc340aa0a913b8e00e6d3`.

## Release amendment 003 and EXP-525 focused validation

- Release 0.11.3 adds an explicit release-input mode to the artifact generator and independent
  validator. It may skip only unconsumed outputs declared by parent summaries; all 28 actual
  manifest inputs, consumed CSV/provenance hashes, six no-refit validations, scientific decisions,
  and 42 output identities remain mandatory. Default mode retains complete parent-output checking.
- The existing artifact/release test family was strengthened without increasing the 427-test
  topology. It proves that default mode rejects a missing raw array, release mode regenerates an
  exact manifest/42-output package without it, release-input validation passes, and removal of a
  consumed raw-window index remains fatal. EXP-525 passed 22/22 focused tests with zero failures,
  errors, or skips; focused Ruff also passed. JUnit and metadata SHA-256 values are
  `3ced76a02bfda72a45e3c958fae325414751020231623205e70d469b9dd80cd1` and
  `f162281645e5701baa08606ed9eddb88512eb74e4514396fc59a7ece71f2eee5`.
- This record precedes the amendment-003 freeze. A new complete quality pair, 0.11.3 archive/PDF
  chain, and from-scratch archive-source run must supersede all 0.11.2 candidates before public
  release. None of these author-operated records claims detached Git/DOI reproduction, third-party
  independence, human review, or submission readiness.
