# Methods for the protocol-centric bearing study

> **Manuscript status.** This is the integrated methods source for the v0.3 bearing-evaluation
> paper. Paderborn is retrospective development evidence. HUST is the sealed external replication.
> Exact run manifests and protocol seals remain authoritative when this text is ambiguous.

## Study question and estimands

We test whether fault-diagnosis performance and the ordering of learning methods remain stable when
the train/test split grants different forms of access to the physical system. Four protocols answer
four distinct deployment questions:

1. `measurement_random` / `recording_random`: a new measurement is withheld, while its physical
   identity and operating setting may be represented in training;
2. `setting_holdout` / `load_holdout`: the target operating setting is unseen, while physical
   identities may be shared;
3. `identity_holdout` / `matched_specification_holdout`: physical identities are withheld, while
   operating settings may be shared; and
4. `crossed_holdout`: both the target identity and target setting are simultaneously unseen.

These protocols are not interpreted as repeated estimates of one population quantity. Each defines
a different information-access estimand. For a held identity group \(b\) and setting \(s\), the
crossed protocol is

```text
source      = identity != b AND setting != s
target      = identity == b AND setting == s
quarantine  = (identity == b) XOR (setting == s).
```

The quarantined XOR arms reveal either the target identity at another setting or the target setting
on another identity. They are unavailable to standardization, fitting, early stopping, calibration,
thresholding, and model selection. No target labels are used before scoring.

## Paderborn development study

### Cohort, physical units, and signals

The official Paderborn KAt benchmark provides synchronously measured vibration and motor-current
signals under four operating conditions [@Lessmeier2016] and is licensed for non-commercial
academic use under CC BY-NC 4.0. The official archive inventory contained 2,560 canonical MAT
measurements. The primary cohort was
fixed to 29 single-condition physical bearings across four operating settings, with 20 measurements
per bearing-setting cell. The expected 2,320 records were reduced to 2,319 after the pinned parser
found one structurally unreadable file (`N15_M01_F10_KA08_2.mat`). The exclusion was recorded before
outcome modelling; the signal was not imputed and no neighbouring measurement replaced it. The
three diagnostic labels are healthy, inner-race damage, and outer-race damage. Compound-damage
records are outside the factorial primary analysis.

Each measurement provides synchronous four-second, 64-kHz trajectories from one vibration channel
and two motor-current phases. We treat the complete measurement as the prediction row. No window or
time sample is promoted to an independent observation. The physical bearing is the inferential and
bootstrap unit.

### Fixed feature families

Twenty-four deterministic whole-trajectory statistics are computed independently for each channel:
mean, standard deviation, root-mean-square value, minimum, maximum, peak-to-peak range, the 5th,
25th, 50th, 75th, and 95th percentiles, interquartile range, mean absolute value, skewness, excess
kurtosis, mean absolute and RMS first difference, linear slope, spectral centroid, spectral
bandwidth, spectral entropy, and relative low-, mid-, and high-band spectral power. The resulting
feature families are:

- vibration: 24 features;
- motor current: 48 features, with phase-U followed by phase-V features; and
- fusion: all 72 features in the frozen channel order.

Speed, torque, force, temperature, target outcomes, and metadata identifiers are excluded from the
classifier inputs. Feature order is fixed, and standardization is fitted separately on the permitted
source rows of every model fold.

### Four Paderborn protocols

The random comparator uses six class-stratified shuffled measurement folds (seed 20260819). The
setting protocol leaves out each of four operating settings. The identity protocol uses six frozen,
class-balanced physical-identity groups. The crossed protocol evaluates all 24 identity-group by
setting intersections and quarantines both XOR arms. Every retained measurement receives exactly
one out-of-fold prediction from each protocol, method, and seed. All protocol results are also mapped
to the same 24 identity-group by setting cells.

The protocol analysis was specified after earlier Paderborn outcomes were available. It is therefore
reported as retrospective development evidence, regardless of the direction or magnitude of its
effects.

## Sealed HUST external replication

### Prospective cohort and chronology

The external dataset is the 51.2-kHz Hong--Thuan HUST Bearing v3
[@Thuan2023HUST; @Hong2023HUSTData], not the separate 25.6-kHz Zhao--Zio--Shen HUSTbearing release
used by Sun et al. [@Sun2026LeakageResistant]. It was selected after the Paderborn development
analysis and is distributed under CC BY 4.0. Before any signal file was
downloaded or opened, we froze the cohort, official file hashes, feature contract, folds, method
configurations, seeds, endpoints, resampling plan, expected artifact counts, and advancement rules.
The primary cohort contains 45 recordings: healthy (`N`), inner-race (`I`), and outer-race (`O`)
bearings at specification indices 4--8 and loads 0, 200, and 400 W. Each class contributes five
physical bearings, giving 15 physical bearings and three load recordings per bearing. The remaining
ball and compound-fault records are inaccessible to the primary study.

