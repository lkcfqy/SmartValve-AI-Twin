# Industrial UI benchmark

The dashboard borrows information architecture from public product material, not protected artwork, trademarks or screen layouts.

| Public reference | Observed interaction pattern | SmartValve implementation |
|---|---|---|
| [Emerson Fisher ValveLink](https://www.emerson.com/en/final-control/products/fisher-valvelink) | Current/baseline valve signatures, boundary results, diagnostic evidence and maintenance-oriented tests | ValveDNA overlay, abnormal travel boundary, evidence table and work order |
| [Rotork Intelligent Asset Management](https://www.rotork.com/en/service/connected-services) | Fleet health summaries, colour-coded maps, trend/alert review and maintenance prioritisation | Fleet overview, condition × network-impact priority and status map |
| [Rotork Insight 2](https://www.rotork.com/en/support/downloads/insight2) | Actuator configuration, data-log review and traceable asset information | Source context, model version, event history and audit index |
| [SAMSON EXPERTplus](https://pfeiffer.samsongroup.com/document/t83893en.pdf) | NAMUR NE 107-style device state, time-stamped messages and fault-source guidance | NE 107-style status strip, evidence chain and recommended response |

The animated valve cutaway and hydraulic flow field are original additions rather than vendor screen copies. Valve position, motor-current rings, flow-particle speed, abnormal-travel pulses, node pressure and affected-node propagation are driven by the current diagnostic and WNTR result. Cranfield uses a separate ball-screw actuator scene driven only by measured setpoint, position and current; it never renders water flow.

## Design rules

- A status colour must always have text; colour is never the only signal.
- Device health and hydraulic/business impact remain separate metrics.
- The first screen prioritises assets; detailed signatures appear only after drill-down.
- Every conclusion keeps its source grade, model version, data quality and limitation.
- Replayed public or simulated records are labelled as compressed replay, never presented as live field telemetry.
- The visual system is original: dark control-room palette, neutral typography and no vendor logos or copied assets.
