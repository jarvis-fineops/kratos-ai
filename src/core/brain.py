"""Kratos Brain - The central intelligence hub"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

from .types import (
    Incident,
    IncidentType,
    IncidentSeverity,
    Prediction,
    PredictionConfidence,
    Remediation,
    KubernetesResource,
    ResourceMetrics,
)
from .knowledge_base import KnowledgeBase
from ..ml.predictors import FailurePredictor, AnomalyDetector, TimeSeriesForecaster
from ..remediation.engine import RemediationEngine, RemediationPlan

logger = logging.getLogger(__name__)


class KratosMode(str, Enum):
    OBSERVE = "observe"
    PREDICT = "predict"
    RECOMMEND = "recommend"
    SEMI_AUTO = "semi_auto"
    AUTO = "auto"


@dataclass
class ClusterState:
    total_nodes: int
    ready_nodes: int
    total_pods: int
    running_pods: int
    pending_pods: int
    failed_pods: int
    namespaces: List[str]
    timestamp: datetime


@dataclass
class KratosStatus:
    mode: KratosMode
    is_running: bool
    knowledge_stats: Dict[str, Any]
    active_predictions: int
    pending_remediations: int
    last_incident: Optional[datetime]
    last_remediation: Optional[datetime]
    uptime_seconds: float


class KratosBrain:
    """The central intelligence hub for Kratos AI."""
    
    def __init__(
        self,
        k8s_client=None,
        mode: KratosMode = KratosMode.RECOMMEND,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.k8s_client = k8s_client
        self.mode = mode
        self.config = config or {}
        
        self.knowledge_base = KnowledgeBase()
        self.failure_predictor = FailurePredictor(knowledge_base=self.knowledge_base)
        self.anomaly_detector = AnomalyDetector()
        self.time_series_forecaster = TimeSeriesForecaster()
        
        self.remediation_engine = RemediationEngine(
            k8s_client=k8s_client,
            knowledge_base=self.knowledge_base,
            dry_run=(mode == KratosMode.OBSERVE),
            config=self.config.get("remediation", {}),
        )
        
        self.is_running = False
        self.started_at: Optional[datetime] = None
        self.active_predictions: Dict[str, Prediction] = {}
        self.cluster_state: Optional[ClusterState] = None
        
        self.on_incident: List[callable] = []
        self.on_prediction: List[callable] = []
        self.on_remediation: List[callable] = []
        
        self.prediction_threshold = self.config.get("prediction_threshold", 0.7)
        self.auto_remediate_threshold = self.config.get("auto_remediate_threshold", 0.85)
        
        logger.info(f"Kratos Brain initialized in {mode.value} mode")
    
    async def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.started_at = datetime.utcnow()
        
        asyncio.create_task(self._observation_loop())
        
        if self.mode in (KratosMode.PREDICT, KratosMode.RECOMMEND, KratosMode.SEMI_AUTO, KratosMode.AUTO):
            asyncio.create_task(self._prediction_loop())
        
        logger.info("Kratos Brain started")
    
    async def stop(self):
        self.is_running = False
        logger.info("Kratos Brain stopped")
    
    def get_status(self) -> KratosStatus:
        uptime = 0.0
        if self.started_at:
            uptime = (datetime.utcnow() - self.started_at).total_seconds()
        
        return KratosStatus(
            mode=self.mode,
            is_running=self.is_running,
            knowledge_stats=self.knowledge_base.get_stats(),
            active_predictions=len(self.active_predictions),
            pending_remediations=len(self.remediation_engine.pending_approvals),
            last_incident=None,
            last_remediation=None,
            uptime_seconds=uptime,
        )
    
    async def _observation_loop(self):
        interval = self.config.get("observe_interval_seconds", 30)
        
        while self.is_running:
            try:
                await self._observe_cluster()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Observation error: {e}")
                await asyncio.sleep(5)
    
    async def _prediction_loop(self):
        interval = self.config.get("predict_interval_seconds", 60)
        
        while self.is_running:
            try:
                await self._run_predictions()
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"Prediction error: {e}")
                await asyncio.sleep(10)
    
    async def _observe_cluster(self):
        if not self.k8s_client:
            return
        
        self.cluster_state = ClusterState(
            total_nodes=3,
            ready_nodes=3,
            total_pods=50,
            running_pods=45,
            pending_pods=3,
            failed_pods=2,
            namespaces=["default", "kube-system", "app"],
            timestamp=datetime.utcnow(),
        )
        
        incidents = await self._detect_incidents()
        for incident in incidents:
            await self._handle_incident(incident)
    
    async def _detect_incidents(self) -> List[Incident]:
        return []
    
    async def _handle_incident(self, incident: Incident):
        logger.info(f"Incident: {incident.type.value} - {incident.message}")
        self.knowledge_base.record_incident(incident)
        
        for callback in self.on_incident:
            try:
                callback(incident)
            except Exception as e:
                logger.error(f"Callback error: {e}")
        
        if self.mode in (KratosMode.RECOMMEND, KratosMode.SEMI_AUTO, KratosMode.AUTO):
            plan = self.remediation_engine.plan_remediation(incident=incident)
            await self._handle_remediation_plan(plan)
    
    async def _run_predictions(self):
        pass
    
    async def _handle_remediation_plan(self, plan: RemediationPlan, preemptive: bool = False):
        logger.info(f"Plan: {plan.remediation.action.value}")
        
        should_execute = False
        if self.mode == KratosMode.AUTO:
            should_execute = plan.safety_validation.safe and not plan.safety_validation.requires_approval
        
        if should_execute:
            remediation = self.remediation_engine.execute(plan, approved_by="auto")
            for callback in self.on_remediation:
                try:
                    callback(remediation)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
    
    def predict_for_resource(self, resource: KubernetesResource, metrics: ResourceMetrics) -> Prediction:
        features = {
            "cpu_usage_cores": metrics.cpu_usage_cores,
            "cpu_limit_cores": metrics.cpu_limit_cores,
            "memory_usage_bytes": metrics.memory_usage_bytes,
            "memory_limit_bytes": metrics.memory_limit_bytes,
        }
        
        result = self.failure_predictor.predict(features)
        
        incident_type = IncidentType.RESOURCE_EXHAUSTION
        if metrics.memory_utilization > metrics.cpu_utilization:
            incident_type = IncidentType.OOM_KILL
        
        if result.probability >= 0.9:
            confidence = PredictionConfidence.VERY_HIGH
        elif result.probability >= 0.8:
            confidence = PredictionConfidence.HIGH
        elif result.probability >= 0.7:
            confidence = PredictionConfidence.MEDIUM
        elif result.probability >= 0.5:
            confidence = PredictionConfidence.LOW
        else:
            confidence = PredictionConfidence.UNCERTAIN
        
        return Prediction(
            incident_type=incident_type,
            target_resource=resource,
            probability=result.probability,
            confidence=confidence,
            eta_seconds=result.eta_seconds,
            evidence=result.evidence,
            model_name=result.model_name,
            model_version=result.model_version,
        )
    
    def get_recommendations(self, resource: KubernetesResource, prediction: Prediction) -> RemediationPlan:
        return self.remediation_engine.plan_remediation(prediction=prediction)
    
    def execute_remediation(self, plan: RemediationPlan, approved_by: str) -> Remediation:
        return self.remediation_engine.execute(plan, approved_by=approved_by)
    
    def get_similar_incidents(self, incident: Incident) -> List[Incident]:
        return self.knowledge_base.find_similar_incidents(incident)
    
    def get_active_predictions(self) -> List[Prediction]:
        now = datetime.utcnow()
        active = []
        for pred in self.active_predictions.values():
            if pred.expires_at and pred.expires_at < now:
                continue
            active.append(pred)
        return active
