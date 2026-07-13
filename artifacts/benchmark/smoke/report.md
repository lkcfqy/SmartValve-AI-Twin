# ValveDNA grouped benchmark report

Model: `valvedna-rules-0.3.0`
Profile: `smoke`

## Protocol

- 6 configured states × 3 severity levels × 3 load groups × 3 seeds = **162 parameterized runs**.
- Unique observable traces: **99**; redundant zero-effect parameterizations: **63**.
- Development runs: 108.
- Grouped holdout/challenge runs: 54.
- First 67% of ordered load-factor groups are development; the remaining group is a smoke-test holdout.
- Ground-truth fault names are used only by this scorer, never by `diagnose()`.

## Holdout results

- Macro F1, counting rejection as error: **1.000**
- Overall accuracy: **1.000**
- Accepted-only accuracy: **1.000**
- Normal false-positive rate: **0.000**
- In-distribution rejection rate: **0.000**
- Out-of-spec voltage rejection recall: **1.000**
- Diagnostic latency p50 / p95 / max: **12.06 / 13.67 / 16.70 ms**

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| normal | 1.000 | 1.000 | 1.000 | 24 |
| friction | 1.000 | 1.000 | 1.000 | 6 |
| stiction | 1.000 | 1.000 | 1.000 | 6 |
| obstruction | 1.000 | 1.000 | 1.000 | 6 |
| actuator_degradation | 1.000 | 1.000 | 1.000 | 6 |
| sensor_drift | 1.000 | 1.000 | 1.000 | 6 |

## Severity monotonicity

Spearman correlation between severity and degradation score (`100 - health`), averaged across load/seed groups:

- `friction`: 1.0
- `stiction`: 1.0
- `obstruction`: 1.0
- `actuator_degradation`: 1.0
- `sensor_drift`: 1.0

## Claim boundary

Simulation benchmark only. Scores do not estimate accuracy on a Weilong valve or any unseen physical product.
