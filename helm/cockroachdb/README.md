# CockroachDB Configuration

This directory contains CockroachDB installation and configuration scripts for the GKE cluster.

## Files Structure
```
cockroachdb/
├── install.sh               # Main installation script
├── create-user-certs.sh    # Client certificate generation
├── connect-db.sh           # Database connection helper
├── client-secure.yaml      # Secure client pod template
├── tlsroute.yaml           # TLSRoute for external UI access
└── client-certs/          # Generated client certificates (gitignored)
    ├── ca.crt             # Certificate Authority
    ├── client.gke.crt     # Client certificate for 'gke' user
    └── client.gke.key     # Client private key
```

## Installation

Run the installation script to deploy CockroachDB with TLS enabled:

```bash
./install.sh
```

This will install:
- CockroachDB cluster (3 replicas) with TLS enabled
- 10Gi persistent storage per node
- Resource-optimized configuration for the GKE cluster

## Configuration

### Cluster Specifications
- **Replicas**: 3 nodes for high availability
- **Storage**: 10Gi persistent volumes per node
- **Resources**: 
  - Requests: 500m CPU, 1.5Gi RAM
  - Limits: 1 CPU, 4Gi RAM
- **TLS**: Enabled with automatic certificate management
- **Namespace**: `cockroachdb`

## Client Certificate Authentication

CockroachDB uses client certificates for authentication (no passwords required).

### Generate Client Certificates

Create client certificates for application access:

```bash
./create-user-certs.sh
```

This script:
1. Creates a certificate generation pod
2. Generates client certificates for the `gke` user
3. Stores certificates locally in `client-certs/`
4. Creates a Kubernetes secret `cockroachdb-app-client-secret`
5. Cleans up the temporary pod

**Important**: Client certificates completely replace password authentication. When using certificates, no password is needed.

## External Access

### CockroachDB UI

The CockroachDB Admin UI is accessible externally via TLS passthrough:

**URL**: https://cockroachdb.richardr.dev

The `tlsroute.yaml` configures a Gateway API TLSRoute that:
- Routes traffic from the NGINX Gateway to CockroachDB UI (port 8080)
- Uses TLS passthrough to forward encrypted traffic directly
- Managed by external-dns for automatic DNS configuration

To apply or update the TLSRoute:

```bash
kubectl apply -f tlsroute.yaml
```

### Connect to Database

Use the connection script to open an interactive SQL shell:

```bash
./connect-db.sh
```

This creates a secure client pod and opens a SQL connection using the root certificates.

## Application Integration

### Using Client Certificates in Pods

Mount the client certificate secret in your application pods:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: your-app
spec:
  template:
    spec:
      containers:
      - name: app
        image: your-app:latest
        volumeMounts:
        - name: client-certs
          mountPath: /cockroach-certs
          readOnly: true
      volumes:
      - name: client-certs
        secret:
          secretName: cockroachdb-app-client-secret
          defaultMode: 0400
```

### Connection String Examples

#### SQLAlchemy (Python)
```python
# Certificate-based authentication (NO PASSWORD)
connection_string = (
    "postgresql://gke@cockroachdb-public.cockroachdb.svc.cluster.local:26257/gkedb"
    "?sslmode=require"
    "&sslcert=/cockroach-certs/tls.crt"
    "&sslkey=/cockroach-certs/tls.key"
    "&sslrootcert=/cockroach-certs/ca.crt"
)
```

#### Environment Variables
```bash
COCKROACH_URL="postgresql://gke@cockroachdb-public.cockroachdb.svc.cluster.local:26257/gkedb?sslmode=require&sslcert=/cockroach-certs/tls.crt&sslkey=/cockroach-certs/tls.key&sslrootcert=/cockroach-certs/ca.crt"
```

## Database Operations

### Connect to SQL Shell

```bash
# Using the connect script
./connect-db.sh

# Or manually with kubectl
kubectl exec -it deployment/cockroachdb-client-secure -n cockroachdb \
  -- ./cockroach sql --certs-dir=/cockroach-certs --host=cockroachdb-public
```

### Create Database and User

```sql
-- Create application database
CREATE DATABASE gkedb;

-- Create application user (matches certificate CN)
CREATE USER gke;

-- Grant permissions
GRANT ALL ON DATABASE gkedb TO gke;
```

### Basic SQL Operations

```sql
-- Show cluster status
SHOW CLUSTER SETTING version;

-- List databases
SHOW DATABASES;

-- List users
SELECT * FROM system.users;

-- Check cluster nodes
SELECT node_id, address, locality FROM crdb_internal.kv_node_status;
```

## Monitoring and Maintenance

### Check Cluster Health

```bash
# View pod status
kubectl get pods -n cockroachdb

# Check logs
kubectl logs -f statefulset/cockroachdb -n cockroachdb

# View cluster info
kubectl exec -it cockroachdb-0 -n cockroachdb \
  -- ./cockroach node status --certs-dir=/cockroach/cockroach-certs
```

### Scaling

CockroachDB supports horizontal scaling:

```bash
# Scale to 5 nodes
kubectl scale statefulset cockroachdb --replicas=5 -n cockroachdb

# Scale back to 3 nodes
kubectl scale statefulset cockroachdb --replicas=3 -n cockroachdb
```

## Security Best Practices

1. **TLS Everywhere**: All connections use TLS with certificate validation
2. **Certificate Authentication**: No passwords stored anywhere
3. **Network Policies**: Consider adding Kubernetes network policies
4. **Regular Cert Rotation**: Certificates are valid for 10 years by default
5. **Least Privilege**: Grant minimal required permissions to application users

## Troubleshooting

### Certificate Issues

```bash
# Check certificate validity
openssl x509 -in client-certs/client.gke.crt -text -noout

# Verify certificate matches user
kubectl exec -it cockroachdb-client-secure -n cockroachdb \
  -- ./cockroach auth-session login gke --certs-dir=/cockroach-certs --host=cockroachdb-public
```

### Connection Problems

```bash
# Test connectivity
kubectl exec -it cockroachdb-client-secure -n cockroachdb \
  -- ./cockroach sql --certs-dir=/cockroach-certs --host=cockroachdb-public --execute="SELECT 1;"

# Check service endpoints
kubectl get endpoints cockroachdb-public -n cockroachdb
```

### Storage Issues

```bash
# Check persistent volume claims
kubectl get pvc -n cockroachdb

# View storage usage
kubectl exec -it cockroachdb-0 -n cockroachdb \
  -- df -h /cockroach/cockroach-data
```

## Cost Optimization

- **Storage**: Uses standard persistent disks (10Gi per node)
- **Compute**: Optimized resource requests/limits for cost efficiency
- **High Availability**: 3-node cluster balances availability and cost
- **Spot Instances**: Compatible with spot instance nodes (with proper restart handling)

## Integration with NATS

CockroachDB works well with NATS JetStream for event-driven architectures:

1. **Transactional Outbox**: Store events in CockroachDB, publish to NATS
2. **Change Data Capture**: Use CockroachDB changefeeds with NATS
3. **Event Sourcing**: Store event streams in CockroachDB, replay via NATS

For more information, see the [CockroachDB documentation](https://www.cockroachlabs.com/docs/).