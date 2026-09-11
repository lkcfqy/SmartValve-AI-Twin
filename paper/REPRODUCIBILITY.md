# Reproducibility appendix

## Scope and source state

The development checkout is `/home/fqy/lkcproject/SmartValve-AI-Twin` under WSL2 Ubuntu 24.04.
Public research revision `c9cd069caa51943e6413e105fc1f4775704643c5` is available on branch
`research/bearing-protocol-audit-0.11.3`; its GitHub Actions run passed the complete test, coverage,
security, Compose, and image-build gate. The earlier scientific runs retain their original
repository state rooted at baseline commit `0dc184370e37833c74f32c529a7ef30d5df351ce`, including the
then-uncommitted research additions. Every formal run captures Git status, diff hash, source-tree
fingerprint, command, UTC timing, environment, hardware, input hashes, stdout, stderr, exit status,
and output hashes rather than rewriting that history after publication.

The final experiments used Python 3.12.3, NumPy 2.5.1, pandas 2.3.3, SciPy 1.18.0, scikit-learn
1.9.0, and PyTorch 2.13.0+cu130. The machine exposed 16 logical CPUs, approximately 15 GiB WSL
memory, and an NVIDIA RTX 3080 with 10,240 MiB VRAM.

## Environment

The repository separates three dependency roles: `requirements.lock` is the deployment runtime,
`requirements-ci.lock` contains development, security, and research imports with
`torch==2.13.0+cpu` for ordinary review hosts, and `requirements-research.lock` pins the Ubuntu GPU
full-refit environment. `build-requirements.lock` separately fixes the installer and wheel-build
toolchain, including pip itself. For a clean CPU quality run from the project root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r build-requirements.lock
.venv/bin/python -m pip install --require-hashes -r requirements-ci.lock
.venv/bin/python -m pip install . --no-build-isolation --no-deps
```

For an optional full GPU refit, create a separate virtual environment and replace only the CI-lock
line above with `requirements-research.lock`; do not mutate the reviewed CPU environment in place.

Do not silently update the locked packages for a canonical rerun. A newer-library run is a
portability experiment and must receive its own experiment ID.

On 2026-08-19, dependency audit identified fixed advisories in the previously locked
`cryptography 49.0.0` and `GitPython 3.1.51`. The runtime and CI locks were regenerated with
`cryptography 50.0.0` and `GitPython 3.1.59`, and the new research lock was generated from that
corrected state. All three application-environment locks are audited by the final gate. The active
sealed GPU process was not hot-upgraded. Final clean reproduction installs the corrected locks into
a fresh environment and installs the project from an external `git archive` copy of the exact
detached revision, keeping build-backend metadata outside the source checkout.

The same audit found that the old build lock used yanked `build 1.5.1`, did not pin pip, and carried
`setuptools 82.0.1` with `PYSEC-2026-3447`. The corrected build lock fixes non-yanked
`build 1.5.0`, `pip 26.1.2`, and `setuptools 84.0.0`; the runtime quality command audits that build
lock together with `requirements.lock`.

## Data integrity

`data/external/manifest.json` records the allow-listed Cranfield, SKAB, and UCI inputs with byte
counts and SHA-256 values. Paderborn uses the separately sealed 32-archive inventory. The decisive
D2 sequence is:

1. final pre-access seal: EXP-374, seal SHA-256
   `b907e1e0e6876e1e35166a526a6d019df83e1587246784588fb0bda44a71efe1`;
2. complete 2,560-MAT structure inventory: EXP-400;
3. frozen v0.5 three-channel/72-feature extraction: EXP-406, metrics SHA-256
   `4425947919dc8e6730c7cf83dc8e33a8b58a64e07d777cd14527806667663de2` and feature-matrix SHA-256
   `9d9a6d0d48cc590ec842006a779454d76ad299072978e0d0b094b138ddf56d29`;
4. independent feature validation: EXP-407;
5. structural-exclusion-aware split, fold, and expected manifests: EXP-408 through EXP-411;
6. final post-feature/pre-model execution seal: EXP-416, SHA-256
   `e87ceabf74aa86e41a616fe3f796738d122542412b71ae75aade07644679560b`.

The single unreadable primary record is `N15_M01_F10_KA08_2.mat`. Its exclusion is structural,
recorded before outcome modeling, and uncompensated: the primary count is 2,319, not 2,320.

## Canonical final runs

| Stage | Run | Principal output SHA-256 |
|---|---|---|
| D0/D1 base comparison | EXP-340-DG-SELECT | metrics `7d885242f5bd74bed650488c7d4dbd4483ab1153ec330914d98edf838a46827b` |
| D0/D1 selective comparison | EXP-342-SELECTIVE | metrics `4caa1e4bb2a07b98be6af2752a0b310f751b8bd0f7fda34b03578ebfbd9983e6` |
| D0/D1 physical inference | EXP-344-BOOTSTRAP | metrics `cfcaf5a16e8d30a4b52a0a6bcb6237fe3dff8b1fe416d5e8e8ac1dafe503e246` |
| D0/D1 component attribution | EXP-347-RATIO-ABLATION | metrics `b7edab2bf7d1703008c93805af90627cba4a63478c468101e183cf7178d2e8a7` |
| D2 base comparison | EXP-417-PADERBORN-D2-BASE | metrics `167d2e04bede2dfbd5b37eb6c63bbef8b51b6c3c58d8f68624fca3cf64fa1c95` |
| D2 base validation | EXP-418B-PADERBORN-D2-BASE-RECONCILE | validation `b14fcb57598ae3f4c7d03fba28c87f4ae2dc47f6a30dd8085d61a3bc0b80d6b3` |
| D2 selective comparison | EXP-419-PADERBORN-D2-SELECTIVE | metrics `234a9b3f3d2809be7d5f670dfb752248596d0d8c1171cc47434aa96ea92247aa` |
| D2 selective validation | EXP-420B-PADERBORN-D2-SELECTIVE-RECONCILE | validation `7a57d075056778e39d0ff847c8a8944c97c65fa2bb90804558babae30ef3a75d` |
| D2 bearing inference | EXP-421B-PADERBORN-D2-BOOTSTRAP | metrics `465cfe62da9b60c75484992b6b0d2b13cb97197f5e9b390955086160986b69f8` |
| Six-test family | EXP-422B-CONFIRMATORY-FAMILY | metrics `0143b1e6703a1941f636001b298ce29837386258127068e715fe4ffe73854476` |
| Manuscript artifacts | EXP-423E-MULTIRIG-PAPER-ARTIFACTS | manifest `bceeefe1a555e1997189dadc734c9a5e7dd770b72871c488ce254c490a1ec9a6` |

### Bearing-protocol continuation

| Stage | Run | Principal output SHA-256 |
|---|---|---|
| Paderborn fusion four-protocol audit | EXP-434B-PADERBORN-NEURAL-PROTOCOL | summary `0a717c6bc1e4d94182b11f91502397d32a3816d86931ed5369316714a2a13a9e` |
| Fusion independent validation | EXP-456A-PADERBORN-PROTOCOL-VALIDATION | validation `03428d40112509c08ffe11bf56ca172a6975b5570d653bc5ac1fbf5a0ece8099` |
| Classical sensor audit/validation | EXP-436/437 | summary `fe12ce9d8380274d0485a9c0577c502bb53c424fa7428641e7f27f94a5e8b6f2`; validation `17777e4813042d32baf7d4930747dd1a9cc77708de78643bd0f0a69e0624fb64` |
| Vibration neural audit | EXP-438-PADERBORN-NEURAL-VIBRATION | summary `e30592e1b0f7b94c012f99c10a2f5374907a3fa76fd5d3f6773796f47eeeb5fb` |
| HUST signal-unopened replication | EXP-445/447 | summary `3f721ff50cc72b845d5ce16a3c7ef987ae5c33cb0d69bfab0804a9be38b5d61a`; validation `ba9ceee356fe8cc04ddfe1a28f6e46038fd0c60c4ea374df196400b22fdf6c6a` |
| HUST equal-volume control | EXP-449/450B | summary `23b898440a6a09c4efd21ea6e9faec16ca637989a5310e4fa69f8067f5e4833c`; validation `b7e13cf20ff51d06690e56b0f1d45102ecba23dc0df56ad4a7790e4c5d263abe` |
| HUST post-hoc physical-unit influence | EXP-464R1/465 | summary `431e580c9ee2d3489980fd4edad31151f97eeff343656473d1df8504c2406e18`; validation `dfb88a40883c71059eab856bfc6e25247192431b83a66ebbdc6f1bbccd0e587a` |
| Motor-current neural audit | EXP-451-PADERBORN-NEURAL-CURRENT | summary `47ce349cc8ab633d51384614310bc926bcff7a8b5f294f2e91318a9765e51e46` |
| Combined three-sensor attribution | EXP-452/453 | summary `72f1bbca7ae6fa2e50f105ff699a2022b7705ca8cda0dd2ea43c341edb8b23ea`; validation `acb71e10125a710681ae3fc8fee72ee7f691947d21932955af753a5d5301c5cc` |
| Hash-locked raw windows | EXP-455-PADERBORN-RAW-WINDOWS | summary `af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191` |
| Raw/FFT/STFT architecture sensitivity | EXP-456R1-PADERBORN-RAW-ARCHITECTURES | summary `5781106c9b192df2943a2deff1ab62473aa29916843c6df78a67bf189278ee7f` |
| Independent raw metric/bootstrap validation | EXP-457-PADERBORN-RAW-VALIDATION | validation `822f6c504b66c6398c56b6480bc1139a068b1fd7d3457918799865deca0858b0` |
| Independent pre-outcome raw topology validation | EXP-477-PADERBORN-RAW-TOPOLOGY-VALIDATION | validation `3e3f9f4886e650b50c8d3bc914b6a4cd711e24ef8b41c556cf8eb583772139e6` |
| Final bearing artifacts | EXP-458/459R1 | manifest `4abf54dbdb8dd89c0f998ac8e96dc59d51734d28ee5e96f55c1dc15197b4aec7`; validation `425c0c4861aaee9c6c004c121b0334d5345c34e1e75cdb40adc440f810b8243d` |
| Empirical manuscript | EXP-460/461 | manuscript `784392b35d9c8a69c9554e01c6ed5b936a75716c276a8a7aca47244f6a44532f`; validation `d77dac66e0a34c0f9c4f087bd3a14a11f06782f0a43e48fa7e9c6073ff794f35` |
| Final amendment-003 quality | EXP-526/527 | summary `144e1da0c173b06e5ad724a9e6317dd6e995ea6a2f2172772fdf4e8ddd301f24`; validation `0879773d4e0dc148d5f873595213f4871a2df34606c9bb483f9579a939dc860d` |
| Withdrawn 0.11.1 archive | EXP-510/511/514 | archive `b12b4210e031031da28e2689f8da56b9c19408dca5ad0421fa6c196358ce4327`; archive-source run failed 7/427 |
| Withdrawn 0.11.2 archive | EXP-520/521/524 | archive `7dc8b4fa4dc73acfdd7808c47f0d99dd3aa8a1c30e49acd59c1650157305d7b4`; archive-source quality passed but raw-free regeneration interface failed |
| Final 0.11.3 archive | EXP-528/529 | archive `c86ea0c8413702c48db752350caf6dda1ca80015adf306caf1bf99682facf66f`; manifest `cf19a4a8df140a095efaa5256ac506d2d8ad676d50794e505515d09276cb9418` |
| 0.11.3 archive-source reproduction | EXP-532R1 | summary `008ba0617ab24897dd3e21bc5ca4fb74b900ae6f082e62f040da55af9c6a5174`; 427/427 tests and exact 42-output two-pass regeneration |
| Detached public-commit reproduction | EXP-533 | commit `c9cd069caa51943e6413e105fc1f4775704643c5`; summary `bde9664ab3aef91d4dfa48151c18411829b494d4e300ccb54799254b3f8ffcc8` |
| Empirical five-figure PDF preflight | EXP-490/491 | PDF `c041274804f7818b97f002d47ccde97baf23e67c42d6ad4506d89b73daf4b463`; validation `09ff92a7473a05c83f7673eb19eb52efb2f8459153639c97f12d6ef8bc263939` |

EXP-456 raw/FFT/STFT fitting was externally interrupted at outcome-blind progress 79/270 and is
excluded from evidence. EXP-456R1 completed the exact from-scratch recovery under the unchanged
seal: 270 fits, 166,968 window predictions, 41,742 seed-recording predictions, 13,914 ensemble
predictions, and 270 traces. Raw 1D, log-FFT, and log-STFT random-minus-crossed effects were
`0.363114`, `0.170716`, and `0.205668`; all three physical-bearing interval lower limits exceeded
zero and the frozen median-at-least-0.15 rule passed. EXP-457 independently recomputed the complete
metric/bootstrap/gate path without producer calculation imports or model refitting. EXP-477 matched
every observed key against pre-outcome EXP-476 and declared `refit_performed=false`,
`aggregate_metrics_recomputed=false`, and `gate_outcome_read=false`. EXP-476 contains only expected
keys and physical metadata, with no probability, score, interval, rank, model state, or gate
outcome. Validator amendment 001, made before any EXP-456R1 result was read, and all superseding
source hashes remain recorded in `research/PADERBORN_RAW_VALIDATOR_AMENDMENT_001.md`.

EXP-458 then generated the exact 28-input/42-output artifact package. EXP-459 is retained as a
validator-only failure caused by a `6.494804694057166e-14` difference between the full-precision raw
median and its 12-decimal CSV serialization. Validator 0.4.1 keeps the scientific decision at full
precision, accepts that redundant serialization only within `1e-12`, rejects larger drift, and
passed EXP-459R1 without refitting. EXP-460/461 rendered and independently validated the empirical
manuscript. EXP-518/519 passed and independently validated 427/427 tests, 8/8 fixed checks, and
`78.16118753400171%` coverage after amendment 002. EXP-514 retained seven archive-source failures
from 0.11.1. EXP-520/521 then built and reopened 0.11.2, but EXP-524 retained a later failure at the
raw-free artifact-regeneration boundary after its 427-test, coverage, security, dependency, archive,
and quality-validation prefix passed. Amendment 003 and EXP-525 define and focus-test the bounded
release-input mode. EXP-526--531 complete the 0.11.3 quality/archive/PDF chain; EXP-532 is retained
as a runner-boundary failure, EXP-532R1 passes the full archive-source reproduction, and EXP-533
passes the author-operated detached public-commit reproduction.
EXP-490/491 rendered and independently validated the 24-page five-figure watermarked PDF; the
24/24-page and 5/5-figure bounded visual review is recorded in
`research/BEARING_VISUAL_QA.md`. EXP-533 claims an exact clean detached checkout but explicitly not
third-party independence, DOI acquisition, human approval, or submission readiness; the other
author-operated records retain their narrower claim flags.

Use the timestamped directory names in `paper/README.md` and `research/EXPERIMENT_LEDGER.md` when
locating a run. Each directory's `command.json` is the authoritative expanded command.

## Reconciliation audit

Four unmodified post-outcome checks failed and are retained: EXP-418, EXP-420, EXP-421, and
EXP-422. The permitted corrections are fully specified in:

- `research/protocols/paderborn_compound_row_index_reconciliation_v0.1.md`;
- `research/protocols/paderborn_selective_compound_index_reconciliation_addendum_v0.1.json`;
- `research/protocols/paderborn_bootstrap_structural_exclusion_reconciliation_v0.1.md`; and
- `research/protocols/paderborn_confirmatory_structural_reconciliation_v0.1.md`.

The corresponding wrappers change coordinate/count/version acceptance only. They do not retrain a
model, edit a prediction, impute the missing record, replace a bootstrap draw, select a different
endpoint, or alter the Holm procedure. The exact source/specification hashes are in
`research/D2_FINAL_DECISION.md`.

## Regenerate tables and figures

```bash
make paper-artifacts
```

The target regenerates both disjoint deterministic packages in `paper/generated/`:

- legacy manifest SHA-256:
  `8647cbebaa00b6f616af28a2d0d2f846ae86d4d4d50905d12646a109cab619ed`;
- multi-rig manifest SHA-256:
  `bceeefe1a555e1997189dadc734c9a5e7dd770b72871c488ce254c490a1ec9a6`.

The multi-rig generator refuses any of its four final JSON inputs whose SHA-256 differs from the
locked value. Provenance paths are project-relative, so the manifest is checkout-independent.

### Final bearing submission capsule

The bearing-specific generator is intentionally unavailable as a partial-result shortcut. Its
default mode requires six completed summaries, every output those summaries declare, six
independent validations that explicitly declare `refit_performed=false`, and the hash-locked
raw-window provenance. It then emits six main tables,
four supplementary tables, five deterministic SVG audit sources, five normalized vector-PDF
submission exports, captions, and one relative-path manifest. The restricted raw NPY array is
verified against the window summary but is not listed as a redistributable manuscript input; its
row index and extraction traces are retained. CairoSVG renders each source and pypdf replaces the
volatile creation/modification metadata with fixed values; repeated conversion is tested for
bitwise equality.

For the raw-data-free evidence archive only, both CLIs accept an explicit `--release-input-mode`.
It permits absent outputs that a parent summary declares but the 28-input paper package does not
consume. It still hash-checks all 28 manifest inputs, every consumed CSV against its parent
summary, the raw-window index and extraction traces, and all six validations. The default remains
strict; tests require default failure when the raw NPY is absent, exact 42-output/manifest equality
in release mode, and release-mode failure when a consumed index is absent.

`scripts/validate_bearing_paper_artifacts.py` is the independent post-generation gate. Without
calling the generator, it re-hashes the fixed 28-input/42-output topology, requires all six no-refit
validations, recomputes all headline ranges and
method-level intervals, rechecks the two cross-summary equality constraints, parses every SVG, and
requires redundant dash/marker encodings in figures that otherwise rely on color. It also opens all
five PDFs independently, requires one page per figure, and verifies their normalized timestamps.
It also requires each PDF's embedded title to equal the accessible title of its same-stem SVG,
preventing a hash-consistent but semantically mismatched figure pair. Its result must be retained
with the release.

After that validation, `scripts/render_bearing_manuscript.py` replaces seven explicit empirical
hold blocks in the integrated template using only the locked manifest headline values. It renders
the same bounded structure whether the raw sensitivity passes or fails, cites Table 6 and Figure 3,
and preserves all human-owned authorship, funding, and conflict markers with
`submission_ready=false`. `scripts/validate_bearing_manuscript.py` does not call the renderer: it
independently verifies the template, manifest, manuscript, and render-report hashes; the abstract;
all three raw effects and intervals; pass/fail wording; the post-hoc HUST deletion findings;
39-contrast counts; all 15 artifact callouts;
word count; and retained human holds. EXP-460/461 record those two steps only after successful
no-refit EXP-459R1; failed EXP-459 remains in the incident and experiment logs.

After EXP-457, `scripts/validate_ress_submission.py` checks that the journal abstract is identical
in the manuscript and submission materials, contains at most 200 words, and has no hold marker; it
also enforces one to seven keywords, three to five highlights of at most 85 characters, the 13,000-
word manuscript ceiling, and the data/code/AI statements. The paper manifest stores the exact
headline score ranges and method-level effects, and `scripts/generate_ress_submission_materials.py`
renders the abstract and highlights from those hash-locked values rather than copied numbers. The
validator takes `paper/references.bib` as a required input, rejects missing citation keys, duplicate
BibTeX keys, and duplicate DOI values, and records the bibliography hash plus cited/uncited counts.
This makes the exact reference state part of the final preflight instead of relying only on the
Markdown renderer. It also requires explicit manuscript callouts for all six main tables, five main
figures, and four supplementary tables, preventing a generated-but-orphaned upload artifact. The
renderer refuses to issue the publisher-recommended past-tense AI declaration unless
`--human-review-confirmed` is explicitly supplied; this flag is reserved for the human authors
after they have checked the analyses, citations, visualizations, and final text. The declaration
uses Elsevier's current full section title and states the named tool, purpose, human review, and
responsibility. It also requires `--code-commit-sha` to be a concrete nonzero 40- or 64-character
lowercase revision and `--artifact-doi` to be an `https://doi.org/...` identifier. Generic
repository/archive promises cannot pass the final text validator.
Validator version 0.9.0 also requires a separate editable `.txt` file whose filename contains
`highlights`. `scripts/generate_ress_submission_materials.py` derives this upload from the same
hash-locked Highlights section, and the validator requires its ordered bullets to match that
section exactly; a renamed, stale, non-bullet, or non-editable companion cannot pass.
`research/AI_ASSISTANCE_RECORD.md` separately records the research and writing uses, technical
controls, and still-pending human review evidence; it is included in the deterministic release.
The validator requires separate manuscript sections for data availability, code/artifacts, and the
full AI declaration; the manuscript and submission-material declarations must normalize to exactly
the same text, and both code sections must carry the same concrete commit and artifact DOI.
It also requires non-empty CRediT, funding, and competing-interest sections. The working manuscript
contains explicit author-action markers in those sections, so it cannot pass until the human
authors provide and approve the facts rather than allowing an automated no-conflict/no-funding
assumption.
After the empirical manuscript and each release-source amendment,
`scripts/run_final_quality_gate.py` executes the fixed eight-check local gate: full Ruff, pytest
with JUnit output, a second coverage run, medium/high Bandit, strict runtime-plus-build, CPU-CI,
and GPU-research lock audits, and `git diff --check`.
`scripts/validate_final_quality_gate.py` independently checks the
command topology, every log hash, test/error/skip counts, and coverage JSON. Both reports explicitly
deny clean-checkout, independent-reproduction, human-review, and submission-readiness claims.
All dependency audits use strict collection. The CPU-CI lock is queried through OSV because the
default PyPI service otherwise reports the official `+cpu` local-version wheel as skipped despite a
zero exit code.

