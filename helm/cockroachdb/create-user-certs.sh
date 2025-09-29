#!/bin/bash

# Script to create client certificates for CockroachDB applications
# IMPORTANT: Client certificates REPLACE passwords for authentication!
# When using certificates, NO PASSWORD is needed or used.
set -e

NAMESPACE="cockroachdb"
CERTS_DIR="./client-certs"
CA_SECRET="cockroachdb-ca-secret"
CLIENT_SECRET_NAME="cockroachdb-app-client-secret"
USERNAME="gke"  # Change this to your desired application user
CERT_POD_NAME="cockroachdb-cert-creator"

echo "🔧 Creating client certificates for CockroachDB applications..."
echo "ℹ️  Note: Client certificates REPLACE password authentication!"
echo "ℹ️  No password will be needed when using these certificates."

# Create local certs directory
mkdir -p "$CERTS_DIR"

echo "🔎 Cleaning up any existing cert creator pod..."
kubectl delete pod -n "$NAMESPACE" "$CERT_POD_NAME" --ignore-not-found=true --force
kubectl wait --for=delete pod/"$CERT_POD_NAME" -n "$NAMESPACE" --timeout=60s 2>/dev/null || true

echo "🚀 Creating certificate creator pod..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: $CERT_POD_NAME
  namespace: $NAMESPACE
spec:
  restartPolicy: Never
  containers:
  - name: cockroach-cert-creator
    image: cockroachdb/cockroach:latest
    command: ["sleep", "3600"]
    volumeMounts:
    - name: ca-secret
      mountPath: /ca-certs
      readOnly: true
    - name: temp-certs
      mountPath: /tmp/certs
  volumes:
  - name: ca-secret
    secret:
      secretName: $CA_SECRET
  - name: temp-certs
    emptyDir: {}
EOF

echo "⏳ Waiting for cert creator pod to be ready..."
kubectl wait --for=condition=Ready pod/"$CERT_POD_NAME" -n "$NAMESPACE" --timeout=120s

echo "🔑 Creating client certificate for user: $USERNAME"

# Create the certificate inside the pod
kubectl exec -n "$NAMESPACE" "$CERT_POD_NAME" -- /bin/bash -c "
    set -e
    echo 'Setting up certificate directory...'
    cp /ca-certs/ca.crt /tmp/certs/
    
    echo 'Creating client certificate for user: $USERNAME'
    ./cockroach cert create-client '$USERNAME' \
        --certs-dir=/tmp/certs \
        --ca-key=/ca-certs/ca.key \
        --lifetime=43796h
    
    echo 'Certificate created successfully!'
    ls -la /tmp/certs/
"

echo "📥 Copying certificates from pod to local machine..."

# Copy certificates from pod to local machine
kubectl cp "$NAMESPACE/$CERT_POD_NAME:/tmp/certs/ca.crt" "$CERTS_DIR/ca.crt"
kubectl cp "$NAMESPACE/$CERT_POD_NAME:/tmp/certs/client.$USERNAME.crt" "$CERTS_DIR/client.$USERNAME.crt"
kubectl cp "$NAMESPACE/$CERT_POD_NAME:/tmp/certs/client.$USERNAME.key" "$CERTS_DIR/client.$USERNAME.key"

echo "✅ Client certificate created successfully!"

# List the created certificates
echo "📋 Certificate files created:"
ls -la "$CERTS_DIR"

echo "🔐 Creating Kubernetes secret for application client certificates..."

# Delete existing secret if it exists
kubectl delete secret "$CLIENT_SECRET_NAME" -n "$NAMESPACE" --ignore-not-found=true

# Create new secret with client certificates
kubectl create secret generic "$CLIENT_SECRET_NAME" -n "$NAMESPACE" \
    --from-file=ca.crt="$CERTS_DIR/ca.crt" \
    --from-file=tls.crt="$CERTS_DIR/client.$USERNAME.crt" \
    --from-file=tls.key="$CERTS_DIR/client.$USERNAME.key"

echo "✅ Kubernetes secret '$CLIENT_SECRET_NAME' created successfully!"

echo "🧹 Cleaning up cert creator pod..."
kubectl delete pod -n "$NAMESPACE" "$CERT_POD_NAME" --ignore-not-found=true

echo "📝 To use these certificates in your application pods, mount the secret like this:"
echo ""
echo "volumes:"
echo "- name: client-certs"
echo "  secret:"
echo "    secretName: $CLIENT_SECRET_NAME"
echo "    defaultMode: 0400"
echo ""
echo "volumeMounts:"
echo "- name: client-certs"
echo "  mountPath: /cockroach-certs"
echo "  readOnly: true"
echo ""
echo "🔗 SQLAlchemy connection string example (NO PASSWORD NEEDED):"
echo "postgresql://$USERNAME@cockroachdb-public:26257/gkedb?sslmode=require&sslcert=/cockroach-certs/tls.crt&sslkey=/cockroach-certs/tls.key&sslrootcert=/cockroach-certs/ca.crt"
echo ""
echo "🔐 Authentication Method: CERTIFICATE-BASED (not password-based)"
echo "✅ The certificate with CN=$USERNAME authenticates the user"
echo "✅ No password is required or used with certificate authentication"

echo ""
echo "🎉 Client certificate setup complete!"
echo "💡 Remember to use the '$USERNAME' user when connecting to the database."
echo "🔒 The certificates are valid for 10 years by default."