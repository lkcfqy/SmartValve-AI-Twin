#!/usr/bin/env bash
set -euo pipefail

cd /home/fqy/lkcproject/SmartValve-AI-Twin

exec >> artifacts/research/launch/EXP-458-459-watcher.log
exec 2>> artifacts/research/launch/EXP-458-459-watcher.err.log

RAW_RUN_DIR='artifacts/research/runs/EXP-456R1-PADERBORN-RAW-ARCHITECTURES__20260819T021356.938756Z__sealed-raw-fft-stft-protocol-sensitivity-rerun1'
PADERBORN_DIR='artifacts/research/runs/EXP-434B-PADERBORN-NEURAL-PROTOCOL__20260818T180706.816990Z__frozen-nine-method-four-protocol-neural-audit/outputs'
PADERBORN_VALIDATION='artifacts/research/runs/EXP-456A-PADERBORN-PROTOCOL-VALIDATION__20260818T232953.691340Z__explicit-no-refit-neural-protocol-validation/outputs/validation.json'
SENSOR_DIR='artifacts/research/runs/EXP-452-PADERBORN-NEURAL-SENSOR-ATTRIBUTION__20260818T223740.164619Z__combined-three-sensor-neural-attribution/outputs'
SENSOR_VALIDATION='artifacts/research/runs/EXP-453-PADERBORN-NEURAL-SENSOR-VALIDATION__20260818T223826.374149Z__independent-no-refit-three-sensor-validation/outputs/validation.json'
HUST_DIR='artifacts/research/runs/EXP-445-HUST-D3-NEURAL__20260818T201519.078287Z__sealed-one-shot-four-protocol-external-replicati/outputs'
HUST_VALIDATION='artifacts/research/runs/EXP-447-HUST-D3-VALIDATION__20260818T210012.883809Z__independent-no-refit-primary-validation/outputs/validation.json'
HUST_CONTROL_DIR='artifacts/research/runs/EXP-449-HUST-D3-SIZE-MATCHED__20260818T210049.008798Z__sealed-equal-volume-access-control/outputs'
HUST_CONTROL_VALIDATION='artifacts/research/runs/EXP-450B-HUST-D3-SIZE-MATCHED-VALIDATION__20260818T213134.678697Z__tolerant-independent-no-refit-equal-volume-valid/outputs/validation.json'
HUST_INFLUENCE_DIR='artifacts/research/runs/EXP-464R1-HUST-PHYSICAL-UNIT-INFLUENCE__20260819T041145.489149Z__frozen-posthoc-bearing-and-group-deletion-audit-/outputs'
HUST_INFLUENCE_VALIDATION='artifacts/research/runs/EXP-465-HUST-PHYSICAL-UNIT-INFLUENCE-VALIDATION__20260819T041225.238341Z__independent-manual-f1-and-deletion-recomputation/outputs/validation.json'
RAW_WINDOW_DIR='artifacts/research/runs/EXP-455-PADERBORN-RAW-WINDOWS__20260818T222514.301091Z__hash-locked-four-window-vibration-artifact/outputs'

