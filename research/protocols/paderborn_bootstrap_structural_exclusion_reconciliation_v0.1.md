# Paderborn bootstrap structural-exclusion reconciliation — v0.1

- Written: 2026-08-19 after failed EXP-421 and before any D2 bootstrap statistic existed.
- Status: narrow post-outcome implementation correction.
- Frozen statistical design: unchanged.

## Trigger

The base and selective Paderborn artifacts passed independent validation after the separately
disclosed compound-row coordinate reconciliation. The first invocation of the sealed D2 bootstrap,
EXP-421, then stopped before drawing a bootstrap sample with
`Paderborn predictions do not contain the exact pure measurement set`.

The runner still required the original 29 bearings × 4 settings × 20 measurements = 2,320 pure
rows. The already frozen D2 execution amendment, feature artifacts, split manifests, model-fold
manifests, expected manifests, and independently validated model outputs all use 2,319 pure rows
after excluding the exact unreadable MAT member `N15_M01_F10_KA08_2.mat`. This is implementation
drift in the bootstrap's physical-input assertion, not a newly observed statistical choice.

Descriptive D2 closed-set and selective summaries had been read before this amendment. No D2
bootstrap point estimate, replicate, interval, tail probability, or multiplicity result existed.
The correction below depends only on the frozen exclusion and validated physical keys, not on any
performance value.

## Authorized correction

The corrected bootstrap must retain every original design choice:

- exactly 2,000 replicates and root seed 20260818;
- 29 bearing identities, stratified within the three pure classes;
- identical identity draws for PIRL and ERM and all five model seeds;
- minimum held-setting macro F1 and 50%-coverage risk as the two endpoints;
- the same endpoint directions, 0.01 practical thresholds, percentile intervals, and add-one
  two-sided bootstrap-tail diagnostic; and
- complete retained measurements carried whenever an identity is sampled.

Only the physical key contract changes from the impossible full Cartesian set to that set minus
the one frozen exclusion. `KA08` therefore carries 79 retained measurements; each other bearing
carries 80. No missing value is imputed, no observed row is dropped, and no row is resampled as an
independent unit. The primary feature/prediction coordinate remains the validated compact global
range 0 through 2318.

The corrected runner must verify the exact base-prediction and selective-decision hashes, their
independent validation artifacts, the original sealed bootstrap source, this protocol, the D2
execution amendment, and the retained failed EXP-421 command/metadata/stderr before computing any
statistic. It must preserve EXP-421 and emit a new bootstrap version and an explicit reconciliation
record.

## Downstream multiplicity

The sealed six-test confirmatory assembler also retained the obsolete 2,320-row assertion. It must
first fail transparently on the corrected 2,319-row bootstrap package. A later reconciliation may
change only that physical-count/version acceptance check while retaining the same exact six rows,
Holm algorithm, practical thresholds, and internal multi-dataset claim gate.

## Prohibited actions

- no model, prediction, decision, beta, threshold, endpoint, seed, replicate, or resampling-unit
  change;
- no imputation of the unreadable measurement;
- no deletion or replacement of EXP-421;
- no selection based on the resulting bootstrap interval or p-value; and
- no claim that this amendment was prospective.

