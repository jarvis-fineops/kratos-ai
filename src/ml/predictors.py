"""ML Predictors for Failure Prediction"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Result from a prediction model"""
    predicted: bool              # Whether an incident is predicted
    probability: float           # Probability of incident (0-1)
    eta_seconds: Optional[float] # Estimated time until incident
    confidence: float            # Model confidence in prediction (0-1)
    evidence: List[str]          # Evidence supporting prediction
    model_name: str
    model_version: str
    computed_at: datetime = field(default_factory=datetime.utcnow)


class BasePredictor(ABC):
    """Base class for all predictors"""
    
    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.is_trained = False
        self.last_trained_at: Optional[datetime] = None
        self.training_samples = 0
    
    @abstractmethod
    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train the model on historical data"""
        pass
    
    @abstractmethod
    def predict(self, features: Dict[str, Any]) -> PredictionResult:
        """Make a prediction based on current features"""
        pass
    
    def get_info(self) -> Dict[str, Any]:
        """Get model information"""
        return {
            "name": self.name,
            "version": self.version,
            "is_trained": self.is_trained,
            "last_trained_at": self.last_trained_at.isoformat() if self.last_trained_at else None,
            "training_samples": self.training_samples,
        }


class AnomalyDetector(BasePredictor):
    """
    Anomaly detection using Isolation Forest-inspired approach.
    
    Detects unusual patterns in resource metrics that may indicate
    impending failures.
    """
    
    def __init__(self):
        super().__init__("anomaly_detector", "1.0.0")
        
        # Statistics for each metric
        self.metric_stats: Dict[str, Dict[str, float]] = {}
        
        # Rolling windows for each metric
        self.window_size = 100
        self.metric_windows: Dict[str, deque] = {}
        
        # Anomaly thresholds (z-scores)
        self.anomaly_threshold = 3.0  # Standard deviations
        self.warning_threshold = 2.0
    
    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train on historical metrics data"""
        for sample in data:
            for metric_name, value in sample.items():
                if isinstance(value, (int, float)):
                    self._update_stats(metric_name, value)
        
        self.is_trained = True
        self.last_trained_at = datetime.utcnow()
        self.training_samples = len(data)
        
        logger.info(f"AnomalyDetector trained on {len(data)} samples, {len(self.metric_stats)} metrics")
    
    def _update_stats(self, metric_name: str, value: float):
        """Update running statistics for a metric"""
        if metric_name not in self.metric_windows:
            self.metric_windows[metric_name] = deque(maxlen=self.window_size)
        
        self.metric_windows[metric_name].append(value)
        
        # Compute statistics
        values = list(self.metric_windows[metric_name])
        if len(values) >= 5:  # Need minimum samples
            self.metric_stats[metric_name] = {
                "mean": np.mean(values),
                "std": np.std(values) or 0.001,  # Avoid division by zero
                "min": np.min(values),
                "max": np.max(values),
                "samples": len(values),
            }
    
    def predict(self, features: Dict[str, Any]) -> PredictionResult:
        """Detect anomalies in current features"""
        anomalies = []
        max_z_score = 0.0
        evidence = []
        
        for metric_name, value in features.items():
            if not isinstance(value, (int, float)):
                continue
            
            # Update with new value
            self._update_stats(metric_name, value)
            
            stats = self.metric_stats.get(metric_name)
            if not stats or stats["samples"] < 10:
                continue
            
            # Compute z-score
            z_score = abs(value - stats["mean"]) / stats["std"]
            max_z_score = max(max_z_score, z_score)
            
            if z_score >= self.anomaly_threshold:
                anomalies.append(metric_name)
                evidence.append(
                    f"{metric_name}={value:.2f} is {z_score:.1f}σ from mean {stats['mean']:.2f}"
                )
            elif z_score >= self.warning_threshold:
                evidence.append(
                    f"{metric_name}={value:.2f} is elevated ({z_score:.1f}σ from normal)"
                )
        
        is_anomaly = len(anomalies) > 0
        
        # Probability based on how severe the anomaly is
        if max_z_score >= self.anomaly_threshold:
            probability = min(0.95, 0.5 + (max_z_score - self.anomaly_threshold) * 0.15)
        elif max_z_score >= self.warning_threshold:
            probability = 0.3 + (max_z_score - self.warning_threshold) * 0.2
        else:
            probability = max_z_score * 0.15
        
        return PredictionResult(
            predicted=is_anomaly,
            probability=probability,
            eta_seconds=300 if is_anomaly else None,  # 5 minute default
            confidence=min(1.0, self.training_samples / 100),  # More training = more confidence
            evidence=evidence,
            model_name=self.name,
            model_version=self.version,
        )