`scripts/build_bearing_release.py` then builds a deterministic local evidence archive containing
every summary-declared result, generated paper artifact and its hash-locked metric inputs, audit
document, Python source file, test, dependency lock, final local-quality log, required Docker/CI
support file, checked-in benchmark/validation fixture, and all six exact shell launchers that
executed EXP-456R1 and orchestrate EXP-457--463 plus EXP-476/477. Runtime stdout/stderr logs remain
outside the public source tree, while the launchers are content hashed as reproduction source. The
builder requires EXP-459R1's independent 28-input/42-output artifact validation, EXP-461's
independent empirical-manuscript validation, the selected independent final-quality validation,
and EXP-477's independent exact-key validation against the EXP-476 pre-outcome manifest. It checks
their no-refit, manifest-hash, count, coverage, gate-access, and `submission_ready=false` fields and
stores the pre-outcome manifest and all four validation JSON files as named evidence members.
Archive order, timestamps, ownership, and permissions are normalized.
`.mat`, `.npy`, partial-download, RAR, and ZIP inputs are rejected. The builder performs no upload
and cannot substitute for author approval of a public commit or archival DOI.

```bash
.venv/bin/python scripts/build_bearing_release.py \
  --artifact-manifest '<EXP-458>/outputs/bearing_artifact_manifest.json' \
  --artifact-validation '<EXP-459R1>/outputs/validation.json' \
  --empirical-manuscript '<EXP-460>/outputs/BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md' \
  --manuscript-render-report '<EXP-460>/outputs/render_report.json' \
  --manuscript-validation '<EXP-461>/outputs/validation.json' \
  --final-quality-summary '<post-record-freeze-quality>/outputs/final_quality_gate_summary.json' \
  --final-quality-validation '<post-record-freeze-validation>/outputs/validation.json' \
  --raw-topology-manifest '<EXP-476>/outputs/expected_raw_topology_manifest.json' \
  --raw-topology-validation '<EXP-477>/outputs/validation.json' \
  --output-directory '<release-output-directory>' \
  --project-root .
```

