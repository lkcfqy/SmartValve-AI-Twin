# Paderborn prospective evaluation protocol — frozen v0.1

- Frozen: 2026-08-18
- Status: **frozen v0.1; execution is authorized only through the final prospective seal**
- Access state: metadata and archive bytes only; archive contents unopened
- Dataset role: D2 one-shot prospective validation
- Locked split artifact: EXP-311, SHA-256
  `b5ff36988d70ccff22bfccc8b7108d1ad778616a4b5ebf79ffa9e3c2c278f7e7`
- Locked quarantine-safe model-fold artifact: EXP-314, SHA-256
  `35cbbdedd23ba688a051b2d453e75f33ea5966481966b3780c4d9194db989422`
- Locked bearing-cluster bootstrap validation: EXP-315B, source SHA-256
  `bb61b60f0e2ddb7828bc553b27993e13defba1b45b78f4605c70cf5636efab93`
- Locked D2-to-development pair-topology equivalence test: EXP-353, source SHA-256
  `a65647e3127ced33f0f28239aee051d2565f38c4eda25e517d3d37600f3d8a5d`, stdout SHA-256
  `c4b808d34f4db00b333696dec1f3a43a2887d8bfe0cb7af07a3cb98ff43a7830`
- Locked six-test Holm and multi-dataset gate validation: EXP-349, source SHA-256
  `359708ef6a318da401de4a3af603ebab9601e07542f4760fc6f29ea432191ef1`
- Locked value-blind single-MAT structure probe: EXP-357/358, parser SHA-256
  `6581607f41ead0a769b80ee42fb5e71d41f205eba830ff1b2078299d1839b424`
- Locked local RAR reader: EXP-359C, Ubuntu package SHA-256
  `3d05dd213babf0b8b9082a9a7d8663d35d85449b95b8593a4acb52598759e9a6`, binary SHA-256
  `c02de05961b3d6f2a6309b4c40faaaad7891b1a44acdf0f57b882cf2b3612c26`
- Locked isolated RAR-fixture validation: EXP-361, artifact SHA-256
  `b97e0b95c2219c7b2ae38b14a784c9bea215f35232ddcd31e87087041afef0ff`, validator SHA-256
  `de7d4127b1053069eb4e18de8cdb9cd3c2c0a4b808a19bf6a771b7d3f43a88bc`

This document fixes all analysis decisions before any D2 archive member is listed, extracted or
opened. The 32 archive byte streams total 5,357,708,539 bytes and remain under the original
`archive_contents_opened=false` lock. This document alone is not sufficient to access them: the
31-role prospective seal must validate exact paths, byte sizes, SHA-256 values, configurations,
statistics, attestations and the full execution-source tree first.

## Frozen development evidence and activation boundary

The following completed D0/D1 artifacts are immutable inputs to D2:

- EXP-330 PIRL v0.2 metrics SHA-256
  `90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7` and predictions SHA-256
  `a32e0b8bfa7d8a522fa7e26bb26e2ac6f4113d32e5a3589f2b5c106e6f69ed22`;
- EXP-338 outcome-blind DG manifest SHA-256
  `79e68f95e9a5d88921fa79c1d50f34aa84db5c156a5e6c5ba516520c97faa862`;
- EXP-340 strong-baseline metrics SHA-256
  `7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b`, predictions SHA-256
  `7691980fbd47a209d79629c65bb3490ffc866645eec48f4c07509535fdfbe2d6` and independent
  validation SHA-256 `f24815fac5af7fb1409a223670ebb96eace55f1f962b086689c48caf81bae031`;
- EXP-342 source-OOF selective metrics SHA-256
  `4caa1e4bb2a07b98be6af2752a0b310f751b8bd0f7fda34b03578ebfbd9983e6`, decisions SHA-256
  `e49b97f1f63c3d754d1f970a17ba0f9b797cc2841d65e4ef3117b0d54aa99649` and independent
  validation SHA-256 `e7ee4d41688d5195478b1c609eaf684156f45c3a3aa7b9c944a13b97bdd013d5`;
