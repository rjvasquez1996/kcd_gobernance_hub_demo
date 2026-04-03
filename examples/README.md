# Governance Hub Demo - Test Examples

This directory contains example manifests to test the validators and mutators.

## Running the Examples

### Prerequisites
- Minikube with Governance Hub Demo deployed (see parent README.md)
- kubectl configured to access the Minikube cluster

### Test 1: Valid Pod (Should Pass)

```bash
kubectl apply -f test-valid-pod.yaml
```

Expected behavior:
- Pod is created successfully
- Governance labels are injected: `app.kubernetes.io/managed-by: governance-hub-demo`

Verify:
```bash
kubectl get pod valid-test-pod -o jsonpath='{.metadata.labels}' | jq .
```

---

### Test 2: Privileged Pod (Should Fail)

```bash
kubectl apply -f test-privileged-pod.yaml
```

Expected behavior:
- Pod creation is **denied** by `ForbidPrivilegedMode` validator
- Error message: "Container 'app' has privileged: true which is not allowed"

---

### Test 3: Latest Tag Pod (Should Fail)

```bash
kubectl apply -f test-latest-tag-pod.yaml
```

Expected behavior:
- Pod creation is **denied** by `ForbidLatestTag` validator
- Error message: "Container 'app' uses untagged or :latest image 'alpine:latest'. Use explicit, non-latest tags"

---

### Test 4: Pod Without Resources (Should Pass + Mutate)

```bash
kubectl apply -f test-no-resources-pod.yaml
```

Expected behavior:
- Pod is created successfully
- Default resources are injected: CPU 100m, memory 128Mi
- Governance labels are injected

Verify resources were injected:
```bash
kubectl get pod no-resources-test-pod -o jsonpath='{.spec.containers[0].resources}' | jq .
```

Expected output:
```json
{
  "limits": {
    "cpu": "100m",
    "memory": "128Mi"
  },
  "requests": {
    "cpu": "100m",
    "memory": "128Mi"
  }
}
```

---

### Test 5: Invalid Ingress (Should Fail)

```bash
kubectl apply -f test-invalid-ingress.yaml
```

Expected behavior:
- Ingress creation is **denied** by `IngressTLSRequired` validator
- Error message: "Ingress must have TLS configured. Add spec.tls[] with at least one host and secretName"

---

### Test 6: Valid Ingress (Should Pass + Mutate)

```bash
kubectl apply -f test-valid-ingress.yaml
```

Expected behavior:
- Ingress is created successfully
- `ingressClassName: nginx` is injected if not specified
- (In this example it will be mutated since we didn't specify one)

Verify ingress class was injected:
```bash
kubectl get ingress valid-ingress -o jsonpath='{.spec.ingressClassName}'
```

---

## Clean Up

Remove all test resources:

```bash
# Remove all pods
kubectl delete pods --all

# Remove all ingresses
kubectl delete ingresses --all

# Or selectively:
kubectl delete -f test-valid-pod.yaml
kubectl delete -f test-no-resources-pod.yaml
kubectl delete -f test-valid-ingress.yaml
```

---

## Observing Webhook Behavior

### Check Webhook Logs

Get logs from the API pod:
```bash
kubectl logs -n governance-hub-demo -l component=app -f
```

Get logs from the nginx proxy:
```bash
kubectl logs -n governance-hub-demo -l component=nginx -f
```

### Describe Webhook Configurations

```bash
# View validator webhook
kubectl describe validatingwebhookconfigurations governance-hub-validator

# View mutator webhook
kubectl describe mutatingwebhookconfigurations governance-hub-mutator
```

### Monitor API Health

```bash
# Port-forward to the service
kubectl port-forward -n governance-hub-demo svc/governance-hub-app 5000:5000 &

# Check health
curl http://localhost:5000/health

# List policies
curl http://localhost:5000/api/v1/policies | jq .
```

---

## Modifying Validation Rules

To change validation behavior, edit the validator classes in `app/validators/` and rebuild:

```bash
# Edit the validator
nano ../app/validators/pod.py

# Rebuild the image
docker build -t governance-hub-app:latest -f ../Dockerfile ..

# Restart the pod
kubectl rollout restart deployment/governance-hub-app -n governance-hub-demo

# Wait for it to be ready
kubectl wait --for=condition=ready pod -l component=app -n governance-hub-demo --timeout=30s
```

---

## Advanced: Manual AdmissionReview Testing

If you want to test the webhook endpoints directly:

```bash
# Port-forward to nginx (HTTPS:443)
kubectl port-forward -n governance-hub-demo svc/governance-hub-nginx 8443:443 &

# Create an AdmissionReview payload
cat > admission-review.json <<EOF
{
  "apiVersion": "admission.k8s.io/v1",
  "kind": "AdmissionReview",
  "request": {
    "uid": "test-123",
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
            "image": "alpine:3.18"
          }
        ]
      }
    }
  }
}
EOF

# Test validation endpoint (should fail because no resource limits)
curl -k -X POST https://localhost:8443/api/v1/validate \
  -H "Content-Type: application/json" \
  -d @admission-review.json \
  -v | jq .

# Test mutation endpoint
curl -k -X POST https://localhost:8443/api/v1/mutate \
  -H "Content-Type: application/json" \
  -d @admission-review.json \
  -v | jq .
```

---

## Understanding the Mutation Patches

When mutators generate patches, they follow [RFC 6902 - JSON Patch](https://tools.ietf.org/html/rfc6902) format.

Common patch operations:
- `add` - Add a new field
- `replace` - Replace an existing field
- `remove` - Remove a field

Example patch (from base64 in webhook response):
```json
[
  {
    "op": "add",
    "path": "/metadata/labels/app.kubernetes.io~1managed-by",
    "value": "governance-hub-demo"
  },
  {
    "op": "add",
    "path": "/spec/containers/0/resources",
    "value": {
      "requests": {"cpu": "100m", "memory": "128Mi"},
      "limits": {"cpu": "100m", "memory": "128Mi"}
    }
  }
]
```

Note: The `~1` is the escaped form of `/` in JSON Patch paths (RFC 6901 JSON Pointer escaping).
