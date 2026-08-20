# Novelty and claim matrix

- Literature-search cutoff: 2026-08-19
- Intended article type: prospective replication, reliability, and evaluation audit
- Algorithmic novelty status: PIRL is a tested candidate, but its broad superiority hypothesis is
  not supported.
- Evidence status: D0/D1 development, sealed D2, six-test correction, retrospective Paderborn
  four-protocol/sensor artifacts, sealed HUST D3 replication, and equal-volume control are
  complete; raw-architecture sensitivity is running.

## Contribution relative to established practice

| Contribution | Established practice | What this study adds | Final strength |
|---|---|---|---|
| Dataset-level prospective validation | Random seeds and within-dataset folds are often treated as replication | Freezes the method on two rigs and opens an independent-bearing dataset only after the execution seal | Strong evaluation contribution |
| Access-explicit protocols | Target-normal data are frequently described ambiguously | Separates target-free P0, source-extrapolated P1, and target-calibrated P2; the headline neural test is strictly P0 | Strong protocol contribution |
| Strong source-only comparison | New industrial losses are often compared mainly with ERM | Uses ERM plus CORAL, VREx, GroupDRO, DANN, LISA, MatchDG, and CCDG under the same selector | Strong benchmark discipline; no new SOTA |
| Physical-unit inference | Window-level samples can inflate apparent precision | Uses complete actuator/hydraulic blocks and bearing identities, with paired 2,000-draw inference | Strong statistical contribution on the observed cohorts |
| Selective-risk family | Coverage-risk curves are often reported without multiplicity or zero-coverage groups | Freezes one selective endpoint per dataset, reports effective accuracy and zero coverage, and corrects a six-test family | Strong reliability audit |
| Component state equality | Ablations usually compare only rounded scores | Shows full=ratio-only and margin-only=ERM at the serialized model-state level | Strong negative attribution result |
| Retained structural failures | Data exceptions and validator fixes are commonly summarized informally | Retains every failed run, freezes coordinate/count reconciliation, and proves predictions/statistics unchanged | Strong artifact/audit contribution |
| PIRL algorithm | Response-ratio regularization is the proposed mechanism | Produces one positive endpoint on one dataset but fails the frozen multi-dataset gate | Insufficient for a general algorithmic novelty claim |
| Crossed physical access audit | Hendriks, Abburi, Wheat, and Vieira already establish independent-bearing evaluation; Vieira also compares condition-wise leakage and vibration representations | Holds records/configurations fixed across random, setting-only, identity-only, and simultaneous identity × setting holdout; quarantines both XOR arms | Strong retrospective extension with sealed HUST protocol-gap replication and equal-volume falsification |
| DG ranking stability | DomainBed establishes that evaluation/model selection can reverse generic DG comparisons | Measures nine industrial DG rankings on common physical cells; random/crossed pooled Kendall `tau=-0.555556` | Strong observed benchmark result, with random-ceiling caveat |
| Industrial DG benchmark scope | Zhao et al. already provide an application-oriented taxonomy, reproducible framework, and ten-dataset cross-condition/cross-machine benchmark | Tests the validity of score and model selection under a joint physical-identity × setting access intervention | Evaluation-validity extension; not a new DG taxonomy or leaderboard |
| Multi-sensor leakage attribution | Kaya and Jobani already compare Paderborn vibration, phase current, and fusion under measurement-wise, condition-holdout, and separate bearing-code-disjoint tests | Places vibration-only, motor-current-only, and fused features inside one four-protocol factorial audit, including simultaneous identity × setting quarantine and the same DG suite | Validated retrospective attribution; fusion has a larger gap and lower crossed performance than vibration, without a standalone sensor-novelty claim |
| Raw-architecture sensitivity | Knap et al. already provide leakage-safe raw, FFT, and STFT CNN baselines on Paderborn | Reuses the frozen random/crossed physical-access topology, four whole-record windows, record aggregation, and bearing-level inference | Sealed retrospective falsification in progress; interrupted EXP-456 is excluded and no claim is made until EXP-456R1/457 validate |
| Lightweight bearing-disjoint STFT | Li and Zhang already report a consumer-GPU, recording-grouped, bearing-disjoint Paderborn STFT preprint | Tests raw/FFT/STFT under the same simultaneous identity × setting access intervention rather than a bearing-only split | Adjacent non-peer-reviewed prior art; no architecture or low-compute priority claim |
| HUST load transfer | Spirto et al. already evaluate Hong--Thuan HUST Bearing across load while reusing the same nominal specifications | Separates shared-specification load access from simultaneous unseen specification × load access | Single-axis prior art; crossed interaction remains the narrow estimand |

## Supported claims

