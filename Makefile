KUBECONFIG ?= $(HOME)/.kube/contexts/sage-dev/dev
DEV_OVERLAY := /sdf/home/y/ytl/k8s/ai-playground-deploy/kubernetes/overlays/dev/
TAG := $(shell t=$$(git describe --tags --exact-match 2>/dev/null); [ -n "$$t" ] && echo "$${t\#v}" || grep '^version' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')

.PHONY: all backend frontend deploy

all: backend frontend deploy

backend:
	$(MAKE) -C backend docker-push TAG=$(TAG)

frontend:
	$(MAKE) -C frontend docker-push TAG=$(TAG)

deploy:
	KUBECONFIG=$(KUBECONFIG) $(MAKE) -C $(DEV_OVERLAY) apply 
	KUBECONFIG=$(KUBECONFIG) kubectl -n dev rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend
