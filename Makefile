.PHONY: install test lint security sbom image-scan demo dashboard cli api data validate benchmark benchmark-smoke benchmark-challenge benchmark-cranfield docker-build docker-up docker-down

SYFT_IMAGE := anchore/syft@sha256:473a60e3a58e29aca3aedb3e99e787bb4ef273917e44d10fcbea4330a07320bb
GRYPE_IMAGE := anchore/grype@sha256:decd87500a90c1e4faa1706f77b0b2cbc1d2f9364e976f1898ce9037de09cc3a

install:
	.venv/bin/python -m pip install -e '.[dev,security]'

test:
	.venv/bin/python -m pytest

lint:
	.venv/bin/ruff check src tests dashboard

security:
	.venv/bin/bandit -q -r src -ll
	.venv/bin/pip-audit -r requirements.lock --disable-pip

sbom:
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock $(SYFT_IMAGE) smartvalve-ai-twin:0.4.0 -o spdx-json > artifacts/sbom.spdx.json

image-scan:
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v "$(CURDIR)/security:/work/security:ro" $(GRYPE_IMAGE) smartvalve-ai-twin:0.4.0 --vex /work/security/openvex.json --fail-on high

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

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
