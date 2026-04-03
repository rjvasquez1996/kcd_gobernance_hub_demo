# Governance Hub Demo - Kubernetes Governance Service

A production-inspired demonstration of a Kubernetes admission webhook service for policy validation and resource mutation. Fully self-contained and deployable on Minikube with zero external dependencies.

## Overview

Governance Hub implements two types of Kubernetes admission webhooks:

### **Validating Webhooks** (Deny Invalid Resources)
- **Pod Validators**:
  - `ForbidPrivilegedMode` - Blocks privileged containers and privilege escalation
  - `RequireResourceLimits` - Requires CPU/memory limits on all containers
  - `ForbidLatestTag` - Blocks container images using `:latest` or untagged versions

- **Namespace Validators**:
  - `NoDirectNamespaceCreation` - Blocks direct CREATE operations on Namespace resources
  - `RequiredLabelsCheck` - Requires `team` and `environment` labels on namespaces

- **Ingress Validators**:
  - `IngressTLSRequired` - Requires TLS configuration on all Ingress resources
  - `IngressRuleLimit` - Limits number of rules per Ingress (default: 5)

### **Mutating Webhooks** (Automatically Fix Resources)
- **Pod Mutators**:
  - `CommonLabelsMutator` - Injects governance labels
  - `DefaultResourcesMutator` - Adds default resource requests/limits (100m CPU, 128Mi memory)

- **Namespace Mutators**:
  - `RemoveKubectlAnnotationMutator` - Removes kubectl's last-applied-configuration annotation

- **Ingress Mutators**:
  - `IngressClassDefaultMutator` - Sets default `ingressClassName: nginx` if not specified

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Kubernetes API Server                                       │
│  (AdmissionReview Request)                                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  nginx (HTTPS:443)                                          │
│  - TLS termination                                          │
│  - Request routing                                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│  Flask Application (HTTP:5000)                              │
│  ├── /api/v1/validate  → ValidatingWebhook                 │
│  ├── /api/v1/mutate    → MutatingWebhook                   │
│  ├── /api/v1/policies  → List active policies              │
│  └── /api/v1/health    → Service health check              │
└────────────────────────┬────────────────────────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ Validators  │ │ Mutators    │ │ Policies    │
    │ (Pod, NS,   │ │ (Pod, NS,   │ │ (Config)    │
    │  Ingress)   │ │  Ingress)   │ │             │
    └─────────────┘ └─────────────┘ └─────────────┘
```

## Prerequisites

- **Minikube** 1.20+
- **Docker** (for building images)
- **kubectl** 1.20+
- **openssl** (for generating TLS certificates)
- **bash** shell

## Quick Start

> **Note**: TLS certificates are not included in the repository and must be generated on first deployment. The `generate-certs.sh` script will create them automatically during the deployment process (Step 6 below).

### 1. Start Minikube

```bash
minikube start --driver=docker --memory 4096 --cpus 2
```

### 2. Configure Docker to Use Minikube's Docker Daemon

```bash
eval $(minikube docker-env)
```

### 3. Navigate to Demo Directory

```bash
cd /Users/ricardovasquez/test/kcd/demo
```

### 4. Build Docker Images

```bash
# Build Flask app image
docker build -t governance-hub-app:latest -f Dockerfile .

# Build nginx proxy image
docker build -t governance-hub-nginx:latest -f Dockerfile.nginx .
```

Verify images were built:
```bash
docker images | grep governance-hub
```

### 5. Create Namespace and Apply Base Manifests

```bash
# Create the namespace first
kubectl apply -f k8s/namespace.yaml

# Create nginx ConfigMap and app deployment
kubectl apply -f k8s/app-deployment.yaml \
              -f k8s/app-service.yaml \
              -f k8s/nginx-configmap.yaml \
              -f k8s/nginx-deployment.yaml \
              -f k8s/nginx-service.yaml
```

### 6. Generate TLS Certificates

```bash
# Make script executable
chmod +x k8s/tls/generate-certs.sh

# Generate certificates and create Kubernetes secret
cd k8s/tls
./generate-certs.sh
cd ../..
```

**Important**: Save the base64-encoded CA certificate output - you'll need it in the next step.

### 7. Update Webhook Configurations with CA Certificate

Edit the CA certificate placeholder in the webhook configurations:

```bash
# Get the base64-encoded CA certificate
CA_BUNDLE=$(base64 < k8s/tls/ca.crt | tr -d '\n')

# Update validating webhook
sed -i.bak "s|caBundle: \"\"|caBundle: \"$CA_BUNDLE\"|" k8s/validating-webhook.yaml

# Update mutating webhook
sed -i.bak "s|caBundle: \"\"|caBundle: \"$CA_BUNDLE\"|" k8s/mutating-webhook.yaml
```

Or manually copy the CA certificate from the `generate-certs.sh` output into both YAML files.

### 8. Apply Webhook Configurations

```bash
kubectl apply -f k8s/validating-webhook.yaml \
              -f k8s/mutating-webhook.yaml
