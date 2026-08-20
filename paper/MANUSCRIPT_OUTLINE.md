# Protocol-centric bearing manuscript outline

## Working position

The primary paper is now a bearing-diagnosis evaluation paper, not a paper claiming a superior
PIRL algorithm. Its central question is whether model performance and method ranking survive the
deployment access actually claimed: a new recording, a new operating setting, a new physical
bearing, or a bearing and setting that are both unseen.

Working title:

> When the Split Changes the Winner: A Factorial Audit of Bearing Identity, Operating Condition,
> and Sensor Access

Alternative title:

> Double-Unseen Bearing Diagnosis: Physical-Unit Evidence from Four Access Protocols and Nine
> Domain-Generalization Methods

The Paderborn study is retrospective development evidence. The sealed HUST study is the
protocol-prospective, signal-unopened external test. No HUST result is inserted into the narrative
until the complete run and independent no-refit recomputation pass.

## 1. Introduction

1. Reported bearing-diagnosis accuracy is inseparable from the physical access encoded by the
   train/test split. Holding out windows, recordings, operating settings, or physical bearings
   answers different deployment questions.
2. Existing work establishes recording leakage and bearing-identity leakage. Recent studies also
   compare condition holdout, bearing-code holdout, input representations, and vibration/current
   fusion. The unresolved question is their interaction: what happens when identity and operating
   setting are simultaneously unseen and neither XOR cross-arm is available for fitting or model
   selection?
3. Model ranking matters as much as absolute score. A nearly saturated random split can select a
   different method from a crossed deployment split, invalidating architecture claims made under
   convenient access.
4. State the design: the same records, features, frozen configurations, nine methods, and five
   seeds are evaluated under four protocols; uncertainty is computed over physical bearings; sensor
   families are audited on Paderborn; the factorial conclusions are tested once on sealed HUST.
5. Preview only validated findings. Report Paderborn as development evidence and HUST as the
   external test, including a failed replication if that is the observed outcome.

The introduction must not claim the first leakage-safe, bearing-wise, HUST, or multi-sensor study.

## 2. Related work and exact novelty boundary

### 2.1 Leakage-safe bearing evaluation

Position Hendriks, Abburi, Wheat, Knap, and Vieira. Credit independent-bearing evaluation,
recording-level separation, controlled leakage exposure, and representation-sensitive conclusions
as prior art.

### 2.2 Operating-condition generalization and multi-sensor diagnosis

Position target-free DG and the nine mechanism families. Treat Kaya and Jobani as the nearest
Paderborn sensor study: vibration, phase current, fusion, condition holdout, and separate
bearing-code holdout are prior art. Their explicitly deferred combined bearing-code × condition
test motivates, but does not prove priority for, the crossed design.

### 2.3 Benchmark rankings and model selection

Connect DomainBed-style selection sensitivity to industrial diagnosis. Explain why a method ranking
under shared-identity random access cannot be presumed to identify the best method for a
double-unseen target.

### 2.4 Contribution boundary

Claim only the evaluated combination:

1. four access-matched protocols on the same cohort and configurations;
2. simultaneous identity × setting holdout with both XOR arms quarantined;
3. nine-method score and rank stability, not merely one proposed model versus ERM;
4. physical-bearing paired uncertainty rather than windows or seeds as replicates;
5. sensor-family attribution inside the same factorial protocol; and
6. one sealed external factorial replication on HUST.

Use “not found in the documented search” rather than “first” or “unprecedented.”

## 3. Deployment access as an experimental factor

### 3.1 Four estimands

Define the deployment questions before their implementation:

- `measurement_random`: new recording/window access while identities and settings may be shared;
- `setting_holdout`: unseen operating setting while identities may be shared;
- `identity_holdout`: unseen physical identity while settings may be shared;
- `crossed_holdout`: unseen identity and unseen setting simultaneously.

State that these are different estimands, not a ladder in which one number is universally “more
correct.” The crossed protocol targets the strictest deployment claim made in this paper.

