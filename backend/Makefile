VENV     := .venv
PYTHON   := $(VENV)/bin/python
PIP      := $(VENV)/bin/pip
UVICORN  := $(VENV)/bin/uvicorn
PYTEST   := $(VENV)/bin/pytest

.PHONY: dev test run clean

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

clean:
	rm -rf $(VENV) __pycache__ app/__pycache__ .pytest_cache
