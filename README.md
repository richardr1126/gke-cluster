# GKE Cost-Optimized Cluster Manager

This script creates a Google Kubernetes Engine (GKE) cluster optimized for cost with the following specifications:

## Cluster Configuration

- **Cluster Type**: Single zonal cluster (cost-optimized)
- **Zone**: us-central1-b
- **Region**: us-central1
- **Default Node Pool**: t2d-standard-2 (2 vCPUs, 8GB RAM)
- **ML Node Pool**: n2d-highcpu-4 (4 vCPUs, 4GB RAM) with dedicated=ml:NoSchedule taint
- **Initial Node Count**: 3 nodes per pool
- **Instance Type**: Spot instances (preemptible) for 60-91% cost savings
- **Disk**: 20GB standard persistent disk for default pool, 50GB for ML pool
- **Network**: Private nodes (no external IPs, Cloud NAT for internet access)
- **ML Pool Autoscaling**: 0-6 nodes
- **Estimated Cost**: ~$40-67/month with spot instances

## Features

- ✅ Spot instances for maximum cost savings (60-91% off)
- ✅ Private nodes (no external IPs - saves on quota)
- ✅ Automatic Cloud NAT setup for internet access
- ✅ Dual node pools (default + ML-optimized)
- ✅ ML pool autoscaling (0-6 nodes)
- ✅ Workload Identity for secure GCP access
- ✅ Cost Management for cost allocation tracking
- ✅ Container-Optimized OS (COS_CONTAINERD)
- ✅ Managed Prometheus disabled to reduce costs
- ✅ Automatic PVC disk cleanup on cluster deletion

## Prerequisites

1. **Google Cloud SDK**: Install and authenticate
   ```bash
   # Install gcloud SDK
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   
   # Authenticate
   gcloud auth login
   gcloud auth application-default login
   
   # Set project
   gcloud config set project YOUR_PROJECT_ID
   ```

2. **Python Dependencies**: Install required packages
   ```bash
   # Install from pyproject.toml
   pip install -e .
   
   # Or install manually
   pip install google-cloud-container google-cloud-compute
   ```

3. **Enable APIs**: Make sure the following APIs are enabled
   ```bash
   gcloud services enable container.googleapis.com
   gcloud services enable compute.googleapis.com
   ```

## Usage

### Create a Cluster

```bash
# Create cluster with default name and spot instances
# This automatically creates Cloud NAT for internet access
python gke-cluster.py create

# Create cluster with custom name
python gke-cluster.py create --name my-cluster

# Create cluster without spot instances (more expensive but more reliable)
python gke-cluster.py create --no-spot
```

The script will:
1. Create the GKE cluster with private nodes
2. Automatically set up Cloud Router and Cloud NAT
3. Configure two node pools (default + ML)

### Scale a Cluster

```bash
# Scale all pools to 5 nodes each
python gke-cluster.py scale --name cost-optimized-cluster --nodes 5

# Scale down to 0 nodes (save money, only pay for control plane)
python gke-cluster.py scale --nodes 0

# Scale specific pool only
python gke-cluster.py scale --name cost-optimized-cluster --nodes 3 --pool ml-pool

# Scale default pool only
python gke-cluster.py scale --nodes 2 --pool default-pool
```

### List Clusters

```bash
python gke-cluster.py list
```

### Delete a Cluster

```bash
# Delete default cluster
# This automatically cleans up:
# - All PVC disks (persistent volumes)
# - The GKE cluster
# - Cloud NAT configuration
# - Cloud Router
python gke-cluster.py delete

# Delete specific cluster
python gke-cluster.py delete --name my-cluster
```

### Connect to Your Cluster

After creation, connect to your cluster:

```bash
# Connect to the cluster
gcloud container clusters get-credentials cost-optimized-cluster \
  --zone us-central1-b --project YOUR_PROJECT_ID

# Verify nodes
kubectl get nodes

# Check node pools
kubectl get nodes --show-labels | grep pool
```

## Node Pools

### Default Pool
- **Machine Type**: t2d-standard-2 (2 vCPUs, 8GB RAM)
- **Purpose**: General workloads
- **Disk**: 20GB standard persistent disk
- **Autoscaling**: Manual (use scale command)

### ML Pool
- **Machine Type**: n2d-highcpu-4 (4 vCPUs, 4GB RAM)
- **Purpose**: ML inference workloads (optimized for ONNX INT8 models)
- **Disk**: 50GB standard persistent disk
- **Taint**: `dedicated=ml:NoSchedule`
- **Autoscaling**: Enabled (0-6 nodes)

To deploy to ML pool, add toleration and node selector:
```yaml
tolerations:
- key: "dedicated"
  operator: "Equal"
  value: "ml"
  effect: "NoSchedule"
nodeSelector:
  cloud.google.com/gke-nodepool: ml-pool
```

## Private Nodes & Cloud NAT

The cluster uses **private nodes** to save on external IP quota:

