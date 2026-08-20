# Multi-rig method candidates and falsification gates

- Version: `0.1.0`
- Date: 2026-08-18
- Status: development document, not a frozen D2 protocol
- Allowed development data: D0 Cranfield and D1 UCI hydraulic only
- Sealed data: D2 Paderborn archives may be downloaded and hashed but not opened

> **Post-D2 status update (2026-08-19).** D2 has been opened and evaluated. This document's
> pre-D2 wording is retained as protocol history. PIRL v0.2 failed the frozen multi-dataset gate;
> D0--D2 are now development data for any v0.3 decision. See
> `research/V03_CONTRIBUTION_DECISION.md`.

## Candidate contribution

Working name: **Paired Intervention Response Learning with a Source-Only Risk Envelope
(PIRL-SORE)**.

### Development status after EXP-320/321

The original v0.1 hinge below is retained as historical design evidence but is no longer the
headline candidate. EXP-320 showed a UCI performance improvement, and EXP-321 localized most of
that signal to the intervention-only arm. However, the intervention-only arm increased the final
source nuisance/fault response ratio on both development datasets. The frozen mechanism rule
therefore rejected the hinge.

The active v0.2 candidate replaces the saturating hinge with the non-saturating response-ratio
objective

    L_ratio = R_N / (R_F + 0.0001) + max(0, margin - R_F)

and removes the worst-environment training term. EXP-330 selected `r64_l1p0_m0p5` only from inner
source-environment out-of-fold predictions under
research/protocols/pirl_ratio_selection_v0.2.md. It lowered the mean representation and
probability response ratios on both D0 and D1 and passed the frozen efficacy gate, so it advances
to the strong-baseline stage. This gate pass does not authorize D2 or establish a significant
advantage.

This name and formulation are provisional until exact-title searches, D0/D1 ablations and code
tests are complete. The method does not claim causal identification. It uses experimentally
controlled context changes as supervised negative controls and fault changes as positive controls.

Let `z_i = normalize(g(x_i))` be a unit-length representation and `p_i` its class probabilities.
Within source environments, construct two explicitly audited pair sets:

- nuisance pairs `N`: same fault state and matched experimental unit, different operating context;
- fault pairs `F`: different fault states, same context and matched block where the rig permits it.

Define mean squared representation responses `R_N` and `R_F` over the two sets. The proposed
intervention loss is

```text
L_PIR = max(0, R_N - rho * R_F)
```

with unit-normalized representations to prevent a scale-only solution. The primary training
objective is a source empirical-risk term, a worst-source-environment term and `lambda * L_PIR`.
The output-space nuisance/fault total-variation ratio is still an evaluation metric and is not
silently substituted for the training objective.

The rationale differs from marginal domain alignment: a representation is not rewarded merely for
making source domains indistinguishable. It must reduce a known label-preserving response relative
to a known label-changing response. MatchDG, LISA, conditional contrastive learning, DARM and
industrial causal-DG methods remain mandatory closest baselines.

## Source-only risk envelope

The rejector receives no target trajectory, target label or target batch. Candidate nonconformity
uses classifier uncertainty plus normalized distance from source class support:

```text
A(x) = (1 - max_y p(y|x)) + beta * min_y robust_distance(z, source_class_y)
```

`beta`, the acceptance threshold and any temperature/logit normalization are selected only from
nested leave-one-source-environment-out predictions. The selection objective is minimum worst-held-
source selective risk subject to a pre-specified minimum coverage. Maximum softmax probability,
energy, max-logit p-normalization, Mahalanobis distance and ensemble disagreement are separate
baselines, not hidden components chosen on D2.

No target-risk or conformal-coverage theorem is claimed under arbitrary shift. The term “risk
envelope” means an empirical source-environment stress test. Every result must report full
risk-coverage curves, AURC, coverage at fixed source-selected thresholds, accepted errors and
per-environment coverage.

## Pair topology by development dataset

| Dataset | Nuisance pair | Fault pair | Primary held shift |
|---|---|---|---|
| Cranfield | same motion/fault/repetition, different source load | same motion/load/repetition, different fault | one complete load within motion |
| UCI hydraulic | same valve/repetition and other context factors, different source level of tested factor | same exact context/repetition, different valve state | one complete cooler/pump/accumulator level |
| Paderborn (sealed) | same bearing/measurement index, different source operating setting | same setting/measurement index, different pure-class source bearings | one operating setting plus one asset fold |

Paderborn fault pairs are class-matched across assets, not counterfactual states of one bearing;
this weaker topology must be disclosed and ablated. The three compound-damage bearings KB23,
KB24 and KB27 are excluded from three-class fitting and accuracy. They are reserved for a
predeclared open-set abstention stress test, avoiding a post-hoc forced dominant-component label.

