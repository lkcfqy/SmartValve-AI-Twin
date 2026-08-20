# Related work

> **Multi-rig status notice.** The literature synthesis began with the Cranfield audit and was
> extended for the frozen neural comparison. D2 is now complete: the broad PIRL efficacy gate
> failed, so the final positioning is prospective non-replication and evaluation reliability, not a
> new state-of-the-art architecture. EXP-433--435 add a retrospective four-protocol Paderborn
> analysis. The signal-unopened HUST replication and equal-volume control are complete; the
> protocol gap replicated, while the directional rank reversal did not because the accessible
> HUST protocols saturated. A fresh pre-submission search is still required.

## Distribution shift and falsifiable domain-generalization evaluation

Domain generalization (DG) seeks a predictor that transfers to an unseen environment without using
that environment during training. Invariant Risk Minimization (IRM) formalized one influential route:
learn a representation on which the same predictor is optimal across training environments
[@Arjovsky2019]. This idea is attractive for machinery diagnosis because operating condition can
alter sensor trajectories without changing the fault label. It does not, however, make causal
identification automatic. Rosenfeld et al. give settings in which IRM fails to recover the invariant
predictor and can fail on sufficiently different test distributions [@Rosenfeld2021].

Evaluation discipline is therefore part of the scientific contribution. DomainBed showed that
inconsistent architectures, tuning, and model-selection rules can reverse DG comparisons and that
carefully implemented empirical risk minimization is a strong baseline [@Gulrajani2021]. WILDS
similarly demonstrated substantial in-distribution versus out-of-distribution gaps on naturally
occurring shifts and standardized their evaluation [@Koh2021]. Group DRO targets worst-group
rather than average loss, but its neural-network performance depends materially on regularization
[@Sagawa2020]. These findings motivate our frozen estimator settings, strict target-access boundary,
and joint reporting of mean, worst-environment, calibration, and control metrics.

The frozen neural comparator suite covers distinct inductive biases rather than many variants of one
loss. CORAL aligns source-environment representation moments, adapting Deep CORAL's original
source--target correlation-alignment idea [@Sun2016DeepCORAL]. V-REx penalizes dispersion of risk
across source environments [@Krueger2021], while Group DRO directly reweights high-loss source
groups [@Sagawa2020]. DANN uses gradient reversal to suppress environment-predictive features
[@Ganin2016]. The original DANN protocol reads unlabeled target data; our comparator instead
discriminates only among source environments and never reads target rows. LISA selectively mixes
same-label examples across domains in our implementation, which is one of the two pairing branches
in the original method [@Yao2022]. MatchDG motivates matching representations for same objects
observed under different interventions; our adaptation uses pre-audited same-fault cross-context
pairs rather than learned object recovery [@Mahajan2021]. Finally, CCDG supplies a directly relevant
industrial comparator based on class-conditional contrast across operating domains [@Ragab2022].
All eight methods, including tuned ERM, share preprocessing, backbone capacity, source-only nested
selection, seed set, and stopping rule. They are controlled adaptations under one protocol, not
claims of byte-for-byte reproduction of the original architectures.

Our study is deliberately narrower than causal identification. Load is an observed environment
variable and its label-preserving changes are used as negative controls; fault-state changes are
positive controls. A lower probability response to the nuisance control than to the positive control
is evidence of a desirable ordering, but it neither identifies a structural causal model nor proves
that the classifier uses a causal mechanism.

## Industrial fault diagnosis under unseen operating conditions

The Cranfield data were collected on one linear electromechanical actuator rig under multiple loads
and motion profiles with seeded faults [@RuizCarcel2018; @CranfieldData2018]. The original study
focused on feature extraction and state classification, not a target-free leave-one-load-out DG audit.
The single-rig design is useful for controlled operating interventions but cannot establish transfer to
independent assets.

Industrial DG is now a substantial field. Zhao et al. supplied an application-oriented formulation,
benchmark code, and experiments across cross-condition and cross-machine fault-diagnosis tasks
[@Zhao2024]. Recent methods often call representations causal when they separate fault-associated
and domain-associated factors. Examples include deep causal factorization for cross-machine bearing
diagnosis [@Jia2023], domain-discriminator-guided suppression of non-causal channels
[@Ma2024], and target-free causal gating under speed/load shifts [@Yang2026]. The latter explicitly
states that “causal” is mechanism-oriented and stability-focused rather than formal graph
identification, a distinction we also adopt.

