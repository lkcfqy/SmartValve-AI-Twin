# Figure captions

1. **Reference-access uncertainty.** Macro-F1 and multiclass Brier point estimates with 95% paired
   physical-block bootstrap percentile intervals (2,000 replicates). P2 uses a healthy trajectory at
   the held-out load and is target-condition calibration, not pure domain generalization.
2. **Estimator-by-environment falsification.** Five-seed P0 macro-F1 means for the fixed classical
   estimator suite. The outlined `trap/-40` ExtraTrees cell is at the frozen balanced-chance failure
   level; the other four families do not reproduce that catastrophic value.
3. **Selective coverage–risk trade-off.** Mean coverage against accepted-set error for four frozen
   EXP-012 policies. The hybrid point is post-EXP-010 exploratory. Source-to-source conformal
   calibration supplies no shifted-target guarantee.
4. **Environment-prediction probe.** Load macro-F1 under repetition-disjoint evaluation. P2 never
   reads the held-out repetition as its healthy reference. Decodability diagnoses retained nuisance
   information but not causal use by the fault classifier.
