#!/usr/bin/env python3

import argparse
import os
import time
import sys
from pprint import pprint

import google.auth
from google.cloud import container_v1

# Get default credentials and project
try:
    credentials, project = google.auth.default()
except Exception as e:
    print("❌ Error: Could not get default credentials.")
    print("Make sure you have run 'gcloud auth application-default login'")
    sys.exit(1)

# Initialize the GKE client
cluster_manager_client = container_v1.ClusterManagerClient(credentials=credentials)

# Configuration
DEFAULT_CLUSTER_NAME = "cost-optimized-cluster"
ZONE = "us-central1-b"  # Single zone for cost optimization
MACHINE_TYPE = "t2d-standard-2"  # Ultra-low-cost machine (2 vCPUs, 8GB RAM)
MACHINE_TYPE_ML = "n2d-highcpu-4"  # Compute-optimized for ML inference (4 vCPUs, 4GB RAM)
NODE_COUNT = 0  # Start with 0 nodes for cost optimization
DISK_SIZE_GB = 20  # Minimum disk size
DISK_SIZE_GB_ML = 80  # Larger disk for ML node pool
DISK_TYPE = "pd-standard"  # Standard persistent disk (cheapest)

def create_gke_cluster(cluster_name, enable_spot=True):
    """Create a GKE cluster with cost-optimized settings using mostly defaults.

    We keep only options that directly reduce cost:
    - Spot (preemptible) nodes
    - Small machine type and disk
    - Disable managed Prometheus (Managed Service for Prometheus)
    Everything else is left to GKE defaults to reduce complexity and drift.
    """
    try:
        print(f"Creating GKE cluster '{cluster_name}' in project '{project}'...")
        print(f"Zone: {ZONE}")
        print(f"Machine Type: {MACHINE_TYPE} (2 vCPUs, 8GB RAM)")
        print(f"Initial Node Count: {NODE_COUNT} (no autoscaling)")
        print(f"Spot Instances: {enable_spot}")
        print(f"Disk: {DISK_SIZE_GB}GB {DISK_TYPE}")
        
        # Configure a minimal node config with cost savers for default pool
        # Spot instances (preemptible) enabled by default
        node_config_default = container_v1.NodeConfig(
            machine_type=MACHINE_TYPE,
            disk_size_gb=DISK_SIZE_GB,
            disk_type=DISK_TYPE,
            spot=enable_spot,
            image_type="COS_CONTAINERD",
        )
        
        # Configure ML node config optimized for CPU inference (ONNX INT8 models)
        # n2d-highcpu-4: 4 vCPUs, 4GB RAM, AMD EPYC Rome for good INT8 performance
        node_config_ml = container_v1.NodeConfig(
            machine_type=MACHINE_TYPE_ML,
            disk_size_gb=DISK_SIZE_GB_ML,
            disk_type=DISK_TYPE,
            spot=enable_spot,
            taints=[
                container_v1.NodeTaint(
                    key="dedicated",
                    value="ml",
                    effect=container_v1.NodeTaint.Effect.NO_SCHEDULE,
                )
            ],
            image_type="COS_CONTAINERD",
        )
        
        # Configure default node pool with no autoscaling, starting with 0 nodes
        node_pool_default = container_v1.NodePool(
            name="default-pool",
            config=node_config_default,
            initial_node_count=0,
        )
        
        # Configure ML inference node pool optimized for DistilBERT sentiment analysis
        node_pool_ml = container_v1.NodePool(
            name="ml-pool",
            config=node_config_ml,
            initial_node_count=0,
        )
        
        # Configure the cluster.
        # Disable Managed Service for Prometheus to reduce cost.
        # Enable cost management for cost allocation tracking.
        # Enable workload identity for secure access to Google Cloud services.
        cluster = container_v1.Cluster(
            name=cluster_name,
            locations=[ZONE],
            node_pools=[node_pool_default, node_pool_ml],
            monitoring_config=container_v1.MonitoringConfig(
                managed_prometheus_config=container_v1.ManagedPrometheusConfig(
                    enabled=False
                )
            ),
            cost_management_config=container_v1.CostManagementConfig(
                enabled=True
            ),
            workload_identity_config=container_v1.WorkloadIdentityConfig(
                workload_pool=f"{project}.svc.id.goog"
            ),
        )
        
        # Create the cluster
        parent = f"projects/{project}/locations/{ZONE}"
        request = container_v1.CreateClusterRequest(
            parent=parent,
            cluster=cluster
        )
        
        print("\n🚀 Starting cluster creation...")
        operation = cluster_manager_client.create_cluster(request=request)
        
        # Wait for the operation to complete
        print("⏳ Waiting for cluster creation to complete...")
        print("This typically takes 3-5 minutes for a small cluster.")
        
        # Poll for operation completion
        operation_name = operation.name
        while True:
            op_request = container_v1.GetOperationRequest(
                name=f"projects/{project}/locations/{ZONE}/operations/{operation_name.split('/')[-1]}"
            )
            current_op = cluster_manager_client.get_operation(request=op_request)
            
            if current_op.status == container_v1.Operation.Status.DONE:
                print("✅ Cluster creation completed!")
                break
            elif current_op.status == container_v1.Operation.Status.ABORTING:
                print("❌ Cluster creation failed!")
                print(f"Error: {current_op.status_message}")
                return False
            else:
                print(f"Status: {current_op.status}")
                time.sleep(30)  # Check every 30 seconds
        
        # Get cluster info
        get_request = container_v1.GetClusterRequest(
            name=f"projects/{project}/locations/{ZONE}/clusters/{cluster_name}"
        )
        created_cluster = cluster_manager_client.get_cluster(request=get_request)
        
        print(f"\n🎉 Cluster '{cluster_name}' created successfully!")
        print(f"Cluster endpoint: {created_cluster.endpoint}")
        print(f"Cluster status: {created_cluster.status}")
        try:
            node_count = sum((p.initial_node_count or 0) for p in (created_cluster.node_pools or []))
            print(f"Node count (initial): {node_count}")
        except Exception:
            print("Node count: Unknown")
        print(f"\n✅ Enabled features:")
        print(f"   - Cost Management: Enabled for cost allocation tracking")
        print(f"   - Workload Identity: {project}.svc.id.goog")
        
        # Instructions for connecting
        print(f"\n📝 To add this cluster to your kubeconfig and connect:")
        print(f"╭─ Run this command ─────────────────────────────────────────────────╮")
        print(f"│ gcloud container clusters get-credentials {cluster_name} --zone {ZONE} --project {project}")
        print(f"╰────────────────────────────────────────────────────────────────────╯")
        print(f"\n📋 After running the command above, you can use:")
        print(f"   kubectl get nodes              # View cluster nodes")
        print(f"   kubectl get pods --all-namespaces  # View all pods")
        print(f"   kubectl cluster-info          # View cluster information")
        print(f"\n💡 Node scaling commands:")
        print(f"   python gke-cluster.py scale --name {cluster_name} --nodes 5  # Scale all pools to 5 nodes")
        print(f"   python gke-cluster.py scale --name {cluster_name} --nodes 5 --pool default-pool  # Scale specific pool")
        print(f"   python gke-cluster.py scale --name {cluster_name} --nodes 0  # Scale all pools to 0 (save money)")
        print(f"\n🔒 ML pool taint: dedicated=ml:NoSchedule (only workloads with matching toleration can run there)")
        
        # Cost estimation
        print(f"\n💰 Estimated monthly cost (spot instances):")
        print(f"   - default-pool (5 x t2d-standard-2 spot): ~$20-33/month")
        print(f"   - ml-pool (3 x n2d-highcpu-4 spot): ~$15-25/month")
        print(f"   - 100GB standard persistent disk: ~$4/month")
        print(f"   - Total estimated: ~$39-62/month")
        print(f"   Note: Spot instances can be terminated, but offer 60-91% cost savings!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating cluster: {e}")
        return False

