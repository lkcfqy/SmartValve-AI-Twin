# D2 final decision

- Decision date: 2026-08-18 UTC
- Candidate: frozen PIRL v0.2
- Prospective dataset: Paderborn Bearing DataCenter
- Decision status: **NO-GO for a multi-dataset PIRL-superiority claim**
- Data status: D2 is now observed and must be treated as development evidence for any future method

## Predeclared rule

A dataset-endpoint test is confirmatory-positive only if its paired effect is at least 0.01, its
95% physical-unit percentile interval has lower bound above zero, and its Holm-adjusted two-sided p
is at most 0.05. The internal multi-dataset gate requires at least one positive endpoint on at least
two of Cranfield, UCI Hydraulic, and Paderborn, with no materially harmful endpoint whose interval
excludes zero. No subset, pooled substitute, or post-outcome endpoint replacement is allowed.

## Final six-test decision

| Dataset | Endpoint | Positive-favors-PIRL effect | 95% interval | Raw p | Holm p | Positive |
|---|---|---:|---:|---:|---:|---|
| Cranfield | minimum-environment macro F1 | +0.007785 | [-0.016053, 0.031119] | 0.410795 | 1.000000 | no |
| Cranfield | selective risk at source 50% | -0.000174 | [-0.007159, 0.006241] | 1.000000 | 1.000000 | no |
| UCI Hydraulic | minimum-environment macro F1 | +0.000860 | [0.000000, 0.002473] | 0.213893 | 0.855572 | no |
| UCI Hydraulic | selective risk at source 50% | +0.044069 | [0.038991, 0.049302] | 0.001000 | 0.005997 | **yes** |
| Paderborn | minimum-environment macro F1 | +0.020921 | [-0.045959, 0.081241] | 0.692654 | 1.000000 | no |
| Paderborn | selective risk at source 50% | -0.031777 | [-0.070919, 0.007151] | 0.097951 | 0.489755 | no |

- Positive tests: 1/6.
- Datasets with a positive endpoint: UCI Hydraulic only.
- Materially harmful tests: 0/6 under the frozen definition.
- Multi-dataset evidence gate: **failed**.

Canonical family metrics:
`EXP-422B-CONFIRMATORY-FAMILY__20260818T163128.647362Z__reconciled-six-test-holm-family/outputs/metrics.json`,
SHA-256 `0143b1e6703a1941f636001b298ce29837386258127068e715fe4ffe73854476`.

## D2 descriptive context

The nine-method Paderborn run trained 1,080 final models and retained 104,355 primary and 259,200
compound prediction rows. MatchDG led pooled macro F1 at 0.395157; PIRL was 0.382868 and ERM
0.369505. PIRL led descriptive minimum-setting macro F1 at 0.318539 versus ERM 0.297618, but its
paired bearing-level interval crossed zero widely. At the nominal source-50% policy, descriptive
unweighted fold risk was 0.611661 for PIRL and 0.614684 for ERM, yet the confirmatory pooled
bearing-level effect favored ERM at the point estimate. These estimands must remain separate.

## Component attribution

EXP-347 found full PIRL byte-identical to ratio-only and margin-only byte-identical to ERM across all
65 D0/D1 final models. The margin term has no observed effect. This rules out a claim that two
independently effective components explain the candidate's behavior.

## Structural exclusion and reconciliation ledger

One primary MAT file, `N15_M01_F10_KA08_2.mat`, was structurally unreadable. The retained primary
count is 2,319. No imputation, substitution, or target-outcome-based exclusion occurred.

### Base validation

- EXP-418 failed because expected compound keys used original manifest row indices while model
  outputs used compact post-exclusion indices.
- Protocol SHA-256:
  `72702a2d66e01dafe5a911d503364cc7b888f69d4f1cb118e675883d73f4cddd`.
- Reconciliation source SHA-256:
  `9535cfadf5204759f94a345574fae56618d8b23902dc308644643bade8e9c4de`.
