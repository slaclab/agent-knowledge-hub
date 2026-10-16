DEV_KUBECONFIG  ?= $(HOME)/.kube/config.sage-dev
PROD_KUBECONFIG ?= $(HOME)/.kube/config.sage

DEV_OVERLAY  := /sdf/home/y/ytl/k8s/ai-playground-deploy/kubernetes/overlays/dev/
PROD_OVERLAY := /sdf/home/y/ytl/k8s/ai-playground-deploy/kubernetes/overlays/prod/
TAG := $(shell t=$$(git describe --tags --exact-match 2>/dev/null); [ -n "$$t" ] && echo "$${t\#v}" || grep '^version' backend/pyproject.toml | sed 's/version = "\(.*\)"/\1/')

.PHONY: all backend frontend dev-deploy prod-deploy pin-digests

all: backend frontend dev-deploy

containers: backend frontend

backend:
	$(MAKE) -C backend lock-check audit
	$(MAKE) -C backend docker-push TAG=$(TAG)

frontend:
	$(MAKE) -C frontend docker-push TAG=$(TAG)

dev-deploy:
	KUBECONFIG=$(DEV_KUBECONFIG) $(MAKE) -C $(DEV_OVERLAY) apply
	KUBECONFIG=$(DEV_KUBECONFIG) kubectl -n dev rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend

prod-deploy:
	KUBECONFIG=$(PROD_KUBECONFIG) $(MAKE) -C $(PROD_OVERLAY) apply
	KUBECONFIG=$(PROD_KUBECONFIG) kubectl -n prod rollout restart deployment agent-knowledge-hub-backend agent-knowledge-hub-frontend

# Pin prod, and this repo's stage and prod copies, to the registry digests of $(TAG) (#034).
# Run after `make containers` has pushed $(TAG); dev keeps :latest.
PINNED_MANIFESTS := $(PROD_OVERLAY)agent-knowledge-hub/backend-deployment.yaml \
	$(PROD_OVERLAY)agent-knowledge-hub/frontend-deployment.yaml \
	kubernetes/overlays/prod/backend-deployment.yaml kubernetes/overlays/prod/frontend-deployment.yaml \
	kubernetes/overlays/stage/backend-deployment.yaml kubernetes/overlays/stage/frontend-deployment.yaml

pin-digests:
	python3 scripts/pin_image_digests.py $(TAG) $(PINNED_MANIFESTS)
