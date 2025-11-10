"""
Phase X: Predictive Ops Engine - Auto-Healing System
Self-healing automation for AetherLink delivery pipeline.

Modules:
- predictors: Strategy selection based on anomaly patterns
- rules: Policy configuration and safety limits
- engine: Main executor for auto-healing actions
"""

__version__ = "1.26.0"

from .engine import (
    AutohealResult,
    clear_endpoint_cooldown,
    get_healing_history,
    run_autoheal_cycle,
)
from .predictors import choose_strategy, predict_outcome_probability
from .rules import AUTOHEAL_LIMITS, STRATEGY_PRIORITIES

__all__ = [
    "choose_strategy",
    "predict_outcome_probability",
    "AUTOHEAL_LIMITS",
    "STRATEGY_PRIORITIES",
    "run_autoheal_cycle",
    "AutohealResult",
    "get_healing_history",
    "clear_endpoint_cooldown",
]