A separate `scripts/validate_bearing_release.py` process reads the archive back, compares its
internal and external manifests, recomputes every member digest, and rejects extra members, unsafe
paths, non-file entries, missing validation-chain flags, or non-normalized metadata.

The retained 0.11.1 archive passed its internal byte/topology validation but later failed seven of
427 tests when EXP-514 exercised the archive as source in a fresh non-editable environment. Release
amendment 002 therefore withdraws 0.11.1 as a public candidate and defines 0.11.2: the missing
Docker/CI files, paper support material, generated-package inputs, and benchmark fixtures are now
included, while no-Git provenance and installed-package source resolution are explicit. EXP-515's
531-file non-public structural preflight passed the affected 34-test family from extracted source.
EXP-516/517 then passed and independently validated the complete eight-check development-tree gate:
427/427 tests, zero skips, `78.16118753400171%` path coverage, and all static/security/dependency
checks. Those reports retain `clean_checkout_claimed=false`,
`independent_reproduction_claimed=false`, `human_review_claimed=false`, and
`submission_ready=false`. EXP-518/519 supplied the post-freeze pair to 0.11.2; EXP-520/521 built
and reopened that archive. EXP-524 then passed the clean 427-test/coverage/security prefix but
correctly failed when the general artifact tools required an unconsumed raw NPY that the release
prohibits. Amendment 003 and EXP-525 add the bounded release-input mode and withdraw 0.11.2 as the
public candidate. Release 0.11.3 must receive a new full quality pair and complete archive-source
run. A later formal detached reproduction remains mandatory after an author-approved revision and
release DOI exist.

