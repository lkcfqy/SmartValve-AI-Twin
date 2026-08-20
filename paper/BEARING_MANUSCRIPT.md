# Physical Access Changes Estimated Bearing-Diagnosis Reliability: A Crossed Identity--Condition Audit with Sealed Replication

<!-- SMARTVALVE_EMPIRICAL_FINAL:WORKING_NOTICE:START -->
> **Working manuscript — raw sensitivity in progress.** All compact-feature Paderborn sensor and
> HUST claims below are independently validated. The final manuscript must contain no placeholder
> or unvalidated raw-architecture number.
<!-- SMARTVALVE_EMPIRICAL_FINAL:WORKING_NOTICE:END -->

## Abstract

<!-- SMARTVALVE_EMPIRICAL_FINAL:ABSTRACT:START -->
The abstract is held in `paper/TITLE_ABSTRACT.md` until the raw-architecture sensitivity passes its
independent validator. It will report the deployment question, physical-unit design, Paderborn
development result, sealed HUST replication, equal-volume falsification, representation
sensitivity, and narrow engineering implication in at most 200 words.
<!-- SMARTVALVE_EMPIRICAL_FINAL:ABSTRACT:END -->

## 1. Introduction

Machine-learning accuracy for bearing diagnosis is inseparable from the information made available
by the train/test split. A shuffled collection of measurements may withhold every target file and
still expose the same physical bearing, operating condition, acquisition session, or correlated
metadata during training. Such a split estimates performance for a new measurement drawn from a
partly familiar physical context. It does not estimate performance on a new bearing under a new
operating condition. The distinction matters because vibration and electrical signals can encode
stable specimen signatures as well as fault state, and the fixed association between a physical
bearing and its label can turn identity recognition into apparently successful diagnosis
[@Hendriks2022; @Abburi2023; @Matania2024; @Wheat2024; @Vieira2026].

Here, *estimated diagnostic reliability* means the credibility and repeatability of a reported
fault-classification performance estimate for a stated physical-access scenario. It does not mean
bearing survival probability, remaining useful life, safety integrity, or demonstrated factory
reliability. The reliability problem is evidential: an access-mismatched validation design can
produce an optimistic performance estimate and select a model or sensor that is not optimal for
the intended deployment population, even when every test record is formally held out.

Prior work has established the danger of recording and bearing reuse. Leakage-safe benchmarks have
separated runs or physical components, and recent studies have compared condition-wise and
bearing-wise validation, input representations, and vibration/current fusion
[@Matania2024; @Wheat2024; @Vieira2026; @Knap2026; @Kaya2026]. Panić et al. further show across more than
600,000 CWRU/Paderborn evaluations that pipeline choices can affect domain-shift results as much as
architecture and that optimal choices can reverse across collections [@Panic2027]. The unresolved
engineering question addressed here
is narrower but harder: how do performance, model choice, and sensor conclusions change when
physical identity and operating setting are manipulated jointly on the same cohort? In particular,
if identity \(b\) and setting \(s\) define the deployment target, training on either the same
identity at another setting or the same setting on another identity grants partial access to the
target context. We therefore quarantine both XOR cross-arms and compare the resulting
double-unseen target with three less restrictive access regimes.

This question is not only about the size of an accuracy drop. A convenient split is often used to
select an architecture or domain-generalization (DG) mechanism. DomainBed showed in general-purpose
DG that implementation and selection protocol can materially change method rankings
[@Gulrajani2021]. Industrial diagnosis adds nested physical dependence: many signal windows can come
from one recording, several recordings can come from one component, and the same component can
appear under several operating settings. Treating windows or optimisation seeds as independent
replicates can make a fragile ranking appear precise. A valid comparison must therefore hold model
capacity, hyperparameters, seeds, and target rows fixed across access protocols and quantify
uncertainty over physical components.

We conduct a factorial evaluation on the Paderborn KAt bearing corpus [@Lessmeier2016] and a sealed
external replication on HUST Bearing v3. Four protocols represent new measurements with shared context, unseen operating
setting with shared identities, unseen identity with shared settings, and simultaneous unseen
identity and setting. Nine source-only learning mechanisms—ERM, CORAL, V-REx, GroupDRO, DANN,
LISA, MatchDG, CCDG, and PIRL-ratio—share one compact encoder family, source-only preprocessing,
fixed development-selected configurations, 300-epoch budget, and five seeds. Paderborn additionally
repeats the full protocol panel for vibration, two-phase motor current, and fused features, while a
seven-model classical suite checks whether the main protocol effect is peculiar to neural
optimisation. Performance differences use paired, class-stratified physical-bearing bootstrap
intervals; method rankings are compared with Kendall's tau and explicit rank shifts.

The Paderborn analysis is retrospective development evidence. To prevent that result from becoming
a post-hoc generalization claim, the HUST cohort, official hashes, feature contract, four split
topologies, model configurations, seeds, endpoints, 5,000-draw physical-bearing resampling plan,
expected artifact counts, and descriptive advancement thresholds were sealed before any HUST signal
was downloaded or opened. The first valid HUST model run is retained regardless of outcome and is
recomputed by an independent no-refit validator. Before reading its scores, we also froze an
equal-source-volume control that compares strict crossed access with partial identity/setting access
on identical targets and exactly 24 source recordings per fold. This control addresses the most
immediate alternative explanation—that a crossed-protocol drop is merely caused by having fewer
training records—without claiming causal identification.

The contribution is an evaluation contract, not a new state-of-the-art classifier. Specifically,
the study contributes:

1. four access-matched views of the same records, culminating in a simultaneous identity-by-setting
   target for which both partial-access XOR arms are physically absent from fitting;
2. a controlled nine-method comparison of score and rank stability, rather than one proposed loss
   compared only with ERM;
3. sensor-family attribution under the same factorial topology on Paderborn;
4. paired uncertainty at the physical-bearing level rather than window- or seed-level
   pseudo-replication;
