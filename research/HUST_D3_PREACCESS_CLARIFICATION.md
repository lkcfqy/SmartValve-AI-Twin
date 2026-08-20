# HUST D3 pre-access semantic clarification

- Date: 2026-08-19 (Asia/Shanghai)
- Status: frozen before HUST MAT download, MAT opening, feature extraction, or model fitting
- Parent seal SHA-256: `eb66d23601ba21fe70b125d503ec56c51fbcfc2f5c59d6d1f2bf4335485428ef`
- Scope: label/probability-column semantics only; no cohort, split, feature, model, seed,
  endpoint, bootstrap, gate, or stopping rule changes

The parent seal states the condition order as `N`, `I`, `O`. The inherited SmartValve neural
implementation and its already frozen probability-column schema use the semantic order
`healthy`, `outer`, `inner`, corresponding to HUST conditions `N`, `O`, `I`.

For D3, the executable label mapping and all probability arrays are therefore fixed as:

| Probability index | Column | Semantic label | HUST condition |
|---:|---|---|---|
| 0 | `probability_healthy` | `healthy` | `N` |
| 1 | `probability_outer` | `outer` | `O` |
| 2 | `probability_inner` | `inner` | `I` |

This is a semantic clarification, not an outcome-dependent amendment. The mapping is bijective,
was inherited before HUST signal access, and leaves all class-symmetric endpoints unchanged. The
mapping must be checked in the metadata-only expected manifest, execution seal, model runner, and
independent artifact validator.
