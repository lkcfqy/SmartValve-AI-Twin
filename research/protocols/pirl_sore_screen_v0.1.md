# PIRL-SORE D0/D1 initial falsification screen v0.1

- Status: frozen before any neural-network target prediction was produced
- Frozen: 2026-08-18
- Access tier: P0 source-only features
- Development datasets: D0 Cranfield and D1 UCI hydraulic
- Sealed dataset: D2 Paderborn archive contents remain unopened

## Purpose

This run asks whether the provisional intervention loss is worth further development. It is not a
hyperparameter search, a final baseline comparison, or the prospective D2 evaluation. Both a null
result and a harmful result must remain in the ledger.

## Inputs and outer folds

D0 uses all 180 raw-feature trials and globally leaves out one complete load at a time. Both motion
profiles remain in source and target, giving three outer folds with 120 source and 60 target trials.
The nuisance pairs match motion, fault and repetition while changing source load. The fault pairs
match motion, load and repetition while changing fault.

D1 uses the frozen 1,440-cycle, 336-feature matrix with SHA-256
4359ce099e421cc9e55c65115d39f4a4c0463255f72f834a49d802fa6a038516. One complete
cooler, pump or accumulator level is held out, giving ten outer folds. Nuisance pairs change the
tested source factor while matching the other context factors, valve state and repetition. Fault
pairs change valve state while matching exact context and repetition.

The exact row counts and pair counts must reproduce EXP-310-DOMAIN-CONTRACT. Scaling statistics,
class support and every learned parameter are fit on source rows only.

## Frozen model comparison

Both methods use a two-layer tabular encoder with hidden dimension 128, unit-normalized
representation dimension 32, GELU activation, LayerNorm and a linear classifier.

- ERM minimizes source cross entropy only.
- PIRL-SORE minimizes source cross entropy plus 0.5 times worst exact-source-environment risk plus
  0.5 times max(0, R_N - 0.5 R_F).

Both use AdamW, learning rate 0.001, weight decay 0.0001, 300 full-source epochs and gradient-norm
clipping at 5. Seeds are 11, 23, 37, 53 and 71. The training budget, encoder and classifier are
identical. No target batch participates in fitting, early stopping, threshold selection or
normalization.

## Frozen screen outputs

For each outer fold and seed, retain categorical predictions, all class probabilities, normalized
representations, source nuisance/fault responses, source probability total-variation responses,
training checkpoints and model-state hashes.

Report unweighted mean-fold and worst-fold macro F1, accuracy, multiclass Brier score, target
risk-coverage AURC, error rate among the lowest-scored 50 percent, and the source response ratios.
The provisional risk-envelope ranking is uncertainty plus 0.25 times minimum robust diagonal
class-support distance. The 50-percent target ranking is diagnostic only; it is not a deployable
source-selected acceptance threshold.

## Decision boundary

PIRL-SORE advances to source-only tuning only if it improves worst-fold macro F1 on at least one
development dataset without lowering mean-fold macro F1 by more than 0.02 on the other. A reduction
in source representation response ratio without target performance improvement is mechanism
evidence only and cannot pass the efficacy gate.

All comparisons at this stage are descriptive across the five paired model seeds. Physical-block
intervals and multiplicity correction are required before a paper claim.
