# External review packet

- Purpose: structured domain, statistical, and independent-reproduction review before submission
- Current status: **review scaffold only; no human review or approval has occurred**
- Intended venue route: Reliability Engineering & System Safety first, subject to reviewer advice
- Manuscript: `paper/BEARING_MANUSCRIPT.md`
- Required review point: only after EXP-456R1, EXP-476/477, and the complete EXP-457--463
  validation, manuscript, and release chain are complete

This packet turns the remaining external-review gate into explicit, auditable questions. It must not
be interpreted as review evidence until identified human reviewers complete the relevant sections
against one immutable code revision and evidence archive.

## Review-version identity

Complete these fields before sending the package to reviewers. A response against a different
revision does not close the submission gate.

| Field | Human-supplied value |
|---|---|
| Git commit (40 or 64 lowercase hexadecimal characters) | |
| Public commit URL | |
| Evidence-archive DOI | |
| Evidence-archive SHA-256 | |
| Final bearing-artifact manifest SHA-256 | |
| EXP-457 validation SHA-256 | |
| EXP-477 exact-topology validation SHA-256 | |
| EXP-459 validation SHA-256 | |
| EXP-461 validation SHA-256 | |
| EXP-461V final-quality validation SHA-256 | |
| EXP-463 validation SHA-256 | |
| Manuscript SHA-256 | |
| Final venue PDF SHA-256 | |
| Separate editable Highlights SHA-256 | |
| Bibliography SHA-256 | |
| Review package issued (UTC) | |

## Minimum evidence bundle

Reviewers should receive the exact versions of:

1. `paper/BEARING_MANUSCRIPT.md`, the final venue PDF, final submission materials, the separate
   editable Highlights file, author-completed `paper/RESS_HUMAN_SUBMISSION_FIELDS.md`, tables,
   figures, and captions;
2. `paper/NOVELTY_MATRIX.md`, `paper/references.bib`, and `research/LITERATURE_SEARCH_LOG.md`;
3. `research/ADVERSARIAL_REVIEW.md` and `research/TOP_TIER_REVIEW_RISKS.md`;
4. the Paderborn raw seal, HUST factorial seal, size-matched-control seal, frozen post-hoc HUST
   influence plan, and all amendments;
5. the append-only experiment ledger and incident record;
6. the EXP-476 pre-outcome raw-topology manifest, final bearing-artifact manifest, and EXP-457,
   EXP-477, EXP-459, EXP-461, EXP-461V, and EXP-463 validations;
7. the deterministic evidence archive, its external manifest, and checksum; and
8. dependency locks and the clean-environment reproduction transcript.

Raw Paderborn signals must not be redistributed with this packet. Reviewers who reproduce from raw
data must acquire them under the source licence and verify the project manifest hashes.

## A. Condition-monitoring / mechanical-systems review

For every item, record `accept`, `revision required`, or `not qualified to assess`, followed by a
specific comment and manuscript location.

| ID | Review question | Reviewer decision and evidence |
|---|---|---|
| D1 | Do the four protocols correspond to clearly different and physically meaningful deployment-access scenarios? | |
| D2 | Does XOR quarantine actually exclude both partial-access routes for a new identity at a new operating setting? | |
| D3 | Are the Paderborn bearing/setting axes and HUST specification/load axes described accurately, including their non-equivalence? | |
| D4 | Is “estimated diagnostic reliability” consistently distinguished from component survival, safety integrity, RUL, and deployed reliability? | |
| D5 | Are vibration, motor-current, and fusion conclusions technically plausible and limited to observed access effects rather than causal sensor attribution? | |
| D6 | Does the raw/FFT/STFT sensitivity adequately bound the engineered-feature objection without pretending to cover transformers or foundation models? | |
| D7 | Are the HUST ceiling, five-bearings-per-class sample, and specification/identity confounding prominent enough? | |
| D8 | Does the equal-volume control rule out source count alone while preserving the stated access-and-membership limitation? | |
| D9 | Are fault taxonomy, signal provenance, sampling rates, physical units, and prediction units correct in every table and figure? | |
| D10 | Is the engineering contribution substantial and scoped appropriately for the selected journal? | |

### Domain-review sign-off

- Reviewer legal name:
- Affiliation and role:
- Relevant expertise:
- Conflict-of-interest statement:
- Exact review-version Git commit:
- Review date:
- Unresolved issue IDs:
- Verdict: `suitable after listed revisions` / `not yet suitable` / `unable to judge venue fit`
- Signature or verifiable written approval reference:

