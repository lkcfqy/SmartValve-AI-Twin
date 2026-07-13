# Contributing

Use Python 3.12 and keep scientific claims narrower than the evidence that supports them.

1. Create a focused branch and do not commit `.env`, downloaded public data, runtime databases,
   customer files, or credentials.
2. Install with `make install`, then run `make lint`, `make test`, and `make security`.
3. Update model/benchmark artifacts only through their reproducible commands. Do not edit metric
   JSON by hand.
4. Any rule or feature change requires a new model version, regenerated full and locked-challenge
   artifacts, and an explanation in `docs/benchmark_history.md`.
5. UI text must distinguish S0 simulation, S1 public rigs, S2 own hardware, and S3 verified
   enterprise evidence. Operator-declared uploads are S3 candidates until independently checked.
6. Preserve the append-only audit contract and backward-compatible API fields unless a versioned
   migration is documented.

Bug fixes should include a regression test. Security-sensitive changes should also update the
threat assumptions in `SECURITY.md` or `docs/deployment.md`.
