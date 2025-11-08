#!/bin/bash

# NATS JetStream installation script
set -e

# Set local dir
DIR=$(dirname "$0")
cd "$DIR" || exit 1

# Add prometheus-community helm repo if not already added
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo update

echo "🚀 Installing Prometheus Stack via Helm..."
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
  -f ./kube-prometheus-stack-values.yaml \
  --namespace monitoring \
  --create-namespace \
  --wait

echo "🌐 Configuring Grafana HTTPRoute..."
# Apply Grafana HTTPRoute
kubectl apply -f ./httproute.yaml

# Success
echo "✅ Prometheus Stack installed successfully!"