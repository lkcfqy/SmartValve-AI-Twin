| Protocol | Features | Healthy reference | Target trajectory | Target labels | Deployment interpretation |
|---|---|---|---|---|---|
| P0 | raw features | none | no | no | strict target-free baseline |
| P1 | delta + relative features | linear healthy reference from two source loads | no | no | source-only extrapolation |
| P2 | delta + relative features | different healthy repetition at held-out load | yes | no | target-condition calibration; not pure DG |
