# Clean-environment reproduction protocol

- Status: protocol prepared; final execution requires an author-approved public commit and archive
- Required quality runtime: Ubuntu 24.04, CPython 3.12, CPU execution, and a fresh virtual
  environment; the optional full refit uses a separate GPU environment
- Evidence owner: independent reproducer identified in `research/EXTERNAL_REVIEW_PACKET.md`
- Raw-data rule: do not copy Paderborn raw signals into the public evidence archive

This protocol separates three claims that must not be conflated: code quality in a clean checkout,
validation of the released evidence archive, and full model refitting from independently acquired
raw data. The submission gate requires the first two. A third-party full refit is stronger evidence
but may be limited by data licences and GPU time.

## 1. Freeze the reviewed revision

The corresponding author supplies a concrete Git commit, archive DOI, archive SHA-256, external
release-manifest SHA-256, final artifact-manifest SHA-256, and the exact test count declared by the
hash-locked EXP-461V validation. The reproducer records them before running any command and
verifies that the checkout is detached at exactly that revision.

```bash
export SMARTVALVE_REPRO_COMMIT='<40-or-64-character-commit>'
export SMARTVALVE_EXPECTED_TEST_COUNT='<exact-positive-integer-from-EXP-461V>'
export SMARTVALVE_REPRO_ROOT="$(mktemp -d)"
mkdir -p "${SMARTVALVE_REPRO_ROOT}/records"
git clone https://github.com/lkcfqy/SmartValve-AI-Twin.git \
  "${SMARTVALVE_REPRO_ROOT}/SmartValve-AI-Twin"
git -C "${SMARTVALVE_REPRO_ROOT}/SmartValve-AI-Twin" checkout --detach \
  "${SMARTVALVE_REPRO_COMMIT}"
git -C "${SMARTVALVE_REPRO_ROOT}/SmartValve-AI-Twin" rev-parse HEAD
git -C "${SMARTVALVE_REPRO_ROOT}/SmartValve-AI-Twin" status --short
```

The observed `HEAD` must equal the supplied commit and `status --short` must be empty. Retain the
terminal transcript and its SHA-256.

## 2. Create an independent locked environment

Run inside the clean checkout. Do not copy the development `.venv` or use an editable package from
another directory.

```bash
cd "${SMARTVALVE_REPRO_ROOT}/SmartValve-AI-Twin"
python3.12 --version
export SMARTVALVE_REPRO_VENV="${SMARTVALVE_REPRO_ROOT}/quality-venv"
export SMARTVALVE_REPRO_BUILD_SOURCE="${SMARTVALVE_REPRO_ROOT}/build-source"
export SMARTVALVE_REPRO_PY="${SMARTVALVE_REPRO_VENV}/bin/python"
export SMARTVALVE_REPRO_RUFF="${SMARTVALVE_REPRO_VENV}/bin/ruff"
export SMARTVALVE_REPRO_BANDIT="${SMARTVALVE_REPRO_VENV}/bin/bandit"
export SMARTVALVE_REPRO_AUDIT="${SMARTVALVE_REPRO_VENV}/bin/pip-audit"
export PYTHONDONTWRITEBYTECODE=1
export COVERAGE_FILE="${SMARTVALVE_REPRO_ROOT}/records/.coverage"
mkdir -p "${SMARTVALVE_REPRO_BUILD_SOURCE}"
set -o pipefail
git archive --format=tar "${SMARTVALVE_REPRO_COMMIT}" \
  | tar -xf - -C "${SMARTVALVE_REPRO_BUILD_SOURCE}"
python3.12 -m venv "${SMARTVALVE_REPRO_VENV}"
"${SMARTVALVE_REPRO_PY}" -m pip install --require-hashes -r build-requirements.lock
"${SMARTVALVE_REPRO_PY}" -m pip install --require-hashes -r requirements-ci.lock
"${SMARTVALVE_REPRO_PY}" -m pip install --no-build-isolation --no-deps \
  "${SMARTVALVE_REPRO_BUILD_SOURCE}"
"${SMARTVALVE_REPRO_PY}" scripts/validate_cpu_quality_environment.py \
  > "${SMARTVALVE_REPRO_ROOT}/records/cpu-environment-validation.json"
"${SMARTVALVE_REPRO_PY}" scripts/validate_installed_lock_environment.py \
  --lock build-requirements.lock \
  --lock requirements-ci.lock \
  --allow-package smartvalve-ai-twin \
  > "${SMARTVALVE_REPRO_ROOT}/records/installed-lock-validation.json"
export SMARTVALVE_EXTERNAL_DATA="${SMARTVALVE_REPRO_ROOT}/public-data-cache"
"${SMARTVALVE_REPRO_PY}" -m smartvalve.data.external sync \
  > "${SMARTVALVE_REPRO_ROOT}/records/external-sync.json"
"${SMARTVALVE_REPRO_PY}" scripts/validate_external_artifact_status.py \
  > "${SMARTVALVE_REPRO_ROOT}/records/external-status.json"
"${SMARTVALVE_REPRO_PY}" -m pip freeze --all \
  > "${SMARTVALVE_REPRO_ROOT}/records/clean-environment-freeze.txt"
sha256sum build-requirements.lock requirements.lock requirements-ci.lock \
  requirements-research.lock > "${SMARTVALVE_REPRO_ROOT}/records/lock-sha256.txt"
```