def delete_cluster(cluster_name):
    """Delete a GKE cluster."""
    try:
        print(f"Deleting cluster '{cluster_name}'...")
        
        delete_request = container_v1.DeleteClusterRequest(
            name=f"projects/{project}/locations/{ZONE}/clusters/{cluster_name}"
        )
        
        operation = cluster_manager_client.delete_cluster(request=delete_request)
        
        print("⏳ Waiting for cluster deletion to complete...")
        operation_name = operation.name
        while True:
            op_request = container_v1.GetOperationRequest(
                name=f"projects/{project}/locations/{ZONE}/operations/{operation_name.split('/')[-1]}"
            )
            current_op = cluster_manager_client.get_operation(request=op_request)
            
            if current_op.status == container_v1.Operation.Status.DONE:
                print("✅ Cluster deleted successfully!")
                break
            elif current_op.status == container_v1.Operation.Status.ABORTING:
                print("❌ Cluster deletion failed!")
                print(f"Error: {current_op.status_message}")
                return False
            else:
                print(f"Status: {current_op.status}")
                time.sleep(30)
        
        return True
        
    except Exception as e:
        print(f"❌ Error deleting cluster: {e}")
        return False

def scale_cluster(cluster_name, target_node_count=0, pool_name=None):
    """Scale node pool(s) in a GKE cluster to the specified number of nodes.
    
    Args:
        cluster_name: Name of the cluster to scale
        target_node_count: Target number of nodes (default: 0 for cost optimization)
        pool_name: Specific node pool to scale (default: None for all pools)
    """
    try:
        print(f"Scaling cluster '{cluster_name}' to {target_node_count} nodes...")
        
        # First, get the cluster to see its current node pools
        get_request = container_v1.GetClusterRequest(
            name=f"projects/{project}/locations/{ZONE}/clusters/{cluster_name}"
        )
        
        try:
            cluster = cluster_manager_client.get_cluster(request=get_request)
        except Exception as e:
            print(f"❌ Error: Cluster '{cluster_name}' not found or inaccessible.")
            print(f"   Make sure the cluster exists and you have proper permissions.")
            return False
        
        if cluster.status != container_v1.Cluster.Status.RUNNING:
            print(f"❌ Error: Cluster is not in RUNNING state (current: {cluster.status})")
            return False
        
        # Filter node pools if a specific pool was requested
        pools_to_scale = cluster.node_pools
        if pool_name:
            pools_to_scale = [p for p in cluster.node_pools if p.name == pool_name]
            if not pools_to_scale:
                print(f"❌ Error: Node pool '{pool_name}' not found in cluster.")
                print(f"   Available pools: {', '.join([p.name for p in cluster.node_pools])}")
                return False
            print(f"Scaling specific node pool: {pool_name}")
        else:
            print(f"Scaling all {len(cluster.node_pools)} node pool(s)")
        
        print(f"Found {len(pools_to_scale)} node pool(s) to scale:")
        
        operations = []
        for node_pool in pools_to_scale:
            current_count = node_pool.initial_node_count
            print(f"  - {node_pool.name}: {current_count} nodes -> {target_node_count} nodes")
            
            # Create the scaling request
            scale_request = container_v1.SetNodePoolSizeRequest(
                name=f"projects/{project}/locations/{ZONE}/clusters/{cluster_name}/nodePools/{node_pool.name}",
                node_count=target_node_count
            )
            
            # Execute the scaling operation
            operation = cluster_manager_client.set_node_pool_size(request=scale_request)
            operations.append((operation, node_pool.name))
        
        # Wait for all operations to complete (concurrently)
        print("\n⏳ Waiting for all scaling operations to complete...")
        if target_node_count == 0:
            print("💡 Scaling to 0 will stop all compute costs but keep the cluster configuration.")
            print("   You can scale back up later with: python gke-cluster.py scale --name {cluster_name} --nodes 5")
        
        # Track operation status for all pools
        operation_status = {pool_name: {"done": False, "success": None} for _, pool_name in operations}
        
        # Poll all operations together
        while not all(status["done"] for status in operation_status.values()):
            for operation, pool_name in operations:
                if operation_status[pool_name]["done"]:
                    continue
                    
                operation_name = operation.name
                op_request = container_v1.GetOperationRequest(
                    name=f"projects/{project}/locations/{ZONE}/operations/{operation_name.split('/')[-1]}"
                )
                current_op = cluster_manager_client.get_operation(request=op_request)
                
                if current_op.status == container_v1.Operation.Status.DONE:
                    print(f"   ✅ Node pool '{pool_name}' scaled successfully!")
                    operation_status[pool_name]["done"] = True
                    operation_status[pool_name]["success"] = True
                elif current_op.status == container_v1.Operation.Status.ABORTING:
                    print(f"   ❌ Scaling failed for node pool '{pool_name}': {current_op.status_message}")
                    operation_status[pool_name]["done"] = True
                    operation_status[pool_name]["success"] = False
            
            # Sleep only if there are still operations in progress
            if not all(status["done"] for status in operation_status.values()):
                time.sleep(10)  # Check every 10 seconds for scaling operations
        
        all_success = all(status["success"] for status in operation_status.values())
        
        if all_success:
            pool_info = f" (pool: {pool_name})" if pool_name else " (all pools)"
            print(f"\n✅ Cluster '{cluster_name}' scaled successfully to {target_node_count} nodes{pool_info}!")
            if target_node_count == 0:
                if pool_name:
                    print(f"💰 Compute costs reduced for pool '{pool_name}'")
                    print(f"🔄 To scale back up: python gke-cluster.py scale --name {cluster_name} --nodes 5 --pool {pool_name}")
                else:
                    print("💰 Compute costs are now $0 (you only pay for the control plane if using multiple zones)")
                    print(f"🔄 To scale back up: python gke-cluster.py scale --name {cluster_name} --nodes 5")
            return True
        else:
            print(f"\n⚠️  Some scaling operations failed. Check the output above.")
            return False
        
    except Exception as e:
        print(f"❌ Error scaling cluster: {e}")
        return False

