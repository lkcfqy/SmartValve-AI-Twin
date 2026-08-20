# Title, research questions, and abstract template

> **Submission hold:** the complete neural sensor family, HUST primary, and equal-volume results
> are independently validated. The raw/FFT/STFT placeholder below must be replaced only after
> the from-scratch EXP-456R1 recovery run and its no-refit validator pass; the interrupted EXP-456
> is excluded. This file is not yet submission text.

## Preferred reliability-journal title

> Physical Access Changes Estimated Bearing-Diagnosis Reliability: A Crossed Identity--Condition
> Audit with Sealed Replication

The earlier method-selection title is retained only as an alternative because HUST replicated the
score gap but not Paderborn's directional winner reversal:

> When the Split Changes the Winner: A Factorial Audit of Bearing Identity, Operating Condition,
> and Sensor Access

Short-title option:

> Double-Unseen Bearing Diagnosis

## Research questions

- **RQ1 — Access sensitivity:** How much does pooled record-level macro F1 change when the same
  records and frozen configurations move from measurement-random access to simultaneous unseen
  physical identity and unseen operating setting with both XOR arms quarantined?
- **RQ2 — Ranking validity:** Do nine controlled domain-generalization methods retain their ranking
  across measurement-random, setting-holdout, identity-holdout, and crossed-holdout protocols?
- **RQ3 — Sensor attribution:** Do vibration, motor current, and their fusion exhibit different
  protocol gaps and method-rank distortions under identical Paderborn access contracts?
- **RQ4 — External replication:** Do the Paderborn protocol-gap and rank-instability patterns meet
  predeclared thresholds in a signal-unopened, one-shot HUST factorial evaluation?
- **RQ5 — Alternative explanations:** Does the access effect survive equal source-record volume on
  HUST, deletion of any one observed HUST bearing or matched group, and raw/FFT/STFT vibration
  architectures on Paderborn?
- **RQ6 — Evidence integrity:** Do every count, hash, aggregation, metric, rank, and physical-unit
  bootstrap result reproduce without refitting models?

## Defensible contributions

1. A four-protocol, access-matched audit that changes only the train/test access contract while
   preserving the cohort, features, configurations, methods, and seeds.
2. A simultaneous identity × setting target in which observations sharing exactly one target
   factor form quarantined XOR arms unavailable to preprocessing, fitting, early stopping,
   calibration, and model selection.
3. A nine-method ranking audit with paired physical-bearing uncertainty, rather than a single new
   model compared only with ERM or inference over windows/seeds.
4. A Paderborn sensor-family attribution inside the same factorial design, explicitly building on
   prior vibration/current/fusion and separate holdout studies.
5. A sealed HUST replication whose metadata, feature contract, topology, selected configurations,
   source code, runtime dependencies, expected output keys, and interpretation gates were fixed
   before the first model fit.
6. A complete post-hoc no-refit HUST physical-unit influence audit that reports every bearing and
   matched-group deletion without presenting deletion ranges as confidence intervals.
7. Prediction-level artifacts, retained failures and amendments, content hashes, and independent
   no-refit recomputation suitable for external audit.

## Abstract template — do not submit with placeholders

Bearing-fault diagnosis studies often compare algorithms under splits that expose different
physical identities or operating conditions, so an apparent method improvement may instead reflect
a more permissive deployment estimand. We evaluate the same records, representations, frozen model
configurations, nine domain-generalization methods, and five seeds under four access protocols:
measurement-random, operating-setting holdout, physical-identity holdout, and simultaneous
identity × setting holdout. In the crossed protocol, both exclusive-OR arms that reveal either the
target identity or target setting are quarantined from all fitting and selection. Results are
aggregated at recording level and uncertainty is estimated by paired, class-stratified resampling
of physical bearings.

On Paderborn fusion features, measurement-random macro F1 ranged from 0.9645 to 0.9871, whereas
crossed-holdout macro F1 ranged from 0.3601 to 0.4031. All nine random-minus-crossed physical-bearing
bootstrap intervals excluded zero. Method ranks reversed (Kendall tau = -0.5556): CCDG moved from
first to ninth, while MatchDG moved from ninth to first. A classical ExtraTrees control showed a
corresponding 0.4537 gap. Vibration-only models independently retained positive gaps of
0.2934--0.4299 with all interval lower bounds above zero; their random/crossed rank agreement was
-0.3889. Motor-current gaps were 0.2981--0.5187, again with all nine interval lower bounds above
zero, and rank agreement was -0.3333. In the paired three-sensor analysis, fusion had a larger
protocol gap than vibration for all nine methods, while vibration had higher crossed performance
for all nine. **Raw-architecture result:** {{insert only after EXP-456R1/457 validation}}.

We then executed a signal-unopened, prospectively sealed HUST replication on 15 physical bearings,
45 recordings, three loads, and 1,260 frozen fits. Random and load-holdout macro F1 was 1.0000 for
every method, while crossed performance was 0.7468--0.7740. All nine random-minus-crossed intervals
excluded zero and the median effect was 0.2260, passing the predeclared 7/9 and 0.15 protocol-gap
rule. An outcome-blind control with 24 source recordings in both arms also produced nine positive
shared-access-minus-crossed effects, median 0.2260, with all intervals excluding zero; record count
alone was therefore insufficient to explain the gap. HUST's rank rule mechanically passed through
a four-position shift, but random performance was completely tied and Kendall tau undefined, so it
did not replicate Paderborn's directional winner reversal. In a separate post-hoc no-refit audit,
all 18 method-by-comparison effects remained positive after deleting any one bearing and after
deleting any one class-balanced matched-specification group; these ranges are sensitivity
diagnostics rather than confidence intervals. These findings support an access-explicit
evaluation and replication protocol, not a claim that identity leakage, bearing-wise splitting,
multi-sensor diagnosis, or any individual DG mechanism is new.

## Non-claims

- This is not the first leakage-safe, bearing-wise, Paderborn, HUST, or multi-sensor bearing study.
- A condition-holdout score is not evidence of unseen-bearing generalization, and a separate
  bearing holdout is not evidence of their simultaneous generalization.
- A random-minus-crossed gap combines access restriction and reduced source sample size; it cannot
  be attributed to identity leakage alone.
- Rank reversal on two public datasets does not establish a population-wide ordering or failure of
  any original DG algorithm.
- The shared compact feature-based implementations are controlled comparators, not exhaustive
  reproductions of raw-signal architectures.
- Model seeds, windows, measurements, and folds are not physical replicates.
- No causal representation, shifted-target guarantee, safety certification, or factory-deployment
  validity is claimed.
