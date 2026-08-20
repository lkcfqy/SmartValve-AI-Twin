# Multi-rig results

## Development evidence did not establish closed-set leadership

In the frozen D0/D1 nine-method comparison, PIRL was not the best closed-set method. On Cranfield,
CORAL achieved mean-fold macro F1 0.840899 versus PIRL 0.840046. On UCI Hydraulic, MatchDG achieved
0.732869 versus PIRL 0.724352. These comparisons block a state-of-the-art or consistent-ranking
claim before the prospective D2 result is considered.

The paired D0/D1 physical bootstrap produced one practically and inferentially positive endpoint
before family correction: UCI selective risk. Cranfield minimum-environment macro F1 and selective
risk were null; the UCI minimum-environment effect was positive but below the frozen 0.01 practical
threshold.

The component ablation was exact rather than approximate: all 65 full-PIRL final model states were
byte-identical to ratio-only, and all 65 margin-only states were byte-identical to ERM. Every
corresponding prediction and metric was therefore equal. The observed PIRL behavior is attributable
to the response-ratio term; the experiment supplies no evidence that the margin contributes.

## Sealed Paderborn closed-set evaluation

The canonical run completed 1,080 final models over nine methods, five seeds, and 24 folds. Its
104,355 primary target predictions and 259,200 compound predictions passed probability, topology,
and provenance validation after the disclosed row-coordinate reconciliation.

The generated full table is `generated/table_08_paderborn_closed_set.md`.

| Method | Pooled macro F1 | Minimum-setting macro F1 | Minimum identity-setting F1 | Brier | ECE |
|---|---:|---:|---:|---:|---:|
| PIRL | 0.3829 ± 0.0180 | **0.3185 ± 0.0362** | 0.0687 ± 0.0729 | 0.9442 ± 0.0288 | 0.4158 ± 0.0229 |
| ERM | 0.3695 ± 0.0160 | 0.2976 ± 0.0352 | 0.0320 ± 0.0480 | 0.9504 ± 0.0310 | 0.4385 ± 0.0248 |
| MatchDG | **0.3952 ± 0.0171** | 0.2966 ± 0.0367 | 0.0668 ± 0.0718 | 0.9278 ± 0.0165 | 0.4074 ± 0.0192 |
| CCDG | 0.3737 ± 0.0106 | 0.3082 ± 0.0224 | 0.0313 ± 0.0391 | 0.9501 ± 0.0251 | 0.4346 ± 0.0206 |

PIRL has the highest descriptive minimum-setting score, but MatchDG has the highest pooled score.
PIRL's seed-wise minimum-setting difference from ERM ranges from -0.007323 to +0.057573, already
indicating that the mean difference is not uniformly positive.

## Paderborn selective evaluation

At nominal 50% source coverage, unweighted fold summaries were:

| Method | Target coverage | Selective risk | Effective accuracy | Minimum environment coverage | Zero-coverage groups |
|---|---:|---:|---:|---:|---:|
| ERM | 0.7082 | 0.6147 | 0.2954 | 0.1646 | 0 |
| PIRL | 0.7176 | 0.6117 | 0.2782 | 0.0000 | 3 |

The roughly 0.003 unweighted mean-risk difference descriptively favors PIRL, but PIRL also has
three zero-coverage groups and lower effective accuracy. More importantly, this fold average is not
the confirmatory estimand. Bearing-level pooled inference gives ERM-minus-PIRL selective risk
-0.031777, so its point estimate favors ERM. The discrepancy is a weighting effect and must be
reported, not resolved by choosing the more favorable summary.

The generated full table is `generated/table_09_paderborn_selective.md`.

## Physical-unit inference

Paderborn used 2,000 paired, truth-stratified bearing-identity bootstrap replicates over 29
identities and the exact 2,319 observed primary rows.

- Closed-set endpoint, PIRL minus ERM minimum-setting macro F1: 0.020921, 95% interval
  [-0.045959, 0.081241], raw two-sided p=0.692654.
- Selective endpoint, ERM minus PIRL risk at the source-selected 50% policy: -0.031777, 95% interval
  [-0.070919, 0.007151], raw two-sided p=0.097951.

Neither Paderborn endpoint is confirmatory-positive. The selective point estimate is adverse, but
its interval includes zero; the frozen material-harm rule therefore does not classify it as
resolved harm.

## Frozen six-test family

The generated table is `generated/table_10_confirmatory_family.md`, and Figure 5 is
`generated/figure_05_confirmatory_forest.svg`.

| Dataset | Endpoint | Effect | 95% interval | Holm p | Positive |
|---|---|---:|---:|---:|---|
| Cranfield | minimum-environment macro F1 | +0.007785 | [-0.016053, 0.031119] | 1.000000 | no |
| Cranfield | selective risk | -0.000174 | [-0.007159, 0.006241] | 1.000000 | no |
| UCI Hydraulic | minimum-environment macro F1 | +0.000860 | [0.000000, 0.002473] | 0.855572 | no |
| UCI Hydraulic | selective risk | +0.044069 | [0.038991, 0.049302] | 0.005997 | **yes** |
| Paderborn | minimum-environment macro F1 | +0.020921 | [-0.045959, 0.081241] | 1.000000 | no |
| Paderborn | selective risk | -0.031777 | [-0.070919, 0.007151] | 0.489755 | no |

Only one of six tests is confirmatory-positive. The only dataset with a confirmed improvement is
UCI Hydraulic. No endpoint meets the frozen material-harm rule, but absence of resolved harm is not
evidence of benefit.

## Decision against the internal top-tier algorithm gate

The predeclared rule required at least one confirmatory-positive endpoint on at least two datasets,
with no materially harmful endpoint on the third. The observed positive-dataset count is one, so
`internal_multi_dataset_evidence_gate_passed=false`.

Accordingly:

- the study does not support a PIRL-superiority paper;
- the prospective D2 result cannot be relabeled exploratory or omitted;
- the UCI result may be reported only inside the complete six-test family; and
- the defensible paper direction is a prospective non-replication/evaluation audit.

## Structural failures and why they do not change the numerical result

The first unmodified base validator, selective validator, bootstrap, and confirmatory assembler all
failed and remain recorded. Their failures concerned compact-versus-original row coordinates, a
stale 2,320-row assertion after the documented exclusion, and a version acceptance check. The final
wrappers changed no prediction, probability, model state, bootstrap draw, endpoint, raw p-value, or
Holm computation. Base and selective probability/topology checks subsequently passed, including
zero maximum difference from frozen reference projections. This history strengthens traceability;
it does not turn the null D2 endpoints into positive evidence.

## Bottom line

The experiment is scientifically informative and unusually well audited, but its algorithmic
headline failed. The evidence is appropriate for a mixed-result reliability or reproducibility
manuscript after full prose, related-work, and external review; it is not currently a top-tier
algorithm submission.
