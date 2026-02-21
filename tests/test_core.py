"""Tests for Kratos AI core components"""

import pytest
from datetime import datetime

import sys
sys.path.insert(0, "../src")

from core.types import (
    Incident,
    IncidentType,
    IncidentSeverity,
    Prediction,
    Remediation,
    RemediationAction,
    RemediationOutcome,
    KubernetesResource,
    ResourceMetrics,
)
from core.knowledge_base import KnowledgeBase


class TestIncident:
    def test_create_incident(self):
        incident = Incident(
            type=IncidentType.OOM_KILL,
            severity=IncidentSeverity.HIGH,
            message="Pod crashed due to OOM",
        )
        
        assert incident.id is not None
        assert incident.type == IncidentType.OOM_KILL
        assert incident.severity == IncidentSeverity.HIGH
        assert not incident.is_resolved
    
    def test_incident_resolution(self):
        incident = Incident(
            type=IncidentType.CRASH_LOOP,
            message="CrashLoopBackOff",
        )
        
        assert incident.duration_seconds is None
        
        incident.resolved_at = datetime.utcnow()
        
        assert incident.is_resolved
        assert incident.duration_seconds is not None


class TestResourceMetrics:
    def test_utilization_calculation(self):
        metrics = ResourceMetrics(
            cpu_usage_cores=0.5,
            cpu_limit_cores=1.0,
            cpu_request_cores=0.25,
            memory_usage_bytes=512 * 1024**2,
            memory_limit_bytes=1024 * 1024**2,
            memory_request_bytes=256 * 1024**2,
        )
        
        assert metrics.cpu_utilization == 50.0
        assert metrics.memory_utilization == 50.0
    
    def test_zero_limit_handling(self):
        metrics = ResourceMetrics(
            cpu_usage_cores=0.5,
            cpu_limit_cores=0,
            cpu_request_cores=0.25,
            memory_usage_bytes=512 * 1024**2,
            memory_limit_bytes=0,
            memory_request_bytes=256 * 1024**2,
        )
        
        assert metrics.cpu_utilization == 0.0
        assert metrics.memory_utilization == 0.0


class TestKnowledgeBase:
    def test_record_incident(self, tmp_path):
        kb = KnowledgeBase(storage_path=tmp_path / "knowledge")
        
        incident = Incident(
            type=IncidentType.OOM_KILL,
            severity=IncidentSeverity.HIGH,
            message="Test incident",
        )
        
        incident_id = kb.record_incident(incident)
        
        assert incident_id in kb.incidents
        assert IncidentType.OOM_KILL in kb._incident_by_type
    
    def test_find_similar_incidents(self, tmp_path):
        kb = KnowledgeBase(storage_path=tmp_path / "knowledge")
        
        resource = KubernetesResource(
            kind="Pod",
            name="api-server-123",
            namespace="default",
            labels={"app": "api"},
        )
        
        # Record multiple similar incidents
        for i in range(5):
            incident = Incident(
                type=IncidentType.OOM_KILL,
                resource=resource,
                message=f"OOM kill {i}",
            )
            kb.record_incident(incident)
        
        # Find similar
        test_incident = Incident(
            type=IncidentType.OOM_KILL,
            resource=resource,
            message="OOM kill test",
        )
        
        similar = kb.find_similar_incidents(test_incident)
        
        assert len(similar) >= 4  # Should find the previous incidents
    
    def test_pattern_detection(self, tmp_path):
        kb = KnowledgeBase(storage_path=tmp_path / "knowledge")
        kb.min_occurrences_for_pattern = 3
        
        resource = KubernetesResource(
            kind="Pod",
            name="test-pod",
            namespace="default",
        )
        
        # Record enough incidents to trigger pattern detection
        for i in range(5):
            incident = Incident(
                type=IncidentType.CRASH_LOOP,
                resource=resource,
                message="CrashLoopBackOff",
            )
            kb.record_incident(incident)
        
        # Should have detected a pattern
        assert len(kb.patterns) > 0


class TestRemediation:
    def test_create_remediation(self):
        remediation = Remediation(
            action=RemediationAction.SCALE_MEMORY_UP,
            parameters={"new_memory": "2Gi"},
        )
        
        assert remediation.id is not None
        assert not remediation.is_executed
        assert not remediation.is_successful
    
    def test_remediation_execution(self):
        remediation = Remediation(
            action=RemediationAction.RESTART_POD,
        )
        
        remediation.executed_at = datetime.utcnow()
        remediation.outcome = RemediationOutcome.SUCCESS
        
        assert remediation.is_executed
        assert remediation.is_successful


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
