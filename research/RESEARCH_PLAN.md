# SmartValve causal-audit research plan

- Plan version: `0.3.0`
- Initial protocol frozen: `2026-08-17`
- Execution update: `2026-08-18`, after EXP-020; hypotheses and frozen protocols are unchanged
- Repository baseline: `0dc184370e37833c74f32c529a7ef30d5df351ce`
- Primary dataset: Cranfield Real Linear Actuator Rig
- Final execution update: `2026-08-18`, after sealed D2 and the six-test Holm family
- Current phase: the original one-rig plan is historical. The multi-rig experiment completed and
  its algorithmic gate failed; `TOP_TIER_UPGRADE_PLAN.md` and `D2_FINAL_DECISION.md` govern current
  claims.

## 1. Research objective

The first paper will test whether industrial fault classifiers identify fault mechanisms or exploit
operating-condition fingerprints. The initial causal abstraction is:

```text
fault mechanism F  ---> sensor trajectory X <--- operating condition E
                                      ^
                                      |
                              asset/run identity U
```

The diagnostic model solves the inverse problem `X -> F`. Accuracy under a random or average split
does not establish a causal representation. We therefore use pre-specified label-preserving changes
of `E` as negative controls and fault changes as positive controls.

Final multi-rig working title after EXP-422B:

> Access, Abstention, and Non-Replication: A Prospectively Sealed Multi-Rig Audit of Industrial
> Fault Diagnosis

## 2. Claims that are and are not in scope

In scope:

- reproducible comparison of explicit deployment protocols;
- robustness to unseen load within each motion family;
- sensitivity of class probabilities to label-preserving load changes;
- the value and cost of target-condition healthy calibration;
- uncertainty, calibration, worst-group performance, and paired-control metrics.

Out of scope for the Cranfield phase:

- identification of a complete physical structural causal model;
- individual-level counterfactual recovery from unpaired experimental noise;
- water-valve, Weilong-product, field, RUL, leakage, or safety-certification claims;
- independent-asset generalization, because the public data come from one actuator rig.

The audit may falsify a causal or invariance claim. Passing the audit alone does not prove causal
identifiability.

## 3. Pre-specified hypotheses

- `H1`: the checked-in matched-reference result is reproducible within numerical tolerance.
- `H2`: aggregate accuracy hides a materially weaker worst operating group.
- `H3`: access to a healthy reference from the held-out target load materially changes performance;
  this gain must be reported as calibration, not pure domain generalization.
- `H4`: some methods with similar macro F1 have different nuisance-intervention sensitivity.
- `H5`: model ranking changes when worst-group, calibration, and control metrics supplement macro F1.

No hypothesis will be rewritten after its primary result is observed. Later exploratory hypotheses
must receive a new protocol version and experiment ID.

## 4. Cranfield protocol ladder

All primary folds hold out one complete load within one motion family. Windows are never randomly
split. The three reference-access protocols are evaluated separately:

1. `raw_no_target_reference`: raw trial features; no target-domain healthy calibration.
2. `source_healthy_reference`: the reference is derived only from healthy trials in training loads.
3. `matched_target_healthy_reference`: a different healthy repetition from the same motion and load
   is available at inference, matching the existing deployment assumption.

These protocols answer different questions and must never be pooled into one headline number.
Details are frozen in `research/protocols/cranfield_audit_v0.1.md`.

## 5. Experiment sequence

| ID | Purpose | Status | Decision use |
|---|---|---|---|
| EXP-000 | Clone, environment, hardware, and dependency fingerprint | complete | establishes provenance |
| EXP-001 | Locked lint/test baseline | complete | verifies checkout integrity |
| EXP-002 | Public-data sync and SHA-256 verification | complete | freezes inputs |
| EXP-003 | Reproduce checked-in Cranfield ExtraTrees result | complete | validates H1/H2 |
| EXP-010 | Five-seed comparison of three reference-access protocols and controls | complete, falsified | validates H3/H4/H5 |
| EXP-011 | Paired trial-block bootstrap | complete | quantifies uncertainty |
| EXP-012 | Source-only conformal abstention on unsupported environments | complete, exploratory | tests safe failure handling |
| EXP-020 | Environment probe plus fixed classical estimator suite | complete, model-independent criterion failed | diagnoses shortcuts and claim robustness |
| EXP-PAPER-002 | SHA-locked tables, figures, captions, and claim map | complete | freezes manuscript evidence |
| EXP-030 / EXP-100–111 | Second physical dataset | complete: frozen UCI audit, identity check and physical-block intervals | external development evidence |

