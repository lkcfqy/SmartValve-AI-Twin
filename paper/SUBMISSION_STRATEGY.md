# Submission strategy

- Checked: 2026-08-19 (Asia/Shanghai)
- Article type: protocol, reliability, and reproducible evaluation study
- Current outcome: the HUST protocol-gap and equal-volume gates passed 9/9; the Paderborn
  directional rank reversal did **not** externally replicate because HUST's accessible protocols
  saturated at macro F1 1.0
- Decision rule: retain RESS as the preferred route and lock the submission venue only after the
  raw-architecture sensitivity, final artifacts, independent reproduction, and human scope review
  are complete

## Venue ladder

### 1. Reliability Engineering & System Safety — preferred first submission

[RESS's official scope](https://www.sciencedirect.com/journal/reliability-engineering-and-system-safety)
centres methods that enhance safety and reliability in complex technological systems. It has direct
precedent for an application-oriented DG benchmark in fault diagnosis
[@Zhao2024] and for uncertainty-informed bearing diagnosis. The present paper should therefore lead
with reliability of the *validation estimate*: convenient access protocols can overstate diagnostic
reliability and choose a different method/sensor for a deployment population.

The current [RESS author guide](https://www.sciencedirect.com/journal/reliability-engineering-and-system-safety/publish/guide-for-authors)
limits the abstract to 200 words, requests one to seven keywords, requires three to five separate
highlights of at most 85 characters each, requires a research-data statement, and caps the
manuscript at 13,000 words. The integrated draft is below the manuscript cap, but its final abstract,
highlights, keywords, declarations, and data statement must be generated and checked after the raw
architecture result is independently validated.

A direct live recheck at `2026-08-19T08:32:52Z` reached the official Guide for Authors but was
stopped by its CAPTCHA. The challenge was neither solved nor bypassed. The automated constraints
below therefore remain a strong local preflight, while a human author must repeat a line-by-line
check on the live guide immediately before upload. The directly readable official journal page
continued to list automatic fault detection/diagnosis, data analysis, uncertainty, and substantive
complex-system reliability problems within scope.

Elsevier's current [artwork overview](https://www.elsevier.com/about/policies-and-standards/author/artwork-and-media-instructions/artwork-overview)
accepts vector PDF artwork and recommends Arial/Helvetica-class fonts. The final artifact generator
therefore retains accessible code-rendered SVG sources while producing same-stem, one-page vector
PDF uploads with normalized metadata and matching embedded titles.

The official journal page checked on 2026-08-19 lists both optional open access and a subscription
route. The subscription route states that no publication fee is charged to authors, so lack of an
open-access APC budget does not by itself block a RESS submission. The live options and any
institutional agreement must be rechecked at submission.

This is the strongest current fit because the external score-gap replicated prospectively and
survived an equal-source-volume control, whereas method-rank direction did not replicate. The paper
must not become a generic nine-classifier leaderboard. It should connect physical-unit uncertainty,
access assumptions, and model-selection regret to reliability decisions and make the HUST ceiling
result a limitation rather than hiding it.

### 2. Mechanical Systems and Signal Processing — conditional stretch

[MSSP's current author guide](https://www.sciencedirect.com/journal/mechanical-systems-and-signal-processing/publish/guide-for-authors)
places machine/system health monitoring inside scope but expects a demonstrable, significant
advance in engineering knowledge. Its separate
[machine-learning guidance](https://media.journals.elsevier.com/content/files/machine-learning-04180327.pdf)
explicitly warns that a feature/classifier study on a simple rotor-bearing rig is insufficient and
may be rejected without review; it emphasizes principled hyperparameter choice and rigorous
generalization evidence. Our contribution is an evaluation contract rather than another
classifier, but this still makes MSSP a higher desk-rejection risk than RESS.

Use MSSP first only if all of the following are true:

- raw/FFT/STFT sensitivity shows that the access conclusion is not confined to compact statistics;
- sensor attribution is complete rather than selectively reported;
- the manuscript demonstrates engineering knowledge about deployment estimands, not a repackaged
  classifier comparison; and
- a mechanical-systems expert agrees that the factorial access contract clears MSSP's novelty bar.

MSSP currently requires a concise abstract, research-data deposit/link or an explanation, and an
explicit declaration of generative-AI assistance when it was used. Its guide requires human authors
to verify, edit, and take responsibility for every claim and reference. AI-generated manuscript
artwork is prohibited, so final figures remain deterministic and code-rendered. SVGs are retained
as auditable sources; normalized vector-PDF exports are the submission artwork, avoiding
rasterization and volatile PDF timestamps.

### 3. IEEE Transactions on Instrumentation and Measurement — measurement framing

[IEEE TIM's official scope](https://ieee-ims.org/publication/ieee-tim) includes measurement theory
and practice, processing and preservation of measured information, and systems used to monitor or
record physical phenomena. This route is viable if the paper treats the split/access contract as a
measurement-validity problem and clearly links sensor modality, physical-unit inference, and
uncertainty to instrumentation practice.

TIM's current [information for authors](https://ieee-ims.org/publication/ieee-tim/information-authors)
requires authors to state explicitly how the work advances I&M and to place the novelty in I&M
literature. A regular submission uses the IEEE two-column format, a single self-contained PDF, at
least five pages, two EDICS, and ORCIDs for all authors. TIM now provides specific topical guides for
AI/classification and measurement uncertainty; these must shape the final terminology if TIM is
chosen.

TIM is weaker fit if the final manuscript reads mainly as a domain-generalization benchmark with
little measurement-system interpretation.

### 4. IEEE Transactions on Industrial Informatics — conditional stretch

TII is considered only if the manuscript adds a credible industrial-informatics/deployment layer.
The present public-rig study has no factory, edge, networked-control, or online-system validation, so
an IIoT framing alone would overclaim the evidence.

## Outcome-conditioned decision

| Validated outcome | Recommended route | Allowed headline |
|---|---|---|
| **Observed:** HUST protocol gap and equal-volume control pass, but directional rank reversal does not replicate | **RESS first; MSSP conditional stretch; TIM second** | Evaluation access materially changes estimated reliability across two bearing systems; method-order evidence is Paderborn-specific and HUST is ceiling-limited |
| HUST protocol-gap and directional rank evidence both replicate, with raw/sensor sensitivity complete | MSSP or RESS after expert scope review | Crossed access changes both estimated performance and method selection across systems |
| HUST rank instability passes but median performance-gap gate fails | RESS/TIM after careful scale analysis | Method choice is access-sensitive even without a replicated large median score gap |
| Both HUST gates fail | Do not market as externally replicated top-tier result | Paderborn development pattern failed a sealed external test; submit only as a transparent non-replication/audit paper after expert review |
| Any artifact validator fails without a bounded, outcome-neutral explanation | No submission | Repair and retain the failure; never replace it silently |

## Mandatory work before any submission

1. Complete and independently validate the sealed Paderborn raw/FFT/STFT sensitivity; motor
   current and three-sensor attribution are already complete.
2. Replace the raw hold in the integrated manuscript and produce a venue-uploadable manuscript
   source rather than submitting the Markdown audit files as-is.
3. Build and visually inspect the final main figures with physical units and access semantics
   visible; move exhaustive hashes to
   the supplement.
4. Run full tests, coverage, clean-environment reproduction, artifact-link checks, and independent
   evidence-archive validation.
5. Obtain advisor/domain-expert review and independent statistical review; approve author order,
   affiliations, ORCIDs, CRediT, funding, and competing-interest statements.
6. Repeat the closest-work search immediately before submission, especially evaluation-protocol
   and benchmark papers published after Knap, Vieira, Kaya, and Zhao.
7. Verify every venue rule on the live official author page, including page/word limits, data/code
   availability, authorship, and AI-use disclosure.

Venue rank and acceptance cannot be guaranteed. The choice above is based on scientific scope and
the strength of the eventual validated evidence, not on a promise of publication.
