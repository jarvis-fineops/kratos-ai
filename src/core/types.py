"""Core data types for Kratos AI"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid


class IncidentSeverity(str, Enum):
    """Severity levels for incidents"""
    CRITICAL = "critical"    # Service down, data loss risk
    HIGH = "high"            # Degraded performance, partial outage
    MEDIUM = "medium"        # Potential issues, proactive intervention needed
    LOW = "low"              # Minor issues, informational
    INFO = "info"            # Normal observations, learning data


class IncidentType(str, Enum):
    """Types of Kubernetes incidents"""
    OOM_KILL = "oom_kill"
    CRASH_LOOP = "crash_loop"
    IMAGE_PULL_FAIL = "image_pull_fail"
    READINESS_FAIL = "readiness_fail"
    LIVENESS_FAIL = "liveness_fail"
    NODE_NOT_READY = "node_not_ready"
    NODE_MEMORY_PRESSURE = "node_memory_pressure"
    NODE_DISK_PRESSURE = "node_disk_pressure"
    NODE_PID_PRESSURE = "node_pid_pressure"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    EVICTION = "eviction"
    PENDING_POD = "pending_pod"
    NETWORK_ISSUE = "network_issue"
    VOLUME_ISSUE = "volume_issue"
    CONFIG_ERROR = "config_error"
    SCALING_ISSUE = "scaling_issue"
    DEPLOYMENT_FAIL = "deployment_fail"
    UNKNOWN = "unknown"


class PredictionConfidence(str, Enum):
    """Confidence levels for predictions"""
    VERY_HIGH = "very_high"  # >95% confidence
    HIGH = "high"            # 85-95% confidence
    MEDIUM = "medium"        # 70-85% confidence
    LOW = "low"              # 50-70% confidence
    UNCERTAIN = "uncertain"  # <50% confidence


class RemediationAction(str, Enum):
    """Types of remediation actions"""
    # Resource adjustments
    SCALE_MEMORY_UP = "scale_memory_up"
    SCALE_MEMORY_DOWN = "scale_memory_down"
    SCALE_CPU_UP = "scale_cpu_up"
    SCALE_CPU_DOWN = "scale_cpu_down"
    SCALE_REPLICAS_UP = "scale_replicas_up"
    SCALE_REPLICAS_DOWN = "scale_replicas_down"
    
    # Pod operations
    RESTART_POD = "restart_pod"
    DELETE_POD = "delete_pod"
    CORDON_NODE = "cordon_node"
    DRAIN_NODE = "drain_node"
    
    # Deployment operations
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    PAUSE_DEPLOYMENT = "pause_deployment"
    
    # Network operations
    RESET_NETWORK_POLICY = "reset_network_policy"
    UPDATE_SERVICE = "update_service"
    
    # Configuration
    UPDATE_CONFIG_MAP = "update_config_map"
    UPDATE_SECRET = "update_secret"
    UPDATE_RESOURCE_QUOTA = "update_resource_quota"
    
    # Scheduling
    ADD_NODE_AFFINITY = "add_node_affinity"
    REMOVE_NODE_AFFINITY = "remove_node_affinity"
    UPDATE_PRIORITY_CLASS = "update_priority_class"
    
    # Custom
    CUSTOM_SCRIPT = "custom_script"
    NOTIFY_ONLY = "notify_only"
    NO_ACTION = "no_action"


class RemediationOutcome(str, Enum):
    """Outcome of a remediation attempt"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"
    SKIPPED = "skipped"
    PENDING_APPROVAL = "pending_approval"
    DRY_RUN = "dry_run"


@dataclass
class ResourceMetrics:
    """Resource usage metrics snapshot"""
    cpu_usage_cores: float
    cpu_limit_cores: float
    cpu_request_cores: float
    memory_usage_bytes: int
    memory_limit_bytes: int
    memory_request_bytes: int
    network_rx_bytes: int = 0
    network_tx_bytes: int = 0
    storage_usage_bytes: int = 0
    storage_limit_bytes: int = 0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def cpu_utilization(self) -> float:
        """CPU utilization as percentage of limit"""
        if self.cpu_limit_cores == 0:
            return 0.0
        return (self.cpu_usage_cores / self.cpu_limit_cores) * 100
    
    @property
    def memory_utilization(self) -> float:
        """Memory utilization as percentage of limit"""
        if self.memory_limit_bytes == 0:
            return 0.0
        return (self.memory_usage_bytes / self.memory_limit_bytes) * 100