Specification index is used as the outer matching factor. A group such as index 4 contains three
different specimens (`N4`, `I4`, and `O4`) that share the 6204 specification. Consequently, the
matched-specification protocol confounds specimen identity with specification and cannot identify
their separate effects.

The prospective chronology is preserved as immutable runs: metadata-only topology; factorial seal;
official acquisition and file-hash validation; structural feature extraction; execution amendment
for an outcome-neutral indexing assertion; transitive runtime dependency lock; source/topology
preflight; one-shot model execution; and independent no-refit recomputation. Failed attempts remain
in the ledger and cannot be replaced silently.

### Signal and feature contract

Each official MAT file must expose exactly one eligible real numeric vector of 512,000 finite
samples, corresponding to ten seconds at 51.2 kHz. The entire vector is divided in acquisition order
into ten contiguous, non-overlapping one-second windows. We do not discard run-up, filter,
resample, overlap, augment, or amplitude-normalize the signal. The same 24 statistics used for each
Paderborn channel are computed on every window, producing 450 optimisation rows. Window
probabilities are averaged within a recording before argmax classification and all reported
endpoints. Thus, windows affect optimisation but not the prediction or inferential unit.

### Four HUST protocols

The recording-random comparator uses five class-stratified recording folds (seed 20260819), with all
ten windows from a recording kept together. The load protocol holds out each of the three loads. The
identity proxy holds out each of the five matched specification groups. The crossed design contains
15 specification-group by load folds. Each crossed fold has 24 source recordings, three target
recordings, and 18 quarantined recordings; all 45 recordings are targeted exactly once under every
protocol.

Source environments are load values in every protocol. Source-only nuisance pairs join aligned
windows from the same physical bearing at different loads. Source-only fault pairs join aligned
windows from different classes with the same specification group and load. Every crossed fold has
120 nuisance and 240 fault pairs. Target and quarantine coordinates cannot enter either pair set.

## Controlled model comparison

### Shared network and optimisation

All neural methods use a compact tabular encoder with a linear input layer, GELU activation, layer
normalisation, a second linear representation layer, unit-normalised representation, and linear
three-class head. Source features are standardized using source-only means and standard deviations.
Training uses full-batch AdamW for 300 epochs, learning rate 0.001, weight decay 0.0001, and gradient
clipping at norm 5.0. There is no target validation, target-aware early stopping, calibration, or
post-seal tuning. Five deterministic seeds are used: 11, 23, 37, 53, and 71. Seed probabilities are
averaged before measurement or recording aggregation and scoring.

The nine mechanism families are identical-backbone ERM, CORAL, V-REx, GroupDRO, DANN, LISA,
MatchDG, CCDG, and PIRL-ratio. Exact hyperparameters were selected on earlier source-only development
partitions and then frozen. Most methods use a 64-dimensional representation and penalty weight
1.0. V-REx uses 32 dimensions and penalty weight 0.1; GroupDRO uses exponentiated-gradient step
size 1.0. DANN uses gradient-reversal coefficient 1.0, LISA uses Beta(2,2) mixing, and CCDG uses
temperature 0.7. PIRL-ratio uses a 64-dimensional representation, nuisance/fault response-ratio
weight 1.0, intervention weight 1.0, response epsilon 0.0001, and rho 0.5. We evaluate controlled
implementations of mechanism families rather than claim exact reproduction of every original
architecture.

On Paderborn, the complete nine-method, four-protocol suite is repeated for vibration, motor current,
and fusion. A fixed seven-model classical suite (dummy prior, nearest centroid, shrinkage LDA, L2
logistic regression, linear SVM, RBF SVM, and ExtraTrees) provides a capacity-independent
falsification analysis. Classical and neural results are not pooled.

### Raw-vibration architecture sensitivity

Because the controlled mechanism suite uses compact statistics, a separately sealed retrospective
sensitivity adapts the MIT-licensed raw, log-FFT, and log-STFT CNN layer definitions of Knap et al.
[@Knap2026]. This is an attributed architecture adaptation, not a reproduction of their separate
source--target scenarios. From each complete 256,000-sample vibration record, four 8,192-sample
windows are taken at the fixed offsets 0, 82,603, 165,205, and 247,808. All windows from a recording
remain in the same split; each window is standardized independently.

Only measurement-random and strict crossed access are compared. The raw 1D CNN uses three
convolutional blocks (32/64/128 channels) and global pooling; the FFT variant prepends a
log-amplitude real FFT and instance normalization; the STFT variant uses a 1,024-point Hann STFT,
hop 256, a three-block 2D CNN, and global pooling. All models use the same 128--64--3 head, 50 fixed
epochs, AdamW at 0.001, batch size 128, and seeds 41, 42, and 43. No target validation, early
stopping, or post-seal search is permitted. Four window probabilities are averaged within recording
and seed, then three seed probabilities are averaged before scoring. The 270-fit family uses the
same physical-bearing bootstrap. Its frozen rule requires positive effects and positive interval
lower limits for all three architectures and a median random-minus-crossed effect of at least 0.15.
The sensitivity can strengthen only the access-gap conclusion; the nine-method rank result remains
specific to the shared compact backbone.