Panić et al. supply a particularly close evaluation study rather than a new DG loss
[@Panic2027]. Across more than 600,000 CWRU/Paderborn evaluations, their task-focused pipeline
varies dataset construction, representation, normalization, model, and training choices; isolates
speed, load, force, fault-type, and severity shifts; and shows that preferred choices can reverse
across collections. That work establishes systematic factor isolation, simple-baseline discipline,
and cross-collection design sensitivity as prior art. The present study instead estimates the joint
physical-access problem formed by bearing identity and setting, quarantines both one-axis XOR arms,
uses physical-bearing uncertainty, and freezes a separate HUST replication and equal-volume access
control. The distinction is an interaction/access contract, not priority over domain-shift auditing.

Digital-twin augmentation is another route. Azari et al. combine simulated multi-domain data, a DG
network, and runtime adaptation in a rotating-machinery study [@Azari2025]. This is adjacent to the
longer-term SmartValve digital-twin vision, but it requires a trustworthy simulator and validation of
the simulation-to-real gap. The present paper instead asks whether claims are already supported by
the available physical trials before adding synthetic data.

Operating-condition information can itself be diagnostically relevant or a shortcut. Han et al.
directly study how condition effects change multi-condition fault-diagnosis behavior
[@Han2025]. Our environment probe complements this question by asking how accurately load can be
decoded from each diagnostic representation under repetition-disjoint evaluation. Decodability is a
shortcut warning, not proof that the fault classifier causally relies on load.

Independent-component evaluation has a substantial lineage. Hendriks et al. show on CWRU that a
condition-wise split reuses the same physical bearings and propose an independent-bearing benchmark
[@Hendriks2022]. Abburi et al. likewise report materially lower macro F1 under bearing-aware splits
[@Abburi2023]. Wheat et al. compare six classical frequency/envelope pipelines on McMaster and
Paderborn data under run-, day-, and part-separated splits, report error-rate differences as large
as 0.47, and audit the split reporting of 55 prior Paderborn studies [@Wheat2024]. They also make the
key mechanism explicit: vibration can identify a physical part whose identity is correlated with
its fixed class, so mixing that part across train and test produces an optimistic estimate.

Knap et al. introduce a leakage-safe, recording-separated CWRU/Paderborn benchmark with common
machine- and deep-learning pipelines and six fixed source--target scenarios [@Knap2026]. Their
Paderborn scenarios treat operating condition, damage provenance, and bearing identity as separate
transfer factors. Their repeated-seed raw 1D-CNN, FFT-CNN, and STFT-CNN results make raw/spectral
architecture comparison explicit; the reported final Paderborn macro F1 is 0.537 for
cross-operating-condition and 0.326 for cross-bearing-instance transfer. This establishes
reproducible cross-domain scenario benchmarking and strong raw baselines as prior art, but it does
not provide the four access-matched views of one cohort or the simultaneous identity--setting target
with both XOR arms quarantined.

Li and Zhang's July 2026 Research Square preprint adds a lightweight, physics-guided STFT model and
a Paderborn bearing-disjoint evaluation with recording-grouped preprocessing [@LiZhang2026FSMSN].
It is non-peer-reviewed and does not report the simultaneous unseen-bearing/unseen-setting
intersection with both one-axis arms excluded. It nevertheless closes any claim that a compact
consumer-GPU STFT model or a Paderborn bearing-disjoint time--frequency test is new here.

Alsafari and Yafoz explicitly study a leak-free Paderborn/CWRU “double domain shift” in which fault
severity and motor load change together [@Alsafari2026]. Their models receive 5, 10, or 20 labelled
target support samples before evaluation. This establishes compound-shift terminology, leak-free
three-way splitting, multi-architecture comparison, and simultaneous two-factor evaluation as prior
art. Our estimand differs in both axes and access: physical component identity and operating setting
are jointly unseen, both one-factor cross-arms are unavailable, and no labelled or unlabelled target
row is used for adaptation.

