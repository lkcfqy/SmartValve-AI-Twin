# AI-assistance audit record

- Record version: `smartvalve-ai-assistance-record-0.1.0`
- Project: SmartValve bearing-diagnosis validation-protocol study
- Tool/service: OpenAI Codex desktop application
- Use period covered: August 2026
- Policy reference checked: Elsevier,
  [*Generative AI policies for journals*](https://www.elsevier.com/about/policies-and-standards/generative-ai-policies-for-journals),
  updated June 2026
- Human final approval: **pending**

## Uses in the research workflow

OpenAI Codex assisted with software implementation and review, unit and artifact-validation tests,
experiment command construction and monitoring, provenance documentation, official-source
literature discovery, manuscript organization, and language editing. These uses are disclosed in
the Methods section because they include code and research-workflow assistance, not only spelling
or grammar correction.

## Uses in manuscript preparation

OpenAI Codex proposed and edited prose, table/figure-generation code, submission checks, and the AI
declaration. The final manuscript must retain Elsevier's separate declaration naming the tool,
purpose, human review, and author responsibility. Codex is not an author or cited as an author.

## Prohibited substitutions and controls

- Codex did not supply dataset labels, fabricate observations, alter raw signals, or replace the
  numerical producers.
- Frozen experiment code, inputs, endpoints, thresholds, and interpretation rules are content
  hashed before outcome access. Interrupted runs and validator failures are retained.
- Paper values are generated from locked artifacts and independently recomputed without refitting.
- Intermediate outcomes of the sealed raw-architecture experiment are not inspected.
- Literature claims require direct publisher, dataset-owner, official-policy, or primary-paper
  support; no citation is accepted solely because an AI tool proposed it.
- Figures are deterministic plots of validated numerical artifacts, not generative-AI images.
- Public commits, archive deposits, authorship, author order, affiliations, ORCIDs, conflicts,
  funding statements, and submission remain human decisions.

## Human review evidence required before submission

The corresponding author must complete and date each item; unchecked items are submission blocks.

- [ ] Recompute or spot-check every headline value against the final locked manifest.
- [ ] Open every table and figure; verify labels, units, legends, captions, and grayscale meaning.
- [ ] Open every cited source and verify that the manuscript claim is directly supported.
- [ ] Review all code changes that affect inputs, splits, fitting, aggregation, or inference.
- [ ] Confirm that limitations and retained negative/null/interrupted results are not omitted.
- [ ] Confirm the final AI declaration accurately describes both research and writing assistance.
- [ ] Approve the exact manuscript, supplement, code commit, and evidence-archive DOI.
- [ ] Record reviewer name, role, date, and signed/traceable review location below.

## Sign-off

| Role | Name | Date | Review evidence/location | Status |
|---|---|---|---|---|
| Corresponding author | pending | pending | pending | not approved |
| Condition-monitoring/domain reviewer | pending | pending | pending | not reviewed |
| Statistical/reproduction reviewer | pending | pending | pending | not reviewed |

This file documents the control process; it does not itself prove that human review occurred. The
past-tense publisher declaration may be generated only after the corresponding author completes
the required review and explicitly confirms it.
