# GKE Cost-Optimized Cluster Manager

This script creates a Google Kubernetes Engine (GKE) cluster optimized for cost with the following specifications:

## Cluster Configuration

- **Cluster Type**: Single zonal cluster (cost-optimized)
- **Zone**: us-central1-b
- **Machine Type**: e2-standard-2 (2 vCPUs, 8GB RAM) - cheapest option with 8GB RAM
- **Initial Node Count**: 0 nodes (scale up as needed)
- **Instance Type**: Spot instances (preemptible) for 60-91% cost savings
- **Disk**: 20GB standard persistent disk per node
- **Scaling**: Manual scaling from 0-N nodes
- **Estimated Cost**: $0 when scaled to 0 nodes, ~$17-27/month when scaled to 3 nodes

## Features

- ✅ Spot instances for maximum cost savings
- ✅ Manual scaling (0-N nodes) for precise cost control
- ✅ Workload Identity for secure GCP access
- ✅ Cost Management for cost allocation tracking
- ✅ Container-Optimized OS (COS_CONTAINERD) for better performance
- ✅ Managed Prometheus disabled to reduce costs
- ✅ Starts with 0 nodes to minimize initial costs

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
   pip install google-cloud-container google-auth
   ```

3. **Enable APIs**: Make sure the following APIs are enabled
   ```bash
   gcloud services enable container.googleapis.com
   gcloud services enable compute.googleapis.com
   ```

## Usage

### Create a Cluster

```bash
# Create cluster with default name and spot instances (starts with 0 nodes)
python gke-cluster.py create

# Create cluster with custom name
python gke-cluster.py create --name my-cluster

# Create cluster without spot instances (more expensive but more reliable)
python gke-cluster.py create --no-spot
```

### Scale a Cluster

```bash
# Scale up to 3 nodes
python gke-cluster.py scale --name cost-optimized-cluster --nodes 3

# Scale down to 0 nodes (save money)
python gke-cluster.py scale --nodes 0

# Scale specific cluster
python gke-cluster.py scale --name my-cluster --nodes 2
```

### List Clusters

```bash
python gke-cluster.py list
```

### Delete a Cluster

```bash
# Delete default cluster
python gke-cluster.py delete

# Delete specific cluster
python gke-cluster.py delete --name my-cluster
```

### Connect to Your Cluster

After creation and scaling up, connect to your cluster:

```bash
# First, scale up your cluster if it has 0 nodes
python gke-cluster.py scale --nodes 3

# Then connect to it
gcloud container clusters get-credentials cost-optimized-cluster --zone us-central1-b
kubectl get nodes
```

## Cost Optimization Features

### Spot Instances
- **Savings**: 60-91% off regular instance prices
- **Trade-off**: Can be terminated with 30-second notice
- **Best for**: Development, testing, fault-tolerant workloads

### Machine Type Selection
- **e2-standard-2**: Cheapest option with 8GB RAM
- **Resources**: 2 vCPUs, 8GB RAM per node
- **Total cluster**: 6 vCPUs, 24GB RAM across 3 nodes

### Storage Optimization
- **Standard Persistent Disk**: Cheapest disk option
- **Size**: 20GB per node (minimum recommended)
- **Performance**: Suitable for most development workloads

## Important Notes

### Spot Instance Considerations
- Spot instances can be terminated at any time
- Your workloads should be designed to handle interruptions
- Use for development, testing, or fault-tolerant applications
- Consider using regular instances for production workloads

### Monitoring Costs
The cluster enables resource usage export to help track costs:
- Monitor usage in the Google Cloud Console
- Set up billing alerts for cost control
- Review the GKE usage metering data

### Scaling
The cluster uses manual node scaling for precise cost control:
```bash
# Scale cluster nodes up
python gke-cluster.py scale --nodes 3

# Scale cluster nodes down to save money
python gke-cluster.py scale --nodes 0

# Scale application replicas (after nodes are available)
kubectl scale deployment your-app --replicas=5
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

### Insufficient Quota
Check your project quotas in the Google Cloud Console under IAM & Admin > Quotas.

### Cluster Creation Fails
- Check project permissions
- Verify zone availability
- Ensure sufficient quota for e2-standard-2 instances

## Security Best Practices

The script includes several security optimizations:
- Workload Identity for secure service access
- Container-Optimized OS (COS_CONTAINERD) for better security
- Uses GKE defaults for RBAC and security policies
- Latest Kubernetes version
- Cost management enabled for usage tracking

## Example Workflow

```bash
# 1. Create the cluster (starts with 0 nodes)
python gke-cluster.py create

# 2. Scale up the cluster to have nodes
python gke-cluster.py scale --nodes 3

# 3. Connect to the cluster
gcloud container clusters get-credentials cost-optimized-cluster --zone us-central1-b

# 4. Deploy a simple application
kubectl create deployment hello-world --image=gcr.io/google-samples/hello-app:1.0
kubectl expose deployment hello-world --type=LoadBalancer --port=8080

# 5. Check the deployment
kubectl get pods
kubectl get services

# 6. Clean up when done
kubectl delete service hello-world
kubectl delete deployment hello-world
# Scale down to save money, or delete entirely
python gke-cluster.py scale --nodes 0  # Just scale down
# OR
python gke-cluster.py delete  # Delete completely
```

## Cost Estimation

**Monthly costs (approximate, spot instances):**
- 3 x e2-standard-2 spot nodes: $15-25
- 60GB standard persistent disk: $2.40
- Load balancer (if used): $18-20
- **Total: ~$17-47/month**

*Prices may vary by region and are subject to change. Spot instance pricing is typically 60-91% less than regular instances.*