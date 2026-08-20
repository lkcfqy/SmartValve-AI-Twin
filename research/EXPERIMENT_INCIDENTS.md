# Experiment incident log

This append-only log records interruptions that prevent a recorded experiment from reaching its
own terminal metadata state. Interrupted outputs are retained for audit but are never promoted to
paper evidence.

## 2026-08-19 — EXP-456 Paderborn raw architectures

- Detection time: `2026-08-19T02:12:05Z`.
- Run directory:
  `artifacts/research/runs/EXP-456-PADERBORN-RAW-ARCHITECTURES__20260818T223720.239397Z__sealed-raw-fft-stft-protocol-sensitivity`.
- Observed state: `metadata.json` still said `running`; no matching training or recorded-run
  process existed; `stderr.log` was empty; no final architecture summary existed.
- Last outcome-blind progress record: fit `79/270`, protocol `crossed_holdout`, architecture
  `cnn1d`, fold `identity=2|setting=N15_M07_F10`, seed `41`.
- Durable checkpoint boundary: 54 completed measurement-random fits. The additional crossed fits
  were present only in the progress log because the frozen producer checkpoints predictions at
  architecture boundaries.
- Cause classification: external process/session loss. The exact operating-system cause is not
  recoverable from the empty stderr and stale parent metadata, so no narrower cause is asserted.
- Integrity decision: do not inspect outcome values, do not modify the sealed implementation, do
  not resume from partial checkpoints, and do not use any EXP-456 output in analysis.
- Recovery: rerun all 270 fits from the beginning under a new recorded-run identifier, with the
  exact command and the unchanged seal SHA-256
  `d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b`.
- Operational note: a `nohup`/`setsid` launch test was reclaimed by WSL before it created a run
  directory, so it is not an experiment and produced no experimental output. EXP-456R1 is instead
  held by a hidden Windows `wsl.exe` parent; its recorded-run and training children were verified
  alive with an empty stderr after startup.

## 2026-08-19 — EXP-464 HUST influence-audit command placeholder

- Run directory:
  `artifacts/research/runs/EXP-464-HUST-PHYSICAL-UNIT-INFLUENCE__20260819T041119.293897Z__frozen-posthoc-bearing-and-group-deletion-audit`.
- Observed state: the recorded run reached terminal `failed` status with exit code 2 after
  1.345256 seconds. PowerShell transformed the unquoted `{run_dir}/outputs` placeholder into
  encoded-command tokens, so the producer received no value for `--output-directory`.
- Integrity decision: retain the failed command, metadata, and stderr; it produced no scientific
  output and no deletion effect was inspected.
- Recovery: EXP-464R1 repeated the exact frozen inputs and implementation with the placeholder
  passed literally. No analysis rule, prediction, endpoint, or hash lock changed.

## 2026-08-19 — EXP-466 final-quality preflight stopped for GPU isolation

- Detection time: `2026-08-19T05:15:42Z`.
- Run directory:
  `artifacts/research/runs/EXP-466-FINAL-QUALITY-PREFLIGHT__20260819T051037.331336Z__end-to-end-seven-check-local-gate-preflight`.
- Observed state: the preflight had completed Ruff and its first 380-test JUnit run. During the
  coverage rerun, `nvidia-smi` showed the coverage pytest process as a second CUDA client beside
  the sealed EXP-456R1 raw-training process, with total device use 7,186 MiB of 10,240 MiB.
- Integrity decision: terminate only the resolved coverage child PID `950397` rather than permit an
  optional preflight to continue sharing the experimental GPU. The quality runner retained all
  completed logs, marked coverage exit `-15`, emitted a failed summary, and the recorded wrapper
  reached terminal `failed` status with exit code 1 after 368.566195 seconds.
- Scientific scope: EXP-466 is a software-gate preflight, produced no paper result, and is never
  promoted as final-quality evidence. EXP-456R1 remained alive, its stderr stayed empty, and its
  inputs, code, seeds, and model process were untouched. The short concurrent interval can affect
  wall-clock timing, so raw fit duration is not used as an architecture-efficiency claim; the
  frozen score/interval endpoints are unchanged in definition.
- Recovery: do not rerun another CUDA-capable full-suite preflight while EXP-456R1 is active.
  EXP-461Q/461V execute only after the raw experiment, independent validator, artifacts, and
  empirical manuscript have completed.

