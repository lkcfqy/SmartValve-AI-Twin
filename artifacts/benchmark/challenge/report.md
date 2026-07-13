# ValveDNA grouped benchmark report

Model: `valvedna-rules-0.3.0`
Profile: `challenge`

## Protocol

- 6 configured states × 5 severity levels × 5 load groups × 10 seeds = **1500 parameterized runs**.
- Unique observable traces: **1050**; redundant zero-effect parameterizations: **450**.
- Development runs: 0.
- Grouped holdout/challenge runs: 1500.
- Locked challenge created after version 0.3 rules were frozen. All exact load and seed groups differ from the 3000-run development/regression matrix.
- Ground-truth fault names are used only by this scorer, never by `diagnose()`.

## Holdout results

- Macro F1, counting rejection as error: **0.874**
- Overall accuracy: **0.877**
- Accepted-only accuracy: **0.877**
- Normal false-positive rate: **0.000**
- In-distribution rejection rate: **0.000**
- Out-of-spec voltage rejection recall: **1.000**
- Diagnostic latency p50 / p95 / max: **12.09 / 13.43 / 17.51 ms**

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| normal | 0.764 | 1.000 | 0.867 | 500 |
| friction | 0.857 | 0.600 | 0.706 | 200 |
| stiction | 1.000 | 0.950 | 0.974 | 200 |
| obstruction | 1.000 | 0.950 | 0.974 | 200 |
| actuator_degradation | 1.000 | 0.950 | 0.974 | 200 |
| sensor_drift | 0.926 | 0.630 | 0.750 | 200 |

## Severity monotonicity

Spearman correlation between severity and degradation score (`100 - health`), averaged across load/seed groups:

- `friction`: 1.0
- `stiction`: 1.0
- `obstruction`: 1.0
- `actuator_degradation`: 1.0
- `sensor_drift`: 1.0

## Claim boundary

Simulation benchmark only. Scores do not estimate accuracy on a Weilong valve or any unseen physical product.
