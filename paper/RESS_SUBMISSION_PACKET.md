# RESS submission packet map and cover-letter draft

- Status: **working submission scaffold; do not upload while any hold below is open**
- Target: Reliability Engineering & System Safety research article
- Working title: *Physical Access Changes Estimated Bearing-Diagnosis Reliability: A Crossed
  Identity--Condition Audit with Sealed Replication*
- Live-guide check: repeat on the actual submission date

This file maps validated project artifacts to journal-upload files and supplies a bounded cover-
letter draft. It does not supply author consent, reviewer identities, a public commit, or an archive
DOI.

## Hard holds

- [x] EXP-479--479R3 generate and page-check a deterministic 19-page watermarked working PDF;
      this proves the renderer path only and is explicitly not the upload manuscript.
- [x] Validator 0.9.0 generates and synchronizes a separate editable `*highlights*.txt`; final
      content still waits for the validated raw result and human review.
- [x] EXP-456R1 plus independent EXP-457 metric and EXP-477 exact-topology validation complete
      successfully.
- [x] EXP-458 generates the 28-input/42-output paper artifact package.
- [x] EXP-459R1 independently validates every final artifact without model refitting; the
      precision-only EXP-459 failure remains retained.
- [x] EXP-460/461 render and independently validate the empirical-final manuscript.
- [x] EXP-526/527 complete and independently validate the final amendment-003 local gate:
      427/427 tests, zero skips, and 78.172076% path coverage.
- [x] EXP-514 retains the seven-test archive-source failure that withdraws release 0.11.1; release
      amendment 002 and EXP-515 verify the bounded 0.11.2 structural correction.
- [x] EXP-520/521 build and reopen 0.11.2; EXP-524 retains its later raw-free artifact-regeneration
      boundary failure, and amendment 003 plus EXP-525 focus-test the bounded 0.11.3 correction.
- [x] EXP-528/529 build and independently reopen the final 532-file release 0.11.3; EXP-532 is
      retained as a runner-boundary failure and EXP-532R1 passes all 24 archive-source steps,
      including exact two-pass regeneration of 42 outputs.
- [x] Public commit `c9cd069caa51943e6413e105fc1f4775704643c5` passes GitHub Actions and the
      separately sealed author-operated EXP-533 detached-clone reproduction.
- [x] EXP-490/491 render the watermarked empirical five-figure PDF and independently bind its
      ordered figure hashes, upstream validators, and release identity; this remains a preflight.
- [x] The integrated manuscript contains the validated raw result and cites Table 6 and Figure 3.
- [ ] A venue-uploadable manuscript is rendered and visually checked page by page.
- [x] A post-amendment-003 0.11.3 archive is independently reopened and passes the complete
      author-operated archive-source clean run; earlier failed runs remain retained.
- [x] An author-operated detached clean-checkout reproduction completes from the authorized public
      revision and byte-binds the scientific source, scripts, and public artifacts to release 0.11.3.
- [ ] An external reproducer repeats the detached run from the public archival deposit and records
      identity, conflicts, deviations, and verdict.
- [ ] Domain, statistical, and reproduction review issues are resolved.
- [ ] All human author, CRediT, funding, conflict, and AI-disclosure fields are approved.
- [ ] `RESS_HUMAN_SUBMISSION_FIELDS.md` is completed by the authors against the exact upload hashes.
- [ ] The concrete public commit and evidence-archive DOI are inserted consistently; the commit is
      available, but no DOI has yet been assigned.

## Upload map

