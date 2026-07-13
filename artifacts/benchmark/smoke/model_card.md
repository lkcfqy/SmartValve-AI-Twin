# Model card: valvedna-rules-0.3.0

## Intended use

Transparent full-stroke valve/actuator signature screening for an industrial engineering PoC. The model compares current-versus-position signatures, motion time, stagnation, reported travel and process consistency.

## Decision outputs

- `normal`: no actionable deviation under the current evidence.
- `diagnosed`: one transparent rule matched with an evidence trail.
- `needs_review`: out-of-spec supply or an unclassified signature; do not auto-dispatch maintenance.

## Evaluation

- Profile: `smoke`.
- Operating-condition holdout macro F1: 1.000.
- Normal false-positive rate: 0.000.
- Out-of-spec voltage rejection recall: 1.000.
- p95 diagnostic latency: 13.67 ms.

## Known limitations

- Evaluation is deterministic simulation plus separately reported public-rig evidence; it is not Weilong product accuracy.
- Low-severity faults can be indistinguishable from normal measurement variation.
- Travel-to-hydraulic-loss mapping is illustrative until a Kv/Cv curve is fitted.
- Leakage and remaining useful life are not validated.
- The current rejection test covers supply-voltage scope and unclassified signatures, not every distribution shift.

## Required human oversight

Maintenance decisions require an engineer to review the source grade, operating condition, data quality, evidence variables and previous baseline. `needs_review` must never be converted to a root cause automatically.