- **Private Nodes**: Nodes only have private IPs (no external IPs)
- **Cloud NAT**: Provides outbound internet access for:
  - Pulling container images
  - Accessing external APIs
  - Downloading packages
- **Security**: Nodes are unreachable from the internet
- **Cost**: Adds ~$1-5/month for NAT

**Benefits:**
- ✅ No external IP quota needed (only LoadBalancer needs 1 external IP)
- ✅ Reduced attack surface
- ✅ All outbound traffic through NAT gateway
- ✅ Can scale to 9 nodes without external IP quota issues

## Cost Optimization Features

### Spot Instances
- **Savings**: 60-91% off regular instance prices
- **Trade-off**: Can be terminated with 30-second notice
- **Best for**: Development, testing, fault-tolerant workloads

### Machine Type Selection
- **Default Pool (t2d-standard-2)**: 2 vCPUs, 8GB RAM
- **ML Pool (n2d-highcpu-4)**: 4 vCPUs, 4GB RAM (compute-optimized)
- **Total capacity**: 18 vCPUs, 48GB RAM at full scale (3+6 nodes)

### Storage Optimization
- **Standard Persistent Disk**: Cheapest disk option
- **Sizes**: 20GB default, 50GB for ML nodes
- **Performance**: Suitable for most development workloads

### Automatic Cleanup
- **PVC Disks**: Automatically deleted with cluster
- **Cloud NAT**: Automatically removed with cluster
- **No Orphaned Resources**: All resources cleaned up on delete

## Important Notes

### Private Nodes
- Nodes do not have external IPs
- Internet access provided via Cloud NAT
- LoadBalancer services still work (get external IP)
- Only 1 external IP needed for entire cluster

### Monitoring Costs
The cluster enables cost management to help track costs:
- Monitor usage in the Google Cloud Console
- Set up billing alerts for cost control
- Review the GKE usage metering data

### Scaling
```bash
# Scale all pools
python gke-cluster.py scale --nodes 5

# Scale specific pool
python gke-cluster.py scale --nodes 3 --pool ml-pool

# Scale to 0 to minimize costs
python gke-cluster.py scale --nodes 0

# ML pool autoscales automatically (0-6 nodes)
# based on workload demand
```

## Troubleshooting

### Authentication Issues
```bash
gcloud auth application-default login
gcloud config set project YOUR_PROJECT_ID
```

### API Not Enabled
```bash
gcloud services enable container.googleapis.com compute.googleapis.com
```

## Security Best Practices

The script includes several security optimizations:
- Private nodes (no direct internet access to nodes)
- Cloud NAT for controlled outbound access
- Workload Identity for secure service access
- Container-Optimized OS (COS_CONTAINERD)
- Uses GKE defaults for RBAC and security policies
- Latest Kubernetes version
- Cost management enabled for usage tracking

## Example Workflow

```bash
# 1. Create the cluster (includes Cloud NAT setup)
python gke-cluster.py create

# 2. Connect to the cluster
gcloud container clusters get-credentials cost-optimized-cluster \
  --zone us-central1-b

# 3. Deploy a simple application
kubectl create deployment hello-world --image=gcr.io/google-samples/hello-app:1.0

# 6. Clean up when done (automatically removes PVCs and Cloud NAT)
python gke-cluster.py delete
```

## Cost Estimation

**Monthly costs (approximate, spot instances):**
- Default Pool (3 x t2d-standard-2): ~$20-33
- ML Pool (3 x n2d-highcpu-4): ~$15-25
- Persistent Disk (100GB standard): ~$4
- Cloud NAT: ~$1-5
- **Total: ~$40-67/month**

**Cost when scaled to 0 nodes:**
- Control plane: Free (single zonal cluster)
- Cloud NAT: ~$1/month (minimal with no traffic)
- **Total: ~$1/month**

*Prices may vary by region and are subject to change. Spot instance pricing is typically 60-91% less than regular instances.*

### Private Cluster Architecture
```
┌─────────────────────────────────────────┐
│  Internet                               │
└──────────────┬──────────────────────────┘
               │
        ┌──────▼──────┐
        │ LoadBalancer│ (1 external IP)
        └──────┬──────┘
               │
┌──────────────▼──────────────────────────┐
│  GKE Cluster (Private Nodes)            │
│  ┌──────────────┐  ┌──────────────┐    │
│  │ Default Pool │  │   ML Pool    │    │
│  │ (private IP) │  │ (private IP) │    │
│  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼────────────┘
          │                  │
          └────────┬─────────┘
                   │
            ┌──────▼──────┐
            │  Cloud NAT  │
            └──────┬──────┘
                   │
            ┌──────▼──────────────┐
            │ Internet (outbound) │
            └─────────────────────┘
```

### Key Advantages
- ✅ Only 1 external IP needed (for LoadBalancer)
- ✅ Nodes isolated from internet
- ✅ Controlled outbound access via NAT
- ✅ Can scale to 9 nodes without quota issues
- ✅ Automatic resource cleanup
- ✅ Cost-optimized with spot instances