| Journal upload | Project source | Final check |
|---|---|---|
| Title page / author metadata | Human-completed `RESS_HUMAN_SUBMISSION_FIELDS.md`, transferred to the live journal form or required editable title-page format | Legal names/order, affiliation markers, corresponding-author email/postal address, and ORCIDs reconciled; no automated values |
| Main manuscript | Final non-watermarked output of `scripts/render_ress_pdf.py` from the EXP-460 empirical manuscript | Exactly five validated main-figure PDFs supplied, title page, line/page numbering, abstract, keywords, citations, tables, declarations, and references verified; do not upload `SMARTVALVE_BEARING_MANUSCRIPT_WORKING_PREFLIGHT.pdf` |
| Highlights | `--highlights-output` from `scripts/generate_ress_submission_materials.py`, rendered from the hash-locked bearing manifest | Separate editable `.txt` whose filename contains `highlights`; 3--5 bullets; each no more than 85 characters; exact ordered match to submission materials |
| Figures 1--5 | EXP-458 `bearing_figure_00_access_lattice.pdf` through `bearing_figure_04_hust_equal_volume.pdf` | Five one-page vector PDFs; same-stem SVG titles match; fonts, grayscale encodings, and clipping visually checked |
| Figure captions | EXP-458 `BEARING_FIGURE_CAPTIONS.md` integrated into manuscript or supplied as requested | Every figure cited once or more and numbering preserved |
| Tables 1--6 | EXP-458 `bearing_table_00_*` through `bearing_table_05_*` in editable table form | Values match CSV/Markdown/TeX triplets and each table is cited |
| Supplementary Tables S1--S4 | EXP-458 `bearing_table_s01_*` through `bearing_table_s04_*` | One labelled supplement with methods, units, post-hoc influence scope, and standalone captions |
| Table captions | EXP-458 `BEARING_TABLE_CAPTIONS.md` | Captions match manuscript meanings and table numbers |
| Research-data statement | Hash-locked RESS materials plus manuscript `Data availability` | Both datasets, licences, non-redistribution, and derived-artifact boundary agree |
| Code/artifact statement | Hash-locked RESS materials plus manuscript `Code and artifacts` | Exact public commit URL and exact archive DOI agree |
| Generative-AI declaration | RESS materials and manuscript declaration section | Exact same normalized text, human-reviewed and author-approved |
| Cover letter | Draft below, completed by corresponding author | No placeholders, no unsupported novelty, all declarations approved |
| Evidence link | Author-approved DOI deposit | Archive, external manifest, checksum, and validation report downloadable |

The code-rendered SVG files remain auditable sources. Upload vector PDFs unless the live guide or
editor requests another format. The evidence archive is linked through its DOI; raw Paderborn or
HUST signals are never uploaded with the manuscript. `RESS_HUMAN_SUBMISSION_FIELDS.md` is also
excluded from the public evidence archive because the completed record may contain personal
contact and approval information; the corresponding author transfers it separately to the
journal system.

## Cover-letter draft

> Dear Editor,
>
> Please consider our research article, “Physical Access Changes Estimated Bearing-Diagnosis
> Reliability: A Crossed Identity--Condition Audit with Sealed Replication,” for publication in
> *Reliability Engineering & System Safety*.
>
> A fault-diagnosis score estimates reliability only for the physical information access encoded by
> its validation split. We evaluate identical bearing records and frozen model configurations under
> measurement-random, operating-setting-held-out, physical-identity-held-out, and simultaneously
> identity-by-setting-held-out protocols. The strict crossed protocol quarantines both partial-
> access arms, and uncertainty resamples physical bearings rather than signal windows or training
> seeds.
>
> The study combines a controlled nine-method Paderborn audit across vibration, motor current, and
> fused features with a signal-unopened, pre-sealed HUST Bearing v3 replication. The HUST protocol
> gap passes its predeclared rule and remains under an equal-source-volume control, while the
> Paderborn directional rank reversal does not reproduce because HUST's accessible protocols
> saturate. A complete post-hoc no-refit deletion audit reports that no single observed HUST
> bearing or class-balanced matched group reverses any of the 18 method-by-comparison effects; its
> ranges are not presented as confidence intervals. A separately sealed raw/FFT/STFT analysis
> found positive physical-bearing interval lower limits for all three architectures, showing that
> the access result is not confined to compact engineered statistics. We retain failed runs,
> amendments, hashes, prediction-level artifacts, and independent no-refit validations.
>
> The contribution is an access-explicit reliability-evaluation contract, not a new classifier, a
> causal amount of leakage, or a claim of deployed safety. We believe it fits the journal because it
> addresses when a diagnostic performance estimate is valid for a stated physical deployment
> population and shows that access assumptions can change the selected method and sensor.
>
> **Corresponding-author action required before use:** add only author-approved statements about
> originality, concurrent submission, author consent, conflicts, funding, data/code availability,
> the public commit, and the evidence-archive DOI. Do not infer or automate these declarations.
>
> Sincerely,
>
> **Corresponding-author action required:** legal name, affiliation, postal address, institutional
> email, and ORCID.

## Corresponding-author completion

- [ ] Replace both action-required paragraphs with verified facts.
- [ ] Confirm that every author approved the exact submitted version and author order.
- [ ] Confirm the work is not under review elsewhere and disclose any preprint as required.
- [ ] Confirm funding and competing-interest wording with all authors.
- [ ] Insert and open-test the exact commit URL and artifact DOI.
- [ ] Check that the cover letter does not claim “first,” state of the art, causal leakage, safety
      certification, factory validation, or directional HUST rank replication.
- [ ] Name any suggested reviewers only after a human conflict-of-interest check; do not generate
      names from the citation list automatically.
