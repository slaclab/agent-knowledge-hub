PYTHON3  ?= python3
VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
UVICORN  := $(VENV)/bin/uvicorn
PYTEST   := $(VENV)/bin/pytest
PIP_COMPILE := $(abspath $(VENV)/bin/pip-compile)
PIP_AUDIT   := $(VENV)/bin/pip-audit

# Lockfiles pin every package with its hashes (#036). Compile them with Python 3.12, the image's
# Python, because pip-compile resolves environment markers for the interpreter it runs on.
LOCK_FLAGS := --quiet --generate-hashes --allow-unsafe --strip-extras
export CUSTOM_COMPILE_COMMAND := make -C backend lock

REGISTRY     ?= docker.io/slaclab
IMAGE        ?= $(REGISTRY)/agent-knowledge-hub-backend
TAG          ?= dev
CONTAINER_RT ?= podman

.PHONY: dev test run clean docker-build docker-push lock lock-check audit check-python

dev: $(VENV)/bin/activate

$(VENV)/bin/activate: requirements-dev.lock
	$(PYTHON3) -m venv $(VENV)
	$(PIP) install --require-hashes -r requirements-dev.lock
	@cp -n .env.example .env 2>/dev/null && echo "Created .env from .env.example — edit DEV_USER before running" || true
	@touch $(VENV)/bin/activate

test: $(VENV)/bin/activate
	$(PYTEST) tests/ -v

run: $(VENV)/bin/activate
	$(UVICORN) app.main:app --reload

check-python: $(VENV)/bin/activate
	@$(PYTHON) -c 'import sys; v = sys.version_info[:2]; sys.exit(0 if v == (3, 12) else "Compile the lockfiles with Python 3.12, the image Python; $(VENV) has %d.%d. Run: make clean; make PYTHON3=python3.12 dev" % v)'

# Regenerate both lockfiles after editing requirements.txt or requirements-dev.txt.
lock: check-python
	$(PIP_COMPILE) $(LOCK_FLAGS) --output-file=requirements.lock requirements.txt
	$(PIP_COMPILE) $(LOCK_FLAGS) --output-file=requirements-dev.lock requirements-dev.txt

# Fail if either lockfile is not what `make lock` would write. The lockfiles are copied first, so
# pip-compile keeps their pins and only an edited requirements file changes the result.
lock-check: check-python
	@tmp=$$(mktemp -d) && trap 'rm -rf "$$tmp"' EXIT && \
	cp requirements.txt requirements-dev.txt requirements.lock requirements-dev.lock "$$tmp"/ && \
	(cd "$$tmp" && $(PIP_COMPILE) $(LOCK_FLAGS) --output-file=requirements.lock requirements.txt && \
	 $(PIP_COMPILE) $(LOCK_FLAGS) --output-file=requirements-dev.lock requirements-dev.txt) && \
	diff -u requirements.lock "$$tmp/requirements.lock" && \
	diff -u requirements-dev.lock "$$tmp/requirements-dev.lock" || \
	{ echo "The lockfiles are stale. Run: make -C backend lock"; exit 1; }

# Fail on any known vulnerability in the packages the image installs.
audit: $(VENV)/bin/activate
	$(PIP_AUDIT) --require-hashes --disable-pip -r requirements.lock

docker-build:
	$(CONTAINER_RT) build -t $(IMAGE):$(TAG) .

docker-push: docker-build
	$(CONTAINER_RT) push $(IMAGE):$(TAG)
	$(CONTAINER_RT) tag $(IMAGE):$(TAG) $(IMAGE):latest
	$(CONTAINER_RT) push $(IMAGE):latest

clean:
	rm -rf $(VENV) __pycache__ app/__pycache__ .pytest_cache
