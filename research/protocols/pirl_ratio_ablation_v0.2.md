# PIRL response-ratio component ablation v0.2

- Frozen: 2026-08-18, after EXP-330 and before any v0.2 ablation prediction
- Access tier: P0 source-only
- Datasets: D0 Cranfield and D1 UCI Hydraulic
- D2 state: archive contents remain unopened

Formal execution is authorized only with the UCI physical-sensor feature matrix SHA-256
`4359ce099e421cc9e55c65115d39f4a4c0463255f72f834a49d802fa6a038516`, this exact frozen
protocol, the four EXP-330 reference hashes below, and an outcome-blind expected-key manifest
generated before any ablation fit. The manifest must contain exactly 195 model keys and 67,500
target-prediction keys for the three arms, five seeds, three D0 folds and ten D1 folds. Any hash,
count or canonical key-set mismatch invalidates the run.

## Locked full method

Reuse the full-method results without refitting from
`EXP-330-PIRL-RATIO-SELECT__20260818T062351.285563Z__source-only-nonsaturating-ratio-selection-and-ev`.
The locked hashes are:

- metrics: `90bf71655ef2dbee9ab46ba2cb614f4c100d4553b6b4e94ffe5db140e21f72f7`;
- predictions: `a32e0b8bfa7d8a522fa7e26bb26e2ac6f4113d32e5a3589f2b5c106e6f69ed22`;
- tuning traces: `a2eff73fc2b84de1c551bb022c75ca4d700defeacb034a0d830d9dbb2e35724f`;
  and
- final traces: `d84aca64c937ffce91d608f8b0b2dd90eaf621785ef927404a895c84b465834d`.

The selected full configuration is `r64_l1p0_m0p5`: 64-dimensional representation, hidden
dimension 128, response-ratio weight 1.0, fault margin 0.5, margin weight 1.0, 300 epochs, AdamW
learning rate 0.001 and weight decay 0.0001. The full loss is
`CE + nuisance_response / (fault_response + 1e-4) + relu(0.5 - fault_response)`.

## Frozen arms

Every arm keeps the full method's architecture, optimizer, initialization seeds, fold topology,
epoch budget and all undeclared fields unchanged:

- `same_arch_erm`: classification risk only; both response-ratio components have effective weight
  zero through method `erm`;
- `ratio_only`: retain the nuisance/fault response ratio and set anti-collapse margin weight to
  zero; and
- `margin_only`: retain the anti-collapse fault-response margin and set ratio-term weight to zero.

Fit each arm under seeds 11, 23, 37, 53 and 71 on the three D0 and ten D1 outer folds, for 195 new
models. No hyperparameter is selected in this experiment.

Each completed model must emit one unique training trace and exactly one prediction for every row
of its held outer fold. An independent post-run validator must compare both artifacts to the
pre-run manifest, verify the recorded hashes and counts, and check finite normalized probabilities
before any component result is interpreted.

## Reporting and interpretation

Report all closed-set, calibration, risk-ranking and source response-ratio metrics already used in
EXP-330, with paired five-seed differences for every arm minus the locked full method and for each
partial arm minus same-architecture ERM. Do not turn the ablation into a new method-selection
round.

The full mechanism receives strong component evidence only if its response ratio improves against
same-architecture ERM and neither partial arm explains all cross-dataset closed-set and mechanism
effects. A partial arm outperforming the full model is retained as negative attribution evidence;
it cannot replace the headline configuration after the fact. Physical-block intervals for the
headline full-versus-tuned-ERM comparison are handled by the separately frozen bootstrap, not by
model-seed standard deviations in this ablation.
