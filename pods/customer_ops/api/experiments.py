"""
A/B Experimentation Framework for CustomerOps AI Agent.

Supports:
- Feature flag bucketing (consistent hashing by tenant)
- Variant assignment with sticky sessions
- Per-variant metrics tracking
- Statistical significance testing (chi-square)
- Auto-promotion of winning variants

Usage:
    from .experiments import get_variant, track_outcome

    variant = get_variant(tenant, "enrichment_model")
    if variant == "control":
        # Use standard enrichment
    elif variant == "gpt4":
        # Use GPT-4 enrichment

    track_outcome(tenant, "enrichment_model", variant, outcome="booked")
"""

import hashlib
import time
from dataclasses import dataclass
from typing import Any, Literal

from prometheus_client import Counter, Gauge

from .logger import logger

# Prometheus metrics for experiments
EXPERIMENT_ASSIGNED = Counter(
    "experiment_variant_assigned_total",
    "Total experiment variant assignments",
    ["experiment", "variant"],
)

EXPERIMENT_OUTCOME = Counter(
    "experiment_outcome_total",
    "Experiment outcomes by variant",
    ["experiment", "variant", "outcome"],
)

EXPERIMENT_CONVERSION_RATE = Gauge(
    "experiment_conversion_rate", "Conversion rate by experiment variant", ["experiment", "variant"]
)

EXPERIMENT_SAMPLE_SIZE = Gauge(
    "experiment_sample_size", "Sample size by experiment variant", ["experiment", "variant"]
)


@dataclass
class ExperimentVariant:
    """A single variant in an A/B test."""

    name: str
    traffic_weight: float  # 0.0 - 1.0
    config: dict[str, Any]  # Variant-specific configuration


@dataclass
class Experiment:
    """A/B test experiment configuration."""

    name: str
    description: str
    enabled: bool
    variants: list[ExperimentVariant]
    start_date: int  # Unix timestamp
    min_sample_size: int = 100  # Minimum samples per variant before significance testing
    auto_promote: bool = True  # Auto-promote winners
    promoted_variant: str | None = None  # Promoted winner (if any)


# Active experiments registry
# In production, load from Redis or config service
EXPERIMENTS: dict[str, Experiment] = {
    "enrichment_model": Experiment(
        name="enrichment_model",
        description="Test GPT-4 vs Claude for intent/sentiment enrichment",
        enabled=False,  # Disabled by default
        start_date=int(time.time()),
        variants=[
            ExperimentVariant(
                name="control",
                traffic_weight=0.5,
                config={"model": "gpt-3.5-turbo", "temperature": 0.0},
            ),
            ExperimentVariant(
                name="gpt4", traffic_weight=0.5, config={"model": "gpt-4", "temperature": 0.0}
            ),
        ],
        min_sample_size=50,
    ),
    "followup_timing": Experiment(
        name="followup_timing",
        description="Test aggressive (5min) vs conservative (30min) follow-up delays",
        enabled=True,
        start_date=int(time.time()),
        variants=[
            ExperimentVariant(
                name="control",
                traffic_weight=0.5,
                config={"delay_seconds": 1800},  # 30 min
            ),
            ExperimentVariant(
                name="aggressive",
                traffic_weight=0.5,
                config={"delay_seconds": 300},  # 5 min
            ),
        ],
        min_sample_size=100,
    ),
    "prediction_threshold": Experiment(
        name="prediction_threshold",
        description="Test high-confidence (0.7) vs standard (0.5) prediction threshold for follow-ups",
        enabled=False,
        start_date=int(time.time()),
        variants=[
            ExperimentVariant(name="control", traffic_weight=0.5, config={"threshold": 0.5}),
            ExperimentVariant(
                name="high_confidence", traffic_weight=0.5, config={"threshold": 0.7}
            ),
        ],
        min_sample_size=100,
    ),
}


