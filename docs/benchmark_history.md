# Benchmark iteration history

## Protocol policy

Fault labels are passed only to the simulator and scorer. `diagnose()` receives baseline/current measurements and extracted signatures, never the hidden configured fault. Rows are not randomly split.

## v0.2 baseline — 3000-parameter grouped regression

- 6 configured states × 5 severities × 10 load groups × 10 seeds.
- 2100 development rows and 900 grouped high-load regression rows.
- Macro F1: 0.670.
- Overall accuracy: 0.757.
- Normal false-positive rate: 0.000.
- Out-of-spec voltage rejection recall: 1.000.
- P95 diagnostic latency: 15.49 ms.

The confusion matrix exposed a physically incorrect absolute rule: high-load friction and actuator degradation were frequently classified as travel obstruction because the rule asked only whether current travel reached 94%.

## v0.3 correction — same 3000-parameter grouped regression

The rule was changed to compare current maximum travel with the healthy baseline recorded under the same load. Peak-current ratio separates a hard obstruction/stall from distributed friction, and low-current travel loss supports actuator degradation.

- Macro F1: 0.953.
- Overall accuracy: 0.954.
- Normal false-positive rate: 0.000.
- Out-of-spec voltage rejection recall: 1.000.
- P95 diagnostic latency in the regenerated 0.4 software environment: 13.78 ms.

Because v0.3 was created after reading the v0.2 regression result, the 900 grouped rows are regression evidence, not a pristine final test.

## v0.3 frozen challenge — 1500 new parameterizations

After freezing v0.3, a new challenge used five different load factors (`0.72, 0.86, 1.03, 1.21, 1.43`) and seeds `100–109`. No rule was changed after reading the result.

- Macro F1: 0.874.
- Overall accuracy: 0.877.
- Normal false-positive rate: 0.000.
- Out-of-spec voltage rejection recall: 1.000.
- P95 diagnostic latency in the regenerated 0.4 software environment: 13.43 ms.
- Main misses: low-severity friction and position-sensor drift were classified as normal.

This is still S0 simulation evidence. It measures consistency across simulator operating conditions, not accuracy on a physical valve or a Weilong product.

## Observable-trace correction

The simulator artifacts now report both parameter combinations and unique observable traces.
Zero severity makes multiple configured fault names produce the same normal signal, so the full
matrix contains 2,100 unique traces across 3,000 combinations and the challenge contains 1,050
across 1,500. Historical F1 values are unchanged; the corrected language prevents duplicate
zero-effect parameterizations from being described as independent samples.

## Cranfield source-specific development benchmark

Software 0.4 adds a separate 180-trial public-actuator experiment. Motion-specific Extra Trees
models use leave-one-load-out development cross-validation with a different healthy repetition as
the matched baseline. Aggregate accuracy is 0.872 and macro F1 is 0.874. The trapezoidal -40 kgf
fold is only 0.333 accuracy. Hyperparameters were selected while observing this dataset, so the
result is development evidence rather than a locked final test or a served production model.
