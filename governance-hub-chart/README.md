# Governance Hub Helm Chart

A Helm chart for deploying the Governance Hub, a Kubernetes admission webhook service for policy validation and resource mutation.

## Prerequisites

- Kubernetes 1.20+
- Helm 3.0+
- Docker images for the app and nginx (built and available in your cluster/registry)

## Installation

### 1. Generate TLS Certificates

First, generate the TLS certificates and CA bundle:

```bash
cd ./k8s/tls
./generate-certs.sh
export CA_BUNDLE=$(base64 < ca.crt | tr -d '\n')
cd ../..
```

### 2. Install the Chart

```bash
helm install governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

Or with custom values:

```bash
helm install governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE" \
  --set app.image.tag=v1 \
  --set nginx.image.tag=v1 \
  --values custom-values.yaml
```

### 3. Verify Installation

```bash
# Check the deployment
kubectl get deployment -n governance-hub-demo

# Check webhook configurations
kubectl get validatingwebhookconfigurations
kubectl get mutatingwebhookconfigurations

# Check pods
kubectl get pods -n governance-hub-demo
```

## Configuration

### Key Values

| Parameter | Description | Default |
|-----------|-------------|---------|
| `global.namespace` | Kubernetes namespace | `governance-hub-demo` |
| `app.image.repository` | Flask app image repository | `governance-hub-app` |
| `app.image.tag` | Flask app image tag | `v1` |
| `app.replicaCount` | Number of app replicas | `1` |
| `nginx.image.repository` | Nginx image repository | `governance-hub-nginx` |
| `nginx.image.tag` | Nginx image tag | `v1` |
| `nginx.replicaCount` | Number of nginx replicas | `1` |
| `tls.secretName` | TLS secret name | `governance-hub-tls` |
| `tls.caBundle` | CA certificate bundle (required) | `""` |
| `webhooks.validating.enabled` | Enable validating webhooks | `true` |
| `webhooks.mutating.enabled` | Enable mutating webhooks | `true` |

### Custom Values File Example

```yaml
global:
  namespace: custom-namespace

app:
  replicaCount: 2
  image:
    tag: custom-v1

nginx:
  replicaCount: 2
  config:
    workerConnections: 2048
```

## Upgrade

```bash
helm upgrade governance-hub ./governance-hub-chart \
  --set tls.caBundle="$CA_BUNDLE"
```

## Uninstall

```bash
helm uninstall governance-hub
```

## Webhooks

### Validating Webhook

The validating webhook enforces policies:
- `ForbidPrivilegedMode` — Blocks privileged containers and privilege escalation
- `RequireResourceLimits` — Requires CPU and memory limits on all containers
- `ForbidLatestTag` — Blocks `:latest` or untagged images
- `NoDirectNamespaceCreation` — Blocks direct namespace CREATE operations
- `RequiredLabelsCheck` — Requires `team` and `environment` labels on namespaces
- `IngressTLSRequired` — Requires TLS on all Ingress resources
- `IngressRuleLimit` — Limits number of rules per Ingress (default: 5)

Each validator can be enabled/disabled individually via `policies.validators` in `values.yaml`.

### Mutating Webhook

The mutating webhook automatically modifies resources:
- `CommonLabelsMutator` — Injects governance labels on pods
- `DefaultResourcesMutator` — Adds default resource requests/limits (100m CPU, 128Mi memory)
- `RemoveKubectlAnnotationMutator` — Removes `kubectl.kubernetes.io/last-applied-configuration` from namespaces
- `IngressClassDefaultMutator` — Sets `ingressClassName: nginx` if not specified

Each mutator can be enabled/disabled individually via `policies.mutators` in `values.yaml`.

## Customizing Webhooks

Edit `values.yaml` to customize webhook behavior:

```yaml
webhooks:
  validating:
    enabled: true
    failurePolicy: Fail  # or "Ignore"
    timeoutSeconds: 10

webhookRules:
  resources:
    - pods
    - deployments
    # Add more resources as needed
```

## Troubleshooting

### Webhooks not triggering

1. Check webhook configurations:
   ```bash
   kubectl describe validatingwebhookconfigurations governance-hub-demo-validator
   kubectl describe mutatingwebhookconfigurations governance-hub-demo-mutator
   ```

2. Verify CA bundle is set correctly:
   ```bash
   kubectl get validatingwebhookconfigurations governance-hub-demo-validator -o yaml
   ```

3. Check pod logs:
   ```bash
   kubectl logs -n governance-hub-demo -l component=app
   kubectl logs -n governance-hub-demo -l component=nginx
   ```

### TLS Errors

1. Regenerate certificates:
   ```bash
   cd k8s/tls && rm -f *.key *.crt *.csr && ./generate-certs.sh
   ```

2. Update CA bundle in values and reinstall:
   ```bash
   export CA_BUNDLE=$(base64 < k8s/tls/ca.crt | tr -d '\n')
   helm upgrade governance-hub ./governance-hub-chart --set tls.caBundle="$CA_BUNDLE"
   ```

## Chart Structure

```
governance-hub-chart/
├── Chart.yaml                    # Chart metadata
├── values.yaml                   # Default configuration
├── README.md                     # This file
└── templates/
    ├── _helpers.tpl              # Helper templates
    ├── namespace.yaml            # Namespace resource
    ├── app-deployment.yaml       # Flask app deployment
    ├── app-service.yaml          # Flask app service
    ├── nginx-configmap.yaml      # Nginx configuration
    ├── nginx-deployment.yaml     # Nginx deployment
    ├── nginx-service.yaml        # Nginx service
    ├── validating-webhook.yaml   # Validating webhook config
    └── mutating-webhook.yaml     # Mutating webhook config
```

## Notes

- The chart defaults to `imagePullPolicy: Never` suitable for Minikube. For production, change to `IfNotPresent` or `Always` and use a proper registry.
- TLS certificates must be manually generated and the CA bundle provided during installation.
- The chart creates a new namespace by default; set `global.namespace` to deploy to an existing namespace.
