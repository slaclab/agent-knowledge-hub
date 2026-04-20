CONTEXT      = agent-knowledge-hub-dev
NAMESPACE    = dev
KUBECONFIG  ?= $(HOME)/.kube/contexts/s3df/dev
SECRET_PATH  ?= secret/tid/agent-knowledge-hub-dev/mongo

.PHONY: apply diff dump secrets clean-secrets

apply: ensure-context secrets
	kubectl apply -k .
	$(MAKE) clean-secrets

diff: ensure-context
	kubectl diff -k .

dump:
	kubectl kustomize . | yh

secrets:
	mkdir -p etc/.secrets
	set -e; for i in MONGODB_BACKUP_USER MONGODB_BACKUP_PASSWORD \
	    MONGODB_CLUSTER_ADMIN_USER MONGODB_CLUSTER_ADMIN_PASSWORD \
	    MONGODB_CLUSTER_MONITOR_USER MONGODB_CLUSTER_MONITOR_PASSWORD \
	    MONGODB_USER_ADMIN_USER MONGODB_USER_ADMIN_PASSWORD; do \
	  vault kv get --field=$$i $(SECRET_PATH) > etc/.secrets/$$i; \
	done

clean-secrets:
	rm -rf etc/.secrets/

ensure-context:
	@kubectl config current-context | grep -q "$(CONTEXT)" || \
	  (echo "Wrong context. Expected: $(CONTEXT)"; exit 1)
