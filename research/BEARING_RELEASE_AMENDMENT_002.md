# Bearing technical-release amendment 002

- Amendment date: 2026-08-19 UTC
- Superseded public-candidate release: `smartvalve-bearing-evidence-release-0.11.1`
- Replacement release topology: `smartvalve-bearing-evidence-release-0.11.2`
- Triggering retained run: `EXP-514-ARCHIVE-SOURCE-CLEAN-REPRODUCTION-V0.11.1`
- Scientific-result impact: none
- Model refit: none

## Detection

EXP-514 extracted the independently validated 0.11.1 archive twice outside the development
checkout, created a fresh CPython 3.12 virtual environment, installed the hash-locked CPU stack
without editable mode, reacquired and verified all five public fixtures, and passed the CPU-only,
installed-lock, and Ruff preflights. The first exact test pass then retained seven failures among
427 collected tests. The run stopped before coverage and downstream evidence checks, reported
`failed_supplementary_archive_source_clean_reproduction`, and kept all stdout, JUnit, environment,
download, and exception records.

The failures exposed release-source completeness assumptions that the internal archive validator
was not designed to test:

1. `Dockerfile` and `.dockerignore` were absent even though packaging tests inspect them.
2. Six paper support documents, the checked-in `paper/generated` packages, their eight locked
   metric inputs, and the service benchmark fixtures were absent even though the exact suite reads
   them.
3. the provenance recorder used only `git ls-files`, so a valid tar extraction without `.git`
   produced a zero-file source fingerprint.
4. the RESS PDF validator derived the project root from installed-package depth, which is invalid
   for a non-editable wheel installation.

The service benchmark endpoint failure was a consequence of the omitted checked-in benchmark
fixtures. No scientific prediction, interval, bootstrap result, table value, figure value, or
manuscript claim failed comparison in EXP-514.

## Integrity decision

Retain EXP-510/511 as correct build-and-reopen evidence for release 0.11.1 and retain EXP-514 as a
failed clean-reproduction attempt. Do not add files to the existing archive, reuse its checksum, or
describe its 427-test topology as cleanly reproduced. Release 0.11.1 is withdrawn as the public
candidate even though its internal member hashes remain valid.

## Bounded correction

Release 0.11.2:

- includes the Docker/CI support files, required paper support documents, checked-in generated
  paper packages, their hash-locked inputs, and service benchmark fixtures;
- makes source fingerprinting fall back to a bounded filesystem inventory when Git metadata is
  unavailable, while excluding runtime caches, external data, and recorded-run output roots;
- resolves release-bound PDF source files through the explicit project-root contract rather than
  installed-package directory depth; and
- extends the existing release-topology test without increasing or weakening the test count.

The complete local quality gate, independent quality validation, deterministic release build,
independent archive reopen, release-bound PDF validation, and archive-source clean reproduction
must all be rerun under new experiment identifiers. The replacement must continue to exclude raw
dataset files and `paper/RESS_HUMAN_SUBMISSION_FIELDS.md`, and all records must keep human review,
formal third-party reproduction, DOI publication, and submission readiness false.
