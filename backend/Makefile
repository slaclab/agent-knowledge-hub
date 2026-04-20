VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
UVICORN  := $(VENV)/bin/uvicorn
PYTEST   := $(VENV)/bin/pytest

REGISTRY     ?=
IMAGE        ?= $(if $(REGISTRY),$(REGISTRY)/agent-knowledge-hub-backend,agent-knowledge-hub-backend)
TAG          ?= dev
CONTAINER_RT ?= sudo podman

.PHONY: dev test run clean docker-build docker-push

dev: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements-dev.txt requirements.txt
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements-dev.txt
	@cp -n .env.example .env 2>/dev/null && echo "Created .env from .env.example — edit DEV_USER before running" || true
	@touch $(VENV)/bin/activate

test: $(VENV)/bin/activate
	$(PYTEST) tests/ -v

run: $(VENV)/bin/activate
	$(UVICORN) app.main:app --reload

docker-build:
	$(CONTAINER_RT) build -t $(IMAGE):$(TAG) .

docker-push: docker-build
	$(CONTAINER_RT) push $(IMAGE):$(TAG)

clean:
	rm -rf $(VENV) __pycache__ app/__pycache__ .pytest_cache
