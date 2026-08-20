# Bearing technical-release amendment 001

- Amendment date: 2026-08-19 UTC
- Superseded public-candidate release: `smartvalve-bearing-evidence-release-0.11.0`
- Replacement release topology: `smartvalve-bearing-evidence-release-0.11.1`
- Scientific-result impact: none
- Model refit: none

## Detection

After EXP-503/504 built and independently reopened the record-frozen 0.11.0 archive, a planned
archive-source clean reproduction compared the archive inventory with the manuscript-package
documentation. `paper/README.md`, `paper/REPRODUCIBILITY.md`, and
`research/PAPER_READINESS_CHECKLIST.md` all cite `research/BEARING_VISUAL_QA.md`, but the release
builder's explicit document allow-list did not include that file. The archive validator correctly
proved that the produced archive matched its own manifest; neither the builder nor validator had
claimed that every newly referenced audit document was in the allow-list.

## Integrity decision

Retain EXP-503/504 as valid evidence for the archive they actually describe, but do not promote
release 0.11.0 as the public candidate. Do not silently copy the missing document into the existing
archive or reuse its checksum. No scientific summary, prediction, interval, bootstrap draw,
manuscript value, figure, quality log, dependency lock, or human-review flag is changed.

## Bounded correction

Release 0.11.1 adds this amendment and `research/BEARING_VISUAL_QA.md` to
`DEFAULT_DOCUMENTS`. The existing release-topology test now requires both files and the explicit
0.11.1 version. The complete project quality gate, deterministic release build, independent
archive reopen, and downstream release-bound manuscript-layout validation must be rerun under new
experiment identifiers. The replacement archive must continue to exclude raw dataset files and
`paper/RESS_HUMAN_SUBMISSION_FIELDS.md`, and it must keep
`technical_manuscript_submission_ready=false`.

The archive-source clean reproduction may start only from the independently validated replacement
archive. Its result remains a local archive-origin preflight and cannot substitute for the formal
detached-commit reproduction, public DOI, or independent human review.
