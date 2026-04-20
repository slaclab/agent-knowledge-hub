CONTEXT           = agent-knowledge-hub-dev
NAMESPACE         = dev
KUBECONFIG       ?= $(HOME)/.kube/contexts/s3df/dev
REGISTRY         ?= docker.io/slaclab
TAG              ?= dev
CONTAINER_RT     ?= sudo podman
MONGO_SECRET_PATH ?= secret/tid/agent-knowledge-hub-dev/mongo

.PHONY: apply diff destroy rollout-restart dump operator-apply mongodb-apply secrets clean-secrets docker-build docker-push

operator-apply:
	KUBECONFIG=$(KUBECONFIG) kubectl apply --server-side --force-conflicts -k operator/mongo/

mongodb-apply: ensure-context
	$(MAKE) -C mongodb/ apply KUBECONFIG=$(KUBECONFIG)

secrets:
	mkdir -p etc/.secrets
	@MONGO_USER=$$(vault kv get --field=MONGODB_APP_USER $(MONGO_SECRET_PATH)) && \
	 MONGO_PASS=$$(vault kv get --field=MONGODB_APP_PASSWORD $(MONGO_SECRET_PATH)) && \
	 echo -n "mongodb://$${MONGO_USER}:$${MONGO_PASS}@mongodb-rs0.$(NAMESPACE).svc.cluster.local/agent-skills?replicaSet=rs0&authSource=agent-skills" \
	   > etc/.secrets/MONGO_URI

clean-secrets:
	rm -rf etc/.secrets/

apply: ensure-context secrets
	kubectl apply -k .
	$(MAKE) clean-secrets

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
