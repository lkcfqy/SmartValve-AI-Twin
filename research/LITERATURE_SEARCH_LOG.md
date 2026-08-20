# Literature search log

- Search cut-off: 2026-08-19 (Asia/Shanghai)
- Scope: domain generalization, causality/invariance, target-normal access, selective prediction,
  conformal prediction, and industrial fault diagnosis under operating-condition shift.
- Source policy: paper landing pages, publisher pages, conference proceedings, arXiv records, and
  official dataset records. Search snippets from aggregators were used only to locate primary pages.
- Claim policy: absence statements mean “not found in this documented search,” never proof that no
  such paper exists.

## Query families

The web search used combinations of the following phrases:

- `industrial fault diagnosis domain generalization unseen operating conditions`
- `causal invariant fault diagnosis domain generalization bearing actuator`
- `target-free fault diagnosis operating-condition shift`
- `healthy normal reference target condition fault diagnosis adaptation`
- `Cranfield linear actuator fault diagnosis load domain generalization`
- `conformal prediction fault diagnosis abstention reject option`
- `conformal prediction covariate shift selective classification`
- exact-title and DOI follow-ups for each included paper.
- `paired intervention domain generalization representation`
- `fault sensitivity context sensitivity response ratio domain generalization`
- `source-only selective classification domain generalization risk coverage`
- `machinery fault diagnosis IRM Meta-GENE DARM operating condition`
- `CORAL VREx GroupDRO DANN LISA MatchDG source-only domain generalization baseline`
- `Conditional Contrastive Domain Generalization fault diagnosis official code CCDG`
- `maximum softmax energy Mahalanobis deep ensemble OOD uncertainty primary paper`
- `generalized eigenvalue domain invariant feature learning nuisance scatter`
- `same class different domain different class same domain generalized eigenvalue`
- `Domain-Invariant Component Analysis Scatter Component Analysis Multidomain Discriminant`
- `Invariant-Feature Subspace Recovery class conditional covariance`
- `bearing fault diagnosis unseen bearing identity unseen operating condition double unseen`
- `leakage-safe reproducible vibration fault diagnosis benchmark physical identity`
- `HUST bearing dataset official DOI license bearing types operating conditions`
- `Impact of Data Leakage in Vibration Signals Used for Bearing Fault Diagnosis`
- `Paderborn run-to-run part-to-part bearing identity leakage split`
- `Towards better benchmarking using the CWRU bearing fault dataset`
- `A Closer Look at Bearing Fault Classification Approaches bearing split`
- `Towards a more realistic evaluation of machine learning models for bearing fault diagnosis`
- `bearing-wise condition-wise leakage HUST Paderborn input representation ranking`
- `bearing fault diagnosis combined bearing operating condition holdout`
- `bearing fault diagnosis unseen bearing identities unseen operating conditions`
- exact-title/full-text review of Kaya and Jobani 2026, including their eight bearing-code
  scenarios, vibration/current/fusion comparison, limitations, and future-work statement.
- 2026-08-19 pre-submission update: `simultaneous unseen bearing identity operating condition
  holdout`, `Paderborn double unseen no target adaptation`, `crossed holdout bearing diagnosis`,
  `"bearing identity" "operating condition" holdout`, and exact-phrase variants.

## Inclusion priorities

1. The original Cranfield actuator paper and official dataset record.
2. Rigorous general DG evaluation and theoretical caution around invariance.
3. Industrial DG benchmarks and representative causal/physics-inspired methods.
4. Work that uses normal target data, because it is adjacent to SmartValve P2.
5. Selective classification and conformal work that clarifies guarantees under exchangeability or
   shift.
6. Industrial conformal fault-diagnosis papers through the search cut-off.

## High-relevance primary sources reviewed

