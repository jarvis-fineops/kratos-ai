"""Knowledge Base - Learns from every incident"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import hashlib

from .types import (
    Incident,
    IncidentType,
    IncidentSeverity,
    Pattern,
    Remediation,
    RemediationAction,
    RemediationOutcome,
    KubernetesResource,
)

logger = logging.getLogger(__name__)


@dataclass
class IncidentFingerprint:
    """Unique fingerprint for incident similarity matching"""
    incident_type: IncidentType
    resource_kind: str
    namespace: str
    label_hash: str  # Hash of sorted labels
    error_pattern: str  # Normalized error message pattern
    
    def to_hash(self) -> str:
        """Generate unique hash for this fingerprint"""
        content = f"{self.incident_type}:{self.resource_kind}:{self.namespace}:{self.label_hash}:{self.error_pattern}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class KnowledgeBase:
    """
    Central knowledge store for Kratos AI.
    
    Stores incidents, patterns, and remediation history.
    Learns from every incident to improve future predictions.
    """
    
    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path("/var/lib/kratos-ai/knowledge")
        
        # In-memory stores (backed by persistent storage)
        self.incidents: Dict[str, Incident] = {}
        self.patterns: Dict[str, Pattern] = {}
        self.remediations: Dict[str, Remediation] = {}
        
        # Indexes for fast lookup
        self._incident_by_type: Dict[IncidentType, List[str]] = defaultdict(list)
        self._incident_by_resource: Dict[str, List[str]] = defaultdict(list)
        self._incident_by_fingerprint: Dict[str, List[str]] = defaultdict(list)
        self._remediation_success_rate: Dict[Tuple[IncidentType, RemediationAction], List[bool]] = defaultdict(list)
        
        # Pattern detection thresholds
        self.min_occurrences_for_pattern = 3
        self.similarity_threshold = 0.8
        self.pattern_decay_days = 90  # Patterns older than this lose weight
        
        self._load_from_storage()
    
    def _load_from_storage(self):
        """Load knowledge base from persistent storage"""
        if not self.storage_path.exists():
            self.storage_path.mkdir(parents=True, exist_ok=True)
            return
        
        # Load incidents
        incidents_file = self.storage_path / "incidents.jsonl"
        if incidents_file.exists():
            with open(incidents_file) as f:
                for line in f:
                    try:
                        data = json.loads(line)
                        incident = self._dict_to_incident(data)
                        self._index_incident(incident)
                    except Exception as e:
                        logger.warning(f"Failed to load incident: {e}")
        
        # Load patterns
        patterns_file = self.storage_path / "patterns.json"
        if patterns_file.exists():
            with open(patterns_file) as f:
                data = json.load(f)
                for p_data in data:
                    pattern = Pattern(**p_data)
                    self.patterns[pattern.id] = pattern
        
        logger.info(f"Loaded {len(self.incidents)} incidents, {len(self.patterns)} patterns")
    
    def _save_incident(self, incident: Incident):
        """Append incident to storage"""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        incidents_file = self.storage_path / "incidents.jsonl"
        
        with open(incidents_file, "a") as f:
            f.write(json.dumps(self._incident_to_dict(incident)) + "\n")
    
    def _save_patterns(self):
        """Save all patterns to storage"""
        self.storage_path.mkdir(parents=True, exist_ok=True)
        patterns_file = self.storage_path / "patterns.json"
        
        patterns_data = []
        for pattern in self.patterns.values():
            patterns_data.append({
                "id": pattern.id,
                "name": pattern.name,
                "description": pattern.description,
                "incident_types": [t.value for t in pattern.incident_types],
                "indicators": pattern.indicators,
                "recommended_actions": [a.value for a in pattern.recommended_actions],
                "success_rate": pattern.success_rate,
                "occurrence_count": pattern.occurrence_count,
                "last_seen": pattern.last_seen.isoformat() if pattern.last_seen else None,
                "confidence": pattern.confidence,
            })
        
        with open(patterns_file, "w") as f:
            json.dump(patterns_data, f, indent=2)
    
    def _incident_to_dict(self, incident: Incident) -> Dict:
        """Convert incident to serializable dict"""
        return {
            "id": incident.id,
            "type": incident.type.value,
            "severity": incident.severity.value,
            "resource": {
                "kind": incident.resource.kind,
                "name": incident.resource.name,
                "namespace": incident.resource.namespace,
                "labels": incident.resource.labels,
            } if incident.resource else None,
            "message": incident.message,
            "details": incident.details,
            "occurred_at": incident.occurred_at.isoformat(),
            "detected_at": incident.detected_at.isoformat(),
            "resolved_at": incident.resolved_at.isoformat() if incident.resolved_at else None,
            "root_cause": incident.root_cause,
            "tags": incident.tags,
        }
    
    def _dict_to_incident(self, data: Dict) -> Incident:
        """Convert dict back to incident"""
        resource = None
        if data.get("resource"):
            resource = KubernetesResource(
                kind=data["resource"]["kind"],
                name=data["resource"]["name"],
                namespace=data["resource"]["namespace"],
                labels=data["resource"].get("labels", {}),
            )
        
        return Incident(
            id=data["id"],
            type=IncidentType(data["type"]),
            severity=IncidentSeverity(data["severity"]),
            resource=resource,
            message=data["message"],
            details=data.get("details", {}),
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            detected_at=datetime.fromisoformat(data["detected_at"]),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            root_cause=data.get("root_cause"),
            tags=data.get("tags", []),
        )
    
    def _compute_fingerprint(self, incident: Incident) -> IncidentFingerprint:
        """Compute fingerprint for incident similarity matching"""
        resource = incident.resource or KubernetesResource(kind="Unknown", name="", namespace="default")
        
        # Hash sorted labels
        label_items = sorted(resource.labels.items())
        label_str = "|".join(f"{k}={v}" for k, v in label_items)
        label_hash = hashlib.md5(label_str.encode()).hexdigest()[:8]
        
        # Normalize error message to pattern
        error_pattern = self._normalize_error_message(incident.message)
        
        return IncidentFingerprint(
            incident_type=incident.type,
            resource_kind=resource.kind,
            namespace=resource.namespace,
            label_hash=label_hash,
            error_pattern=error_pattern,
        )
    
    def _normalize_error_message(self, message: str) -> str:
        """Normalize error message to a pattern by removing variable parts"""
        import re
        
        # Remove UUIDs
        normalized = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "<UUID>", message)
        
        # Remove timestamps
        normalized = re.sub(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}", "<TIMESTAMP>", normalized)
        
        # Remove IP addresses
        normalized = re.sub(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", "<IP>", normalized)
        
        # Remove numbers (but keep error codes)
        normalized = re.sub(r"(?<![A-Z])\d{3,}(?![A-Z])", "<NUM>", normalized)
        
        # Remove pod-specific suffixes
        normalized = re.sub(r"-[a-z0-9]{5,10}(-[a-z0-9]{5})?", "-<POD_SUFFIX>", normalized)
        
        return normalized.lower().strip()
    
    def _index_incident(self, incident: Incident):
        """Add incident to all indexes"""
        self.incidents[incident.id] = incident
        
        # Index by type
        self._incident_by_type[incident.type].append(incident.id)
        
        # Index by resource
        if incident.resource:
            resource_key = f"{incident.resource.kind}/{incident.resource.namespace}/{incident.resource.name}"
            self._incident_by_resource[resource_key].append(incident.id)
        
        # Index by fingerprint
        fingerprint = self._compute_fingerprint(incident)
        self._incident_by_fingerprint[fingerprint.to_hash()].append(incident.id)
    
    def record_incident(self, incident: Incident) -> str:
        """
        Record a new incident and trigger pattern learning.
        
        Returns the incident ID.
        """
        self._index_incident(incident)
        self._save_incident(incident)
        
        # Trigger pattern detection
        self._detect_patterns(incident)
        
        logger.info(f"Recorded incident {incident.id}: {incident.type.value} - {incident.message[:50]}")
        return incident.id
    
    def record_remediation(self, remediation: Remediation):
        """Record a remediation and its outcome for learning"""
        self.remediations[remediation.id] = remediation
        
        # Track success rate by incident type + action
        if remediation.incident_id:
            incident = self.incidents.get(remediation.incident_id)
            if incident:
                key = (incident.type, remediation.action)
                success = remediation.outcome in (RemediationOutcome.SUCCESS, RemediationOutcome.PARTIAL_SUCCESS)
                self._remediation_success_rate[key].append(success)
                
                # Update pattern success rates
                self._update_pattern_success_rates(incident.type, remediation.action, success)
        
        logger.info(f"Recorded remediation {remediation.id}: {remediation.action.value} -> {remediation.outcome.value}")
    
    def find_similar_incidents(
        self, 
        incident: Incident, 
        max_results: int = 10,
        max_age_days: int = 90
    ) -> List[Incident]:
        """Find incidents similar to the given one"""
        fingerprint = self._compute_fingerprint(incident)
        similar_ids = self._incident_by_fingerprint.get(fingerprint.to_hash(), [])
        
        cutoff = datetime.utcnow() - timedelta(days=max_age_days)
        similar = []
        
        for inc_id in similar_ids:
            if inc_id == incident.id:
                continue
            inc = self.incidents.get(inc_id)
            if inc and inc.occurred_at >= cutoff:
                similar.append(inc)
        
        # Sort by recency
        similar.sort(key=lambda x: x.occurred_at, reverse=True)
        return similar[:max_results]
    
    def get_recommended_actions(
        self, 
        incident_type: IncidentType
    ) -> List[Tuple[RemediationAction, float]]:
        """
        Get recommended remediation actions for an incident type,
        sorted by historical success rate.
        """
        recommendations = []
        
        for (inc_type, action), outcomes in self._remediation_success_rate.items():
            if inc_type == incident_type and len(outcomes) >= 2:
                success_rate = sum(outcomes) / len(outcomes)
                recommendations.append((action, success_rate))
        
        # Also check patterns
        for pattern in self.patterns.values():
            if incident_type in pattern.incident_types:
                for action in pattern.recommended_actions:
                    # Check if already in recommendations
                    existing = [r for r in recommendations if r[0] == action]
                    if not existing:
                        recommendations.append((action, pattern.success_rate))
        
        # Sort by success rate descending
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations
    
    def _detect_patterns(self, new_incident: Incident):
        """Detect new patterns from accumulated incidents"""
        fingerprint = self._compute_fingerprint(new_incident)
        similar_ids = self._incident_by_fingerprint.get(fingerprint.to_hash(), [])
        
        if len(similar_ids) >= self.min_occurrences_for_pattern:
            # Check if pattern already exists
            pattern_name = f"{new_incident.type.value}_{fingerprint.to_hash()}"
            existing_pattern = None
            
            for p in self.patterns.values():
                if p.name == pattern_name:
                    existing_pattern = p
                    break
            
            if existing_pattern:
                # Update existing pattern
                existing_pattern.occurrence_count = len(similar_ids)
                existing_pattern.last_seen = datetime.utcnow()
                existing_pattern.confidence = min(1.0, len(similar_ids) / 10)  # Max confidence at 10 occurrences
            else:
                # Create new pattern
                indicators = self._extract_indicators(
                    [self.incidents[id] for id in similar_ids if id in self.incidents]
                )
                
                pattern = Pattern(
                    name=pattern_name,
                    description=f"Auto-detected pattern for {new_incident.type.value} incidents",
                    incident_types=[new_incident.type],
                    indicators=indicators,
                    recommended_actions=self._infer_actions(new_incident.type),
                    success_rate=0.5,  # Start with neutral
                    occurrence_count=len(similar_ids),
                    last_seen=datetime.utcnow(),
                    confidence=len(similar_ids) / 10,
                )
                
                self.patterns[pattern.id] = pattern
                logger.info(f"Detected new pattern: {pattern.name}")
            
            self._save_patterns()
    
    def _extract_indicators(self, incidents: List[Incident]) -> Dict[str, Any]:
        """Extract common indicators from a set of similar incidents"""
        indicators = {
            "common_namespace": None,
            "common_labels": {},
            "typical_severity": None,
            "avg_duration_seconds": None,
            "common_root_causes": [],
        }
        
        if not incidents:
            return indicators
        
        # Find common namespace
        namespaces = [i.resource.namespace for i in incidents if i.resource]
        if namespaces and len(set(namespaces)) == 1:
            indicators["common_namespace"] = namespaces[0]
        
        # Find common labels
        all_labels = [i.resource.labels for i in incidents if i.resource]
        if all_labels:
            common_keys = set.intersection(*[set(l.keys()) for l in all_labels])
            for key in common_keys:
                values = [l[key] for l in all_labels]
                if len(set(values)) == 1:
                    indicators["common_labels"][key] = values[0]
        
        # Most common severity
        severities = [i.severity for i in incidents]
        indicators["typical_severity"] = max(set(severities), key=severities.count).value
        
        # Average duration
        durations = [i.duration_seconds for i in incidents if i.duration_seconds]
        if durations:
            indicators["avg_duration_seconds"] = sum(durations) / len(durations)
        
        # Common root causes
        root_causes = [i.root_cause for i in incidents if i.root_cause]
        if root_causes:
            cause_counts = defaultdict(int)
            for cause in root_causes:
                cause_counts[cause] += 1
            indicators["common_root_causes"] = sorted(
                cause_counts.keys(), 
                key=lambda x: cause_counts[x], 
                reverse=True
            )[:3]
        
        return indicators
    
    def _infer_actions(self, incident_type: IncidentType) -> List[RemediationAction]:
        """Infer recommended actions based on incident type"""
        action_map = {
            IncidentType.OOM_KILL: [RemediationAction.SCALE_MEMORY_UP, RemediationAction.RESTART_POD],
            IncidentType.CRASH_LOOP: [RemediationAction.RESTART_POD, RemediationAction.ROLLBACK_DEPLOYMENT],
            IncidentType.IMAGE_PULL_FAIL: [RemediationAction.NO_ACTION],  # Usually needs manual fix
            IncidentType.READINESS_FAIL: [RemediationAction.RESTART_POD],
            IncidentType.LIVENESS_FAIL: [RemediationAction.RESTART_POD],
            IncidentType.NODE_NOT_READY: [RemediationAction.CORDON_NODE, RemediationAction.DRAIN_NODE],
            IncidentType.NODE_MEMORY_PRESSURE: [RemediationAction.DRAIN_NODE],
            IncidentType.NODE_DISK_PRESSURE: [RemediationAction.DRAIN_NODE],
            IncidentType.RESOURCE_EXHAUSTION: [RemediationAction.SCALE_REPLICAS_UP, RemediationAction.SCALE_CPU_UP],
            IncidentType.EVICTION: [RemediationAction.SCALE_MEMORY_UP],
            IncidentType.PENDING_POD: [RemediationAction.SCALE_REPLICAS_DOWN],
            IncidentType.SCALING_ISSUE: [RemediationAction.SCALE_REPLICAS_UP],
            IncidentType.DEPLOYMENT_FAIL: [RemediationAction.ROLLBACK_DEPLOYMENT],
        }
        
        return action_map.get(incident_type, [RemediationAction.NOTIFY_ONLY])
    
    def _update_pattern_success_rates(
        self, 
        incident_type: IncidentType, 
        action: RemediationAction, 
        success: bool
    ):
        """Update success rates in patterns that match this incident type"""
        for pattern in self.patterns.values():
            if incident_type in pattern.incident_types and action in pattern.recommended_actions:
                # Exponential moving average
                alpha = 0.1  # Learning rate
                pattern.success_rate = alpha * (1.0 if success else 0.0) + (1 - alpha) * pattern.success_rate
        
        self._save_patterns()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get knowledge base statistics"""
        return {
            "total_incidents": len(self.incidents),
            "total_patterns": len(self.patterns),
            "total_remediations": len(self.remediations),
            "incidents_by_type": {
                t.value: len(ids) for t, ids in self._incident_by_type.items()
            },
            "top_patterns": [
                {"name": p.name, "occurrences": p.occurrence_count, "success_rate": p.success_rate}
                for p in sorted(self.patterns.values(), key=lambda x: x.occurrence_count, reverse=True)[:5]
            ],
        }