## Equal-source-volume HUST control

The strict crossed source contains fewer recordings than the easier HUST protocols. Before reading
any primary HUST scores, we therefore froze an auxiliary control that retains the exact crossed
target and exactly 24 source recordings per fold. Its source comprises both XOR arms plus six
recordings from the cyclic successor specification group at the two non-target loads. It exposes the
target bearings at other loads and the target load on other groups, but never an exact target
recording. Class balance, load and group support, source-window count, and the 120 nuisance/240 fault
pair budgets match the strict crossed protocol. All nine configurations and five seeds remain
unchanged.

For each method, the auxiliary contrast is shared-access equal-volume macro F1 minus strict-crossed
macro F1 on identical target recordings. This is a strong falsification of the simple training-size
explanation, not a causal estimate: the two source sets differ in information access as well as
membership.

## Outcomes and physical-unit inference

Primary performance is pooled, record-level macro F1. We also report balanced accuracy, accuracy,
minimum class recall, and the mean, median, minimum, and 25th percentile of common physical-cell
macro F1. Confusion matrices, method-minus-ERM effects, window-to-record disagreement, predictive
entropy, duration, parameter count, peak CUDA memory, and model-state hashes are retained as
secondary or audit outputs.

For each neural method, the primary protocol contrast is random-access pooled macro F1 minus
crossed-holdout pooled macro F1. Paderborn uses 2,000 paired, class-stratified physical-bearing
bootstrap draws. HUST uses 5,000 paired draws; within each of the three classes, five physical
bearings are sampled with replacement and all load recordings and protocol predictions for a sampled
bearing travel together. Percentile 2.5% and 97.5% limits are descriptive cohort-conditional
intervals. Windows, recordings from the same bearing, folds, and random seeds are not treated as
independent replicates. No p-value or universal population ordering is claimed.

For rank stability, methods are ordered by pooled record-level macro F1 with average ranks for ties.
We report Kendall's tau for every protocol pair, each method's rank shift, the maximum absolute
shift, and the score range in both protocols. Rank changes are always interpreted beside score
compression.

We also report descriptive finite-cohort selection regret. For every method tied for the best
accessible-protocol score, regret is the best crossed score minus that method's crossed score. A
unique accessible leader gives one value; an accessible ceiling tie gives the minimum and maximum
over all tied leaders. This endpoint quantifies the decision consequence on the observed cohort and
is not an expected regret for another machine population.

After the primary HUST conclusions were known, a separately frozen post-hoc audit recomputed both
access effects without refitting after deleting each of 15 bearings and each of five class-balanced
matched-specification groups. Every deletion is retained, strict sign stability requires every
effect to exceed zero, and no p-value is computed. The deletion ranges are sensitivity diagnostics,
not confidence intervals, independent replicates, or replacements for the primary bootstrap.

## Frozen external interpretation rules

The HUST protocol-gap pattern is called descriptively replicated only if at least seven of nine
random-minus-crossed point estimates are positive and their median is at least 0.15 macro F1.
Ranking instability is called descriptively replicated if random/crossed Kendall tau is below 0.50
or at least one method moves by three ranks. For the equal-volume control, the corresponding access
rule requires at least seven of nine positive shared-minus-crossed effects and a median of at least
0.10. These are predeclared advancement rules, not hypothesis tests. All methods, intervals, ranks,
failures, and null results are reported irrespective of whether a rule passes.

## Artifact verification

Every formal run records its expanded command, UTC timing, hardware and software environment, Git
state, input and output hashes, stdout, stderr, exit status, and source-tree fingerprint. Independent
validators consume frozen predictions and recompute seed ensembling, record aggregation, metrics,
cell summaries, ranks, bootstrap draws, confusion counts, diagnostics, and artifact hashes without
fitting a model. Final manuscript tables and figures must be generated only from independently
validated artifacts. A clean-checkout/container reproduction and the complete lint, test, and
coverage gates are required before submission.

## AI-assisted computational workflow

OpenAI Codex was used as an AI-assisted software-engineering and manuscript-preparation tool. It
proposed and edited analysis code, tests, experiment commands, documentation, and prose within the
versioned project workspace. It did not provide dataset labels or replace the numerical pipelines:
all reported values originate from deterministic scripts, sealed configurations, retained result
files, and independent no-refit validators. AI-proposed changes were subjected to the same automated
tests, static checks, hash verification, and artifact review as other changes. Human authors retain
sole responsibility for independently checking the analyses, citations, visualizations, and final
text before submission.
