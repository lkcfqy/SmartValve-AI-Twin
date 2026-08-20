#!/usr/bin/env python3
"""Fail unless the active quality environment uses the locked CPU-only PyTorch build."""

from __future__ import annotations

import json
from importlib.metadata import version

import torch

EXPECTED_TORCH_VERSION = "2.13.0+cpu"


def main() -> None:
    metadata_version = version("torch")
    runtime_version = str(torch.__version__)
    result = {
        "status": "passed_cpu_quality_environment_validation",
        "expected_torch_version": EXPECTED_TORCH_VERSION,
        "metadata_torch_version": metadata_version,
        "runtime_torch_version": runtime_version,
        "compiled_cuda_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
    }
    if (
        metadata_version != EXPECTED_TORCH_VERSION
        or runtime_version != EXPECTED_TORCH_VERSION
        or torch.version.cuda is not None
        or result["cuda_available"] is not False
    ):
        result["status"] = "failed_cpu_quality_environment_validation"
        raise RuntimeError(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
