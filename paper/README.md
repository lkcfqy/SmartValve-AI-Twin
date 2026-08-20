# SmartValve bearing-protocol manuscript package

- Evidence freeze: Paderborn retrospective design and signal-unopened HUST replication, 2026-08-19
- Validated empirical status: complete for compact-feature Paderborn fusion/vibration/current,
  combined sensor attribution, HUST primary replication, HUST equal-source-volume control, and
  the post-hoc no-refit HUST physical-unit influence audit
- Active hold: final 0.11.3 archive validation and complete clean run, detached author-approved
  revision/DOI reproduction, external human review, and completed venue-owned submission fields
- Intended article type: validation-estimate reliability, physical-access protocol, and sealed
  external replication
- Preferred first-submission scope: Reliability Engineering & System Safety
- Working-render status: deterministic 24-page empirical five-figure watermarked PDF passed
  independent machine validation and 24/24-page plus 5/5-figure agent visual preflight; human
  visual approval and the final non-watermarked upload remain open
- Acceptance status: no venue tier or acceptance is guaranteed

## Working title

> Physical Access Changes Estimated Bearing-Diagnosis Reliability: A Crossed Identity--Condition
> Audit with Sealed Replication

## Central validated result

A train/test split defines which physical identities and operating conditions are visible during
fitting and therefore changes the deployment quantity being estimated. Under a strict crossed
protocol that withholds both axes and quarantines both partial-access XOR arms, all 27 Paderborn
sensor-by-method random-minus-crossed physical-bearing intervals and all nine HUST intervals have
positive lower limits. Paderborn method leaders change under all three sensor views. HUST
prospectively reproduces the score gap, but not the directional rank reversal because its
accessible protocols saturate at macro F1 1.0. An equal-volume HUST control retains the gap with
identical targets and 24 source recordings in each arm, ruling out source-record count alone.
Across both HUST access comparisons, all 18 method-by-comparison effects remain positive after
deleting any one bearing or any one class-balanced matched-specification group. This deletion audit
is post hoc and does not create independent physical units or population confidence intervals.

This is an evaluation and reliability contribution, not a claim that PIRL or another classifier is
state of the art. The earlier six-test PIRL superiority gate failed and remains disclosed.

## Start here

1. `BEARING_MANUSCRIPT.md` is the integrated template; EXP-460's hash-locked
   `BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md` is the canonical 9,369-word empirical manuscript.
2. `TITLE_ABSTRACT.md` contains the preferred title, research questions, contribution boundary,
   and the abstract source.
3. `BEARING_METHODS.md`, `BEARING_RESULTS.md`, and `BEARING_DISCUSSION.md` retain modular sources
   for audit and copyediting.
4. `SUBMISSION_STRATEGY.md` documents the RESS-first venue rationale and MSSP/TIM alternatives.
5. `NOVELTY_MATRIX.md` maps supported and prohibited claims to the closest literature.
6. `REPRODUCIBILITY.md` records the environment, canonical commands, hashes, and quality gates.
7. `research/EXPERIMENT_LEDGER.md` is the append-only run chronology, including failures.
8. `research/ADVERSARIAL_REVIEW.md` records the strongest rejection arguments, bounded responses,
   and residual submission gates.
9. `RESS_SUBMISSION_PACKET.md` maps the validated artifacts to journal uploads and contains a
   bounded cover-letter draft with explicit human-owned declarations.
10. `research/EXTERNAL_REVIEW_PACKET.md` and `research/CLEAN_REPRODUCTION_PROTOCOL.md` define the
    evidence required from domain, statistical, and independent reproduction review.
11. EXP-518/519 completed and independently validated the amendment-002 post-freeze eight-check
    package. EXP-520/521 built and reopened 0.11.2, but EXP-524 retained a later raw-free artifact-
    reproduction interface failure after its 427-test/coverage/security prefix passed. Amendment
    003 and EXP-525 define and focus-test the bounded 0.11.3 replacement; its final gate, archive
    reopen, and complete clean run remain.
12. `scripts/render_ress_pdf.py`, `scripts/validate_ress_pdf.py`,
    `scripts/generate_ress_submission_materials.py`, and `scripts/validate_ress_submission.py`
    enforce the ordered five-figure manuscript PDF, its independent post-release identity check,
    separately editable Highlights, and synchronized journal-text boundary; working renders remain
    under ignored `output/` and page-inspection scratch files under ignored `tmp/`.
