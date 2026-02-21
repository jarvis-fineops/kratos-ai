"""Remediation Engine - Intelligent auto-remediation with explainability"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable
import json

from .safety import SafetyValidator, SafetyValidation
from ..core.types import (
    Incident,
    IncidentType,
    Prediction,
    Remediation,
    RemediationAction,
    RemediationOutcome,
    Explanation,
    ExplanationStep,
    KubernetesResource,
)

logger = logging.getLogger(__name__)


@dataclass
class RemediationPlan:
    """A planned remediation with full context"""
    remediation: Remediation
    safety_validation: SafetyValidation
    estimated_impact: str
    estimated_duration_seconds: int
    can_rollback: bool
    rollback_plan: Optional[str] = None


class RemediationEngine:
    """
    Intelligent remediation engine with full explainability.
    
    Features:
    - Safety validation before any action
    - Full explanation chain for every action
    - Automatic rollback capability
    - Dry-run mode for testing
    - Approval gates for high-risk actions
    """
    
    def __init__(
        self,
        k8s_client=None,  # Kubernetes client
        knowledge_base=None,
        dry_run: bool = False,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.k8s_client = k8s_client
        self.knowledge_base = knowledge_base
        self.dry_run = dry_run
        self.config = config or {}
        
        self.safety_validator = SafetyValidator(self.config.get("safety", {}))
        
        # Action registry
        self.action_handlers: Dict[RemediationAction, Callable] = {}
        self._register_default_handlers()
        
        # Remediation history for rollback
        self.history: List[Remediation] = []
        
        # Pending approvals
        self.pending_approvals: Dict[str, RemediationPlan] = {}
    
    def _register_default_handlers(self):
        """Register default action handlers"""
        self.action_handlers = {
            RemediationAction.SCALE_MEMORY_UP: self._handle_scale_memory_up,
            RemediationAction.SCALE_MEMORY_DOWN: self._handle_scale_memory_down,
            RemediationAction.SCALE_CPU_UP: self._handle_scale_cpu_up,
            RemediationAction.SCALE_CPU_DOWN: self._handle_scale_cpu_down,
            RemediationAction.SCALE_REPLICAS_UP: self._handle_scale_replicas,
            RemediationAction.SCALE_REPLICAS_DOWN: self._handle_scale_replicas,
            RemediationAction.RESTART_POD: self._handle_restart_pod,
            RemediationAction.DELETE_POD: self._handle_delete_pod,
            RemediationAction.ROLLBACK_DEPLOYMENT: self._handle_rollback_deployment,
            RemediationAction.NOTIFY_ONLY: self._handle_notify_only,
        }
    
    def plan_remediation(
        self,
        incident: Optional[Incident] = None,
        prediction: Optional[Prediction] = None,
        suggested_action: Optional[RemediationAction] = None,
    ) -> RemediationPlan:
        """
        Plan a remediation action with full safety analysis.
        
        Returns a plan that can be reviewed before execution.
        """
        if not incident and not prediction:
            raise ValueError("Either incident or prediction must be provided")
        
        # Determine target resource
        target_resource = None
        if incident and incident.resource:
            target_resource = incident.resource
        elif prediction and prediction.target_resource:
            target_resource = prediction.target_resource
        
        # Determine action
        if suggested_action:
            action = suggested_action
        elif incident:
            action = self._select_action_for_incident(incident)
        elif prediction:
            action = self._select_action_for_prediction(prediction)
        else:
            action = RemediationAction.NOTIFY_ONLY
        
        # Generate parameters
        parameters = self._generate_parameters(action, incident, prediction)
        
        # Create explanation
        explanation = self._generate_explanation(
            action=action,
            incident=incident,
            prediction=prediction,
            parameters=parameters,
        )
        
        # Create remediation object
        remediation = Remediation(
            action=action,
            target_resource=target_resource,
            incident_id=incident.id if incident else None,
            prediction_id=prediction.id if prediction else None,
            parameters=parameters,
            explanation=explanation,
            dry_run=self.dry_run,
        )
        
        # Validate safety
        target_dict = {
            "kind": target_resource.kind if target_resource else "Unknown",
            "namespace": target_resource.namespace if target_resource else "default",
            "name": target_resource.name if target_resource else "unknown",
            "labels": target_resource.labels if target_resource else {},
        }
        
        safety_validation = self.safety_validator.validate(
            action=action.value,
            target_resource=target_dict,
            parameters=parameters,
        )
        
        # Update remediation status based on safety
        if safety_validation.requires_approval:
            remediation.requires_approval = True
            remediation.outcome = RemediationOutcome.PENDING_APPROVAL
        
        return RemediationPlan(
            remediation=remediation,
            safety_validation=safety_validation,
            estimated_impact=self._estimate_impact(action, target_resource),
            estimated_duration_seconds=self._estimate_duration(action),
            can_rollback=action in self._rollbackable_actions(),
            rollback_plan=explanation.rollback_plan,
        )
    
    def execute(self, plan: RemediationPlan, approved_by: Optional[str] = None) -> Remediation:
        """
        Execute a remediation plan.
        
        Args:
            plan: The remediation plan to execute
            approved_by: Who approved this action (required for high-risk actions)
        
        Returns:
            The executed remediation with outcome
        """
        remediation = plan.remediation
        
        # Check safety
        if not plan.safety_validation.safe:
            remediation.outcome = RemediationOutcome.SKIPPED
            remediation.error_message = plan.safety_validation.get_summary()
            logger.warning(f"Remediation blocked by safety: {remediation.error_message}")
            return remediation
        
        # Check approval
        if plan.safety_validation.requires_approval and not approved_by:
            remediation.outcome = RemediationOutcome.PENDING_APPROVAL
            self.pending_approvals[remediation.id] = plan
            logger.info(f"Remediation {remediation.id} requires approval: {plan.safety_validation.approval_reason}")
            return remediation
        
        if approved_by:
            remediation.approved_by = approved_by
        
        # Execute
        remediation.executed_at = datetime.utcnow()
        
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would execute: {remediation.action.value}")
                remediation.outcome = RemediationOutcome.DRY_RUN
            else:
                handler = self.action_handlers.get(remediation.action)
                if handler:
                    success = handler(remediation)
                    remediation.outcome = RemediationOutcome.SUCCESS if success else RemediationOutcome.FAILED
                else:
                    logger.warning(f"No handler for action: {remediation.action}")
                    remediation.outcome = RemediationOutcome.SKIPPED
            
            remediation.completed_at = datetime.utcnow()
            
            # Record in history
            self.history.append(remediation)
            
            # Record in knowledge base
            if self.knowledge_base:
                self.knowledge_base.record_remediation(remediation)
            
            # Record for rate limiting
            if remediation.target_resource:
                self.safety_validator.record_action({
                    "kind": remediation.target_resource.kind,
                    "namespace": remediation.target_resource.namespace,
                    "name": remediation.target_resource.name,
                })
            
            logger.info(f"Remediation {remediation.id} completed: {remediation.outcome.value}")
            
        except Exception as e:
            remediation.outcome = RemediationOutcome.FAILED
            remediation.error_message = str(e)
            remediation.completed_at = datetime.utcnow()
            logger.error(f"Remediation {remediation.id} failed: {e}")
        
        return remediation
    
    def rollback(self, remediation_id: str) -> Optional[Remediation]:
        """
        Rollback a previously executed remediation.
        
        Returns the rollback remediation if successful.
        """
        original = None
        for r in self.history:
            if r.id == remediation_id:
                original = r
                break
        
        if not original:
            logger.error(f"Cannot find remediation {remediation_id} for rollback")
            return None
        
        if not original.is_successful:
            logger.warning(f"Cannot rollback failed remediation {remediation_id}")
            return None
        
        # Create rollback action
        rollback_action = self._get_rollback_action(original.action)
        if not rollback_action:
            logger.warning(f"No rollback available for {original.action}")
            return None
        
        # Generate rollback parameters
        rollback_params = self._get_rollback_parameters(original)
        
        rollback = Remediation(
            action=rollback_action,
            target_resource=original.target_resource,
            parameters=rollback_params,
            explanation=Explanation(
                summary=f"Rolling back remediation {remediation_id}",
                rollback_plan="This is a rollback action",
            ),
        )
        
        # Plan and execute rollback
        plan = RemediationPlan(
            remediation=rollback,
            safety_validation=self.safety_validator.validate(
                action=rollback_action.value,
                target_resource={
                    "kind": original.target_resource.kind if original.target_resource else "Unknown",
                    "namespace": original.target_resource.namespace if original.target_resource else "default",
                    "name": original.target_resource.name if original.target_resource else "unknown",
                    "labels": original.target_resource.labels if original.target_resource else {},
                },
                parameters=rollback_params,
            ),
            estimated_impact="Reverting previous change",
            estimated_duration_seconds=30,
            can_rollback=False,
        )
        
        result = self.execute(plan, approved_by="system_rollback")
        
        if result.is_successful:
            original.rollback_remediation_id = result.id
            result.rollback_remediation_id = original.id  # Link back
        
        return result
    
    def _select_action_for_incident(self, incident: Incident) -> RemediationAction:
        """Select best action based on incident type and history"""
        # Check knowledge base for recommended actions
        if self.knowledge_base:
            recommendations = self.knowledge_base.get_recommended_actions(incident.type)
            if recommendations and recommendations[0][1] > 0.6:  # >60% success rate
                return recommendations[0][0]
        
        # Default mappings
        default_actions = {
            IncidentType.OOM_KILL: RemediationAction.SCALE_MEMORY_UP,
            IncidentType.CRASH_LOOP: RemediationAction.RESTART_POD,
            IncidentType.READINESS_FAIL: RemediationAction.RESTART_POD,
            IncidentType.LIVENESS_FAIL: RemediationAction.RESTART_POD,
            IncidentType.NODE_NOT_READY: RemediationAction.CORDON_NODE,
            IncidentType.NODE_MEMORY_PRESSURE: RemediationAction.NOTIFY_ONLY,
            IncidentType.RESOURCE_EXHAUSTION: RemediationAction.SCALE_REPLICAS_UP,
            IncidentType.EVICTION: RemediationAction.SCALE_MEMORY_UP,
            IncidentType.DEPLOYMENT_FAIL: RemediationAction.ROLLBACK_DEPLOYMENT,
        }
        
        return default_actions.get(incident.type, RemediationAction.NOTIFY_ONLY)
    
    def _select_action_for_prediction(self, prediction: Prediction) -> RemediationAction:
        """Select preemptive action based on prediction"""
        preemptive_actions = {
            IncidentType.OOM_KILL: RemediationAction.SCALE_MEMORY_UP,
            IncidentType.RESOURCE_EXHAUSTION: RemediationAction.SCALE_REPLICAS_UP,
            IncidentType.NODE_MEMORY_PRESSURE: RemediationAction.NOTIFY_ONLY,
        }
        
        return preemptive_actions.get(prediction.incident_type, RemediationAction.NOTIFY_ONLY)
    
    def _generate_parameters(
        self,
        action: RemediationAction,
        incident: Optional[Incident],
        prediction: Optional[Prediction],
    ) -> Dict[str, Any]:
        """Generate parameters for the remediation action"""
        params = {}
        
        if action == RemediationAction.SCALE_MEMORY_UP:
            # Get current memory
            current_memory = 512 * 1024**2  # Default 512Mi
            if incident and incident.metrics_snapshot:
                current_memory = incident.metrics_snapshot.memory_limit_bytes
            
            # Increase by 50%
            params["old_memory_bytes"] = current_memory
            params["new_memory_bytes"] = int(current_memory * 1.5)
            params["max_allowed_memory_bytes"] = 4 * 1024**3  # 4GB cap
        
        elif action == RemediationAction.SCALE_REPLICAS_UP:
            params["increase_by"] = 1
            params["max_replicas"] = 10
        
        elif action == RemediationAction.SCALE_REPLICAS_DOWN:
            params["decrease_by"] = 1
            params["min_replicas"] = 1
        
        return params
    
    def _generate_explanation(
        self,
        action: RemediationAction,
        incident: Optional[Incident],
        prediction: Optional[Prediction],
        parameters: Dict[str, Any],
    ) -> Explanation:
        """Generate a full explanation for the remediation"""
        steps = []
        step_num = 1
        
        # Step 1: Observation
        if incident:
            steps.append(ExplanationStep(
                step_number=step_num,
                category="observation",
                content=f"Detected {incident.type.value} incident: {incident.message}",
                evidence=[f"Incident ID: {incident.id}", f"Severity: {incident.severity.value}"],
            ))
        elif prediction:
            steps.append(ExplanationStep(
                step_number=step_num,
                category="observation",
                content=f"Predicted {prediction.incident_type.value} with {prediction.probability*100:.0f}% probability",
                evidence=prediction.evidence,
            ))
        step_num += 1
        
        # Step 2: Analysis
        analysis_content = self._generate_analysis(incident, prediction)
        steps.append(ExplanationStep(
            step_number=step_num,
            category="analysis",
            content=analysis_content,
        ))
        step_num += 1
        
        # Step 3: Decision
        decision_content = f"Selected action: {action.value}"
        if self.knowledge_base:
            # Add historical context
            recommendations = self.knowledge_base.get_recommended_actions(
                incident.type if incident else prediction.incident_type
            )
            if recommendations:
                top_action, success_rate = recommendations[0]
                decision_content += f" (historically {success_rate*100:.0f}% successful)"
        
        steps.append(ExplanationStep(
            step_number=step_num,
            category="decision",
            content=decision_content,
        ))
        step_num += 1
        
        # Step 4: Action details
        action_detail = self._describe_action(action, parameters)
        steps.append(ExplanationStep(
            step_number=step_num,
            category="action",
            content=action_detail,
        ))
        step_num += 1
        
        # Risk assessment
        risk_assessment = self._assess_risk(action, parameters)
        
        # Rollback plan
        rollback_plan = self._generate_rollback_plan(action, parameters)
        
        return Explanation(
            summary=f"{action.value} to {resolve if incident else prevent} {incident.type.value if incident else prediction.incident_type.value}",
            steps=steps,
            risk_assessment=risk_assessment,
            rollback_plan=rollback_plan,
        )
    
    def _generate_analysis(
        self,
        incident: Optional[Incident],
        prediction: Optional[Prediction],
    ) -> str:
        """Generate analysis text"""
        if incident and incident.metrics_snapshot:
            metrics = incident.metrics_snapshot
            return (
                f"Current resource utilization: "
                f"CPU {metrics.cpu_utilization:.1f}%, "
                f"Memory {metrics.memory_utilization:.1f}%"
            )
        elif prediction:
            return f"Predicted failure in approximately {prediction.eta_minutes:.0f} minutes based on {len(prediction.evidence)} signals"
        return "Analyzing situation based on available data"
    
    def _describe_action(self, action: RemediationAction, params: Dict[str, Any]) -> str:
        """Describe the action in human terms"""
        if action == RemediationAction.SCALE_MEMORY_UP:
            old_mb = params.get("old_memory_bytes", 0) / 1024**2
            new_mb = params.get("new_memory_bytes", 0) / 1024**2
            return f"Increase memory limit from {old_mb:.0f}Mi to {new_mb:.0f}Mi"
        
        elif action == RemediationAction.SCALE_REPLICAS_UP:
            return f"Increase replicas by {params.get(increase_by, 1)}"
        
        elif action == RemediationAction.RESTART_POD:
            return "Delete pod to trigger restart (managed by ReplicaSet/Deployment)"
        
        elif action == RemediationAction.ROLLBACK_DEPLOYMENT:
            return "Rollback deployment to previous revision"
        
        return f"Execute {action.value}"
    
    def _assess_risk(self, action: RemediationAction, params: Dict[str, Any]) -> str:
        """Assess the risk of an action"""
        low_risk = {
            RemediationAction.NOTIFY_ONLY,
            RemediationAction.SCALE_MEMORY_UP,
            RemediationAction.SCALE_CPU_UP,
        }
        medium_risk = {
            RemediationAction.RESTART_POD,
            RemediationAction.SCALE_REPLICAS_UP,
            RemediationAction.SCALE_REPLICAS_DOWN,
        }
        high_risk = {
            RemediationAction.DELETE_POD,
            RemediationAction.ROLLBACK_DEPLOYMENT,
            RemediationAction.CORDON_NODE,
            RemediationAction.DRAIN_NODE,
        }
        
        if action in low_risk:
            return "LOW - No service disruption expected"
        elif action in medium_risk:
            return "MEDIUM - Brief disruption possible, automatic recovery"
        elif action in high_risk:
            return "HIGH - Service disruption likely, manual verification recommended"
        return "UNKNOWN - Review action carefully"
    
    def _generate_rollback_plan(self, action: RemediationAction, params: Dict[str, Any]) -> str:
        """Generate rollback plan for an action"""
        if action == RemediationAction.SCALE_MEMORY_UP:
            old_mb = params.get("old_memory_bytes", 0) / 1024**2
            return f"Revert memory limit to {old_mb:.0f}Mi"
        elif action == RemediationAction.SCALE_REPLICAS_UP:
            return f"Reduce replicas by {params.get(increase_by, 1)}"
        elif action == RemediationAction.ROLLBACK_DEPLOYMENT:
            return "Roll forward to current revision"
        return "Manual intervention may be required"
    
    def _rollbackable_actions(self) -> set:
        """Actions that can be automatically rolled back"""
        return {
            RemediationAction.SCALE_MEMORY_UP,
            RemediationAction.SCALE_MEMORY_DOWN,
            RemediationAction.SCALE_CPU_UP,
            RemediationAction.SCALE_CPU_DOWN,
            RemediationAction.SCALE_REPLICAS_UP,
            RemediationAction.SCALE_REPLICAS_DOWN,
        }
    
    def _get_rollback_action(self, action: RemediationAction) -> Optional[RemediationAction]:
        """Get the inverse action for rollback"""
        rollback_map = {
            RemediationAction.SCALE_MEMORY_UP: RemediationAction.SCALE_MEMORY_DOWN,
            RemediationAction.SCALE_MEMORY_DOWN: RemediationAction.SCALE_MEMORY_UP,
            RemediationAction.SCALE_CPU_UP: RemediationAction.SCALE_CPU_DOWN,
            RemediationAction.SCALE_CPU_DOWN: RemediationAction.SCALE_CPU_UP,
            RemediationAction.SCALE_REPLICAS_UP: RemediationAction.SCALE_REPLICAS_DOWN,
            RemediationAction.SCALE_REPLICAS_DOWN: RemediationAction.SCALE_REPLICAS_UP,
        }
        return rollback_map.get(action)
    
    def _get_rollback_parameters(self, remediation: Remediation) -> Dict[str, Any]:
        """Generate parameters for rollback"""
        params = remediation.parameters.copy()
        
        # Swap old/new values
        if "old_memory_bytes" in params and "new_memory_bytes" in params:
            params["old_memory_bytes"], params["new_memory_bytes"] = \
                params["new_memory_bytes"], params["old_memory_bytes"]
        
        return params
    
    def _estimate_impact(self, action: RemediationAction, resource: Optional[KubernetesResource]) -> str:
        """Estimate the impact of an action"""
        if action == RemediationAction.NOTIFY_ONLY:
            return "No impact - notification only"
        elif action in (RemediationAction.SCALE_MEMORY_UP, RemediationAction.SCALE_CPU_UP):
            return "Minimal - pod restart required to apply new limits"
        elif action == RemediationAction.RESTART_POD:
            return "Brief - single pod restart (~30 seconds)"
        elif action == RemediationAction.DRAIN_NODE:
            return "Significant - all pods on node will be evicted"
        return "Unknown - review action impact"
    
    def _estimate_duration(self, action: RemediationAction) -> int:
        """Estimate duration in seconds"""
        durations = {
            RemediationAction.NOTIFY_ONLY: 1,
            RemediationAction.SCALE_MEMORY_UP: 60,
            RemediationAction.SCALE_CPU_UP: 60,
            RemediationAction.SCALE_REPLICAS_UP: 120,
            RemediationAction.RESTART_POD: 30,
            RemediationAction.ROLLBACK_DEPLOYMENT: 180,
            RemediationAction.DRAIN_NODE: 300,
        }
        return durations.get(action, 60)
    
    # Action Handlers
    def _handle_scale_memory_up(self, remediation: Remediation) -> bool:
        """Handle memory scaling"""
        logger.info(f"Scaling memory up for {remediation.target_resource}")
        # Implementation would use k8s_client to patch the deployment
        return True
    
    def _handle_scale_memory_down(self, remediation: Remediation) -> bool:
        return True
    
    def _handle_scale_cpu_up(self, remediation: Remediation) -> bool:
        return True
    
    def _handle_scale_cpu_down(self, remediation: Remediation) -> bool:
        return True
    
    def _handle_scale_replicas(self, remediation: Remediation) -> bool:
        return True
    
    def _handle_restart_pod(self, remediation: Remediation) -> bool:
        return True
    
    def _handle_delete_pod(self, remediation: Remediation) -> bool:
        return True
    
    def _handle_rollback_deployment(self, remediation: Remediation) -> bool:
        return True
    
    def _handle_notify_only(self, remediation: Remediation) -> bool:
        logger.info(f"Notification: {remediation.explanation.summary if remediation.explanation else Alert}")
        return True