### 3.2 Crossed quarantine

For held identity `b` and setting `s`, define:

```text
source      = identity != b AND setting != s
target      = identity == b AND setting == s
quarantine  = (identity == b) XOR (setting == s)
```

Explain that the two XOR arms would reveal either the target identity or the target setting. They
are unavailable to preprocessing, fitting, early stopping, calibration, and selection.

### 3.3 Information-access ledger

For every protocol, list whether training can access target recordings, target identity at another
setting, target setting on another identity, target labels, target-normal trajectories, and target
covariates. The headline experiments are strict P0/source-only tests.

## 4. Data, physical units, and frozen representations

### 4.1 Paderborn development cohort

Report official provenance, retained/excluded records, physical bearing IDs, four operating
settings, class construction, synchronized vibration/current channels, non-overlapping windows,
and the 24-feature contract. Distinguish physical bearings, measurements, and windows in every
count.

### 4.2 HUST external cohort

Report 15 physical bearings, three diagnostic classes, five specifications per class, three loads,
45 recordings, ten non-overlapping one-second windows per recording, and 450 optimization rows.
Disclose that `matched_specification_group` combines three distinct class-specific bearings and
therefore confounds specimen identity with specification.

### 4.3 Prospective chronology

Give a dated chain from metadata-only inventory to factorial seal, acquisition hashes, structural
feature extraction, execution amendment, explicit transitive dependency lock, and the one-shot
model run. Retain every failed acquisition/seal/validator attempt and show that no failed attempt
fit a HUST model or emitted predictions.

## 5. Models and controlled comparison

### 5.1 Nine frozen methods

Evaluate ERM, CORAL, V-REx, GroupDRO, DANN, LISA, MatchDG, CCDG, and PIRL-ratio with one shared
backbone, feature contract, source-only selector, stopping rule, and five seeds. Describe each as a
controlled implementation of a mechanism family, not an exact reproduction of every original
paper.

### 5.2 Sensor families

On Paderborn, repeat the complete four-protocol suite for vibration-only, motor-current-only, and
fusion features. Treat the sensor comparison as attribution inside the protocol audit, not as an
independent novelty claim.

### 5.3 Classical falsification suite

Use the fixed classical models as a capacity-independent check that the protocol gap is not unique
to compact neural networks. Keep the classical and neural claims separate when cohorts, selection,
or seeds differ.

## 6. Endpoints and inference

### 6.1 Primary protocol effect

For every method, estimate pooled record-level macro F1 under `measurement_random` minus
`crossed_holdout`. Pair protocols on the same physical identities. Report all point estimates and
95% class-stratified physical-bearing bootstrap intervals.

### 6.2 Rank stability

Report Kendall tau between protocol-specific nine-method ranks, every method's rank shift, the
maximum absolute shift, and the score range under each protocol. Discuss ceiling compression
whenever random scores occupy a narrow high-performance range.

### 6.3 Secondary outcomes

Report balanced accuracy, accuracy, minimum class recall, cell-level summaries, confusion matrices,
method-minus-ERM effects, fit resource diagnostics, and window-to-record disagreement. Do not treat
cells, windows, folds, or seeds as independent physical replicates.

### 6.4 Predeclared HUST interpretation

Protocol-gap replication requires at least seven of nine positive point estimates and a median gap
of at least 0.15 macro F1. Rank-instability replication requires Kendall tau below 0.50 or at least
one method moving by three ranks. These are descriptive advancement rules, not population-level
hypothesis tests.

## 7. Results

### 7.1 Paderborn classical protocol contrast

Show the large ExtraTrees random/crossed gap and the four-protocol table. Use this only as the
capacity-independent entry point.

### 7.2 Paderborn neural score and rank reversal

Report all nine methods under all four protocols, physical-bearing intervals, random/crossed
Kendall tau, and the opposite leader/laggard shifts. Put score compression and rank movement in one
figure so the reader cannot interpret rank reversal without its scale.

