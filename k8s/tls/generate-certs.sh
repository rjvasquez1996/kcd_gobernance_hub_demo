#!/bin/bash

# Generate self-signed TLS certificates for admission webhooks
# This script creates a CA and server certificate for the governance-hub webhook service

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

echo "Generating TLS certificates for Kubernetes admission webhooks..."

# Certificate configuration
CN="governance-hub-nginx.governance-hub-demo.svc"
NAMESPACE="governance-hub-demo"
SERVICE_NAME="governance-hub-nginx"

# Cleanup old certificates
rm -f ca.key ca.crt server.key server.csr server.crt

echo ""
echo "1. Generating CA key and certificate..."
openssl genrsa -out ca.key 2048
openssl req -new -x509 -days 365 -key ca.key -out ca.crt \
  -subj "/CN=governance-hub-ca/O=MyOrg/C=US"

echo ""
echo "2. Generating server key and CSR..."
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
  -subj "/CN=${CN}/O=MyOrg/C=US"

echo ""
echo "3. Signing server certificate with CA..."

# Create a temporary extension file for the certificate
cat > /tmp/cert_ext.cnf << EOF
[v3_alt]
subjectAltName=DNS:${SERVICE_NAME},DNS:${SERVICE_NAME}.${NAMESPACE},DNS:${SERVICE_NAME}.${NAMESPACE}.svc
EOF

openssl x509 -req -days 365 \
  -in server.csr \
  -CA ca.crt \
  -CAkey ca.key \
  -CAcreateserial \
  -out server.crt \
  -extensions v3_alt \
  -extfile /tmp/cert_ext.cnf

# Clean up temporary file
rm -f /tmp/cert_ext.cnf

echo ""
echo "4. Creating Kubernetes secret..."
kubectl create secret generic governance-hub-tls \
  --from-file=server.crt=server.crt \
  --from-file=server.key=server.key \
  --namespace=${NAMESPACE} \
  --dry-run=client \
  -o yaml | kubectl apply -f -

echo ""
echo "5. Displaying CA certificate (base64) for webhook configuration..."
echo ""
echo "Save this value for caBundle in webhook configurations:"
echo ""
base64 < ca.crt | tr -d '\n'
echo ""
echo ""

echo "✓ TLS certificates generated successfully!"
echo ""
echo "Files created:"
echo "  - ca.key (CA private key)"
echo "  - ca.crt (CA certificate)"
echo "  - server.key (server private key)"
echo "  - server.crt (server certificate)"
echo "  - server.csr (certificate signing request, safe to delete)"
echo ""
echo "Kubernetes secret created: governance-hub-tls in namespace ${NAMESPACE}"
