# Bearing manuscript and figure visual QA

- Inspection time: `2026-08-19T12:22:45Z`
- Scope: agent visual preflight of the validated empirical working PDF and the five main vector
  figures; this is not author, domain-expert, editor, or accessibility certification
- Result: **24/24 manuscript pages and 5/5 standalone figures passed this bounded preflight**
- Submission status: **false**; the inspected manuscript is deliberately watermarked

## Hash-locked inputs

- EXP-490 working PDF:
  `c041274804f7818b97f002d47ccde97baf23e67c42d6ad4506d89b73daf4b463`
- EXP-490 render report:
  `2039f73fa0a18ab534edb067dd62c1b00ae0fcd3ff228dca46c1e56a1e981583`
- EXP-491 independent PDF validation:
  `09ff92a7473a05c83f7673eb19eb52efb2f8459153639c97f12d6ef8bc263939`
- Figure 1, access lattice:
  `1ea8df3ae07847066101e0c14df3795f74334d34f4242d3cf7249bad88f0eea0`
- Figure 2, Paderborn protocol profiles:
  `1974166d714dbedffff6c1b31a1a13c748152d944bdc145327cc1af6f60b8e66`
- Figure 3, cross-study gap forest:
  `508cb8a50a1eeda3ef7c7fb1ea38fc0143cf6758f835c9dcf72c17827b67aa03`
- Figure 4, sensor-view gaps:
  `ae281d4ac17d19ae4c731d5c0940a2f3f37526a4d0a090c10a6368c4a5d15003`
- Figure 5, HUST equal-volume control:
  `70ae76384b9f8432cb843ca39248c5fbf96baa2309dba88afc6c5d4aad2717bc`

## Inspection method

The five one-page vector PDFs were rasterized at 180 dpi. The 24-page empirical working PDF was
rasterized page by page at 120 dpi with Poppler `pdftoppm` 26.05.0. Every rendered page was opened
and inspected in order. The review checked page identity and order, headings, paragraph flow,
tables, references, footers, watermark continuity, missing glyphs, clipping, collisions, blank
pages, figure titles, legends, axis labels, interval marks, grayscale-redundant line/marker
encodings, and consistency between the five standalone figures and appended manuscript pages.

Two apparent concerns in whole-page thumbnails were rechecked with targeted crops and PDF text
coordinates. Page 6 contains three separate, vertically spaced feature-family bullets; they are
not collapsed. Page 12 retains clear whitespace between its last paragraph and the `Page 12`
footer; the text does not collide. Neither concern is an unresolved defect.

## Findings

- All 24 manuscript pages are present, legible, and in the expected order; no page is blank.
- Tables remain inside the page frame with readable headers and complete rows.
- The working-preflight watermark is visible without obscuring the manuscript.
- All five appended figure pages are complete and free of visible clipping or missing labels.
- Encodings do not rely on color alone: method/sensor families retain marker and/or line-style
  distinctions.
- No unresolved overlap, footer collision, missing glyph, truncated label, or figure-order defect
  was observed.
- Page 17 contains intentional whitespace because authorship, funding, and competing-interest
  fields remain human-owned holds; it is not treated as evidence of completion.

## Limits and required human action

This inspection is a reproducible technical preflight, not a human-review claim. It does not prove
appearance after journal conversion, printing, grayscale reproduction, assistive-technology use,
or copyediting. The corresponding author and at least one independent human reviewer must inspect
the exact final non-watermarked upload PDF, every figure and table, and all declarations. The
machine reports must continue to state `human_visual_review_complete=false` and
`submission_ready=false` until that review and the other submission holds are genuinely closed.