`requirements-ci.lock` includes the research import surface but pins the PyTorch CPU wheel, so the
quality suite is executable on an ordinary review host without CUDA. The sync command downloads all
public test fixtures into a cache outside the checkout and verifies their byte counts and SHA-256
values before pytest collection; therefore a skipped public-data test is a failed gate. Record the
Python, pip, OS, CPU, RAM, GPU/driver, CUDA, data-status, and lock-file hashes. A dependency-
resolution change, missing hash, unpinned extra package, or failed data download is a failed
reproduction condition, not permission to edit the lock or skip a test silently.

## 3. Code-quality and security gates

```bash
"${SMARTVALVE_REPRO_RUFF}" check . \
  > "${SMARTVALVE_REPRO_ROOT}/records/ruff.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/ruff.stderr.log"
"${SMARTVALVE_REPRO_PY}" -m pytest -q -p no:cacheprovider \
  --junitxml="${SMARTVALVE_REPRO_ROOT}/records/pytest.xml" \
  > "${SMARTVALVE_REPRO_ROOT}/records/pytest.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/pytest.stderr.log"
"${SMARTVALVE_REPRO_PY}" -m pytest -q -p no:cacheprovider \
  --cov=src/smartvalve \
  --cov-report=term-missing \
  --cov-report="json:${SMARTVALVE_REPRO_ROOT}/records/coverage.json" \
  --cov-fail-under=75 \
  > "${SMARTVALVE_REPRO_ROOT}/records/coverage.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/coverage.stderr.log"
"${SMARTVALVE_REPRO_BANDIT}" -q -r src scripts research/scripts -ll \
  > "${SMARTVALVE_REPRO_ROOT}/records/bandit.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/bandit.stderr.log"
"${SMARTVALVE_REPRO_AUDIT}" -r requirements.lock -r build-requirements.lock \
  --disable-pip --strict \
  > "${SMARTVALVE_REPRO_ROOT}/records/pip-audit-runtime-build.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/pip-audit-runtime-build.stderr.log"
"${SMARTVALVE_REPRO_AUDIT}" -r requirements-ci.lock --disable-pip --strict \
  --vulnerability-service osv \
  > "${SMARTVALVE_REPRO_ROOT}/records/pip-audit-ci.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/pip-audit-ci.stderr.log"
"${SMARTVALVE_REPRO_AUDIT}" -r requirements-research.lock --disable-pip --strict \
  > "${SMARTVALVE_REPRO_ROOT}/records/pip-audit-research.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/pip-audit-research.stderr.log"
git diff --check \
  > "${SMARTVALVE_REPRO_ROOT}/records/git-diff-check.stdout.log" \
  2> "${SMARTVALVE_REPRO_ROOT}/records/git-diff-check.stderr.log"
"${SMARTVALVE_REPRO_PY}" -c \
  "import json, os; from pathlib import Path; from smartvalve.experiments.final_quality_gate import _coverage_percent, _pytest_counts; root=Path('${SMARTVALVE_REPRO_ROOT}/records'); counts=_pytest_counts(root/'pytest.xml'); coverage=_coverage_percent(root/'coverage.json'); expected=int(os.environ['SMARTVALVE_EXPECTED_TEST_COUNT']); assert expected > 0 and counts['tests'] == expected and counts['failures'] == counts['errors'] == counts['skipped'] == 0, (expected, counts); assert coverage >= 75.0, coverage; print(json.dumps({'expected_test_count': expected, 'pytest_counts': counts, 'coverage_percent': coverage}, sort_keys=True))" \
  > "${SMARTVALVE_REPRO_ROOT}/records/quality-topology.json"
git status --porcelain=v1 --untracked-files=all \
  > "${SMARTVALVE_REPRO_ROOT}/records/post-quality-git-status.txt"
test ! -s "${SMARTVALVE_REPRO_ROOT}/records/post-quality-git-status.txt"
sha256sum "${SMARTVALVE_REPRO_ROOT}"/records/* \
  > "${SMARTVALVE_REPRO_ROOT}/records/record-sha256.txt"
```

