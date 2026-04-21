NODE_MODULES := node_modules
NEXT         := $(NODE_MODULES)/.bin/next

REGISTRY     ?= docker.io/slaclab
IMAGE        ?= $(REGISTRY)/agent-knowledge-hub-frontend
TAG          ?= $(shell git describe --tags --exact-match 2>/dev/null | sed 's/^v//' || echo dev)
CONTAINER_RT ?= sudo podman

.PHONY: dev build start lint clean docker-build docker-push

dev: $(NODE_MODULES)
	$(NEXT) dev

build: $(NODE_MODULES)
	$(NEXT) build

start: build
	$(NEXT) start

$(NODE_MODULES): package.json
	npm install
	@cp -n .env.example .env.local 2>/dev/null && echo "Created .env.local from example" || true
	@touch $(NODE_MODULES)

lint: $(NODE_MODULES)
	$(NEXT) lint

docker-build:
	$(CONTAINER_RT) build -t $(IMAGE):$(TAG) .

docker-push: docker-build
	$(CONTAINER_RT) push $(IMAGE):$(TAG)

clean:
	rm -rf $(NODE_MODULES) .next