Vieira et al. provide the closest current study [@Vieira2026]. They advocate strict bearing-wise
splitting on CWRU, Paderborn, Ottawa, and HUST, construct controlled tests that keep the trained
model fixed while changing test exposure, compare time-, frequency-, and envelope-domain inputs,
and show that invalid access can distort the selected representation. Their HUST appendix also
compares shallow and deep methods under bearing-wise splits. Consequently, this paper does not
claim to discover bearing-identity leakage, introduce part-separated Paderborn/HUST evaluation, or
first show that split validity interacts with input representation.

Spirto et al. apply a low-compute symmetrized-dot-pattern/FNN pipeline to the Hong--Thuan HUST
Bearing cohort and evaluate a load transfer in which the same four nominal bearing specifications
appear on both sides [@Spirto2026]. This establishes HUST v3 load-transfer evaluation as prior art,
but it does not withhold bearing specification and load simultaneously. Our HUST question is the
interaction between those access axes, with both partial-access arms quarantined, rather than load
transfer alone.

Mannone et al.'s VibFM study is another close Paderborn precedent [@Mannone2026VibFM]. A masked
spectrogram Transformer is pretrained on 16 non-Paderborn vibration corpora and transferred to the
same three-class real-damage Paderborn subset. Their downstream design keeps complete four-second
measurements intact and evaluates ten leakage-resistant bearing-code splits over five physical
bearings per class. All four operating settings remain represented within each split, and the
reported per-setting table is a breakdown of bearing-wise transfer rather than a separately unseen
setting or crossed identity-by-setting target. Thus foundation-model transfer, whole-record
spectrogram input, and rigorous bearing-level Paderborn evaluation are prior art; the remaining
distinction is the factorial access intervention and source-only method-rank comparison.

Sun et al. independently make temporal leakage a central HUSTbearing design variable
[@Sun2026LeakageResistant]. They partition continuous recordings before windowing, add guard
interval and overlap audits, and compare raw-signal and log-STFT branches in an adaptive graph-fusion
model. Their benchmark is the distinct Zhao--Zio--Shen HUSTbearing release at 25.6 kHz with nine
states and 11 operating conditions, rather than the Hong--Thuan HUST Bearing v3 cohort at 51.2 kHz
used here. More importantly, their split prevents neighbouring-window reuse inside continuous
records; it does not test a physical-specimen-by-load target with both partial-access arms
quarantined. Temporal partition-before-windowing, raw/STFT sensitivity, and leakage-resistant HUST
evaluation are therefore prior art, while the physical access factors and estimands remain
different.

Kaya and Jobani provide the closest multi-sensor Paderborn comparison [@Kaya2026]. They evaluate
vibration-only, phase-current-only, and vibration--current fusion models under measurement-wise and
operating-condition holdout validation, and add a separate eight-scenario bearing-code-disjoint
test for their two strongest temporal models. Their identity test does not simultaneously hold out
an operating condition: the paper explicitly lists combined bearing-code and operating-condition
holdout as future work. Thus, sensor-family comparison, condition holdout, and unseen-bearing
testing are all prior art; our distinction is their factorial combination with XOR quarantine,
paired physical-bearing inference, and a common nine-method DG ranking audit.

Our narrower extension changes the question from a single-axis leakage demonstration to a
factorial deployment stress test. The same records and frozen model configurations are evaluated
with shared identity/setting, unseen setting only, unseen identity only, and simultaneous unseen
identity plus setting; in the last protocol, both XOR cross-arms are quarantined. We then test rank
stability for nine controlled DG methods and use paired bearing-level resampling. Wheat et al.
evaluate each Paderborn operating condition independently. Vieira et al. treat a condition-wise
test as a deliberately leaked comparator and study representation choice within vibration, but do
not report the simultaneous unseen-identity/unseen-setting intersection with XOR quarantine, a
neural DG ranking audit, or vibration-versus-motor-current attribution inside that crossed design.
Kaya and Jobani make the sensor comparison directly, but separate their condition and identity
holdouts. These are
distinctions, not priority claims.

## Healthy target data: calibration is not target-free DG

Healthy measurements from a deployed target asset are often much easier to collect than target
faults. Goodarzi and Schütze exploit normal-class target data for test-time domain adaptation across
six condition-monitoring datasets [@Goodarzi2025]. This supports the practical relevance of target
healthy data, but also clarifies the access boundary: a method that reads a healthy target trajectory
is an adaptation or calibration method, not strict target-free DG.