| ID | Claim | Evidence | Allowed wording |
|---|---|---|---|
| M1 | PIRL is not the best closed-set method on either development dataset | EXP-340: Cranfield CORAL 0.840899 > PIRL 0.840046; UCI MatchDG 0.732869 > PIRL 0.724352 | “Competitive on selected metrics, but not the closed-set leader” |
| M2 | The PIRL margin is observationally inactive in the frozen D0/D1 optimization | EXP-347 byte-identical state and prediction comparisons | “No independent margin contribution was observed” |
| M3 | MatchDG leads pooled Paderborn macro F1, while PIRL leads minimum-setting macro F1 descriptively | EXP-417 and Table 8 | “Rankings depend on the predeclared metric” |
| M4 | Paderborn closed-set improvement over ERM is unresolved | EXP-421B effect 0.020921, interval [-0.045959, 0.081241] | “No confirmed D2 closed-set benefit” |
| M5 | Paderborn selective risk does not confirm and its point estimate favors ERM | EXP-421B effect -0.031777, interval [-0.070919, 0.007151] | “No confirmed D2 selective benefit; adverse but unresolved point estimate” |
| M6 | UCI selective risk is the sole confirmatory-positive family member | EXP-422B Holm p=0.005997, effect 0.044069, positive interval | “One dataset-endpoint improvement within the complete six-test family” |
| M7 | The multi-dataset evidence gate fails | EXP-422B positive datasets = 1; required at least 2 | “The broad replication criterion was not met” |
| M8 | No endpoint meets the frozen material-harm definition | EXP-422B has no adverse interval excluding zero | “No statistically resolved material harm under the frozen rule,” not “proved harmless” |
| M9 | Structural reconciliation did not alter model or inferential outputs | EXP-418B, EXP-420B, EXP-421B, and EXP-422B | “Coordinate/count/version corrections only; no rerun, imputation, or endpoint change” |
| M10 | Shared-identity access severely inflates Paderborn performance under fixed models | EXP-433/434B: classical ExtraTrees 0.998389 vs 0.544720; neural ranges 0.964534--0.987148 vs 0.360074--0.403121 | “Large retrospective protocol gap on Paderborn” |
| M11 | The neural random-minus-crossed effect is physically robust in the observed cohort | EXP-434B: all nine class-stratified bearing-bootstrap intervals exclude zero | “All nine descriptive physical-bearing intervals exclude zero,” not a population-wide guarantee |
| M12 | Neural method ranking depends strongly on access protocol | EXP-434B: random/crossed Kendall `tau=-0.555556`; CCDG 1st/9th and MatchDG 9th/1st | “Rank reversal under the observed Paderborn protocols,” with explicit random-ceiling caveat |
| M13 | Identity leakage itself is established prior art | Matania et al. 2024 frame improper example separation as a recurring condition-monitoring problem; Wheat et al. 2024 compare run/day/part splits, report up to 0.47 error-rate difference, and audit 55 Paderborn studies | “We extend the audit to crossed axes and DG ranking”; never “we discovered bearing leakage” |
| M14 | EXP-434B artifacts independently reproduce | EXP-435 and explicit-no-refit EXP-456A: seed/checkpoint/import differences 0; metric/rank/bootstrap differences about 1e-12 | “Passed independent artifact recomputation without refitting” |
| M15 | Bearing-wise HUST evaluation and representation-sensitive leakage are prior art | Vieira et al. 2026 evaluate CWRU, Paderborn, Ottawa, and HUST; compare time/frequency/envelope and controlled leakage exposure | “We study a narrower crossed-axis and multi-sensor ranking question,” never “first leakage-safe HUST study” |
| M16 | Paderborn vibration/current/fusion and separate identity or condition holdouts are prior art | Kaya and Jobani 2026 compare those sensor families and report separate operating-condition and bearing-code holdouts; combined identity × condition holdout is future work | “We combine the axes in one factorial audit,” never “first multi-sensor leakage study” |
| M17 | Leakage-resistant HUSTbearing temporal splitting and raw/STFT fusion are prior art | Sun et al. 2026 partition a distinct Zhao--Zio--Shen HUSTbearing release before windowing with guard intervals and overlap auditing | “Our HUST v3 estimand is physical specification × load access,” never “first leakage-resistant HUST protocol” |
| M20 | Task-focused domain-shift pipelines and design-choice reversals are prior art | Panić et al. evaluate more than 600,000 CWRU/Paderborn configurations, isolate multiple physical shift factors, and find collection-dependent optimal choices | “We estimate a joint identity × setting access interaction with XOR quarantine and sealed HUST replication,” never “first systematic domain-shift audit” |
| M18 | Leak-free simultaneous two-factor bearing shift is prior art | Alsafari and Yafoz 2026 jointly shift fault severity and load on CWRU/Paderborn with labelled few-shot target support | “Our axes and access differ: target-free physical identity × setting with both one-axis arms quarantined,” never “first double domain shift” |
| M19 | Leakage-resistant Paderborn foundation-model transfer is prior art | Mannone et al. 2026 pretrain VibFM on 16 other datasets, retain whole four-second Paderborn measurements, and evaluate ten bearing-code-disjoint splits on five bearings per class | “Our contribution is the four-cell access factorial and rank audit,” never “first whole-record or foundation-model leakage-safe Paderborn study” |
| M21 | The protocol gap replicates on signal-unopened HUST | EXP-445/447: all nine random-minus-crossed effects positive, every interval lower limit above zero, median effect 0.226030 | “The predeclared HUST protocol-gap rule passed 9/9” |
| M22 | HUST does not reproduce Paderborn's directional winner reversal | EXP-445/447: all methods tie at 1.0 under random/load access; random/crossed Kendall tau is undefined | “Score-gap replication with a ceiling-limited, non-directional rank result” |
| M23 | Source-record count alone does not explain the HUST gap | EXP-449/450B: identical targets and 24 source recordings per arm; all nine shared-minus-crossed intervals exclude zero | “The equal-volume control falsifies source count alone,” not a causal leakage estimate |
| M24 | Paderborn sensor conclusions depend on access | EXP-451--453: all 27 sensor-by-method gap intervals have positive lower limits; fusion-minus-vibration gap intervals are positive for 9/9; vibration crossed scores exceed fusion for 9/9 | “Fusion's random advantage does not survive the strict crossed deployment estimand” |
| M25 | Complete neural sensor attribution independently reproduces | EXP-453: 250,452 ensemble rows and 12 derived artifacts recomputed without fitting; maximum difference `5.1e-13` | “Passed independent no-refit sensor recomputation” |
| M26 | Paderborn bearing-disjoint STFT evaluation is prior art | Li and Zhang 2026 use grouped recordings, unseen bearing identities, STFT inputs, and consumer-GPU training in a Research Square preprint | “Our raw sensitivity changes the physical-access topology,” never “first lightweight/bearing-disjoint STFT benchmark” |
| M27 | Hong--Thuan HUST Bearing load-transfer evaluation is prior art | Spirto et al. 2026 train/validate and test across load while retaining the same nominal bearing specifications | “Our HUST estimand jointly withholds specification and load,” never “first HUST load-transfer study” |

