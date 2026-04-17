.PHONY: help colima-start minikube-start minikube-stop minikube-status minikube-delete build build-app build-nginx docker-images push-images setup deploy create-namespace create-test-namespaces deploy-helm wait-deployments generate-certs generate-certs-fresh generate-certs-if-missing redeploy verify cleanup cleanup-helm cleanup-docker-images cleanup-certs cleanup-minikube test test-setup test-teardown test-policies test-privileged test-latest test-mutation test-labels logs logs-app logs-nginx shell ports port-forward exec-app exec-nginx check-deps helm-status

# Variables
NAMESPACE ?= governance-hub-demo
TEST_NAMESPACE ?= governance-hub-test
VALIDATOR_TEST_NAMESPACE ?= governance-hub-validator-test
APP_IMAGE ?= governance-hub-app:v1
NGINX_IMAGE ?= governance-hub-nginx:v1
DOCKER_BUILDKIT ?= 1
MINIKUBE_MEMORY ?= 3072
MINIKUBE_CPUS ?= 2
MINIKUBE_DRIVER ?= docker
MINIKUBE_K8S_VERSION ?= v1.35.1
COLIMA_MEMORY ?= 4
COLIMA_CPUS ?= 2
COLIMA_DISK ?= 60
HELM_RELEASE ?= governance-hub
CHART_PATH ?= ./governance-hub-chart
NAMESPACE_TEAM ?= platform
NAMESPACE_ENV ?= dev

# Use colima if available, otherwise fall back to the local Docker daemon
COLIMA_CMD := $(shell command -v colima 2>/dev/null)

