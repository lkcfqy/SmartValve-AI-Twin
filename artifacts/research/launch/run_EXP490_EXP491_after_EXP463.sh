#!/usr/bin/env bash
set -euo pipefail

cd /home/fqy/lkcproject/SmartValve-AI-Twin

exec >> artifacts/research/launch/EXP-490-491-watcher.log
exec 2>> artifacts/research/launch/EXP-490-491-watcher.err.log

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
  mapfile -t EXP463_RUNS < <(
    find artifacts/research/runs -maxdepth 1 -type d \
      -name 'EXP-463-BEARING-EVIDENCE-RELEASE-VALIDATION__*' -print | sort
  )
  if (( ${#EXP463_RUNS[@]} == 0 )); then
    sleep 60
    continue
  fi
  if (( ${#EXP463_RUNS[@]} != 1 )); then
    printf '%s expected one EXP-463 run, observed %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${#EXP463_RUNS[@]}" >&2
    exit 21
  fi
  EXP463_RUN_DIR="${EXP463_RUNS[0]}"
  EXP463_STATUS="$(run_status "${EXP463_RUN_DIR}")"
  if [[ "${EXP463_STATUS}" == 'running' ]]; then
    sleep 60
    continue
  fi
  if [[ "${EXP463_STATUS}" != 'complete' ]]; then
    printf '%s EXP-463 ended with status=%s; RESS PDF handoff stopped\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${EXP463_STATUS}" >&2
    exit 22
  fi
  break
done

EXP458_RUN_DIR="$(unique_run 'EXP-458-BEARING-PAPER-ARTIFACTS__*' 'EXP-458')"
EXP459_RUN_DIR="$(unique_run 'EXP-459R1-BEARING-PAPER-VALIDATION__*' 'EXP-459R1')"
EXP460_RUN_DIR="$(unique_run 'EXP-460-BEARING-EMPIRICAL-MANUSCRIPT__*' 'EXP-460')"
EXP461_RUN_DIR="$(unique_run 'EXP-461-BEARING-EMPIRICAL-MANUSCRIPT-VALIDATION__*' 'EXP-461')"
EXP462_RUN_DIR="$(unique_run 'EXP-462-BEARING-EVIDENCE-RELEASE__*' 'EXP-462')"
for RUN_DIR in \
  "${EXP458_RUN_DIR}" \
  "${EXP459_RUN_DIR}" \
  "${EXP460_RUN_DIR}" \
  "${EXP461_RUN_DIR}" \
  "${EXP462_RUN_DIR}"; do
  STATUS="$(run_status "${RUN_DIR}")"
  if [[ "${STATUS}" != 'complete' ]]; then
    printf '%s required predecessor %s has status=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${RUN_DIR}" "${STATUS}" >&2
    exit 23
  fi
done

ARTIFACT_DIR="${EXP458_RUN_DIR}/outputs"
ARTIFACT_MANIFEST="${ARTIFACT_DIR}/bearing_artifact_manifest.json"
ARTIFACT_VALIDATION="${EXP459_RUN_DIR}/outputs/validation.json"
EMPIRICAL_MANUSCRIPT="${EXP460_RUN_DIR}/outputs/BEARING_MANUSCRIPT_EMPIRICAL_FINAL.md"
MANUSCRIPT_VALIDATION="${EXP461_RUN_DIR}/outputs/validation.json"
RELEASE_MANIFEST="${EXP462_RUN_DIR}/outputs/release_manifest.json"
RELEASE_VALIDATION="${EXP463_RUN_DIR}/outputs/validation.json"
BIBLIOGRAPHY='paper/references.bib'
FIGURE_1="${ARTIFACT_DIR}/bearing_figure_00_access_lattice.pdf"
FIGURE_2="${ARTIFACT_DIR}/bearing_figure_01_protocol_profiles.pdf"
FIGURE_3="${ARTIFACT_DIR}/bearing_figure_02_gap_forest.pdf"
FIGURE_4="${ARTIFACT_DIR}/bearing_figure_03_sensor_gaps.pdf"
FIGURE_5="${ARTIFACT_DIR}/bearing_figure_04_hust_equal_volume.pdf"
for REQUIRED_PATH in \
  "${ARTIFACT_MANIFEST}" \
  "${ARTIFACT_VALIDATION}" \
  "${EMPIRICAL_MANUSCRIPT}" \
  "${MANUSCRIPT_VALIDATION}" \
  "${RELEASE_MANIFEST}" \
  "${RELEASE_VALIDATION}" \
  "${BIBLIOGRAPHY}" \
  "${FIGURE_1}" \
  "${FIGURE_2}" \
  "${FIGURE_3}" \
  "${FIGURE_4}" \
  "${FIGURE_5}"; do
  if [[ ! -f "${REQUIRED_PATH}" ]]; then
    printf '%s required RESS PDF input is absent: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REQUIRED_PATH}" >&2
    exit 24
  fi
done

RELEASE_MANIFEST_SHA256="$(sha256sum "${RELEASE_MANIFEST}" | awk '{print $1}')"
mapfile -t RELEASE_FIELDS < <(
  .venv/bin/python - "${RELEASE_VALIDATION}" <<'PY'
import json
import sys
from pathlib import Path

value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(value.get("status", ""))
print(str(value.get("raw_dataset_files_included", "")).lower())
print(str(value.get("technical_manuscript_submission_ready", "")).lower())
print(str(value.get("human_submission_fields_included", "")).lower())
print(value.get("manifest_sha256", ""))
PY
)
if [[ "${RELEASE_FIELDS[0]}" != 'passed_independent_deterministic_release_validation' \
   || "${RELEASE_FIELDS[1]}" != 'false' \
   || "${RELEASE_FIELDS[2]}" != 'false' \
   || "${RELEASE_FIELDS[3]}" != 'false' \
   || "${RELEASE_FIELDS[4]}" != "${RELEASE_MANIFEST_SHA256}" ]]; then
  printf '%s EXP-463 validation fields do not authorize RESS PDF preflight\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 25
fi

.venv/bin/python - "${RELEASE_MANIFEST}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
records = {
    str(item.get("path", "")): item
    for item in manifest.get("files", [])
    if isinstance(item, dict)
}
required = (
    "src/smartvalve/experiments/ress_pdf.py",
    "src/smartvalve/experiments/ress_pdf_validation.py",
    "scripts/render_ress_pdf.py",
    "scripts/validate_ress_pdf.py",
)
for relative in required:
    record = records.get(relative)
    path = Path(relative).resolve(strict=True)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if (
        record is None
        or record.get("sha256") != digest
        or int(record.get("bytes", -1)) != path.stat().st_size
    ):
        raise SystemExit(f"release-bound live PDF source changed: {relative}")
PY

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-490-RESS-EMPIRICAL-PDF-PREFLIGHT \
  --name postrelease-five-figure-watermarked-working-pdf \
  --description "Render the validated empirical manuscript and five ordered vector figures into a deterministic watermarked RESS working PDF after the independently validated technical release; retain all human submission holds." \
  -- \
  .venv/bin/python scripts/render_ress_pdf.py \
  --manuscript "${EMPIRICAL_MANUSCRIPT}" \
  --bibliography "${BIBLIOGRAPHY}" \
  --figure-pdf "${FIGURE_1}" \
  --figure-pdf "${FIGURE_2}" \
  --figure-pdf "${FIGURE_3}" \
  --figure-pdf "${FIGURE_4}" \
  --figure-pdf "${FIGURE_5}" \
  --working-preflight \
  --output '{run_dir}/outputs/RESS_EMPIRICAL_WORKING_PREFLIGHT.pdf' \
  --report '{run_dir}/outputs/RESS_EMPIRICAL_WORKING_PREFLIGHT.report.json'

EXP490_RUN_DIR="$(unique_run 'EXP-490-RESS-EMPIRICAL-PDF-PREFLIGHT__*' 'EXP-490')"
if [[ "$(run_status "${EXP490_RUN_DIR}")" != 'complete' ]]; then
  printf '%s EXP-490 RESS empirical PDF preflight did not complete\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >&2
  exit 26
fi
EMPIRICAL_PDF="${EXP490_RUN_DIR}/outputs/RESS_EMPIRICAL_WORKING_PREFLIGHT.pdf"
PDF_REPORT="${EXP490_RUN_DIR}/outputs/RESS_EMPIRICAL_WORKING_PREFLIGHT.report.json"
for REQUIRED_PATH in "${EMPIRICAL_PDF}" "${PDF_REPORT}"; do
  if [[ ! -f "${REQUIRED_PATH}" ]]; then
    printf '%s EXP-490 output is absent: %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${REQUIRED_PATH}" >&2
    exit 27
  fi
done

PDF_SHA256="$(sha256sum "${EMPIRICAL_PDF}" | awk '{print $1}')"
PDF_REPORT_SHA256="$(sha256sum "${PDF_REPORT}" | awk '{print $1}')"
MANUSCRIPT_SHA256="$(sha256sum "${EMPIRICAL_MANUSCRIPT}" | awk '{print $1}')"
BIBLIOGRAPHY_SHA256="$(sha256sum "${BIBLIOGRAPHY}" | awk '{print $1}')"
ARTIFACT_MANIFEST_SHA256="$(sha256sum "${ARTIFACT_MANIFEST}" | awk '{print $1}')"
ARTIFACT_VALIDATION_SHA256="$(sha256sum "${ARTIFACT_VALIDATION}" | awk '{print $1}')"
MANUSCRIPT_VALIDATION_SHA256="$(sha256sum "${MANUSCRIPT_VALIDATION}" | awk '{print $1}')"
RELEASE_VALIDATION_SHA256="$(sha256sum "${RELEASE_VALIDATION}" | awk '{print $1}')"

.venv/bin/python -m smartvalve.experiments.recorded_run \
  --experiment-id EXP-491-RESS-EMPIRICAL-PDF-VALIDATION \
  --name independent-ordered-figure-and-upstream-gate-validation \
  --description "Independently validate the watermarked empirical RESS PDF, ordered figure titles and hashes, manuscript and bibliography identities, upstream validators, and release gate without rendering or fitting." \
  -- \
  .venv/bin/python scripts/validate_ress_pdf.py \
  --pdf "${EMPIRICAL_PDF}" \
  --pdf-sha256 "${PDF_SHA256}" \
  --report "${PDF_REPORT}" \
  --report-sha256 "${PDF_REPORT_SHA256}" \
  --manuscript "${EMPIRICAL_MANUSCRIPT}" \
  --manuscript-sha256 "${MANUSCRIPT_SHA256}" \
  --bibliography "${BIBLIOGRAPHY}" \
  --bibliography-sha256 "${BIBLIOGRAPHY_SHA256}" \
  --artifact-manifest "${ARTIFACT_MANIFEST}" \
  --artifact-manifest-sha256 "${ARTIFACT_MANIFEST_SHA256}" \
  --artifact-validation "${ARTIFACT_VALIDATION}" \
  --artifact-validation-sha256 "${ARTIFACT_VALIDATION_SHA256}" \
  --manuscript-validation "${MANUSCRIPT_VALIDATION}" \
  --manuscript-validation-sha256 "${MANUSCRIPT_VALIDATION_SHA256}" \
  --release-manifest "${RELEASE_MANIFEST}" \
  --release-manifest-sha256 "${RELEASE_MANIFEST_SHA256}" \
  --release-validation "${RELEASE_VALIDATION}" \
  --release-validation-sha256 "${RELEASE_VALIDATION_SHA256}" \
  --output '{run_dir}/outputs/validation.json'

printf '%s EXP-490/491 empirical RESS PDF preflight and validation completed\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
