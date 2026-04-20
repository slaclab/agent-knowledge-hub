CONTEXT      = agent-knowledge-hub-dev
NAMESPACE    = dev
KUBECONFIG  ?= $(HOME)/.kube/contexts/s3df/dev
REGISTRY     ?= docker.io/slaclab
TAG          ?= dev
CONTAINER_RT ?= sudo podman

.PHONY: apply diff destroy rollout-restart dump docker-build docker-push

apply: ensure-context
	kubectl apply -k .

diff: ensure-context
	kubectl diff -k .

dump:
	kubectl kustomize . | yh

rollout-restart: ensure-context
	kubectl rollout restart deployment/agent-knowledge-hub-backend -n $(NAMESPACE)
	kubectl rollout restart deployment/agent-knowledge-hub-frontend -n $(NAMESPACE)

destroy: ensure-context
	kubectl delete -k .

docker-build:
	$(MAKE) -C ../../../backend  docker-build REGISTRY=$(REGISTRY) TAG=$(TAG) CONTAINER_RT="$(CONTAINER_RT)"
	$(MAKE) -C ../../../frontend docker-build REGISTRY=$(REGISTRY) TAG=$(TAG) CONTAINER_RT="$(CONTAINER_RT)"

docker-push:
	$(MAKE) -C ../../../backend  docker-push REGISTRY=$(REGISTRY) TAG=$(TAG) CONTAINER_RT="$(CONTAINER_RT)"
	$(MAKE) -C ../../../frontend docker-push REGISTRY=$(REGISTRY) TAG=$(TAG) CONTAINER_RT="$(CONTAINER_RT)"

ensure-context:
	@kubectl config current-context | grep -q "$(CONTEXT)" || \
	  (echo "Wrong context. Expected: $(CONTEXT)"; exit 1)
