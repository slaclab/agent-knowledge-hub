NODE_MODULES := node_modules
NEXT         := $(NODE_MODULES)/.bin/next

.PHONY: dev build start lint clean

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

clean:
	rm -rf $(NODE_MODULES) .next