5. a sealed, signal-unopened HUST replication with predeclared interpretation rules and a separately
   frozen equal-volume falsification; and
6. an artifact chain that retains failed attempts and independently recomputes every primary table,
   rank, interval, and hash without model refitting.

We do not claim to discover bearing-identity leakage, introduce the first part-separated benchmark,
or provide the first vibration/current comparison. Those are established contributions
[@Hendriks2022; @Wheat2024; @Vieira2026; @Kaya2026]. Nor does the crossed contrast identify a causal
amount of leakage: the protocols target different deployment populations and change source
composition. The intended engineering conclusion is conditional and auditable—what model and
sensor conclusions survive when the physical access implied by deployment is enforced?

## 2. Related work

### 2.1 Leakage-safe bearing evaluation

Independent-component evaluation predates this study. Hendriks et al. showed that commonly used
condition-wise CWRU splits can place observations from the same bearing in both training and test
sets and proposed an independent-bearing evaluation [@Hendriks2022]. Abburi et al. likewise found
materially lower performance under bearing-aware splits [@Abburi2023]. Matania et al. identify
improper example separation as a recurring test--training leakage problem in condition-based
maintenance and explain why evaluation units must respect the underlying acquisition structure
[@Matania2024]. Wheat et al. compared
run-, day-, and part-separated pipelines on McMaster and Paderborn data, quantified large error-rate
changes, and audited the split reporting of prior Paderborn studies [@Wheat2024]. Their mechanism is
directly relevant: a model can decode physical-part identity, which remains correlated with its
fixed diagnostic class.

Knap et al. provide a reproducible leakage-safe CWRU/Paderborn benchmark with recording separation
and fixed source-to-target scenarios for operating condition, damage provenance, and bearing
identity, including raw 1D, FFT, and STFT CNN baselines [@Knap2026]. Vieira et al. extend
bearing-wise evaluation across CWRU, Paderborn, Ottawa,
and HUST, deliberately expose controlled leakage at test time, and show that invalid access can
change which vibration representation appears best [@Vieira2026]. These works establish
recording-separated evaluation, bearing-wise testing, HUST bearing evaluation, and
representation-sensitive leakage as prior art. Our distinction is not priority but factorial
combination: one common cohort is viewed under shared context, one-axis holdouts, and a two-axis
intersection in which both partial-access arms are quarantined; method ranks and sensor families are
then analysed on common physical units.

Two additional 2026 studies narrow the single-axis boundary. Li and Zhang report a non-peer-reviewed
Paderborn preprint with grouped recordings, a bearing-disjoint target, STFT input, and consumer-GPU
training [@LiZhang2026FSMSN]. It does not report the simultaneous unseen-identity/unseen-setting
intersection or XOR quarantine. Spirto et al. evaluate the Hong--Thuan HUST Bearing cohort under a
load change while the same four nominal bearing specifications appear in training/validation and
test [@Spirto2026]. Thus Paderborn bearing-disjoint STFT evaluation and HUST load transfer are also
prior art; the remaining question is their joint physical-access interaction, not either axis alone.

Panić et al. provide the closest broad protocol analysis: their task-focused pipeline isolates
speed, load, force, fault-type, and severity shifts on CWRU and Paderborn, introduces relative
performance drop, and shows that implementation choices and preferred baselines vary by collection
[@Panic2027]. This establishes systematic shift-factor and pipeline analysis as prior art. Our
question differs in the interaction and access estimand: physical identity and operating setting are
crossed on the same target cohort, both partial-access XOR arms are removed from fitting, uncertainty
resamples physical bearings, and the resulting access effect is tested once on a signal-unopened
HUST cohort with an equal-source-volume control. We therefore claim neither the first task-focused
domain-shift pipeline nor the first finding that design choices alter conclusions.

Compound distribution shifts are also explicit prior art. Alsafari and Yafoz jointly shift fault
severity and load in a leak-free CWRU/Paderborn few-shot benchmark and compare six architectures
[@Alsafari2026]. Their models adapt with labelled target support. Our two axes are physical identity
and setting, and the headline protocol is target-free with both one-axis cross-arms quarantined.
Accordingly, we claim neither the phrase “double domain shift” nor simultaneous two-factor
evaluation as new; the distinction is the physical access contract and paired rank audit.

Sun et al. address a complementary HUSTbearing leakage mechanism by partitioning continuous
records before windowing, inserting guard intervals, auditing overlap, and comparing raw and
log-STFT representations [@Sun2026LeakageResistant]. Their study uses the distinct
Zhao--Zio--Shen 25.6-kHz, nine-state/11-condition release; ours uses the Hong--Thuan 51.2-kHz HUST
Bearing v3 cohort [@Thuan2023HUST; @Hong2023HUSTData]. Their estimand is temporal-neighbour
separation, whereas ours is physical specification-by-load access. We therefore do not claim first
partition-before-windowing, leakage-resistant HUST evaluation, or raw/time-frequency sensitivity.

Mannone et al. evaluate a self-supervised masked-spectrogram Transformer on the same three-class
real-damage Paderborn subset using complete four-second measurements and ten bearing-code-disjoint
splits [@Mannone2026VibFM]. Paderborn is excluded from their 16-dataset pretraining corpus, making
this a strong precedent for leakage-resistant foundation-model transfer. Their four operating
conditions remain available on both sides of a bearing split; per-condition results are diagnostic
breakdowns, not an unseen-setting or crossed target. We therefore position compact engineered
features as a controlled low-compute representation, not as a comprehensive alternative to raw or
pretrained signal encoders.

### 2.2 Operating-condition generalization and method selection

DG seeks a predictor that transfers to an unseen target environment without target-domain training
data. Mechanism families include moment alignment through CORAL [@Sun2016DeepCORAL], risk-variance
regularization through V-REx [@Krueger2021], worst-group reweighting through GroupDRO
[@Sagawa2020], adversarial environment suppression through DANN [@Ganin2016], selective
interpolation through LISA [@Yao2022], matched-instance alignment through MatchDG
[@Mahajan2021], and class-conditional contrast for machinery diagnosis through CCDG
[@Ragab2022]. Invariant or causal language does not itself establish identification; IRM, for
example, has known failure regimes under finite environments and representation flexibility
[@Arjovsky2019; @Rosenfeld2021].

