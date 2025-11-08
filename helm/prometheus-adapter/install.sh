#!/bin/bash

# NATS JetStream installation script
set -e

# Set local dir
DIR=$(dirname "$0")
cd "$DIR" || exit 1

# Add prometheus-community helm repo if not already added
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
helm repo update

# Install Prometheus Adapter
echo "Installing Prometheus Adapter..."
helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
  --namespace monitoring \
  --values prometheus-adapter-values.yaml \
  --wait
  
echo "Prometheus Adapter installed successfully!"