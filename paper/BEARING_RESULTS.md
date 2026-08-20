# Results for the protocol-centric bearing study

> **Validated-result draft.** Paderborn fusion, vibration, motor-current, and combined sensor
> artifacts, and the HUST primary and equal-source-volume artifacts, have passed independent
> no-refit recomputation. The raw-architecture section remains explicitly held until its validator
> passes. This file is not submission-ready while that hold remains.

## Paderborn classical falsification and identity diagnostic

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

## Paderborn neural protocol contrast

### Fusion features

All nine methods were near the ceiling under measurement-random access but performed substantially
worse when both identity and setting were unseen. The complete pooled macro-F1 panel is:

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

### Vibration features

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

### Motor current and paired sensor attribution

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

Absolute crossed performance gave a different sensor conclusion. Vibration exceeded fusion for
all nine methods by 0.123507--0.181672; eight of nine paired intervals excluded zero. Vibration
also exceeded motor current for every method by 0.109507--0.162847, with five intervals excluding
zero. Motor current exceeded fusion by only 0.001380--0.051846 and none of those intervals excluded
zero. MatchDG was the crossed leader for all three views. These results show that fusion's near-
ceiling random scores do not imply better simultaneous unseen-identity-and-setting performance.
They do not identify which signal feature a classifier causally uses.

### Raw-vibration architecture sensitivity

**Submission hold:** the separately sealed Knap-style raw-1D, log-FFT, and log-STFT sensitivity has
entered its frozen 270-fit, from-scratch EXP-456R1 recovery execution after EXP-456 was externally
interrupted and excluded. No intermediate performance outcome is inspected. It is a retrospective
two-protocol falsification of compact-representation dependence, not an additional confirmatory
family. Its complete three-architecture result will be reported only after EXP-457 independent
no-refit validation.

## Sealed HUST external replication

The one-shot HUST run completed all 1,260 frozen fits, 81,000 seed-window predictions, 1,620
recording-level method/protocol predictions, 5,000 physical-bearing bootstrap draws, and every
expected secondary artifact. The independent validator refit no model and reproduced probabilities
exactly, with maximum aggregate, rank, and bootstrap numeric differences below
5e-13. All 45 official input files and the 450-row feature topology retained their locked hashes.

### Performance and protocol-gap replication

All methods achieved macro F1 1.000000 under both recording-random and load-holdout access. Under
matched-specification holdout, eight methods scored 0.797980 and DANN scored 0.741591. Under the
simultaneous crossed protocol, pooled recording macro F1 was 0.746795--0.773970:

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

### Rank endpoint and ceiling limitation

The frozen rank-instability rule mechanically passed because the maximum average-rank movement was
four positions. However, recording-random and load-holdout performance was exactly 1.0 for all nine
methods, giving every method average rank 5 and making Kendall tau undefined rather than negative.
The observed four-position movement is therefore a consequence of a complete ceiling tie followed
by small crossed differences; it is not an external replication of Paderborn's directional winner
reversal. Matched-specification/crossed Kendall tau was 0.632456 for pooled macro F1 and 0.442326
for mean-cell macro F1. The honest conclusion is asymmetric: HUST strongly replicates the protocol
gap, while its frozen rank rule passes in a scientifically weak, ceiling-limited form.

### Equal-source-volume access control

The outcome-blind auxiliary run completed 675 frozen fits. It used the same target recordings and
exactly 24 source recordings per fold in both arms, with identical class balance, all load/group
support, and matched 120 nuisance/240 fault pair budgets. Every method achieved macro F1 1.000000
under equal-volume shared access, compared with 0.746795--0.773970 under strict crossed access:

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

### Post-hoc physical-unit influence

The no-refit audit retained all 18 method-by-comparison cells, 270 leave-one-bearing effects, and
90 class-balanced leave-one-specification-group effects. Every cell remained positive under both
deletion schemes. Minimum deleted-sample effects were 0.174546 for bearing deletion and 0.112234
for group deletion; maximum absolute changes from the corresponding full-cohort effects were
0.051485 and 0.113796. Supplementary Table S4 reports every summary cell. These are post-hoc
sensitivity diagnostics, not confidence intervals or new independent physical units.

The independent validator refit no model and reproduced all prediction, aggregation, rank,
bootstrap, confusion, and diagnostic artifacts with maximum numeric difference below 5e-13. The
first validator invocation is retained as a failed audit: exact Python dictionary equality treated
two undefined Kendall correlations (`NaN`) as unequal. Version 0.1.1 changed only the validator to
recognize `NaN`-to-`NaN` equivalence and allow at most 1e-12 serialization drift; the successful
recomputation had zero numeric difference in the findings themselves.

## Cross-dataset synthesis pending raw-architecture validation

The validated evidence shows a large random/crossed protocol gap on both Paderborn and HUST with
physical-bearing interval lower limits above zero for all 36 method-by-system/sensor primary
contrasts: 27 across the three Paderborn sensor views and nine on HUST. Paderborn demonstrates
leader instability under all three sensor views and shows that vibration is materially stronger
than fusion under crossed access despite fusion's higher random scores. HUST does not provide
comparable rank discrimination because its easy protocols saturate. The equal-source-volume
falsification excludes source-record count as a sufficient explanation for the HUST effect. The
remaining empirical hold is the separately sealed raw/FFT/STFT analysis, which determines whether
the protocol-gap conclusion survives representations outside the compact statistic family.
