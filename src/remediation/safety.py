"""Safety Validator - Ensures remediation actions are safe"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk levels for remediation actions"""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SafetyCheck:
    """Result of a safety check"""
    name: str
    passed: bool
    risk_level: RiskLevel
    message: str
    blocking: bool = False  # If True, action must not proceed


@dataclass
class SafetyValidation:
    """Complete safety validation result"""
    safe: bool
    overall_risk: RiskLevel
    checks: List[SafetyCheck] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    requires_approval: bool = False
    approval_reason: Optional[str] = None
    
    def get_summary(self) -> str:
        """Get human-readable summary"""
        passed = sum(1 for c in self.checks if c.passed)
        total = len(self.checks)
        
        if self.safe:
            return f"SAFE ({passed}/{total} checks passed, risk: {self.overall_risk.value})"
        else:
            failed = [c.name for c in self.checks if not c.passed and c.blocking]
            return f"BLOCKED by: " + ", ".join(failed)


class SafetyValidator:
    """
    Validates remediation actions for safety before execution.
    
    Enforces blast radius limits, rate limiting, and approval gates.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Default safety limits
        self.max_pods_affected_percent = self.config.get("max_pods_affected_percent", 25)
        self.max_nodes_affected_percent = self.config.get("max_nodes_affected_percent", 10)
        self.max_actions_per_hour = self.config.get("max_actions_per_hour", 20)
        self.cooldown_seconds = self.config.get("cooldown_seconds", 60)
        
        # High-risk actions that always require approval
        self.high_risk_actions: Set[str] = {
            "drain_node",
            "rollback_deployment",
            "delete_pod",
            "update_secret",
            "cordon_node",
        }
        
        # Protected namespaces
        self.protected_namespaces: Set[str] = {
            "kube-system",
            "kube-public",
            "kube-node-lease",
            "monitoring",
            "istio-system",
        }
        
        # Protected label selectors (workloads with these labels need approval)
        self.protected_labels: Dict[str, Set[str]] = {
            "app": {"database", "postgres", "mysql", "redis", "elasticsearch"},
            "tier": {"data", "database"},
            "critical": {"true", "yes"},
        }
        
        # Action tracking for rate limiting
        self.action_history: List[datetime] = []
        self.recent_targets: Dict[str, datetime] = {}
    
    def validate(
        self,
        action: str,
        target_resource: Dict[str, Any],
        parameters: Dict[str, Any],
        cluster_state: Optional[Dict[str, Any]] = None,
    ) -> SafetyValidation:
        """
        Validate a remediation action for safety.
        
        Args:
            action: The action type (e.g., "scale_memory_up")
            target_resource: The Kubernetes resource being acted upon
            parameters: Action parameters
            cluster_state: Current cluster state for context
        
        Returns:
            SafetyValidation result
        """
        checks = []
        warnings = []
        requires_approval = False
        approval_reason = None
        
        # Check 1: Rate limiting
        rate_check = self._check_rate_limit()
        checks.append(rate_check)
        
        # Check 2: Cooldown period
        cooldown_check = self._check_cooldown(target_resource)
        checks.append(cooldown_check)
        
        # Check 3: Protected namespace
        namespace_check = self._check_protected_namespace(target_resource)
        checks.append(namespace_check)
        if not namespace_check.passed:
            requires_approval = True
            approval_reason = f"Target is in protected namespace: {target_resource.get('namespace')}"
        
        # Check 4: Protected workload
        workload_check = self._check_protected_workload(target_resource)
        checks.append(workload_check)
        if not workload_check.passed:
            requires_approval = True
            approval_reason = workload_check.message
        
        # Check 5: High-risk action
        if action in self.high_risk_actions:
            checks.append(SafetyCheck(
                name="high_risk_action",
                passed=True,  # Not blocking, but requires approval
                risk_level=RiskLevel.HIGH,
                message=f"Action {action} is classified as high-risk",
                blocking=False,
            ))
            requires_approval = True
            approval_reason = f"High-risk action: {action}"
        
        # Check 6: Blast radius (if cluster state provided)
        if cluster_state:
            blast_check = self._check_blast_radius(action, target_resource, cluster_state)
            checks.append(blast_check)
            if blast_check.risk_level == RiskLevel.HIGH:
                requires_approval = True
                approval_reason = blast_check.message
        
        # Check 7: Resource limits
        resource_check = self._check_resource_limits(action, parameters)
        checks.append(resource_check)
        if resource_check.risk_level >= RiskLevel.MEDIUM:
            warnings.append(resource_check.message)
        
        # Determine overall safety
        blocking_failures = [c for c in checks if not c.passed and c.blocking]
        is_safe = len(blocking_failures) == 0
        
        # Determine overall risk
        risk_levels = [c.risk_level for c in checks]
        if RiskLevel.CRITICAL in risk_levels:
            overall_risk = RiskLevel.CRITICAL
        elif RiskLevel.HIGH in risk_levels:
            overall_risk = RiskLevel.HIGH
        elif RiskLevel.MEDIUM in risk_levels:
            overall_risk = RiskLevel.MEDIUM
        elif RiskLevel.LOW in risk_levels:
            overall_risk = RiskLevel.LOW
        else:
            overall_risk = RiskLevel.NONE
        
        return SafetyValidation(
            safe=is_safe,
            overall_risk=overall_risk,
            checks=checks,
            warnings=warnings,
            requires_approval=requires_approval,
            approval_reason=approval_reason,
        )
    
    def _check_rate_limit(self) -> SafetyCheck:
        """Check if rate limit has been exceeded"""
        now = datetime.utcnow()
        hour_ago = now - timedelta(hours=1)
        
        # Clean old entries
        self.action_history = [t for t in self.action_history if t > hour_ago]
        
        if len(self.action_history) >= self.max_actions_per_hour:
            return SafetyCheck(
                name="rate_limit",
                passed=False,
                risk_level=RiskLevel.HIGH,
                message=f"Rate limit exceeded: {len(self.action_history)}/{self.max_actions_per_hour} actions in last hour",
                blocking=True,
            )
        
        return SafetyCheck(
            name="rate_limit",
            passed=True,
            risk_level=RiskLevel.NONE,
            message=f"Rate limit OK: {len(self.action_history)}/{self.max_actions_per_hour}",
        )
    
    def _check_cooldown(self, target_resource: Dict[str, Any]) -> SafetyCheck:
        """Check if target is in cooldown period"""
        resource_key = f"{target_resource.get('kind')}/{target_resource.get('namespace')}/{target_resource.get('name')}"
        
        if resource_key in self.recent_targets:
            last_action = self.recent_targets[resource_key]
            elapsed = (datetime.utcnow() - last_action).total_seconds()
            
            if elapsed < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - elapsed)
                return SafetyCheck(
                    name="cooldown",
                    passed=False,
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Target in cooldown period, {remaining}s remaining",
                    blocking=True,
                )
        
        return SafetyCheck(
            name="cooldown",
            passed=True,
            risk_level=RiskLevel.NONE,
            message="No cooldown in effect",
        )
    
    def _check_protected_namespace(self, target_resource: Dict[str, Any]) -> SafetyCheck:
        """Check if target is in a protected namespace"""
        namespace = target_resource.get("namespace", "default")
        
        if namespace in self.protected_namespaces:
            return SafetyCheck(
                name="protected_namespace",
                passed=False,
                risk_level=RiskLevel.HIGH,
                message=f"Namespace {namespace} is protected - requires approval",
                blocking=False,  # Allow with approval
            )
        
        return SafetyCheck(
            name="protected_namespace",
            passed=True,
            risk_level=RiskLevel.NONE,
            message="Namespace is not protected",
        )
    
    def _check_protected_workload(self, target_resource: Dict[str, Any]) -> SafetyCheck:
        """Check if target is a protected workload"""
        labels = target_resource.get("labels", {})
        
        for label_key, protected_values in self.protected_labels.items():
            label_value = labels.get(label_key, "").lower()
            if label_value in protected_values:
                return SafetyCheck(
                    name="protected_workload",
                    passed=False,
                    risk_level=RiskLevel.HIGH,
                    message=f"Workload has protected label: {label_key}={label_value}",
                    blocking=False,  # Allow with approval
                )
        
        return SafetyCheck(
            name="protected_workload",
            passed=True,
            risk_level=RiskLevel.NONE,
            message="Workload is not protected",
        )
    
    def _check_blast_radius(
        self,
        action: str,
        target_resource: Dict[str, Any],
        cluster_state: Dict[str, Any],
    ) -> SafetyCheck:
        """Check blast radius of the action"""
        total_pods = cluster_state.get("total_pods", 100)
        total_nodes = cluster_state.get("total_nodes", 3)
        
        affected_pods = 1  # Most actions affect 1 pod
        affected_nodes = 0
        
        if action in ("drain_node", "cordon_node"):
            affected_nodes = 1
            # Estimate pods on node
            affected_pods = total_pods // total_nodes if total_nodes > 0 else total_pods
        
        pod_percent = (affected_pods / total_pods * 100) if total_pods > 0 else 0
        node_percent = (affected_nodes / total_nodes * 100) if total_nodes > 0 else 0
        
        if pod_percent > self.max_pods_affected_percent:
            return SafetyCheck(
                name="blast_radius",
                passed=False,
                risk_level=RiskLevel.CRITICAL,
                message=f"Blast radius too high: {pod_percent:.1f}% of pods affected (max {self.max_pods_affected_percent}%)",
                blocking=True,
            )
        
        if node_percent > self.max_nodes_affected_percent:
            return SafetyCheck(
                name="blast_radius",
                passed=False,
                risk_level=RiskLevel.HIGH,
                message=f"Would affect {node_percent:.1f}% of nodes (max {self.max_nodes_affected_percent}%)",
                blocking=False,
            )
        
        return SafetyCheck(
            name="blast_radius",
            passed=True,
            risk_level=RiskLevel.LOW if pod_percent > 5 else RiskLevel.NONE,
            message=f"Blast radius acceptable: ~{pod_percent:.1f}% pods",
        )
    
    def _check_resource_limits(
        self,
        action: str,
        parameters: Dict[str, Any],
    ) -> SafetyCheck:
        """Validate resource change parameters"""
        if action == "scale_memory_up":
            new_memory = parameters.get("new_memory_bytes", 0)
            max_memory = parameters.get("max_allowed_memory_bytes", 4 * 1024**3)  # 4GB default
            
            if new_memory > max_memory:
                return SafetyCheck(
                    name="resource_limits",
                    passed=False,
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Requested memory {new_memory/1024**3:.1f}GB exceeds maximum {max_memory/1024**3:.1f}GB",
                    blocking=True,
                )
        
        if action == "scale_replicas_up":
            new_replicas = parameters.get("new_replicas", 0)
            max_replicas = parameters.get("max_replicas", 50)
            
            if new_replicas > max_replicas:
                return SafetyCheck(
                    name="resource_limits",
                    passed=False,
                    risk_level=RiskLevel.MEDIUM,
                    message=f"Requested replicas {new_replicas} exceeds maximum {max_replicas}",
                    blocking=True,
                )
        
        return SafetyCheck(
            name="resource_limits",
            passed=True,
            risk_level=RiskLevel.NONE,
            message="Resource parameters within limits",
        )
    
    def record_action(self, target_resource: Dict[str, Any]):
        """Record an executed action for rate limiting and cooldown"""
        now = datetime.utcnow()
        self.action_history.append(now)
        
        resource_key = f"{target_resource.get('kind')}/{target_resource.get('namespace')}/{target_resource.get('name')}"
        self.recent_targets[resource_key] = now
        
        logger.info(f"Recorded action on {resource_key}")