def _hash_tenant(tenant: str, experiment: str) -> float:
    """
    Consistent hash of tenant+experiment to [0, 1].
    Ensures same tenant always gets same variant.
    """
    combined = f"{tenant}:{experiment}"
    hash_bytes = hashlib.sha256(combined.encode()).digest()
    # Convert first 8 bytes to float in [0, 1]
    hash_int = int.from_bytes(hash_bytes[:8], byteorder="big")
    return hash_int / (2**64)


def get_variant(tenant: str, experiment_name: str) -> str:
    """
    Get experiment variant for a tenant.

    Uses consistent hashing to ensure:
    - Same tenant always gets same variant
    - Variants distributed according to traffic_weight

    Args:
        tenant: Tenant identifier (e.g., "acme_corp")
        experiment_name: Name of experiment (e.g., "enrichment_model")

    Returns:
        Variant name (e.g., "control", "gpt4")
        Returns "control" if experiment not found or disabled.
    """
    exp = EXPERIMENTS.get(experiment_name)

    # Return control if experiment doesn't exist or is disabled
    if not exp or not exp.enabled:
        return "control"

    # If winner promoted, always return winner
    if exp.promoted_variant:
        logger.info(
            "experiment_promoted_variant",
            extra={
                "experiment": experiment_name,
                "tenant": tenant,
                "promoted": exp.promoted_variant,
            },
        )
        return exp.promoted_variant

    # Consistent hash assignment
    hash_value = _hash_tenant(tenant, experiment_name)

    # Cumulative distribution for traffic weights
    cumulative = 0.0
    for variant in exp.variants:
        cumulative += variant.traffic_weight
        if hash_value < cumulative:
            EXPERIMENT_ASSIGNED.labels(experiment=experiment_name, variant=variant.name).inc()

            logger.debug(
                "experiment_variant_assigned",
                extra={
                    "experiment": experiment_name,
                    "tenant": tenant,
                    "variant": variant.name,
                    "hash": hash_value,
                },
            )

            return variant.name

    # Fallback to last variant (handles rounding errors)
    return exp.variants[-1].name if exp.variants else "control"


def get_variant_config(tenant: str, experiment_name: str) -> dict[str, Any]:
    """
    Get configuration for assigned variant.

    Args:
        tenant: Tenant identifier
        experiment_name: Experiment name

    Returns:
        Variant configuration dict, or {} if not found.
    """
    exp = EXPERIMENTS.get(experiment_name)
    if not exp or not exp.enabled:
        return {}

    variant_name = get_variant(tenant, experiment_name)

    for variant in exp.variants:
        if variant.name == variant_name:
            return variant.config

    return {}


def track_outcome(
    tenant: str,
    experiment_name: str,
    variant: str,
    outcome: Literal["booked", "ghosted", "qualified", "callback", "nurture", "lost"],
):
    """
    Track experiment outcome for a variant.

    Args:
        tenant: Tenant identifier
        experiment_name: Experiment name
        variant: Variant name
        outcome: Outcome type
    """
    EXPERIMENT_OUTCOME.labels(experiment=experiment_name, variant=variant, outcome=outcome).inc()

    logger.info(
        "experiment_outcome_tracked",
        extra={
            "experiment": experiment_name,
            "tenant": tenant,
            "variant": variant,
            "outcome": outcome,
        },
    )