## 2026-08-19 — EXP-471G isolated public-data sync TLS failure

- Run directory:
  `artifacts/research/runs/EXP-471G-CPU-REPRO-PUBLIC-DATA-SYNC__20260819T061222.022102Z__isolated-hash-verified-public-fixture-sync`.
- Observed state: terminal `failed`, exit code 1 after 21.433860 seconds. Four small fixtures had
  passed their byte/SHA-256 locks; the UCI request ended during TLS negotiation with
  `ssl.SSLEOFError`, wrapped as `urllib.error.URLError`. No incorrect payload was accepted and no
  final UCI file was installed.
- Integrity decision: retain the run, traceback, four verified cache entries, and absent fifth
  entry. Do not label a transient transport error as a dataset-integrity failure or silently skip
  the dependent tests.
- Recovery: add bounded three-attempt HTTPS retry without weakening allow-list, byte-count,
  SHA-256, or atomic-replacement checks; force-reinstall the non-editable wheel as EXP-471H; rerun
  sync as EXP-471I and all-five status validation as EXP-471J. Both validations passed.

## 2026-08-19 — EXP-472 isolated CPU suite cache-scope assertion

- Run directory:
  `artifacts/research/runs/EXP-472-CPU-ISOLATED-FULL-PYTEST__20260819T061607.645863Z__zero-gpu-full-suite-with-public-fixtures`.
- Observed state: terminal `failed`, exit code 1 after 208.499623 seconds; 383 tests passed and one
  failed. The failing test required a configured cache directory to be literally named `external`,
  although the clean protocol intentionally used an outside-checkout `public-data` directory.
- Integrity decision: retain the complete 384-test JUnit topology. The failure is a false directory-
  name constraint, not permission to move public data back into the checkout or mark the run
  successful.
- Recovery: replace the name assertion with the intended safety invariant that the cache neither
  equals nor descends from `data/generated`; rerun all tests from scratch as EXP-472R1. The rerun
  passed 384/384 with zero failures, errors, or skips; EXP-473 then passed the independent coverage
  rerun at 77.95%.

## 2026-08-19 — EXP-459 artifact-validator serialization precision

- Run directory:
  `artifacts/research/runs/EXP-459-BEARING-PAPER-VALIDATION__20260819T115822.883637Z__independent-no-refit-bearing-paper-artifact-vali`.
- Observed state: terminal `failed`, exit code 1. The artifact generator stored the raw-family
  median in a CSV field rounded to 12 decimal places, while the independent validator compared it
  for exact equality with the full-precision summary value. The values differed by
  `6.494804694057166e-14`; no model, prediction, endpoint, bootstrap draw, or advancement decision
  differed.
- Integrity decision: retain the failed run and its stderr. Do not weaken the scientific gate or
  replace the full-precision decision value. Failed-run metadata and stderr SHA-256 values are
  `598604624a5c0de3cd0a67c9783c188044dd2a35f544bd7eb230b57be2c51034` and
  `d132b16babe955cc3c8a5831427391727a942b6e92351aa2d0549891de4bde58`.
- Recovery: validator 0.4.1 retains the full-precision summary for the decision and accepts the
  independently recomputed 12-decimal CSV representation only when its absolute difference is at
  most `1e-12`. A negative regression test rejects larger drift. EXP-459R1 reran validation only,
  performed no refit, and passed with the observed `6.49e-14` difference recorded explicitly.

## 2026-08-19 — EXP-514 release-0.11.1 archive-source clean reproduction

- Run directory:
  `artifacts/research/runs/EXP-514-ARCHIVE-SOURCE-CLEAN-REPRODUCTION-V0.11.1__20260819T131527.442562Z__fresh-noneditable-public-data-quality-and-artifa`.
- Observed state: terminal `failed`, exit code 1 after 832.788963 seconds. The run verified the
  external 0.11.1 archive and manifest bytes, extracted the archive twice outside the development
  checkout, created a fresh CPython 3.12 environment, installed the build and CPU-CI locks with
  hashes, installed the package without editable mode, passed the CPU-only and installed-package
  lock validators, reacquired all five public fixtures into a fresh 79 MiB cache, froze the
  environment, and passed Ruff. Its first full pytest pass then collected 427 tests with seven
  failures, zero errors, and zero skips.