## Quality gates

Run the unchanged full-project checks:

```bash
make lint
make test
make coverage
```

The coverage target deliberately identifies `src/smartvalve` by filesystem path. With the pinned
NumPy 2.5/pytest-cov stack, asking coverage to resolve the importable package name can import NumPy
during source discovery and then trigger NumPy's duplicate-load guard during pytest collection.
Path-based discovery measures the same source tree without that pre-import.

The paper-package tests verify both manifests, all input hashes, every generated byte count/hash,
valid SVG XML, disjoint output ownership, relative provenance paths, the six-member family, the
single positive test, the failed internal gate, required manuscript documents, and BibTeX coverage.
The legacy PIRL-package formal gates are EXP-424 and EXP-425. Ruff passed. All 269 tests passed with no skips;
coverage was exactly 75.00% over 8,164 statements, meeting but not exceeding the frozen threshold.
The only warning was the already documented scikit-learn 1.9 `SVC(probability=True)` deprecation.
Complete logs and hashes are recorded at the end of `research/EXPERIMENT_LEDGER.md`.
Those counts do not certify the later bearing continuation; its full-project and clean-environment
gates are rerun after the raw result and final artifact generation.

An interim post-hardening `make test` on 2026-08-19 passed all 354 collected tests in 188.39
seconds with no skips and one already documented scikit-learn 1.9 `SVC(probability=True)` future
deprecation warning. The path-based `make coverage` reran all 354 tests in 425.59 seconds and
measured 77.68%, clearing the unchanged 75% gate. `make lint` and `make security` also passed; both
dependency locks had zero known `pip-audit` findings. These are interim regression checks, not
substitutes for the final recorded clean-environment gate after raw integration.