def list_clusters():
    """List all GKE clusters in the project."""
    try:
        print(f"Listing clusters in project '{project}', zone '{ZONE}':")
        
        parent = f"projects/{project}/locations/{ZONE}"
        request = container_v1.ListClustersRequest(parent=parent)
        
        response = cluster_manager_client.list_clusters(request=request)
        
        if not response.clusters:
            print("No clusters found.")
            return
        
        for cluster in response.clusters:
            node_count = sum(pool.initial_node_count for pool in cluster.node_pools)
            print(f"  - {cluster.name} ({cluster.status}) - {node_count} nodes")
            
    except Exception as e:
        print(f"❌ Error listing clusters: {e}")

def main():
    """Main function to handle cluster operations."""
    parser = argparse.ArgumentParser(
        description="Create and manage cost-optimized GKE clusters with spot instances"
    )
    parser.add_argument(
        "action",
        choices=["create", "delete", "list", "scale"],
        help="Action to perform: create cluster, delete cluster, list clusters, or scale cluster"
    )
    parser.add_argument(
        "--name",
        default=DEFAULT_CLUSTER_NAME,
        help=f"Name of the cluster (default: {DEFAULT_CLUSTER_NAME})"
    )
    parser.add_argument(
        "--no-spot",
        action="store_true",
        help="Disable spot instances (use regular instances instead)"
    )
    parser.add_argument(
        "--nodes",
        type=int,
        default=0,
        help="Number of nodes to scale to (default: 0 for cost optimization)"
    )
    parser.add_argument(
        "--pool",
        help="Specific node pool to scale (default: scale all pools)"
    )
    
    args = parser.parse_args()
    
    print("=== GKE Cost-Optimized Cluster Manager ===")
    print(f"Project: {project}")
    print(f"Zone: {ZONE}")
    
    if args.action == "create":
        enable_spot = not args.no_spot
        success = create_gke_cluster(args.name, enable_spot)
        if not success:
            sys.exit(1)
    elif args.action == "delete":
        success = delete_cluster(args.name)
        if not success:
            sys.exit(1)
    elif args.action == "list":
        list_clusters()
    elif args.action == "scale":
        success = scale_cluster(args.name, args.nodes, args.pool)
        if not success:
            sys.exit(1)

if __name__ == "__main__":
    main()