Required results are the exact released test count with zero failures and zero skips, coverage at
least 75%, no medium/high Bandit
finding, and no known vulnerability or unaudited dependency reported under strict collection for
the build, runtime, CPU-CI, or GPU-research lock. The CPU lock uses OSV so the local-version suffix on the
official PyTorch CPU wheel is audited instead of silently skipped by the PyPI service. Retain full
stdout/stderr and exit codes; a short “passed” note is insufficient evidence. The environment,
public-data cache, JUnit, coverage data, command logs, and hashes stay outside the checkout, while
Python bytecode and pytest's checkout-local cache are disabled. The package is built from a
`git archive` copy of the exact detached commit outside the checkout, so build-backend metadata also
cannot be hidden inside the source tree. Therefore the final empty Git status is not obtained merely
by hiding the reproduction products behind `.gitignore`.

## 4. Evidence-archive validation

Download the three release files from the author-approved DOI into a directory outside the clone:

- `smartvalve-bearing-evidence.tar.gz`;
- `release_manifest.json`; and
- `smartvalve-bearing-evidence.tar.gz.sha256`.

First compare the downloaded byte hashes with the values supplied before reproduction. Then invoke
the independent archive validator from the clean checkout:

```bash
"${SMARTVALVE_REPRO_PY}" scripts/validate_bearing_release.py \
  --archive '<download-directory>/smartvalve-bearing-evidence.tar.gz' \
  --manifest '<download-directory>/release_manifest.json' \
  --checksum '<download-directory>/smartvalve-bearing-evidence.tar.gz.sha256' \
  --archive-sha256 '<expected-archive-sha256>' \
  --manifest-sha256 '<expected-release-manifest-sha256>' \
  --output "${SMARTVALVE_REPRO_ROOT}/records/clean-release-validation.json"
```

The validator must confirm normalized member order, timestamps, ownership, permissions, internal
and external manifest equality, every member hash, absence of unexpected members, exclusion of
raw/archive inputs, and explicit inclusion flags for the artifact, manuscript, and final-local-
quality independent validations. The reproducer also checks that EXP-457 and EXP-459 declare
independent no-refit validation, that EXP-461 declares independent no-refit manuscript validation
with `submission_ready=false`, and that EXP-461V verifies all eight local checks without claiming
clean or independent reproduction. The hashes must match the reviewed artifact/manuscript package.
The archive must contain the exact EXP-459, EXP-461, and EXP-461V validation JSON files rather than
only restating their verdicts in its manifest.

## 5. Deterministic paper-artifact check

Using the paths and hashes inside the released manifest, run
`scripts/validate_bearing_paper_artifacts.py --release-input-mode` with
`${SMARTVALVE_REPRO_PY}` without invoking a model fit. Regenerate the 42-output artifact directory
twice from the same 28 locked inputs using `scripts/bearing_paper_artifacts.py
--release-input-mode`, and require identical manifests and file hashes. This explicit mode may omit
only unconsumed outputs declared by parent summaries; it still requires and hashes every manifest
input, verifies every consumed CSV/provenance file against its parent summary, and recomputes all
decisions. The default mode remains the full experiment-directory check and must not be weakened.
Inspect all SVG and PDF pairs visually, including labels, legends, grayscale encodings, physical
units, clipping, one-page PDF geometry, and matching accessible titles.

Record any platform-specific rendering difference byte-for-byte. Do not normalize or replace an
unexpected result without an issue entry and a new reviewed revision.

## 6. Optional full refit from raw data

A full refit requires the reproducer to acquire Paderborn and HUST from their official sources,
accept the applicable licences, and verify the acquisition manifest before feature extraction.
The reproducer should then execute the sealed protocols in chronological order, retain failed runs,
and compare output hashes and numerical tolerances with the released summaries. Raw files remain
outside the repository and archive.

Create a separate environment for that optional GPU work; do not replace the CPU wheel in the
quality environment in place:

```bash
python3.12 -m venv .venv-research
.venv-research/bin/python -m pip install --require-hashes -r build-requirements.lock
.venv-research/bin/python -m pip install --require-hashes -r requirements-research.lock
.venv-research/bin/python -m pip install --no-build-isolation --no-deps .
.venv-research/bin/python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

Because GPU libraries and deterministic kernels can differ across hardware, a numerical mismatch
must be reported with exact environment evidence. It is not automatically proof of scientific
failure, but it prevents a claim of bitwise full-refit reproduction until explained.

## 7. Completion record

The independent reproducer completes the reproduction section of
`research/EXTERNAL_REVIEW_PACKET.md` with:

- identity, affiliation, relationship to the authors, and conflict statement;
- exact commit and all archive/manuscript hashes;
- machine and environment inventory;
- transcript and generated-report SHA-256 values;
- deviations and unresolved issue IDs; and
- one of `independently reproduced`, `partially reproduced`, or `not reproduced`.

No automated tool or project author may fill the reproducer identity, verdict, or signature fields.