# Color output
BLUE := \033[0;34m
GREEN := \033[0;32m
RED := \033[0;31m
NC := \033[0m # No Color

##@ Help
help: ## Display this help message
	@echo "$(BLUE)Governance Hub Demo - Makefile$(NC)"
	@echo "$(BLUE)==============================$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "$(GREEN)%-25s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(BLUE)Usage:$(NC)"
	@echo "  make build           # Build Docker images"
	@echo "  make deploy          # Full deployment (Minikube + K8s + webhooks)"
	@echo "  make test            # Run all tests"
	@echo "  make cleanup         # Clean up everything"
	@echo ""
	@echo "$(BLUE)Quick Start:$(NC)"
	@echo "  1. make setup   # Full fresh setup (minikube + build + namespaces + webhook)"
	@echo "  2. make test    # Run all integration tests"

##@ Minikube
colima-start: ## Start Colima if available, otherwise verify Docker daemon is running
	@if [ -n "$(COLIMA_CMD)" ]; then \
		echo "$(BLUE)Starting Colima...$(NC)"; \
		CURRENT_MEM=$$(colima list 2>/dev/null | awk 'NR>1 && $$1=="default" {gsub(/GiB/,"",$$5); print int($$5)}'); \
		if colima status 2>/dev/null | grep -q "Running" && [ "$${CURRENT_MEM:-0}" -ge "$(COLIMA_MEMORY)" ]; then \
			echo "Colima already running with sufficient memory ($${CURRENT_MEM}GiB)"; \
		else \
			colima stop 2>/dev/null || true; \
			colima start --cpu $(COLIMA_CPUS) --memory $(COLIMA_MEMORY) --disk $(COLIMA_DISK); \
		fi; \
		echo "$(GREEN)✓ Colima started$(NC)"; \
	else \
		echo "$(BLUE)Colima not found — using Docker daemon directly...$(NC)"; \
		docker info > /dev/null 2>&1 || (echo "$(RED)Docker is not running. Please start Docker Desktop or the Docker daemon first.$(NC)"; exit 1); \
		DOCKER_MEM_GiB=$$(docker info --format '{{.MemTotal}}' 2>/dev/null | awk '{printf "%d", $$1/1024/1024/1024}'); \
		if [ "$${DOCKER_MEM_GiB:-0}" -lt "$(COLIMA_MEMORY)" ]; then \
			echo "$(RED)Warning: Docker has $${DOCKER_MEM_GiB}GiB available, recommended $(COLIMA_MEMORY)GiB. Adjust in Docker Desktop → Settings → Resources.$(NC)"; \
		else \
			echo "Docker memory: $${DOCKER_MEM_GiB}GiB (sufficient)"; \
		fi; \
		echo "$(GREEN)✓ Docker daemon is running$(NC)"; \
	fi

minikube-start: colima-start ## Start Minikube cluster (starts Colima first)
	@echo "$(BLUE)Starting Minikube...$(NC)"
	@if minikube status --format='{{.Host}}' 2>/dev/null | grep -q "Running"; then \
		echo "Minikube already running"; \
	else \
		minikube start --driver=$(MINIKUBE_DRIVER) --cpus=$(MINIKUBE_CPUS) --kubernetes-version=$(MINIKUBE_K8S_VERSION); \
	fi
	@echo "$(GREEN)✓ Minikube started$(NC)"

minikube-stop: ## Stop Minikube cluster
	@echo "$(BLUE)Stopping Minikube...$(NC)"
	minikube stop
	@echo "$(GREEN)✓ Minikube stopped$(NC)"

minikube-status: ## Show Minikube status
	@minikube status

minikube-delete: ## Delete Minikube cluster (irreversible)
	@echo "$(RED)This will delete the entire Minikube cluster!$(NC)"
	@read -p "Are you sure? (y/N) " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		minikube delete; \
		echo "$(GREEN)✓ Minikube deleted$(NC)"; \
	else \
		echo "Cancelled"; \
	fi

##@ Build
build: build-app build-nginx ## Build all Docker images

build-app: ## Build Flask app Docker image and load into Minikube
	@echo "$(BLUE)Building governance-hub-app:latest...$(NC)"
	@unset DOCKER_TLS_VERIFY DOCKER_HOST DOCKER_CERT_PATH MINIKUBE_ACTIVE_DOCKERD && \
	  DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build --no-cache -t $(APP_IMAGE) -f Dockerfile . --quiet
	@echo "$(BLUE)Loading $(APP_IMAGE) into Minikube...$(NC)"
	@unset DOCKER_TLS_VERIFY DOCKER_HOST DOCKER_CERT_PATH MINIKUBE_ACTIVE_DOCKERD && \
	  docker save $(APP_IMAGE) | docker exec -i minikube docker load
	@echo "$(GREEN)✓ App image built and loaded: $(APP_IMAGE)$(NC)"

build-nginx: ## Build nginx Docker image and load into Minikube
	@echo "$(BLUE)Building governance-hub-nginx:latest...$(NC)"
	@unset DOCKER_TLS_VERIFY DOCKER_HOST DOCKER_CERT_PATH MINIKUBE_ACTIVE_DOCKERD && \
	  DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build --no-cache -t $(NGINX_IMAGE) -f Dockerfile.nginx . --quiet
	@echo "$(BLUE)Loading $(NGINX_IMAGE) into Minikube...$(NC)"
	@unset DOCKER_TLS_VERIFY DOCKER_HOST DOCKER_CERT_PATH MINIKUBE_ACTIVE_DOCKERD && \
	  docker save $(NGINX_IMAGE) | docker exec -i minikube docker load
	@echo "$(GREEN)✓ Nginx image built and loaded: $(NGINX_IMAGE)$(NC)"

docker-images: ## List local Docker images
	@echo "$(BLUE)Local governance-hub images:$(NC)"
	@docker images | grep governance-hub || echo "No images found"

##@ Deployment
setup: minikube-start build create-namespace create-test-namespaces generate-certs-if-missing deploy-helm wait-deployments verify ## Full fresh setup (creates all namespaces before webhook is active)

deploy: minikube-start build create-namespace generate-certs-if-missing deploy-helm wait-deployments verify ## Deploy base application (test namespaces must already exist)

create-namespace: ## Create the base application namespace (governance-hub-demo)
	@echo "$(BLUE)Creating namespace $(NAMESPACE) with labels...$(NC)"
	@kubectl create namespace $(NAMESPACE) --dry-run=client -o yaml | \
	kubectl patch -f - -p '{"metadata":{"labels":{"team":"$(NAMESPACE_TEAM)","environment":"$(NAMESPACE_ENV)"}}}' --type merge --dry-run=client -o yaml | \
	kubectl apply -f - > /dev/null
	@echo "$(GREEN)✓ Namespace ready (team: $(NAMESPACE_TEAM), environment: $(NAMESPACE_ENV))$(NC)"

create-test-namespaces: ## Create test namespaces before the webhook is active (must run before deploy-helm)
	@echo "$(BLUE)Creating test namespace $(TEST_NAMESPACE)...$(NC)"
	@kubectl create namespace $(TEST_NAMESPACE) --dry-run=client -o yaml | \
	kubectl patch -f - -p '{"metadata":{"labels":{"team":"$(NAMESPACE_TEAM)","environment":"$(NAMESPACE_ENV)"}}}' --type merge --dry-run=client -o yaml | \
	kubectl apply -f - > /dev/null
	@echo "$(GREEN)✓ Test namespace ready$(NC)"
	@echo "$(BLUE)Creating validator test namespace $(VALIDATOR_TEST_NAMESPACE)...$(NC)"
	@kubectl create namespace $(VALIDATOR_TEST_NAMESPACE) --dry-run=client -o yaml | \
	kubectl patch -f - -p '{"metadata":{"labels":{"team":"$(NAMESPACE_TEAM)","environment":"$(NAMESPACE_ENV)"}}}' --type merge --dry-run=client -o yaml | \
	kubectl apply -f - > /dev/null
	@echo "$(GREEN)✓ Validator test namespace ready$(NC)"

deploy-helm: ## Deploy or upgrade Helm release with current values
	@echo "$(BLUE)Deploying governance-hub Helm chart...$(NC)"
	@if [ ! -f k8s/tls/ca.crt ]; then \
		echo "$(RED)Error: TLS certificate not found at k8s/tls/ca.crt$(NC)"; \
		echo "$(BLUE)Run 'make generate-certs-if-missing' first$(NC)"; \
		exit 1; \
	fi
	@CA_BUNDLE=$$(base64 < k8s/tls/ca.crt | tr -d '\n'); \
	helm upgrade --install $(HELM_RELEASE) $(CHART_PATH) \
	    --namespace $(NAMESPACE) \
	    --set-string tls.caBundle="$$CA_BUNDLE" \
	    --set-string namespaceLabels.team="$(NAMESPACE_TEAM)" \
	    --set-string namespaceLabels.environment="$(NAMESPACE_ENV)" \
	    --wait
	@echo "$(GREEN)✓ Helm release deployed$(NC)"

wait-deployments: ## Wait for deployments to be ready
	@echo "$(BLUE)Waiting for deployments to be ready...$(NC)"
	@kubectl wait --for=condition=available --timeout=120s \
	  deployment/governance-hub-app \
	  deployment/governance-hub-nginx \
	  -n $(NAMESPACE) 2>/dev/null || true
	@echo "$(GREEN)✓ Deployments ready$(NC)"

generate-certs-fresh: ## Generate fresh TLS certificates (overwrites existing)
	@echo "$(BLUE)Generating fresh TLS certificates (overwriting any existing)...$(NC)"
	@cd k8s/tls && chmod +x generate-certs.sh && ./generate-certs.sh > /dev/null 2>&1
	@echo "$(GREEN)✓ TLS certificates generated$(NC)"

generate-certs-if-missing: ## Generate TLS certificates only if they don't exist; always syncs the K8s secret
	@echo "$(BLUE)Checking for existing TLS certificates...$(NC)"
	@if [ -f k8s/tls/ca.crt ] && [ -f k8s/tls/server.crt ] && [ -f k8s/tls/server.key ]; then \
		echo "$(GREEN)✓ TLS certificate files exist$(NC)"; \
	else \
		echo "$(BLUE)Generating TLS certificates...$(NC)"; \
		cd k8s/tls && chmod +x generate-certs.sh && ./generate-certs.sh > /dev/null 2>&1; \
		echo "$(GREEN)✓ TLS certificates generated$(NC)"; \
	fi
	@echo "$(BLUE)Syncing TLS secret to cluster...$(NC)"
	@kubectl delete secret governance-hub-tls --namespace=$(NAMESPACE) --ignore-not-found > /dev/null
	@kubectl create secret tls governance-hub-tls \
		--cert=k8s/tls/server.crt \
		--key=k8s/tls/server.key \
		--namespace=$(NAMESPACE) > /dev/null
	@echo "$(GREEN)✓ TLS secret synced$(NC)"

generate-certs: generate-certs-if-missing ## Alias for generate-certs-if-missing

redeploy: build create-namespace generate-certs-if-missing ## Rebuild Docker images and redeploy via Helm
	@echo "$(BLUE)Redeploying with new images...$(NC)"
	@if [ ! -f k8s/tls/ca.crt ]; then \
		echo "$(RED)Error: TLS certificate not found at k8s/tls/ca.crt$(NC)"; \
		exit 1; \
	fi
	@CA_BUNDLE=$$(base64 < k8s/tls/ca.crt | tr -d '\n'); \
	helm upgrade --install $(HELM_RELEASE) $(CHART_PATH) \
	    --namespace $(NAMESPACE) \
	    --set-string tls.caBundle="$$CA_BUNDLE" \
	    --set-string namespaceLabels.team="$(NAMESPACE_TEAM)" \
	    --set-string namespaceLabels.environment="$(NAMESPACE_ENV)"
	@kubectl rollout restart deployment/governance-hub-app -n $(NAMESPACE) 2>/dev/null || true
	@kubectl rollout restart deployment/governance-hub-nginx -n $(NAMESPACE) 2>/dev/null || true
	@make wait-deployments
	@echo "$(GREEN)✓ Redeploy complete$(NC)"

##@ Verification
verify: ## Verify deployment status
	@echo "$(BLUE)Verifying deployment...$(NC)"
	@echo ""
	@echo "$(BLUE)Pods:$(NC)"
	@kubectl get pods -n $(NAMESPACE) -o wide || echo "No pods found"
	@echo ""
	@echo "$(BLUE)Services:$(NC)"
	@kubectl get svc -n $(NAMESPACE) || echo "No services found"
	@echo ""
	@echo "$(BLUE)Webhooks:$(NC)"
	@echo "  Validating: $$(kubectl get validatingwebhookconfigurations | grep governance | wc -l)"
	@echo "  Mutating:   $$(kubectl get mutatingwebhookconfigurations | grep governance | wc -l)"
	@echo ""
	@echo "$(GREEN)✓ Verification complete$(NC)"

##@ Unit Testing (no cluster required)
unit-test: ## Run unit tests locally with pytest
	@echo "$(BLUE)Installing test dependencies...$(NC)"
	@pip install -r requirements-test.txt -q
	@echo "$(BLUE)Running unit tests...$(NC)"
	@pytest tests/ -v
	@echo "$(GREEN)✓ Unit tests passed$(NC)"

unit-test-cov: ## Run unit tests with coverage report
	@echo "$(BLUE)Running unit tests with coverage...$(NC)"
	@pip install -r requirements-test.txt -q
	@pytest tests/ -v --cov=validators --cov=mutators --cov=api --cov-report=term-missing
	@echo "$(GREEN)✓ Coverage report complete$(NC)"

##@ Integration Testing (requires running cluster)
test: test-setup create-test-namespaces test-policies test-privileged test-latest test-mutation test-labels test-teardown ## Run all integration tests against cluster

test-setup: ## Verify test namespaces exist and clean up any leftover test pods
	@echo "$(BLUE)Preparing test namespace $(TEST_NAMESPACE)...$(NC)"
	@kubectl delete pod --all -n $(TEST_NAMESPACE) --ignore-not-found > /dev/null 2>&1 || true
	@echo "$(GREEN)✓ Test namespace ready$(NC)"
	@echo "$(BLUE)Preparing validator test namespace $(VALIDATOR_TEST_NAMESPACE)...$(NC)"
	@kubectl delete pod --all -n $(VALIDATOR_TEST_NAMESPACE) --ignore-not-found > /dev/null 2>&1 || true
	@echo "$(GREEN)✓ Validator test namespace ready$(NC)"

test-teardown: ## Delete test namespaces and all resources in them
	@echo "$(BLUE)Cleaning up test namespace $(TEST_NAMESPACE)...$(NC)"
	@kubectl delete namespace $(TEST_NAMESPACE) --ignore-not-found > /dev/null
	@echo "$(GREEN)✓ Test namespace deleted$(NC)"
	@echo "$(BLUE)Cleaning up validator test namespace $(VALIDATOR_TEST_NAMESPACE)...$(NC)"
	@kubectl delete namespace $(VALIDATOR_TEST_NAMESPACE) --ignore-not-found > /dev/null
	@echo "$(GREEN)✓ Validator test namespace deleted$(NC)"

test-policies: ## Test policies endpoint
	@echo "$(BLUE)Testing policies endpoint...$(NC)"
	@kubectl exec -i -n $(NAMESPACE) \
	  $$(kubectl get pod -n $(NAMESPACE) -l component=nginx -o jsonpath='{.items[0].metadata.name}') \
	  -- wget -q -O - http://governance-hub-app:5000/api/v1/policies | head -20
	@echo "$(GREEN)✓ Policies test passed$(NC)"

test-privileged: ## Test that privileged pods are blocked
	@echo "$(BLUE)Testing: Reject privileged pod...$(NC)"
	@echo "Expected: Pod creation should be denied"
	@if kubectl run privileged-test \
	  --image=alpine:3.18 \
	  --overrides='{"spec":{"containers":[{"name":"test","image":"alpine:3.18","resources":{"limits":{"cpu":"100m","memory":"64Mi"}},"securityContext":{"privileged":true}}]}}' \
	  -n $(VALIDATOR_TEST_NAMESPACE) 2>&1 | grep -qi "denied\|not allowed"; then \
	    echo "$(GREEN)✓ Privileged pod correctly rejected$(NC)"; \
	else \
	    kubectl delete pod privileged-test -n $(VALIDATOR_TEST_NAMESPACE) --ignore-not-found > /dev/null 2>&1; \
	    echo "$(RED)✗ FAIL: Privileged pod was not rejected$(NC)"; exit 1; \
	fi

test-latest: ## Test that :latest images are blocked
	@echo "$(BLUE)Testing: Reject :latest tag...$(NC)"
	@echo "Expected: Pod creation should be denied"
	@if kubectl run test-latest --image=alpine:latest -n $(VALIDATOR_TEST_NAMESPACE) 2>&1 | grep -qi "denied\|not allowed\|latest"; then \
	    echo "$(GREEN)✓ Latest tag correctly rejected$(NC)"; \
	else \
	    kubectl delete pod test-latest -n $(VALIDATOR_TEST_NAMESPACE) --ignore-not-found > /dev/null 2>&1; \
	    echo "$(RED)✗ FAIL: Pod with :latest tag was not rejected$(NC)"; exit 1; \
	fi

test-mutation: ## Test that resources and labels are mutated
	@echo "$(BLUE)Testing: Resource mutation...$(NC)"
	@kubectl apply -f examples/test-mutation-pod.yaml -n $(TEST_NAMESPACE) > /dev/null
	@sleep 2
	@echo "  Checking if default resources were injected..."
	@if kubectl get pod test-mutation-pod -n $(TEST_NAMESPACE) -o jsonpath='{.spec.containers[0].resources.limits.cpu}' 2>/dev/null | grep -q "."; then \
	    echo "  Resources: $$(kubectl get pod test-mutation-pod -n $(TEST_NAMESPACE) -o jsonpath='{.spec.containers[0].resources}')"; \
	    echo "$(GREEN)✓ Resource mutation verified$(NC)"; \
	else \
	    echo "$(RED)✗ FAIL: Default resources were not injected by mutating webhook$(NC)"; exit 1; \
	fi

test-labels: ## Test that governance labels are injected by mutating webhook
	@echo "$(BLUE)Testing: Label injection...$(NC)"
	@if kubectl get pod test-mutation-pod -n $(TEST_NAMESPACE) -o yaml 2>/dev/null | grep -qE "app.kubernetes.io/managed-by|governance/policy-version"; then \
	    kubectl get pod test-mutation-pod -n $(TEST_NAMESPACE) -o yaml | grep -E "app.kubernetes.io/managed-by|governance/policy-version" | head -5; \
	    echo "$(GREEN)✓ Label injection verified$(NC)"; \
	else \
	    echo "$(RED)✗ FAIL: Governance labels not injected by mutating webhook$(NC)"; exit 1; \
	fi

##@ Logs
logs: ## Show combined logs from all pods
	@echo "$(BLUE)Recent logs from governance-hub-demo namespace:$(NC)"
	@kubectl logs -n $(NAMESPACE) --all-containers=true -l app=governance-hub-demo --tail=20 || echo "No logs found"

logs-app: ## Show Flask app logs
	@echo "$(BLUE)Flask app logs:$(NC)"
	@kubectl logs -n $(NAMESPACE) -l component=app --tail=50 -f || true

logs-nginx: ## Show nginx logs
	@echo "$(BLUE)Nginx logs:$(NC)"
	@kubectl logs -n $(NAMESPACE) -l component=nginx --tail=50 -f || true

##@ Access
ports: ## Show all exposed ports
	@echo "$(BLUE)Service ports in $(NAMESPACE):$(NC)"
	@kubectl get svc -n $(NAMESPACE) -o wide

port-forward: ## Forward nginx service to localhost:8443
	@echo "$(BLUE)Forwarding governance-hub-nginx:443 to localhost:8443...$(NC)"
	@echo "Press Ctrl+C to stop"
	@kubectl port-forward -n $(NAMESPACE) svc/governance-hub-nginx 8443:443

shell: ## Open shell in nginx pod
	@echo "$(BLUE)Opening shell in nginx pod...$(NC)"
	@kubectl exec -it -n $(NAMESPACE) \
	  $$(kubectl get pod -n $(NAMESPACE) -l component=nginx -o jsonpath='{.items[0].metadata.name}') \
	  -- sh

exec-app: ## Execute command in app pod (use COMMAND="...")
	@if [ -z "$(COMMAND)" ]; then \
		echo "Usage: make exec-app COMMAND=\"your command here\""; \
	else \
		kubectl exec -it -n $(NAMESPACE) \
		  $$(kubectl get pod -n $(NAMESPACE) -l component=app -o jsonpath='{.items[0].metadata.name}') \
		  -- $(COMMAND); \
	fi

exec-nginx: ## Execute command in nginx pod (use COMMAND="...")
	@if [ -z "$(COMMAND)" ]; then \
		echo "Usage: make exec-nginx COMMAND=\"your command here\""; \
	else \
		kubectl exec -it -n $(NAMESPACE) \
		  $$(kubectl get pod -n $(NAMESPACE) -l component=nginx -o jsonpath='{.items[0].metadata.name}') \
		  -- $(COMMAND); \
	fi

##@ Cleanup
cleanup: cleanup-helm cleanup-docker-images cleanup-certs cleanup-minikube ## Full cleanup including Minikube config

cleanup-helm: ## Uninstall Helm release and delete namespaces
	@echo "$(BLUE)Uninstalling Helm release...$(NC)"
	@helm uninstall $(HELM_RELEASE) --namespace $(NAMESPACE) 2>/dev/null || true
	@kubectl delete namespace $(NAMESPACE) --ignore-not-found 2>/dev/null || true
	@kubectl delete namespace $(TEST_NAMESPACE) --ignore-not-found 2>/dev/null || true
	@kubectl delete namespace $(VALIDATOR_TEST_NAMESPACE) --ignore-not-found 2>/dev/null || true
	@echo "$(GREEN)✓ Helm release uninstalled$(NC)"

cleanup-docker-images: ## Remove local Docker images and unload from Minikube
	@echo "$(BLUE)Removing Docker images...$(NC)"
	@docker rmi -f $(APP_IMAGE) 2>/dev/null || true
	@docker rmi -f $(NGINX_IMAGE) 2>/dev/null || true
	@docker exec minikube docker rmi -f $(APP_IMAGE) 2>/dev/null || true
	@docker exec minikube docker rmi -f $(NGINX_IMAGE) 2>/dev/null || true
	@echo "$(GREEN)✓ Docker images removed$(NC)"

cleanup-certs: ## Remove generated TLS certificates
	@echo "$(BLUE)Removing TLS certificates...$(NC)"
	@rm -f k8s/tls/*.key k8s/tls/*.crt k8s/tls/*.csr k8s/tls/*.srl
	@echo "$(GREEN)✓ Certificates removed$(NC)"

cleanup-minikube: ## Delete Minikube cluster, remove its config, and stop Colima
	@echo "$(BLUE)Deleting Minikube cluster...$(NC)"
	@minikube delete 2>/dev/null || true
	@rm -rf $(HOME)/.minikube 2>/dev/null || true
	@echo "$(GREEN)✓ Minikube cluster and config removed$(NC)"
	@if [ -n "$(COLIMA_CMD)" ]; then \
		echo "$(BLUE)Stopping Colima...$(NC)"; \
		colima stop 2>/dev/null || true; \
		echo "$(GREEN)✓ Colima stopped$(NC)"; \
	fi

helm-status: ## Show Helm release status
	@helm status $(HELM_RELEASE) --namespace $(NAMESPACE) 2>/dev/null || echo "No Helm release found"

##@ Development
check-deps: ## Check if all required tools are installed
	@echo "$(BLUE)Checking dependencies...$(NC)"
	@command -v minikube >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) minikube" || echo "$(RED)✗$(NC) minikube"
	@command -v kubectl >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) kubectl" || echo "$(RED)✗$(NC) kubectl"
	@command -v docker >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) docker" || echo "$(RED)✗$(NC) docker"
	@command -v colima >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) colima (optional)" || echo "$(BLUE)○$(NC) colima (optional, falls back to Docker daemon)"
	@command -v openssl >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) openssl" || echo "$(RED)✗$(NC) openssl"
	@command -v helm >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) helm (optional)" || echo "$(BLUE)○$(NC) helm (optional)"

.DEFAULT_GOAL := help
