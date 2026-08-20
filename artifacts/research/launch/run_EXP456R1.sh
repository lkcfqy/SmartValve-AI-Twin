#!/usr/bin/env bash
set -euo pipefail

cd /home/fqy/lkcproject/SmartValve-AI-Twin

exec .venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-456R1-PADERBORN-RAW-ARCHITECTURES \
  --name sealed-raw-fft-stft-protocol-sensitivity-rerun1 \
  --description "Full from-scratch recovery rerun after externally interrupted EXP-456; exact frozen retrospective raw-vibration architecture sensitivity." \
  -- \
  .venv/bin/python scripts/paderborn_raw_architecture_sensitivity.py \
  --raw-window-dir artifacts/research/runs/EXP-455-PADERBORN-RAW-WINDOWS__20260818T222514.301091Z__hash-locked-four-window-vibration-artifact/outputs \
  --raw-window-summary-sha256 af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191 \
  --features artifacts/research/runs/EXP-406-PADERBORN-FEATURES__20260818T141439.240427Z__v05-resampled-outcome-blind-features/outputs/primary_feature_matrix.parquet \
  --features-sha256 c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4 \
  --seal research/PADERBORN_RAW_ARCHITECTURE_SENSITIVITY_SEAL.md \
  --seal-sha256 d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b \
  --output-dir '{run_dir}/outputs' \
  --device cuda:0 \
  --epochs 50 \
  --batch-size 128 \
  --bootstrap-draws 2000 \
  >> artifacts/research/launch/EXP-456R1.outer.log \
  2>> artifacts/research/launch/EXP-456R1.outer.err.log

