# Source-OOF selective evaluation — frozen v0.1

- Drafted: 2026-08-18
- Frozen: 2026-08-18, before any selective refit or selective target result
- Status: execution authorized only with every exact hash below
- Data roles: D0 Cranfield and D1 UCI Hydraulic development only
- Target access class: P0 for every fitted model and every rejector decision
- D2 state: archive contents remain unopened

EXP-340 finished with exit code 0 and its artifacts passed the predeclared EXP-338 structural
manifest in EXP-340-VALIDATE. No selective model has been refit and no selective target result has
been inspected at the time this copy is frozen.

## Question and claim boundary

The experiment asks whether the proposed PIRL response-ratio representation combined with a
source-selected risk envelope improves failure-aware selective prediction relative to a tuned,
identical-backbone ERM. It does not claim finite-sample target coverage, conformal validity under
domain shift, calibrated probabilities, or superiority to every open-set/OOD method.

The strong DG methods in EXP-340 are closed-set generalization comparators. The confirmatory
selective comparison is deliberately limited to PIRL and tuned ERM so that rejection-score effects
are not conflated with eight separate model-selection searches. Score-family comparisons within
each model are secondary.

## Immutable inputs

1. EXP-330 metrics SHA-256: `90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7`.
2. EXP-330 predictions SHA-256:
   `a32e0b8bfa7d8a522fa7e26bb26e2ac6f4113d32e5a3589f2b5c106e6f69ed22`.
3. EXP-330 selected PIRL configuration: `r64_l1p0_m0p5`, 64-dimensional representation,
   intervention weight 1.0, fault margin 0.5, 300 epochs, AdamW learning rate 0.001 and weight decay
   0.0001.
4. EXP-340 metrics SHA-256:
   `7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b`.
5. EXP-340 predictions SHA-256:
   `7691980fbd47a209d79629c65bb3490ffc866645eec48f4c07509535fdfbe2d6`.
6. EXP-340 selected tuned-ERM configuration: `erm_r64`, 64-dimensional representation,
   128-dimensional hidden layer, 300 epochs, AdamW learning rate 0.001, weight decay 0.0001,
   gradient clipping norm 5.0 and no DG penalty.
7. UCI feature matrix SHA-256:
   `4359ce099e421cc9e55c65115d39f4a4c0463255f72f834a49d802fa6a038516`.
8. EXP-340 launch source-tree fingerprint:
   `e658ac4599d2edb3d184c2c49b0f66541bf83a2de74a7090fba1a75c7752af43` over 215 files.
9. EXP-340-VALIDATE result SHA-256:
   `f24815fac5af7fb1409a223670ebb96eace55f1f962b086689c48caf81bae031`;
   validation passed against pre-run manifest SHA-256
   `79e68f95e9a5d88921fa79c1d50f34aa84db5c156a5e6c5ba516520c97faa862`.
10. EXP-341B selective input-preflight SHA-256:
    `8227754e6548c61f55119170f42624cb16a12eac049facc6c2e3b85bfbf188a6`.
11. EXP-341C outcome-blind selective expected-manifest SHA-256:
    `75af0e966a342b5dbdf245ba78fd34d67da393f6793a6ab75d9d6b61018a45de`.

The formal runner requires the feature, protocol, preflight, expected-manifest and both metrics
hashes on its command line before any GPU fit. It validates every referenced artifact against the
hashes embedded in its metrics record and refuses a PIRL reference that did not pass both frozen
development gates.

## Refit and crosscheck design

Use the three Cranfield leave-one-load-out folds and ten UCI leave-one-context-level-out folds from
EXP-310. Use paired seeds 11, 23, 37, 53 and 71. For each dataset, method, seed and outer fold:

1. partition only the outer-source environments into the same deterministic four inner folds used
   for model selection;
2. fit the already selected configuration on three inner partitions and predict the fourth exactly
   once, yielding one OOF prediction for every outer-source row;