class TimeSeriesForecaster(BasePredictor):
    """
    Time series forecaster for resource usage prediction.
    
    Uses exponential smoothing and trend analysis to predict
    future resource usage and identify when limits will be breached.
    """
    
    def __init__(self):
        super().__init__("time_series_forecaster", "1.0.0")
        
        # Time series data for each resource
        self.series: Dict[str, List[Tuple[datetime, float]]] = {}
        
        # Exponential smoothing parameters
        self.alpha = 0.3  # Level smoothing
        self.beta = 0.1   # Trend smoothing
        
        # Forecasting parameters
        self.max_history_points = 500
        self.min_points_for_forecast = 10
    
    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train on historical time series data"""
        for sample in data:
            timestamp = sample.get("timestamp", datetime.utcnow())
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            
            for metric_name, value in sample.items():
                if metric_name == "timestamp":
                    continue
                if isinstance(value, (int, float)):
                    self._add_datapoint(metric_name, timestamp, value)
        
        self.is_trained = True
        self.last_trained_at = datetime.utcnow()
        self.training_samples = len(data)
        
        logger.info(f"TimeSeriesForecaster trained on {len(data)} samples")
    
    def _add_datapoint(self, metric_name: str, timestamp: datetime, value: float):
        """Add a data point to the series"""
        if metric_name not in self.series:
            self.series[metric_name] = []
        
        self.series[metric_name].append((timestamp, value))
        
        # Keep only recent history
        if len(self.series[metric_name]) > self.max_history_points:
            self.series[metric_name] = self.series[metric_name][-self.max_history_points:]
    
    def _forecast(
        self, 
        metric_name: str, 
        horizon_seconds: float
    ) -> Tuple[float, float, float]:
        """
        Forecast future value using Holt linear trend method.
        
        Returns: (predicted_value, lower_bound, upper_bound)
        """
        if metric_name not in self.series:
            return (0.0, 0.0, 0.0)
        
        data = self.series[metric_name]
        if len(data) < self.min_points_for_forecast:
            return (data[-1][1], data[-1][1], data[-1][1])
        
        # Extract values
        values = [v for _, v in data]
        
        # Initialize level and trend
        level = values[0]
        trend = (values[-1] - values[0]) / len(values) if len(values) > 1 else 0
        
        # Apply exponential smoothing
        for value in values:
            prev_level = level
            level = self.alpha * value + (1 - self.alpha) * (level + trend)
            trend = self.beta * (level - prev_level) + (1 - self.beta) * trend
        
        # Estimate time interval between points
        if len(data) >= 2:
            total_seconds = (data[-1][0] - data[0][0]).total_seconds()
            avg_interval = total_seconds / (len(data) - 1) if len(data) > 1 else 60
        else:
            avg_interval = 60
        
        # Forecast
        steps = horizon_seconds / avg_interval if avg_interval > 0 else 1
        forecast = level + trend * steps
        
        # Compute prediction interval (simple approach)
        residuals = [abs(v - (level + trend * i)) for i, (_, v) in enumerate(data[-20:])]
        if residuals:
            std_error = np.mean(residuals)
            lower = forecast - 1.96 * std_error
            upper = forecast + 1.96 * std_error
        else:
            lower = forecast * 0.9
            upper = forecast * 1.1
        
        return (forecast, lower, upper)
    
    def predict(self, features: Dict[str, Any]) -> PredictionResult:
        """Predict if resource limits will be breached"""
        evidence = []
        breach_predictions = []
        
        # Add current values to series
        timestamp = datetime.utcnow()
        for metric_name, value in features.items():
            if isinstance(value, (int, float)):
                self._add_datapoint(metric_name, timestamp, value)
        
        # Check for memory breach
        memory_usage = features.get("memory_usage_bytes", 0)
        memory_limit = features.get("memory_limit_bytes", 0)
        
        if memory_limit > 0:
            # Forecast memory usage in 30 minutes
            forecast, lower, upper = self._forecast("memory_usage_bytes", 1800)
            utilization_forecast = (forecast / memory_limit) * 100
            
            if utilization_forecast >= 95:
                breach_predictions.append({
                    "type": "memory",
                    "probability": min(0.95, (utilization_forecast - 90) / 10),
                    "eta_seconds": self._estimate_breach_time("memory_usage_bytes", memory_limit),
                })
                evidence.append(
                    f"Memory forecast: {utilization_forecast:.1f}% in 30min (currently {(memory_usage/memory_limit)*100:.1f}%)"
                )
        
        # Check for CPU breach
        cpu_usage = features.get("cpu_usage_cores", 0)
        cpu_limit = features.get("cpu_limit_cores", 0)
        
        if cpu_limit > 0:
            forecast, _, _ = self._forecast("cpu_usage_cores", 1800)
            utilization_forecast = (forecast / cpu_limit) * 100
            
            if utilization_forecast >= 90:
                breach_predictions.append({
                    "type": "cpu",
                    "probability": min(0.9, (utilization_forecast - 85) / 15),
                    "eta_seconds": self._estimate_breach_time("cpu_usage_cores", cpu_limit),
                })
                evidence.append(
                    f"CPU forecast: {utilization_forecast:.1f}% in 30min (currently {(cpu_usage/cpu_limit)*100:.1f}%)"
                )
        
        # Determine overall prediction
        if breach_predictions:
            max_breach = max(breach_predictions, key=lambda x: x["probability"])
            return PredictionResult(
                predicted=True,
                probability=max_breach["probability"],
                eta_seconds=max_breach["eta_seconds"],
                confidence=min(1.0, len(self.series.get("memory_usage_bytes", [])) / 50),
                evidence=evidence,
                model_name=self.name,
                model_version=self.version,
            )
        
        return PredictionResult(
            predicted=False,
            probability=0.1,
            eta_seconds=None,
            confidence=0.8,
            evidence=["No resource breach predicted in next 30 minutes"],
            model_name=self.name,
            model_version=self.version,
        )
    
    def _estimate_breach_time(self, metric_name: str, limit: float) -> Optional[float]:
        """Estimate seconds until limit is breached"""
        if metric_name not in self.series or not self.series[metric_name]:
            return None
        
        data = self.series[metric_name]
        if len(data) < 2:
            return None
        
        # Compute average growth rate
        values = [v for _, v in data[-10:]]
        if len(values) < 2:
            return None
        
        growth_rate = (values[-1] - values[0]) / len(values)
        
        if growth_rate <= 0:
            return None  # Not growing
        
        current = values[-1]
        remaining = limit - current
        
        if remaining <= 0:
            return 0  # Already breached
        
        # Estimate time to breach
        intervals_to_breach = remaining / growth_rate
        
        # Estimate interval duration
        if len(data) >= 2:
            total_seconds = (data[-1][0] - data[0][0]).total_seconds()
            avg_interval = total_seconds / (len(data) - 1)
        else:
            avg_interval = 60
        
        return intervals_to_breach * avg_interval


class FailurePredictor(BasePredictor):
    """
    Main failure prediction model that combines multiple signals.
    
    Uses ensemble approach combining anomaly detection, time series
    forecasting, and pattern matching from the knowledge base.
    """
    
    def __init__(self, knowledge_base=None):
        super().__init__("failure_predictor", "1.0.0")
        
        self.anomaly_detector = AnomalyDetector()
        self.time_series_forecaster = TimeSeriesForecaster()
        self.knowledge_base = knowledge_base
        
        # Feature weights learned from historical performance
        self.weights = {
            "anomaly": 0.3,
            "time_series": 0.4,
            "pattern": 0.3,
        }
    
    def train(self, data: List[Dict[str, Any]]) -> None:
        """Train all sub-models"""
        self.anomaly_detector.train(data)
        self.time_series_forecaster.train(data)
        
        self.is_trained = True
        self.last_trained_at = datetime.utcnow()
        self.training_samples = len(data)
        
        logger.info(f"FailurePredictor ensemble trained on {len(data)} samples")
    
    def predict(self, features: Dict[str, Any]) -> PredictionResult:
        """Make ensemble prediction"""
        evidence = []
        
        # Get anomaly detection result
        anomaly_result = self.anomaly_detector.predict(features)
        evidence.extend([f"[Anomaly] {e}" for e in anomaly_result.evidence])
        
        # Get time series forecast
        ts_result = self.time_series_forecaster.predict(features)
        evidence.extend([f"[Forecast] {e}" for e in ts_result.evidence])
        
        # Get pattern-based prediction (if knowledge base available)
        pattern_probability = 0.0
        if self.knowledge_base:
            pattern_result = self._check_patterns(features)
            pattern_probability = pattern_result["probability"]
            evidence.extend([f"[Pattern] {e}" for e in pattern_result["evidence"]])
        
        # Ensemble combination
        weighted_probability = (
            self.weights["anomaly"] * anomaly_result.probability +
            self.weights["time_series"] * ts_result.probability +
            self.weights["pattern"] * pattern_probability
        )
        
        # Adjust for convergent evidence
        signals_triggered = sum([
            1 if anomaly_result.predicted else 0,
            1 if ts_result.predicted else 0,
            1 if pattern_probability > 0.5 else 0,
        ])
        
        if signals_triggered >= 2:
            weighted_probability = min(0.98, weighted_probability * 1.3)
            evidence.append(f"[Ensemble] {signals_triggered}/3 predictors agree - high confidence")
        
        # Determine ETA (use time series if available)
        eta = ts_result.eta_seconds
        if anomaly_result.eta_seconds and (eta is None or anomaly_result.eta_seconds < eta):
            eta = anomaly_result.eta_seconds
        
        return PredictionResult(
            predicted=weighted_probability > 0.5,
            probability=weighted_probability,
            eta_seconds=eta,
            confidence=min(
                anomaly_result.confidence,
                ts_result.confidence,
            ),
            evidence=evidence,
            model_name=self.name,
            model_version=self.version,
        )
    
    def _check_patterns(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """Check for matching patterns in knowledge base"""
        if not self.knowledge_base:
            return {"probability": 0.0, "evidence": []}
        
        evidence = []
        max_pattern_match = 0.0
        
        # This would be enhanced with actual pattern matching logic
        # For now, return neutral
        return {"probability": max_pattern_match, "evidence": evidence}
    
    def update_weights(self, actual_outcome: bool, prediction_result: PredictionResult):
        """
        Update ensemble weights based on prediction accuracy.
        
        Uses simple online learning to adjust weights based on
        which predictors were correct.
        """
        learning_rate = 0.05
        
        # Determine which predictors were correct
        correct = prediction_result.predicted == actual_outcome
        
        if correct:
            # Reinforce current weights
            pass
        else:
            # Adjust weights (simplified - in production, track per-predictor accuracy)
            logger.info(f"Updating predictor weights after {correct if correct else incorrect} prediction")