13. `RESS_HUMAN_SUBMISSION_FIELDS.md` is the intentionally incomplete author/title-page, CRediT,
    funding, conflict, release-identity, and approval record. No automated tool may fill it.

## Canonical bearing evidence

| Evidence | Canonical run | Locked SHA-256 |
|---|---|---|
| Paderborn fusion four-protocol neural audit | `EXP-434B-PADERBORN-NEURAL-PROTOCOL` | summary `0a717c6bc1e4d94182b11f91502397d32a3816d86931ed5369316714a2a13a9e` |
| Fusion independent validation | `EXP-456A-PADERBORN-PROTOCOL-VALIDATION` | validation `03428d40112509c08ffe11bf56ca172a6975b5570d653bc5ac1fbf5a0ece8099` |
| Classical three-sensor audit | `EXP-436-PADERBORN-SENSOR-CLASSICAL` | summary `fe12ce9d8380274d0485a9c0577c502bb53c424fa7428641e7f27f94a5e8b6f2` |
| Vibration neural audit | `EXP-438-PADERBORN-NEURAL-VIBRATION` | summary `e30592e1b0f7b94c012f99c10a2f5374907a3fa76fd5d3f6773796f47eeeb5fb` |
| Motor-current neural audit | `EXP-451-PADERBORN-NEURAL-CURRENT` | summary `47ce349cc8ab633d51384614310bc926bcff7a8b5f294f2e91318a9765e51e46` |
| Combined sensor attribution | `EXP-452-PADERBORN-NEURAL-SENSOR-ATTRIBUTION` | summary `72f1bbca7ae6fa2e50f105ff699a2022b7705ca8cda0dd2ea43c341edb8b23ea` |
| Combined sensor validation | `EXP-453-PADERBORN-NEURAL-SENSOR-VALIDATION` | validation `acb71e10125a710681ae3fc8fee72ee7f691947d21932955af753a5d5301c5cc` |
| Sealed HUST primary replication | `EXP-445-HUST-D3-NEURAL` | summary `3f721ff50cc72b845d5ce16a3c7ef987ae5c33cb0d69bfab0804a9be38b5d61a` |
| HUST primary validation | `EXP-447-HUST-D3-VALIDATION` | validation `ba9ceee356fe8cc04ddfe1a28f6e46038fd0c60c4ea374df196400b22fdf6c6a` |
| HUST equal-volume control | `EXP-449-HUST-D3-SIZE-MATCHED` | summary `23b898440a6a09c4efd21ea6e9faec16ca637989a5310e4fa69f8067f5e4833c` |
| Equal-volume validation | `EXP-450B-HUST-D3-SIZE-MATCHED-VALIDATION` | validation `b7e13cf20ff51d06690e56b0f1d45102ecba23dc0df56ad4a7790e4c5d263abe` |
| HUST physical-unit influence audit | `EXP-464R1-HUST-PHYSICAL-UNIT-INFLUENCE` | summary `431e580c9ee2d3489980fd4edad31151f97eeff343656473d1df8504c2406e18` |
| Influence audit validation | `EXP-465-HUST-PHYSICAL-UNIT-INFLUENCE-VALIDATION` | validation `dfb88a40883c71059eab856bfc6e25247192431b83a66ebbdc6f1bbccd0e587a` |
| Raw-window artifact | `EXP-455-PADERBORN-RAW-WINDOWS` | summary `af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191` |
| Raw/FFT/STFT sensitivity | `EXP-456R1-PADERBORN-RAW-ARCHITECTURES` | summary `5781106c9b192df2943a2deff1ab62473aa29916843c6df78a67bf189278ee7f` |
| Raw metric validation | `EXP-457-PADERBORN-RAW-VALIDATION` | validation `822f6c504b66c6398c56b6480bc1139a068b1fd7d3457918799865deca0858b0` |
| Raw topology validation | `EXP-477-PADERBORN-RAW-TOPOLOGY-VALIDATION` | validation `3e3f9f4886e650b50c8d3bc914b6a4cd711e24ef8b41c556cf8eb583772139e6` |
| Final bearing artifacts | `EXP-458/459R1` | manifest `4abf54dbdb8dd89c0f998ac8e96dc59d51734d28ee5e96f55c1dc15197b4aec7`; validation `425c0c4861aaee9c6c004c121b0334d5345c34e1e75cdb40adc440f810b8243d` |
| Empirical manuscript | `EXP-460/461` | manuscript `784392b35d9c8a69c9554e01c6ed5b936a75716c276a8a7aca47244f6a44532f`; validation `d77dac66e0a34c0f9c4f087bd3a14a11f06782f0a43e48fa7e9c6073ff794f35` |
| Amendment-002 post-freeze quality | `EXP-518/519` | summary `919f88939c2c27ba99d8635d774df6f4c31f17c56ce0c0c24ccb2e14b81e5729`; validation `bd057e4fea03f68b5b3cffa117091bdcc6cda5631ec53fb1f9fb8dbe69b53ca7` |
| Withdrawn 0.11.1 archive candidate | `EXP-510/511/514` | archive `b12b4210e031031da28e2689f8da56b9c19408dca5ad0421fa6c196358ce4327`; internal validation `205e7690b66ad3a2de1f556ddf5f3fae841145cac72530bac547927cfdf0cc91`; clean run failed 7/427 |
| Withdrawn 0.11.2 archive candidate | `EXP-520/521/524` | 531 files; archive `7dc8b4fa4dc73acfdd7808c47f0d99dd3aa8a1c30e49acd59c1650157305d7b4`; clean run passed quality but failed raw-free artifact regeneration |
| 0.11.3 bounded correction preflight | `EXP-525` | 22/22 focused tests; default strict mode retained; release-input mode exact-output and missing-consumed-input controls passed |
| Empirical PDF preflight | `EXP-490/491` | PDF `c041274804f7818b97f002d47ccde97baf23e67c42d6ad4506d89b73daf4b463`; validation `09ff92a7473a05c83f7673eb19eb52efb2f8459153639c97f12d6ef8bc263939` |

