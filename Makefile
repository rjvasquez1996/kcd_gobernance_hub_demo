.PHONY: help minikube-start minikube-stop minikube-status build build-app build-nginx docker-images push-images deploy deploy-base wait-deployments generate-certs generate-certs-fresh generate-certs-if-missing update-webhooks deploy-webhooks verify cleanup test test-policies test-privileged test-latest test-mutation test-labels logs logs-app logs-nginx shell ports exec-app exec-nginx

# Variables
NAMESPACE ?= governance-hub-demo
APP_IMAGE ?= governance-hub-app:latest
NGINX_IMAGE ?= governance-hub-nginx:latest
DOCKER_BUILDKIT ?= 1
MINIKUBE_MEMORY ?= 4096
MINIKUBE_CPUS ?= 2
MINIKUBE_DRIVER ?= docker

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
	@echo "  1. make minikube-start"
	@echo "  2. make deploy"
	@echo "  3. make verify"
	@echo "  4. make test"

##@ Minikube
minikube-start: ## Start Minikube cluster
	@echo "$(BLUE)Starting Minikube...$(NC)"
	@minikube start --driver=$(MINIKUBE_DRIVER) --memory=$(MINIKUBE_MEMORY) --cpus=$(MINIKUBE_CPUS) 2>/dev/null || echo "Minikube already running"
	@eval $$(minikube docker-env)
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

build-app: ## Build Flask app Docker image
	@echo "$(BLUE)Building governance-hub-app:latest...$(NC)"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build -t $(APP_IMAGE) -f Dockerfile . --quiet
	@echo "$(GREEN)✓ App image built: $(APP_IMAGE)$(NC)"

build-nginx: ## Build nginx Docker image
	@echo "$(BLUE)Building governance-hub-nginx:latest...$(NC)"
	@DOCKER_BUILDKIT=$(DOCKER_BUILDKIT) docker build -t $(NGINX_IMAGE) -f Dockerfile.nginx . --quiet
	@echo "$(GREEN)✓ Nginx image built: $(NGINX_IMAGE)$(NC)"

docker-images: ## List local Docker images
	@echo "$(BLUE)Local governance-hub images:$(NC)"
	@docker images | grep governance-hub || echo "No images found"

##@ Deployment
deploy: minikube-start build deploy-base wait-deployments generate-certs-if-missing update-webhooks deploy-webhooks verify ## Full deployment pipeline

deploy-base: ## Apply base Kubernetes manifests
	@echo "$(BLUE)Creating namespace and applying base manifests...$(NC)"
	@kubectl apply -f k8s/namespace.yaml > /dev/null
	@kubectl apply -f k8s/app-deployment.yaml \
	                -f k8s/app-service.yaml \
	                -f k8s/nginx-configmap.yaml \
	                -f k8s/nginx-deployment.yaml \
	                -f k8s/nginx-service.yaml > /dev/null
	@echo "$(GREEN)✓ Base manifests applied$(NC)"

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

generate-certs-if-missing: ## Generate TLS certificates only if they don't exist
	@echo "$(BLUE)Checking for existing TLS certificates...$(NC)"
	@if [ -f k8s/tls/ca.crt ] && [ -f k8s/tls/server.crt ] && [ -f k8s/tls/server.key ]; then \
		echo "$(GREEN)✓ TLS certificates already exist, skipping generation$(NC)"; \
	else \
		echo "$(BLUE)Generating TLS certificates...$(NC)"; \
		cd k8s/tls && chmod +x generate-certs.sh && ./generate-certs.sh > /dev/null 2>&1; \
		echo "$(GREEN)✓ TLS certificates generated$(NC)"; \
	fi

generate-certs: generate-certs-if-missing ## Alias for generate-certs-if-missing

