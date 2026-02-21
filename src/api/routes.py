"""FastAPI routes for Kratos AI"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from datetime import datetime

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


# Global brain instance (would be properly initialized in production)
_brain = None


def get_brain():
    global _brain
    if _brain is None:
        from ..core.brain import KratosBrain, KratosMode
        _brain = KratosBrain(mode=KratosMode.RECOMMEND)
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


@router.post("/predict", response_model=PredictionResponse)
async def predict_failure(metrics: MetricsInput):
    """Predict potential failures based on current metrics"""
    brain = get_brain()
    
    from ..core.types import KubernetesResource, ResourceMetrics
    
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
    
    from ..core.types import Incident, IncidentType, IncidentSeverity, KubernetesResource
    
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
