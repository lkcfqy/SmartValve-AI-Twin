#!/usr/bin/env bash
set -euo pipefail

cd /home/fqy/lkcproject/SmartValve-AI-Twin

exec >> artifacts/research/launch/EXP-460-461-watcher.log
exec 2>> artifacts/research/launch/EXP-460-461-watcher.err.log

TEMPLATE='paper/BEARING_MANUSCRIPT.md'
TEMPLATE_SHA256='2cab0c44e4d9f38236ea57adbca6ba0f07e3c7e2c9683190d80abb015611c9fb'

while true; do
  mapfile -t EXP459_RUNS < <(
    find artifacts/research/runs -maxdepth 1 -type d \
      -name 'EXP-459R1-BEARING-PAPER-VALIDATION__*' -print | sort
  )
  if (( ${#EXP459_RUNS[@]} == 0 )); then
    sleep 60
    continue
  fi
  if (( ${#EXP459_RUNS[@]} != 1 )); then
    printf '%s expected one EXP-459R1 run, observed %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP459_RUNS[@]}" >&2
    exit 20
  fi
  EXP459_RUN_DIR="${EXP459_RUNS[0]}"
  EXP459_STATUS="$({
    .venv/bin/python -c \
      "import json; from pathlib import Path; print(json.loads(Path('${EXP459_RUN_DIR}/metadata.json').read_text())['status'])"
  })"
  if [[ "${EXP459_STATUS}" == 'running' ]]; then
    sleep 60
    continue
  fi
  if [[ "${EXP459_STATUS}" != 'complete' ]]; then
    printf '%s EXP-459R1 ended with status=%s; manuscript handoff stopped\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${EXP459_STATUS}" >&2
    exit 21
  fi
  break
done

mapfile -t EXP458_RUNS < <(
  find artifacts/research/runs -maxdepth 1 -type d \
    -name 'EXP-458-BEARING-PAPER-ARTIFACTS__*' -print | sort
)
if (( ${#EXP458_RUNS[@]} != 1 )); then
  printf '%s expected one EXP-458 run, observed %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP458_RUNS[@]}" >&2
  exit 22
fi
EXP458_RUN_DIR="${EXP458_RUNS[0]}"
EXP458_STATUS="$({
  .venv/bin/python -c \
    "import json; from pathlib import Path; print(json.loads(Path('${EXP458_RUN_DIR}/metadata.json').read_text())['status'])"
})"
if [[ "${EXP458_STATUS}" != 'complete' ]]; then
  printf '%s EXP-458 status is %s; manuscript handoff stopped\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${EXP458_STATUS}" >&2
  exit 23
fi

ARTIFACT_MANIFEST="${EXP458_RUN_DIR}/outputs/bearing_artifact_manifest.json"
ARTIFACT_VALIDATION="${EXP459_RUN_DIR}/outputs/validation.json"
for REQUIRED_PATH in "${TEMPLATE}" "${ARTIFACT_MANIFEST}" "${ARTIFACT_VALIDATION}"; do
  if [[ ! -f "${REQUIRED_PATH}" ]]; then
    printf '%s required manuscript input is absent: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REQUIRED_PATH}" >&2
    exit 24
  fi
done

OBSERVED_TEMPLATE_SHA256="$(sha256sum "${TEMPLATE}" | awk '{print $1}')"
if [[ "${OBSERVED_TEMPLATE_SHA256}" != "${TEMPLATE_SHA256}" ]]; then
  printf '%s manuscript template changed: expected %s, observed %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${TEMPLATE_SHA256}" \
    "${OBSERVED_TEMPLATE_SHA256}" >&2
  exit 25
fi
ARTIFACT_MANIFEST_SHA256="$(sha256sum "${ARTIFACT_MANIFEST}" | awk '{print $1}')"
ARTIFACT_VALIDATOR_SOURCE_SHA256="$(
  sha256sum src/smartvalve/experiments/bearing_paper_validation.py | awk '{print $1}'
)"
if [[ "${ARTIFACT_VALIDATOR_SOURCE_SHA256}" != \
      'a2a9c26ffbcd8ed7f7964581b5cd35740e910c4be5d8c80babbc0300f4bcdcd9' ]]; then
  printf '%s artifact-validator source changed before manuscript rendering\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 29
fi

mapfile -t VALIDATION_FIELDS < <(
  .venv/bin/python - "${ARTIFACT_VALIDATION}" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value.get("status", ""))
print(str(value.get("refit_performed", "")).lower())
print(value.get("manifest_sha256", ""))
print(value.get("validator_version", ""))
print(value.get("input_count", ""))
print(value.get("output_count", ""))
print(str(float(value.get("raw_median_summary_csv_difference", 1.0)) <= 1e-12).lower())
PY
)
if [[ "${VALIDATION_FIELDS[0]}" != 'passed_independent_bearing_paper_artifact_validation' \
   || "${VALIDATION_FIELDS[1]}" != 'false' \
   || "${VALIDATION_FIELDS[2]}" != "${ARTIFACT_MANIFEST_SHA256}" \
   || "${VALIDATION_FIELDS[3]}" != 'smartvalve-bearing-paper-validator-0.4.1' \
   || "${VALIDATION_FIELDS[4]}" != '28' \
   || "${VALIDATION_FIELDS[5]}" != '42' \
   || "${VALIDATION_FIELDS[6]}" != 'true' ]]; then
  printf '%s EXP-459R1 validation fields do not authorize manuscript rendering\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 26
fi

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-460-BEARING-EMPIRICAL-MANUSCRIPT \
  --name hash-locked-empirical-final-human-fields-pending \
  --description "Render the empirically final bearing manuscript from the independently validated 42-output artifact manifest while retaining every human-owned submission hold." \
  -- \
  .venv/bin/python scripts/render_bearing_manuscript.py \
  --template "${TEMPLATE}" \
  --artifact-manifest "${ARTIFACT_MANIFEST}" \
  --artifact-manifest-sha256 "${ARTIFACT_MANIFEST_SHA256}" \
  --output '{run_dir}/outputs/BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md' \
  --report '{run_dir}/outputs/render_report.json'

mapfile -t EXP460_RUNS < <(
  find artifacts/research/runs -maxdepth 1 -type d \
    -name 'EXP-460-BEARING-EMPIRICAL-MANUSCRIPT__*' -print | sort
)
if (( ${#EXP460_RUNS[@]} != 1 )); then
  printf '%s expected one EXP-460 run, observed %s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP460_RUNS[@]}" >&2
  exit 27
fi
EXP460_RUN_DIR="${EXP460_RUNS[0]}"
EMPIRICAL_MANUSCRIPT="${EXP460_RUN_DIR}/outputs/BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md"
RENDER_REPORT="${EXP460_RUN_DIR}/outputs/render_report.json"
for REQUIRED_PATH in "${EMPIRICAL_MANUSCRIPT}" "${RENDER_REPORT}"; do
  if [[ ! -f "${REQUIRED_PATH}" ]]; then
    printf '%s EXP-460 output is absent: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REQUIRED_PATH}" >&2
    exit 28
  fi
done
EMPIRICAL_MANUSCRIPT_SHA256="$(sha256sum "${EMPIRICAL_MANUSCRIPT}" | awk '{print $1}')"
RENDER_REPORT_SHA256="$(sha256sum "${RENDER_REPORT}" | awk '{print $1}')"

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-461-BEARING-EMPIRICAL-MANUSCRIPT-VALIDATION \
  --name independent-hash-and-claim-manuscript-validation \
  --description "Independently verify the empirical manuscript abstract, raw outcomes, rule wording, artifact callouts, counts, hashes, and retained human holds without calling its renderer." \
  -- \
  .venv/bin/python scripts/validate_bearing_manuscript.py \
  --manuscript "${EMPIRICAL_MANUSCRIPT}" \
  --manuscript-sha256 "${EMPIRICAL_MANUSCRIPT_SHA256}" \
  --report "${RENDER_REPORT}" \
  --report-sha256 "${RENDER_REPORT_SHA256}" \
  --template "${TEMPLATE}" \
  --template-sha256 "${TEMPLATE_SHA256}" \
  --artifact-manifest "${ARTIFACT_MANIFEST}" \
  --artifact-manifest-sha256 "${ARTIFACT_MANIFEST_SHA256}" \
  --output '{run_dir}/outputs/validation.json'

printf '%s EXP-460/461 empirical manuscript handoff completed\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