## 6. Baseline suite

Start with low-variance, low-compute methods before neural architectures:

- multinomial logistic regression;
- RBF SVM;
- Extra Trees;
- HistGradientBoosting;
- a small MLP or 1D-CNN only after the tabular protocol is stable;
- CORAL, GroupDRO, and one recent reproducible industrial-DG method in the multi-dataset phase.

All preprocessing is fitted on the training partition only. Hyperparameter selection must use an
inner split of source loads/runs; the held-out load cannot select a model or threshold.

## 7. Primary metrics

- trial-level accuracy and macro F1;
- worst-fold accuracy and macro F1;
- multiclass Brier score and expected calibration error;
- paired nuisance sensitivity across loads for fixed `(motion, fault, repetition)`;
- paired fault sensitivity for fixed `(motion, load, repetition)`;
- control ratio `nuisance_sensitivity / fault_sensitivity` (lower is better);
- 95% confidence intervals from block bootstrap over complete three-class trial blocks.

Average accuracy is never reported without the worst fold and its sample count.

## 8. Go/no-go rule after the first audit

Continue to a multi-dataset paper if at least one of the following is observed with a trial-block
bootstrap interval that does not collapse to a negligible effect:

- method ranking changes under the audit metrics;
- target healthy calibration changes macro F1 or worst-fold performance materially;
- nuisance sensitivity reveals a failure hidden by aggregate F1;
- a complex baseline is no more robust than ERM/ExtraTrees under the same protocol.

If none occurs, stop the benchmark expansion and pivot to mechanism-grounded reasoning on
FactoryBench. Negative results remain in the ledger.

### EXP-010 decision update

The project passes the *continue-investigating* gate, not the robustness gate:

- P2 target calibration changes average macro-F1 only modestly but changes method ranking and
  deployment requirements;
- P1 source-linear extrapolation is substantially worse than P0 and increases nuisance sensitivity;
- all three protocols collapse to a constant class on `trap/-40` for all five seeds, a failure hidden
  by aggregate macro-F1 around 0.75-0.87;
- therefore the immediate paper contribution is a falsification/audit plus safe abstention and a
  mechanism-aware correction, not a claim that reference normalization solves domain shift.

No new representation will be called successful unless it improves `trap/-40` under source-only
selection or abstains on that environment without using its labels.

### EXP-011/012/020 decision update

- The paired block bootstrap does not resolve a P2-over-P0 macro-F1 advantage, while P2 has a
  reliably worse ExtraTrees Brier score. P1 is reliably harmful.
- Source-only conformal singleton selection accepts every observed P0 `trap/-40` error. It cannot
  be presented as shifted-target risk control.
- A post-EXP-010 hybrid support/conformal rule observes zero accepted errors at about 46.3%
  coverage, but is exploratory, rejects correct low-load sinusoidal trials, and has no target-risk
  guarantee.
- The catastrophic P0 `trap/-40` collapse is not model-independent: only ExtraTrees meets the
  frozen all-seed chance-level criterion. The manuscript must report this falsification prominently.
- Load remains perfectly decodable from P0 and substantially decodable from P2 under
  repetition-disjoint probing. This is evidence of nuisance retention, not causal use by a fault
  classifier.
- The first manuscript is therefore an audit/negative-result paper. It does not claim a new causal
  DG or conformal algorithm. A stronger submission will require prospective validation on an
  independent asset or dataset.

## 9. Reproducibility and record policy

Every run must be launched through the recorded-run wrapper and produce:

- immutable run ID and UTC timestamps;
- exact Git commit plus dirty-tree diff hash;
- command, working directory, exit code, stdout, and stderr;
- Python, OS, CPU, memory, GPU, and selected dependency versions;
- input manifest and SHA-256 hashes;
- output file sizes and SHA-256 hashes;
- a human interpretation appended to `research/EXPERIMENT_LEDGER.md`.

Failed and null runs are retained. A run directory is never overwritten. Secrets and full process
environments are not recorded.

## 10. Twelve-week schedule

- Weeks 1-2: EXP-000 through EXP-012 on Cranfield.
- Weeks 3-5: baseline suite and a second actuator/bearing/robot dataset.
- Weeks 6-7: intervention cards, metric validation, and statistical analysis.
- Weeks 8-9: calibration, abstention, ablations, and robustness checks.
- Week 10: freeze code, protocol, test data, and artifact release.
- Weeks 11-12: manuscript, appendix, model cards, and archival release.

The schedule targets a submission-ready manuscript, not guaranteed acceptance.
