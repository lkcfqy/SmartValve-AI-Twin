# Third-party notices

## pdm-bench architecture reference

The raw-signal sensitivity models in
`src/smartvalve/experiments/paderborn_raw_sensitivity.py` adapt the layer definitions of
`pdm-bench` commit `ca524087219fd47bb7fb51ce63563c05b34cd6ee`:

- source: <https://github.com/1Sensor/pdm-bench>
- paper: Knap, Jachymczyk, and Lalik (2026), *Leakage-Safe, Reproducible Benchmarking for
  Vibration-Based Fault Diagnosis*, DOI `10.36001/phme.2026.v9i1.4924`
- upstream files: `src/pdm_bench/training/dl/models.py` and the Paderborn task configuration

The adaptation changes the source--target protocol, deterministic window sampling, seeding, and
artifact/inference layer. It is not represented as an exact reproduction of the upstream paper.

MIT License

Copyright (c) 2026 Paweł Knap and Urszula Jachymczyk

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