Timestamped directories and full output digests are authoritative in the experiment ledger.
Interrupted EXP-456 remains only as an incident artifact; retained EXP-459 records the independent
validator's representation-precision failure and EXP-459R1 is the successful no-refit successor.
EXP-514 and EXP-524 are likewise retained as the failed 0.11.1 and 0.11.2 archive-source attempts;
neither is converted into a pass by later focused or local quality checks.

## Generated material

`paper/generated/` retains the earlier Cranfield and multi-rig packages. The final bearing package
was generated under EXP-458 and independently validated under EXP-459R1: six main tables, four
supplementary tables, five SVG sources, five normalized vector PDFs, captions, submission text, and
the 42-output manifest. The generator rejects any summary or validation whose SHA-256 differs from
the command-line lock.

The current canonical empirical inspection artifact is EXP-490's deterministic 24-page
`RESS_EMPIRICAL_WORKING_PREFLIGHT.pdf`, with an explicit non-submission watermark and five validated
one-page main figures. EXP-491 independently binds it to the validated technical release, and
`research/BEARING_VISUAL_QA.md` records the 24/24-page and 5/5-figure agent preflight. Final PDF mode
still rejects all working and human-action markers; no technical preflight substitutes for final
author approval.

## Drafting rules

- Lead with reliability of the validation estimate and physical information access.
- Describe Paderborn factorial results as retrospective development evidence.
- Describe HUST as protocol-prospective and signal-unopened, not literature-outcome-blind.
- Report HUST's score-gap replication and ceiling-limited rank non-replication together.
- Report all methods, sensor views, intervals, ties, and failed validators without selection.
- Treat windows and seeds as optimisation units, never as physical replicates.
- State that the equal-volume control rules out source count alone, not a causal leakage amount.
- Label the HUST deletion audit post hoc; never call its ranges confidence intervals or new
  independent replicates.
- Do not use “state of the art,” “causal representation,” “validated for deployment,” or a
  population-wide algorithm ordering.

## Legacy package

The earlier PIRL/access/selective-prediction audit remains in `MULTIRIG_METHODS.md`,
`MULTIRIG_RESULTS.md`, `METHODS.md`, and `RESULTS.md`. Those files document the failed prospective
algorithmic gate and are supporting chronology, not the headline manuscript.