update-webhooks: ## Update webhook configs with CA certificate
	@echo "$(BLUE)Updating webhook configurations with CA certificate...$(NC)"
	@export CA_BUNDLE=$$(base64 < k8s/tls/ca.crt | tr -d '\n'); \
	sed -i.bak "s|caBundle: \"\"|caBundle: \"$$CA_BUNDLE\"|" k8s/validating-webhook.yaml; \
	sed -i.bak "s|caBundle: \"\"|caBundle: \"$$CA_BUNDLE\"|" k8s/mutating-webhook.yaml; \
	rm -f k8s/*.bak
	@echo "$(GREEN)✓ Webhook configurations updated$(NC)"

deploy-webhooks: ## Apply webhook configurations
	@echo "$(BLUE)Applying webhook configurations...$(NC)"
	@kubectl apply -f k8s/validating-webhook.yaml \
	                -f k8s/mutating-webhook.yaml > /dev/null
	@sleep 2
	@echo "$(GREEN)✓ Webhooks deployed$(NC)"

redeploy: ## Restart all deployments
	@echo "$(BLUE)Restarting deployments...$(NC)"
	@kubectl rollout restart deployment/governance-hub-app -n $(NAMESPACE)
	@kubectl rollout restart deployment/governance-hub-nginx -n $(NAMESPACE)
	@make wait-deployments
	@echo "$(GREEN)✓ Deployments restarted$(NC)"

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

##@ Testing
test: test-policies test-privileged test-latest test-mutation test-labels ## Run all tests

test-policies: ## Test policies endpoint
	@echo "$(BLUE)Testing policies endpoint...$(NC)"
	@kubectl exec -i -n $(NAMESPACE) \
	  $$(kubectl get pod -n $(NAMESPACE) -l component=nginx -o jsonpath='{.items[0].metadata.name}') \
	  -- wget -q -O - http://governance-hub-app:5000/api/v1/policies | head -20
	@echo "$(GREEN)✓ Policies test passed$(NC)"

test-privileged: ## Test that privileged pods are blocked
	@echo "$(BLUE)Testing: Reject privileged pod...$(NC)"
	@echo "Expected: Pod creation should be denied"
	@kubectl run --rm -it privileged-test \
	  --image=alpine \
	  --overrides='{"spec": {"containers": [{"name": "test", "image": "alpine", "securityContext": {"privileged": true}}]}}' \
	  -n $(NAMESPACE) \
	  -- sh -c "echo 'Pod created'" 2>&1 || echo "$(GREEN)✓ Privileged pod correctly rejected$(NC)"

test-latest: ## Test that :latest images are blocked
	@echo "$(BLUE)Testing: Reject :latest tag...$(NC)"
	@echo "Expected: Pod creation should be denied"
	@kubectl run test-latest --image=alpine:latest -n $(NAMESPACE) 2>&1 | grep -i "latest\|denied" || true
	@echo "$(GREEN)✓ Latest tag test completed$(NC)"

test-mutation: ## Test that resources are mutated
	@echo "$(BLUE)Testing: Resource mutation...$(NC)"
	@kubectl apply -f examples/test-valid-pod.yaml -n $(NAMESPACE) > /dev/null 2>&1 || true
	@echo "  Checking if default resources were injected..."
	@kubectl get pod test-valid-pod -n $(NAMESPACE) -o yaml 2>/dev/null | grep -A 2 "resources:" || echo "Pod not found or no resources"
	@echo "$(GREEN)✓ Mutation test completed$(NC)"

test-labels: ## Test that labels are mutated
	@echo "$(BLUE)Testing: Label injection...$(NC)"
	@kubectl get pods -n $(NAMESPACE) -o yaml | grep -E "app.kubernetes.io/managed-by|governance/policy-version" | head -5 || echo "No labels found"
	@echo "$(GREEN)✓ Label test completed$(NC)"

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
cleanup: cleanup-webhooks cleanup-k8s cleanup-docker-images ## Full cleanup

cleanup-webhooks: ## Delete webhook configurations
	@echo "$(BLUE)Deleting webhook configurations...$(NC)"
	@kubectl delete validatingwebhookconfigurations governance-hub-validator 2>/dev/null || true
	@kubectl delete mutatingwebhookconfigurations governance-hub-mutator 2>/dev/null || true
	@echo "$(GREEN)✓ Webhooks deleted$(NC)"

cleanup-k8s: cleanup-webhooks ## Delete Kubernetes namespace
	@echo "$(BLUE)Deleting namespace $(NAMESPACE)...$(NC)"
	@kubectl delete namespace $(NAMESPACE) 2>/dev/null || true
	@echo "$(GREEN)✓ Namespace deleted$(NC)"

cleanup-docker-images: ## Remove local Docker images
	@echo "$(BLUE)Removing Docker images...$(NC)"
	@docker rmi -f $(APP_IMAGE) 2>/dev/null || true
	@docker rmi -f $(NGINX_IMAGE) 2>/dev/null || true
	@echo "$(GREEN)✓ Docker images removed$(NC)"

cleanup-certs: ## Remove generated TLS certificates
	@echo "$(BLUE)Removing TLS certificates...$(NC)"
	@rm -f k8s/tls/*.key k8s/tls/*.crt k8s/tls/*.csr k8s/tls/*.srl
	@echo "$(GREEN)✓ Certificates removed$(NC)"

full-clean: cleanup cleanup-certs minikube-delete ## Complete cleanup including Minikube

##@ Development
check-deps: ## Check if all required tools are installed
	@echo "$(BLUE)Checking dependencies...$(NC)"
	@command -v minikube >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) minikube" || echo "$(RED)✗$(NC) minikube"
	@command -v kubectl >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) kubectl" || echo "$(RED)✗$(NC) kubectl"
	@command -v docker >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) docker" || echo "$(RED)✗$(NC) docker"
	@command -v openssl >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) openssl" || echo "$(RED)✗$(NC) openssl"
	@command -v helm >/dev/null 2>&1 && echo "$(GREEN)✓$(NC) helm (optional)" || echo "$(BLUE)○$(NC) helm (optional)"

.DEFAULT_GOAL := help
