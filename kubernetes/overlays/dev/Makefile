CONTEXT           = agent-knowledge-hub-dev
NAMESPACE         = dev
KUBECONFIG       ?= $(HOME)/.kube/contexts/s3df/dev
REGISTRY         ?= docker.io/slaclab
TAG              ?= dev
CONTAINER_RT     ?= sudo podman
MONGO_SECRET_PATH ?= secret/tid/agent-knowledge-hub-dev/mongo
APP_SECRET_PATH   ?= secret/tid/agent-knowledge-hub-dev/app

.PHONY: apply diff destroy rollout-restart dump operator-apply secrets clean-secrets create-db-user docker-build docker-push

operator-apply:
	KUBECONFIG=$(KUBECONFIG) kubectl apply --server-side --force-conflicts -k operator/mongo/

secrets:
	mkdir -p etc/.secrets
	@set -e; for i in MONGODB_BACKUP_USER MONGODB_BACKUP_PASSWORD \
	    MONGODB_CLUSTER_ADMIN_USER MONGODB_CLUSTER_ADMIN_PASSWORD \
	    MONGODB_CLUSTER_MONITOR_USER MONGODB_CLUSTER_MONITOR_PASSWORD \
	    MONGODB_USER_ADMIN_USER MONGODB_USER_ADMIN_PASSWORD; do \
	  vault kv get --field=$$i $(MONGO_SECRET_PATH) > etc/.secrets/$$i; \
	done
	@MONGO_USER=$$(vault kv get --field=MONGODB_APP_USER $(MONGO_SECRET_PATH)) && \
	 MONGO_PASS=$$(vault kv get --field=MONGODB_APP_PASSWORD $(MONGO_SECRET_PATH)) && \
	 echo -n "mongodb://$${MONGO_USER}:$${MONGO_PASS}@mongodb-mongos.$(NAMESPACE).svc.cluster.local/agent-skills?authSource=agent-skills" \
	   > etc/.secrets/MONGO_URI
	@set -e; for i in GITHUB_APP_ID GITHUB_APP_PRIVATE_KEY; do \
	  vault kv get --field=$$i $(APP_SECRET_PATH) > etc/.secrets/$$i; \
	done

create-db-user: ensure-context
	@APP_USER=$$(vault kv get --field=MONGODB_APP_USER $(MONGO_SECRET_PATH)) && \
	 APP_PASS=$$(vault kv get --field=MONGODB_APP_PASSWORD $(MONGO_SECRET_PATH)) && \
	 ADMIN_USER=$$(vault kv get --field=MONGODB_USER_ADMIN_USER $(MONGO_SECRET_PATH)) && \
	 ADMIN_PASS=$$(vault kv get --field=MONGODB_USER_ADMIN_PASSWORD $(MONGO_SECRET_PATH)) && \
	 kubectl exec -n $(NAMESPACE) mongodb-mongos-0 -- \
	   mongosh --quiet admin -u "$$ADMIN_USER" -p "$$ADMIN_PASS" --eval " \
	     var db = db.getSiblingDB('agent-skills'); \
	     var u = db.getUser('$$APP_USER'); \
	     if (u) { db.updateUser('$$APP_USER', {pwd: '$$APP_PASS'}); print('updated'); } \
	     else { db.createUser({user: '$$APP_USER', pwd: '$$APP_PASS', roles: [{role: 'readWrite', db: 'agent-skills'}]}); print('created'); } \
	   "

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