For machinery diagnosis specifically, Zhao et al. formulate an application-oriented DG taxonomy
and benchmark existing methods across eight public and two self-collected datasets under
cross-condition and cross-machine tasks [@Zhao2024]. Their work establishes broad industrial DG
benchmarking and reproducible method comparison as prior art. The present study does not propose a
replacement taxonomy or another accuracy leaderboard. It audits whether a benchmark score and the
method selected from it remain valid when physical identity and operating-setting access are
changed jointly and made explicit.

Comparison protocol is therefore part of the claim. DomainBed demonstrated that changes in
architecture, tuning, and model selection can reverse generic DG conclusions and that a carefully
implemented ERM baseline is difficult to beat [@Gulrajani2021]. WILDS similarly documented large
in-distribution/out-of-distribution gaps under standardized, naturally occurring shifts
[@Koh2021]. We adapt the mechanism families to one source-only industrial protocol, share the
network, optimiser, epoch budget, preprocessing, and seed set, and describe them as controlled
mechanism implementations rather than exact reproductions of every original architecture. The
endpoint is not universal algorithm superiority; it is whether the finite-cohort method ordering is
stable to a physically meaningful access change.

### 2.3 Multi-sensor bearing diagnosis

Multi-sensor fusion can improve diagnosis while also multiplying shortcut channels. Kaya and Jobani
provide the closest Paderborn comparison: they evaluate vibration, phase current, and their fusion
under measurement-wise and operating-condition holdout validation and add separate bearing-code
holdout scenarios for selected temporal models [@Kaya2026]. Their paper explicitly leaves combined
bearing-code and operating-condition holdout as future work. Accordingly, vibration/current/fusion,
condition holdout, and bearing-code holdout are not claimed here as novel in isolation. We place all
three sensor families inside one four-protocol panel, retain both XOR arms as inaccessible in the
crossed case, and ask whether access changes not only sensor performance but the ordering of nine DG
mechanisms.

Cross-setting bearing re-identification is included as a diagnostic. High re-identification macro
F1 demonstrates that a feature family retains physical-identity information when the operating
setting changes. It does not prove that a fault classifier uses that information, and a smaller
protocol gap for current than vibration does not prove that current is identity-free. The factorial
fault result, re-identification result, and equal-volume control are therefore reported as distinct
pieces of evidence.

### 2.4 Scope of inference

The study is intentionally narrower than causal representation learning or deployed safety. Its
paired controls and quarantined topology make information access explicit, but do not specify a
structural causal graph or identify counterfactual fault outcomes. Bootstrap intervals quantify
uncertainty conditional on the observed physical-bearing cohorts; they do not establish a universal
ordering across machines, factories, or sensor installations. Likewise, a source-only DANN variant
aligns observed source load environments and does not consume unlabeled target data as in the
original adaptation setting. These boundaries allow a strong reliability claim without relabelling
an evaluation effect as an algorithmic or causal breakthrough.

## 3. Methods

### 3.1 Study question and estimands

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

Table 1 states the corresponding source, target, quarantine, and deployment semantics; Figure 1
shows the same two-axis physical-access lattice. These visual definitions are part of the estimand,
not merely split-implementation details.

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

### 3.2 Paderborn development study

#### 3.2.1 Cohort, physical units, and signals

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

#### 3.2.2 Fixed feature families

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

#### 3.2.3 Four Paderborn protocols

The random comparator uses six class-stratified shuffled measurement folds (seed 20260819). The
setting protocol leaves out each of four operating settings. The identity protocol uses six frozen,
class-balanced physical-identity groups. The crossed protocol evaluates all 24 identity-group by
setting intersections and quarantines both XOR arms. Every retained measurement receives exactly
one out-of-fold prediction from each protocol, method, and seed. All protocol results are also mapped
to the same 24 identity-group by setting cells.

The protocol analysis was specified after earlier Paderborn outcomes were available. It is therefore
reported as retrospective development evidence, regardless of the direction or magnitude of its
effects.

### 3.3 Sealed HUST external replication

#### 3.3.1 Prospective cohort and chronology

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

#### 3.3.2 Signal and feature contract

Each official MAT file must expose exactly one eligible real numeric vector of 512,000 finite
samples, corresponding to ten seconds at 51.2 kHz. The entire vector is divided in acquisition order
into ten contiguous, non-overlapping one-second windows. We do not discard run-up, filter,
resample, overlap, augment, or amplitude-normalize the signal. The same 24 statistics used for each
Paderborn channel are computed on every window, producing 450 optimisation rows. Window
probabilities are averaged within a recording before argmax classification and all reported
endpoints. Thus, windows affect optimisation but not the prediction or inferential unit.

#### 3.3.3 Four HUST protocols

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

### 3.4 Controlled model comparison

#### 3.4.1 Shared network and optimisation

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

#### 3.4.2 Raw-vibration architecture sensitivity

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

### 3.5 Equal-source-volume HUST control

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

### 3.6 Outcomes and physical-unit inference

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

After the primary HUST outcomes and broad conclusions were known, we froze a separate post-hoc
physical-unit influence audit. Without refitting, it recomputes both the recording-random-minus-
crossed and equal-volume-shared-minus-crossed effects after deleting (i) one of the 15 physical
bearings with all three load recordings or (ii) one of five matched-specification groups with its
three class-specific bearings. Every method, comparison, and deletion is retained. Strict sign
stability requires every deletion effect to remain greater than zero. These deletion ranges are
sensitivity diagnostics, not confidence intervals or independent replicates; no p-value is
computed, and the audit does not replace the predeclared physical-bearing bootstrap.

### 3.7 Frozen external interpretation rules

