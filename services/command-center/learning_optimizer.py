# services/command-center/learning_optimizer.py
"""
Phase XXIII-D: Learning Optimization & Continuous Improvement

This module implements reinforcement learning for the adaptive AI system:
- Dynamic confidence thresholds per alert type
- Feedback weighting from operator interactions
- Outcome tracking and success rate analysis
- Continuous model improvement through data-driven adjustments
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Prometheus metrics (optional)
try:
    from prometheus_client import Gauge

    ADAPTIVE_CURRENT_THRESHOLD = Gauge(
        "aetherlink_adaptive_current_threshold",
        "Current dynamic confidence threshold for alert types",
        ["alert_type"],
    )
except ImportError:
    # Fallback for when prometheus_client is not available
    class DummyGauge:
        def labels(self, **kwargs):
            return self

        def set(self, value):
            pass

    ADAPTIVE_CURRENT_THRESHOLD = DummyGauge()

# Configuration constants
MAX_HISTORY_PER_TYPE = 1000  # Maximum historical actions to keep per alert type
MIN_SAMPLES_FOR_ADAPTATION = 10  # Minimum samples before adapting thresholds
CONFIDENCE_DECAY_FACTOR = 0.95  # How much past performance influences current thresholds
FEEDBACK_WEIGHT_MULTIPLIER = 0.1  # How much operator feedback influences thresholds


@dataclass
class AlertTypePerformance:
    """Tracks performance metrics for a specific alert type."""

    alert_type: str
    total_actions: int = 0
    successful_actions: int = 0
    failed_actions: int = 0
    auto_actions: int = 0
    manual_actions: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0

    # Rolling history of recent actions (alert_id, success, was_auto, timestamp)
    recent_actions: deque[tuple[str, bool, bool, datetime]] = field(
        default_factory=lambda: deque(maxlen=MAX_HISTORY_PER_TYPE)
    )

    # Dynamic confidence threshold (starts at 0.9, adapts based on performance)
    current_threshold: float = 0.9

    # Success rate over different time windows
    success_rate_1h: float = 0.0
    success_rate_24h: float = 0.0
    success_rate_7d: float = 0.0

    def success_rate(self) -> float:
        """Calculate overall success rate."""
        if self.total_actions == 0:
            return 0.0
        return self.successful_actions / self.total_actions

    def auto_success_rate(self) -> float:
        """Calculate success rate for automated actions."""
        if self.auto_actions == 0:
            return 0.0
        # Count successful auto actions
        successful_auto = sum(
            1 for _, success, was_auto, _ in self.recent_actions if success and was_auto
        )
        return successful_auto / self.auto_actions if self.auto_actions > 0 else 0.0

    def update_success_rates(self) -> None:
        """Update success rates for different time windows."""
        now = datetime.now()
        windows = [
            (timedelta(hours=1), "success_rate_1h"),
            (timedelta(hours=24), "success_rate_24h"),
            (timedelta(days=7), "success_rate_7d"),
        ]

        for delta, attr_name in windows:
            cutoff = now - delta
            recent = [action for action in self.recent_actions if action[3] >= cutoff]
            if recent:
                success_count = sum(1 for _, success, _, _ in recent if success)
                rate = success_count / len(recent)
                setattr(self, attr_name, rate)
            else:
                setattr(self, attr_name, 0.0)

    def adapt_threshold(self) -> float:
        """Adapt confidence threshold based on performance and feedback."""
        if self.total_actions < MIN_SAMPLES_FOR_ADAPTATION:
            return self.current_threshold

        # Base threshold adjustment on success rate
        success_rate = self.success_rate()
        auto_success_rate = self.auto_success_rate()

        # If auto actions are performing well, we can be more aggressive
        if auto_success_rate > 0.8 and success_rate > 0.7:
            target_threshold = max(
                0.7, self.current_threshold - 0.05
            )  # Lower threshold = more automation
        elif auto_success_rate < 0.6 or success_rate < 0.5:
            target_threshold = min(
                0.95, self.current_threshold + 0.05
            )  # Higher threshold = less automation
        else:
            target_threshold = self.current_threshold

        # Apply feedback weighting
        feedback_ratio = (self.positive_feedback - self.negative_feedback) / max(
            1, self.positive_feedback + self.negative_feedback
        )
        feedback_adjustment = feedback_ratio * FEEDBACK_WEIGHT_MULTIPLIER
        target_threshold = max(0.5, min(0.99, target_threshold + feedback_adjustment))

        # Smooth transition using exponential moving average
        self.current_threshold = (
            CONFIDENCE_DECAY_FACTOR * self.current_threshold
            + (1 - CONFIDENCE_DECAY_FACTOR) * target_threshold
        )

        # Update Prometheus gauge
        ADAPTIVE_CURRENT_THRESHOLD.labels(alert_type=self.alert_type).set(self.current_threshold)

        logger.info(
            f"Adapted threshold for {self.alert_type}: {self.current_threshold:.3f} "
            f"(success_rate={success_rate:.3f}, auto_success_rate={auto_success_rate:.3f}, "
            f"feedback_ratio={feedback_ratio:.3f})"
        )

        return self.current_threshold


@dataclass
class LearningState:
    """Global learning state for the adaptive system."""

    alert_type_performance: dict[str, AlertTypePerformance] = field(default_factory=dict)
    global_stats: dict[str, Any] = field(default_factory=dict)

    def get_or_create_performance(self, alert_type: str) -> AlertTypePerformance:
        """Get or create performance tracker for an alert type."""
        if alert_type not in self.alert_type_performance:
            self.alert_type_performance[alert_type] = AlertTypePerformance(alert_type=alert_type)
        return self.alert_type_performance[alert_type]

    def record_action(self, alert_type: str, alert_id: str, success: bool, was_auto: bool) -> None:
        """Record an action outcome."""
        perf = self.get_or_create_performance(alert_type)
        perf.total_actions += 1
        if success:
            perf.successful_actions += 1
        else:
            perf.failed_actions += 1

        if was_auto:
            perf.auto_actions += 1
        else:
            perf.manual_actions += 1

        perf.recent_actions.append((alert_id, success, was_auto, datetime.now()))
        perf.update_success_rates()
        perf.adapt_threshold()

    def record_feedback(self, alert_type: str, feedback: str) -> None:
        """Record operator feedback."""
        perf = self.get_or_create_performance(alert_type)
        if feedback == "good" or feedback == "positive":
            perf.positive_feedback += 1
        elif feedback == "bad" or feedback == "negative":
            perf.negative_feedback += 1

        # Re-adapt threshold after feedback
        perf.adapt_threshold()

    def get_dynamic_threshold(self, alert_type: str) -> float:
        """Get the current dynamic threshold for an alert type."""
        perf = self.get_or_create_performance(alert_type)
        return perf.current_threshold

    def get_performance_summary(self) -> dict[str, Any]:
        """Get a summary of learning performance across all alert types."""
        summary = {
            "total_alert_types": len(self.alert_type_performance),
            "total_actions": sum(p.total_actions for p in self.alert_type_performance.values()),
            "total_auto_actions": sum(p.auto_actions for p in self.alert_type_performance.values()),
            "overall_success_rate": 0.0,
            "auto_success_rate": 0.0,
            "alert_type_breakdown": {},
        }

        if summary["total_actions"] > 0:
            total_successful = sum(
                p.successful_actions for p in self.alert_type_performance.values()
            )
            summary["overall_success_rate"] = total_successful / summary["total_actions"]

        if summary["total_auto_actions"] > 0:
            total_auto_successful = sum(
                sum(1 for _, success, was_auto, _ in p.recent_actions if success and was_auto)
                for p in self.alert_type_performance.values()
            )
            summary["auto_success_rate"] = total_auto_successful / summary["total_auto_actions"]

        # Per-type breakdown
        for alert_type, perf in self.alert_type_performance.items():
            summary["alert_type_breakdown"][alert_type] = {
                "total_actions": perf.total_actions,
                "success_rate": perf.success_rate(),
                "auto_success_rate": perf.auto_success_rate(),
                "current_threshold": perf.current_threshold,
                "positive_feedback": perf.positive_feedback,
                "negative_feedback": perf.negative_feedback,
                "success_rates": {
                    "1h": perf.success_rate_1h,
                    "24h": perf.success_rate_24h,
                    "7d": perf.success_rate_7d,
                },
            }

        return summary


# Global learning state instance
LEARNING_STATE = LearningState()


def analyze_learning_patterns(
    audit_data: list[dict[str, Any]], window_hours: int = 24
) -> dict[str, Any]:
    """
    Analyze audit data to extract learning insights and update the learning state.
    This is called periodically to improve the system's understanding.
    """
    cutoff_time = datetime.now() - timedelta(hours=window_hours)
    recent_audits = [
        entry
        for entry in audit_data
        if datetime.fromisoformat(entry.get("timestamp", "2000-01-01T00:00:00Z").replace("Z", ""))
        >= cutoff_time
    ]

    # Process recent actions to update learning state
    for entry in recent_audits:
        operation = entry.get("operation", "")
        metadata = entry.get("metadata", {})

        # Track alert acknowledgments
        if operation == "operator.alert.ack":
            alert_id = metadata.get("alert_id")
            was_auto = metadata.get("applied") == "adaptive.auto"
            # For now, assume all acks are successful (we could add failure detection later)
            success = True

            # Try to infer alert type from metadata or use generic
            alert_type = metadata.get("alert_type", "unknown")
            LEARNING_STATE.record_action(alert_type, alert_id, success, was_auto)

        # Track operator feedback
        elif operation == "operator.adaptive.feedback":
            feedback = metadata.get("feedback")
            target = metadata.get("target")
            if target and feedback:
                alert_type = metadata.get("alert_type", "unknown")
                LEARNING_STATE.record_feedback(alert_type, feedback)

    # Return current learning insights
    return {
        "learning_summary": LEARNING_STATE.get_performance_summary(),
        "dynamic_thresholds": {
            alert_type: perf.current_threshold
            for alert_type, perf in LEARNING_STATE.alert_type_performance.items()
        },
        "recommendations": _generate_learning_recommendations(),
    }


def _generate_learning_recommendations() -> list[str]:
    """Generate recommendations based on learning insights."""
    recommendations = []

    summary = LEARNING_STATE.get_performance_summary()

    # Check for alert types that need threshold adjustments
    for alert_type, perf in LEARNING_STATE.alert_type_performance.items():
        if perf.total_actions >= MIN_SAMPLES_FOR_ADAPTATION:
            auto_rate = perf.auto_success_rate()
            manual_rate = perf.success_rate() - auto_rate  # Approximate

            if auto_rate > 0.9 and perf.current_threshold > 0.8:
                recommendations.append(
                    f"Consider lowering threshold for {alert_type} (auto success: {auto_rate:.1%})"
                )
            elif auto_rate < 0.7 and perf.current_threshold < 0.95:
                recommendations.append(
                    f"Consider raising threshold for {alert_type} (auto success: {auto_rate:.1%})"
                )

    # Check overall automation health
    if summary["total_auto_actions"] > 0:
        auto_rate = summary["auto_success_rate"]
        if auto_rate < 0.8:
            recommendations.append(
                f"Overall auto success rate is low ({auto_rate:.1%}). Consider reviewing thresholds."
            )
        elif auto_rate > 0.95:
            recommendations.append(
                f"Excellent auto performance ({auto_rate:.1%}). Consider expanding automation scope."
            )

    return recommendations


def get_dynamic_threshold(alert_type: str) -> float:
    """Get the current dynamic threshold for an alert type."""
    return LEARNING_STATE.get_dynamic_threshold(alert_type)


def record_action_outcome(alert_type: str, alert_id: str, success: bool, was_auto: bool) -> None:
    """Record the outcome of an action for learning."""
    LEARNING_STATE.record_action(alert_type, alert_id, success, was_auto)


def record_operator_feedback(alert_type: str, feedback: str) -> None:
    """Record operator feedback for learning."""
    LEARNING_STATE.record_feedback(alert_type, feedback)
