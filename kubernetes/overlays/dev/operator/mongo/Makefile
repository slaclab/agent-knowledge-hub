MONGO_OPERATOR_VERSION ?= 1.22.0
CONTEXT               = agent-knowledge-hub-dev
KUBECONFIG           ?= $(HOME)/.kube/contexts/s3df/dev

.PHONY: apply diff dump update-operator

apply:
	kubectl apply --server-side --force-conflicts -k .

diff:
	kubectl diff -k .

dump:
	kubectl kustomize . | yh

update-operator:
	curl -sf "https://raw.githubusercontent.com/percona/percona-server-mongodb-operator/v$(MONGO_OPERATOR_VERSION)/deploy/crd.yaml" \
	  -o mongo-operator-crds.yaml
	curl -sf "https://raw.githubusercontent.com/percona/percona-server-mongodb-operator/v$(MONGO_OPERATOR_VERSION)/deploy/rbac.yaml" \
	  -o mongo-operator-rbac.yaml
	curl -sf "https://raw.githubusercontent.com/percona/percona-server-mongodb-operator/v$(MONGO_OPERATOR_VERSION)/deploy/operator.yaml" \
	  -o mongo-operator.yaml
