# v0.3 contribution decision after D2 failure analysis

- Decision date: 2026-08-19 (Asia/Shanghai)
- Decision status: active development; not submission-ready
- Observed development data: D0 Cranfield, D1 UCI Hydraulic, D2 Paderborn
- Prospective candidate: D3 HUST Bearing v3; metadata only, not sealed or opened

## Evidence update after EXP-433--435

The protocol thesis now has strong **retrospective Paderborn evidence** across both classical and
neural model families:

- fixed classical ExtraTrees fell from `0.998389` pooled macro F1 under measurement-random access
  to `0.544720` under crossed access; the paired physical-bearing interval for the difference was
  `[0.332442, 0.596978]`;
- the nine frozen neural DG methods occupied `0.964534--0.987148` under measurement-random access
  but only `0.360074--0.403121` under crossed access;
- all nine neural random-minus-crossed bearing-bootstrap intervals excluded zero;
- neural pooled-rank agreement between random and crossed access was Kendall `tau=-0.555556`;
  CCDG moved from rank 1 to 9, while MatchDG moved from rank 9 to 1;
- setting-only selected PIRL-ratio as the apparent leader, whereas identity-only and crossed access
  selected MatchDG. Thus an operating-condition-only benchmark is not a substitute for a physical
  identity holdout;
- independent EXP-435 recomputation matched seed means exactly and reproduced metrics, ranks, and
  bootstrap summaries to approximately `1e-12`.

These findings materially strengthen the audit contribution. They do **not** make the project
submission-ready by themselves: all Paderborn protocol choices were made after D2 outcomes were
known, the random neural regime has ceiling compression, and the central result still lacks an
untouched cross-system replication.

## Decision

The project will not rename or lightly modify PIRL v0.2 and claim a new superior algorithm. The
frozen six-test family failed its multi-dataset efficacy gate, the margin was inactive, MatchDG led
the Paderborn pooled endpoint, and post-D2 target-informed diagnostics cannot be confirmatory.

The provisional generalized-eigenvalue idea is retained only as a **paired-scatter baseline**.
DICA, SCA, conditional invariant representation, MDA, Fisher/LDA, and ISR already cover the main
invariant/discriminant subspace principle. SmartValve's audited pair construction is useful
experimental structure, not sufficient algorithmic novelty.

The primary v0.3 route is therefore a reliability and evaluation paper with the working thesis:

> Industrial DG conclusions and method rankings can change sharply when physical identity and
> operating condition are both unseen, cross-arms are quarantined, selection remains source-only,
> and uncertainty is evaluated at the physical unit rather than at the window level.

## Candidate contribution stack

1. **Crossed physical holdout.** Hold an asset/identity axis and an operating-condition axis
   simultaneously. Use only the complement intersection for training, the held-axis intersection
   for testing, and quarantine the two XOR cross-arms.
2. **Protocol contrast.** Compare random/window, recording-safe, single-axis, and crossed-axis
   protocols without changing model capacity or preprocessing.
3. **Selection audit.** Quantify whether source-only validation predicts target ranking and
   physical-group tail performance.
4. **Reliability audit.** Report macro F1, worst physical group, calibration, selective risk,
   group coverage, effective accuracy, and zero-coverage groups.
5. **Prospective replication.** Freeze all changes using D0--D2, then execute one sealed HUST D3
   evaluation and report confirmation or rejection without endpoint substitution.

## Claims currently prohibited

- PIRL is state of the art or generally superior.
- The paired-scatter baseline is a novel generalized-eigenvalue DG method.
- Paderborn remains prospective for any post-EXP-417 choice.
- HUST D3 is sealed, untouched in every sense, or authorized for signal access; only public
  metadata and filenames have been inventoried.
- The crossed protocol is the first of its kind. The documented search supports a narrower
  closest-work distinction, not proof of absence.
- The project is currently at top-conference/top-journal submission quality.

## Go/no-go gate before D3 signal access

All of the following must be complete and hash-frozen:

- manuscript-level hypothesis and estimands;
- exact primary/open-set HUST cohorts and filename manifest;
- windowing or full-record feature contract and no-overlap audit;
- model list, fixed budgets, source-only selection, seeds, and deterministic fallbacks;
- random/recording/single-axis/crossed-axis comparison matrix;
- primary endpoint, minimum practical effect, physical resampling unit, and multiplicity family;
- selective thresholds and zero-coverage handling;
- code tests, expected topology manifests, and execution seal.

Until that gate passes, D3 MAT downloads remain unauthorized.

## Current manuscript thesis after the update

The defensible paper is no longer an algorithm-superiority paper. Its central empirical statement
is now:

> Shared physical identity can make industrial fault diagnosis appear nearly solved, while
> simultaneous unseen identity and operating condition exposes severe tail failure and can reverse
> the ranking of otherwise fixed DG methods.

The phrase "can reverse" is supported on retrospective Paderborn only. The sealed D3 primary test
must ask whether the protocol gap and predeclared ranking-instability statistic replicate; it must
not require the same winning method or the same rank order.