- EXP-344 paired physical-block bootstrap metrics SHA-256
  `cfcaf5a16e8d30a4b52a0a6bcb6237fe3dff8b1fe416d5e8e8ac1dafe503e246`; and
- EXP-347 component-ablation metrics SHA-256
  `b7edab2bf7d1703008c93805af90627cba4a63478c468101e183cf7178d2e8a7` and independent
  validation SHA-256 `14b0eeeaf8f23f9b35c2721304252e55f242165f76f5491f380315cbfc3b9a30`.

The final-seal builder requires 31 distinct evidence roles; aliases and reuse of one path under
multiple roles are rejected. It binds the two frozen protocols, all selected configurations, five
paired seeds, the exact six-test statistical family, metadata-only expected-key manifests, both D2
artifact validators and the untouched prospective flags. Its initial authorization is limited to
one predeclared MAT key/shape/dtype probe. Bulk extraction remains conditional on a passing probe.

The extraction dependency is also prepared without weakening this boundary. A local, non-root
installation pins Ubuntu noble `unrar=1:7.0.7-1build1` by package and binary hash. EXP-361 supplied
that binary only with libarchive's 336-byte RAR test fixture pinned to immutable upstream commit
`34c4a536a88d5114cfab7ca9bff48c0d235fd53a`; CRC testing, the exact five-entry topology, both
regular-file payload hashes and a contained symbolic link all passed. The validator accepts no
Paderborn path and attests that no Paderborn member was listed, extracted or opened. Two earlier
package-layout assumption failures are retained in the ledger. This is tool readiness, not D2
execution authorization.

The 31 mandatory seal roles are:

1. `frozen_paderborn_protocol`, `source_selective_protocol`;
2. `paderborn_archive_lock`, `paderborn_lock_verification`;
3. `cranfield_normal_data`, `cranfield_lack_lubrication_data`,
   `cranfield_backlash_data`, `uci_feature_matrix`;
4. `pirl_development_metrics`, `pirl_development_predictions`, `dg_expected_manifest`,
   `dg_selection_metrics`, `dg_selection_predictions`, `dg_artifact_validation`;
5. `source_selective_metrics`, `source_selective_decisions`,
   `development_selective_bootstrap_metrics`, `pirl_ablation_metrics`;
6. `paderborn_split_manifest`, `paderborn_model_fold_manifest`;
7. `paderborn_parser_source`, `paderborn_feature_source`, `paderborn_partition_source`,
   `paderborn_bootstrap_source`, `confirmatory_family_source`; and
8. `paderborn_evaluation_source`, `paderborn_expected_manifest`,
   `paderborn_artifact_validation_source`, `paderborn_selective_source`,
   `paderborn_selective_expected_manifest`, `paderborn_selective_artifact_validation_source`.

## Official measurement contract

The official corpus contains 32 bearing identities, four settings and 20 four-second measurements
per identity/setting. Each expected measurement filename has the form
`<setting>_<bearing>_<1..20>.mat`. The vibration signal and two motor-current phases are synchronous
at 64 kHz, so each main channel must contain exactly 256,000 finite samples. Speed, torque, radial
force and temperature are support measurements and are excluded from primary classifier inputs.

The complete expected inventory is 2,560 MAT measurements. A structural mismatch stops execution;
files are never silently dropped. The frozen parser searches semantic `Name`/`Data` records,
not fragile MATLAB field positions, and requires exactly `vibration_1`, `phase_current_1` and
`phase_current_2`; synthetic MAT round-trip, changed-order, missing, duplicate, wrong-length and
wrong-root tests pass. After the final seal, it may first inspect only the MAT keys, shapes and
dtypes of lexicographically first `N15_M07_F10_K001_1.mat`. It may not print signal values, summary
statistics, spectra or labels. The structure probe no longer calls the full channel parser: it
reports semantic names/paths, stored and squeezed shapes, original dtypes and sample counts, with
`value_dependent_validation_performed=false`. A synthetic MAT containing NaN passes this structural
probe but is rejected by the later full parser, proving that finite-value scanning has not leaked
into the first access stage. A parser-only change is permitted solely to match the official nesting,
must be tested and hash-recorded before bulk extraction, and cannot alter the cohort, channels,
features, split or model.