The HUST protocol-gap pattern is called descriptively replicated only if at least seven of nine
random-minus-crossed point estimates are positive and their median is at least 0.15 macro F1.
Ranking instability is called descriptively replicated if random/crossed Kendall tau is below 0.50
or at least one method moves by three ranks. For the equal-volume control, the corresponding access
rule requires at least seven of nine positive shared-minus-crossed effects and a median of at least
0.10. These are predeclared advancement rules, not hypothesis tests. All methods, intervals, ranks,
failures, and null results are reported irrespective of whether a rule passes.

### 3.8 Artifact verification

Every formal run records its expanded command, UTC timing, hardware and software environment, Git
state, input and output hashes, stdout, stderr, exit status, and source-tree fingerprint. Independent
validators consume frozen predictions and recompute seed ensembling, record aggregation, metrics,
cell summaries, ranks, bootstrap draws, confusion counts, diagnostics, and artifact hashes without
fitting a model. Final manuscript tables and figures must be generated only from independently
validated artifacts. A clean-checkout/container reproduction and the complete lint, test, and
coverage gates are required before submission.

### 3.9 AI-assisted computational workflow

OpenAI Codex was used as an AI-assisted software-engineering and manuscript-preparation tool. It
proposed and edited analysis code, tests, experiment commands, documentation, and prose within the
versioned project workspace. It did not provide dataset labels or replace the numerical pipelines:
all reported values originate from deterministic scripts, sealed configurations, retained result
files, and independent no-refit validators. AI-proposed changes were subjected to the same automated
tests, static checks, hash verification, and artifact review as other changes. Human authors retain
sole responsibility for independently checking the analyses, citations, visualizations, and final
text before submission.

## 4. Results

### 4.1 Paderborn classical falsification and identity diagnostic

With the cohort, feature matrix, and target rows held fixed, the seven-model classical suite showed
a large access effect that was not specific to the compact neural encoder. ExtraTrees fusion macro
F1 was 0.998389 under measurement-random access and 0.544720 under crossed holdout, a paired
physical-bearing effect of 0.453670 (95% percentile interval 0.332442--0.596978). Its minimum common
cell macro F1 fell from 0.983323 to 0.164103. ExtraTrees remained the best classical model under all
four protocols, so this analysis supports score sensitivity but not a classical winner reversal.

The sensor audit further showed that exact bearing identity remained decodable across operating
settings. The strongest 29-class re-identification macro F1 was 0.603389 from vibration with linear
SVM, 0.511639 from motor current with ExtraTrees, and 0.696992 from fusion with ExtraTrees. The
explicit dummy-prior baseline had macro F1 0.002300; balanced-chance accuracy and balanced accuracy
are 1/29 = 0.034483. These values diagnose identity information in all three feature families; they
do not establish that the fault classifiers causally used it.

For ExtraTrees, random/crossed macro F1 was 0.990864/0.598245 for vibration,
0.982279/0.382770 for motor current, and 0.998389/0.544720 for fusion. The vibration-minus-current
difference in protocol gaps was -0.206891 (95% interval -0.345241 to -0.052394): despite stronger
cross-setting re-identification, vibration retained substantially more crossed diagnostic
performance than motor current. Thus re-identification strength and diagnostic protocol loss are
related diagnostics, not interchangeable estimands.

### 4.2 Paderborn neural protocol contrast

#### 4.2.1 Fusion features

All nine methods were near the ceiling under measurement-random access but performed substantially
worse when both identity and setting were unseen. The complete pooled macro-F1 panel is:

Table 2 reports all four access protocols and their paired random-minus-crossed effects; Figure 2
shows the same method profiles without suppressing intermediate one-axis holdouts.

| Method | Random | Setting only | Identity only | Crossed | Random - crossed |
|---|---:|---:|---:|---:|---:|
| CCDG | 0.987148 | 0.693530 | 0.444517 | 0.360074 | 0.627074 |
| CORAL | 0.987114 | 0.710589 | 0.428882 | 0.365211 | 0.621903 |
| DANN | 0.986582 | 0.715607 | 0.422201 | 0.381491 | 0.605091 |
| ERM | 0.986785 | 0.715940 | 0.426079 | 0.363616 | 0.623169 |
| GroupDRO | 0.987102 | 0.704040 | 0.417081 | 0.371644 | 0.615458 |
| LISA | 0.985489 | 0.711340 | 0.438564 | 0.370798 | 0.614691 |
| MatchDG | 0.964534 | 0.700543 | 0.448653 | 0.403121 | 0.561413 |
| PIRL-ratio | 0.980487 | 0.724324 | 0.397558 | 0.386175 | 0.594312 |
| V-REx | 0.985665 | 0.695289 | 0.436549 | 0.361551 | 0.624114 |

Every random-minus-crossed 2,000-draw bearing-bootstrap interval excluded zero; lower limits ranged
from 0.456014 to 0.526773. Access also changed the pooled ordering: CCDG ranked first and MatchDG
ninth under random access, whereas MatchDG ranked first and CCDG ninth under crossed access.
Random/crossed Kendall tau was -0.555556. Because the random scores occupied only
0.964534--0.987148, this ordinal reversal is always reported beside the compressed score range.
The crossed scores occupied 0.360074--0.403121.

#### 4.2.2 Vibration features

Vibration produced higher crossed performance than fusion for every method, while retaining a large
random/crossed gap:

| Method | Random | Setting only | Identity only | Crossed | Random - crossed |
|---|---:|---:|---:|---:|---:|
| CCDG | 0.942579 | 0.757298 | 0.633287 | 0.525050 | 0.417529 |
| CORAL | 0.940175 | 0.774750 | 0.644822 | 0.533362 | 0.406813 |
| DANN | 0.934865 | 0.772695 | 0.595329 | 0.504998 | 0.429867 |
| ERM | 0.938577 | 0.774361 | 0.639351 | 0.540528 | 0.398049 |
| GroupDRO | 0.932638 | 0.765748 | 0.596881 | 0.509259 | 0.423378 |
| LISA | 0.920816 | 0.756534 | 0.651184 | 0.538723 | 0.382094 |
| MatchDG | 0.878226 | 0.751855 | 0.652552 | 0.584793 | 0.293433 |
| PIRL-ratio | 0.912067 | 0.753246 | 0.646555 | 0.549296 | 0.362770 |
| V-REx | 0.935419 | 0.774202 | 0.642418 | 0.532411 | 0.403008 |