## Claims explicitly prohibited

- “PIRL is state of the art,” “PIRL generally outperforms ERM,” or “PIRL generalizes across rigs.”
- “The Paderborn experiment validates PIRL.”
- “Five of six tests failed” when “were null under the frozen criterion” is the accurate wording.
- Reporting only the UCI-positive endpoint without the other five family members.
- Substituting pooled Paderborn macro F1, unweighted fold risk, or compound-fault results for either
  frozen confirmatory endpoint.
- “The representation is causal” or “the loss identifies a physical mechanism.”
- “The rejector is safe,” “coverage is guaranteed under shift,” or “validated for deployment.”
- Treating model seeds, signal windows, or measurements from one bearing as independent physical
  replications.
- Omitting the unreadable KA08 record or any failed unmodified validator/bootstrap/assembler run.
- Reusing Paderborn as a fresh prospective test after changing the method in response to its result.
- “We are the first to identify bearing-identity leakage,” “the first leakage-safe Paderborn
  benchmark,” or “the first part-separated Paderborn evaluation.”
- “The crossed protocol is unprecedented”; the documented search supports only a closest-work
  distinction.
- “The first leakage-safe HUST evaluation” or “the first demonstration that leakage changes the
  best representation.”
- “The first Paderborn vibration/current/fusion leakage audit” or any claim that sensor-family
  comparison alone is novel.
- “The first partition-before-windowing, leakage-resistant HUST, raw/STFT, or HUST fusion study.”
- “The first double-domain, compound-shift, or simultaneous two-factor bearing benchmark.”
- “The first leakage-resistant Paderborn foundation-model, spectrogram, or whole-measurement study.”
- “The first lightweight or bearing-disjoint Paderborn STFT study,” or “the first Hong--Thuan HUST
  Bearing load-transfer evaluation.”
- “The first task-focused domain-shift pipeline,” “the first systematic factor audit,” or “the first
  evidence that implementation choices can reverse condition-monitoring conclusions.”
- Treating the negative random/crossed Kendall value as stable without noting that random scores
  are compressed near the ceiling.
- Calling the raw/FFT/STFT sensitivity complete before EXP-456R1 and EXP-457 validate.

## Publication implication

The artifact and evaluation contribution is substantially stronger than the algorithmic result.
The Paderborn protocol gap and DG rank reversal can anchor a serious reliability paper, but the
Hendriks--Abburi--Wheat--Vieira lineage substantially narrows novelty: identity leakage,
part-separated evaluation, HUST bearing-wise evaluation, and vibration-representation sensitivity
are not new. Top-tier viability now depends on the combination of simultaneous two-axis
quarantine, DG ranking instability, multi-sensor attribution, physical inference, and a sealed HUST
factorial replication. Paderborn is development evidence for every such post-EXP-417 claim.