## Candidate Paderborn split, not yet authorized for execution

The official documentation supports three pure labels: 6 healthy, 12 outer-ring-damage and 11
inner-ring-damage bearing identities. KB23, KB24 and KB27 contain multiple inner/outer-ring damage
and are not silently collapsed into a pure class. The primary closed-set cohort therefore contains
29 assets; the three KB assets form an outcome-blind compound/open-set stress cohort.

Before archive opening, assign one healthy bearing to each of six folds. Distribute the 12 pure
outer assets as two per fold and the 11 pure inner assets as two in five folds and one in the sixth,
balancing artificial versus real damage origin as far as the official metadata permits. Cross
these six identity folds with the four official operating settings. In each of 24 outer folds,
training excludes both the test bearing identities and the complete test setting; testing uses
their intersection. Therefore every primary test measurement comes from an unseen asset under an
unseen setting.

The metadata-only candidate assignment is fixed in code as follows. It remains a development
manifest—not authorization to open D2—until the full D0/D1 method and baseline choices are frozen.

| Identity fold | Healthy | Outer | Inner |
|---|---|---|---|
| 0 | K001 | KA01, KA04 | KI01, KI04 |
| 1 | K002 | KA03, KA15 | KI03, KI14 |
| 2 | K003 | KA05, KA16 | KI05, KI16 |
| 3 | K004 | KA06, KA22 | KI07, KI17 |
| 4 | K005 | KA07, KA30 | KI08, KI18 |
| 5 | K006 | KA08, KA09 | KI21 |

This is the most even origin allocation permitted by the official counts: five folds receive one
artificial and one real asset within each damaged class; the residual fold receives the seventh
artificial outer asset and the sixth real inner asset. Every fold still contains both damage
origins overall. `smartvalve.experiments.paderborn_splits` validates exact coverage, disjointness,
compound exclusion, class counts, origin coverage and the complete 6 x 4 cross-product without
accessing archive contents.

The 4-second measurement is the prediction unit. The 20 repeated measurements from one
bearing/setting remain clustered. Primary uncertainty resamples bearing identities stratified by
class; measurements and repeated predictions are never treated as independent assets.

## Backbone and tuning candidates (v0.1, superseded by the frozen v0.2 grid)

Initial development uses deterministic per-sensor time/dynamic/spectral features and a compact MLP
so the representation objective, not GPU scale, is tested first. A small raw-signal 1D encoder is an
architecture ablation only after the feature protocol is stable.

Candidate grid, to be reduced and frozen using D0/D1 only:

- representation dimension: `32` or `64`;
- `rho`: `0.25`, `0.5`, or `0.75`;
- intervention weight `lambda`: `0.1`, `0.5`, or `1.0`;
- worst-environment weight: `0` or `0.5`;
- five fixed seeds shared with existing audits.

Nested source-environment validation chooses one configuration per dataset without reading the
outer target level. A single common configuration is preferred for D2; dataset-specific choices
must be justified before the seal is broken.

## Mandatory baselines

1. ERM with the identical backbone and training budget.
2. CORAL, GroupDRO, IRM/VREx and source-only multi-domain adversarial learning.
3. LISA or an equivalent same-label/different-domain selective-mixup implementation.
4. MatchDG when exact object matches are available.
5. CCDG adapted from the paper authors' public implementation, using feature-level
   class-conditional contrast, class labels, temperature 0.7 and source-only loss-weight
   selection; the later Zhao port's domain-label call and logistic schedule are not used.
6. Existing five classical estimators on deterministic features.
7. Rejectors: MSP, entropy/energy, max-logit p-normalization, robust Mahalanobis and disagreement.

All methods receive the same P0 information in the primary setting. Any target-unlabeled, target-
normal or target-labeled method is reported in a separate access tier.

## Development and prospective falsification gates

Reject PIRL as the headline method before D2 if, after physical-block intervals on D0/D1, it fails
both of these criteria relative to tuned ERM:

1. a positive paired worst-environment macro-F1 effect on at least one dataset without a material
   negative effect on the other; and
2. a lower paired selective risk at at least 50% coverage on at least one dataset without hiding
   errors through severe per-environment coverage collapse.

After D2, the method passes the internal multi-rig gate only if the frozen primary comparison
improves worst-environment macro F1 or selective risk on at least two datasets, has no material
regression on the third, and survives the pre-specified correction. Failure remains a prospective
negative result; D2 cannot be reused to select a replacement method.