## Cohorts and prediction unit

- Primary closed set: 29 pure-class identities—6 healthy, 12 outer-ring and 11 inner-ring.
- Compound stress set: KB23, KB24 and KB27; these 240 measurements never enter closed-set fitting,
  hyperparameter selection or accuracy.
- Prediction unit: one complete four-second measurement.
- Repeated measurements are not segmented into pseudo-independent windows in the primary result.
- Physical uncertainty unit: bearing identity, carrying all 80 measurements across four settings.

The compound set has no forced three-class ground truth. It is used only for predeclared abstention
coverage and predicted-class-distribution diagnostics; no compound accuracy or dominant-component
accuracy is reported.

## Frozen primary representation

The primary tabular representation applies the same 24 whole-trajectory time, dynamic and
normalized-frequency statistics used on D1 independently to vibration, current phase U and current
phase V, producing 72 features. Feature computation sees the entire four-second channel exactly
once and cannot use the bearing label or setting metadata. Non-finite inputs or outputs stop the
run. Standardization is fitted separately inside each source partition. No fixed-Hz or envelope
features, raw-signal model, vibration-only view or current-only view is authorized. The fused
72-feature representation is the sole D2 representation, so no post-outcome modality or feature
sensitivity can be introduced.

## Prospective double-unseen folds

EXP-311 assigns the pure identities before signal access:

| Identity fold | Healthy | Outer | Inner |
|---|---|---|---|
| 0 | K001 | KA01, KA04 | KI01, KI04 |
| 1 | K002 | KA03, KA15 | KI03, KI14 |
| 2 | K003 | KA05, KA16 | KI05, KI16 |
| 3 | K004 | KA06, KA22 | KI07, KI17 |
| 4 | K005 | KA07, KA30 | KI08, KI18 |
| 5 | K006 | KA08, KA09 | KI21 |

Cross each identity fold with each official setting to obtain 24 outer folds. For a held identity
group `I` and setting `S`:

- source: identities not in `I` **and** settings other than `S`;
- target: identities in `I` **and** setting `S`;
- quarantine: the two remaining cross arms (held identities at source settings and source
  identities at the held setting).

Thus source and target deliberately do not partition the full table. Folds 0–4 contain 1,440
source, 100 target and 780 quarantined measurements. Fold 5 contains 1,500 source, 80 target and
740 quarantined measurements. Quarantined measurements cannot contribute to normalization,
selection, early stopping, thresholds or diagnostics in that fold.

## Source intervention pairs

- Nuisance pair: same bearing and measurement index, two different source settings.
- Fault pair: same source setting and measurement index, two source identities with different pure
  labels.

Every pair coordinate is source-local. Because D2 has unequal numbers of assets per class, the
metadata-only frozen implementation takes the minimum source class count within each
setting/measurement block, constructs that many pairs for each of healthy/outer, healthy/inner and
outer/inner, and rotates sorted identities deterministically across blocks. Thus the three class
pair strata receive exactly equal weight rather than letting the larger outer/inner Cartesian
product dominate. A synthetic balanced-block test compares both nuisance and fault pairs as
undirected multisets, including multiplicity, and verifies that the D2 rule reduces exactly to the
D0/D1 all-pairs topology when there is one row per class and intervention cell. The test source hash
is locked above; all four focused tests passed in the formal EXP-353 run.

## Models and source-only selection

Configuration selection is complete and used D0/D1 only. Every network uses hidden dimension 128,
300 full-batch epochs, Adam learning rate 0.001, weight decay 0.0001, gradient clipping at 5.0 and
paired seeds 11, 23, 37, 53 and 71. The immutable common candidate identifiers are:

| Method | Candidate | Representation | Frozen method parameter |
|---|---:|---:|---|
| PIRL ratio v0.2 | `r64_l1p0_m0p5` | 64 | ratio weight 1.0, rho 0.5, margin 0.5, margin weight 1.0 |
| ERM | `erm_r64` | 64 | penalty 0 |
| CORAL | `coral_r64_w1p0` | 64 | penalty weight 1.0 |
| VREx | `vrex_r32_w0p1` | 32 | penalty weight 0.1 |
| GroupDRO | `groupdro_r64_q1p0` | 64 | group step size 1.0 |
| DANN | `dann_r64_w1p0` | 64 | coefficient 1.0 |
| LISA | `lisa_r64_w1p0` | 64 | penalty weight 1.0, alpha 2.0 |
| MatchDG | `matchdg_r64_w1p0` | 64 | penalty weight 1.0 |
| CCDG | `ccdg_r64_w1p0` | 64 | penalty weight 1.0, temperature 0.7 |

D2 receives these configurations without early stopping, hyperparameter search or model
reselection. Every primary method is P0: target features, target labels, target normal
trajectories, target statistics and target batch composition are absent from fitting and
selection. P1/P2 calibration or adaptation is outside this protocol and cannot rescue a failed P0
result.

## Frozen expected output topology

Before the final seal and without opening an archive member, two metadata-only expected-key
manifests are generated from this protocol plus locked EXP-311 and EXP-314 inputs. The closed-set
manifest requires exactly 1,080
models, 104,400 primary target predictions, 259,200 unlabeled compound predictions and 1,080 fold
metric rows. These counts equal nine methods, five seeds and 24 folds, with every pure measurement
targeted exactly once per method/seed and every compound measurement scored by every fitted model.

The selective extension is restricted to frozen PIRL and tuned ERM. Leaving one target setting out
leaves three source settings, so each outer fold has exactly three source-environment OOF
partitions. The extension therefore requires exactly:

- 720 source-OOF training models and 348,000 source-OOF predictions;
- 23,200 individual target and 57,600 individual compound predictions;
- 69,600 source, 4,640 target and 11,520 compound five-seed ensemble predictions;
- 5,760 source-frozen policies, 288 beta selections, 5,760 primary policy evaluations, 1,920
  ranking evaluations and 5,760 compound policy diagnostics; and
- 556,800 primary selection decisions and 1,382,400 compound selection decisions.

Every artifact key set, count and canonical hash is checked independently. The base validator
checks four artifacts, per-method representation dimensions, unit norms, probabilities, target
release attestations and the absence of forced compound outcomes. The selective validator checks
all 14 artifacts, finite scores and thresholds, normalized probabilities, source-only policy
attestations, exact preservation of the independently validated base predictions, reconstruction
of all ensembles from their members and the absence of compound truth, correctness or accuracy
fields.

## Metrics and selective prediction

Closed-set reports must include, for each seed and method:

- pooled prospective-target macro F1, balanced accuracy, multiclass Brier and ECE;
- macro F1 for each of four held settings and their minimum;
- all 24 identity/setting-fold macro F1 values and their minimum as a descriptive stress metric;
- per-class recall, confusion matrices and artificial-versus-real damage strata;
- representation and probability nuisance/fault responses under the balanced pair estimand;
- fit time, inference time, parameter count and peak memory; and
- full risk–coverage curves, AURC, risk at source-selected 50%, 70% and 90% coverage, accepted
  errors and coverage by setting/class/identity fold.

Selective scores are fixed as individual MSP, normalized predictive entropy, energy at temperature
1, negative maximum logit, p-norm-normalized maximum logit at p=2, robust class-support distance
and their risk envelope. The five-seed ensemble adds Jensen-Shannon disagreement and mean robust
support. The risk-envelope beta is selected only from `{0, 0.1, 0.25, 0.5, 1.0}` on each
source-OOF method/seed/fold group; thresholds target nominal source coverages 0.5, 0.7 and 0.9 while
requiring minimum source-environment coverage 0.25. Target coverage and target outcomes never alter
beta or thresholds. On the compound stress set, report only coverage, score distribution and
predicted-class distribution at these source-frozen thresholds.

## Physical-unit uncertainty and multiplicity

For D2, resample bearing identities with replacement within the three pure classes; each selected
identity carries all settings and repetitions, and identical draws are applied to every paired
method/seed. Measurements are never resampled as independent units. Use exactly 2,000 replicates
with seed 20260818 and retain the full draw/metric tensor.

