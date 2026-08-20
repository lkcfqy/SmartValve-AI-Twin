# PIRL-SORE component-attribution ablation v0.1

- Status: frozen after EXP-320 and before any new ablation target prediction
- Frozen: 2026-08-18
- Motivation: EXP-320 passed its descriptive efficacy screen on UCI, but the final intervention
  hinge was zero in every model and the source response ratios increased
- Access tier: P0 source-only
- Sealed dataset: Paderborn archive contents remain unopened

## Locked reference

The ERM and full PIRL-SORE rows are reused without refitting from EXP-320. Its metrics SHA-256 is
2909e32f19aa4b9beb5c28da821c1fd3e8b4e6670691eb64e03a21a5c9182ebf, prediction
SHA-256 is a80a93ef58aef8a135fe53dde3ed00a6255b350c3d766d5236e7e9555e02fa13, and
training-trace SHA-256 is c0f0002b577e446e3f7a38cb5296d55bd02a31591de7c7f404e88691c2ad2302.

All data, outer folds, architecture, optimizer, 300-epoch budget, five seeds, metrics and
risk-envelope diagnostic are identical to the frozen initial screen.

## New ablation arms

- worst_erm: source empirical risk plus 0.5 times worst exact-source-environment risk; intervention
  weight exactly zero.
- pirl_only: source empirical risk plus 0.5 times max(0, R_N - 0.5 R_F); worst-environment weight
  exactly zero.

No other setting changes. Each new arm fits 65 models: three Cranfield and ten UCI outer folds
under seeds 11, 23, 37, 53 and 71.

## Attribution decisions

The full model's UCI gain is attributed primarily to worst-environment training if worst_erm
recovers at least 80 percent of the full-minus-ERM mean macro-F1 improvement and pirl_only recovers
less than 20 percent. Brier and AURC directions must be reported even if they disagree.

The current intervention hinge is considered mechanistically supported only if pirl_only lowers the
mean source representation-response ratio relative to ERM on both development datasets and
improves worst-fold macro F1 on at least one, without lowering mean-fold macro F1 by more than 0.02
on the other.

If this mechanism rule fails, the current hinge is rejected as the headline contribution even if
the full model passes the earlier efficacy screen. A replacement loss may be developed on D0/D1
under a new version, while EXP-320 and this ablation remain immutable negative evidence.

This is a component-attribution experiment, not a statistical paper claim. Physical-block
intervals are deferred until a final method survives development and is compared with the complete
baseline suite.
