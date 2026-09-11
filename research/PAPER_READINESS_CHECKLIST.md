# Paper-readiness checklist

- Audit date: 2026-08-20 UTC
- Legacy PIRL algorithm-paper status: **NO-GO**; the frozen efficacy family remains failed
- v0.4 bearing-protocol paper status: scientific family, final artifacts, empirical manuscript,
  release 0.11.3, archive-source reproduction, working-PDF preflight, public Git revision, cloud CI,
  and author-operated detached-commit reproduction complete. Earlier 0.11.1/0.11.2 failures and
  the bounded EXP-532 runner failure remain visible. Public archival hosting/DOI, independent
  third-party reproduction, venue-final files, and external human review remain
- Candidate article type: protocol reliability, deployment-estimand audit, and sealed replication
- Acceptance status: no venue acceptance can be inferred or guaranteed

## Current v0.4 bearing-protocol gate matrix

| Gate | Evidence | Status |
|---|---|---|
| Four access protocols | random, setting-only, identity-only, and strict crossed with XOR quarantine | **pass**, EXP-433--435 |
| Controlled neural comparison | nine frozen mechanisms, common backbone/configuration/seeds, 1,800 protocol fits | **pass**, EXP-434B/435 |
| Paderborn sensor sensitivity | classical and neural vibration/current/fusion under common protocols | **pass**, EXP-436--438 and EXP-451--453; 27/27 gap intervals above zero |
| Physical-unit inference | paired class-stratified bearing bootstrap, no seed/window pseudoreplication | **pass** |
| Sealed external replication | signal-unopened HUST topology/code/runtime/threshold freeze and one-shot run | **pass**, EXP-439B--447 |
| External protocol-gap gate | at least 7/9 positive and median at least 0.15 | **pass 9/9**, median `0.226030` |
| External rank replication | directional Paderborn winner reversal on HUST | **not supported**; easy protocols tie at 1.0 and tau is undefined |
| Equal-source-volume falsification | same targets, 24 source records, balance/support/pair budgets | **pass 9/9**, EXP-446/448--450B |
| HUST physical-unit influence | post-hoc no-refit deletion of each bearing and each class-balanced matched group | **pass as a sensitivity audit**, EXP-464R1/465; 18/18 signs stable under both schemes, not confirmatory |
| Independent no-refit validation | predictions through physical bootstrap recomputed with explicit no-refit declarations | **pass** for fusion (EXP-456A), combined sensors, HUST primary, equal-volume control, HUST deletion audit, and raw architectures (EXP-457); EXP-477 separately passed exact pre-outcome topology validation |
| Raw/high-resolution representation sensitivity | access effect outside the compact 24-statistic view | **pass**, EXP-456R1/457/477; all 270 fits completed, raw/FFT/STFT effects were `0.363114`, `0.170716`, and `0.205668`, all three 95% lower limits exceeded zero, and the median `0.205668` exceeded the frozen 0.15 threshold |
| Integrated manuscript and deterministic artifacts | one coherent paper, tables, figures, supplement manifest | **pass**, EXP-458/459R1 and EXP-460/461; 28 inputs, 42 outputs, five SVG/PDF pairs, a 9,369-word empirical manuscript, 39/39 final interval lower limits positive, and all human holds retained; failed precision-only EXP-459 remains visible |
| Final local technical quality package | eight fixed checks, JUnit/coverage evidence, independent log/hash validator, release inclusion | **pass**, EXP-526/527; 427/427 tests, zero failures/errors/skips, `78.172076%` coverage, 8/8 checks, and independent hash/log validation under amendment 003 |
| Dependency and static security preflight | pinned build, runtime, CPU-CI, and GPU-research locks plus application/project-script Bandit | **pass in final local, archive-source, detached-commit, and cloud-CI environments**, EXP-526/527, EXP-532R1, EXP-533, and Actions run `32327320449`; expanded medium/high Bandit and all three strict dependency audits passed |
| Dedicated public-candidate secret scan | positive-control-validated Gitleaks over current candidate and Git history | **current preflight pass; final rescan open**; checksum-verified v8.18.4 detected the synthetic control, then found zero leaks across 431 candidate files and all three existing commits; v8.29.1 was rejected after its control failed |
| Bibliography resolver and metadata integrity | unique DOI redirects, registered CSL metadata, and recent-work claim-context checks | **current preflight pass; final human check open**; all 28 unique DOIs resolve off doi.org, all 28 registered titles/years match, the highest-risk Panić/Vieira/Kaya/Knap contexts were spot-checked against primary sources, and PI-FSL was screened as labelled-target adjacency rather than a closer target-free access audit |
| Internal DOCX structure preflight | style-driven manuscript conversion plus style and OOXML package audits | **machine-structural pass; visual inspection open**; the working preflight has 52 hierarchical headings, 21 real numbered/list items, five fixed-grid tables, and zero package-audit failures, but no Word/LibreOffice renderer was available and it is not a final venue artifact |
| Internal RESS PDF visual preflight | deterministic A4 manuscript render, text extraction, page topology, ordered figure identity, and page inspection | **empirical five-figure watermarked preflight pass**, EXP-490/491 plus `research/BEARING_VISUAL_QA.md`; 24 pages, zero blanks, five ordered vector figures, upstream release/source binding, and 24/24 pages plus 5/5 figures agent-inspected; human visual approval and a non-watermarked upload remain open |
| RESS submission-text integrity | synchronized title/abstract/release identifiers/disclosures plus length, keyword, separate editable-highlight, citation, and callout constraints | **local preflight pass; live human guide check open**; validator v0.9.0 extends EXP-475 with an independently named `.txt` Highlights upload and exact bullet synchronization; EXP-480R1 passes 28/28 PDF/submission tests, but the official Guide presented a CAPTCHA and was neither solved nor bypassed |
| Full quality and clean-environment reproduction | Ruff/tests/coverage plus independent environment | **author-operated machine preflight pass; third-party reproduction open**; EXP-532R1 passed the complete raw-free 0.11.3 archive-source chain with 427/427 tests, `78.086659%` coverage, 14 evidence gates, and exact two-pass regeneration of 42 outputs. EXP-533 then passed the exact detached public commit with 427/427 tests and `78.172076%` coverage |
| Container/Compose CI gate | Compose interpolation and reproducible application-image build | **pass in GitHub Actions**, run `32327320449`; lint/tests, security checks, Compose validation, and the actual application-image build all exited zero on public commit `c9cd069` |
| Clean-reproduction logistics | detached commit, hashed release, locked environment, QA, artifact and archive validation | **author-operated archive-source and detached-public-commit pass; DOI/third-party open**; retained EXP-514/524/532 failures document the correction path, EXP-532R1 passes the 0.11.3 archive source, and EXP-533 binds `c9cd069` byte-for-byte to 110 `src/smartvalve`, 47 `scripts`, and 42 `paper/generated` files while revalidating the exact archive/artifact hashes |
| Human domain/statistical review | advisor plus independent condition-monitoring/statistics review | **open; cannot be self-certified** |
| External review logistics | immutable-version domain/statistics/reproduction questions and issue log | **packet prepared** in `research/EXTERNAL_REVIEW_PACKET.md`; no review has occurred |

