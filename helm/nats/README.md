# NATS JetStream Configuration

This directory contains NATS JetStream configuration and examples for the GKE cluster.

## Files Structure
```
nats/
├── install.sh           # Installation script
├── nats-values.yaml     # NATS server Helm values
├── gateway.yaml         # Gateway configuration for monitoring
├── README.md           # This file
└── examples/           # Example JetStream resources
    ├── stream.yaml     # Stream examples
    ├── consumer.yaml   # Consumer examples
    └── keyvalue.yaml   # Key-Value store examples
```

## Installation

Run the installation script:
```bash
./install.sh
```

This will install:
- NATS server with JetStream enabled (3 replicas for HA)
- NACK (NATS JetStream Controller) for managing streams and consumers via Kubernetes CRDs
- Gateway route for monitoring at https://nats.gke.richardr.dev

## Configuration

### NATS Server (`nats-values.yaml`)
- **Clustering**: 3 replicas with topology spread constraints
- **JetStream**: File storage with 10Gi persistent volumes per instance
- **Resources**: 1 CPU / 2Gi RAM requests, 2 CPU / 4Gi RAM limits
- **Monitoring**: Port 8222 enabled
- **Memory Management**: GOMEMLIMIT set to ~80% of memory limit (3.4Gi)

You can customize these values files to adjust the configuration for your needs.

## Monitoring

Access the NATS monitoring dashboard at:
- **Web UI**: https://nats.gke.richardr.dev
- **JetStream Stats**: https://nats.gke.richardr.dev/jsz
- **Server Info**: https://nats.gke.richardr.dev/varz
- **Connections**: https://nats.gke.richardr.dev/connz

## Using NATS

### Connect with nats-box
```bash
kubectl exec -it deployment/nats-box -n nats -- nats --help
```

### Create a Stream
```bash
kubectl apply -f examples/stream.yaml
```

### Create a Consumer
```bash
kubectl apply -f examples/consumer.yaml
```

## Configuration

- **Storage**: 10Gi persistent storage per NATS server instance
- **Clustering**: 3 replicas for high availability
- **JetStream**: Enabled with file storage
- **Namespace**: `nats`