def calculate_significance(experiment_name: str, outcome_type: str = "booked") -> dict[str, Any]:
    """
    Calculate statistical significance of experiment results.

    Uses chi-square test to compare conversion rates across variants.

    Args:
        experiment_name: Experiment name
        outcome_type: Outcome to test (default "booked")

    Returns:
        {
            "significant": bool,
            "p_value": float,
            "chi_square": float,
            "winner": str or None,
            "variants": {variant: {"rate": float, "samples": int, "conversions": int}}
        }
    """
    exp = EXPERIMENTS.get(experiment_name)
    if not exp:
        return {"significant": False, "error": "Experiment not found"}

    try:
        from scipy import stats

        # Collect data from Prometheus metrics
        # In production, query Prometheus API or use in-memory counters
        # For now, use placeholder logic
        # Simulated data structure (replace with actual Prometheus query)
        variant_data = {}

        for variant in exp.variants:
            # These would come from Prometheus queries in production
            # For now, using placeholder values
            total = 0  # Total assignments
            conversions = 0  # Successful outcomes

            if total > 0:
                variant_data[variant.name] = {
                    "samples": total,
                    "conversions": conversions,
                    "rate": conversions / total,
                }

        # Need at least 2 variants with data
        if len(variant_data) < 2:
            return {
                "significant": False,
                "error": "Need at least 2 variants with data",
                "variants": variant_data,
            }

        # Check minimum sample size
        for variant_name, data in variant_data.items():
            if data["samples"] < exp.min_sample_size:
                return {
                    "significant": False,
                    "error": f"Insufficient samples for {variant_name}",
                    "min_required": exp.min_sample_size,
                    "variants": variant_data,
                }

        # Chi-square test
        observed = [
            [d["conversions"], d["samples"] - d["conversions"]] for d in variant_data.values()
        ]
        chi2, p_value, dof, expected = stats.chi2_contingency(observed)

        # Determine winner (highest conversion rate)
        winner = max(variant_data.items(), key=lambda x: x[1]["rate"])[0]

        result = {
            "significant": p_value < 0.05,
            "p_value": float(p_value),
            "chi_square": float(chi2),
            "winner": winner if p_value < 0.05 else None,
            "variants": variant_data,
        }

        logger.info(
            "experiment_significance_calculated",
            extra={
                "experiment": experiment_name,
                "significant": result["significant"],
                "p_value": p_value,
                "winner": result["winner"],
            },
        )

        return result

    except ImportError:
        return {
            "significant": False,
            "error": "scipy not installed (pip install scipy)",
        }
    except Exception as e:
        logger.error(
            "experiment_significance_failed",
            extra={
                "experiment": experiment_name,
                "error": str(e),
            },
        )
        return {
            "significant": False,
            "error": str(e),
        }


def promote_winner(experiment_name: str) -> dict[str, Any]:
    """
    Promote winning variant to 100% traffic.

    Args:
        experiment_name: Experiment name

    Returns:
        Result dict with promoted variant or error
    """
    exp = EXPERIMENTS.get(experiment_name)
    if not exp:
        return {"ok": False, "error": "Experiment not found"}

    if not exp.auto_promote:
        return {"ok": False, "error": "Auto-promotion disabled for this experiment"}

    # Calculate significance
    result = calculate_significance(experiment_name)

    if not result.get("significant"):
        return {
            "ok": False,
            "error": "No statistically significant winner yet",
            "p_value": result.get("p_value"),
        }

    winner = result.get("winner")
    if not winner:
        return {"ok": False, "error": "No winner identified"}

    # Promote winner
    exp.promoted_variant = winner

    logger.info(
        "experiment_winner_promoted",
        extra={
            "experiment": experiment_name,
            "winner": winner,
            "p_value": result.get("p_value"),
        },
    )

    return {
        "ok": True,
        "experiment": experiment_name,
        "promoted": winner,
        "p_value": result.get("p_value"),
        "chi_square": result.get("chi_square"),
        "variants": result.get("variants"),
    }


def list_experiments() -> dict[str, Any]:
    """
    List all experiments with status.

    Returns:
        Dict of experiment names to status info
    """
    result = {}

    for name, exp in EXPERIMENTS.items():
        result[name] = {
            "name": exp.name,
            "description": exp.description,
            "enabled": exp.enabled,
            "promoted_variant": exp.promoted_variant,
            "variants": [v.name for v in exp.variants],
            "start_date": exp.start_date,
            "min_sample_size": exp.min_sample_size,
            "auto_promote": exp.auto_promote,
        }

    return result