The current evidence is a credible top-domain-journal candidate, not yet a submission package. It
does not supply the broad method novelty expected by a general ML top conference.

## Legacy v0.2 PIRL gate matrix

| Gate | Required evidence | Final status |
|---|---|---|
| Three physical datasets | Cranfield, UCI Hydraulic, and Paderborn with distinct physical units | **pass** |
| Source-only candidate | frozen PIRL v0.2 with target rows absent from selection | **pass** |
| Strong neural baselines | ERM, CORAL, VREx, GroupDRO, DANN, LISA, MatchDG, CCDG | **pass**, EXP-340/417 |
| Source-OOF rejector | threshold and score selected without target labels | **pass**, EXP-342/419 |
| Prospective independent-asset test | post-seal Paderborn execution without method change | **pass**, EXP-416/417/419 |
| Physical-unit inference | 2,000 paired replicates per dataset and Paderborn bearing resampling | **pass**, EXP-344/421B |
| Multiplicity control | exact six-test Holm family with practical threshold | **pass**, EXP-422B |
| Component attribution | full/ratio-only/margin-only/ERM comparison | **pass as an audit**, but margin contribution is null |
| Multi-dataset benefit | positive endpoint on at least two datasets, no resolved material harm | **fail**: UCI only |
| D2 confirmation | at least one Paderborn confirmatory-positive endpoint | **fail**: 0/2 |
| Algorithm leadership | consistent advantage over strong baselines | **fail**: PIRL is not best on D0, D1, or Paderborn pooled F1 |
| Structural traceability | failed checks retained; correction bounded and outcome-neutral | **pass**, EXP-418B/420B/421B/422B |
| Portable paper artifacts | deterministic tables/figures and relative-path manifests | **pass**, EXP-423E |
| Final full-project quality gate | Ruff plus all tests at unchanged 75% coverage | **pass at boundary**: EXP-424/425, 269 passed, 75.00% |

