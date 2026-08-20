.PHONY: install test coverage lint security sbom image-scan demo dashboard cli api data validate benchmark benchmark-smoke benchmark-challenge benchmark-cranfield paper-artifacts backup docker-build docker-up docker-down

IMAGE := smartvalve-ai-twin:0.6.0

SYFT_IMAGE := anchore/syft@sha256:473a60e3a58e29aca3aedb3e99e787bb4ef273917e44d10fcbea4330a07320bb
GRYPE_IMAGE := anchore/grype@sha256:decd87500a90c1e4faa1706f77b0b2cbc1d2f9364e976f1898ce9037de09cc3a

install:
	.venv/bin/python -m pip install -e '.[dev,security,research]'

test:
	.venv/bin/python -m pytest

coverage:
	.venv/bin/python -m pytest --cov=src/smartvalve --cov-report=term-missing --cov-fail-under=75

lint:
	.venv/bin/ruff check .

security:
	.venv/bin/bandit -q -r src scripts research/scripts -ll
	.venv/bin/pip-audit -r requirements.lock -r build-requirements.lock --disable-pip --strict
	.venv/bin/pip-audit -r requirements-ci.lock --disable-pip --strict --vulnerability-service osv
	.venv/bin/pip-audit -r requirements-research.lock --disable-pip --strict

sbom:
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock $(SYFT_IMAGE) $(IMAGE) -o spdx-json > artifacts/sbom.spdx.json

image-scan:
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$(CURDIR)/security:/work/security:ro" $(GRYPE_IMAGE) $(IMAGE) --vex /work/security/openvex.json --fail-on high

demo:
	.venv/bin/python -m smartvalve.launcher

dashboard:
	.venv/bin/streamlit run dashboard/app.py

cli:
	.venv/bin/python -m smartvalve.demo

api:
	.venv/bin/uvicorn smartvalve.service.app:app --host 0.0.0.0 --port 8000

data:
	.venv/bin/python -m smartvalve.data.external sync

validate:
	.venv/bin/python -m smartvalve.validation

benchmark:
	.venv/bin/python -m smartvalve.experiments.benchmark --profile full

benchmark-smoke:
	.venv/bin/python -m smartvalve.experiments.benchmark --profile smoke

benchmark-challenge:
	.venv/bin/python -m smartvalve.experiments.benchmark --profile challenge

benchmark-cranfield:
	.venv/bin/python -m smartvalve.experiments.cranfield_benchmark

paper-artifacts:
	.venv/bin/python -m smartvalve.experiments.paper_artifacts --output-directory paper/generated
	.venv/bin/python scripts/multirig_paper_artifacts.py \
		--base-metrics artifacts/research/runs/EXP-417-PADERBORN-D2-BASE__20260818T150037.112666Z__sealed-one-shot-nine-method-external-evaluation/outputs/metrics.json \
		--base-sha256 167d2e04bede2dfbd5b37eb6c63bbef8b51b6c3c58d8f68624fca3cf64fa1c95 \
		--selective-metrics artifacts/research/runs/EXP-419-PADERBORN-D2-SELECTIVE__20260818T155301.056559Z__sealed-source-oof-selective-evaluation/outputs/metrics.json \
		--selective-sha256 234a9b3f3d2809be7d5f670dfb752248596d0d8c1171cc47434aa96ea92247aa \
		--bootstrap-metrics artifacts/research/runs/EXP-421B-PADERBORN-D2-BOOTSTRAP__20260818T162752.972286Z__reconciled-frozen-bearing-identity-paired-bootst/outputs/metrics.json \
		--bootstrap-sha256 465cfe62da9b60c75484992b6b0d2b13cb97197f5e9b390955086160986b69f8 \
		--family-metrics artifacts/research/runs/EXP-422B-CONFIRMATORY-FAMILY__20260818T163128.647362Z__reconciled-six-test-holm-family/outputs/metrics.json \
		--family-sha256 0143b1e6703a1941f636001b298ce29837386258127068e715fe4ffe73854476 \
		--output-directory paper/generated

backup:
	.venv/bin/python -m smartvalve.storage.backup backup --database data/runtime/smartvalve.db --output-directory data/backups

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