After closing the empirical-manuscript and dual-validation release chain, the 2026-08-19 local
regression passed all 366 collected tests in 195.28 seconds. A separate path-based coverage run
again passed all 366 tests in 448.27 seconds and measured 77.87% over 11,236 statements, above the
unchanged 75% threshold. Full-source Ruff and Bandit passed, both runtime and CI dependency locks
had zero known `pip-audit` findings, and `git diff --check` was clean. The only warning remained the
documented scikit-learn 1.9 `SVC(probability=True)` future deprecation. This is the final local gate
for the current source state, but it remains distinct from the clean-checkout independent
reproduction required after an author-approved revision and release DOI exist.

After integrating the frozen HUST physical-unit influence audit and Supplementary Table S4, all 373
collected tests passed again. Full-source Ruff, the medium/high-severity Bandit gate, and
`git diff --check` passed. Bandit's 15 retained findings were all low severity and concern the
existing explicit subprocess/archive tooling or false-positive password-token names. The 77.87%
coverage value above belongs to the preceding 366-test state; coverage is deliberately rerun after
the sealed raw result and final artifact chain complete rather than relabelled as a current value.

The subsequent final-quality hardening state collects and passes 380 tests. A new hostile JUnit
fixture verifies that both quality-report readers reject XML entity expansion through
`defusedxml`, closing the two medium-severity B314 findings discovered by the first Bandit pass.
Full Ruff, medium/high Bandit, both locked dependency audits, and `git diff --check` pass. A fresh
path-based preflight coverage run measures 77.94% over 11,820 statements against the unchanged 75%
floor. This is current local preflight evidence, not the formal EXP-461Q/461V transcript or a clean-
checkout independent reproduction; both remain downstream of the sealed raw result and empirical
manuscript.