All nine physical-bearing interval lower limits were positive (0.213272--0.344104). CCDG led
random access, while MatchDG led crossed access. MatchDG moved from ninth to first and
random/crossed Kendall tau was -0.388889. Compared with fusion, the smaller vibration gap coexisted
with materially better crossed scores, showing that the sensor conclusion itself depends on the
deployment protocol.

#### 4.2.3 Motor current and paired sensor attribution

Motor current retained the access effect but produced a lower and wider measurement-random score
range than vibration or fusion:

| Method | Random | Setting only | Identity only | Crossed | Random - crossed | 95% interval |
|---|---:|---:|---:|---:|---:|---:|
| CCDG | 0.892775 | 0.557013 | 0.400410 | 0.411920 | 0.480854 | 0.410755--0.554085 |
| CORAL | 0.892886 | 0.530213 | 0.398472 | 0.379816 | 0.513071 | 0.443951--0.580216 |
| DANN | 0.894312 | 0.593167 | 0.398979 | 0.395491 | 0.498822 | 0.412460--0.586812 |
| ERM | 0.888375 | 0.537780 | 0.389472 | 0.380625 | 0.507751 | 0.437595--0.575689 |
| GroupDRO | 0.885384 | 0.527937 | 0.405632 | 0.373024 | 0.512360 | 0.451585--0.574019 |
| LISA | 0.887727 | 0.608174 | 0.413748 | 0.416901 | 0.470826 | 0.390688--0.549391 |
| MatchDG | 0.730703 | 0.617351 | 0.373152 | 0.432645 | 0.298059 | 0.201835--0.400718 |
| PIRL-ratio | 0.748995 | 0.586048 | 0.381565 | 0.429196 | 0.319798 | 0.220598--0.413750 |
| V-REx | 0.888265 | 0.534846 | 0.390419 | 0.369564 | 0.518701 | 0.450116--0.583967 |

All nine interval lower limits were positive. DANN led measurement-random access, while MatchDG
led crossed access and moved from ninth to first; pooled-rank Kendall tau was -0.333333. The
current-only result therefore reproduces Paderborn's finite-cohort leader instability without
claiming that the identity of a winning method generalizes beyond this cohort.

The combined no-refit analysis then placed all three sensor views on exactly the same 2,319 target
records, nine methods, four protocols, and 2,000 physical-bearing bootstrap draws. All 27
sensor-by-method random-minus-crossed intervals had positive lower limits. Fusion's protocol gap
exceeded vibration's for every method: paired differences were 0.175224--0.267980, and all nine
intervals excluded zero. Fusion also had a larger gap than motor current for every method
(0.103098--0.274513), with six of nine intervals excluding zero. In contrast, vibration-minus-
current gap differences ranged from -0.115693 to 0.042972 and none of their nine intervals excluded
zero.

Table 3 reports the complete 27-cell sensor-by-method attribution, and Figure 4 displays the paired
protocol gaps on their common bearing-bootstrap scale. Supplementary Table S1 gives every paired
between-sensor gap contrast and interval rather than only the counts summarized above.

Absolute crossed performance gave a different sensor conclusion. Vibration exceeded fusion for
all nine methods by 0.123507--0.181672; eight of nine paired intervals excluded zero. Vibration
also exceeded motor current for every method by 0.109507--0.162847, with five intervals excluding
zero. Motor current exceeded fusion by only 0.001380--0.051846 and none of those intervals excluded
zero. MatchDG was the crossed leader for all three views. These results show that fusion's near-
ceiling random scores do not imply better simultaneous unseen-identity-and-setting performance.
They do not identify which signal feature a classifier causally uses.
Supplementary Table S2 retains every paired crossed-score contrast and interval.

#### 4.2.4 Raw-vibration architecture sensitivity

<!-- SMARTVALVE_EMPIRICAL_FINAL:RAW_RESULTS:START -->
**Submission hold:** the separately sealed Knap-style raw-1D, log-FFT, and log-STFT sensitivity has
entered its frozen 270-fit, from-scratch EXP-456R1 recovery execution after EXP-456 was externally
interrupted and excluded. No intermediate performance outcome is inspected. It is a retrospective
two-protocol falsification of compact-representation dependence, not an additional confirmatory
family. Its complete three-architecture result will be reported only after EXP-457 independent
no-refit validation.
<!-- SMARTVALVE_EMPIRICAL_FINAL:RAW_RESULTS:END -->

### 4.3 Sealed HUST external replication

The one-shot HUST run completed all 1,260 frozen fits, 81,000 seed-window predictions, 1,620
recording-level method/protocol predictions, 5,000 physical-bearing bootstrap draws, and every
expected secondary artifact. The independent validator refit no model and reproduced probabilities
exactly, with maximum aggregate, rank, and bootstrap numeric differences below
5e-13. All 45 official input files and the 450-row feature topology retained their locked hashes.

#### 4.3.1 Performance and protocol-gap replication

All methods achieved macro F1 1.000000 under both recording-random and load-holdout access. Under
matched-specification holdout, eight methods scored 0.797980 and DANN scored 0.741591. Under the
simultaneous crossed protocol, pooled recording macro F1 was 0.746795--0.773970:

Table 4 reports the full HUST four-protocol result.

