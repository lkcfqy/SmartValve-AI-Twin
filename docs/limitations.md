# Limitations and claim policy

## What is physically measured

- Cranfield files contain real 25 Hz position setpoint, position error and motor current from an instrumented electromechanical linear-actuator rig with seeded faults.
- SKAB contains real measurements from a physical water-circulation testbed, including pressure, flow, motor electrical signals, vibration and anomaly labels.

## What remains unvalidated

- Neither public source is a Qingdao Weilong valve or a manufacturer-specific equivalent.
- The model is not calibrated to a valve type, diameter, actuator, pressure class or Kv/Cv curve.
- WNTR computes network consequences; it does not model stem friction or actuator current.
- Internal leakage and remaining useful life are not physically validated.
- The CNY 200 desktop-rig adapter exists, but no hardware has been purchased or tested.
- SQLite and a single API process are suitable for a hardened single-node engineering pilot, not proof of site-scale high availability.
- NAMUR NE 107 labels are presentation mappings, not certification claims.
- The 3000-run regression matrix and 1500-run locked challenge are deterministic S0 simulation evidence. Their F1 and false-positive rates are not estimates of physical or manufacturer-product performance.
- The locked challenge shows lower macro F1 than the regression matrix (0.874 vs 0.953), principally from low-severity friction and sensor-drift misses; the model was not retuned after reading that challenge.
- The simulation matrices contain 2100/1050 unique observable traces across 3000/1500 parameter combinations; zero-severity duplicates are not independent samples.
- The Cranfield source-specific development benchmark reports 87.2% leave-one-load-out accuracy, but its trapezoidal -40 kgf fold is only 33.3%. It is not a locked product-accuracy result.
- The API `confidence` field is retained for compatibility but is an uncalibrated heuristic evidence strength, not a probability.

## Allowed project statement

“A hardened single-node industrial engineering pilot validated on public physical actuator and water-loop benchmarks, ready for calibration on one enterprise valve model.”

## Disallowed project statement

“Production-ready Weilong predictive-maintenance system” until product data, acceptance criteria, security review and field reliability testing are complete.