The corrected CPU-lock preflight then created a fresh external virtual environment, installed the
hash-locked build and CPU-CI environments plus a non-editable project wheel, verified
`torch==2.13.0+cpu` with no compiled/available CUDA, and passed `pip check`. Exact installed-lock
parity found 120 locked packages and 121 installed packages, with the project wheel as the sole
allowed extra and no missing, unexpected, or mismatched version. A first public-data sync failed
with a retained TLS EOF. After bounded retry hardening, all five fixtures independently passed
byte/SHA-256 validation. The first 384-test run retained one cache-name-assumption failure;
the corrected rerun passed 384/384 with zero skips. EXP-473 independently reran all 384 tests under
explicit path coverage and measured `77.95036299172716%` over 11,846 statements; JUnit and coverage
JSON SHA-256 values are `2c73d4b51dfa99d5ac81a90b073df56bc13890dc07559206f8b2e60c0ef80785`
and `206eae1aadcdfbd11ee4f336760d88190bacec6f23f44c2cc4468f5a1f86a675`. This proves an
isolated zero-GPU environment preflight, not a clean checkout or independent reproduction.

Static-security scope correction (2026-08-19): earlier historical paragraphs used
"full-source Bandit" for a command that in fact scanned only `src/`. Expanding the exact gate to
`src scripts research/scripts` initially returned exit 1 with two medium-severity B310 findings in
the HUST acquisition and metadata-inventory scripts. Neither finding was suppressed. Both callers
now reject non-HTTPS URLs, non-exact Mendeley hostnames, and embedded credentials before using the
already locked `requests` dependency. CI, the Makefile, the final-quality command topology, and the
clean-reproduction protocol now use the expanded three-directory scope, while the deterministic
release also includes `research/scripts/*.py`. The post-fix Bandit 1.9.4 JSON records 42,855 lines,
zero medium/high findings, 25 low-severity detections, seven pre-existing explicitly skipped tests,
and an empty result set at the `-ll` threshold. Twenty-one focused security, quality-gate, and
release tests passed; full-tree Ruff, CI-YAML parsing, and `git diff --check` also passed. These are
the recorded EXP-474 local preflight results, not the still-pending formal EXP-461Q/461V or clean-
checkout reproduction.

