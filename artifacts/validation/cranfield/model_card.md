# Cranfield source-specific development benchmark

- Version: `cranfield-extra-trees-dev-0.1.0`
- Trials: 180 across six motion/load groups
- Leave-one-load-out accuracy: 0.8722
- Macro F1: 0.8736
- Scope: electromechanical ball-screw actuator, not a water valve

## Split and leakage boundary

Each trial is compared with a different normal repetition from the same motion/load condition; the evaluated current trial is never its own baseline.
Every fold excludes all labelled trials at the test load from model fitting.

## Limitations

- Development cross-validation, not a locked independent final test.
- Hyperparameters were selected while observing this dataset and these group folds.
- Trials are repeated experiments from one public actuator rig, not independent assets.
- The -40 kg trapezoidal fold is a documented failure mode, not hidden from reporting.
- Evidence scores are uncalibrated tree-vote strengths and must not be read as probabilities.
- This benchmark is not served as the generic ValveDNA diagnosis and does not prove water-valve performance.
