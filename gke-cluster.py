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
NODE_COUNT = 3  # Start with 3 nodes for cost optimization
ML_MAX_NODES = 6  # Max nodes for ML pool autoscaling
DISK_SIZE_GB = 20  # Minimum disk size
DISK_SIZE_GB_ML = 50  # Larger disk for ML node pool
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
        print(f"\n{'='*70}")
        print(f"🚀 Creating GKE Cluster: '{cluster_name}'")
        print(f"{'='*70}")
        print(f"\n📍 Cluster Configuration:")
        print(f"   Project: {project}")
        print(f"   Zone: {ZONE}")
        print(f"\n🖥️  Default Node Pool:")
        print(f"   Machine Type: {MACHINE_TYPE} (2 vCPUs, 8GB RAM)")
        print(f"   Initial Nodes: {NODE_COUNT}")
        print(f"   Spot Instances: {'✅ Enabled' if enable_spot else '❌ Disabled'}")
        print(f"   Disk: {DISK_SIZE_GB}GB {DISK_TYPE}")
        print(f"\n🤖 ML Node Pool:")
        print(f"   Machine Type: {MACHINE_TYPE_ML} (4 vCPUs, 4GB RAM)")
        print(f"   Initial Nodes: {NODE_COUNT}")
        print(f"   Autoscaling: 0-{ML_MAX_NODES} nodes")
        print(f"   Spot Instances: {'✅ Enabled' if enable_spot else '❌ Disabled'}")
        print(f"   Disk: {DISK_SIZE_GB_ML}GB {DISK_TYPE}")
        print(f"   Taint: dedicated=ml:NoSchedule")
        
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
            initial_node_count=NODE_COUNT,
        )
        
        # Configure ML inference node pool optimized for DistilBERT sentiment analysis
        # Enable autoscaling from 3 to 9 nodes for balanced performance and cost
        node_pool_ml = container_v1.NodePool(
            name="ml-pool",
            config=node_config_ml,
            initial_node_count=NODE_COUNT,
            autoscaling=container_v1.NodePoolAutoscaling(
                enabled=True,
                min_node_count=0,
                max_node_count=ML_MAX_NODES,
            ),
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
        
        print(f"\n{'='*70}")
        print("⚙️  Initiating cluster creation...")
        operation = cluster_manager_client.create_cluster(request=request)
        
        # Wait for the operation to complete
        print(f"\n⏳ Cluster creation in progress...")
        print(f"   ⏱️  Estimated time: 3-5 minutes")
        print(f"   Operation ID: {operation.name.split('/')[-1]}")
        
        # Poll for operation completion
        operation_name = operation.name
        status_dots = 0
        while True:
            op_request = container_v1.GetOperationRequest(
                name=f"projects/{project}/locations/{ZONE}/operations/{operation_name.split('/')[-1]}"
            )
            current_op = cluster_manager_client.get_operation(request=op_request)
            
            if current_op.status == container_v1.Operation.Status.DONE:
                print(f"\n{'='*70}")
                print("✅ Cluster creation completed successfully!")
                print(f"{'='*70}")
                break
            elif current_op.status == container_v1.Operation.Status.ABORTING:
                print(f"\n{'='*70}")
                print("❌ Cluster creation failed!")
                print(f"{'='*70}")
                print(f"Error: {current_op.status_message}")
                return False
            else:
                dots = '.' * (status_dots % 4)
                print(f"\r   {'🔄' if status_dots % 2 == 0 else '⚙️ '} Status: {current_op.status.name}{dots:<3}", end='', flush=True)
                status_dots += 1
                time.sleep(30)  # Check every 30 seconds
        
        # Get cluster info
        get_request = container_v1.GetClusterRequest(
            name=f"projects/{project}/locations/{ZONE}/clusters/{cluster_name}"
        )
        created_cluster = cluster_manager_client.get_cluster(request=get_request)
        
        print(f"\n📊 Cluster Details:")
        print(f"   Name: {cluster_name}")
        print(f"   Endpoint: {created_cluster.endpoint}")
        print(f"   Status: {created_cluster.status.name}")
        print(f"   Kubernetes Version: {created_cluster.current_master_version}")
        
        try:
            total_nodes = sum((p.initial_node_count or 0) for p in (created_cluster.node_pools or []))
            print(f"\n🖥️  Node Pools:")
            for pool in created_cluster.node_pools:
                print(f"   • {pool.name}: {pool.initial_node_count} nodes ({pool.config.machine_type})")
            print(f"   Total initial nodes: {total_nodes}")
        except Exception:
            print("   Node count: Unknown")
        
        print(f"\n✅ Enabled Features:")
        print(f"   • Cost Management: Enabled for cost allocation tracking")
        print(f"   • Workload Identity: {project}.svc.id.goog")
        print(f"   • Managed Prometheus: Disabled (cost optimization)")
        
        # Instructions for connecting
        print(f"\n{'='*70}")
        print(f"📝 Next Steps")
        print(f"{'='*70}")
        print(f"\n🔗 Connect to your cluster:")
        print(f"   gcloud container clusters get-credentials {cluster_name} \\")
        print(f"     --zone {ZONE} --project {project}")
        print(f"\n🎯 Verify cluster:")
        print(f"   kubectl get nodes")
        print(f"   kubectl get pods --all-namespaces")
        print(f"   kubectl cluster-info")
        
        print(f"\n⚖️  Scale node pools:")
        print(f"   # Scale all pools")
        print(f"   python gke-cluster.py scale --name {cluster_name} --nodes 5")
        
        print(f"\n   # Scale specific pool")
        print(f"   python gke-cluster.py scale --name {cluster_name} --nodes 5 --pool ml-pool")
        
        print(f"\n   # Scale to 0 to save money")
        print(f"   python gke-cluster.py scale --name {cluster_name} --nodes 0")
        
        print(f"\n💡 Important Notes:")
        print(f"   • ML pool has taint: dedicated=ml:NoSchedule")
        print(f"   • Only workloads with matching toleration can run on ML nodes")
        print(f"   • ML pool autoscales from 0 to {ML_MAX_NODES} nodes")
        
        # Cost estimation
        print(f"\n{'='*70}")
        print(f"💰 Cost Estimation (Spot Instances)")
        print(f"{'='*70}")
        print(f"   Default Pool ({NODE_COUNT} x {MACHINE_TYPE}): ~$20-33/month")
        print(f"   ML Pool ({NODE_COUNT} x {MACHINE_TYPE_ML}):     ~$15-25/month")
        print(f"   Persistent Disk (100GB standard):   ~$4/month")
        print(f"   " + "-" * 50)
        print(f"   Total Estimated Cost:               ~$39-62/month")
        print(f"\n   ⚠️  Spot instances offer 60-91% savings but can be preempted")
        print(f"   💡 Scale to 0 nodes when not in use to minimize costs")
        print(f"\n{'='*70}")
        
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
            if pool_name:
                print(f"\n✅ Cluster '{cluster_name}' scaled successfully to {target_node_count} nodes (pool: {pool_name})!")
                if target_node_count == 0:
                    print(f"💰 Compute costs reduced for pool '{pool_name}'")
                    print(f"🔄 To scale back up: python gke-cluster.py scale --name {cluster_name} --nodes 5 --pool {pool_name}")
            else:
                scaled_pools = [name for _, name in operations]
                print(f"\n✅ Cluster '{cluster_name}' scaled successfully to {target_node_count} nodes (all {len(scaled_pools)} pools)!")
                print(f"   Scaled pools: {', '.join(scaled_pools)}")
                if target_node_count == 0:
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