| Key | Year | Primary source | Why reviewed |
|---|---:|---|---|
| Sun2016DeepCORAL | 2016 | [Author record](https://arxiv.org/abs/1607.01719) and [publisher DOI](https://doi.org/10.1007/978-3-319-49409-8_35) | Correlation alignment; original target-access adaptation setting distinguished from our source-only multi-environment penalty |
| Ganin2016 | 2016 | [JMLR](https://www.jmlr.org/papers/v17/15-239.html) | Gradient reversal and domain-indistinguishable features; original unlabeled-target access distinguished from our source-environment-only adaptation |
| Lessmeier2016 | 2016 | [Official benchmark paper](https://mb.uni-paderborn.de/fileadmin-mb/kat/PDF/Veroeffentlichungen/20160703_PHME16_CM_bearing.pdf) and [official dataset page](https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter) | Paderborn asset identities, pure versus compound damage, four settings, repeated-measurement unit and license |
| Hendrycks2017 | 2017 | [ICLR/OpenReview paper](https://openreview.net/references/pdf?id=Hyg_kKPOx) | Maximum-softmax baseline for misclassification/OOD detection |
| Lakshminarayanan2017 | 2017 | [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2017/hash/9ef2ed4b7fd2c810847ffa5fa85bce38-Abstract.html) | Deep-ensemble predictive uncertainty under known and shifted distributions |
| RuizCarcel2018 | 2018 | [IEEE paper](https://doi.org/10.1109/TIM.2018.2814067) and [official manuscript](https://dspace.lib.cranfield.ac.uk/bitstream/1826/13386/4/diagnosis_of_faults_in_linear_actuators-2018.pdf) | Original linear-actuator method and experimental context |
| CranfieldData2018 | 2018 | [Official dataset DOI](https://doi.org/10.17862/cranfield.rd.5097649) | Loads, motions, seeded faults, license, and provenance |
| Lee2018 | 2018 | [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2018/hash/abdeb6f575ac5c6676b747bca8d09cc2-Abstract.html) | Class-conditional feature-space Mahalanobis confidence baseline |
| Arjovsky2019 | 2019 | [arXiv](https://arxiv.org/abs/1907.02893) | Invariant Risk Minimization formulation |
| Tibshirani2019 | 2019 | [NeurIPS proceedings](https://proceedings.neurips.cc/paper_files/paper/2019/hash/8fb21ee7a2207526da55a679f0332de2-Abstract.html) | Conformal validity under covariate shift requires weighting/shift information |
| Sagawa2020 | 2020 | [ICLR/OpenReview paper](https://openreview.net/pdf?id=ryxGuJrFvS) | Worst-group objectives and the role of regularization |
| Liu2020Energy | 2020 | [NeurIPS proceedings](https://proceedings.neurips.cc/paper/2020/hash/f5496252609c43eb8a3d147ab9b9c006-Abstract.html) | Logit-energy OOD score compared with softmax confidence |
| Rosenfeld2021 | 2021 | [arXiv](https://arxiv.org/abs/2010.05761) | Formal counterexamples and failure modes for IRM |
| Krueger2021 | 2021 | [ICML/PMLR](https://proceedings.mlr.press/v139/krueger21a.html) | V-REx source-risk dispersion penalty and extrapolated-domain motivation |
| Hendriks2022 | 2022 | [Publisher DOI](https://doi.org/10.1016/j.ymssp.2021.108732) | Direct CWRU precedent: different operating conditions from the same physical bearing are not an independent domain-shift test; proposes independent-bearing evaluation |
| Mahajan2021 | 2021 | [ICML/PMLR](https://proceedings.mlr.press/v139/mahajan21b.html) | Shows class-conditional domain invariance is insufficient and uses causal object matching |
| Gulrajani2021 | 2021 | [ICLR/OpenReview](https://openreview.net/forum?id=lQdXeXDoWtI) | Consistent DG evaluation and model-selection boundary |
| Koh2021 | 2021 | [PMLR](https://proceedings.mlr.press/v139/koh21a.html) | Real-world distribution shifts and standardized OOD evaluation |
| Yao2022 | 2022 | [ICML/PMLR](https://proceedings.mlr.press/v162/yao22b.html) | LISA pairs same-label/different-domain and same-domain/different-label samples |
| Ragab2022 | 2022 | [IEEE DOI](https://doi.org/10.1109/TIM.2022.3154000), [paper PDF](https://personal.ntu.edu.sg/xlli/publication/Conditional.pdf), and [authors' code](https://github.com/mohamedr002/CCDG) | CCDG class-conditional contrastive industrial DG baseline |
| Abburi2023 | 2023 | [PHM Society paper](https://papers.phmsociety.org/index.php/phmconf/article/download/3473/phmc_23_3473) | Shows bearing-wise rather than random splitting materially lowers macro F1 on CWRU/XJTU and argues for bearing-aware partitions |
| Jia2023 | 2023 | [Publisher DOI](https://doi.org/10.1016/j.ymssp.2023.110228) | Causal-factorization DG for cross-machine bearing diagnosis |
| Mo2024 | 2024 | [IEEE DOI](https://doi.org/10.1109/TCYB.2022.3223783) | Sparsity-constrained IRM with machinery-fault theory and experiments |
| Angelopoulos2024 | 2024 | [ICLR/OpenReview](https://openreview.net/forum?id=33XGfHLtZg) | Conformal control of monotone risks and its assumptions |
| Zhao2024 | 2024 | [Publisher page](https://www.sciencedirect.com/science/article/pii/S0951832024000395) and [code](https://github.com/CHAOZHAO-1/Domain-generalization-fault-diagnosis-benchmark) | Application-oriented industrial DG taxonomy and benchmark |
| Ma2024 | 2024 | [Publisher page](https://www.sciencedirect.com/science/article/pii/S0951832024005118) | Causality-inspired multi-source DG with domain-guided suppression |
| Wheat2024 | 2024 | [IEEE DOI](https://doi.org/10.1109/ACCESS.2024.3497716) and [open author PDF](https://prod-ms-be.lib.mcmaster.ca/server/api/core/bitstreams/464bbf81-0c76-4adc-9942-f07cc5a05954/content) | Directly demonstrates bearing-identity leakage: six classical pipelines, two datasets, run/day/part splits, up to 0.47 error-rate difference, and a 55-paper Paderborn split audit |
| GarciaGalindo2024 | 2024 | [PMLR](https://proceedings.mlr.press/v230/garcia-galindo24a.html) | Multiclass conformal reject option and performance estimation |
| Cattelan2024 | 2024 | [UAI/PMLR](https://proceedings.mlr.press/v244/cattelan24a.html) | Extensive post-hoc selective-classification study, including shifted data |
| Pham2024 | 2024 | [UAI/PMLR](https://proceedings.mlr.press/v244/pham24a.html) | Directional/non-stationary DG theory makes interpolation versus extrapolation explicit |
| Azari2025 | 2025 | [Open manuscript](https://www.diva-portal.org/smash/get/diva2%3A1909391/FULLTEXT01.pdf) | Digital-twin augmentation plus DG and runtime adaptation |
| Heddoub2025 | 2025 | [Publisher page](https://www.sciencedirect.com/science/article/pii/S2405896325008535) | Conformal prediction on TEP/CSTR fault diagnosis |
| Goodarzi2025 | 2025 | [Open article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12737140/) | Test-time adaptation using normal-class target data |
| Han2025 | 2025 | [arXiv](https://arxiv.org/abs/2506.17740) | Direct study of operating-condition information in fault diagnosis |
| Heddoub2026 | 2026 | [Publisher page](https://www.sciencedirect.com/science/article/pii/S0959152426000843) | Mondrian conformal open-set diagnosis on DAMADICS and TEP |
| Johansson2026 | 2026 | [Publisher page](https://www.sciencedirect.com/science/article/pii/S2666827026000034) | Shows that singleton conformal sets do not automatically inherit the nominal error rate |
| Yang2026 | 2026 | [Publisher page](https://www.sciencedirect.com/science/article/pii/S1568494626013189) | Strict target-free DG and an explicit non-formal use of “causal” |
| Vieira2026 | 2026 | [MSSP-linked arXiv v5](https://arxiv.org/html/2509.22267v5) and [publisher DOI](https://doi.org/10.1016/j.ymssp.2026.114640) | Closest current prior: bearing-wise evaluation on CWRU, Paderborn, Ottawa, and HUST; controlled fixed-training leakage tests; time/frequency/envelope sensitivity; HUST shallow/deep comparison |

## Search outcome for SmartValve

- The literature already contains many causal/physics-inspired industrial DG models, so a generic
  “causal DG network” would be crowded and compute-intensive.
- Industrial conformal fault diagnosis is no longer an empty niche. In particular, the 2026
  DAMADICS/TEP paper prevents a first-use claim for valve/process diagnosis.
- Normal-class target data are an established adaptation resource. SmartValve must therefore label
  P2 as target-condition calibration/adaptation rather than pure DG.
- No reviewed source used the exact combination of (i) an explicit P0/P1/P2 target-access ladder,
  (ii) paired nuisance/fault probability controls, (iii) physical-block uncertainty, (iv) a fixed
  classical-estimator falsification suite, and (v) a demonstrated failure of source-only conformal
  rejection on the Cranfield cross-load actuator task.
- The defensible contribution is an audit protocol and negative empirical result, not a new causal
  identification or conformal-coverage theorem.

## 2026-08-19 v0.3 novelty and benchmark audit

The post-D2 search reviewed the following additional primary sources:

| Key | Year | Primary source | Consequence for v0.3 |
|---|---:|---|---|
| Muandet2013 | 2013 | [ICML/PMLR](https://proceedings.mlr.press/v28/muandet13.html) | DICA already learns a kernel invariant transformation by reducing domain dissimilarity while preserving the input--output relation |
| Ghifary2017 | 2017 | [TPAMI record](https://pubmed.ncbi.nlm.nih.gov/28113617/) and [author manuscript](https://arxiv.org/abs/1510.04373) | SCA already trades class separability against domain mismatch and has a generalized-eigenvalue solution |
| Li2018CIDG | 2018 | [AAAI](https://ojs.aaai.org/index.php/AAAI/article/view/11682) | Class-conditional domain-invariant distributions are established prior art |
| Hu2020MDA | 2020 | [UAI/PMLR](https://proceedings.mlr.press/v115/hu20a.html) | MDA explicitly minimizes within-class cross-domain divergence while maximizing class separability and compactness; this is the closest boundary to the paired-scatter probe |
| Wang2022ISR | 2022 | [ICML/PMLR](https://proceedings.mlr.press/v162/wang22x.html) | ISR-Mean/ISR-Cov already recover invariant subspaces from class-conditional first/second moments using eigendecomposition |
| To2025DPE | 2025 | [ICML/PMLR](https://proceedings.mlr.press/v267/to25a.html) | Diverse prototypical ensembles already target subpopulation worst-group robustness; a prototype ensemble alone is not a new contribution |
| Knap2026 | 2026 | [PHM Society](https://papers.phmsociety.org/index.php/phme/article/view/4924) | Leakage-safe CWRU/Paderborn benchmarking and recording-level separation are now explicit prior art |
| Thuan2023HUST | 2023 | [Mendeley Data](https://data.mendeley.com/datasets/cbv7jyx4p9/3) and [data note](https://doi.org/10.1186/s13104-023-06400-4) | HUST Bearing v3 is a CC BY 4.0 candidate D3 with five bearing specifications and three loads |
| Wheat2024 | 2024 | [IEEE DOI](https://doi.org/10.1109/ACCESS.2024.3497716) and [open PDF](https://prod-ms-be.lib.mcmaster.ca/server/api/core/bitstreams/464bbf81-0c76-4adc-9942-f07cc5a05954/content) | The core claim that mixed physical parts inflate Paderborn performance is already explicit prior art; their KAt comparison holds each operating condition separate rather than testing a crossed unseen-part × unseen-setting intersection |
| Matania2024 | 2024 | [PHM Society](https://papers.phmsociety.org/index.php/phme/article/view/4125), DOI `10.36001/phme.2024.v8i1.4125` | Test--training leakage caused by improper example separation in condition-based maintenance is explicit prior art; the paper strengthens the prohibition on claiming discovery of the leakage problem |
| Hendriks2022 | 2022 | [Publisher DOI](https://doi.org/10.1016/j.ymssp.2021.108732) | Condition-wise CWRU evaluation can reuse the same physical bearings; independent-bearing benchmarking predates this project |
| Abburi2023 | 2023 | [Open proceedings PDF](https://papers.phmsociety.org/index.php/phmconf/article/download/3473/phmc_23_3473) | Bearing-aware split effects and macro-F1 reporting are explicit prior art |
| Vieira2026 | 2026 | [MSSP-linked arXiv v5](https://arxiv.org/html/2509.22267v5) | Directly studies bearing-wise versus condition/segment leakage, controls training-set composition, compares input representations, and already evaluates HUST v3 |
| Kaya2026 | 2026 | [Sensors](https://doi.org/10.3390/s26123829) and [Europe PMC full text](https://europepmc.org/article/MED/42356802) | Directly compares Paderborn vibration, phase current, and fusion under measurement-wise and condition-holdout validation, then separately tests unseen bearing codes; combined bearing-code × condition holdout is explicitly left as future work |
| Sun2026LeakageResistant | 2026 | [Sensors/PMC full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC13119979/) | Partition-before-windowing, guard intervals, overlap auditing, raw/log-STFT comparison, and adaptive fusion are direct leakage-resistant HUSTbearing prior art; it uses the distinct Zhao--Zio--Shen 25.6-kHz, nine-state/11-condition release and addresses temporal-neighbour rather than Hong--Thuan v3 physical specification × load access |
| Panic2027 | online 2026; volume 2027 | [RESS publisher record](https://www.sciencedirect.com/science/article/pii/S0951832026008501), DOI `10.1016/j.ress.2026.113041` | Closest broad evaluation-methodology paper: more than 600,000 CWRU/Paderborn evaluations, explicit pipeline choices, isolated speed/load/force/fault-type/severity shifts, simple baselines, relative performance drop, and collection-dependent reversals. It does not evaluate simultaneous bearing identity × setting targets with both XOR arms quarantined, physical-bearing bootstrap inference, or a signal-unopened HUST replication/equal-volume access control. |
| Alsafari2026 | 2026 | [Official CMES full text](https://www.techscience.com/CMES/v148n1/68217/html) | Direct “double domain shift” and leak-free CWRU/Paderborn benchmark under joint fault-severity × load shift; models use labelled K-shot target support, so it closes broad compound-shift priority but not target-free physical-identity × setting access |
| Mannone2026VibFM | 2026 | [PHM Society article](https://papers.phmsociety.org/index.php/phme/article/view/4912) and [open PDF](https://papers.phmsociety.org/index.php/phme/article/download/4912/2937) | Masked-spectrogram Transformer pretrained on 16 other datasets; same three-class real-damage Paderborn subset, whole four-second measurements, five bearings/class, and ten bearing-code-disjoint splits; operating settings are shared rather than crossed |

Knap et al.'s official [MIT-licensed benchmark repository](https://github.com/1Sensor/pdm-bench)
was pinned locally at commit `ca524087219fd47bb7fb51ce63563c05b34cd6ee` (commit date
2026-03-24). Its published Paderborn pipeline uses 8,192-sample windows with 50% overlap, 50 epochs,
and raw 1D-CNN, log-FFT CNN, and log-STFT CNN baselines. The paper reports separate
cross-operating-condition and cross-bearing-instance scenarios, not their simultaneous
intersection. This makes the repository a lawful, stronger architecture reference for a separately
sealed retrospective raw-signal sensitivity; any adaptation must retain attribution and cannot be
presented as an exact reproduction of Knap's source--target scenarios.

### Decision from the overlap check

The provisional paired-intervention generalized eigenfilter is **not** advanced as a novel method.
Its exact pair estimator is useful as a controlled, source-only diagnostic baseline, but the core
Rayleigh/scatter/invariant-subspace idea is already occupied by DICA, SCA, MDA, classical Fisher
analysis, and ISR. EXP-430 therefore names it `paired_scatter`, labels every target comparison
retrospective, and prohibits confirmatory use.

The benchmark/audit route is also not novelty-free. Hendriks et al., Abburi et al., Knap et al., and
Wheat et al. establish the independent-bearing split problem from several angles. Kaya et al. also
compare vibration, phase current, and their fusion on a Paderborn subset under measurement-wise,
condition-holdout, and a separate bearing-code-disjoint stress test; the paper explicitly reserves
combined bearing-code and operating-condition holdout for future work. Vieira et al. is
the closest current work: it evaluates four public datasets including Paderborn and HUST, constructs
bearing-wise splits, holds the trained model fixed in a controlled leakage test, and shows that
invalid access can also change conclusions about time/frequency/envelope input representations.
SmartValve therefore cannot claim to discover bearing-identity leakage, establish the need for
part-separated evaluation, be the first Paderborn or HUST leakage-safe benchmark, or be the first to
show that leakage interacts with representation choice. The remaining defensible gap must be stated
more narrowly:

1. simultaneous unseen physical identity **and** unseen operating setting, with both XOR cross-arms
   quarantined rather than reused for fitting or selection;
2. an access-explicit P0/P1/P2 contract and source-only selection audit;
3. physical-unit selective risk, group coverage, effective accuracy, and multiplicity;
4. cross-system replication spanning actuator, hydraulic-cycle, and bearing measurements; and
5. a protocol-prospective, signal-unopened test of whether the two-axis conclusions and rankings
   survive HUST D3, with prior HUST outcome exposure disclosed; and
6. a Paderborn multi-sensor attribution audit (vibration versus motor current versus fusion) inside
   the same four-protocol factorial design. This no longer stands alone as a novelty claim because
   Kaya et al. already compare these sensor families; the distinction is the crossed access audit,
   physical-bearing inference, and nine-method ranking analysis.

EXP-433--435 now add retrospective evidence for item 1 and the ranking component of item 5:
the nine fixed neural methods occupy a narrow ceiling range under measurement-random access but a
low-performance range under the crossed protocol, with negative Kendall rank agreement and
opposite 1st/9th positions for CCDG and MatchDG. This extends Wheat et al.'s classical split-gap
finding to controlled DG-method ranking and a simultaneous second unseen axis; it does not replace
the need for D3 replication.

This is a candidate evaluation contribution, not yet a top-tier-ready result. A claim that the
crossed quarantine protocol is unprecedented remains prohibited; the search establishes only that
the exact combination was not found in the documented query set. Kaya et al.'s explicit future-work
statement is positive evidence for the gap but is not a field-wide priority proof. Because Vieira et al. already
report HUST bearing-wise outcomes, D3 is not literature-outcome-blind even though the MAT signals
and the proposed factorial endpoint remain unopened.

A 2026 Sensors search also found Sun et al.'s explicitly leakage-resistant HUSTbearing study. It
closes any remaining claim around first partition-before-windowing, guard-interval auditing,
raw/STFT leakage sensitivity, or HUST fusion. Because that paper uses a different HUSTbearing
release and controls temporal-neighbour overlap rather than physical specimen and load access, it is
adjacent rather than identical to the sealed D3 estimand. The manuscript must name both datasets
and sampling rates to prevent readers from conflating them.

The same update found Alsafari and Yafoz's July 2026 leak-free few-shot benchmark under joint fault
severity and load shift. This prohibits describing the present work as the first compound or double
domain-shift bearing study. The remaining distinction is narrower: the target factor is a physical
identity-by-setting intersection; neither labelled target support nor either one-axis cross-arm is
available; and nine frozen source-only methods are compared for rank as well as score stability.

Mannone et al.'s July 2026 VibFM paper is the strongest representation-level Paderborn overlap found
in the update. It already combines non-Paderborn self-supervised pretraining, whole-record
spectrograms, five physical bearings per class, and ten bearing-disjoint Paderborn splits. This
eliminates any novelty claim around foundation-model transfer or whole-record leakage resistance.
It does not withhold an operating setting or quarantine either identity/setting cross-arm. Its
availability also raises the manuscript bar: compact engineered features must be justified as a
controlled, reproducible low-compute probe, and representation dependence remains an explicit
limitation unless a frozen VibFM/raw sensitivity can be executed lawfully.

The official [VibFM repository](https://github.com/SFZ-Uni-Stuttgart/VibFM) was inspected on
2026-08-19. It exposes source and the Paderborn transfer workflow, but explicitly excludes trained
checkpoints and says checkpoint instructions will accompany a later model-release package. It also
states that no open-source license has been selected, so repository code currently has no reuse
grant. There are no releases. Consequently, SmartValve must not copy or adapt this implementation,
and a frozen VibFM baseline is not presently reproducible without obtaining both the authors'
checkpoint and permission. This is recorded as an external availability constraint, not evidence
against the baseline. A clean-room raw/STFT sensitivity based only on published methods remains
possible if it is separately specified and labelled retrospective.

## Frozen neural-baseline provenance boundary

The eight-method comparison is mechanism-stratified: tuned ERM; source-moment alignment (CORAL);
source-risk dispersion (V-REx); worst-source reweighting (Group DRO); source-environment
adversarial confusion (DANN); selective same-label cross-domain interpolation (LISA); audited
cross-context matching (MatchDG); and industrial class-conditional contrast (CCDG). Original DANN
and Deep CORAL are target-access domain-adaptation methods, so the SmartValve variants are explicitly
source-only adaptations. SmartValve's LISA uses the same-label/different-domain branch only, its
MatchDG uses known physical pair metadata instead of object-match discovery, and its CCDG follows
the authors' public feature-level implementation semantics. The shared backbone, preprocessing,
nested source-only model selection, seed set, and stopping rules make these controlled comparators;
they are not byte-for-byte reproductions of the original models.

## Closest-method boundary for the multi-rig extension

| Candidate element | Closest reviewed work | What cannot be claimed | Remaining testable gap |
|---|---|---|---|
| Same-label cross-context contraction | MatchDG and LISA | Object/domain matching or conditional contrastive learning is not new | Use *known physical intervention blocks* to measure and optimize context response relative to fault response, rather than assuming marginal invariance |
| Fault-class separation | supervised contrastive and distance-aware risk minimization families | Prototype or instance-distance losses are crowded | Couple separation to a dimensionless paired response ratio and audit the same ratio in probability space |
| Source-only model selection | DomainBed and mixup-guided DG selection | Target-free validation is not new | Freeze leave-one-physical-environment selection and show whether it predicts prospective D2 ranking |
| Abstention | conformal risk control and post-hoc confidence estimators | No distribution-free target guarantee is available after an arbitrary unseen shift | Treat the source-only rejector as a stress-tested risk envelope; report accepted errors and risk-coverage without a false coverage theorem |
| Industrial evaluation | Zhao et al. benchmark, SCIRM, Meta-GENE, causal industrial DG | Another accuracy-only bearing benchmark is not enough | Explicit P0/P1/P2 access cards, physical-block intervals, context/fault controls, independent component identities and a sealed prospective run |

The tested method family is therefore an **intervention response-ratio representation plus a
source-only risk envelope**. D2 is now observed. Only UCI selective risk was positive in the frozen
six-test family, neither Paderborn endpoint confirmed, and the multi-dataset gate failed. The method
must be positioned as a falsified broad candidate inside an evaluation audit, not as the paper's
validated algorithmic contribution.

## CCDG implementation audit

The primary paper describes class-conditional contrast on classifier scores, whereas the paper
authors' public `ERM_Contrastive` implementation applies the loss to learned features with class
labels and fixed temperature 0.7 (repository HEAD inspected at
`de2e7a0600fc44aeefd36e56ccb311257b346d40`). The later Zhao benchmark, inspected at
`370fca37e9323c79384dd1f14d8aac358f4cd359`, contains a materially different port:
its training call passes domain labels and adds a logistic loss-weight schedule. SmartValve follows
the paper authors' public implementation semantics (feature vectors, class labels, temperature
0.7, no Zhao schedule) while retaining the shared SmartValve backbone and source-only model
selection. This is an adaptation, not a byte-for-byte reproduction of the original raw-signal
architecture, and must be described that way in tables and captions.

## Required update before submission

Repeat the exact-title/DOI and citation-forward searches immediately before submission. The field
is moving quickly, and 2026 online-first articles already overlap both target-free causal DG and
conformal fault diagnosis.

### 2026-08-19 pre-submission query update

The exact-axis update recovered the already integrated Vieira, Kaya, Knap, Alsafari, Panić, and
Mannone papers. It also recovered a July 2026 PadéNet study on simultaneous load-torque and radial-
force variation and several condition-transfer or leave-one-bearing-out studies. Those additional
papers either use unlabeled target-domain adaptation, vary operating variables without withholding
physical identity, or withhold identity without simultaneously withholding setting. None of the
primary pages reviewed in this update exposed the same target-free physical-identity × setting
intersection with both XOR arms quarantined. This is an absence in the documented query set, not a
priority proof. The manuscript therefore retains its narrow factorial-access contribution and its
explicit prohibition on “first double-domain-shift,” “first leakage-safe,” or “first bearing-wise”
claims.

Vieira et al.'s MSSP article became publisher-visible on 2026-08-15, four days before this update.
Its final DOI, four-dataset scope, bearing-wise split, controlled leakage tests, and representation
sensitivity were rechecked against the publisher page rather than inferred from the earlier arXiv
record. No change to the closest-work ordering was warranted: Vieira remains the closest leakage-
evaluation paper; Kaya remains the closest Paderborn sensor/one-axis-holdout paper; Knap remains the
closest raw-architecture benchmark; and Panić remains the closest broad protocol-methodology paper.

The same update checked Matania et al.'s official PHM Society record and the July 2026 Zenodo
software artifact *Leakage-controlled, compute-matched audit of generative augmentation for
imbalanced bearing fault diagnosis* (DOI `10.5281/zenodo.21285414`). Matania et al. is now cited in
the manuscript because it directly establishes the general condition-maintenance leakage warning.
The Zenodo deposit is recorded as adjacent, non-peer-reviewed software evidence: it preregisters a
random-segment versus condition-and-instance-held-out augmentation audit across CWRU, Paderborn,
and XJTU-SY, but studies imbalance/generative augmentation rather than the present crossed
identity-by-setting estimand. It narrows broad reproducibility rhetoric but does not change the
closest-work ordering or justify a priority claim.

### Post-execution status correction

Earlier entries in this append-only log describe HUST D3 as future or unopened because they were
written before signal access. EXP-445/447 subsequently completed the sealed run and independent
no-refit validation: the predeclared score-gap rule passed for 9/9 methods, but HUST's accessible
protocols saturated and did not directionally reproduce the Paderborn winner reversal. EXP-449/450B
then retained 9/9 positive intervals with identical targets and 24 source recordings per arm. Those
results replace the earlier future tense for current manuscript positioning without rewriting the
historical search decisions.

### 2026-08-19 final exact-axis addendum

The final query pass used the combinations `bearing identity operating condition train test split`,
`bearing-wise operating-condition Paderborn`, `simultaneous bearing operating condition holdout`,
`HUST Bearing load split bearing identity`, and `Paderborn bearing-disjoint FFT STFT`. Searches were
restricted in interpretation to primary publisher pages, proceedings papers, or author preprints.
Four newly surfaced records were screened against the frozen target-free physical-identity ×
setting intersection:

| Record | Primary source checked | Protocol relevance | Decision |
|---|---|---|---|
| Li and Zhang, *A Lightweight Multi-Scale Frequency-Aware Network for Noise-Robust Rolling Bearing Fault Diagnosis* | [Research Square v1](https://doi.org/10.21203/rs.3.rs-10393437/v1), posted 2026-07-24 | Paderborn real-damage subset, grouped recordings, bearing-disjoint evaluation, STFT, and a compact model; no simultaneous unseen identity × setting intersection or XOR quarantine was reported | Added as adjacent non-peer-reviewed raw/STFT and bearing-disjoint prior art; no change to closest-work ordering |
| Spirto et al., *Rolling Bearing Fault Detection Using Symmetrized Dot Pattern Indices and Feedforward Neural Network* | [Structural Health Monitoring publisher page](https://doi.org/10.1177/14759217261441867), online 2026-05-22 | Hong--Thuan HUST Bearing load transfer with nominal specifications 6205--6208 represented on both training/validation and test sides | Added as direct single-axis HUST v3 load-transfer prior art; it does not test unseen specification × unseen load |
| Wu et al., *CBiHCL: A Collaborative Bi-Stream Hierarchical Contrastive Learning for Fault Diagnosis under Unseen Working Conditions* | [Information Sciences publisher page](https://www.sciencedirect.com/science/article/pii/S0020025526002604) | Cross-condition DG on Paderborn; search-accessible protocol text did not expose simultaneous physical-identity quarantine | Screened as method-level cross-condition work, not a closer access audit |
| Neupane et al., *Multi-Sensor Anomaly Detection Using Scalograms and Kurtograms Fusion on the Paderborn University Dataset* | [Mechanical Systems and Signal Processing publisher page](https://www.sciencedirect.com/science/article/pii/S0888327026004905) | Multi-sensor Paderborn anomaly detection with vibration, current, and torque; no search-accessible evidence of the frozen crossed split | Screened as sensor/representation adjacency; Kaya remains the closer access-protocol comparator |

No reviewed primary record in this addendum combined target-free unseen physical identity and unseen
setting on the same target cells while excluding both identity-only and setting-only cross-arms.
This remains a documented search outcome, not a priority proof. The manuscript now explicitly cites
Li--Zhang and Spirto because they close two residual single-axis claims: lightweight
bearing-disjoint Paderborn STFT and Hong--Thuan HUST load transfer, respectively.

### 2026-08-19 citation-context spot audit and PI-FSL screen

A second primary-source pass checked the highest-risk recent-work sentences in the frozen bearing
manuscript rather than relying only on DOI metadata or titles:

- Panić et al.'s official RESS record states more than 600,000 CWRU/Paderborn evaluations, an
  explicit task-focused pipeline, factor-specific shifts, and collection-dependent reversals of
  optimal choices. The manuscript's “more than 600,000” and broad protocol-methodology statements
  are supported without expansion.
- Vieira et al.'s author v5 record names CWRU, Paderborn, Ottawa, and HUST; fixes trained models for
  controlled leaked-versus-unseen-bearing test exposure; compares shallow and deep methods; and
  reports dataset-dependent representation/model conclusions. The manuscript's four-dataset,
  bearing-wise, fixed-model leakage-test, and representation-sensitivity boundary is supported.
- Kaya and Jobani's open full text separately evaluates measurement-wise, condition-holdout, and
  bearing-code-disjoint protocols with vibration, phase current, and fusion. Its limitations section
  explicitly leaves a combined bearing-code and operating-condition holdout for future work. The
  manuscript's statement that the axes were evaluated separately is therefore supported.
- Knap et al.'s official PHM paper and pinned public repository define six fixed source--target
  scenarios, recording-level separation, and separate Paderborn operating-condition and bearing-
  instance tasks with raw 1D, FFT, and STFT configurations. They do not expose the present
  simultaneous identity-by-setting target or its two XOR-arm quarantine.

The same pass screened Wan et al., *PI-FSL: Physics-Informed Few-Shot Domain Adaptation for Robust
Cross-Domain Condition Monitoring* ([Technologies 2026, 14, 167](https://doi.org/10.3390/technologies14030167)).
Its combined machine--operation scenario is on the Bosch tool-wear benchmark and uses labelled
few-shot target support. Its bearing support suite uses single-axis HUST-CN frequency, HUST-VN
operating-condition, and Paderborn operating-condition transfers under a two-way five-shot protocol.
It is relevant compound-shift/adaptation adjacency, but it does not test a target-free bearing-
identity × operating-setting intersection or quarantine the two partial-access arms. Because the
frozen manuscript already disclaims priority for compound shifts and cites a closer labelled-target
bearing benchmark, PI-FSL does not change the closest-work ordering and no manuscript edit was made.

This spot audit reduces citation-context risk but does not replace final author-by-author reading of
every cited source, nor the required last-day citation-forward search.
