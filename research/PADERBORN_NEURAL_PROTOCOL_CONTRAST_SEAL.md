# Paderborn neural protocol-contrast development seal

- Frozen: 2026-08-19 (Asia/Shanghai), before EXP-434 execution
- Status: retrospective D2 development; never confirmatory
- Extends: `research/PADERBORN_PROTOCOL_CONTRAST_SEAL.md`

## Locked inputs

- EXP-406 primary feature matrix SHA-256:
  `c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4`
- EXP-417 crossed-holdout prediction SHA-256:
  `5e3801e9df4636f180e85ccde060fade77422dfbcb65d5699bf7a93a49d9b400`
- Original D2 prospective seal SHA-256:
  `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`
- PIRL development-selection metrics SHA-256:
  `90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7`
- DG development-selection metrics SHA-256:
  `7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b`

The existing crossed predictions are imported rather than refit. Their fold builder must be
byte-equivalent in source/target/quarantine and pair coordinates to the new generic protocol
builder. Any parity failure stops execution.

## Frozen methods, configurations, and seeds

The nine methods are `PIRL-ratio`, ERM, CORAL, VREx, GroupDRO, DANN, LISA, MatchDG, and CCDG.
Their exact D0/D1-selected configuration objects and candidate identifiers are loaded from the
original prospective seal; no parameter may be altered. All use 300 full-batch epochs and the same
tabular encoder family already evaluated in EXP-417. Seeds are exactly `11, 23, 37, 53, 71`.

The three newly trained protocols contain 16 folds: six measurement-random, four setting-holdout,
and six identity-holdout. This yields `16 × 9 × 5 = 720` new fits. Together with 1,080 imported
crossed fits, each protocol/method/seed must predict all 2,319 rows exactly once, for 417,420
seed-level prediction rows total.

## Invariants held across protocols

- The 72 EXP-406 features, architecture, optimizer, epoch budget, selected hyperparameters, and
  seeds do not change.
- Environment IDs remain the four operating-setting codes in every protocol. This is intentional:
  only data access changes, not the semantic environment definition available to DG methods.
- Nuisance and fault pairs are rebuilt from source rows only with the exact EXP-417 Paderborn pair
  rules. Target and quarantine coordinates cannot appear in either pair array.
- Preprocessing is fitted on each source partition inside the frozen trainers.
- There is no validation, early stopping, hyperparameter search, checkpoint choice, or target-aware
  model selection in EXP-434.
- The two XOR cross-arms remain inaccessible in crossed folds. They are ordinary source or target
  rows only where another protocol explicitly grants that access.

## Estimation and uncertainty

For every protocol/method/row, average the three class probabilities over the five seeds, then take
the argmax. Map all predictions to the same 24 identity-fold × setting evaluation cells. Report the
same pooled and cell-level metrics, protocol-minus-crossed effects, rank concordance, and 2,000-draw
class-stratified paired bearing bootstrap specified in the classical contrast seal.

The main descriptive quantities are:

1. measurement-random minus crossed pooled macro F1 for each non-dummy neural method;
2. the drop in minimum 24-cell macro F1;
3. Kendall rank agreement between each easier protocol and crossed holdout;
4. whether any method's relative rank or apparent gain over ERM changes by protocol.

No p-values, target-selected thresholds, or confirmatory labels are allowed. A ranking that does
not change must be reported just as prominently as a reversal.

## Fail-closed checks

Stop before scoring if any input hash or selected configuration changes, CUDA is unavailable, the
new crossed fold topology differs from EXP-417, a fold loses a class or valid source pair topology,
a protocol/method/seed misses or duplicates a target row, probabilities are non-finite or fail to
sum to one within `2e-6`, metadata differ from EXP-406, the crossed import has anything other than
1,080 model-fold groups, or the five-seed ensemble is incomplete.