```

### 9. Verify Deployment

```bash
# Check that pods are running
kubectl get pods -n governance-hub-demo

# Expected output:
# NAME                                READY   STATUS    RESTARTS   AGE
# governance-hub-app-xxxxxxxxxx-xxxxx     1/1     Running   0          XXs
# governance-hub-nginx-xxxxxxxxxx-xxxxx   1/1     Running   0          XXs

# Check service endpoints
kubectl get svc -n governance-hub-demo

# Check webhook configurations
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations
```

## Testing the Demo

### Test 1: Query Available Policies

```bash
# Get a shell in the nginx pod
kubectl exec -it -n governance-hub-demo \
  $(kubectl get pod -n governance-hub-demo -l component=nginx -o jsonpath='{.items[0].metadata.name}') \
  -- sh

# Inside the pod, test the policies endpoint
wget -O - http://governance-hub-app:5000/api/v1/policies

# Expected output: JSON list of validators and mutators
```

### Test 2: Test Validator - Reject Privileged Pod

```bash
# Try to create a privileged pod
kubectl run --rm -it privileged-test \
  --image=alpine \
  --overrides='{"spec": {"containers": [{"name": "test", "image": "alpine", "securityContext": {"privileged": true}}]}}' \
  -- sh
```

Expected: Pod creation is denied with message about privileged mode not allowed.

### Test 3: Test Validator - Reject Untagged Image

```bash
kubectl run test-latest --image=alpine:latest
```

Expected: Pod creation is denied because `:latest` tag is not allowed.

### Test 4: Test Mutator - Resource Limits Injection

Create a pod without resource limits:

```bash
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: test-mutation
spec:
  containers:
  - name: app
    image: alpine:3.18
    command: ['sleep', '3600']
EOF
```

Then inspect the created pod:

```bash
kubectl get pod test-mutation -o yaml | grep -A10 resources
```

Expected: Resource requests and limits have been automatically injected (100m CPU, 128Mi memory).

### Test 5: Test Mutator - Label Injection

Check that the pod has governance labels:

```bash
kubectl get pod test-mutation -o yaml | grep -A5 labels
```

Expected: Labels `app.kubernetes.io/managed-by: governance-hub-demo` and `governance/policy-version: v1` are present.

### Test 6: Test Namespace Validation

Try to create a namespace directly:

```bash
kubectl create namespace test-namespace
```

Expected: Creation is denied with message about direct namespace creation not allowed.

### Test 7: Direct API Testing (Advanced)

If you want to test the webhook endpoints directly:

```bash
# Port-forward to the nginx service
kubectl port-forward -n governance-hub-demo svc/governance-hub-nginx 8443:443 &

# Create a test AdmissionReview payload
cat > /tmp/admission-review.json <<EOF
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "request": {
    "uid": "12345",
    "kind": {
      "group": "",
      "kind": "Pod"
    },
    "operation": "CREATE",
    "namespace": "default",
    "object": {
      "apiVersion": "v1",
      "kind": "Pod",
      "metadata": {
        "name": "test-pod"
      },
      "spec": {
        "containers": [
          {
            "name": "app",
            "image": "alpine:3.18",
            "resources": {}
          }
        ]
      }
    }
  }
}
EOF

# Test validation endpoint
curl -k -X POST https://localhost:8443/api/v1/validate \
  -H "Content-Type: application/json" \
  -d @/tmp/admission-review.json | jq .

# Test mutation endpoint
curl -k -X POST https://localhost:8443/api/v1/mutate \
  -H "Content-Type: application/json" \
  -d @/tmp/admission-review.json | jq .
```

## Project Structure

```
demo/
├── app/                          # Flask application
│   ├── app.py                    # Flask entry point
│   ├── requirements.txt           # Python dependencies
│   ├── validators/
│   │   ├── __init__.py           # Registration & discovery
│   │   ├── base.py               # Validator base class
│   │   ├── pod.py                # Pod validators
│   │   ├── namespace.py          # Namespace validators
│   │   └── ingress.py            # Ingress validators
│   ├── mutators/
│   │   ├── __init__.py           # Registration & discovery
│   │   ├── base.py               # Mutator base class
│   │   ├── pod.py                # Pod mutators
│   │   ├── namespace.py          # Namespace mutators
│   │   └── ingress.py            # Ingress mutators
│   └── api/
│       ├── __init__.py           # Flask blueprints
│       ├── validate.py           # POST /validate endpoint
│       ├── mutate.py             # POST /mutate endpoint
│       ├── policies.py           # GET /policies endpoint
│       └── health.py             # GET /health endpoint
├── nginx/
│   └── nginx.conf                # Nginx configuration
├── k8s/                          # Kubernetes manifests
│   ├── namespace.yaml
│   ├── app-deployment.yaml
│   ├── app-service.yaml
│   ├── nginx-deployment.yaml
│   ├── nginx-service.yaml
│   ├── nginx-configmap.yaml
│   ├── validating-webhook.yaml
│   ├── mutating-webhook.yaml
│   └── tls/
│       └── generate-certs.sh     # TLS certificate generation
├── Dockerfile                    # Python 3.11-slim + Flask
├── Dockerfile.nginx              # nginx:alpine
└── README.md                     # This file
```

## Adding New Validators

To add a new validator:

1. Create a new class in `app/validators/<resource>.py` extending `Validator`
2. Implement `is_applicable()` and `validate()` methods
3. Decorate with `@registered_as_validator`

Example:

```python
from validators.base import Validator, registered_as_validator