3. fit class-conditional robust representation support on the inner-training representations and
   compute the validation row's minimum robust class-support distance;
4. concatenate all four validation partitions only after their predictions are complete; and
5. refit on the full outer source and predict the untouched outer target.

Every final refit must reproduce the corresponding locked model-state SHA-256 exactly. Target row
keys, truth, prediction and correctness must match the locked reference artifact, and the maximum
absolute probability difference must not exceed `2e-6`. Any discrepancy stops the run rather than
creating a new result.

## Frozen scores

All scores use the convention that larger means stronger rejection evidence.

- maximum-softmax uncertainty, `1 - max(p)`;
- normalized predictive entropy;
- energy uncertainty with temperature 1;
- negative maximum raw logit;
- negative maximum centered logit after row-wise L2 normalization (SmartValve adaptation);
- minimum robust class-support distance; and
- risk envelope `1 - max(p) + beta * distance`.

In addition, form a fixed five-member deep ensemble from the paired seeds by averaging class
probabilities. Its secondary scores are ensemble MSP uncertainty, ensemble predictive entropy,
normalized Jensen-Shannon member disagreement, mean member robust-support distance and an
ensemble risk envelope. Ensemble size five is fixed before any selective outcome is inspected and
requires no additional model fitting.

For each individual or ensemble risk envelope, select `beta` separately inside each
dataset/method/seed/outer-fold source OOF group (the ensemble uses the sentinel seed `-1`) from
`{0, 0.1, 0.25, 0.5, 1}`. Minimize worst-source-environment AURC, then pooled source AURC, then the
smaller beta. This is the only error-informed rejector choice. No target prediction, label,
statistic, batch composition or achieved coverage enters it.

## Frozen thresholds

Evaluate nominal source coverages 50%, 70% and 90%. For each score and source OOF group, take the
larger of:

- the empirical pooled score quantile that accepts at least the nominal source coverage; and
- every source environment's empirical 25%-coverage quantile.

Accept rows whose score is at most this fixed threshold. Source errors are reported but cannot
change a threshold. Ties are all accepted, so realized source coverage may exceed nominal
coverage. The already fixed threshold is applied unchanged to the outer target. Target coverage is
never forced after the fact.

## Metrics and failure disclosure

For every score, fold and seed, retain the complete target risk-coverage ranking and report AURC,
finite-sample optimal AURC, excess AURC, error-detection AUROC and error-detection average
precision. At each source-selected coverage report:

- realized target coverage and accepted errors;
- selective risk and worst-environment selective risk;
- minimum target-environment coverage;
- effective accuracy (correct and accepted divided by all target rows);
- macro F1 with abstention counted as an error;
- error-detection recall and correct-rejection rate; and
- coverage and selective risk by target environment and true class.

Zero global or environment coverage is a result, not an exception. Its selective risk is recorded
as null, its conservative worst-environment risk contribution is one, and its count is surfaced in
every aggregate. Row-level decisions retain physical block identifiers for the later paired block
bootstrap.

The primary selective endpoint for later corrected inference is PIRL minus tuned ERM selective
risk at 50% source-selected coverage using the risk envelope. The 70%/90% points, other scores and
ranking diagnostics are secondary. Effect direction, physical bootstrap implementation and Holm
family are frozen in the later multi-rig statistics protocol before D2 activation.

## Leakage and artifact gates

- Source and target prediction frames are passed to separate functions; policy selection has no
  target argument.
- A target-label permutation test must leave every threshold, beta and acceptance decision
  unchanged.
- All probabilities must be finite and normalized; all scores and support distances must be finite.
- Every OOF source row and target row must appear exactly once per method/seed/outer fold before
  long-form score decisions are generated.
- The formal artifact set contains source OOF predictions, target predictions, all policies, beta
  diagnostics, ranking metrics, row-level decisions, training traces and reference crosschecks,
  each with byte count, row/model count and SHA-256.
- Paderborn archive contents remain unopened throughout this experiment.
