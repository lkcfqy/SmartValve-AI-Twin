#!/usr/bin/env bash
set -euo pipefail

cd /home/fqy/lkcproject/SmartValve-AI-Twin

exec >> artifacts/research/launch/EXP-457-watcher.log
exec 2>> artifacts/research/launch/EXP-457-watcher.err.log

RAW_RUN_DIR='artifacts/research/runs/EXP-456R1-PADERBORN-RAW-ARCHITECTURES__20260819T021356.938756Z__sealed-raw-fft-stft-protocol-sensitivity-rerun1'
SEAL_SHA256='d82557180cf7cdbb1075d041dc0c3fa106e270041033adbcb6fcfaeb94a5d63b'
EXPECTED_MANIFEST='artifacts/research/runs/EXP-476-PADERBORN-RAW-TOPOLOGY-MANIFEST__20260819T084548.389414Z__outcome-blind-exact-raw-prediction-key-manifest/outputs/expected_raw_topology_manifest.json'
EXPECTED_MANIFEST_SHA256='440b6e9f3a5c156a3b022a7ea8a5667de33c8bc954c3223f73df5be53f622607'
FEATURES='artifacts/research/runs/EXP-406-PADERBORN-FEATURES__20260818T141439.240427Z__v05-resampled-outcome-blind-features/outputs/primary_feature_matrix.parquet'
FEATURES_SHA256='c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4'
RAW_WINDOW_DIR='artifacts/research/runs/EXP-455-PADERBORN-RAW-WINDOWS__20260818T222514.301091Z__hash-locked-four-window-vibration-artifact/outputs'
RAW_WINDOW_SUMMARY_SHA256='af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191'
MISSING_PROCESS_POLLS=0

while true; do
  RUN_STATUS="$({
    .venv/bin/python -c \
      "import json; from pathlib import Path; print(json.loads(Path('${RAW_RUN_DIR}/metadata.json').read_text())['status'])"
  })"
  if [[ "${RUN_STATUS}" != 'running' ]]; then
    break
  fi
  if pgrep -f "${RAW_RUN_DIR}/outputs" >/dev/null; then
    MISSING_PROCESS_POLLS=0
  else
    MISSING_PROCESS_POLLS=$((MISSING_PROCESS_POLLS + 1))
    if (( MISSING_PROCESS_POLLS >= 3 )); then
      printf '%s EXP-456R1 metadata is running but its process is absent\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
      exit 2
    fi
  fi
  sleep 60
done

if [[ "${RUN_STATUS}" != 'complete' ]]; then
  printf '%s EXP-456R1 ended with status=%s; EXP-457 not started\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${RUN_STATUS}" >&2
  exit 3
fi

RAW_SUMMARY="${RAW_RUN_DIR}/outputs/raw_architecture_sensitivity_summary.json"
if [[ ! -f "${RAW_SUMMARY}" ]]; then
  printf '%s EXP-456R1 completed without its declared summary\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 4
fi
RAW_SUMMARY_SHA256="$(sha256sum "${RAW_SUMMARY}" | awk '{print $1}')"

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-457-PADERBORN-RAW-VALIDATION \
  --name independent-no-refit-raw-architecture-validation \
  --description "Independently recompute the sealed raw-architecture topology, aggregation, physical-bearing bootstrap, and gate without fitting." \
  -- \
  .venv/bin/python scripts/validate_paderborn_raw_architecture_sensitivity.py \
  --result-dir "${RAW_RUN_DIR}/outputs" \
  --summary-sha256 "${RAW_SUMMARY_SHA256}" \
  --seal research/PADERBORN_RAW_ARCHITECTURE_SENSITIVITY_SEAL.md \
  --seal-sha256 "${SEAL_SHA256}" \
  --features-sha256 "${FEATURES_SHA256}" \
  --raw-window-summary-sha256 "${RAW_WINDOW_SUMMARY_SHA256}" \
  --output '{run_dir}/outputs/validation.json'

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-477-PADERBORN-RAW-TOPOLOGY-VALIDATION \
  --name preoutcome-manifest-exact-key-and-physical-metadata-validation \
  --description "Validate every raw prediction key, fold assignment, physical metadata row, model-state identity, training-trace schedule, and probability vector against the outcome-blind EXP-476 manifest without refitting, recomputing metrics, or reading the gate." \
  -- \
  .venv/bin/python scripts/validate_paderborn_raw_topology.py \
  --result-dir "${RAW_RUN_DIR}/outputs" \
  --result-summary-sha256 "${RAW_SUMMARY_SHA256}" \
  --expected-manifest "${EXPECTED_MANIFEST}" \
  --expected-manifest-sha256 "${EXPECTED_MANIFEST_SHA256}" \
  --features "${FEATURES}" \
  --features-sha256 "${FEATURES_SHA256}" \
  --raw-window-dir "${RAW_WINDOW_DIR}" \
  --raw-window-summary-sha256 "${RAW_WINDOW_SUMMARY_SHA256}" \
  --seal research/PADERBORN_RAW_ARCHITECTURE_SENSITIVITY_SEAL.md \
  --seal-sha256 "${SEAL_SHA256}" \
  --output '{run_dir}/outputs/validation.json'

printf '%s EXP-457 metric validation and EXP-477 exact-topology validation completed\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
