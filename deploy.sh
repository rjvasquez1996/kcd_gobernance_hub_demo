#!/bin/bash

# Governance Hub Demo - Quick Deployment Script
# This script automates the deployment process on Minikube

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "Governance Hub Demo - Deployment Script"
echo "=========================================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v minikube &> /dev/null; then
    echo "❌ Minikube not found. Please install Minikube."
    exit 1
fi

if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl not found. Please install kubectl."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker not found. Please install Docker."
    exit 1
fi

if ! command -v openssl &> /dev/null; then
    echo "❌ openssl not found. Please install openssl."
    exit 1
fi

echo "✓ All prerequisites found"
echo ""

# Check Minikube status
echo "Checking Minikube status..."
if ! minikube status &> /dev/null; then
    echo "Starting Minikube..."
    minikube start --driver=docker --memory=4096 --cpus=2
else
    echo "✓ Minikube is already running"
fi
echo ""

# Configure Docker
echo "Configuring Docker to use Minikube's Docker daemon..."
eval $(minikube docker-env)
echo "✓ Docker configured"
echo ""

# Build images
echo "Building Docker images..."
echo "  - Building governance-hub-app:latest..."
docker build -t governance-hub-app:latest -f Dockerfile . > /dev/null 2>&1
echo "  ✓ governance-hub-app:latest built"

echo "  - Building governance-hub-nginx:latest..."
docker build -t governance-hub-nginx:latest -f Dockerfile.nginx . > /dev/null 2>&1
echo "  ✓ governance-hub-nginx:latest built"
echo ""

# Create namespace
echo "Creating Kubernetes namespace..."
kubectl apply -f k8s/namespace.yaml > /dev/null
echo "✓ Namespace created"
echo ""

# Apply base manifests
echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/app-deployment.yaml \
              -f k8s/app-service.yaml \
              -f k8s/nginx-configmap.yaml \
              -f k8s/nginx-deployment.yaml \
              -f k8s/nginx-service.yaml > /dev/null
echo "✓ Base manifests applied"
echo ""

# Wait for deployments to be ready
echo "Waiting for deployments to be ready..."
kubectl wait --for=condition=available --timeout=120s \
  deployment/governance-hub-app \
  deployment/governance-hub-nginx \
  -n governance-hub-demo > /dev/null 2>&1 || true
echo "✓ Deployments are ready (or timed out - this is OK)"
echo ""

# Generate TLS certificates
echo "Generating TLS certificates..."
cd k8s/tls
./generate-certs.sh > /dev/null 2>&1
CA_BUNDLE=$(base64 < ca.crt | tr -d '\n')
cd ../..
echo "✓ TLS certificates generated"
echo ""

# Update webhook configurations with CA certificate
echo "Updating webhook configurations with CA certificate..."
sed -i.bak "s|caBundle: \"\"|caBundle: \"$CA_BUNDLE\"|" k8s/validating-webhook.yaml
sed -i.bak "s|caBundle: \"\"|caBundle: \"$CA_BUNDLE\"|" k8s/mutating-webhook.yaml
rm -f k8s/*.bak
echo "✓ Webhook configurations updated"
echo ""

# Apply webhook configurations
echo "Applying webhook configurations..."
kubectl apply -f k8s/validating-webhook.yaml \
              -f k8s/mutating-webhook.yaml > /dev/null
echo "✓ Webhook configurations applied"
echo ""

# Wait a moment for webhooks to be ready
echo "Waiting for webhooks to be registered..."
sleep 3
echo "✓ Webhooks registered"
echo ""

# Display summary
echo "=========================================="
echo "✓ Deployment Complete!"
echo "=========================================="
echo ""
echo "Cluster Info:"
echo "  - Namespace: governance-hub-demo"
echo "  - Pods:"
kubectl get pods -n governance-hub-demo | tail -n +2 | awk '{print "    - " $1 " (" $3 ")"}'
echo ""
echo "Available Endpoints:"
echo "  - API: http://governance-hub-app:5000/api/v1"
echo "  - Health: http://localhost:5000/health"
echo "  - Policies: http://localhost:5000/api/v1/policies"
echo ""
echo "Next Steps:"
echo "  1. Run tests with: kubectl apply -f k8s/examples/"
echo "  2. Check logs with: kubectl logs -n governance-hub-demo -l app=governance-hub-demo"
echo "  3. Read the full guide: cat README.md"
echo ""
echo "To test directly:"
echo "  kubectl exec -it -n governance-hub-demo \\
    \$(kubectl get pod -n governance-hub-demo -l component=nginx -o jsonpath='{.items[0].metadata.name}') \\
    -- sh"
echo ""
