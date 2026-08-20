# RTX 3080 PyTorch/CUDA environment record v0.1

- Status: validated
- Date: 2026-08-18
- Host layer: WSL2, Ubuntu 24.04, Python 3.12.3
- GPU: NVIDIA GeForce RTX 3080, 10,240 MiB, compute capability 8.6
- Driver: 610.74
- PyTorch: 2.13.0+cu130
- Compiled CUDA: 13.0
- cuDNN reported by PyTorch: 9.20.0

## Installation boundary

The CUDA build was installed from the official PyTorch CUDA 13.0 wheel index:

    .venv/bin/python -m pip install \
      --index-url https://download.pytorch.org/whl/cu130 \
      torch==2.13.0+cu130

The project research extra declares the public-version constraint torch==2.13.0 for dependency
discovery. Reproduction of this Linux/RTX environment must additionally use the index and local
version above. Mac development may use the platform-native wheel and must be reported as a
different compute environment.

The exact installed distribution set is preserved in the successful recorded run as
outputs/pip_freeze.txt. It is evidence for this workstation, not a portable cross-platform lock.

## Validation history

- EXP-300-GPU-ENV failed before tensor execution because the memory-statistics call received an
  uninitialized device object. The run is retained.
- EXP-301-GPU-ENV changed the argument to integer device zero but still called the allocator
  before CUDA context initialization. The run is retained.
- EXP-302-GPU-ENV explicitly initialized the CUDA context and passed every frozen check.

The final run requires two independently reconstructed CUDA forward/backward passes to be
bit-for-bit identical. It also requires finite, nonzero gradients and CPU/GPU maximum absolute
differences below frozen tolerances. Its JSON and full package inventory are hashed by the
recorded-run manifest.

The measured microbenchmark is only a feasibility check for the compact tabular network. It is not
a model comparison, an application latency claim, or a substitute for per-method compute reporting
in the final experiments.