## B. Statistical review

| ID | Review question | Reviewer decision and evidence |
|---|---|---|
| S1 | Are recordings/windows aggregated to the operational prediction unit before scoring, with no window or seed pseudo-replication? | |
| S2 | Is the class-stratified physical-bearing bootstrap paired correctly across protocols, methods, and sensor contrasts? | |
| S3 | Are 2,000 Paderborn and 5,000 HUST draws adequate for the claimed descriptive precision, given the small physical cohorts? | |
| S4 | Are percentile intervals described as cohort-conditional descriptive intervals rather than population guarantees or multiplicity-adjusted tests? | |
| S5 | Are tied and ceiling-compressed rankings handled correctly, especially undefined HUST Kendall correlations? | |
| S6 | Is finite-cohort model-selection regret computed and interpreted without post-hoc method selection? | |
| S7 | Does the equal-volume comparison support only falsification of source count, not a causal amount of leakage? | |
| S8 | Is every retrospective, prospective, primary, auxiliary, and failed analysis labelled consistently? | |
| S9 | Does the raw sensitivity rule remain interpretable and reported regardless of whether it passes? | |
| S10 | Does Supplementary Table S4 correctly present the complete HUST deletion audit as post-hoc influence sensitivity rather than confidence intervals or added independent units? | |
| S11 | Are effect magnitudes, intervals, denominators, target counts, and all table-to-text values internally consistent? | |

### Statistical-review sign-off

- Reviewer legal name:
- Affiliation and role:
- Relevant statistical expertise:
- Conflict-of-interest statement:
- Exact review-version Git commit:
- Review date:
- Unresolved issue IDs:
- Verdict: `claims supported after listed revisions` / `claims not yet supported` / `unable to assess`
- Signature or verifiable written approval reference:

## C. Independent reproduction

The reproducer must not reuse the development virtual environment or accept producer summaries as
proof. Record every command, start/end time, machine/OS/GPU, and observed digest.

| ID | Reproduction requirement | Independent observation |
|---|---|---|
| R1 | Create a fresh environment from the locked dependencies and record installation output. | |
| R2 | Verify official dataset files and licence boundaries without receiving redistributed raw signals. | |
| R3 | Verify every design/code seal and all immutable input hashes before execution. | |
| R4 | Re-run the documented validators, match every raw prediction key to EXP-476, and confirm `refit_performed: false`, `aggregate_metrics_recomputed: false`, and `gate_outcome_read: false` where required. | |
| R5 | Regenerate all 42 final paper artifacts and obtain the declared manifest hashes. | |
| R6 | Re-run full Ruff, tests, coverage, the build/runtime, CPU-CI, and GPU-research lock audits, Bandit, and diff-check gates independently of the archived EXP-461Q/461V local report; the observed test count must equal, not merely exceed, EXP-461V's hash-locked count. | |
| R7 | Build the evidence archive twice and confirm bitwise deterministic archive/manifest hashes. | |
| R8 | Independently validate the archive topology, normalized metadata, and absence of prohibited raw/archive inputs. | |
| R9 | Render and visually inspect every final figure and the venue-uploadable manuscript. | |
| R10 | Report all deviations, including environment-specific failures or undocumented manual steps. | |

### Reproduction sign-off

- Reproducer legal name:
- Affiliation and role:
- Relationship to authors:
- Machine/OS/GPU:
- Exact review-version Git commit:
- Reproduction start/end (UTC):
- Transcript SHA-256 and archive location:
- Unresolved issue IDs:
- Verdict: `independently reproduced` / `partially reproduced` / `not reproduced`
- Signature or verifiable written approval reference:

## Consolidated issue log

No issue is closed by deleting evidence or silently changing an outcome. Each resolution must name
the affected files, commit, tests, and whether a new analysis was required.

| Issue ID | Reviewer | Severity | Finding | Required action | Author response | Evidence/commit | Reviewer closure |
|---|---|---|---|---|---|---|---|
| | | | | | | | |

## Author completion check

These remain author-owned and cannot be completed by an automated agent:

- [ ] every reviewer identity, conflict statement, and exact reviewed revision is recorded;
- [ ] every major/critical issue has a documented disposition and reviewer closure;
- [ ] all authors approve names, order, affiliations, CRediT roles, funding, and conflicts;
- [ ] all authors verify every citation, number, figure, and generative-AI disclosure;
- [ ] the corresponding author approves the public commit, archive DOI, licence boundaries, and
      actual submission; and
- [ ] the final manuscript hash matches the version reviewed and uploaded.
