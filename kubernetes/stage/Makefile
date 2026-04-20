CONTEXT      = agent-knowledge-hub-stage
NAMESPACE    = agent-knowledge-hub-stage
KUBECONFIG  ?= $(HOME)/.kube/contexts/s3df/stage
SECRET_PATH ?= secret/tid/agent-knowledge-hub-stage

.PHONY: apply diff destroy rollout-restart dump secrets clean-secrets

apply: ensure-context secrets
	kubectl apply -k .
	$(MAKE) clean-secrets

diff: ensure-context
	kubectl diff -k .

dump:
	kubectl kustomize . | yh

rollout-restart: ensure-context
	kubectl rollout restart deployment/agent-knowledge-hub-backend -n $(NAMESPACE)

destroy: ensure-context
	kubectl delete -k .

secrets:
	mkdir -p etc/.secrets
	set -e; for i in GITHUB_TOKEN ADMIN_USERS MONGO_ROOT_USERNAME MONGO_ROOT_PASSWORD; do \
	  vault kv get --field=$$i $(SECRET_PATH) > etc/.secrets/$$i; \
	done
	kubectl create secret generic agent-knowledge-hub-secrets \
	  --from-file=etc/.secrets/ \
	  -n $(NAMESPACE) \
	  --dry-run=client -o yaml | kubectl apply -f -

clean-secrets:
	rm -rf etc/.secrets/

ensure-context:
	@kubectl config current-context | grep -q "$(CONTEXT)" || \
	  (echo "Wrong context. Expected: $(CONTEXT)"; exit 1)