## Confirmatory decision

The frozen family has six tests. Only UCI Hydraulic selective risk is confirmatory-positive:
effect 0.044069, 95% interval [0.038991, 0.049302], Holm-adjusted p=0.005997. Both Cranfield tests,
UCI minimum-environment macro F1, and both Paderborn tests are null under the joint practical,
interval, and multiplicity rule. No test meets the frozen material-harm definition.

The rule requires improvement on at least two datasets. The observed count is one; therefore
`internal_multi_dataset_evidence_gate_passed=false`.

## What is ready

- The four-protocol Paderborn comparison is complete for seven classical and nine neural methods.
- Fusion, vibration, motor current, and their shared physical-bearing sensor contrasts have passed
  independent no-refit recomputation.
- The signal-unopened HUST protocol gap passed its frozen rule, and the complete ceiling-limited
  rank result is retained rather than promoted as a directional replication.
- The HUST equal-source-volume control passed 9/9 and rules out source-record count alone.
- The complete post-hoc HUST deletion audit passed independent manual-F1 recomputation; no single
  observed bearing or matched group reversed any of the 18 effects.
- A validated 9,369-word empirical manuscript, exact novelty matrix, RESS-first venue strategy,
  access-lattice artifact code, and append-only run ledger exist.
- A deterministic, watermarked 24-page empirical working PDF with five final vector figures passed
  24/24-page and 5/5-figure agent visual inspection; the independent validator binds five distinct
  ordered PDF hashes and the RESS tooling creates and validates a separate editable Highlights
  upload.
- Failed experiments and validator amendments remain visible with bounded scientific claims.
- Release amendment 002 converts all seven retained EXP-514 failures into explicit source-package
  requirements; the extracted 0.11.2 structural preflight passed the affected 34-test family and
  the full development topology passed EXP-516/517.
- Release amendment 003 converts the retained EXP-524 raw-free regeneration failure into an
  explicit release-input contract. EXP-525 passed 22/22 focused tests, including exact regenerated
  output equality and negative controls for default strict mode and missing consumed inputs.
- Release 0.11.3 passed its final EXP-526/527 quality pair, deterministic EXP-528/529 archive
  chain, release-bound EXP-530/531 PDF chain, and complete EXP-532R1 archive-source reproduction.
- Public commit `c9cd069caa51943e6413e105fc1f4775704643c5` passed GitHub Actions and the
  separately sealed EXP-533 detached-clone reproduction. The scientific source, validator scripts,
  and all 42 public generated files are byte-identical to release 0.11.3.

## What is not ready

- The non-watermarked venue PDF and exact journal-upload files with human visual review.
- Public archival hosting and a DOI for the three hash-locked release files; the currently validated
  archive remains a local author asset.
