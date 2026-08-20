#!/usr/bin/env bash
set -euo pipefail

cd /home/fqy/lkcproject/SmartValve-AI-Twin

exec >> artifacts/research/launch/EXP-462-463-watcher.log
exec 2>> artifacts/research/launch/EXP-462-463-watcher.err.log

run_status() {
  .venv/bin/python -c \
    "import json; from pathlib import Path; print(json.loads(Path('$1/metadata.json').read_text())['status'])"
}

unique_run() {
  local pattern="$1"
  local label="$2"
  local -a runs
  mapfile -t runs < <(
    find artifacts/research/runs -maxdepth 1 -type d -name "${pattern}" -print | sort
  )
  if (( ${#runs[@]} != 1 )); then
    printf '%s expected one %s run, observed %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${label}" "${#runs[@]}" >&2
    return 20
  fi
  printf '%s\n' "${runs[0]}"
}

while true; do
  mapfile -t EXP461_RUNS < <(
    find artifacts/research/runs -maxdepth 1 -type d \
      -name 'EXP-461-BEARING-EMPIRICAL-MANUSCRIPT-VALIDATION__*' -print | sort
  )
  if (( ${#EXP461_RUNS[@]} == 0 )); then
    sleep 60
    continue
  fi
  if (( ${#EXP461_RUNS[@]} != 1 )); then
    printf '%s expected one EXP-461 run, observed %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP461_RUNS[@]}" >&2
    exit 21
  fi
  EXP461_RUN_DIR="${EXP461_RUNS[0]}"
  EXP461_STATUS="$(run_status "${EXP461_RUN_DIR}")"
  if [[ "${EXP461_STATUS}" == 'running' ]]; then
    sleep 60
    continue
  fi
  if [[ "${EXP461_STATUS}" != 'complete' ]]; then
    printf '%s EXP-461 ended with status=%s; release handoff stopped\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${EXP461_STATUS}" >&2
    exit 22
  fi
  break
done

EXP458_RUN_DIR="$(unique_run 'EXP-458-BEARING-PAPER-ARTIFACTS__*' 'EXP-458')"
EXP459_RUN_DIR="$(unique_run 'EXP-459R1-BEARING-PAPER-VALIDATION__*' 'EXP-459R1')"
EXP460_RUN_DIR="$(unique_run 'EXP-460-BEARING-EMPIRICAL-MANUSCRIPT__*' 'EXP-460')"
EXP477_RUN_DIR="$(unique_run 'EXP-477-PADERBORN-RAW-TOPOLOGY-VALIDATION__*' 'EXP-477')"
for RUN_DIR in \
  "${EXP458_RUN_DIR}" \
  "${EXP459_RUN_DIR}" \
  "${EXP460_RUN_DIR}" \
  "${EXP477_RUN_DIR}"; do
  STATUS="$(run_status "${RUN_DIR}")"
  if [[ "${STATUS}" != 'complete' ]]; then
    printf '%s required predecessor %s has status=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${RUN_DIR}" "${STATUS}" >&2
    exit 23
  fi
done

ARTIFACT_MANIFEST="${EXP458_RUN_DIR}/outputs/bearing_artifact_manifest.json"
ARTIFACT_VALIDATION="${EXP459_RUN_DIR}/outputs/validation.json"
EMPIRICAL_MANUSCRIPT="${EXP460_RUN_DIR}/outputs/BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md"
RENDER_REPORT="${EXP460_RUN_DIR}/outputs/render_report.json"
MANUSCRIPT_VALIDATION="${EXP461_RUN_DIR}/outputs/validation.json"
RAW_TOPOLOGY_MANIFEST='artifacts/research/runs/EXP-476-PADERBORN-RAW-TOPOLOGY-MANIFEST__20260819T084548.389414Z__outcome-blind-exact-raw-prediction-key-manifest/outputs/expected_raw_topology_manifest.json'
RAW_TOPOLOGY_VALIDATION="${EXP477_RUN_DIR}/outputs/validation.json"
for REQUIRED_PATH in \
  "${ARTIFACT_MANIFEST}" \
  "${ARTIFACT_VALIDATION}" \
  "${EMPIRICAL_MANUSCRIPT}" \
  "${RENDER_REPORT}" \
  "${MANUSCRIPT_VALIDATION}" \
  "${RAW_TOPOLOGY_MANIFEST}" \
  "${RAW_TOPOLOGY_VALIDATION}"; do
  if [[ ! -f "${REQUIRED_PATH}" ]]; then
    printf '%s required release input is absent: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REQUIRED_PATH}" >&2
    exit 24
  fi
done

ARTIFACT_MANIFEST_SHA256="$(sha256sum "${ARTIFACT_MANIFEST}" | awk '{print $1}')"
ARTIFACT_VALIDATION_SHA256="$(sha256sum "${ARTIFACT_VALIDATION}" | awk '{print $1}')"
EMPIRICAL_MANUSCRIPT_SHA256="$(sha256sum "${EMPIRICAL_MANUSCRIPT}" | awk '{print $1}')"
RENDER_REPORT_SHA256="$(sha256sum "${RENDER_REPORT}" | awk '{print $1}')"
ARTIFACT_VALIDATOR_SOURCE_SHA256="$(
  sha256sum src/smartvalve/experiments/bearing_paper_validation.py | awk '{print $1}'
)"
if [[ "${ARTIFACT_VALIDATOR_SOURCE_SHA256}" != \
      'a2a9c26ffbcd8ed7f7964581b5cd35740e910c4be5d8c80babbc0300f4bcdcd9' ]]; then
  printf '%s artifact-validator source changed before release construction\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 35
fi

mapfile -t ARTIFACT_VALIDATION_FIELDS < <(
  .venv/bin/python - "${ARTIFACT_VALIDATION}" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value.get("status", ""))
print(str(value.get("refit_performed", "")).lower())
print(value.get("manifest_sha256", ""))
print(value.get("input_count", ""))
print(value.get("output_count", ""))
print(value.get("svg_count", ""))
print(value.get("submission_pdf_count", ""))
print(str(value.get("raw_dataset_files_in_manifest", "")).lower())
print(value.get("validator_version", ""))
print(str(float(value.get("raw_median_summary_csv_difference", 1.0)) <= 1e-12).lower())
PY
)
if [[ "${ARTIFACT_VALIDATION_FIELDS[0]}" != \
      'passed_independent_bearing_paper_artifact_validation' \
   || "${ARTIFACT_VALIDATION_FIELDS[1]}" != 'false' \
   || "${ARTIFACT_VALIDATION_FIELDS[2]}" != "${ARTIFACT_MANIFEST_SHA256}" \
   || "${ARTIFACT_VALIDATION_FIELDS[3]}" != '28' \
   || "${ARTIFACT_VALIDATION_FIELDS[4]}" != '42' \
   || "${ARTIFACT_VALIDATION_FIELDS[5]}" != '5' \
   || "${ARTIFACT_VALIDATION_FIELDS[6]}" != '5' \
   || "${ARTIFACT_VALIDATION_FIELDS[7]}" != 'false' \
   || "${ARTIFACT_VALIDATION_FIELDS[8]}" != \
      'smartvalve-bearing-paper-validator-0.4.1' \
   || "${ARTIFACT_VALIDATION_FIELDS[9]}" != 'true' ]]; then
  printf '%s EXP-459R1 validation fields do not authorize release construction\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 25
fi

mapfile -t MANUSCRIPT_VALIDATION_FIELDS < <(
  .venv/bin/python - "${MANUSCRIPT_VALIDATION}" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value.get("status", ""))
print(str(value.get("refit_performed", "")).lower())
print(str(value.get("submission_ready", "")).lower())
print(value.get("manuscript_sha256", ""))
print(value.get("render_report_sha256", ""))
print(value.get("artifact_manifest_sha256", ""))
PY
)
if [[ "${MANUSCRIPT_VALIDATION_FIELDS[0]}" != \
      'passed_independent_empirical_manuscript_validation' \
   || "${MANUSCRIPT_VALIDATION_FIELDS[1]}" != 'false' \
   || "${MANUSCRIPT_VALIDATION_FIELDS[2]}" != 'false' \
   || "${MANUSCRIPT_VALIDATION_FIELDS[3]}" != "${EMPIRICAL_MANUSCRIPT_SHA256}" \
   || "${MANUSCRIPT_VALIDATION_FIELDS[4]}" != "${RENDER_REPORT_SHA256}" \
   || "${MANUSCRIPT_VALIDATION_FIELDS[5]}" != "${ARTIFACT_MANIFEST_SHA256}" ]]; then
  printf '%s EXP-461 validation fields do not authorize release construction\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 26
fi

mapfile -t RAW_TOPOLOGY_FIELDS < <(
  .venv/bin/python - "${RAW_TOPOLOGY_MANIFEST}" "${RAW_TOPOLOGY_VALIDATION}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
value = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
print(value.get("status", ""))
print(str(value.get("refit_performed", "")).lower())
print(str(value.get("aggregate_metrics_recomputed", "")).lower())
print(str(value.get("gate_outcome_read", "")).lower())
print(value.get("input_sha256", {}).get("expected_manifest", ""))
print(hashlib.sha256(manifest_path.read_bytes()).hexdigest())
PY
)
if [[ "${RAW_TOPOLOGY_FIELDS[0]}" != \
      'passed_independent_raw_prediction_topology_validation' \
   || "${RAW_TOPOLOGY_FIELDS[1]}" != 'false' \
   || "${RAW_TOPOLOGY_FIELDS[2]}" != 'false' \
   || "${RAW_TOPOLOGY_FIELDS[3]}" != 'false' \
   || "${RAW_TOPOLOGY_FIELDS[4]}" != "${RAW_TOPOLOGY_FIELDS[5]}" \
   || "${RAW_TOPOLOGY_FIELDS[5]}" != \
      '440b6e9f3a5c156a3b022a7ea8a5667de33c8bc954c3223f73df5be53f622607' ]]; then
  printf '%s EXP-477 exact-topology fields do not authorize release construction\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 34
fi

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-461Q-FINAL-LOCAL-QUALITY \
  --name full-lint-test-coverage-security-and-lock-audit \
  --description "Run the final local Ruff, full pytest, coverage, medium/high Bandit, runtime/CPU-CI/GPU-research lock audit, and diff-check gates after the empirical manuscript validates; do not claim a clean checkout, independent reproduction, human review, or submission readiness." \
  -- \
  .venv/bin/python scripts/run_final_quality_gate.py \
  --project-root . \
  --output-directory '{run_dir}/outputs' \
  --expected-test-count 427

EXP461Q_RUN_DIR="$(unique_run 'EXP-461Q-FINAL-LOCAL-QUALITY__*' 'EXP-461Q')"
if [[ "$(run_status "${EXP461Q_RUN_DIR}")" != 'complete' ]]; then
  printf '%s EXP-461Q final local quality gate did not complete\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 27
fi
FINAL_QUALITY_SUMMARY="${EXP461Q_RUN_DIR}/outputs/final_quality_gate_summary.json"
if [[ ! -f "${FINAL_QUALITY_SUMMARY}" ]]; then
  printf '%s EXP-461Q completed without its quality summary\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 28
fi
FINAL_QUALITY_SUMMARY_SHA256="$(sha256sum "${FINAL_QUALITY_SUMMARY}" | awk '{print $1}')"

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-461V-FINAL-LOCAL-QUALITY-VALIDATION \
  --name independent-command-log-test-and-coverage-validation \
  --description "Independently verify the final local quality command topology, all log hashes, JUnit counts, coverage JSON, evidence-scope limits, and zero exit codes without rerunning those checks." \
  -- \
  .venv/bin/python scripts/validate_final_quality_gate.py \
  --summary "${FINAL_QUALITY_SUMMARY}" \
  --summary-sha256 "${FINAL_QUALITY_SUMMARY_SHA256}" \
  --output '{run_dir}/outputs/validation.json'

EXP461V_RUN_DIR="$(unique_run 'EXP-461V-FINAL-LOCAL-QUALITY-VALIDATION__*' 'EXP-461V')"
if [[ "$(run_status "${EXP461V_RUN_DIR}")" != 'complete' ]]; then
  printf '%s EXP-461V final local quality validation did not complete\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 29
fi
FINAL_QUALITY_VALIDATION="${EXP461V_RUN_DIR}/outputs/validation.json"
if [[ ! -f "${FINAL_QUALITY_VALIDATION}" ]]; then
  printf '%s EXP-461V completed without its validation JSON\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 30
fi

mapfile -t QUALITY_VALIDATION_FIELDS < <(
  .venv/bin/python - "${FINAL_QUALITY_VALIDATION}" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value.get("status", ""))
print(value.get("quality_summary_sha256", ""))
print(value.get("verified_check_count", ""))
print(value.get("verified_test_count", ""))
print(value.get("verified_skipped_count", ""))
print(str(value.get("empirical_model_refit_performed", "")).lower())
print(str(value.get("clean_checkout_claimed", "")).lower())
print(str(value.get("independent_reproduction_claimed", "")).lower())
print(str(value.get("human_review_claimed", "")).lower())
print(str(value.get("submission_ready", "")).lower())
PY
)
if [[ "${QUALITY_VALIDATION_FIELDS[0]}" != \
      'passed_independent_final_local_quality_validation' \
   || "${QUALITY_VALIDATION_FIELDS[1]}" != "${FINAL_QUALITY_SUMMARY_SHA256}" \
   || "${QUALITY_VALIDATION_FIELDS[2]}" != '8' \
   || "${QUALITY_VALIDATION_FIELDS[4]}" != '0' \
   || "${QUALITY_VALIDATION_FIELDS[5]}" != 'false' \
   || "${QUALITY_VALIDATION_FIELDS[6]}" != 'false' \
   || "${QUALITY_VALIDATION_FIELDS[7]}" != 'false' \
   || "${QUALITY_VALIDATION_FIELDS[8]}" != 'false' \
   || "${QUALITY_VALIDATION_FIELDS[9]}" != 'false' \
   || "${QUALITY_VALIDATION_FIELDS[3]}" != '427' ]]; then
  printf '%s EXP-461V validation fields do not authorize release construction\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 31
fi

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-462-BEARING-EVIDENCE-RELEASE \
  --name deterministic-validated-technical-candidate-archive \
  --description "Build a deterministic raw-data-free technical evidence archive containing the validated paper artifacts, empirical manuscript, final local quality logs, all independent validations, audit trail, source, tests, and dependency locks; clean-reproduction and human submission holds remain active." \
  -- \
  .venv/bin/python scripts/build_bearing_release.py \
  --artifact-manifest "${ARTIFACT_MANIFEST}" \
  --artifact-validation "${ARTIFACT_VALIDATION}" \
  --empirical-manuscript "${EMPIRICAL_MANUSCRIPT}" \
  --manuscript-render-report "${RENDER_REPORT}" \
  --manuscript-validation "${MANUSCRIPT_VALIDATION}" \
  --final-quality-summary "${FINAL_QUALITY_SUMMARY}" \
  --final-quality-validation "${FINAL_QUALITY_VALIDATION}" \
  --raw-topology-manifest "${RAW_TOPOLOGY_MANIFEST}" \
  --raw-topology-validation "${RAW_TOPOLOGY_VALIDATION}" \
  --output-directory '{run_dir}/outputs' \
  --project-root .

EXP462_RUN_DIR="$(unique_run 'EXP-462-BEARING-EVIDENCE-RELEASE__*' 'EXP-462')"
if [[ "$(run_status "${EXP462_RUN_DIR}")" != 'complete' ]]; then
  printf '%s EXP-462 release build did not complete\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 32
fi

ARCHIVE="${EXP462_RUN_DIR}/outputs/smartvalve-bearing-evidence.tar.gz"
RELEASE_MANIFEST="${EXP462_RUN_DIR}/outputs/release_manifest.json"
CHECKSUM="${EXP462_RUN_DIR}/outputs/smartvalve-bearing-evidence.tar.gz.sha256"
for REQUIRED_PATH in "${ARCHIVE}" "${RELEASE_MANIFEST}" "${CHECKSUM}"; do
  if [[ ! -f "${REQUIRED_PATH}" ]]; then
    printf '%s EXP-462 output is absent: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REQUIRED_PATH}" >&2
    exit 33
  fi
done
ARCHIVE_SHA256="$(sha256sum "${ARCHIVE}" | awk '{print $1}')"
RELEASE_MANIFEST_SHA256="$(sha256sum "${RELEASE_MANIFEST}" | awk '{print $1}')"

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-463-BEARING-EVIDENCE-RELEASE-VALIDATION \
  --name independent-archive-member-hash-and-metadata-validation \
  --description "Independently reopen the candidate technical archive and verify its external/internal manifests, every member digest, normalized metadata, prohibited-data exclusions, and artifact/manuscript/final-quality validation-chain flags." \
  -- \
  .venv/bin/python scripts/validate_bearing_release.py \
  --archive "${ARCHIVE}" \
  --manifest "${RELEASE_MANIFEST}" \
  --checksum "${CHECKSUM}" \
  --archive-sha256 "${ARCHIVE_SHA256}" \
  --manifest-sha256 "${RELEASE_MANIFEST_SHA256}" \
  --output '{run_dir}/outputs/validation.json'

printf '%s EXP-462/463 technical release handoff completed; artifact validation SHA-256=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${ARTIFACT_VALIDATION_SHA256}"