while true; do
  mapfile -t EXP457_RUNS < <(
    find artifacts/research/runs -maxdepth 1 -type d \
      -name 'EXP-457-PADERBORN-RAW-VALIDATION__*' -print | sort
  )
  if (( ${#EXP457_RUNS[@]} == 0 )); then
    sleep 60
    continue
  fi
  if (( ${#EXP457_RUNS[@]} != 1 )); then
    printf '%s expected one EXP-457 run, observed %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP457_RUNS[@]}" >&2
    exit 10
  fi
  EXP457_RUN_DIR="${EXP457_RUNS[0]}"
  EXP457_STATUS="$({
    .venv/bin/python -c \
      "import json; from pathlib import Path; print(json.loads(Path('${EXP457_RUN_DIR}/metadata.json').read_text())['status'])"
  })"
  if [[ "${EXP457_STATUS}" == 'running' ]]; then
    sleep 60
    continue
  fi
  if [[ "${EXP457_STATUS}" != 'complete' ]]; then
    printf '%s EXP-457 ended with status=%s; artifact handoff stopped\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${EXP457_STATUS}" >&2
    exit 11
  fi
  break
done

while true; do
  mapfile -t EXP477_RUNS < <(
    find artifacts/research/runs -maxdepth 1 -type d \
      -name 'EXP-477-PADERBORN-RAW-TOPOLOGY-VALIDATION__*' -print | sort
  )
  if (( ${#EXP477_RUNS[@]} == 0 )); then
    sleep 60
    continue
  fi
  if (( ${#EXP477_RUNS[@]} != 1 )); then
    printf '%s expected one EXP-477 run, observed %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP477_RUNS[@]}" >&2
    exit 15
  fi
  EXP477_RUN_DIR="${EXP477_RUNS[0]}"
  EXP477_STATUS="$({
    .venv/bin/python -c \
      "import json; from pathlib import Path; print(json.loads(Path('${EXP477_RUN_DIR}/metadata.json').read_text())['status'])"
  })"
  if [[ "${EXP477_STATUS}" == 'running' ]]; then
    sleep 60
    continue
  fi
  if [[ "${EXP477_STATUS}" != 'complete' ]]; then
    printf '%s EXP-477 ended with status=%s; artifact handoff stopped\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${EXP477_STATUS}" >&2
    exit 16
  fi
  break
done

RAW_SUMMARY="${RAW_RUN_DIR}/outputs/raw_architecture_sensitivity_summary.json"
RAW_VALIDATION="${EXP457_RUN_DIR}/outputs/validation.json"
RAW_TOPOLOGY_VALIDATION="${EXP477_RUN_DIR}/outputs/validation.json"
for REQUIRED_PATH in "${RAW_SUMMARY}" "${RAW_VALIDATION}" "${PADERBORN_VALIDATION}" \
  "${SENSOR_VALIDATION}" "${HUST_VALIDATION}" "${HUST_CONTROL_VALIDATION}" \
  "${HUST_INFLUENCE_DIR}/hust_influence_audit_summary.json" \
  "${HUST_INFLUENCE_VALIDATION}" "${RAW_TOPOLOGY_VALIDATION}"; do
  if [[ ! -f "${REQUIRED_PATH}" ]]; then
    printf '%s required validated input is absent: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REQUIRED_PATH}" >&2
    exit 12
  fi
done

mapfile -t RAW_VALIDATION_FIELDS < <(
  .venv/bin/python - "${RAW_VALIDATION}" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
implementation = value.get("calculation_implementation", {})
inputs = value.get("input_sha256", {})
counts = value.get("validated_counts", {})
print(value.get("status", ""))
print(str(value.get("refit_performed", "")).lower())
print(inputs.get("features", ""))
print(inputs.get("raw_window_summary", ""))
print(implementation.get("version", ""))
print(str(implementation.get("shared_producer_calculation_code", "")).lower())
print(implementation.get("module_sha256", ""))
print(implementation.get("cli_sha256", ""))
for name in (
    "fits",
    "window_predictions",
    "seed_recording_predictions",
    "ensemble_recording_predictions",
):
    print(counts.get(name, ""))
PY
)
if [[ "${RAW_VALIDATION_FIELDS[0]}" != 'passed_independent_no_refit_recomputation' \
   || "${RAW_VALIDATION_FIELDS[1]}" != 'false' \
   || "${RAW_VALIDATION_FIELDS[2]}" != \
      'c5caf0cfc408057ae4bfaebef37abdf597135620105ec62e17f3aece6800aff4' \
   || "${RAW_VALIDATION_FIELDS[3]}" != \
      'af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191' \
   || "${RAW_VALIDATION_FIELDS[4]}" != \
      'smartvalve-paderborn-raw-independent-calculations-0.2.0' \
   || "${RAW_VALIDATION_FIELDS[5]}" != 'false' \
   || "${RAW_VALIDATION_FIELDS[6]}" != \
      'd053dc678cd382c603e071e2b1f2a9c0b50ce3beaae8d7e20b63b1bbb5db2a17' \
   || "${RAW_VALIDATION_FIELDS[7]}" != \
      '9ae4cd837d9f2383b5bc36f29c4038c096907e9606f6e866018744962cfa7acf' \
   || "${RAW_VALIDATION_FIELDS[8]}" != '270' \
   || "${RAW_VALIDATION_FIELDS[9]}" != '166968' \
   || "${RAW_VALIDATION_FIELDS[10]}" != '41742' \
   || "${RAW_VALIDATION_FIELDS[11]}" != '13914' ]]; then
  printf '%s EXP-457 independent-calculation identity does not authorize artifacts\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 18
fi

mapfile -t RAW_TOPOLOGY_FIELDS < <(
  .venv/bin/python - "${RAW_TOPOLOGY_VALIDATION}" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value.get("status", ""))
print(str(value.get("refit_performed", "")).lower())
print(str(value.get("aggregate_metrics_recomputed", "")).lower())
print(str(value.get("gate_outcome_read", "")).lower())
print(value.get("input_sha256", {}).get("expected_manifest", ""))
for name in (
    "window_predictions",
    "seed_recording_predictions",
    "ensemble_recording_predictions",
    "fits",
    "training_traces",
):
    print(value.get("validated_key_sets", {}).get(name, {}).get("count", ""))
PY
)
if [[ "${RAW_TOPOLOGY_FIELDS[0]}" != \
      'passed_independent_raw_prediction_topology_validation' \
   || "${RAW_TOPOLOGY_FIELDS[1]}" != 'false' \
   || "${RAW_TOPOLOGY_FIELDS[2]}" != 'false' \
   || "${RAW_TOPOLOGY_FIELDS[3]}" != 'false' \
   || "${RAW_TOPOLOGY_FIELDS[4]}" != \
      '440b6e9f3a5c156a3b022a7ea8a5667de33c8bc954c3223f73df5be53f622607' \
   || "${RAW_TOPOLOGY_FIELDS[5]}" != '166968' \
   || "${RAW_TOPOLOGY_FIELDS[6]}" != '41742' \
   || "${RAW_TOPOLOGY_FIELDS[7]}" != '13914' \
   || "${RAW_TOPOLOGY_FIELDS[8]}" != '270' \
   || "${RAW_TOPOLOGY_FIELDS[9]}" != '270' ]]; then
  printf '%s EXP-477 exact-topology fields do not authorize artifact construction\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 17
fi

RAW_SUMMARY_SHA256="$(sha256sum "${RAW_SUMMARY}" | awk '{print $1}')"
RAW_VALIDATION_SHA256="$(sha256sum "${RAW_VALIDATION}" | awk '{print $1}')"

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-458-BEARING-PAPER-ARTIFACTS \
  --name final-validated-bearing-paper-artifacts \
  --description "Generate the deterministic 28-input and 42-output bearing manuscript artifact package only from independently validated result families and the post-hoc physical-unit influence audit." \
  -- \
  .venv/bin/python scripts/bearing_paper_artifacts.py \
  --paderborn-dir "${PADERBORN_DIR}" \
  --paderborn-summary-sha256 0a717c6bc1e4d94182b11f91502397d32a3816d86931ed5369316714a2a13a9e \
  --paderborn-validation "${PADERBORN_VALIDATION}" \
  --paderborn-validation-sha256 03428d40112509c08ffe11bf56ca172a6975b5570d653bc5ac1fbf5a0ece8099 \
  --sensor-dir "${SENSOR_DIR}" \
  --sensor-summary-sha256 72f1bbca7ae6fa2e50f105ff699a2022b7705ca8cda0dd2ea43c341edb8b23ea \
  --sensor-validation "${SENSOR_VALIDATION}" \
  --sensor-validation-sha256 acb71e10125a710681ae3fc8fee72ee7f691947d21932955af753a5d5301c5cc \
  --hust-dir "${HUST_DIR}" \
  --hust-summary-sha256 3f721ff50cc72b845d5ce16a3c7ef987ae5c33cb0d69bfab0804a9be38b5d61a \
  --hust-validation "${HUST_VALIDATION}" \
  --hust-validation-sha256 ba9ceee356fe8cc04ddfe1a28f6e46038fd0c60c4ea374df196400b22fdf6c6a \
  --hust-control-dir "${HUST_CONTROL_DIR}" \
  --hust-control-summary-sha256 23b898440a6a09c4efd21ea6e9faec16ca637989a5310e4fa69f8067f5e4833c \
  --hust-control-validation "${HUST_CONTROL_VALIDATION}" \
  --hust-control-validation-sha256 b7e13cf20ff51d06690e56b0f1d45102ecba23dc0df56ad4a7790e4c5d263abe \
  --hust-influence-dir "${HUST_INFLUENCE_DIR}" \
  --hust-influence-summary-sha256 431e580c9ee2d3489980fd4edad31151f97eeff343656473d1df8504c2406e18 \
  --hust-influence-validation "${HUST_INFLUENCE_VALIDATION}" \
  --hust-influence-validation-sha256 dfb88a40883c71059eab856bfc6e25247192431b83a66ebbdc6f1bbccd0e587a \
  --raw-dir "${RAW_RUN_DIR}/outputs" \
  --raw-summary-sha256 "${RAW_SUMMARY_SHA256}" \
  --raw-window-dir "${RAW_WINDOW_DIR}" \
  --raw-window-summary-sha256 af4d323348b14af03f35bed575b426a0909064e276ab33b821d5b39dbed47191 \
  --raw-validation "${RAW_VALIDATION}" \
  --raw-validation-sha256 "${RAW_VALIDATION_SHA256}" \
  --output-dir '{run_dir}/outputs' \
  --project-root .

mapfile -t EXP458_RUNS < <(
  find artifacts/research/runs -maxdepth 1 -type d \
    -name 'EXP-458-BEARING-PAPER-ARTIFACTS__*' -print | sort
)
if (( ${#EXP458_RUNS[@]} != 1 )); then
  printf '%s expected one completed EXP-458 run, observed %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP458_RUNS[@]}" >&2
  exit 13
fi
EXP458_RUN_DIR="${EXP458_RUNS[0]}"
ARTIFACT_MANIFEST="${EXP458_RUN_DIR}/outputs/bearing_artifact_manifest.json"
if [[ ! -f "${ARTIFACT_MANIFEST}" ]]; then
  printf '%s EXP-458 completed without its artifact manifest\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 14
fi
ARTIFACT_MANIFEST_SHA256="$(sha256sum "${ARTIFACT_MANIFEST}" | awk '{print $1}')"

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-459R1-BEARING-PAPER-VALIDATION \
  --name independent-no-refit-bearing-paper-artifact-validation-csv-tolerance \
  --description "Independently rehash and recompute the final bearing-paper package without invoking its generator or fitting a model; preserve full-precision summary decisions while accepting at most 1e-12 deterministic CSV serialization difference." \
  -- \
  .venv/bin/python scripts/validate_bearing_paper_artifacts.py \
  --manifest "${ARTIFACT_MANIFEST}" \
  --manifest-sha256 "${ARTIFACT_MANIFEST_SHA256}" \
  --project-root . \
  --output '{run_dir}/outputs/validation.json'

printf '%s EXP-457 through EXP-459 deterministic handoff completed\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
