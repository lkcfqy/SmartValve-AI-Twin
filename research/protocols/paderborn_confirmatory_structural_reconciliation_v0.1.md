# Paderborn confirmatory-family structural reconciliation — v0.1

- Written: 2026-08-19 after failed EXP-422 and before any six-test Holm result existed.
- Status: narrow post-outcome validation adapter.

## Trigger

EXP-421B produced the frozen 2,000-replicate D2 bearing bootstrap on the exact retained 2,319-row
cohort. EXP-422 then invoked the unmodified six-test assembler and stopped at
`confirmatory input has an unexpected bootstrap version`. It did not construct the six-row table
or calculate a Holm-adjusted p-value.

The original assembler accepts only bootstrap version 0.1 and exactly 2,320 physical measurements.
The structural-exclusion reconciliation intentionally emits version 0.2 and reports the truthful
2,319 retained measurements plus the one locked exclusion. This is the downstream validation
assertion anticipated by the bootstrap reconciliation protocol.

The two raw D2 endpoint results had been read before this adapter was written. No Holm result or
family-level claim decision existed. The adapter is fixed entirely by the already disclosed
version/count mismatch.

## Authorized adapter

The adapter may change validation acceptance only:

- require D2 bootstrap version `paderborn-paired-bearing-cluster-bootstrap-0.2.0`;
- require 29 pure bearings, 2,320 locked pure measurements, 2,319 retained physical measurements,
  and exactly the frozen `KA08/N15_M01_F10/2` exclusion; and
- prove that the D2 package is bound to the bootstrap reconciliation specification and failed
  EXP-421 record.

After these checks, the adapter must invoke the original assembler unchanged. The exact six test
IDs, raw input effects and p-values, Holm step-down implementation, alpha 0.05, 0.01 practical
threshold, harmful-effect rule, and internal requirement of a positive endpoint on at least two
datasets may not change. The original failed EXP-422 run must be retained and hash-bound.

## Prohibited actions

- no test addition, deletion, pooling, direction change, p-value replacement, or alpha change;
- no alternative multiplicity correction;
- no modification of D0, D1, or D2 bootstrap inputs; and
- no claim that this adapter was prospective.

