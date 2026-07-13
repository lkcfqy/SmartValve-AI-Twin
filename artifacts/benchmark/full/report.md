# ValveDNA grouped benchmark report

Model: `valvedna-rules-0.3.0`
Profile: `full`

## Protocol

- 6 configured states × 5 severity levels × 10 load groups × 10 seeds = **3000 parameterized runs**.
- Unique observable traces: **2100**; redundant zero-effect parameterizations: **900**.
- Development runs: 2100.
- Grouped holdout/challenge runs: 900.
- First 70% of ordered load-factor groups are development and the remaining groups form a grouped regression holdout. Version 0.3 was improved after reviewing the version 0.2 regression result, so this is not a pristine final test.
- Ground-truth fault names are used only by this scorer, never by `diagnose()`.

## Holdout results

- Macro F1, counting rejection as error: **0.953**
- Overall accuracy: **0.954**
- Accepted-only accuracy: **0.954**
- Normal false-positive rate: **0.000**
- In-distribution rejection rate: **0.000**
- Out-of-spec voltage rejection recall: **1.000**
- Diagnostic latency p50 / p95 / max: **12.03 / 13.78 / 19.91 ms**

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| normal | 0.906 | 1.000 | 0.951 | 300 |
| friction | 1.000 | 1.000 | 1.000 | 120 |
| stiction | 1.000 | 1.000 | 1.000 | 120 |
| obstruction | 1.000 | 1.000 | 1.000 | 120 |
| actuator_degradation | 1.000 | 0.917 | 0.957 | 120 |
| sensor_drift | 0.899 | 0.742 | 0.813 | 120 |

## Severity monotonicity

Spearman correlation between severity and degradation score (`100 - health`), averaged across load/seed groups:

- `friction`: 1.0
- `stiction`: 1.0
- `obstruction`: 1.0
- `actuator_degradation`: 1.0
- `sensor_drift`: 1.0

## Claim boundary

Simulation benchmark only. Scores do not estimate accuracy on a Weilong valve or any unseen physical product.
