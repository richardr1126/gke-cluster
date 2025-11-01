#!/bin/bash

# Simple script to install cert-manager and NGINX Gateway Fabric via Helm
set -e

# Load environment variables from .env file
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
else
  echo ".env file not found! Please create one with CLOUDFLARE_API_TOKEN variable."
  exit 1
fi

echo "📦 Installing Gateway API CRDs (including experimental)..."
kubectl kustomize "https://github.com/nginx/nginx-gateway-fabric/config/crd/gateway-api/experimental?ref=v2.2.0" | kubectl apply -f -

# Install cert-manager from jetstack repository and enable Gateway API integration
helm upgrade --install \
  cert-manager oci://quay.io/jetstack/charts/cert-manager \
  --namespace cert-manager \
  --create-namespace \
  --version v1.18.2 \
  --set crds.enabled=true \
  --set "extraArgs={--enable-gateway-api}" \
  --wait

echo "🔄 Restarting cert-manager to ensure Gateway API CRDs are loaded..."
kubectl rollout restart deployment cert-manager -n cert-manager
kubectl rollout status deployment cert-manager -n cert-manager --timeout=5m

echo "🔐 Creating Cloudflare DNS secret for ExternalDNS..."
kubectl create secret generic cloudflare-dns \
  --namespace cert-manager \
  --from-literal=cloudflare_api_token=$CLOUDFLARE_API_TOKEN \
  --dry-run=client -o yaml | kubectl apply -f -

echo "🚀 Installing ExternalDNS via Helm..."
helm upgrade --install external-dns external-dns/external-dns --version 1.15.2 \
  --namespace cert-manager \
  --set provider=cloudflare \
  --set env[0].name=CF_API_TOKEN \
  --set env[0].valueFrom.secretKeyRef.name=cloudflare-dns \
  --set env[0].valueFrom.secretKeyRef.key=cloudflare_api_token \
  --set sources='{service,ingress,gateway-httproute,gateway-grpcroute,gateway-tlsroute}' \
  --wait

echo "🚀 Installing NGINX Gateway Fabric via Helm..."
helm upgrade --install ngf oci://ghcr.io/nginx/charts/nginx-gateway-fabric --create-namespace -n nginx-gateway \
  --set nginxGateway.resources.requests.cpu="100m" \
  --set nginxGateway.resources.requests.memory="128Mi" \
  --set nginxGateway.resources.limits.cpu="200m" \
  --set nginxGateway.resources.limits.memory="256Mi" \
  --set nginxGateway.gwAPIExperimentalFeatures.enable=true

echo "⏳ Waiting for NGINX Gateway Fabric to be ready..."
kubectl wait --timeout=5m -n nginx-gateway deployment/ngf-nginx-gateway-fabric --for=condition=Available

echo "🚪 Creating Gateway resource..."
kubectl apply -f - <<EOF
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: nginx
  namespace: nginx-gateway
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-staging
    external-dns.alpha.kubernetes.io/hostname: gke.richardr.dev
spec:
  gatewayClassName: nginx
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
        namespaces:
          from: All
  - name: https
    hostname: "*.gke.richardr.dev"
    protocol: HTTPS
    port: 443
    tls:
      mode: Terminate
      certificateRefs:
      - name: wildcard-gke-richardr-dev-tls
        kind: Secret
        group: ""
    allowedRoutes:
        namespaces:
          from: All
  - name: tls
    hostname: "cockroachdb.richardr.dev"
    protocol: TLS
    port: 443
    tls:
      mode: Passthrough
    allowedRoutes:
        namespaces:
          from: All
        kinds:
        - kind: TLSRoute
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: wildcard-gke-richardr-dev
  namespace: nginx-gateway
spec:
  secretName: wildcard-gke-richardr-dev-tls
  issuerRef:
    name: letsencrypt-staging
    kind: ClusterIssuer
  dnsNames:
  - "*.gke.richardr.dev"
EOF

echo "📋 Creating Let's Encrypt cluster issuer for Gateway API..."

# Create Let's Encrypt cluster issuers for Gateway API with DNS-01 solver for wildcard certificates
kubectl apply -f - <<EOF
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-staging
spec:
  acme:
    server: https://acme-staging-v02.api.letsencrypt.org/directory
    email: me@richardr.dev
    privateKeySecretRef:
      name: letsencrypt-staging
    solvers:
    - dns01:
        cloudflare:
          apiTokenSecretRef:
            name: cloudflare-dns
            key: cloudflare_api_token
      selector:
        dnsNames:
        - "*.gke.richardr.dev"
    - http01:
        gatewayHTTPRoute:
          parentRefs:
            - name: nginx
              namespace: nginx-gateway
              kind: Gateway
      selector:
        dnsNames:
        - "gke.richardr.dev"
---
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: me@richardr.dev
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - dns01:
        cloudflare:
          apiTokenSecretRef:
            name: cloudflare-dns
            key: cloudflare_api_token
      selector:
        dnsNames:
        - "*.gke.richardr.dev"
    - http01:
        gatewayHTTPRoute:
          parentRefs:
            - name: nginx
              namespace: nginx-gateway
              kind: Gateway
      selector:
        dnsNames:
        - "gke.richardr.dev"
EOF

echo "✅ cert-manager, NGINX Gateway Fabric, and cluster issuers installed successfully!"
echo ""

echo "Starting NATS JetStream installation script..."
./nats/install.sh

echo "Starting CockroachDB installation script..."
./cockroachdb/install.sh