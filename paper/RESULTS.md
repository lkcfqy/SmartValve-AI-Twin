# Results scaffold with evidence links

> **Historical scope notice.** This file preserves the detailed Cranfield-only results. The current
> headline results and final gate are in `MULTIRIG_RESULTS.md` and
> `research/D2_FINAL_DECISION.md`.

Every numerical statement below is tied to a generated table and a locked JSON field. Table and
figure captions are in `generated/FIGURE_CAPTIONS.md`; machine paths are in
`generated/claim_to_field_map.*`.

## RQ1 — Target access changes performance, but not as a simple gain

The raw target-free ExtraTrees protocol P0 obtains macro F1 0.8548 with a paired physical-block 95%
percentile interval [0.8397, 0.8710]. Source-linear extrapolation P1 falls to 0.7523
[0.7321, 0.7733], whereas matched-target calibration P2 reaches 0.8699 [0.8505, 0.8857]. All three
have worst-fold macro F1 0.1667 with a degenerate interval at 0.1667. These values are in Table 3 and
Figure 1.

The paired analysis changes the interpretation of the averages. P1-P0 macro F1 is -0.1025
[-0.1116, -0.0901], resolving source-linear extrapolation as harmful in the frozen protocol. P2-P0
macro F1 is +0.0151 [-0.0069, +0.0373], so the apparent average gain is not resolved away from zero.
P2 also increases the multiclass Brier score by +0.0375 [+0.0281, +0.0475], where larger is worse.
The P2-P0 control-ratio difference, -0.0202 [-0.0528, +0.0101], is likewise unresolved. Table 4 is
the canonical paired-difference table.

Evidence fields:

- `EXP-011.results.<P0|P1|P2>.<metric>`
- `EXP-011.paired_comparisons.P1_minus_P0.macro_f1`
- `EXP-011.paired_comparisons.P2_minus_P0.<macro_f1|multiclass_brier|control_ratio>`

Permitted conclusion: source-linear healthy extrapolation is reliably harmful here; matched-target
calibration has no resolved ExtraTrees macro-F1 advantage and has a worse Brier score. P2 must not be
described as target-free DG.

## RQ2 — The catastrophic ExtraTrees fold is stable but estimator-dependent

For every seed, P0 and P2 classify all 30 `trap/-40` trials as normal, yielding accuracy 1/3 and
macro F1 1/6. P1 also reaches accuracy 1/3 and macro F1 1/6 while predicting a different constant
class. Across 2,000 physical-block replicates, the probability that worst-fold accuracy is at or
below balanced chance is 1.0 for P0, P1, and P2. Thus the frozen ExtraTrees failure is not a seed or
repetition-resampling accident.

The fixed estimator family blocks the broader claim. Under P0, logistic regression and RBF-SVM each
have worst-fold macro F1 0.5556, histogram gradient boosting 0.4573, and shrinkage LDA 0.4779. Only
ExtraTrees meets the all-seed chance-level criterion in `trap/-40`; no fold is corroborated by three
families. Figure 2 and Table 6 show this heterogeneity.

Evidence fields:

- `EXP-011.results.<P0|P1|P2>.chance_failure_probability`
- `EXP-020.fault_classification.results.P0.<estimator>.summary`
- `EXP-020.fault_classification.model_independence`

Permitted conclusion: the ExtraTrees collapse is reproducible for that estimator but is not
model-independent. “All classifiers fail at low load” is contradicted by the experiment.

## RQ3 — Both representations retain load information

The repetition-disjoint load probe obtains P0 macro F1 1.0000 ± 0.0000 overall and for each motion.
The matched-reference P2 representation remains substantially load-decodable at 0.9034 ± 0.0050,
with 0.9075 ± 0.0063 on trapezoidal motion and 0.9000 ± 0.0077 on sinusoidal motion. The held-out
repetition was never read as the P2 reference. Figure 4 and Table 7 report these results.

Evidence field: `EXP-020.environment_probe.results.<P0|P2>.summary`.

Permitted conclusion: raw features retain perfect load separability for this frozen probe, and P2
does not remove all load information. Decodability alone does not show that a particular fault
classifier relies on load and cannot support a causal attribution.

## RQ4 — Source-only conformal singleton selection misses the known failure

With no rejection, mean coverage is 1.0000 and selective accuracy 0.8511, leaving 26.8 accepted
errors per seed, including all 20 `trap/-40` errors. Source-LOO conformal selection reduces coverage
to 0.7967 and raises selective accuracy to 0.8605, but still accepts exactly all 20 `trap/-40`
errors per seed. It therefore does not recognize the observed unsupported-load failure.

The metadata support gate rejects both -40 kg folds. It reaches coverage 0.6667 and selective
accuracy 0.9433, with 6.8 accepted errors and zero accepted `trap/-40` errors; it also rejects all
correct `sin/-40` predictions. The exploratory hybrid reaches 0.4633 coverage and 1.0000 selective
accuracy with zero accepted errors on these recorded trials. Figure 3 and Table 5 make the coverage
cost visible.

Evidence field: `EXP-012.results.<policy>.summary`.

Permitted conclusion: source-only conformal selection failed to reject the known shifted-load
errors. The hybrid's zero accepted errors are a finite, post-hoc observation without a target-risk
guarantee or prospective validation.

## Result hierarchy for the manuscript

Primary confirmatory evidence:

- exact reproduction of the checked-in P2 baseline;
- P0/P1/P2 access audit under frozen ExtraTrees;
- 2,000-replicate paired physical-block intervals and worst-fold stopping rule.

Pre-specified falsification evidence:

- fixed classical estimator family;
- repetition-disjoint load probe;
- failed model-independence criterion.

Exploratory evidence:

- all selective-prediction policies in EXP-012;
- especially the metadata and hybrid policies designed after observing EXP-010.

## Null and negative results that must remain visible

- P2-P0 macro F1 and control-ratio differences are unresolved.
- P2 has worse ExtraTrees Brier score despite a higher point macro F1.
- P1 is worse than P0 rather than an improved source-only normalization.
- The ExtraTrees worst fold is not reproduced at chance level by four other estimator families.
- Conformal singleton selection does not reject the observed failure.
- The metadata gate sacrifices correct low-load sinusoidal predictions.
