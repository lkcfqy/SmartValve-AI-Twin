# Paderborn raw-architecture sensitivity seal

- Seal version: `smartvalve-paderborn-raw-sensitivity-seal-0.1.0`
- Frozen: 2026-08-19 Asia/Shanghai, before raw-window extraction and before any model fit
- Study role: retrospective architecture sensitivity, never confirmatory
- Outcome access at freeze: compact-feature Paderborn protocol outcomes are known; no raw/FFT/STFT
  architecture outcome under the SmartValve factorial splits has been computed or inspected
- Configuration search after seal: prohibited

## Question and advancement rule

This auxiliary analysis asks whether the random-versus-strict-crossed access effect survives three
raw-vibration architectures outside the 24-statistic representation. It does not test the
nine-method ranking claim under another backbone.

The representation-sensitivity rule passes only if all three model point effects
`measurement_random pooled macro F1 - crossed_holdout pooled macro F1` are positive, all three
2,000-draw physical-bearing percentile interval lower limits are above zero, and the median point
effect is at least 0.15 macro F1. Every model, point estimate, interval, failure, and null result is
reported regardless of the rule.

## Prior-art and licence boundary

The architecture layers adapt the MIT-licensed `pdm-bench` repository accompanying Knap,
Jachymczyk, and Lalik (2026), *Leakage-Safe, Reproducible Benchmarking for Vibration-Based Fault
Diagnosis*, DOI `10.36001/phme.2026.v9i1.4924`.

- repository: `https://github.com/1Sensor/pdm-bench`
- pinned commit: `ca524087219fd47bb7fb51ce63563c05b34cd6ee`
- commit date: 2026-03-24
- upstream `LICENSE` SHA-256:
  `01a838da78ab5ea53a35ddff5b3530e54601faf51584138ef4fb6e74a5b65805`
- upstream model source SHA-256:
  `1623d566d69ecf185c68ddb38dd19a52a601fc3498458ee6726074d33cca76f7`
- upstream common configuration SHA-256:
  `99c731242f25810038398243375f267d6af6b550b0022df0833c9ce2e7573325`
- upstream PU operating-condition task SHA-256:
  `964133047ab8d394223df628ca767b4d402fa9036157d37705078dd1a1bba7ac`
- upstream PU bearing-instance task SHA-256:
  `db43814b771ad1a3502d581ea4a698c0af96a2d466cd731b451a5cb2eb3120f5`
- local notice SHA-256:
  `c041cd33035298b03a0af72eff40762a76b5e2fbcaa3d9718f613c11c3b572f2`

Knap et al. use separate cross-operating-condition and cross-bearing-instance scenarios and dense
50%-overlapping windows. SmartValve changes the split to simultaneous identity-by-setting access,
uses four fixed whole-record positions for tractable fold-complete inference, makes CUDA operations
deterministic, aggregates at recording level, and bootstraps physical bearings. The result is an
attributed architecture adaptation, not an exact reproduction of their scenarios or scores.

## Frozen source data and raw-window artifact

- Sealed Paderborn feature summary:
  `artifacts/research/runs/EXP-406-PADERBORN-FEATURES__20260818T141439.240427Z__v05-resampled-outcome-blind-features/outputs/metrics.json`
  — SHA-256 `4425947919dc8e6730c7cf83dc8e33a8b58a64e07d777cd14527806667663de2`.
- Primary 2,319-record feature/metadata matrix SHA-256:
  `c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4`.
- MAT member inventory SHA-256:
  `2e737599c098d2edb2d6b710cc4c3b18784276278cbc26d79ba2a8d464a48423`.
- Archive lock SHA-256:
  `aadfde07c8b23764208794b0165ac6fe5a90a97345bfa368c01eb047dbedc3d2`.
- Frozen `unrar-nonfree` SHA-256:
  `c02de05961b3d6f2a6309b4c40faaaad7891b1a44acdf0f57b882cf2b3612c26`.
- Channel: semantic `vibration_1` only, normalized by the existing full-record endpoint policy to
  exactly 256,000 native-rate samples.
- Window length: 8,192 samples at 64 kHz.
- Windows per record: four, at frozen offsets `0`, `82,603`, `165,205`, and `247,808`.
- The first and last windows touch the record boundaries; the two interior offsets are the rounded
  equally spaced locations between them.
- Stored window dtype: float32. Per-window mean/std normalization occurs lazily inside each training
  view. No label or model outcome chooses an offset.
- Each extracted MAT byte hash must reproduce the sealed member inventory. The raw-window NPY,
  row/window index, extraction traces, and summary receive SHA-256 hashes before fitting.

## Frozen access protocols

Only two pre-existing protocols are used:

1. `measurement_random`: the same six stratified record folds and random seed as EXP-434B; and
2. `crossed_holdout`: the same 24 identity-fold-by-setting intersections, with both XOR cross-arms
   quarantined from fitting.

Every one of the 2,319 records is a target exactly once per protocol. All four windows of a record
travel together. No target or quarantine window may enter training, normalization across records,
model selection, scheduler decisions, or calibration.

## Frozen architectures and optimisation

Three architecture labels are fixed:

- `cnn1d`: Conv1d 1→32 (kernel 7), 32→64 (kernel 5), 64→128 (kernel 3), batch normalization and
  ReLU after each convolution, global average pooling, 128→64→3 head, ReLU and dropout 0.4;
