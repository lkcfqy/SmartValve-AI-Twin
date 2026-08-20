# PIRL non-saturating response-ratio source selection v0.2

- Status: frozen after EXP-321 and before any real-data pirl_ratio target prediction
- Frozen: 2026-08-18
- Development data: D0 Cranfield and D1 UCI hydraulic
- Access tier: P0 source-only
- Prospective D2: Paderborn archive contents remain unopened

## Reason for the version

EXP-321 rejected the v0.1 hinge as a mechanism: it improved several target metrics but increased
the measured nuisance/fault response ratio on both development datasets. The hinge was already zero
at the final epoch in every fitted model, making its constraint non-persistent.

Version 0.2 replaces only that loss. It retains unit-normalized representations and uses

    L_ratio = R_N / (R_F + 0.0001) + max(0, margin - R_F)

The first term is non-saturating whenever nuisance response is nonzero. The second discourages the
joint-collapse solution. The training objective is source cross entropy plus lambda times L_ratio.
The worst-environment training term is removed because EXP-321 showed it recovered only 22.9
percent of the full model's UCI mean-F1 gain and worsened Cranfield metrics. SORE remains a
separate source-selected rejector, not a training-risk penalty.

## Target-blind candidate grid

The common architecture remains hidden dimension 128, GELU, LayerNorm, a unit-normalized
representation and linear classifier. AdamW, learning rate 0.001, weight decay 0.0001, 300 epochs
and gradient clipping at 5 remain fixed.

The 12 candidates are the Cartesian product:

- representation dimension: 32 or 64;
- lambda: 0.1, 0.5 or 1.0;
- fault-response margin: 0.5 or 1.0.

Fault-margin weight is 1.0 and epsilon is 0.0001. All inner fits use seed 11. No candidate may read
an outer-target row, label, feature statistic, prediction or score.

## Inner source-environment selection

For each of the 13 outer folds, only its source rows are partitioned into four deterministic
environment folds. Cranfield holds out each exact motion/load source environment once. UCI assigns
sorted exact context environments round-robin to four partitions. Every source row receives
exactly one out-of-fold prediction.

For each candidate and outer fold, compute source-OOF macro F1, worst exact-environment macro F1,
multiclass Brier and matched probability-response ratio. Candidate configurations within 0.01
absolute macro F1 of that outer fold's best source-OOF value are eligible. Select the eligible
candidate with the lowest probability-response ratio, then lower Brier, then lexicographic
configuration ID.

The final common configuration is the mode of the 13 outer-fold selections. A frequency tie is
resolved by the lower mean rank of source-OOF macro F1 across outer folds, then lower mean rank of
probability-response ratio, then lexicographic configuration ID. This common configuration, not a
per-target selection, is fitted on every complete outer-source partition.

## Final development evaluation

Fit the selected common configuration under seeds 11, 23, 37, 53 and 71 on all three Cranfield and
ten UCI outer folds. Persist target predictions, probabilities, representations, risk-envelope
diagnostic scores, source response ratios, training traces, model hashes, selection records and
all candidate OOF summaries.

The v0.2 mechanism gate requires lower mean source representation-response ratio and lower source
probability-response ratio than hash-locked EXP-320 ERM on both datasets. The efficacy gate
requires a positive worst-fold macro-F1 effect on at least one dataset without a mean-fold
macro-F1 regression below -0.02 on the other. Both gates must pass before pirl_ratio can enter the
strong-baseline suite.

This is still development evidence. Physical-block uncertainty and corrected comparisons are
deferred until the method configuration is frozen for the complete baseline and D2 protocol.
