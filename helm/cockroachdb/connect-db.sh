#!/bin/bash
set -e

NAMESPACE="cockroachdb"
POD_NAME="cockroachdb-client-secure"
DB_SERVICE="cockroachdb-public"
CERTS_DIR="./cockroach-certs"

echo "🔎 Cleaning up previous client pod..."
kubectl delete pod -n "$NAMESPACE" "$POD_NAME" --ignore-not-found=true --force
kubectl wait --for=delete pod/"$POD_NAME" -n "$NAMESPACE" --timeout=60s

echo "🚀 Creating CockroachDB secure client pod..."
kubectl create -f client-secure.yaml -n "$NAMESPACE"

echo "⏳ Waiting for pod to be ready..."
kubectl wait --for=condition=Ready pod/"$POD_NAME" -n "$NAMESPACE" --timeout=120s

echo "💻 Opening SQL shell in pod..."
kubectl exec -it -n "$NAMESPACE" "$POD_NAME" \
  -- ./cockroach sql \
  --certs-dir="$CERTS_DIR" \
  --host="$DB_SERVICE"
