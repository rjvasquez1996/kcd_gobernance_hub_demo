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
- **Colima** (macOS) — used as the Docker runtime; `make setup` starts it automatically
- **kubectl** 1.20+
- **Helm** 3.0+
- **openssl** (for generating TLS certificates)

Install on macOS:

```bash
brew install minikube colima kubectl helm openssl
```

## Namespaces

| Namespace | Purpose |
|-----------|---------|
| `governance-hub-demo` | Base application (webhook service) — excluded from webhook interception |
| `governance-hub-test` | Mutator integration tests |
| `governance-hub-validator-test` | Validator integration tests |

> **Important**: test namespaces must be created **before** the webhook is deployed because `NoDirectNamespaceCreation` blocks namespace creation once the webhook is active. `make setup` handles this automatically.

## Quick Start

```bash
cd demo/
make setup
```

`make setup` runs the full fresh setup in the correct order:

1. Start Colima with 4 CPU / 4GB memory (restarts if under-resourced)
2. Start Minikube using Colima's Docker daemon
3. Build Docker images (`v1`) and load them into Minikube via `docker save | docker exec`
4. Create `governance-hub-demo` namespace
5. Create `governance-hub-test` and `governance-hub-validator-test` namespaces (before webhook is active)
6. Generate TLS certificates and sync the secret
7. Deploy via Helm (activates the admission webhooks)
8. Wait for deployments to be ready
9. Print a verification summary

### Run Integration Tests

```bash
make test
```

### Run Unit Tests (no cluster required)

```bash
make unit-test
```

---

### Manual Setup (step by step)

```bash
# 1. Start Colima (Docker runtime)
make colima-start

# 2. Start Minikube
make minikube-start

# 3. Build images (tagged v1) and load into Minikube
make build

# 4. Create base namespace
make create-namespace

# 5. Create test namespaces (must happen before webhook is active)
make create-test-namespaces

# 6. Generate TLS certificates
make generate-certs-if-missing

# 7. Deploy via Helm (activates the webhook)
make deploy-helm

# 8. Wait for pods
make wait-deployments
```

## Testing the Demo

### Test 1: Query Available Policies

```bash
make test-policies
```

Or manually:

```bash
kubectl exec -it -n governance-hub-demo \
  $(kubectl get pod -n governance-hub-demo -l component=nginx -o jsonpath='{.items[0].metadata.name}') \
  -- wget -q -O - http://governance-hub-app:5000/api/v1/policies
```

### Test 2: Validator - Reject Privileged Pod

> Validator tests run in `governance-hub-validator-test`.

```bash
kubectl run privileged-test \
  --image=alpine:3.18 \
  --overrides='{"spec":{"containers":[{"name":"test","image":"alpine:3.18","resources":{"limits":{"cpu":"100m","memory":"64Mi"}},"securityContext":{"privileged":true}}]}}' \
  -n governance-hub-validator-test
```

Expected: Pod creation is denied with a message about privileged mode not being allowed.

### Test 3: Validator - Reject Latest Tag

```bash
kubectl run test-latest --image=alpine:latest -n governance-hub-validator-test
```

Expected: Pod creation is denied because `:latest` tag is not allowed.

### Test 4: Mutator - Resource Limits Injection

> Mutator tests run in `governance-hub-test`.

```bash
kubectl apply -f examples/test-mutation-pod.yaml -n governance-hub-test
kubectl get pod test-mutation-pod -n governance-hub-test \
  -o jsonpath='{.spec.containers[0].resources}' | jq .
```

Expected: Resource requests and limits have been automatically injected (100m CPU, 128Mi memory).

### Test 5: Mutator - Label Injection

```bash
kubectl get pod test-mutation-pod -n governance-hub-test \
  -o jsonpath='{.metadata.labels}' | jq .
```

Expected: Labels `app.kubernetes.io/managed-by: governance-hub-demo` and `governance/policy-version: v1` are present.

### Test 6: Namespace Validation

```bash
kubectl create namespace test-namespace
```

Expected: Creation is denied with a message about direct namespace creation not being allowed.

### Run All Integration Tests

```bash
make test
```

