# Governance Hub Helm Chart - Quick Start

## Overview

The Kubernetes YAML manifests have been converted to a Helm chart located in `governance-hub-chart/`.

### Chart Structure

```
governance-hub-chart/
├── Chart.yaml                    # Chart metadata
├── values.yaml                   # Default configuration
├── README.md                     # Detailed documentation
├── .helmignore                   # Files to exclude
└── templates/
    ├── _helpers.tpl              # Common Helm templates
    ├── namespace.yaml
    ├── app-deployment.yaml
    ├── app-service.yaml
    ├── nginx-configmap.yaml
    ├── nginx-deployment.yaml
    ├── nginx-service.yaml
    ├── validating-webhook.yaml
    └── mutating-webhook.yaml
```

## Installation Steps

### 1. Generate TLS Certificates

```bash
cd k8s/tls
./generate-certs.sh
export CA_BUNDLE=$(base64 < ca.crt | tr -d '\n')
cd ../..
```

### 2. Install with Helm

```bash
helm install governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

### 3. Verify Installation

```bash
# Check pods
kubectl get pods -n governance-hub-demo

# Check webhooks
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# Check deployment status
helm status governance-hub
```

## Common Operations

### Upgrade the Chart

```bash
helm upgrade governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

### Use Custom Values

```bash
helm install governance-hub ./governance-hub-chart \
  -f custom-values.yaml \
  --set tls.caBundle="$CA_BUNDLE"
```

Example `custom-values.yaml`:
```yaml
global:
  namespace: my-governance

app:
  replicaCount: 3
  image:
    tag: v2

nginx:
  replicaCount: 2
```

### Uninstall

```bash
helm uninstall governance-hub
```

### Dry Run (preview changes)

```bash
helm install governance-hub ./governance-hub-chart \
  --dry-run --debug \
  --set tls.caBundle="$CA_BUNDLE"
```

### View Generated YAML

```bash
helm template governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

## Key Configuration Values

All values from `values.yaml` can be overridden:

```bash
# Override image tags
--set app.image.tag=v2
--set nginx.image.tag=v2

# Scale replicas
--set app.replicaCount=3
--set nginx.replicaCount=2

# Change namespace
--set global.namespace=custom-namespace

# Customize nginx
--set nginx.config.workerConnections=2048
--set nginx.config.clientMaxBodySize=50M
```

## Comparison: Old vs New

### Before (Manual YAML)
```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/app-deployment.yaml
kubectl apply -f k8s/app-service.yaml
# ... repeat for all 8 YAML files
```

### After (Helm Chart)
```bash
helm install governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

## Benefits of Using Helm

✅ **Single Command Deployment**: Deploy everything with one command
✅ **Parameterized Configuration**: Override any value without editing files
✅ **Release Management**: Track and manage deployments with Helm
✅ **Easy Upgrades**: Update with `helm upgrade`
✅ **Version Control**: Chart.yaml tracks chart versions
✅ **Reusability**: Share chart across teams/environments
✅ **Built-in Validation**: `helm lint` catches errors
✅ **Dry-Run Preview**: Test before applying with `--dry-run`

## Troubleshooting

### Chart validation failed
```bash
helm lint governance-hub-chart/
```

### See what will be deployed
```bash
helm template governance-hub governance-hub-chart/ --set tls.caBundle="$CA_BUNDLE"
```

### Check Helm release status
```bash
helm status governance-hub
helm history governance-hub
```

### Rollback a deployment
```bash
helm rollback governance-hub 1  # Rollback to revision 1
```

## Next Steps

- Review `governance-hub-chart/README.md` for detailed documentation
- Customize `values.yaml` for your environment
- Consider publishing to a Helm repository
- Use `helm secrets` plugin for sensitive values (CA bundle, etc.)

## Charts vs Raw YAML

| Aspect | Raw YAML | Helm Chart |
|--------|----------|-----------|
| Deployment | Manual `kubectl apply` | Single `helm install` |
| Configuration | Edit files manually | Override with `--set` |
| Validation | Manual checks | `helm lint` |
| Upgrades | Manual YAML changes | `helm upgrade` |
| Version Control | Track all YAML files | Track Chart.yaml version |
| Reusability | Copy/paste files | Share chart |
| Parameterization | Limited | Full flexibility |

---

**Original Raw YAMLs**: Still in `k8s/` directory for reference
**Helm Chart**: In `governance-hub-chart/` directory
