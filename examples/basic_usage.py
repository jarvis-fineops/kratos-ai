#!/usr/bin/env python3
"""
Basic usage example for Kratos AI

This example demonstrates how to:
1. Initialize the Kratos Brain
2. Submit metrics for prediction
3. Record incidents for learning
4. Get remediation recommendations
"""

import asyncio
from datetime import datetime

# Import Kratos components
import sys
sys.path.insert(0, "../src")

from core.types import (
    Incident,
    IncidentType,
    IncidentSeverity,
    KubernetesResource,
    ResourceMetrics,
)
from core.brain import KratosBrain, KratosMode


async def main():
    # Initialize Kratos Brain in recommendation mode
    print("Initializing Kratos Brain...")
    brain = KratosBrain(mode=KratosMode.RECOMMEND)
    
    # Simulate a resource with metrics
    resource = KubernetesResource(
        kind="Pod",
        name="api-server-abc123",
        namespace="production",
        labels={"app": "api-server", "tier": "backend"},
    )
    
    # Current metrics showing high memory usage
    metrics = ResourceMetrics(
        cpu_usage_cores=0.8,
        cpu_limit_cores=1.0,
        cpu_request_cores=0.5,
        memory_usage_bytes=900 * 1024**2,  # 900Mi
        memory_limit_bytes=1024 * 1024**2,  # 1Gi (88% utilization)
        memory_request_bytes=512 * 1024**2,
    )
    
    print(f"\nResource: {resource.namespace}/{resource.name}")
    print(f"Memory utilization: {metrics.memory_utilization:.1f}%")
    print(f"CPU utilization: {metrics.cpu_utilization:.1f}%")
    
    # Get prediction
    print("\n--- Running Prediction ---")
    prediction = brain.predict_for_resource(resource, metrics)
    
    print(f"Failure predicted: {prediction.probability > 0.5}")
    print(f"Probability: {prediction.probability*100:.1f}%")
    print(f"Incident type: {prediction.incident_type.value}")
    print(f"Confidence: {prediction.confidence.value}")
    if prediction.eta_minutes:
        print(f"ETA: {prediction.eta_minutes:.0f} minutes")
    print("Evidence:")
    for ev in prediction.evidence:
        print(f"  - {ev}")
    
    # Get remediation recommendation
    if prediction.probability > 0.5:
        print("\n--- Remediation Recommendation ---")
        plan = brain.get_recommendations(resource, prediction)
        
        print(f"Recommended action: {plan.remediation.action.value}")
        print(f"Safety: {plan.safety_validation.get_summary()}")
        print(f"Can rollback: {plan.can_rollback}")
        print(f"Estimated duration: {plan.estimated_duration_seconds}s")
        
        if plan.remediation.explanation:
            print("\nExplanation:")
            print(plan.remediation.explanation.to_human_readable())
    
    # Record a sample incident for learning
    print("\n--- Recording Incident for Learning ---")
    incident = Incident(
        type=IncidentType.OOM_KILL,
        severity=IncidentSeverity.HIGH,
        resource=resource,
        message="Container killed due to OOM",
        details={"exit_code": 137, "oom_kill_count": 1},
        metrics_snapshot=metrics,
    )
    
    brain.knowledge_base.record_incident(incident)
    print(f"Incident recorded: {incident.id}")
    
    # Check similar incidents
    similar = brain.get_similar_incidents(incident)
    print(f"Similar past incidents: {len(similar)}")
    
    # Show knowledge base stats
    print("\n--- Knowledge Base Stats ---")
    stats = brain.knowledge_base.get_stats()
    print(f"Total incidents: {stats['total_incidents']}")
    print(f"Total patterns: {stats['total_patterns']}")
    print(f"Incidents by type: {stats['incidents_by_type']}")


if __name__ == "__main__":
    asyncio.run(main())