### Test 7: Direct API Testing (Advanced)

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
    "kind": { "group": "", "kind": "Pod" },
    "operation": "CREATE",
    "namespace": "default",
    "object": {
      "apiVersion": "v1",
      "kind": "Pod",
      "metadata": { "name": "test-pod" },
      "spec": {
        "containers": [{ "name": "app", "image": "alpine:3.18", "resources": {} }]
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
│   ├── requirements.txt          # Python dependencies
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
├── governance-hub-chart/         # Helm chart
│   ├── Chart.yaml
│   ├── values.yaml
│   └── templates/
│       ├── app-deployment.yaml
│       ├── app-service.yaml
│       ├── nginx-deployment.yaml
│       ├── nginx-service.yaml
│       ├── nginx-configmap.yaml
│       ├── validating-webhook.yaml
│       └── mutating-webhook.yaml
├── k8s/tls/
│   └── generate-certs.sh         # TLS certificate generation
├── examples/
│   └── test-mutation-pod.yaml
├── tests/                        # Unit tests (pytest)
├── Dockerfile                    # Python 3.11-slim + Flask
├── Dockerfile.nginx              # nginx:alpine
└── Makefile
```

## Adding New Validators

1. Create a new class in `app/validators/<resource>.py` extending `Validator`
2. Implement `is_applicable()` and `validate()` methods
3. Decorate with `@registered_as_validator`

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

Enable it in `governance-hub-chart/values.yaml`:

```yaml
policies:
  validators:
    MyValidator: true
```

## Adding New Mutators

1. Create a new class in `app/mutators/<resource>.py` extending `Mutator`
2. Implement `is_applicable()` and `generate_patch()` methods
3. Decorate with `@registered_as_mutator`
4. Return a list of RFC 6902 JSON Patch operations

```python
from mutators.base import Mutator, registered_as_mutator

@registered_as_mutator
class MyMutator(Mutator):
    def is_applicable(self, review_request):
        return review_request.get('object', {}).get('kind') == 'Pod'

    def generate_patch(self, review_request):
        return [{'op': 'add', 'path': '/metadata/labels/my-label', 'value': 'my-value'}]
```

Enable it in `governance-hub-chart/values.yaml`:

```yaml
policies:
  mutators:
    MyMutator: true
```

## Troubleshooting

### Webhooks Not Triggering
- Verify webhook configurations: `kubectl get validatingwebhookconfigurations`
- Check CA bundle: `kubectl describe validatingwebhookconfigurations governance-hub-validator`
- Ensure test pods are created in `governance-hub-validator-test` or `governance-hub-test`, not `governance-hub-demo`

### TLS Certificate Errors
- Regenerate certificates: `make generate-certs-fresh`
- Restart nginx: `kubectl rollout restart deployment/governance-hub-nginx -n governance-hub-demo`

### Pods Not Getting Mutated
- Check logs: `make logs-app`
- Verify mutating webhook: `kubectl get mutatingwebhookconfigurations`
- Test mutation endpoint directly (see Test 7 above)

### Build Errors on macOS with Colima
- Images are built using Colima's Docker daemon (tagged `v1`) and loaded into Minikube via `docker save | docker exec -i minikube docker load`
- Colima must have at least 4GB memory allocated — `make colima-start` handles this automatically, restarting Colima if it was started with less
- If you see `ErrImageNeverPull`, the image tag in Minikube doesn't match `values.yaml` (`v1`) — re-run `make build`
- If you see TLS cert errors (`no such file or directory` for `.minikube/certs`), stale `DOCKER_HOST`/`DOCKER_TLS_VERIFY` env vars are set in your shell — open a fresh terminal and retry
- If the cluster is in an inconsistent state: `make cleanup && make setup`

### Test Namespace Does Not Exist
- Test namespaces must be created before the webhook is deployed
- If the webhook is already active, run `make cleanup && make setup` to recreate everything in the correct order

## Cleanup

```bash
# Full cleanup: Helm release, namespaces, Docker images, TLS certs, and Minikube
make cleanup
```

Or to clean individual components:

```bash
make cleanup-helm          # Uninstall Helm release and delete namespaces
make cleanup-docker-images # Remove Docker images locally and from Minikube
make cleanup-certs         # Remove generated TLS certificates
make cleanup-minikube      # Delete Minikube cluster, remove ~/.minikube, and stop Colima
```

## API Reference

### POST /api/v1/validate
Kubernetes admission webhook for validation. Accepts `AdmissionReview` JSON.

**Response:**
```json
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "response": {
    "uid": "...",
    "allowed": true,
    "status": { "message": "denial reason if not allowed" }
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
  "validators": [{ "name": "ForbidPrivilegedMode", "type": "validator", "description": "..." }],
  "mutators": [...],
  "total_validators": 7,
  "total_mutators": 4
}
```

### GET /api/v1/health
```json
{ "status": "ok", "validators_loaded": 7, "mutators_loaded": 4 }
```

## Resources

- [Kubernetes Admission Webhooks](https://kubernetes.io/docs/reference/access-authn-authz/extensible-admission-controllers/)
- [RFC 6902 - JSON Patch](https://tools.ietf.org/html/rfc6902)
- [Minikube Documentation](https://minikube.sigs.k8s.io/)

## License

This demo project is provided as-is for educational and demonstration purposes.