The confirmatory family has two endpoints on D0, D1 and D2 (six tests): PIRL minus tuned ERM for
minimum-environment macro F1, and tuned-ERM minus PIRL for selective risk at 50%
source-selected coverage, so positive always favors PIRL. Use paired physical-unit bootstrap
effects, percentile intervals and two-sided add-one bootstrap tail diagnostics, then Holm-correct
the six p-values once. The minimum material effect is 0.01 absolute for both endpoints. A draw with
no accepted row receives selective risk one. Other baseline comparisons, 24-fold minima, modality
views and compound diagnostics are secondary and explicitly labeled exploratory. On D0/D1,
minimum-environment macro F1 is the worst held-environment fold; on D2 it is the minimum of the four
held-setting macro F1 values pooled over bearings. The D2 path validates the exact
29-bearing/2,320-measurement
contract, global row coordinates, block keys, target-fold membership, label metadata, paired
method/seed completeness and decision metadata parity; five synthetic whole-corpus tests passed
through EXP-315B. Its complete-bearing weight broadcast and retained identity draw tensor are
source-hash locked above. EXP-346 locks an exact six-row family assembler: every cell requires
effect at least 0.01, lower
percentile bound above zero and Holm-adjusted p at most 0.05. It rejects altered run parameters or
unsealed input hashes and permits neither subset selection nor a pooled replacement test. EXP-349
encodes the pre-existing internal cross-dataset gate: at least two datasets must each have a
confirmatory-positive endpoint, and no dataset may have a materially harmful endpoint whose
interval excludes zero.

## Frozen D0/D1 result interpretation

The development evidence is mixed and does not establish a broad accuracy or safety improvement.
On mean fold macro F1, PIRL reached 0.840046 on Cranfield versus the best strong baseline CORAL at
0.840899, and 0.724352 on UCI Hydraulic versus the best strong baseline MatchDG at 0.732869. PIRL is
therefore not the closed-set winner on either development dataset.

The 2,000-replicate paired physical-block bootstrap found:

| Dataset and positive-favors-PIRL contrast | Effect | 95% percentile interval | Raw two-sided p | Material and interval-positive |
|---|---:|---:|---:|---|
| Cranfield PIRL−ERM worst-fold macro F1 | 0.007785 | [-0.016053, 0.031119] | 0.410795 | no |
| Cranfield ERM−PIRL selective risk at 50% | -0.000174 | [-0.007159, 0.006241] | 1.000000 | no |
| UCI PIRL−ERM worst-fold macro F1 | 0.000860 | [0.000000, 0.002473] | 0.213893 | no |
| UCI ERM−PIRL selective risk at 50% | 0.044069 | [0.038991, 0.049302] | 0.001000 | yes |

Thus only the UCI selective-risk endpoint meets the predeclared 0.01 practical-effect and
interval rule before the six-test Holm correction. The component ablation further showed that the
ratio-only arm reproduced all 65 full PIRL model states exactly, while the margin-only arm
reproduced all 65 same-architecture ERM states exactly. The frozen full PIRL configuration is kept
to avoid post-hoc reselection, but no efficacy claim may be attributed to the inactive margin term;
the observed optimization effect is entirely attributable to the ratio penalty on D0/D1.

If D2 does not supply a protocol-defined confirmatory improvement, the manuscript must report a
prospectively validated mixed or negative result. It may still report the open pipeline, leakage
controls, compound abstention behavior and failure analysis, but it may not claim universal
robustness, safety, state of the art, causal identification or clinical/industrial deployment
readiness. Dataset-specific claims require their own material effect, positive interval and
six-test Holm-adjusted p-value; the internal multi-dataset gate is an additional claim filter, not
a substitute hypothesis test.

## No-reselection rule

After any D2 model outcome is produced, no method, feature, fold, pair rule, hyperparameter,
threshold, metric, correction family or stopping rule may change. Protocol-defined reruns are
limited to integrity failures, exact deterministic reproduction and already enumerated
sensitivities. A failed prospective gate is retained as the result; D2 cannot become development
data for a replacement method.