@registered_as_validator
class MyValidator(Validator):
    def is_applicable(self, review_request):
        return review_request.get('object', {}).get('kind') == 'Pod'

    def validate(self, review_request):
        # Return (True, None) to allow or (False, "message") to deny
        return True, None
```

## Adding New Mutators

To add a new mutator:

1. Create a new class in `app/mutators/<resource>.py` extending `Mutator`
2. Implement `is_applicable()` and `generate_patch()` methods
3. Decorate with `@registered_as_mutator`
4. Return a list of RFC 6902 JSON Patch operations

Example:

```python
from mutators.base import Mutator, registered_as_mutator

@registered_as_mutator
class MyMutator(Mutator):
    def is_applicable(self, review_request):
        return review_request.get('object', {}).get('kind') == 'Pod'

    def generate_patch(self, review_request):
        return [
            {
                'op': 'add',
                'path': '/metadata/labels/my-label',
                'value': 'my-value'
            }
        ]
```

## Troubleshooting

### Webhooks Not Triggering
- Verify webhook configurations are applied: `kubectl get validatingwebhookconfigurations`
- Check certificate: `kubectl describe validatingwebhookconfigurations governance-hub-validator`
- Ensure CA bundle is set correctly in webhook config

### TLS Certificate Errors
- Regenerate certificates: `cd k8s/tls && rm -f *.key *.crt *.csr && ./generate-certs.sh`
- Update webhook configurations with new CA bundle
- Restart nginx pod: `kubectl rollout restart deployment/governance-hub-nginx -n governance-hub-demo`

### Pods Not Getting Mutated
- Check mutator logs: `kubectl logs -n governance-hub-demo <nginx-pod> | grep mutate`
- Verify mutating webhook is enabled: `kubectl get mutatingwebhookconfigurations`
- Test mutation endpoint directly with curl (see Testing section)

### High Latency on Pod Creation
- Webhook timeouts default to 10s (configured in webhook YAML)
- Ensure Minikube has sufficient resources: at least 4GB memory, 2 CPUs
- Check app/nginx logs for performance issues

## Cleanup

To delete the demo deployment:

```bash
# Delete webhook configurations first (to avoid hanging deletions)
kubectl delete validatingwebhookconfigurations governance-hub-validator
kubectl delete mutatingwebhookconfigurations governance-hub-mutator

# Delete the namespace (cascades to all resources)
kubectl delete namespace governance-hub-demo

# Stop Minikube
minikube stop
```

## Differences from Original Coastguard

| Aspect | Original | Demo |
|--------|----------|------|
| Database | MySQL + Alembic | None |
| Authentication | MyOrg SSO | None |
| External APIs | YellowPages, Vault | Static config |
| Image Registry | Artifactory | Public registry |
| Metrics | Datadog | Logging only |
| App Server | uWSGI + ddtrace | Flask dev server |
| Proxy | OpenResty (nginx + Lua) | Plain nginx |
| Cloud Provider | AWS EKS specific | Generic Kubernetes |
| Infrastructure | Terraform-managed | Minikube |

## API Reference

### POST /api/v1/validate
Kubernetes admission webhook for validation. Accepts `AdmissionReview` JSON.

**Request:**
```json
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "request": { ... }
}
```

**Response:**
```json
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "response": {
    "uid": "...",
    "allowed": true/false,
    "status": {
      "message": "denial reason if not allowed"
    }
  }
}
```

### POST /api/v1/mutate
Kubernetes admission webhook for mutations. Accepts `AdmissionReview` JSON.

**Response:**
```json
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "response": {
    "uid": "...",
    "allowed": true,
    "patch": "base64-encoded JSON Patch",
    "patchType": "JSONPatch"
  }
}
```

### GET /api/v1/policies
List all active validators and mutators.

**Response:**
```json
{
  "validators": [
    {
      "name": "ForbidPrivilegedMode",
      "type": "validator",
      "description": "Block privileged containers and privilege escalation."
    }
  ],
  "mutators": [...],
  "total_validators": 7,
  "total_mutators": 4
}
```

### GET /api/v1/health
Service health check.

**Response:**
```json
{
  "status": "ok",
  "validators_loaded": 7,
  "mutators_loaded": 4
}
```

## Resources

- [Kubernetes Admission Webhooks](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [RFC 6902 - JSON Patch](https://tools.ietf.org/html/rfc6902)
- [Original Coastguard Project](../../cg/)
- [Minikube Documentation](https://minikube.sigs.k8s.io/)

## License

This demo project is provided as-is for educational and demonstration purposes.
