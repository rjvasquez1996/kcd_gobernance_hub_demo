# Deploy Governance Hub Using Helm Chart

This guide shows how to deploy using the Helm chart with the same local images you already have built.

## Prerequisites

✅ **Images Already Built Locally** (from previous deployment):
- `governance-hub-app:v1`
- `governance-hub-nginx:v1`

✅ **Minikube Running**:
```bash
minikube status
```

## 1. Generate TLS Certificates

```bash
cd k8s/tls
./generate-certs.sh
export CA_BUNDLE=$(base64 < ca.crt | tr -d '\n')
cd ../..
```

This generates:
- `ca.crt` - CA certificate
- `server.crt` - Server certificate
- `server.key` - Server key
- Creates Kubernetes secret: `governance-hub-tls`

## 2. Deploy with Helm

```bash
helm install governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

This will:
- Create namespace `governance-hub-demo`
- Deploy Flask app with image `governance-hub-app:v1`
- Deploy Nginx with image `governance-hub-nginx:v1`
- Configure webhooks with your CA certificate
- All using `imagePullPolicy: Never` for local images

## 3. Verify Deployment

```bash
# Check pods
kubectl get pods -n governance-hub-demo

# Expected output:
# governance-hub-app-xxx    1/1   Running
# governance-hub-nginx-xxx  1/1   Running

# Check webhooks registered
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# Check release
helm status governance-hub
```

## 4. Test the Webhooks

### Test Validators (should DENY):
```bash
# Try to create a privileged pod (should be denied)
kubectl run privileged-test --image=alpine \
  --overrides='{"spec": {"containers": [{"name": "test", "image": "alpine", "securityContext": {"privileged": true}}]}}'
```

Expected error: `admission webhook "validate.governance-hub-demo.svc" denied the request`

### Test Mutators (should INJECT):
```bash
# Create a pod without resources (mutator will add them)
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

# Check injected resources and labels
kubectl get pod test-mutation -o yaml | grep -A 5 "resources:"
kubectl get pod test-mutation -o yaml | grep -A 3 "labels:"
```

Expected: Pod has injected labels and resource limits.

## Chart Configuration

The Helm chart uses these defaults for local deployment:

```yaml
app:
  image:
    repository: governance-hub-app
    tag: "v1"
    pullPolicy: Never  # Local images
  replicaCount: 1

nginx:
  image:
    repository: governance-hub-nginx
    tag: "v1"
    pullPolicy: Never  # Local images
  replicaCount: 1
```

## Common Operations

### View what will be deployed (dry-run)
```bash
helm install governance-hub ./governance-hub-chart \
  --dry-run --debug \
  --set tls.caBundle="$CA_BUNDLE"
```

### See generated YAML
```bash
helm template governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

### Upgrade the deployment
```bash
helm upgrade governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

### Rollback to previous version
```bash
helm history governance-hub
helm rollback governance-hub 1  # Rollback to revision 1
```

### Check deployment history
```bash
helm history governance-hub
```

### Uninstall
```bash
helm uninstall governance-hub
# This will delete the namespace and all resources
```

## Customization Examples

### Scale to multiple replicas
```bash
helm upgrade governance-hub ./governance-hub-chart \
  --set app.replicaCount=3 \
  --set nginx.replicaCount=2 \
  --set tls.caBundle="$CA_BUNDLE"
```

### Change namespace
```bash
helm install governance-hub ./governance-hub-chart \
  --set global.namespace=my-custom-ns \
  --set tls.caBundle="$CA_BUNDLE"
```

### Custom resource limits
```bash
helm upgrade governance-hub ./governance-hub-chart \
  --set app.resources.requests.cpu=200m \
  --set app.resources.limits.cpu=1000m \
  --set tls.caBundle="$CA_BUNDLE"
```

### Adjust webhook timeout
```bash
helm upgrade governance-hub ./governance-hub-chart \
  --set webhooks.validating.timeoutSeconds=20 \
  --set tls.caBundle="$CA_BUNDLE"
```

## Troubleshooting

### Pods not starting?
```bash
kubectl get pods -n governance-hub-demo
kubectl describe pod <pod-name> -n governance-hub-demo
kubectl logs <pod-name> -n governance-hub-demo
```

### Webhooks not triggering?
```bash
# Check webhook configurations
kubectl describe validatingwebhookconfigurations governance-hub-demo-validator
kubectl describe mutatingwebhookconfigurations governance-hub-demo-mutator

# Verify CA bundle is set
kubectl get validatingwebhookconfigurations governance-hub-demo-validator -o yaml | grep caBundle
```

### Want to see what's deployed?
```bash
# List all resources created by Helm
helm get manifest governance-hub

# Or use kubectl
kubectl get all -n governance-hub-demo
```

## Comparison: Raw YAML vs Helm

### Before (Raw YAML)
```bash
# Had to apply 8 separate files
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/app-service.yaml
# ... and 5 more files
```

### After (Helm Chart)
```bash
# Single command to deploy everything
helm install governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

## Next Steps

✅ Chart deployed with local images
✅ Webhooks configured and active
✅ Ready to test validators and mutators

### Explore
- View full documentation: `governance-hub-chart/README.md`
- See all available values: `governance-hub-chart/values.yaml`
- Try production config: `governance-hub-chart/values-production.yaml`

### Extend
- Add webhook rules to `webhookRules` in values.yaml
- Enable/disable webhooks with `webhooks.validating.enabled`
- Adjust timeouts and policies as needed

---

For more details, see `governance-hub-chart/README.md`