- Failure classification: release-source topology, not scientific-result disagreement. The
  0.11.1 archive omitted `Dockerfile`, `.dockerignore`, six paper support documents,
  `paper/generated` and its eight metric inputs, and checked-in service benchmark fixtures. The
  provenance recorder also assumed `git ls-files` was available, and the RESS PDF validator
  derived its project root from editable-source directory depth. These defects explain all seven
  failures; no model, prediction, score, interval, bootstrap draw, figure value, or manuscript
  claim was recomputed or contradicted.
- Integrity decision: retain release 0.11.1 and its successful internal EXP-510/511 byte validation
  as evidence for what that archive contained, retain EXP-514 as a failed clean-reproduction
  attempt, and withdraw 0.11.1 as the public candidate. Do not continue to coverage or relabel the
  run as partially passed.
- Recovery: amendment 002 defines release 0.11.2, adds the missing source/evidence topology, gives
  the recorder a bounded no-Git filesystem fingerprint, and routes PDF source identity through the
  explicit project-root contract. EXP-515's non-public structural preflight included 531 files and
  the previously failing 34-test family passed from its extracted, non-editable-install source.
  EXP-516/517 then passed and independently validated the full 427-test local quality topology;
  final post-record-freeze release and clean-reproduction runs remain separately required.
- JUnit, failed reproduction summary, and recorded-run metadata SHA-256 values are
  `04d5f4f67cce3da809ba9f19ca010a133842b4e9829e12b21f47c86a6e50c011`,
  `45c7c2db613c916addc09b987420897b7ed7f5cda2a5e00dd552f24d4964d563`, and
  `e56bae8e29fda946c4c00583224a2d3e6a0615d7724e46e019e0f61a2f659dda`.

## 2026-08-19 — EXP-524 release-0.11.2 raw-free artifact-reproduction boundary

- Run directory:
  `artifacts/research/runs/EXP-524-ARCHIVE-SOURCE-CLEAN-REPRODUCTION-V0.11.2__20260819T141651.043029Z__fresh-noneditable-archive-source-quality-and-art`.
- Observed state: terminal `failed`, exit code 1 after 1,047.531110 seconds. Two independent archive
  extractions, the fresh Python 3.12 environment, non-editable install, CPU/lock validation, fresh
  five-fixture data sync, Ruff, all 427 tests, `78.07569752078962%` coverage, Bandit, three strict
  dependency audits, archive reopening, and released final-quality validation all exited zero.
  Step 20 then failed because the general artifact validator followed a parent summary to the
  deliberately excluded `vibration_windows.npy` raw signal array.
- Failure classification: release-reproduction interface, not a scientific result or release-byte
  disagreement. The 28 inputs consumed by the paper package are present in the release, but both
  the generator and validator required every additional output declared by their parent summaries.
  That default is appropriate with full experiment directories and incompatible with the declared
  raw-data-free release boundary.
- Integrity decision: retain EXP-520/521 as correct build/reopen evidence for 0.11.2, retain
  EXP-524 as failed, and withdraw 0.11.2 as the public candidate. Do not omit the failed artifact
  step or relabel the preceding quality checks as a complete reproduction.
- Recovery: amendment 003 defines release 0.11.3 and an explicit release-input mode. Default mode
  remains strict. Release mode may omit only unconsumed parent-summary outputs while requiring and
  hash-checking all 28 manifest inputs, verifying each consumed CSV/provenance input against its
  parent summary, recomputing all decisions, and comparing all 42 generated outputs. EXP-525 passed
  the existing 22-test artifact/release family without increasing the 427-test topology; the final
  full quality, archive, and from-scratch reproduction chain remains required.
- Failed summary, JUnit, failing stderr, and metadata SHA-256 values are
  `227331201e73b71803c74149ceb6a3bb025c2648e6297a5700f674a737976887`,
  `74b0a8de97d19dfc856cbf30f4dcf945cf36138ddc48f785a7d246224d8ef6ad`,
  `bcffb2cbe1747a0d05f718680ed05fa7dc43a6d0e205bebead3711b01de8e18b`, and
  `950c9655c7fe7de95700fb700af3e7ab614140faecadc340aa0a913b8e00e6d3`.
