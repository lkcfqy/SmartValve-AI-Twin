# Neural DG source-only selection v0.1

- Status: frozen before any neural-DG outer-target prediction
- Frozen: 2026-08-18
- Development data: D0 Cranfield and D1 UCI hydraulic
- Access tier: P0 source-only
- Prospective D2: Paderborn archive contents remain unopened

## Purpose and comparability

This protocol selects and evaluates strong neural domain-generalization baselines without reading
an outer target row during model selection. Every method uses the same deterministic feature
matrix, source-only standardization, MLP backbone, optimizer, training budget and final seeds as
PIRL. Target rows are used only once per outer fold for final development evaluation.

The suite is tuned ERM, CORAL, VREx, GroupDRO, DANN, LISA, MatchDG and CCDG. MatchDG uses the
audited same-fault cross-context nuisance pairs. LISA mixes those pairs. CCDG follows the paper
authors' public `ERM_Contrastive` semantics: feature-level supervised contrastive loss with class
labels and temperature 0.7. It is a shared-backbone adaptation rather than a reproduction of the
authors' raw-signal network. The inspected authors' code revision is
`de2e7a0600fc44aeefd36e56ccb311257b346d40`. The different Zhao benchmark port at
`370fca37e9323c79384dd1f14d8aac358f4cd359` uses a domain-label call and logistic weight schedule;
both changes are excluded.

## Shared training contract

All models use hidden dimension 128, GELU, LayerNorm, a unit-normalized representation and a linear
classifier. AdamW uses learning rate 0.001 and weight decay 0.0001. Training is full-source-batch
for 300 epochs with gradient clipping at 5. The inner selection seed is 11. DANN uses gradient
reversal coefficient 1.0 before the selected domain-loss weight. LISA uses Beta(2, 2) mixing.

The target-blind grids are:

- ERM: representation dimension 32 or 64;
- GroupDRO: representation dimension 32 or 64 crossed with exponentiated-gradient step size
  0.01, 0.1 or 1.0;
- every other method: representation dimension 32 or 64 crossed with penalty weight 0.1, 0.5 or
  1.0.

This gives 44 unique configurations. Method-specific parameters not named above remain fixed in
the recorded configuration. No method receives target features, labels, normalization statistics,
predictions or batch composition during fitting or selection.

## Inner selection and one common configuration per method

For every outer fold, only its source rows enter the same four deterministic source-environment
partitions used by PIRL v0.2. Every source row receives exactly one OOF probability vector.

The primary selection score is worst exact-source-environment macro F1. Configurations within 0.01
absolute of the outer fold's best score are eligible; among them choose higher overall source-OOF
macro F1, then lower multiclass Brier, then the lexicographic configuration ID.

For each method, choose one common configuration across all 13 D0/D1 outer folds. First take the
mode of the 13 outer choices. A modal tie is resolved by lower mean rank of worst-environment F1,
then overall macro F1, then Brier, then configuration ID. Per-dataset or per-target configurations
are forbidden.

## Final development evaluation and artifacts

Fit each selected common configuration under seeds 11, 23, 37, 53 and 71 on all three Cranfield
and ten UCI outer folds. Persist target probabilities, predictions, representations, diagnostic
risk-envelope scores, source response ratios, candidate OOF metrics, all tuning and final training
traces, peak GPU memory and model-state hashes.

Primary comparison is paired against tuned ERM under the same seeds. Report mean and worst-fold
macro F1, Brier, AURC, risk at 50 percent coverage, representation response ratio and probability
response ratio. These development summaries do not replace physical-block intervals or corrected
multi-dataset inference in the later frozen D2 protocol.

PIRL v0.2 is not reselected in this run. It may be compared from its hash-locked EXP-330 artifact
only if both its frozen mechanism and efficacy gates pass. No outcome from this suite authorizes
opening D2; the complete method, baseline, split and statistical protocol must be frozen first.
