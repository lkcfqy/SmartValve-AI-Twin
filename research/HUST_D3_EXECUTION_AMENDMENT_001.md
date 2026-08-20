# HUST D3 execution-only amendment 001

- Date: 2026-08-19 (Asia/Shanghai)
- Status: frozen after structural feature extraction and before any HUST model fit or outcome
- Parent factorial seal SHA-256: `eb66d23601ba21fe70b125d503ec56c51fbcfc2f5c59d6d1f2bf4335485428ef`
- Pre-access expected manifest SHA-256: `1067cb8a8459f933cbda063d2bcd026accf25c49e12dd66c10154833a1361e9b`
- Failed run retained: `EXP-442-HUST-D3-EXECUTION-SEAL`
- Failed validator script SHA-256: `3c650a7a5a3d0259c58cbe04b5c87aeacbe4d81d6d74150b73db06241cf21d5e`
- Failure boundary: 0 HUST model fits, 0 model predictions, 0 model outcomes inspected

EXP-442 stopped while comparing the extracted feature-row identities to the metadata-only expected
manifest. The expected table materializes `row_index=0..449`; the extracted Parquet intentionally
uses physical row order and does not store a duplicate `row_index` column. The validator attempted
to select the absent materialized column before deriving it, producing a `KeyError`.

The only authorized implementation change is:

1. reset the feature table to canonical physical row order;
2. insert the deterministic integer column `row_index = 0, 1, ..., 449` in memory;
3. compare that derived identity table against the already sealed metadata manifest;
4. permit the execution-seal script itself to differ from its pre-access hash only under this
   amendment, while continuing to require exact pre-access hashes for every other locked source;
5. record both the old and amended execution-seal script hashes in the successful seal.

No signal value, descriptive statistic, label-dependent choice, feature definition, row ordering,
cohort, split, pair topology, model, configuration, seed, endpoint, bootstrap, decision gate, or
stopping rule may change. A second exception is not authorized by this amendment.
