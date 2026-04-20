CONTEXT    = agent-knowledge-hub-stage
NAMESPACE  = agent-knowledge-hub-stage
KUBECONFIG ?= $(HOME)/.kube/contexts/s3df/stage

.PHONY: apply diff destroy rollout-restart secrets clean-secrets

apply: ensure-context secrets
	kubectl apply -k .
	$(MAKE) clean-secrets

diff: ensure-context
	kubectl diff -k .

rollout-restart: ensure-context
	kubectl rollout restart deployment/agent-knowledge-hub-backend -n $(NAMESPACE)

destroy: ensure-context
	kubectl delete -k .

ensure-context:
	@kubectl config current-context | grep -q "$(CONTEXT)" || \
	  (echo "Wrong context. Expected: $(CONTEXT)"; exit 1)

secrets:
	@mkdir -p .secrets
	# vault kv get -field=value secret/tid/agent-skills-stage/github-token > .secrets/GITHUB_TOKEN
	# vault kv get -field=value secret/tid/agent-skills-stage/admin-users > .secrets/ADMIN_USERS
	# vault kv get -field=value secret/tid/agent-skills-stage/mongo-root-password > .secrets/MONGO_ROOT_PASSWORD
	# kubectl create secret generic agent-knowledge-hub-secrets --from-file=.secrets/ -n $(NAMESPACE) --dry-run=client -o yaml | kubectl apply -f -

clean-secrets:
	rm -f .secrets/*