Redirect-control follow-up: a live request then established that the Mendeley file endpoint returns
HTTP 302 to the exact
`prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com` storage host. Because
`requests` follows redirects by default, entry-URL validation alone was incomplete. EXP-474R1
therefore supersedes EXP-474's security-completeness claim: automatic redirects are disabled, one
manually checked HTTPS/443 hop to that exact storage host is permitted, further or unallowlisted
hops are rejected, and metadata-API redirects are forbidden. A live streamed-header probe reached
the allow-listed storage object with status 200 and an empty Requests history. The post-fix gate
passes 26 focused tests and records zero medium/high Bandit findings across 42,912 lines. EXP-474 is
retained as the intermediate result; EXP-474R1 is the current local preflight.

EXP-475 hardens the journal-facing text boundary. Validator version 0.8.0 now requires the article
title in the submission materials to equal the manuscript's sole H1 title after normalizing only
the Markdown double-hyphen/en-dash representation. It also rejects duplicate level-two sections in
either document instead of silently retaining the last occurrence. New negative tests exercise
keyword count, highlight count and length, manuscript length, title drift, and duplicate sections.
Thirty-seven focused RESS, empirical-manuscript, and release tests passed, as did full-tree Ruff,
expanded Bandit, and `git diff --check`. This is submission-package integrity evidence, not a
substitute for the final raw result or human verification of the live author guide.