- Specification SHA-256:
  `39b13483e6a9bc7dfeccfb1895726971295106fbd88c1e68a94eed304391c7db`.
- EXP-418B passed; validation SHA-256
  `b14fcb57598ae3f4c7d03fba28c87f4ae2dc47f6a30dd8085d61a3bc0b80d6b3`.
- Predictions were not changed. Maximum probability-sum error was `1.42e-7`.

### Selective validation

- EXP-420 failed on the same compound coordinate mismatch.
- Reconciliation source SHA-256:
  `b64118ce6bc8a3644b41d401949556765fe8d6b06eace00312f0a24e22027057`.
- Reconciliation addendum SHA-256:
  `18eed62a32c5156a3d883909a6caf8a2ebe54010b8bb13eabc5d7bc8bf9816ba`.
- EXP-420B passed; validation SHA-256
  `7a57d075056778e39d0ff847c8a8944c97c65fa2bb90804558babae30ef3a75d`.
- Ensemble reconstruction had maximum probability difference zero; target labels were absent from
  selection.

### Bearing bootstrap

- EXP-421 failed before inference because an unchanged assertion required 2,320 rows.
- Protocol SHA-256:
  `c1e01dcf46ef18aca241eb86b7fae2c28906a7b5cd3b45b4f5e540d362e98887`.
- Wrapper SHA-256:
  `f1eb02f8af89f9b0e05aa77f9fb09c58d35fe369fc554f451aa9b07c32a15645`.
- Specification SHA-256:
  `9b1879e7cfbed63bb77c34d5896f03d9ca541bfa01e172925e5620161d60f547`.
- EXP-421B used 29 bearings; KA08 contributed 79 rows and every other bearing 80. No imputation was
  made and the class-stratified resampling design was unchanged.
- Metric tensor SHA-256:
  `00beae8fbb4493d3207a0794654e04aa2a71b742cd82324fd1707b898b2b9ce9`;
  draw-plan SHA-256:
  `7c114b3911c598185c9e87e73a69ea3d12b5cfa6f8e071da5e421a6a4a64527f`.

### Confirmatory assembly

- EXP-422 failed before Holm assembly because it rejected bootstrap version 0.2.
- Protocol SHA-256:
  `2f294ac79ca3736b2603a279676170fc0d28949bbe81c15a8be74f78fd0ecce3`.
- Wrapper SHA-256:
  `a1e1af9f3816149b213778bf7ced4d7f34d22fed7fdb031da4be866839af1351`.
- Specification SHA-256:
  `89b50273e460942bd0dded3cb8f34b1c30c83b19e4de18d09a57298b8e4e9948`.
- EXP-422B accepted only the documented version/count change; the original six members and Holm
  implementation were unchanged.

## Allowed conclusion

The sealed experiment provides strong evidence about evaluation reliability: a promising
development candidate did not reproduce as a broad multi-dataset improvement, and the sole positive
endpoint survived the full correction only on UCI. This is a valid mixed-result outcome and a
potential contribution to a reliability/reproducibility paper.

## Prohibited rescue analyses

- Do not tune PIRL on Paderborn and report Paderborn again as prospective validation.
- Do not drop Paderborn selective risk, replace minimum-setting F1 with pooled F1, or add a favorable
  compound endpoint to the confirmatory family.
- Do not change the practical threshold, bootstrap unit, effect orientation, or multiplicity rule.
- Do not exclude seeds, bearings, settings, or folds based on observed performance.
- Do not describe the absence of material harm as evidence of equivalence or safety.

## Next scientific options

1. **Current-paper path:** complete a mixed-result audit manuscript centered on prospective
   validation, metric dependence, source-only abstention, and transparent reconciliation.
2. **New-algorithm path:** treat D0/D1/D2 as development evidence, design a materially different
   method, freeze it, and acquire an untouched D3 with independent physical assets. Only D3 can
   restore a prospective algorithmic claim.