### 7.3 Sensor-family attribution

Report vibration, motor current, and fusion using identical method/protocol panels. Test paired
differences between sensor-specific protocol gaps and compare whether the protocol changes sensor
conclusions as well as model conclusions.

### 7.4 Sealed HUST external result

Report the complete 36-row method × protocol table, 27 protocol-effect intervals, 12 rank
concordances, gate outcome, and all negative results. State whether the Paderborn pattern replicates
according to the frozen thresholds; do not require the same winning method.

### 7.5 Robustness and audit checks

Summarize prediction counts, checkpoint/state hashes, independent no-refit recomputation, failed-run
chronology, and quality gates. Put exhaustive hashes in the artifact appendix rather than the main
text.

## 8. Discussion

1. **Deployment estimand:** a random or single-axis split can answer a materially easier question
   than simultaneous unseen identity and setting.
2. **Winner instability:** architecture selection under convenient access can be unreliable even
   when every implementation and training budget is held fixed.
3. **Sensor attribution:** sensor conclusions are conditional on the access protocol; fusion should
   not be called robust merely because it wins when identity or setting is shared.
4. **External replication:** interpret HUST by the frozen gate and its specification/identity
   confounding, not by whether it reproduces an exact Paderborn number.
5. **Benchmark implication:** papers should publish an access ledger, physical-unit counts, at least
   one identity-disjoint protocol, and rank stability when comparing several methods.
6. **Algorithmic restraint:** PIRL's failed multi-rig superiority gate is supporting evidence that
   evaluation design, not another loss function, is the defensible contribution.

## 9. Limitations

- Paderborn protocol and sensor analyses are retrospective development evidence.
- HUST is signal-unopened and protocol-prospective, but Vieira et al.'s bearing-wise HUST outcomes
  were known before the seal; it is not literature-outcome-blind.
- HUST has only five physical bearings per class and confounds specification group with three
  class-specific specimens.
- Both datasets are controlled public rigs, not prospective factory deployments.
- The shared 24-feature compact-network design enables controlled comparison but does not exhaust
  raw-signal CNNs, transformers, foundation models, or current-specific signal processing.
- Five seeds quantify optimization variability but are not physical replication.
- Percentile intervals are conditional on the observed bearing cohorts and are not universal
  performance guarantees.
- The crossed protocol discards two XOR arms and therefore trades training volume for a stricter
  access claim; score loss cannot be attributed to leakage alone without considering sample size.
- No causal representation, safety guarantee, or population-wide ordering of DG algorithms is
  identified.

## 10. Conclusion

Conclude with the validated protocol and replication results, not a model advertisement. State
which conclusions change when identity and setting are jointly unavailable, whether method ranking
instability replicates, and what minimum reporting contract follows for future bearing-diagnosis
benchmarks.

## Main figures and tables

1. Access-lattice diagram with source, target, and quarantined XOR arms.
2. Dataset × protocol × physical-unit table.
3. Paderborn four-protocol score/rank slopegraph for nine methods.
4. Paderborn physical-bearing forest plot of random-minus-crossed effects.
5. Sensor-family protocol-gap and rank-concordance comparison.
6. HUST prospective replication score/rank panel with frozen-gate annotation.
7. Cross-dataset replication summary and claim-status table.

## Appendices

- A. Dataset provenance, licenses, immutable hashes, and exclusions.
- B. Complete fold membership and XOR-quarantine topology.
- C. Frozen configurations, source-only selection, seeds, and resource use.
- D. All Paderborn classical/neural/sensor metrics and bootstrap draws.
- E. All HUST predictions, record aggregation, metrics, ranks, and draws.
- F. Independent validators and exact recomputation tolerances.
- G. Failed-run, amendment, and structural-reconciliation chronology.
- H. Earlier PIRL/access/selective-prediction negative results.
- I. Commands, environment, manifests, tests, and artifact checksums.
