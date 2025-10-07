#!/bin/bash

# NATS JetStream installation script
set -e

# Set local dir
DIR=$(dirname "$0")
cd "$DIR" || exit 1

echo "🚀 Installing NATS JetStream..."

# Add NATS Helm repository
echo "📦 Adding NATS Helm repository..."
helm repo add nats https://nats-io.github.io/k8s/helm/charts/
helm repo update

echo "📦 Installing NATS server with JetStream enabled..."
helm upgrade --install nats nats/nats \
  --namespace nats \
  --create-namespace \
  --values nats-values.yaml \
  --wait

echo "🔧 Installing NACK (NATS JetStream Controller)..."
helm upgrade --install nack nats/nack \
  --namespace nats \
  --set jetstream.nats.url=nats://nats.nats.svc.cluster.local:4222 \
  --wait

echo "🌐 Creating NATS monitoring Gateway HTTPRoute resource..."
kubectl apply -f httproute.yaml

echo "✅ NATS JetStream and NACK controller installed successfully!"
echo "📊 NATS monitoring available at: https://nats.gke.richardr.dev"
echo "🔍 Key monitoring endpoints:"
echo "  - https://nats.gke.richardr.dev/jsz (JetStream stats)"
echo "  - https://nats.gke.richardr.dev/varz (Server info)"
echo "  - https://nats.gke.richardr.dev/connz (Connections)"
echo ""