@dataclass
class KubernetesResource:
    """Represents a Kubernetes resource"""
    kind: str                    # Pod, Deployment, Node, etc.
    name: str
    namespace: str
    labels: Dict[str, str] = field(default_factory=dict)
    annotations: Dict[str, str] = field(default_factory=dict)
    uid: str = ""
    created_at: Optional[datetime] = None


@dataclass
class Incident:
    """Represents a Kubernetes incident"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: IncidentType = IncidentType.UNKNOWN
    severity: IncidentSeverity = IncidentSeverity.MEDIUM
    resource: Optional[KubernetesResource] = None
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    metrics_snapshot: Optional[ResourceMetrics] = None
    occurred_at: datetime = field(default_factory=datetime.utcnow)
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    root_cause: Optional[str] = None
    related_incidents: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    
    @property
    def is_resolved(self) -> bool:
        return self.resolved_at is not None
    
    @property
    def duration_seconds(self) -> Optional[float]:
        if self.resolved_at:
            return (self.resolved_at - self.occurred_at).total_seconds()
        return None


@dataclass
class Prediction:
    """A prediction of a future incident"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    incident_type: IncidentType = IncidentType.UNKNOWN
    target_resource: Optional[KubernetesResource] = None
    probability: float = 0.0
    confidence: PredictionConfidence = PredictionConfidence.UNCERTAIN
    eta_seconds: Optional[float] = None  # Estimated time until incident
    evidence: List[str] = field(default_factory=list)
    similar_incidents: List[str] = field(default_factory=list)  # IDs of similar past incidents
    model_name: str = ""
    model_version: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    
    @property
    def eta_minutes(self) -> Optional[float]:
        if self.eta_seconds:
            return self.eta_seconds / 60
        return None


@dataclass  
class ExplanationStep:
    """A single step in an explanation chain"""
    step_number: int
    category: str  # observation, analysis, decision, action, outcome
    content: str
    evidence: List[str] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class Explanation:
    """Full explanation for a remediation action"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    summary: str = ""  # One-line summary
    steps: List[ExplanationStep] = field(default_factory=list)
    risk_assessment: str = ""
    alternative_actions: List[str] = field(default_factory=list)
    rollback_plan: str = ""
    references: List[str] = field(default_factory=list)  # Links to docs, runbooks
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_human_readable(self) -> str:
        """Convert explanation to human-readable text"""
        lines = [f"Summary: {self.summary}", ""]
        
        for step in sorted(self.steps, key=lambda s: s.step_number):
            lines.append(f"{step.step_number}. [{step.category.upper()}] {step.content}")
            if step.evidence:
                for ev in step.evidence:
                    lines.append(f"   - Evidence: {ev}")
        
        if self.risk_assessment:
            lines.extend(["", f"Risk Assessment: {self.risk_assessment}"])
        
        if self.rollback_plan:
            lines.extend(["", f"Rollback Plan: {self.rollback_plan}"])
        
        return "\n".join(lines)


@dataclass
class Remediation:
    """A remediation action taken or planned"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action: RemediationAction = RemediationAction.NO_ACTION
    target_resource: Optional[KubernetesResource] = None
    incident_id: Optional[str] = None
    prediction_id: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    outcome: RemediationOutcome = RemediationOutcome.PENDING_APPROVAL
    explanation: Optional[Explanation] = None
    executed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    dry_run: bool = False
    requires_approval: bool = False
    approved_by: Optional[str] = None
    rollback_remediation_id: Optional[str] = None  # If this was rolled back, link to rollback
    
    @property
    def is_executed(self) -> bool:
        return self.executed_at is not None
    
    @property
    def is_successful(self) -> bool:
        return self.outcome in (RemediationOutcome.SUCCESS, RemediationOutcome.DRY_RUN)


@dataclass
class Pattern:
    """A learned pattern from incidents"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    incident_types: List[IncidentType] = field(default_factory=list)
    indicators: Dict[str, Any] = field(default_factory=dict)  # What to look for
    recommended_actions: List[RemediationAction] = field(default_factory=list)
    success_rate: float = 0.0
    occurrence_count: int = 0
    last_seen: Optional[datetime] = None
    confidence: float = 0.0
