# Top-tier review-risk register

- Updated: 2026-08-20 (Asia/Shanghai)
- Intended contribution: protocol, reliability, and reproducible evaluation for bearing diagnosis
- Status vocabulary: `closed`, `mitigated`, `open`, `intrinsic limitation`

| Risk | Why a strong reviewer may reject | Current response | Status / required closure |
|---|---|---|---|
| Novelty collision | Bearing-wise splitting, leakage-safe Paderborn/HUST evaluation, representation sensitivity, vibration/current fusion, systematic domain-shift factor isolation, and design-choice reversals already exist | Exact closest-work matrix now includes Hendriks, Abburi, Wheat, Knap, Vieira, Kaya, and Panić; claims are restricted to the joint identity × setting access estimand, XOR quarantine, nine-method rank audit, physical inference, and sealed HUST/equal-volume replication | **mitigated but high**; Panić et al. 2027 is a direct RESS evaluation-methodology neighbor, so repeat the search immediately before submission and avoid all broad priority language |
| Smaller crossed training set | Random/crossed degradation could be a data-volume effect rather than an access effect | Outcome-blind HUST equal-volume control fixes both sources at 24 recordings and matches class balance, environment support, and 120/240 pair budgets; EXP-449/450B passed 9/9 with median effect 0.226 and all interval lower limits positive | **closed for source count alone**; membership/access still differ, so no causal leakage amount is claimed |
| Retrospective Paderborn analysis | The protocol question was motivated after earlier Paderborn outcomes | All Paderborn post-EXP-417 results are explicitly development evidence; HUST metadata, topology, code, thresholds, and interpretation were sealed before signal/model outcomes; EXP-445/447 validated the gap prospectively | **mitigated**; Paderborn remains development evidence and is never called confirmatory |
| HUST identity/specification confounding | A held index contains three class-specific physical bearings sharing one specification; specimen identity and specification cannot be separated | Use `matched_specification_group`, report 15 physical bearings and five per class, and state the confounding in methods, figures, and limitations | **intrinsic limitation**; no wording can remove it |
| Small physical sample | Thousands of windows can disguise only five HUST bearings per class, and one bearing or matched group could dominate the contrast | Scores are at recording level; uncertainty resamples physical bearing codes, class-stratified; windows and seeds are never inferential replicates. The frozen post-hoc no-refit audit retained positive effects in 18/18 method-comparison cells after every single-bearing deletion and 18/18 after every class-balanced matched-group deletion | **mitigated, not closed**; deletion ranges are not confidence intervals, do not create more units, and remain conditional on the observed cohort |
| Engineered-feature dependence | A fixed 24-feature MLP suite may not represent raw CNN/transformer behavior | Classical and three-view neural sensor checks are complete; the separately frozen MIT-attributed Knap-style raw/FFT/STFT family completed all 270 fits and passed independent metric plus pre-outcome topology validation in EXP-456R1/457/477 | **mitigated, not closed**; all three physical-bearing interval lower limits are positive, but the result does not transfer the nine-method rank claim to raw backbones or cover transformers/foundation models |
| Method-reproduction fidelity | Source-only DANN/CORAL/LISA/MatchDG variants are not exact reproductions of all original settings | Shared backbone and selector isolate mechanism families; Methods, the third-party notice, and the frozen implementation-provenance audit document every adaptation and never claim original-algorithm benchmarking | **mitigated**; residual external-validity limitation remains |
| Ceiling-compressed ranks | Negative Kendall tau can be unstable when random scores differ by only a few points | Always show absolute score range next to ranks, all rank shifts, physical intervals, and the equal-volume control | **mitigated**; never report tau alone |
| Multiple analyses after D2 | A large artifact tree can look like undisclosed outcome-driven exploration | Dataset roles, seals, failed runs, amendments, expected keys, and claim matrix distinguish retrospective, prospective, primary, and auxiliary evidence | **mitigated if manuscript chronology is concise** |
| Missing independent reproduction | A self-validator can share implementation errors with the producer | Main validators recompute without fitting; EXP-532R1 passes the full archive-source chain; EXP-533 passes a detached public clone and byte-binds scientific source/scripts/public artifacts to release 0.11.3 | **open/high for third-party independence**; both clean runs were author-operated, and an external person must repeat from the archival deposit |
| Integrated-manuscript coherence | A collection of evidence files is not a coherent paper | A validated 9,369-word protocol-centric empirical manuscript integrates related work, methods, all retained outcomes, discussion, limitations, and disclosures; a 24-page five-figure working PDF passed bounded visual QA | **mitigated**; human copyedit, non-watermarked venue rendering, and author-owned fields remain |
| No external domain review | Statistical and mechanical interpretations have not been challenged by a human expert | Claim matrix and risk register make the audit surface explicit | **open/high**; require advisor plus independent statistician/condition-monitoring review |
| Venue-scope mismatch | General ML top conferences expect broad methodological novelty; RESS requires a discernible relation to a substantive reliability problem; MSSP's official ML guidance warns that simple-rig feature/classifier papers can be desk-rejected; TIM requires an explicit I&M advance | RESS is preferred because the score-gap and equal-volume evidence concern reliability of the validation estimate, and Zhao et al.'s RESS ten-dataset DG benchmark supplies direct industrial-diagnosis precedent. The manuscript now distinguishes this access-validity audit from another classifier leaderboard. MSSP remains conditional after raw sensitivity, and TIM requires a measurement-validity rewrite | **open**; public test rigs still create desk-rejection risk, so obtain human scope review and follow the live author guidance immediately before submission |

## Submission gate

The package may be called a **top-domain-journal candidate** only after all of the following are
true:

- [x] primary HUST EXP-445 completes once and passes independent no-refit validation;
- [x] the predeclared HUST protocol-gap/rank gates are reported without selection;
- [x] equal-volume HUST control completes and independently validates;
- [x] Paderborn motor-current and combined sensor attribution complete and validate;
- [x] the complete post-hoc HUST physical-unit influence audit independently validates and is
      labelled non-confirmatory;
- [x] one integrated manuscript, figures, tables, supplements, and data/code statement are built;
- [x] full Ruff/test/coverage gates pass after the final implementation;
- [x] author-operated archive-source and detached-public-commit reproductions are completed;
- [ ] an independent third party repeats the detached reproduction from the archival deposit;
- [ ] advisor/domain-expert and statistician reviews are addressed; and
- [ ] current venue scope, format, AI-disclosure, and research-data requirements are checked.

Even after these gates, acceptance or journal tier cannot be guaranteed. A failed HUST replication
does not invalidate the experiment, but it materially changes the viable venue and abstract claim.
