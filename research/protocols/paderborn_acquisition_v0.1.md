# Paderborn Bearing DataCenter acquisition protocol v0.1

- Status: frozen before any archive was opened or any signal/model outcome was inspected
- Frozen: 2026-08-18
- Role: D2 sealed prospective validation dataset
- Official landing page: <https://mb.uni-paderborn.de/en/kat/research/bearing-datacenter>
- Official archive index: <https://groups.uni-paderborn.de/kat/BearingDataCenter/>
- License: Creative Commons Attribution-NonCommercial 4.0 International

## Scope

Acquire all 32 bearing archives exposed by the official index: six `K` healthy bearings, twelve
`KA` outer-ring damage bearings, three `KB` combined-damage bearings, and eleven `KI` inner-ring
damage bearings. The filename list is fixed in source before acquisition. No archive subset may be
selected from model performance.

At this stage the allowed operations are HTTP metadata inspection, byte download, size checking,
SHA-256 calculation and lock-manifest generation. Archives must not be opened, listed, extracted,
featured or used by a classifier. The official `readme_versions.txt` may be stored as provenance;
it reports a 2016 metadata correction for KI03 and contains no sensor outcome.

## Integrity model

The official server does not publish cryptographic checksums. The first complete download is
therefore an explicit trust-on-first-use lock from the HTTPS official host. For every archive,
persist the exact URL, byte count, SHA-256, ETag, Last-Modified value and acquisition time. Later
runs must verify the lock and must stop on any mismatch; they may not silently replace a locked
file.

Downloads use a `.part` file and an HTTP range request for safe continuation. A final filename is
created only after the advertised total byte count is present. An interrupted run and every
integrity failure remain visible in the recorded-run logs.

## Prospective seal

The completed archive lock establishes dataset identity but does not authorize outcome inspection.
Before any archive is opened, a separate Paderborn evaluation protocol must freeze:

1. the eligible files and measurements;
2. fault labels, asset split, operating-condition shifts and physical bootstrap unit;
3. preprocessing, feature/encoder representation and source-only model-selection rule;
4. the new SmartValve method, baselines, hyperparameters and seeds;
5. primary metrics, multiplicity correction and stopping rules; and
6. an automated one-shot seal check that records source and protocol hashes.

Once D2 results are produced, method or hyperparameter changes are prohibited. A necessary bug fix
must create a declared new protocol version, retain the original run and downgrade the corrected
run from prospective to sensitivity analysis unless the fix can be shown to be outcome-blind.

## License boundary

The archives are used only for noncommercial academic research under CC BY-NC 4.0 with required
attribution. They cannot be bundled into the public repository or reused in a commercial product
without separate permission from Paderborn University. Code and derived aggregate research results
remain separable from the locally cached archives.