EXP-479 through EXP-479R3 establish a deterministic working-PDF boundary before empirical final
generation. The ReportLab renderer uses embedded DejaVu fonts, invariant metadata, numbered
BibTeX references, A4 geometry, extractable text, and an unavoidable working-preflight watermark.
Final mode rejects working/author-action markers and requires exactly five one-page main-figure
PDFs. Four retained visual iterations corrected raw Markdown H4 output, excessive justification,
heading/reference collisions, and detached multiline list continuations. The superseding 19-page
working PDF passed Poppler rendering and 19/19 page agent visual inspection, but its report keeps
`human_visual_review_complete=false`, `machine_render_complete=false`, and
`submission_ready=false`. EXP-480's first recorded command failed before collection when
PowerShell rewrote the literal `{run_dir}` placeholder; EXP-480R1 retained that failure and passed
all 28 PDF/submission tests with the corrected literal argument. These preflights do not replace
the post-EXP-461 final empirical PDF or author/editor visual approval. EXP-481 then ran the full
project suite with CUDA hidden and checkout-local bytecode/cache disabled: 414/414 tests passed
with zero failures, errors, or skips in 228.094 seconds. That is an interim dirty-tree regression,
not the still-required final coverage gate or detached clean-checkout reproduction. EXP-483 then
repeated all 414 tests under path-based coverage: 9,757 of 12,536 statements were covered
(`77.83184428844926%`), with zero failures, errors, or skips in the 484.740-second JUnit record.
The unchanged 75% floor passed, but this remains an interim working-tree measurement.
EXP-484 subsequently added a synthetic-fixture positive-path test for deterministic final-mode
assembly with exactly five one-page figure PDFs; both renders were byte-identical and correctly
reported machine completion without submission readiness. EXP-485 then passed the unified 415-test
CPU-only topology with zero failures, errors, or skips in 223.642 seconds. Only the test source
changed after EXP-483, but final post-raw coverage is still rerun rather than inferred.

EXP-488--489R2 extend that boundary from a five-file count to five distinct ordered figure
identities. Renderer 0.1.2 records every appended figure path, byte count, and SHA-256 and rejects
duplicate paths or content. Independent validator 0.2.0 freezes the accepted renderer version,
hash-locks the PDF/report, empirical manuscript, bibliography, 42-output artifact manifest, and
the artifact, manuscript, release-manifest, and release-validation records, and binds the four
live PDF producer/validator sources to the independently validated archive. It also verifies the
five appended page titles in order without invoking the renderer. EXP-492 retained one integration
failure caused by the release test's obsolete five-launcher count. The corrected test requires the
exact six-launcher set, and EXP-492R1 passed all 421 current tests with zero failures, errors, or
skips in 221.778 seconds. These remain dirty-working-tree preflights; the post-empirical
release-source drift check then raised collection to 422, and EXP-492R2 passed all 422 with zero
failures, errors, or skips in 225.829 seconds. Release 0.11.0 then added the RESS upload map while
explicitly excluding the human contact/approval record from the public archive; EXP-493R1 passed
the resulting 424/424 topology with zero skips in 227.654 seconds. These remain dirty-working-tree
preflights. Outcome-blind independent raw-validator tests then raised collection to 427;
EXP-497 passed 427/427 with zero skips in 227.549 seconds, and full-tree Ruff and diff checks also
passed. EXP-499 then replaced the historical final-quality lower bound with exact equality to this
427-test topology in the runner, independent validator, release builder, and armed watcher. The
later EXP-461Q/461V, EXP-516/517, and EXP-518/519 pairs completed that topology in their respective
source states. Release amendment 003 now requires a final 0.11.3 pair and complete archive-source
clean run. A formal detached reproduction remains mandatory. EXP-494 also rescanned the expanded
44,785-line production and
project-script scope with zero medium/high findings, zero errors, and zero `nosec` annotations;
the formal post-empirical security rerun remains part of EXP-461Q.

## Independent reproduction checklist

1. Verify the external archive and manifest hashes before either extraction; extract into two new
   outside-checkout directories and require equal bounded source-tree fingerprints.
2. Create a fresh CPython 3.12 environment, install the build and CPU-CI locks with hashes, install
   the package non-editably, and verify exact CPU-only and installed-lock parity.
3. Acquire all five public fixtures into a fresh outside-checkout cache and verify their bytes and
   SHA-256 values before any test reads them; never redistribute raw inputs in the release.
4. Run Ruff, exactly 427 tests with zero failures/errors/skips, path-based coverage at the unchanged
   75% floor, expanded medium/high Bandit, and all three strict dependency audits.
5. Independently validate the final-quality logs, artifact package, empirical manuscript, archive,
   and empirical PDF without refitting; regenerate the artifact package twice and require exact
   output-tree equality.
6. Require the tested extracted source tree to remain unchanged. Treat disposable build-source
   metadata created by non-editable wheel construction as an expected, separately recorded build
   side effect rather than evidence that the tested tree changed.
7. Preserve every failed run, including EXP-418/420/421/422, precision-only EXP-459, seven-failure
   EXP-514, and raw-free-boundary EXP-524; do not replace them with only successful successors.
8. Repeat the full protocol from an author-approved detached public revision and DOI archive before
   making an independent-reproduction or submission-readiness claim.
