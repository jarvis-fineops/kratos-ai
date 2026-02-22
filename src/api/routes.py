"""FastAPI routes for Kratos AI"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/kratos", tags=["Kratos AI"])


class MetricsInput(BaseModel):
    resource_name: str
    namespace: str
    cpu_usage_cores: float
    cpu_limit_cores: float
    memory_usage_bytes: int
    memory_limit_bytes: int


class PredictionResponse(BaseModel):
    predicted: bool
    probability: float
    incident_type: str
    eta_minutes: Optional[float]
    confidence: str
    evidence: List[str]
    recommended_action: Optional[str]
    explanation: Optional[str]


class IncidentInput(BaseModel):
    type: str
    severity: str
    resource_kind: str
    resource_name: str
    namespace: str
    message: str
    labels: Dict[str, str] = {}


class RemediationApproval(BaseModel):
    remediation_id: str
    approved_by: str


class StatusResponse(BaseModel):
    mode: str
    is_running: bool
    total_incidents: int
    total_patterns: int
    active_predictions: int
    pending_remediations: int
    uptime_seconds: float


class ClusterHealthResponse(BaseModel):
    total_nodes: int
    ready_nodes: int
    total_pods: int
    running_pods: int
    pending_pods: int
    failed_pods: int
    namespaces: List[str]


# Global brain instance
_brain = None
_k8s_client = None


def get_k8s_client():
    global _k8s_client
    if _k8s_client is None:
        try:
            from kubernetes import client, config
            # Load kubeconfig from default location
            config.load_kube_config()
            _k8s_client = client.AppsV1Api()
            logger.info("Kubernetes client initialized successfully")
        except Exception as e:
            logger.warning(f"Failed to initialize K8s client: {e}")
            _k8s_client = None
    return _k8s_client


def get_brain():
    global _brain
    if _brain is None:
        from core.brain import KratosBrain, KratosMode
        k8s_client = get_k8s_client()
        _brain = KratosBrain(k8s_client=k8s_client, mode=KratosMode.RECOMMEND)
        logger.info(f"KratosBrain initialized with k8s_client={k8s_client is not None}")
    return _brain


@router.get("/status", response_model=StatusResponse)
async def get_status():
    """Get Kratos AI system status"""
    brain = get_brain()
    status = brain.get_status()
    return StatusResponse(
        mode=status.mode.value,
        is_running=status.is_running,
        total_incidents=status.knowledge_stats.get("total_incidents", 0),
        total_patterns=status.knowledge_stats.get("total_patterns", 0),
        active_predictions=status.active_predictions,
        pending_remediations=status.pending_remediations,
        uptime_seconds=status.uptime_seconds,
    )


@router.get("/cluster/health", response_model=ClusterHealthResponse)
async def get_cluster_health():
    """Get Kubernetes cluster health"""
    try:
        from kubernetes import client, config
        config.load_kube_config()
        
        v1 = client.CoreV1Api()
        
        # Get nodes
        nodes = v1.list_node()
        total_nodes = len(nodes.items)
        ready_nodes = sum(
            1 for node in nodes.items
            for condition in node.status.conditions
            if condition.type == "Ready" and condition.status == "True"
        )
        
        # Get pods
        pods = v1.list_pod_for_all_namespaces()
        total_pods = len(pods.items)
        running_pods = sum(1 for pod in pods.items if pod.status.phase == "Running")
        pending_pods = sum(1 for pod in pods.items if pod.status.phase == "Pending")
        failed_pods = sum(1 for pod in pods.items if pod.status.phase == "Failed")
        
        # Get namespaces
        namespaces = v1.list_namespace()
        namespace_names = [ns.metadata.name for ns in namespaces.items]
        
        return ClusterHealthResponse(
            total_nodes=total_nodes,
            ready_nodes=ready_nodes,
            total_pods=total_pods,
            running_pods=running_pods,
            pending_pods=pending_pods,
            failed_pods=failed_pods,
            namespaces=namespace_names,
        )
    except Exception as e:
        logger.error(f"Failed to get cluster health: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/pods")
async def get_cluster_pods(namespace: Optional[str] = None):
    """Get pods with their status"""
    try:
        from kubernetes import client, config
        config.load_kube_config()
        
        v1 = client.CoreV1Api()
        
        if namespace:
            pods = v1.list_namespaced_pod(namespace=namespace)
        else:
            pods = v1.list_pod_for_all_namespaces()
        
        pod_list = []
        for pod in pods.items:
            restart_count = 0
            if pod.status.container_statuses:
                restart_count = sum(cs.restart_count for cs in pod.status.container_statuses)
            
            pod_list.append({
                "name": pod.metadata.name,
                "namespace": pod.metadata.namespace,
                "status": pod.status.phase,
                "restarts": restart_count,
                "age": pod.metadata.creation_timestamp.isoformat() if pod.metadata.creation_timestamp else None,
                "node": pod.spec.node_name,
            })
        
        return {"count": len(pod_list), "pods": pod_list}
    except Exception as e:
        logger.error(f"Failed to get pods: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/events")
async def get_cluster_events(limit: int = 50):
    """Get recent cluster events (warnings, errors)"""
    try:
        from kubernetes import client, config
        config.load_kube_config()
        
        v1 = client.CoreV1Api()
        events = v1.list_event_for_all_namespaces(limit=limit)
        
        event_list = []
        for event in sorted(events.items, key=lambda x: x.last_timestamp or x.event_time or datetime.min, reverse=True):
            event_list.append({
                "type": event.type,
                "reason": event.reason,
                "message": event.message,
                "namespace": event.metadata.namespace,
                "object": f"{event.involved_object.kind}/{event.involved_object.name}",
                "count": event.count,
                "last_seen": (event.last_timestamp or event.event_time).isoformat() if (event.last_timestamp or event.event_time) else None,
            })
        
        return {"count": len(event_list), "events": event_list[:limit]}
    except Exception as e:
        logger.error(f"Failed to get events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict", response_model=PredictionResponse)
async def predict_failure(metrics: MetricsInput):
    """Predict potential failures based on current metrics"""
    brain = get_brain()
    
    from core.types import KubernetesResource, ResourceMetrics
    
    resource = KubernetesResource(
        kind="Pod",
        name=metrics.resource_name,
        namespace=metrics.namespace,
    )
    
    resource_metrics = ResourceMetrics(
        cpu_usage_cores=metrics.cpu_usage_cores,
        cpu_limit_cores=metrics.cpu_limit_cores,
        cpu_request_cores=metrics.cpu_limit_cores * 0.5,
        memory_usage_bytes=metrics.memory_usage_bytes,
        memory_limit_bytes=metrics.memory_limit_bytes,
        memory_request_bytes=int(metrics.memory_limit_bytes * 0.5),
    )
    
    prediction = brain.predict_for_resource(resource, resource_metrics)
    
    recommended_action = None
    explanation = None
    
    if prediction.probability > 0.5:
        plan = brain.get_recommendations(resource, prediction)
        recommended_action = plan.remediation.action.value
        if plan.remediation.explanation:
            explanation = plan.remediation.explanation.to_human_readable()
    
    return PredictionResponse(
        predicted=prediction.probability > 0.5,
        probability=prediction.probability,
        incident_type=prediction.incident_type.value,
        eta_minutes=prediction.eta_minutes,
        confidence=prediction.confidence.value,
        evidence=prediction.evidence,
        recommended_action=recommended_action,
        explanation=explanation,
    )


@router.post("/incidents")
async def record_incident(incident: IncidentInput, background_tasks: BackgroundTasks):
    """Record a new incident for learning"""
    brain = get_brain()
    
    from core.types import Incident, IncidentType, IncidentSeverity, KubernetesResource
    
    try:
        incident_type = IncidentType(incident.type)
    except ValueError:
        incident_type = IncidentType.UNKNOWN
    
    try:
        severity = IncidentSeverity(incident.severity)
    except ValueError:
        severity = IncidentSeverity.MEDIUM
    
    resource = KubernetesResource(
        kind=incident.resource_kind,
        name=incident.resource_name,
        namespace=incident.namespace,
        labels=incident.labels,
    )
    
    inc = Incident(
        type=incident_type,
        severity=severity,
        resource=resource,
        message=incident.message,
    )
    
    incident_id = brain.knowledge_base.record_incident(inc)
    
    return {
        "status": "recorded",
        "incident_id": incident_id,
        "similar_incidents": len(brain.get_similar_incidents(inc)),
    }


@router.get("/patterns")
async def get_patterns():
    """Get learned patterns"""
    brain = get_brain()
    stats = brain.knowledge_base.get_stats()
    
    return {
        "total_patterns": stats.get("total_patterns", 0),
        "patterns": stats.get("top_patterns", []),
    }


@router.get("/knowledge/stats")
async def get_knowledge_stats():
    """Get knowledge base statistics"""
    brain = get_brain()
    return brain.knowledge_base.get_stats()


@router.post("/remediation/approve")
async def approve_remediation(approval: RemediationApproval):
    """Approve a pending remediation"""
    brain = get_brain()
    
    if approval.remediation_id not in brain.remediation_engine.pending_approvals:
        raise HTTPException(status_code=404, detail="Remediation not found or not pending")
    
    plan = brain.remediation_engine.pending_approvals[approval.remediation_id]
    result = brain.execute_remediation(plan, approved_by=approval.approved_by)
    
    return {
        "status": "executed",
        "outcome": result.outcome.value,
        "error": result.error_message,
    }


@router.get("/predictions/active")
async def get_active_predictions():
    """Get all active predictions"""
    brain = get_brain()
    predictions = brain.get_active_predictions()
    
    return {
        "count": len(predictions),
        "predictions": [
            {
                "id": p.id,
                "type": p.incident_type.value,
                "probability": p.probability,
                "target": p.target_resource.name if p.target_resource else None,
                "eta_minutes": p.eta_minutes,
            }
            for p in predictions
        ],
    }


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


# ============= NEW ENDPOINTS FOR REMEDIATION & LEARNING =============

class RemediationAction(BaseModel):
    action: str  # restart_pod, scale_memory, scale_replicas
    pod_name: str
    namespace: str
    parameters: Dict[str, Any] = {}


@router.post("/remediation/execute")
async def execute_remediation(action: RemediationAction):
    """Execute a remediation action on a pod/deployment"""
    try:
        from kubernetes import client, config
        config.load_kube_config()
        
        v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()
        
        result = {"status": "pending", "action": action.action, "target": action.pod_name}
        
        if action.action == "restart_pod":
            # Delete the pod to trigger a restart
            v1.delete_namespaced_pod(
                name=action.pod_name,
                namespace=action.namespace
            )
            result["status"] = "success"
            result["message"] = f"Pod {action.pod_name} deleted for restart"
            
            # Record this remediation
            _record_remediation(action.action, action.pod_name, action.namespace, "success")
            
        elif action.action == "scale_memory_up":
            # Find the deployment for this pod
            pods = v1.list_namespaced_pod(namespace=action.namespace)
            target_pod = None
            for pod in pods.items:
                if pod.metadata.name == action.pod_name:
                    target_pod = pod
                    break
            
            if target_pod and target_pod.metadata.owner_references:
                # Get deployment name from ReplicaSet owner
                for owner in target_pod.metadata.owner_references:
                    if owner.kind == "ReplicaSet":
                        rs = apps_v1.read_namespaced_replica_set(owner.name, action.namespace)
                        if rs.metadata.owner_references:
                            for rs_owner in rs.metadata.owner_references:
                                if rs_owner.kind == "Deployment":
                                    # Patch deployment with increased memory
                                    patch = {
                                        "spec": {
                                            "template": {
                                                "spec": {
                                                    "containers": [{
                                                        "name": target_pod.spec.containers[0].name,
                                                        "resources": {
                                                            "limits": {"memory": "256Mi"},
                                                            "requests": {"memory": "128Mi"}
                                                        }
                                                    }]
                                                }
                                            }
                                        }
                                    }
                                    apps_v1.patch_namespaced_deployment(
                                        rs_owner.name, action.namespace, patch
                                    )
                                    result["status"] = "success"
                                    result["message"] = f"Scaled memory for deployment {rs_owner.name}"
                                    _record_remediation(action.action, rs_owner.name, action.namespace, "success")
                                    break
            
            if result["status"] == "pending":
                # For standalone pods, just restart them
                v1.delete_namespaced_pod(name=action.pod_name, namespace=action.namespace)
                result["status"] = "success"
                result["message"] = f"Restarted pod {action.pod_name} (standalone pod)"
                _record_remediation("restart_pod", action.pod_name, action.namespace, "success")
                
        else:
            result["status"] = "error"
            result["message"] = f"Unknown action: {action.action}"
        
        return result
        
    except Exception as e:
        logger.error(f"Remediation failed: {e}")
        _record_remediation(action.action, action.pod_name, action.namespace, "failed", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# In-memory storage for incidents and remediations (will persist to file)
_incidents_log = []
_remediations_log = []
_patterns = {}


def _record_remediation(action: str, target: str, namespace: str, status: str, error: str = None):
    """Record a remediation action"""
    global _remediations_log
    _remediations_log.append({
        "action": action,
        "target": target,
        "namespace": namespace,
        "status": status,
        "error": error,
        "timestamp": datetime.utcnow().isoformat()
    })
    _save_data()


def _record_incident(incident_type: str, target: str, namespace: str, severity: str, message: str):
    """Record an incident for learning"""
    global _incidents_log, _patterns
    
    incident = {
        "type": incident_type,
        "target": target,
        "namespace": namespace,
        "severity": severity,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    _incidents_log.append(incident)
    
    # Update patterns
    pattern_key = f"{incident_type}:{namespace}"
    if pattern_key not in _patterns:
        _patterns[pattern_key] = {"count": 0, "last_seen": None, "targets": set()}
    _patterns[pattern_key]["count"] += 1
    _patterns[pattern_key]["last_seen"] = datetime.utcnow().isoformat()
    _patterns[pattern_key]["targets"].add(target)
    
    _save_data()


def _save_data():
    """Save incidents and remediations to file"""
    import json
    data = {
        "incidents": _incidents_log[-1000:],  # Keep last 1000
        "remediations": _remediations_log[-1000:],
        "patterns": {k: {**v, "targets": list(v["targets"])} for k, v in _patterns.items()}
    }
    try:
        with open("/var/lib/kratos-ai/data.json", "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"Failed to save data: {e}")


def _load_data():
    """Load saved data"""
    global _incidents_log, _remediations_log, _patterns
    import json
    try:
        with open("/var/lib/kratos-ai/data.json", "r") as f:
            data = json.load(f)
            _incidents_log = data.get("incidents", [])
            _remediations_log = data.get("remediations", [])
            _patterns = {k: {**v, "targets": set(v["targets"])} for k, v in data.get("patterns", {}).items()}
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.error(f"Failed to load data: {e}")


# Load data on startup
_load_data()


@router.post("/learn/record-events")
async def record_events_for_learning():
    """Scan current events and record incidents for learning"""
    try:
        from kubernetes import client, config
        config.load_kube_config()
        
        v1 = client.CoreV1Api()
        events = v1.list_event_for_all_namespaces(limit=100)
        
        recorded = 0
        for event in events.items:
            if event.type == "Warning":
                incident_type = "unknown"
                severity = "medium"
                
                if "BackOff" in (event.reason or ""):
                    incident_type = "crash_loop"
                    severity = "high"
                elif "OOM" in (event.message or "") or "Kill" in (event.reason or ""):
                    incident_type = "oom_kill"
                    severity = "high"
                elif "Failed" in (event.reason or ""):
                    incident_type = "failed"
                    severity = "medium"
                elif "Unhealthy" in (event.reason or ""):
                    incident_type = "unhealthy"
                    severity = "medium"
                
                if incident_type != "unknown":
                    target = event.involved_object.name if event.involved_object else "unknown"
                    _record_incident(
                        incident_type,
                        target,
                        event.metadata.namespace,
                        severity,
                        event.message or "No message"
                    )
                    recorded += 1
        
        return {"status": "success", "recorded": recorded, "total_incidents": len(_incidents_log)}
    except Exception as e:
        logger.error(f"Failed to record events: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/learn/stats")
async def get_learning_stats():
    """Get learning statistics"""
    return {
        "total_incidents": len(_incidents_log),
        "total_remediations": len(_remediations_log),
        "total_patterns": len(_patterns),
        "recent_incidents": _incidents_log[-10:],
        "recent_remediations": _remediations_log[-10:],
        "patterns": [
            {
                "type": k.split(":")[0],
                "namespace": k.split(":")[1] if ":" in k else "unknown",
                "count": v["count"],
                "last_seen": v["last_seen"],
                "targets_count": len(v["targets"])
            }
            for k, v in _patterns.items()
        ]
    }


@router.get("/remediations/history")
async def get_remediation_history():
    """Get remediation history"""
    return {
        "total": len(_remediations_log),
        "remediations": _remediations_log[-50:]
    }