| Method | Random | Load only | Specification only | Crossed | Random - crossed | 95% interval |
|---|---:|---:|---:|---:|---:|---:|
| CCDG | 1.000000 | 1.000000 | 0.797980 | 0.751920 | 0.248080 | 0.068623--0.453149 |
| CORAL | 1.000000 | 1.000000 | 0.797980 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| DANN | 1.000000 | 1.000000 | 0.741591 | 0.746795 | 0.253205 | 0.087747--0.457615 |
| ERM | 1.000000 | 1.000000 | 0.797980 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| GroupDRO | 1.000000 | 1.000000 | 0.797980 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| LISA | 1.000000 | 1.000000 | 0.797980 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| MatchDG | 1.000000 | 1.000000 | 0.797980 | 0.773970 | 0.226030 | 0.067340--0.416667 |
| PIRL-ratio | 1.000000 | 1.000000 | 0.797980 | 0.751920 | 0.248080 | 0.068623--0.453149 |
| V-REx | 1.000000 | 1.000000 | 0.797980 | 0.773970 | 0.226030 | 0.067340--0.441705 |

All nine point effects were positive and all nine interval lower limits exceeded zero. The median
effect was 0.226030. The predeclared external protocol-gap rule required at least seven positive
effects and median effect at least 0.15; it therefore passed 9/9 and exceeded the magnitude
threshold.

The result is not an algorithm leaderboard. Six methods tied at 0.773970 under crossed access;
CCDG and PIRL-ratio tied at 0.751920, and DANN scored 0.746795. Each crossed physical cell contains
only one recording per class, and every method's minimum cell macro F1 was 0.333333. The inferential
evidence concerns protocol sensitivity across physical bearings, not a universally superior method.

#### 4.3.2 Rank endpoint and ceiling limitation

The frozen rank-instability rule mechanically passed because the maximum average-rank movement was
four positions. However, recording-random and load-holdout performance was exactly 1.0 for all nine
methods, giving every method average rank 5 and making Kendall tau undefined rather than negative.
The observed four-position movement is therefore a consequence of a complete ceiling tie followed
by small crossed differences; it is not an external replication of Paderborn's directional winner
reversal. Matched-specification/crossed Kendall tau was 0.632456 for pooled macro F1 and 0.442326
for mean-cell macro F1. The honest conclusion is asymmetric: HUST strongly replicates the protocol
gap, while its frozen rank rule passes in a scientifically weak, ceiling-limited form.

#### 4.3.3 Equal-source-volume access control

The outcome-blind auxiliary run completed 675 frozen fits. It used the same target recordings and
exactly 24 source recordings per fold in both arms, with identical class balance, all load/group
support, and matched 120 nuisance/240 fault pair budgets. Every method achieved macro F1 1.000000
under equal-volume shared access, compared with 0.746795--0.773970 under strict crossed access:

Table 5 reports the method-level effects, and Figure 5 contrasts the primary and equal-volume
access comparisons on the same physical-bearing scale.

| Method | Equal-volume shared | Strict crossed | Shared - crossed | 95% interval |
|---|---:|---:|---:|---:|
| CCDG | 1.000000 | 0.751920 | 0.248080 | 0.068623--0.453149 |
| CORAL | 1.000000 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| DANN | 1.000000 | 0.746795 | 0.253205 | 0.087747--0.457615 |
| ERM | 1.000000 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| GroupDRO | 1.000000 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| LISA | 1.000000 | 0.773970 | 0.226030 | 0.067340--0.441705 |
| MatchDG | 1.000000 | 0.773970 | 0.226030 | 0.067340--0.416667 |
| PIRL-ratio | 1.000000 | 0.751920 | 0.248080 | 0.068623--0.453149 |
| V-REx | 1.000000 | 0.773970 | 0.226030 | 0.067340--0.441705 |

All nine effects were positive, all nine interval lower limits exceeded zero, and the median effect
was 0.226030. The frozen access rule required at least seven positive effects and a median of at
least 0.10; it passed 9/9. Thus the HUST protocol effect cannot be explained by source-record count
alone. It remains an access-and-membership contrast rather than a causal estimate of leakage.

The independent validator refit no model and reproduced all prediction, aggregation, rank,
bootstrap, confusion, and diagnostic artifacts with maximum numeric difference below 5e-13. The
first validator invocation is retained as a failed audit: exact Python dictionary equality treated
two undefined Kendall correlations (`NaN`) as unequal. Version 0.1.1 changed only the validator to
recognize `NaN`-to-`NaN` equivalence and allow at most 1e-12 serialization drift; the successful
recomputation had zero numeric difference in the findings themselves.

#### 4.3.4 Post-hoc physical-unit influence

The no-refit deletion audit covered all 18 method-by-comparison cells. Effects remained positive in
18/18 cells under leave-one-bearing-out deletion and 18/18 cells under class-balanced
leave-one-specification-group-out deletion. The minimum deleted-sample effects were 0.174546 and
0.112234, respectively. The largest absolute changes from the corresponding full-cohort effects
were 0.051485 and 0.113796. Supplementary Table S4 reports all 18 summary cells, while the release
archive retains all 270 bearing-deletion and 90 group-deletion rows. This post-hoc result shows that
no single observed bearing or matched group reverses an observed contrast; it does not create more
independent physical units, estimate a factory population, or strengthen the prospective status of
the sealed HUST analysis.

<!-- SMARTVALVE_EMPIRICAL_FINAL:SYNTHESIS:START -->
### 4.4 Cross-dataset synthesis pending raw-architecture validation

The validated evidence shows a large random/crossed protocol gap on both Paderborn and HUST with
physical-bearing interval lower limits above zero for all 36 method-by-system/sensor primary
contrasts: 27 across the three Paderborn sensor views and nine on HUST. Paderborn demonstrates
leader instability under all three sensor views and shows that vibration is materially stronger
than fusion under crossed access despite fusion's higher random scores. HUST does not provide
comparable rank discrimination because its easy protocols saturate. The equal-source-volume
falsification excludes source-record count as a sufficient explanation for the HUST effect. The
remaining empirical hold is the separately sealed raw/FFT/STFT analysis, which determines whether
the protocol-gap conclusion survives representations outside the compact statistic family.
<!-- SMARTVALVE_EMPIRICAL_FINAL:SYNTHESIS:END -->

