"""Record a deterministic PyTorch CUDA forward/backward environment smoke test."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")

import torch
from torch import Tensor, nn

SEED = 20_260_818
INPUT_DIMENSION = 136
CLASS_COUNT = 3
BATCH_SIZE = 4_096
TIMED_STEPS = 20


def _tensor_sha256(tensor: Tensor) -> str:
    data = tensor.detach().cpu().contiguous().numpy().tobytes()
    return hashlib.sha256(data).hexdigest()


def _build_model() -> nn.Module:
    return nn.Sequential(
        nn.Linear(INPUT_DIMENSION, 256),
        nn.GELU(),
        nn.Linear(256, 128),
        nn.GELU(),
        nn.Linear(128, CLASS_COUNT),
    )


def _single_step(
    *,
    device: torch.device,
    state: dict[str, Tensor],
    features: Tensor,
    targets: Tensor,
) -> dict[str, Any]:
    model = _build_model().to(device)
    model.load_state_dict({key: value.to(device) for key, value in state.items()})
    local_features = features.to(device)
    local_targets = targets.to(device)
    model.zero_grad(set_to_none=True)
    logits = model(local_features)
    loss = nn.functional.cross_entropy(logits, local_targets)
    loss.backward()
    gradients = torch.cat(
        [parameter.grad.detach().reshape(-1) for parameter in model.parameters()]
    )
    return {
        "logits": logits.detach().cpu(),
        "gradients": gradients.detach().cpu(),
        "loss": float(loss.detach().cpu()),
        "finite": bool(
            torch.isfinite(logits).all().item()
            and torch.isfinite(gradients).all().item()
            and torch.isfinite(loss).item()
        ),
        "gradient_l2": float(torch.linalg.vector_norm(gradients).detach().cpu()),
    }


def _nvidia_smi() -> dict[str, str] | None:
    command = [
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader,nounits",
    ]
    try:
        output = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return None
    name, driver, memory = (part.strip() for part in output.split(",", maxsplit=2))
    return {
        "name": name,
        "driver_version": driver,
        "memory_total_mib": memory,
    }


def _pip_freeze() -> str:
    return subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    ).stdout


def run(output_directory: Path) -> dict[str, Any]:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available to PyTorch")

    torch.manual_seed(SEED)
    torch.cuda.manual_seed_all(SEED)
    torch.use_deterministic_algorithms(True)
    torch.set_float32_matmul_precision("highest")
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

    generator = torch.Generator(device="cpu").manual_seed(SEED)
    features = torch.randn(BATCH_SIZE, INPUT_DIMENSION, generator=generator)
    targets = torch.randint(CLASS_COUNT, (BATCH_SIZE,), generator=generator)
    reference_model = _build_model()
    initial_state = {
        key: value.detach().clone() for key, value in reference_model.state_dict().items()
    }

    device_index = 0
    device = torch.device(f"cuda:{device_index}")
    torch.cuda.init()
    torch.cuda.reset_peak_memory_stats(device_index)
    cuda_first = _single_step(
        device=device,
        state=initial_state,
        features=features,
        targets=targets,
    )
    cuda_second = _single_step(
        device=device,
        state=initial_state,
        features=features,
        targets=targets,
    )
    torch.cuda.synchronize(device)
    cpu_result = _single_step(
        device=torch.device("cpu"),
        state=initial_state,
        features=features,
        targets=targets,
    )

    logits_repeat_exact = torch.equal(cuda_first["logits"], cuda_second["logits"])
    gradients_repeat_exact = torch.equal(
        cuda_first["gradients"], cuda_second["gradients"]
    )
    logits_cpu_gpu_max_abs = float(
        (cuda_first["logits"] - cpu_result["logits"]).abs().max()
    )
    gradients_cpu_gpu_max_abs = float(
        (cuda_first["gradients"] - cpu_result["gradients"]).abs().max()
    )
    loss_cpu_gpu_abs = abs(cuda_first["loss"] - cpu_result["loss"])

    timed_model = _build_model().to(device)
    timed_features = features.to(device)
    timed_targets = targets.to(device)
    optimizer = torch.optim.AdamW(timed_model.parameters(), lr=1e-3)
    for _ in range(3):
        optimizer.zero_grad(set_to_none=True)
        nn.functional.cross_entropy(timed_model(timed_features), timed_targets).backward()
        optimizer.step()
    torch.cuda.synchronize(device)
    started = perf_counter()
    for _ in range(TIMED_STEPS):
        optimizer.zero_grad(set_to_none=True)
        nn.functional.cross_entropy(timed_model(timed_features), timed_targets).backward()
        optimizer.step()
    torch.cuda.synchronize(device)
    elapsed_seconds = perf_counter() - started

    properties = torch.cuda.get_device_properties(device_index)
    checks = {
        "cuda_available": True,
        "cuda_repeat_logits_exact": logits_repeat_exact,
        "cuda_repeat_gradients_exact": gradients_repeat_exact,
        "cuda_outputs_finite": cuda_first["finite"] and cuda_second["finite"],
        "cpu_outputs_finite": cpu_result["finite"],
        "cpu_gpu_logits_max_abs_le_1e-4": logits_cpu_gpu_max_abs <= 1e-4,
        "cpu_gpu_gradients_max_abs_le_1e-4": gradients_cpu_gpu_max_abs <= 1e-4,
        "cpu_gpu_loss_abs_le_1e-6": loss_cpu_gpu_abs <= 1e-6,
        "nonzero_gradient": cuda_first["gradient_l2"] > 0.0,
    }
    payload: dict[str, Any] = {
        "schema_version": "smartvalve-gpu-environment-smoke-0.1.0",
        "seed": SEED,
        "configuration": {
            "input_dimension": INPUT_DIMENSION,
            "class_count": CLASS_COUNT,
            "batch_size": BATCH_SIZE,
            "timed_steps": TIMED_STEPS,
            "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
            "cublas_workspace_config": os.environ["CUBLAS_WORKSPACE_CONFIG"],
            "float32_matmul_precision": torch.get_float32_matmul_precision(),
        },
        "environment": {
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "torch_version": torch.__version__,
            "torch_cuda_version": torch.version.cuda,
            "cudnn_version": torch.backends.cudnn.version(),
            "nvidia_smi": _nvidia_smi(),
            "device": {
                "name": properties.name,
                "compute_capability": [properties.major, properties.minor],
                "total_memory_bytes": properties.total_memory,
                "multiprocessor_count": properties.multi_processor_count,
            },
        },
        "numerics": {
            "cuda_loss": cuda_first["loss"],
            "cpu_loss": cpu_result["loss"],
            "loss_cpu_gpu_abs": loss_cpu_gpu_abs,
            "logits_cpu_gpu_max_abs": logits_cpu_gpu_max_abs,
            "gradients_cpu_gpu_max_abs": gradients_cpu_gpu_max_abs,
            "cuda_gradient_l2": cuda_first["gradient_l2"],
            "cuda_logits_sha256": _tensor_sha256(cuda_first["logits"]),
            "cuda_gradients_sha256": _tensor_sha256(cuda_first["gradients"]),
        },
        "feasibility": {
            "elapsed_seconds": elapsed_seconds,
            "training_samples_per_second": BATCH_SIZE * TIMED_STEPS / elapsed_seconds,
            "peak_memory_bytes": torch.cuda.max_memory_allocated(device_index),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }

    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "gpu_environment.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_directory / "pip_freeze.txt").write_text(_pip_freeze(), encoding="utf-8")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    payload = run(args.output_dir)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(0 if payload["passed"] else 1)


if __name__ == "__main__":
    main()
