"""Action Library - Collection of remediation actions"""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ActionLibrary:
    """Library of remediation actions for Kubernetes resources"""
    
    def __init__(self, k8s_client=None):
        self.k8s_client = k8s_client
    
    def scale_memory(
        self,
        namespace: str,
        deployment_name: str,
        container_name: str,
        new_memory_limit: str,
        new_memory_request: Optional[str] = None,
    ) -> bool:
        """Scale memory for a deployment container"""
        if not self.k8s_client:
            logger.warning("No K8s client - dry run mode")
            return True
        
        try:
            # Get current deployment
            deployment = self.k8s_client.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
            )
            
            # Find and update container
            for container in deployment.spec.template.spec.containers:
                if container.name == container_name:
                    if container.resources is None:
                        from kubernetes.client import V1ResourceRequirements
                        container.resources = V1ResourceRequirements()
                    
                    if container.resources.limits is None:
                        container.resources.limits = {}
                    if container.resources.requests is None:
                        container.resources.requests = {}
                    
                    container.resources.limits["memory"] = new_memory_limit
                    if new_memory_request:
                        container.resources.requests["memory"] = new_memory_request
                    break
            
            # Apply update
            self.k8s_client.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment,
            )
            
            logger.info(f"Scaled memory for {namespace}/{deployment_name}/{container_name} to {new_memory_limit}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to scale memory: {e}")
            return False
    
    def scale_replicas(
        self,
        namespace: str,
        deployment_name: str,
        replicas: int,
    ) -> bool:
        """Scale deployment replicas"""
        if not self.k8s_client:
            logger.warning("No K8s client - dry run mode")
            return True
        
        try:
            self.k8s_client.patch_namespaced_deployment_scale(
                name=deployment_name,
                namespace=namespace,
                body={"spec": {"replicas": replicas}},
            )
            
            logger.info(f"Scaled {namespace}/{deployment_name} to {replicas} replicas")
            return True
            
        except Exception as e:
            logger.error(f"Failed to scale replicas: {e}")
            return False
    
    def delete_pod(
        self,
        namespace: str,
        pod_name: str,
        grace_period: int = 30,
    ) -> bool:
        """Delete a pod (triggers restart via controller)"""
        if not self.k8s_client:
            logger.warning("No K8s client - dry run mode")
            return True
        
        try:
            from kubernetes.client import V1DeleteOptions
            
            self.k8s_client.delete_namespaced_pod(
                name=pod_name,
                namespace=namespace,
                body=V1DeleteOptions(grace_period_seconds=grace_period),
            )
            
            logger.info(f"Deleted pod {namespace}/{pod_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete pod: {e}")
            return False
    
    def rollback_deployment(
        self,
        namespace: str,
        deployment_name: str,
        revision: Optional[int] = None,
    ) -> bool:
        """Rollback a deployment to previous revision"""
        if not self.k8s_client:
            logger.warning("No K8s client - dry run mode")
            return True
        
        try:
            # Get deployment
            deployment = self.k8s_client.read_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
            )
            
            # Update revision annotation to trigger rollback
            if deployment.spec.template.metadata.annotations is None:
                deployment.spec.template.metadata.annotations = {}
            
            deployment.spec.template.metadata.annotations["kubectl.kubernetes.io/restartedAt"] = \
                datetime.utcnow().isoformat()
            
            self.k8s_client.patch_namespaced_deployment(
                name=deployment_name,
                namespace=namespace,
                body=deployment,
            )
            
            logger.info(f"Triggered rollback for {namespace}/{deployment_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to rollback: {e}")
            return False
    
    def cordon_node(self, node_name: str) -> bool:
        """Mark node as unschedulable"""
        if not self.k8s_client:
            return True
        
        try:
            self.k8s_client.patch_node(
                name=node_name,
                body={"spec": {"unschedulable": True}},
            )
            logger.info(f"Cordoned node {node_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to cordon node: {e}")
            return False
    
    def uncordon_node(self, node_name: str) -> bool:
        """Mark node as schedulable"""
        if not self.k8s_client:
            return True
        
        try:
            self.k8s_client.patch_node(
                name=node_name,
                body={"spec": {"unschedulable": False}},
            )
            logger.info(f"Uncordoned node {node_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to uncordon node: {e}")
            return False