## 5. Discussion

### 5.1 The deployment estimand changes the result

<!-- SMARTVALVE_EMPIRICAL_FINAL:DISCUSSION_ACCESS:START -->
The most stable finding is not that one learning mechanism wins, but that the stated deployment
access materially changes diagnostic performance. On Paderborn, every neural method lost at least
0.561 macro F1 with fusion features, at least 0.293 with vibration, and at least 0.298 with motor
current when moving from measurement-random to simultaneous unseen identity and setting. On HUST,
every method lost 0.226--0.253 recording-level macro F1. All 36 validated random-minus-crossed
physical-bearing intervals have positive lower limits: nine methods for each of the three
Paderborn sensor views and nine on HUST.
<!-- SMARTVALVE_EMPIRICAL_FINAL:DISCUSSION_ACCESS:END -->

This consistency does not mean the three contrasts estimate the same causal quantity. The random
and crossed protocols change which physical contexts are represented in the source, and the
crossed design excludes both partial-access arms. The estimates answer operational questions: what
happens when a deployment grants or withholds observations from the same identity and setting? A
paper that reports only the random result describes a different deployment population from one that
claims transfer to a new component under a new condition.

HUST sharpens the distinction. Recording-random and load-holdout performance was exactly 1.0 for
all nine mechanisms; load holdout therefore appeared solved. Yet crossed performance was
approximately 0.75--0.77 and every method's minimum three-record physical-cell macro F1 was 1/3.
Holding out load alone did not test the double-unseen deployment claim. The remaining errors were
concentrated in fault discrimination rather than health detection: for ERM, all 15 healthy
recordings were correct, whereas inner and outer faults were confused. This is a more actionable
failure mode than an undifferentiated average score because it identifies where deployment
validation must be strengthened.

### 5.2 Paderborn rank reversal did not cleanly replicate on HUST

Paderborn provides strong finite-cohort evidence that a convenient split can select a different
method. With fusion, CCDG moved from first under random access to ninth under crossed access, while
MatchDG moved from ninth to first; Kendall tau was -0.556. Vibration showed the same directional
leader exchange and tau -0.389. These shifts were not generated by different searches or training
budgets: configurations and seeds were fixed, and every method predicted the same physical rows.

The decision consequence is visible in finite-cohort selection regret (Supplementary Table S3).
Selecting the unique random-access leader and then evaluating it under crossed access lost 0.059743
macro F1 for vibration, 0.043047 for fusion, and 0.037154 for motor current relative to the
crossed-access leader. These are observed-cohort oracle differences, not estimates of future-factory
regret, but they translate an ordinal rank change into the score paid by a protocol-mismatched
selection decision.

HUST, however, could not discriminate methods under the easy protocols. All nine scores tied at
1.0, making random/crossed Kendall tau undefined. The predeclared rank-instability rule formally
passed through a four-position average-rank movement, but this is a tie-breaking consequence of a
complete ceiling followed by small crossed differences. Six methods also tied for the highest
crossed macro F1. We therefore do not describe HUST as reproducing a directional winner reversal.
It reproduces access sensitivity while showing that ranking is not always an estimable endpoint on
a small saturated cohort.

Because every HUST method was accessible-optimal, its crossed regret ranged from 0 to 0.027175
depending on how the nine-way tie was resolved. Reporting this range is more faithful than choosing
one arbitrary random-access winner and assigning it a single regret.

This asymmetry is scientifically useful. A protocol can expose a large deployment-performance gap
even when it cannot support claims about algorithm ordering. Future benchmark designs should
pre-screen neither methods nor datasets based on their ability to create a visually appealing
leaderboard. They should report the score range, ties, and physical sample size alongside rank
statistics and treat an undefined correlation as an outcome rather than silently perturbing ties.

### 5.3 Sensor information is not equivalent to sensor robustness

The completed Paderborn evidence rejects a simple story in which greater identity decodability
implies a larger diagnostic access gap. Fusion features supported the strongest exact bearing
re-identification, but vibration produced substantially higher crossed neural performance than
fusion. Fusion's random-minus-crossed gap exceeded vibration's for all nine methods, with every
paired physical-bearing interval above zero. Vibration's crossed score exceeded fusion's for all
nine methods, with eight of nine intervals excluding zero. In the classical suite, motor current
had lower cross-setting re-identification than vibration but also much lower crossed ExtraTrees
diagnostic performance. Thus a feature family can contain decodable identity, fault, condition,
and interaction information simultaneously.

The random split rewards any stable signal correlated with class, including specimen signatures.
The crossed split rewards features whose fault discrimination survives both new identity and new
setting. Sensor fusion can improve the former while degrading the latter if one channel adds a
shortcut that the finite model prefers over a portable cue. Consistent with that risk, fusion's
gap also exceeded motor current's for all nine methods, although only six paired intervals excluded
zero. Vibration and current did not differ reliably in gap magnitude: none of nine paired intervals
excluded zero, even though vibration had higher crossed point scores for every method. This remains
a shortcut-risk interpretation rather than causal feature attribution; the paired analysis
describes what survives the access intervention, not why an internal representation fails.

### 5.4 Training volume is a necessary falsification, not a semantic detail

The strict crossed source is smaller than the random, one-axis, or union-access sources. A raw
random-minus-crossed contrast therefore combines information access with source membership and
quantity. This is why we do not label the entire gap “leakage.” The outcome-blind HUST auxiliary
control gave strict crossed and partial shared access the same 24 source recordings, class balance,
load/specification support, target recordings, and pair budget. All nine shared-minus-crossed
effects were positive, their median was 0.226, and every physical-bearing interval excluded zero.
The frozen 7/9 and 0.10 rule therefore passed. Source-record count alone is not a sufficient
explanation for the HUST result.

The passing control does not identify a causal leakage amount. Source memberships differ by
construction and the shared arm exposes both the target identity at other loads and the target load
on other groups. The control is best understood as a falsification of one plausible alternative
explanation, not a substitute for randomized assignment of physical assets.