Our P0/P1/P2 ladder isolates that distinction. P0 reads no target trajectory. P1 estimates a healthy
reference from source conditions only. P2 reads a different healthy repetition at the held-out
condition. Reporting P2 together with P0 without this boundary would conflate deployment regimes.
The single-actuator experiment shows that a plausible source-linear reference can be reliably
harmful, whereas its small P2 average gain over P0 is not resolved by the paired physical-block
bootstrap and comes with worse ExtraTrees Brier score. The independent UCI hydraulic audit sharpens
rather than merely repeats that result: P1 harms mean-fold macro F1 with intervals excluding zero
for all five estimator families, but the predeclared claim that P2 provides no F1 gain and worsens
Brier is supported by none of them. Target-healthy calibration is therefore a materially different
and rig-dependent regime, not an innocuous preprocessing step that can be pooled with P0.

## Selective classification and conformal prediction under shift

Selective classification trades coverage for risk by allowing abstention [@Geifman2017]. Conformal
methods can produce finite-sample prediction sets under exchangeability, and conformal risk control
extends the machinery to monotone losses [@Angelopoulos2024]. Under covariate shift, validity is not
free: weighted conformal methods require a known or accurately estimated likelihood ratio, often
using unlabeled target covariates [@Tibshirani2019].

Multiclass conformal reject-option methods can estimate performance at selected rejection levels
[@GarciaGalindo2024]. More recent analysis also cautions that accepting only singleton conformal
sets does not automatically transfer the nominal marginal set-error rate to the accepted subset
[@Johansson2026]. Our EXP-012 therefore makes no target-risk guarantee. Its calibration scores come
only from source-to-source held-load predictions; the target load may violate exchangeability.

Conformal fault diagnosis already has direct prior art. Heddoub et al. evaluate conformal fault
classification on the Tennessee Eastman Process and a continuous stirred-tank reactor
[@Heddoub2025]. Their later work combines class-conditional conformal prediction with lightweight
discriminant analysis for open-set diagnosis on DAMADICS valve-actuator and TEP data
[@Heddoub2026]. Consequently, our novelty is not the use of conformal prediction in industrial or
valve diagnosis. Our distinct result is diagnostic: source-domain conformal singleton selection
accepts every observed `trap/-40` ExtraTrees error, while an explicit load-support rule rejects that
unsupported extrapolation at the cost of also rejecting correct low-load sinusoidal trials.

## Position of this paper

This paper is a falsification-first audit rather than another high-capacity DG architecture. Its
updated contribution joins seven elements that the closest reviewed work does not evaluate
together:

1. four access-matched split protocols culminating in simultaneous unseen physical identity and
   operating setting with XOR quarantine;
2. nine fixed DG methods evaluated for both performance and rank stability on the same 24 physical
   cells;
3. an explicit target-information access ladder for healthy references;
4. negative and positive probability-response controls;
5. bearing/repetition-block bootstrap intervals rather than window-level pseudo-replication; and
6. a source-only abstention audit that reports accepted errors, effective accuracy, and
   zero-coverage folds; and
7. a sensor-family analysis of whether vibration, motor current, and their fusion create different
   protocol gaps and DG ranking distortions.

The resulting claims are intentionally asymmetric. We can show that the frozen ExtraTrees failure
is real for that estimator and not a bootstrap artifact, but the classical suite falsifies a universal
model-family claim. We can show strong load decodability, but not causal use of load. We can show a
finite-dataset coverage–risk trade-off for the hybrid gate, but not shifted-target conformal validity.
This calibrated boundary is the principal methodological contribution. The Paderborn protocol
contrast is retrospective, so its cross-dataset interpretation is bounded by the separately sealed
HUST Bearing v3 factorial replication [@Thuan2023HUST; @Hong2023HUSTData]. That replication passed
the predeclared protocol-gap rule for all nine methods, while random/load-access ceiling scores
prevented a directional rank replication; the equal-source-volume control retained the gap for all
nine methods. Vieira et al.'s published HUST bearing-wise results were already known
[@Vieira2026], so prospectiveness applies to the frozen signal access, implementation, and endpoint,
not to the literature outcome.
