# Cranfield paired-bootstrap protocol v0.1

- Status: frozen before EXP-011 results
- Frozen: 2026-08-17
- Input: final EXP-010 v0.1.1 prediction records
- Replicates: 2,000
- Bootstrap RNG seed: 20,260,817

## Estimands

For each protocol, point estimates average the metric over seeds `[11, 23, 37, 53, 71]`.
Intervals quantify experimental-block uncertainty conditional on that frozen five-seed ensemble;
seeds are not treated as independent physical samples.

Performance metrics are accuracy, macro F1, worst-fold macro F1, multiclass Brier score, and
10-bin ECE. Control metrics are nuisance total variation, fault total variation, and their ratio.

## Performance bootstrap

The physical block is `(motion, load_kg, repetition)` and contains all three fault states. Within
each of the six `(motion, load_kg)` strata, sample ten blocks with replacement. Use the same sampled
block sequence for every protocol and random seed. This preserves fold sizes, class balance, and
paired protocol comparisons.

## Control bootstrap

The control metrics compare loads at matched repetition indices. To preserve that topology, sample
ten repetition indices with replacement within each motion and carry all three load blocks and all
three fault states for each draw. This is a synchronized cluster bootstrap over the pre-registered
physical blocks. It is more conservative than treating load blocks as independent and is reported
separately from the performance bootstrap.

## Intervals and comparisons

- Use percentile 95% intervals at the 2.5th and 97.5th percentiles.
- Apply each replicate's sampling indices identically to P0, P1, and P2.
- Report paired differences P1-P0, P2-P0, and P2-P1.
- A paired effect is called statistically resolved only when its interval excludes zero.
- No multiplicity correction is applied; comparison intervals are estimation, not confirmatory
  family-wise hypothesis tests.

Failed replicates, missing cells, non-finite probabilities, and incomplete seed/protocol grids stop
the run rather than being silently dropped.