### 5.5 A minimum reporting contract for bearing diagnosis

The results support a compact reporting contract that is independent of any one architecture:

1. define the prediction row, physical component, operating setting, acquisition session, and all
   nesting before a split is created;
2. publish an access ledger stating whether training reads the same recording, identity at another
   setting, target setting on another identity, target-normal signal, unlabeled target covariates,
   or target labels;
3. include at least one identity-disjoint evaluation when deployment concerns new components, and a
   crossed evaluation when both identity and setting are claimed unseen;
4. keep both XOR partial-access arms outside preprocessing, calibration, selection, and early
   stopping for a strict crossed claim;
5. report source and target physical counts, class balance, environment support, and an
   equal-volume or learning-curve sensitivity when protocols differ materially in source size;
6. compare several mechanisms under one backbone and selector, and report absolute score spread and
   ties beside ranks;
7. aggregate windows to the operational prediction unit and quantify uncertainty over physical
   components, not optimisation seeds; and
8. preserve complete predictions, split coordinates, code/input hashes, failed runs, and an
   independent no-refit recomputation path.

This contract is more consequential than adding another penalty to a benchmark whose split does not
match deployment. The earlier SmartValve PIRL superiority hypothesis failed its frozen multi-rig
gate, while the present protocol analysis produced a replicated access effect without inventing a
new classifier. That sequence illustrates the value of allowing prospective evaluation to reject
the original algorithmic story.

### 5.6 Limitations

Paderborn is retrospective for the factorial question and cannot serve as independent confirmation.
HUST is protocol-prospective and signal-unopened before sealing, but not literature-outcome-blind:
bearing-wise HUST results from prior work were known. HUST includes only five physical bearings per
class. Its matched specification index groups three class-specific specimens and therefore
confounds specimen identity with bearing specification. Each crossed physical cell contains only
three recordings, producing coarse cell metrics and wide cohort-conditional bootstrap intervals.

<!-- SMARTVALVE_EMPIRICAL_FINAL:REPRESENTATION_LIMITATION:START -->
Both corpora are controlled public test rigs rather than prospectively sampled factories. The
shared 24-statistic representation and compact full-batch encoder enable controlled low-compute
comparison but do not exhaust raw-signal CNNs, transformers, self-supervised encoders, or
current-specific demodulation. The implementations isolate mechanism families under a common
protocol; they are not exact reproductions of every original architecture and search space.
<!-- SMARTVALVE_EMPIRICAL_FINAL:REPRESENTATION_LIMITATION:END -->

The four protocols change source membership and, in the primary comparisons, source quantity. The
passing equal-volume control rules out only the simplest quantity explanation. Re-identification is a
decodability probe, not evidence of causal classifier reliance. Physical-bearing bootstrap
intervals condition on the observed cohorts and do not guarantee transfer to another machine,
factory, sensor installation, or fault taxonomy. No safety, causal identification, or deployed
reliability claim follows from these public-data experiments.

Finally, the project has not yet received independent human review from a condition-monitoring
expert or statistician, and a self-authored validator can share conceptual errors with its producer
even when it recomputes every byte independently. The retained validator failure also illustrates
why `NaN` semantics and serialization tolerances must be tested explicitly. A clean-environment
reproduction and external review remain submission gates.

## 6. Conclusion

<!-- SMARTVALVE_EMPIRICAL_FINAL:CONCLUSION:START -->
The evidence supports a protocol paper rather than an algorithm paper. Simultaneously withholding
physical identity and operating setting reveals substantial diagnostic degradation on both
Paderborn development data and a sealed HUST replication; a one-axis load holdout can remain
perfect while that double-unseen target fails. The same HUST gap survives an equal-source-volume
control, so training-record count is not a sufficient explanation. Paderborn further shows that
method and sensor conclusions can reverse under access, whereas HUST's ceiling prevents a
meaningful external leaderboard. The remaining empirical hold is the sealed raw/FFT/STFT
representation sensitivity and must be reported whether positive or null.
<!-- SMARTVALVE_EMPIRICAL_FINAL:CONCLUSION:END -->

## Data availability

Paderborn bearing data are available from the
[Paderborn Bearing Data Center](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter)
under its academic non-commercial licence. HUST Bearing v3 is available from Mendeley Data under
CC BY 4.0 (DOI `10.17632/cbv7jyx4p9.3`). Raw signals are not redistributed. The acquisition
manifests record official URLs, byte counts, archive/member names, and SHA-256 digests.
Use of data-derived artifacts remains subject to each source dataset licence; the repository's
Apache-2.0 software licence does not relicense them.

## Code and artifacts

Development code is maintained at
[github.com/lkcfqy/SmartValve-AI-Twin](https://github.com/lkcfqy/SmartValve-AI-Twin). The exact
submission commit, immutable artifact manifest, and archival release identifier must be created
after author approval; the present uncommitted working tree is not represented as a public archive.
Every reported run already retains its expanded command, environment, source fingerprint, input
and output hashes, stdout, stderr, and exit status locally.

## CRediT authorship contribution statement

**Author action required:** list every human author and only the CRediT roles that each author
actually performed; reconcile this statement with author order and the journal submission form.

## Funding

**Author action required:** identify every grant, institution, and grant number and describe the
funder's role, or provide the authors' verified no-specific-funding statement.

## Declaration of competing interest

**Author action required:** provide the declaration approved by every human author; do not infer a
no-conflict statement from the repository or experiment record.

## Declaration of generative AI and AI-assisted technologies in the manuscript preparation process

During the preparation of this work, the authors used OpenAI Codex in order to assist
with software implementation, test construction, experiment orchestration, documentation, and
language editing. After using this tool, the authors must review and edit the content as needed and
take full responsibility for the content of the published article. No generative-AI output is
listed as an author, and the manuscript figures are deterministically rendered from validated
numerical artifacts rather than generated images.