- `fft`: per-window log-amplitude real FFT, one-channel instance normalization, followed by the
  same 1D convolutional stack and head; and
- `stft`: log-magnitude STFT with Hann window, `n_fft=1024`, hop 256, centered frames, one-channel
  2D instance normalization, Conv2d 1→32→64→128 with two 2×2 max-pools, global average pooling,
  and the same head.

For every architecture/fold/seed: AdamW, learning rate 0.001, weight decay 0.0001, batch size 128,
50 fixed epochs, cross-entropy, gradient clipping at norm 1.0, and ReduceLROnPlateau factor 0.5 with
patience 3 driven only by the epoch's source-training loss. No target validation or early stopping
is allowed. Seeds are the Knap repeated-run set `41, 42, 43`. cuDNN benchmarking is disabled,
deterministic algorithms are required, and `CUBLAS_WORKSPACE_CONFIG=:4096:8` is fixed.

Fit count is `(6 random folds + 24 crossed folds) × 3 architectures × 3 seeds = 270`.

## Frozen aggregation and inference

For each fit, softmax probabilities are retained for every target window. The four window
probabilities are averaged to one recording probability within seed; the three seed probabilities
are then averaged to one out-of-fold recording probability. Argmax occurs only after each averaging
step. The primary metric is pooled recording macro F1; balanced accuracy, accuracy, minimum-class
recall, and the same 24-cell distribution are secondary.

Uncertainty uses 2,000 paired, class-stratified physical-bearing bootstrap draws with the same draw
for both protocols and all architectures. All settings, measurements, windows, and predictions for
a sampled bearing move together. Seeds, windows, measurements, and folds are not inferential
replicates. Intervals are cohort-conditional percentile summaries, not population guarantees or
hypothesis tests.

## Locked local implementation

| Role | Path | SHA-256 |
|---|---|---|
| third-party notice | `THIRD_PARTY_NOTICES.md` | `c041cd33035298b03a0af72eff40762a76b5e2fbcaa3d9718f613c11c3b572f2` |
| raw models/aggregation/inference | `src/smartvalve/experiments/paderborn_raw_sensitivity.py` | `6d2a83c0618a53075a18d28b37d40a77f949b2156f5eca38fc96029c17331d1a` |
| raw-window producer | `scripts/paderborn_raw_window_artifact.py` | `3acb3b8f4c69e50f973d09eead5d87006cc9afc82a87f7ce980d7baed65927d5` |
| model producer | `scripts/paderborn_raw_architecture_sensitivity.py` | `ff5118611116bc3df8f86290cb7674a5260576e768d69cc905508fae7a919a52` |
| independent validator | `scripts/validate_paderborn_raw_architecture_sensitivity.py` | `b5e5fa6757fa7b9a8d56495e26b3c60b28af47cef78f2ded15ae531794b4b48b` |
| focused tests | `tests/test_paderborn_raw_sensitivity.py` | `de3ff6be5ba515dcc7d3b0fdafed8675a434f03ddcc3e0084edee12778c9d680` |
| four-protocol splitter/scorer | `src/smartvalve/experiments/paderborn_protocol_contrast.py` | `ab0868435584a8cda8676f7fae87642151132f70277598a85c1dbdb4c72f88d9` |
| strict partitions | `src/smartvalve/experiments/paderborn_partitions.py` | `ee7cb3aa6d2be59cfa380ebaf2625919c1efc24e125b0cf78332127a95bc4e27` |
| semantic MAT parser | `src/smartvalve/data/paderborn_mat.py` | `1c858ef261a1a38f956742365a50e78a66b8f486905994c411c9117b90c7f728` |
| sealed archive streaming support | `src/smartvalve/experiments/paderborn_feature_run.py` | `e88cc5aa8a78d18a47c1deab04b2634a3d2ce9c45bd02555213bda55bd0643cd` |

Before this seal, focused Ruff passed and 40 relevant tests passed, including a one-epoch CPU
fit/predict smoke test and shape tests for all three architectures.

## Runtime lock

- Python 3.12.3
- NumPy 2.5.1
- pandas 2.3.3
- SciPy 1.18.0
- scikit-learn 1.9.0
- PyTorch 2.13.0+cu130; CUDA 13.0; cuDNN 92000
- pyarrow 23.0.1
- NVIDIA GeForce RTX 3080 10,240 MiB; driver 610.74

The formal run metadata additionally records the complete environment and source-tree fingerprint.

## Independent validation and reporting

The validator must lock every declared output and, without fitting, reproduce four-window
aggregation, three-seed ensembling, record metrics, cell metrics, the exact bootstrap draw plan,
effects, intervals, and the frozen gate. It must also verify 270 distinct model states and the full
protocol/model/seed/row/window topology. Any failure is retained; a validator-only correction must
be documented and cannot alter a fit, probability, endpoint, threshold, or gate.

## Non-claims

- This is not the first raw, FFT, STFT, CNN, leakage-safe, or Paderborn bearing benchmark.
- Four deterministic windows are a bounded compute sensitivity, not dense-window reproduction of
  Knap et al. and not a foundation-model baseline.
- Passing the gate would strengthen only the access-gap conclusion. It would not externally validate
  the nine-method ordering under raw architectures.
- Failure would not invalidate the compact-feature protocol estimand; it would make representation
  dependence a headline limitation.
- No causal leakage amount, safety claim, cross-factory guarantee, or state-of-the-art performance
  claim is permitted.
