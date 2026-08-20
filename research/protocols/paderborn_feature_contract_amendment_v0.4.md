# Paderborn feature-contract amendment v0.4

- Status: frozen final feature-extraction contract
- Frozen: 2026-08-18
- Supersedes execution authorization in: `paderborn_feature_contract_amendment_v0.3.json`
- Predecessor SHA-256: `1f1ffaf605c8281daef509c5788928c36e1a759ab7fd72ec4743b0007fc7bd99`
- K001 structure-inventory amendment: `b5dc4bc84fd4f3c34522b1de7a09cead0d17c437201d2c64fb62d4ec8a11b812`
- K001 structure inventory: `c95510888bc851a7fb60644626f11e5448c1eef4613514e1b88873fb35408d5e`

## Outcome-blind structural evidence

The authorized K001 inventory covered all 80 predeclared MAT measurements. In every
file, vibration, current-U, and current-V were one-dimensional `float64` arrays with
the same within-file length. The inventory contained 38 distinct common lengths,
ranging from 256,000 to 261,196 samples. Five files contained 256,000 samples, 34
contained 256,001, and the remainder contained longer acquisitions. No signal
value, value-dependent statistic, feature, prediction, metric, or model outcome was
emitted. The inventory also confirmed two regular PDF files; both remain quarantined
and unused.

The inventory output is 131,928 bytes with SHA-256
`c95510888bc851a7fb60644626f11e5448c1eef4613514e1b88873fb35408d5e`.

## Final frozen window rule

Each of the three semantic channels must be one-dimensional and finite, all three
must have exactly the same stored length within a measurement, and that common
length must be at least 256,000 samples. The parser retains exactly the first
256,000 samples from every channel, representing the original half-open four-second
window `[0, 4s)` at 64 kHz. A shorter channel or unequal channel lengths abort the
run. No maximum stored length is imposed because the locked files and exact member
hashes already define the corpus and any tail beyond four seconds is deterministically
excluded.

This rule is uniform across all filenames, bearings, operating settings, labels,
folds, methods, and seeds. The bulk MAT inventory now records both the observed
common stored length and the retained length for every measurement, making the
normalization fully auditable without affecting features or models.

The representation remains the same 72 frozen whole-window features. The v0.2
non-MAT quarantine rule remains unchanged. No split, model, hyperparameter, seed,
endpoint, effect-size threshold, or statistical procedure changes.

## Frozen revised artifacts

- K001 structure-inventory `metadata.json`: 12,100 bytes, SHA-256
  `c354cf4486f9205f749e18db5000aa7e3d42bb79530d6b69c19ab5e3675ef32c`
- `src/smartvalve/data/paderborn_features.py`: 4,127 bytes, SHA-256
  `00bab4e4e2b9bf7e2557177a5cc2072f11b9dd5e105f448e562b11f9e408df9a`
- `src/smartvalve/data/paderborn_mat.py`: 8,047 bytes, SHA-256
  `c7e85d3503fe5c1072f5663d4ed5e364d5b074bc1621f8e79cbd770aa1483eae`
- `src/smartvalve/experiments/paderborn_feature_run.py`: 27,948 bytes,
  SHA-256 `54918a4dd49fdeb264482ad3272e58f16e462d8601e49552418b68bf76a39390`
- `tests/test_paderborn_features.py`: 2,433 bytes, SHA-256
  `1853da59462bfef56cef269a724ae0b93d65308a8be2f0c8cd09d2e002765aa6`
- `tests/test_paderborn_mat.py`: 5,346 bytes, SHA-256
  `f6ebdd8c55703d4ef72754e93f489874cef56aef6825a3c5da6a4eaf2b92dfe1`
- `tests/test_paderborn_feature_run.py`: 10,520 bytes, SHA-256
  `4cb8a2681039724af86e73abc86d5c6dd4a9ba4b06881aaedc45c584533534a1`

Targeted lint and all 21 feature/parser/probe/inventory tests passed before v0.4
was frozen.

## Authorization and prospectivity

This amendment authorizes integrity-checked processing of the 32 locked archives,
the exact 2,560 MAT measurements, non-MAT quarantine records, and the frozen
72-feature matrix. It authorizes recording stored/retained sample counts. It does
not authorize model fitting, prediction, metric computation, target-guided
reselection, or model-outcome access.

This final window rule is structure-informed and follows aborted transient feature
computations, so the pipeline is not strictly pre-feature in execution history. No
persisted feature value or model outcome was exposed, and only keys/shapes/dtypes
in K001 informed the rule. The model comparison and statistical evaluation remain
outcome-blind. The paper must disclose this distinction and the amendment chain.
