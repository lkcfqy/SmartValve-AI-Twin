# Bearing evidence-release amendment 003

- Amendment date: 2026-08-19 UTC
- Superseded candidate: `smartvalve-bearing-evidence-release-0.11.2`
- Replacement topology: `smartvalve-bearing-evidence-release-0.11.3`
- Trigger: retained EXP-524 archive-source reproduction failure
- Scientific outputs changed: **none**
- Model fitting performed by this amendment: **none**

## Trigger and retained evidence

EXP-524 began from the independently reopened 531-file release 0.11.2 archive. Two extractions
matched; a fresh CPython 3.12 environment, non-editable install, CPU-only check, installed-lock
check, and fresh five-fixture public-data sync passed. Ruff, all 427 tests, path coverage at
`78.07569752078962%`, expanded medium/high Bandit, all three strict dependency audits, archive
reopening, and independent validation of the released final-quality record also passed.

The run then stopped at its first artifact-package regeneration check. The general artifact
validator followed every output named by each parent experiment summary, including
`vibration_windows.npy`. That raw signal array is deliberately prohibited from the public
raw-data-free archive even though the 28 inputs actually consumed by the paper package are present
and hash-locked. The same all-parent-output precondition would have blocked the subsequent two-pass
generator. This is a release-reproduction interface defect, not a test, score, interval, figure,
or manuscript disagreement. EXP-524 remains failed and must not be relabelled as a pass.

Retained SHA-256 values are:

- failed reproduction summary:
  `227331201e73b71803c74149ceb6a3bb025c2648e6297a5700f674a737976887`;
- 427-test JUnit record:
  `74b0a8de97d19dfc856cbf30f4dcf945cf36138ddc48f785a7d246224d8ef6ad`;
- failing artifact-validator stderr:
  `bcffb2cbe1747a0d05f718680ed05fa7dc43a6d0e205bebead3711b01de8e18b`;
- recorded-run metadata:
  `950c9655c7fe7de95700fb700af3e7ab614140faecadc340aa0a913b8e00e6d3`.

## Bounded correction

Release 0.11.3 adds an explicit `--release-input-mode` to the paper-artifact generator and its
independent validator. The mode has a deliberately narrow contract:

1. the parent summary file itself, expected status, and CLI-supplied SHA-256 remain mandatory;
2. all 28 manifest inputs must exist inside the project root and match their recorded hashes;
3. every consumed CSV is still checked against its parent summary's output-hash map before use;
4. the raw-window index and extraction trace remain required and are checked against the locked
   raw-window summary;
5. all six independent no-refit validation records remain required;
6. the validator still recomputes the headline values, scientific decisions, cross-summary
   identities, output bytes, SVG/PDF topology, and precision tolerance without importing the
   generator; and
7. only unrelated outputs declared by parent summaries may be absent. The mode records that those
   unconsumed parent-summary outputs were not verified.

Default mode is unchanged and continues to require every output declared by every parent summary.
The existing end-to-end artifact test is extended without increasing the 427-test topology: it
must show that default mode rejects a missing raw array, release-input mode regenerates the exact
same manifest and 42 outputs without that array, release-input validation passes, and removal of a
consumed raw-window index is still rejected.

## Recovery boundary

Release 0.11.2 and EXP-520/521 remain valid evidence for the exact bytes they built and reopened,
while EXP-524 remains the authoritative failed attempt to exercise its paper-artifact reproduction
contract. They are withdrawn as the public candidate chain. Before 0.11.3 can replace them, the
focused correction tests, complete 427-test quality gate, independent quality validation,
deterministic archive build/reopen, release-bound PDF validation, and a from-scratch archive-source
run must all pass. A successful author-operated archive-source run still does not claim a detached
public commit, DOI reproduction, third-party independence, human review, or submission readiness.