- A genuinely independent third-party reproduction; EXP-532R1 and EXP-533 are author-operated.
- Advisor/domain-expert and independent statistical review.
- A final author decision on the archival revision, software-license boundary, and artifact DOI.
- Any claim about deployed safety, cross-factory transfer, causal identification, or a
  population-wide algorithm ordering.

## Submission-level interpretation

### General ML algorithm paper

**No-go.** The original PIRL efficacy family failed, and the current contribution is an evaluation
contract rather than a broadly new learning algorithm. Favorable post-hoc analysis cannot change
that contribution class.

### Bearing reliability/protocol paper

**Credible top-domain-journal candidate, not yet a submission package.** The strongest evidence is
the jointly crossed physical-access estimand, physical-unit uncertainty, sealed HUST score-gap
replication, equal-volume falsification, complete sensor attribution, passed raw-architecture
sensitivity, and unusually strong audit trail. Publication level still depends on an independent
detached third-party reproduction, archival artifact hosting, human review, and venue judgment; no
tier or acceptance is guaranteed.

## Remaining checklist for an actual submission

- [x] Integrate Methods, Results, Discussion, and limitations into one manuscript.
- [x] Position the exact closest work and prohibit broad priority/algorithm claims.
- [x] Complete Paderborn motor-current and paired three-sensor validation.
- [x] Generate and machine-audit an internal DOCX structure preflight (not a final venue artifact).
- [x] Generate and inspect a deterministic watermarked RESS working PDF and separate editable
      Highlights preflight (neither is the final upload artifact).
- [x] Complete and independently validate the sealed raw/FFT/STFT family.
- [x] Generate and agent-inspect the final bearing tables, figures, captions, and manifest.
- [x] Run the final local Ruff/tests/coverage/security/lock gate after empirical generation.
- [x] Run the post-amendment-003 full quality pair, then build, independently reopen, and completely
      clean-run release 0.11.3.
- [x] Run an author-operated detached clean-environment reproduction from the authorized public
      revision.
- [ ] Obtain a third-party detached reproduction using the publicly archived release files.
- [ ] Have an advisor/domain expert and independent statistician review the estimand and claims.
- [x] Create an author-authorized public Git commit and pass its cloud CI.
- [ ] Publish the hash-locked technical archive, manifest, and checksum under an archival DOI.
- [ ] Recheck the selected venue's live scope, format, data, authorship, and AI-use rules.

The RESS/Elsevier rules were last checked against official live pages on 2026-08-19. The software
currently enforces the 200-word local abstract cap, one-to-seven keywords, three-to-five Highlights
of no more than 85 characters, a separately named editable Highlights file with exact bullet
synchronization, and Elsevier's June-2026
[generative-AI policy](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals)
requiring a named tool, purpose, human review, and responsibility. A fresh check remains required on
the actual submission date because publisher rules can change.

## Human-owned submission fields

These fields cannot be inferred from Git metadata or generated by the experiment code. They remain
hard submission blockers until the human authors explicitly approve them. The incomplete working
record is `paper/RESS_HUMAN_SUBMISSION_FIELDS.md`:

- [ ] legal author names, order, affiliations, corresponding-author address, and email;
- [ ] ORCID for every author who will be listed;
- [ ] CRediT contribution statement approved by all authors;
- [ ] funding bodies, grant identifiers, and the funders' role, or an explicit no-funding statement;
- [ ] competing-interest declaration approved by every author;
- [ ] advisor/institution decision on authorship and permission to submit;
- [ ] author selection of the public commit, software licence boundary, and archival DOI; and
- [ ] final human verification of every reference, numerical claim, figure, and AI-use disclosure.

The project must not replace these items with guessed names, placeholder grants, or an automated
claim of author consent.

## Decision sentence for every status report

> The complete factorial, sealed HUST, raw-sensitivity, artifact, post-correction local-quality,
> working-PDF, release-0.11.3, archive-source, cloud-CI, and detached-public-commit evidence supports
> a credible top-domain-journal protocol paper, but public archival hosting/DOI, independent
> third-party reproduction, venue-final files, and external human review remain; this is not a
> top-tier algorithm submission.
