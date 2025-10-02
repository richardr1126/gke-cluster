#!/bin/bash

# Simple script to install CockroachDB via Helm
set -e

echo "📦 Adding CockroachDB Helm repository..."
helm repo add cockroachdb https://charts.cockroachdb.com/
helm repo update

echo "🏗️ Creating CockroachDB namespace..."
kubectl create namespace cockroachdb --dry-run=client -o yaml | kubectl apply -f -

echo "🚀 Installing CockroachDB via Helm with TLS enabled..."
helm upgrade --install cockroachdb cockroachdb/cockroachdb \
  --namespace cockroachdb \
  --set tls.enabled=true \
  --set statefulset.replicas="3" \
  --set storage.persistentVolume.size="10Gi" \
  --set statefulset.resources.requests.cpu="250m" \
  --set statefulset.resources.requests.memory="512Mi" \
  --set statefulset.resources.limits.cpu="500m" \
  --set statefulset.resources.limits.memory="1Gi" \
  --wait

# Print instructions to connect to the database
echo "✅ CockroachDB installed successfully!"
