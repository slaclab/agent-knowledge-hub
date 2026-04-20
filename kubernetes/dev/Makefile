CONTEXT    = agent-knowledge-hub-dev
NAMESPACE  = agent-knowledge-hub-dev
KUBECONFIG ?= $(HOME)/.kube/contexts/s3df/dev

.PHONY: apply diff destroy rollout-restart

apply: ensure-context
	kubectl apply -k .

diff: ensure-context
	kubectl diff -k .

rollout-restart: ensure-context
	kubectl rollout restart deployment/agent-knowledge-hub-backend -n $(NAMESPACE)

destroy: ensure-context
	kubectl delete -k .

ensure-context:
	@kubectl config current-context | grep -q "$(CONTEXT)" || \
	  (echo "Wrong context. Expected: $(CONTEXT)"; exit 1)
