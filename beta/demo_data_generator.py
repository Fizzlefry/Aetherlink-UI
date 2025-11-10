#!/usr/bin/env python3
"""
AetherLink Demo Data Generator

Generates realistic NOC data for beta tenant evaluation including:
- Synthetic alerts and incidents
- System metrics and performance data
- Autonomous AI actions and outcomes
- Learning insights and optimization data

Usage:
    python demo_data_generator.py --tenant-id TENANT_ID --days 30 --alerts 500 --incidents 50
"""

import argparse
import json
import os
import random
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class DemoDataGenerator:
    """Generates realistic demo data for beta tenant evaluation."""

    def __init__(self, tenant_id: str, profile: str = "general"):
        self.tenant_id = tenant_id
        self.profile = profile
        self.data_dir = f"provisioning/config/{tenant_id}"
        os.makedirs(self.data_dir, exist_ok=True)

        # Load profile definitions
        profiles_file = os.path.join(os.path.dirname(__file__), "profiles.json")
        with open(profiles_file) as f:
            profiles_data = json.load(f)
            self.profile_definitions = profiles_data.get("profiles", {})

        # Profile-specific alert categories and weights
        self.profile_configs = {
            "general": {
                "weights": {
                    "system": 0.4,
                    "application": 0.3,
                    "infrastructure": 0.2,
                    "security": 0.1,
                },
                "severity_weights": [0.5, 0.3, 0.15, 0.05],  # low, medium, high, critical
            },
            "finserv": {
                "weights": {
                    "system": 0.2,
                    "application": 0.2,
                    "infrastructure": 0.1,
                    "security": 0.5,  # Heavy on security/compliance
                },
                "severity_weights": [0.3, 0.4, 0.2, 0.1],  # More medium/high severity
            },
            "saas": {
                "weights": {
                    "system": 0.3,
                    "application": 0.5,  # Heavy on app performance
                    "infrastructure": 0.1,
                    "security": 0.1,
                },
                "severity_weights": [0.4, 0.4, 0.15, 0.05],  # Balanced severity
            },
            "industrial": {
                "weights": {
                    "system": 0.2,
                    "application": 0.1,
                    "infrastructure": 0.6,  # Heavy on infra/latency
                    "security": 0.1,
                },
                "severity_weights": [0.3, 0.3, 0.3, 0.1],  # More high severity infra issues
            },
        }

        config = self.profile_configs.get(profile, self.profile_configs["general"])
        self.category_weights = config["weights"]  # This is a dict
        self.severity_weights = config["severity_weights"]  # This is a list

        # Alert categories and severities
        self.alert_categories = {
            "system": [
                "CPU Usage",
                "Memory Usage",
                "Disk Space",
                "Network Latency",
                "Service Down",
            ],
            "application": [
                "Error Rate",
                "Response Time",
                "Throughput",
                "Database Connections",
                "Cache Hit Rate",
            ],
            "infrastructure": [
                "Server Unreachable",
                "Load Balancer Issues",
                "Database Replication",
                "Backup Failures",
            ],
            "security": [
                "Failed Login Attempts",
                "Suspicious Activity",
                "SSL Certificate Expiry",
                "Access Violations",
            ],
        }

        # Profile-specific alert types
        if profile == "finserv":
            self.alert_categories["security"].extend(
                ["PCI Compliance Alert", "Data Encryption Failure", "Audit Log Anomaly"]
            )
        elif profile == "saas":
            self.alert_categories["application"].extend(
                ["API Rate Limit Exceeded", "Queue Backlog", "Service Degradation"]
            )
        elif profile == "industrial":
            self.alert_categories["infrastructure"].extend(
                ["Sensor Data Loss", "PLC Communication Failure", "SCADA System Alert"]
            )

        self.severities = ["low", "medium", "high", "critical"]
        self.statuses = ["active", "acknowledged", "resolved", "auto_resolved"]

        # AI action types
        self.ai_actions = [
            "auto_restart_service",
            "scale_resources",
            "clear_cache",
            "kill_process",
            "reroute_traffic",
            "send_notification",
            "create_ticket",
            "run_diagnostic",
            "apply_config_change",
            "rollback_deployment",
        ]

    def generate_alerts(self, count: int, days_back: int) -> list[dict[str, Any]]:
        """Generate synthetic alerts."""
        alerts = []
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days_back)

        for _ in range(count):
            # Random timestamp within the period
            timestamp = start_time + timedelta(
                seconds=random.randint(0, int((end_time - start_time).total_seconds()))
            )

            # Random category based on profile weights
            category = random.choices(
                list(self.category_weights.keys()), weights=list(self.category_weights.values())
            )[0]

            alert_type = random.choice(self.alert_categories[category])

            # Random severity (weighted based on profile)
            severity = random.choices(self.severities, weights=self.severity_weights)[0]

            # Random status
            status = random.choice(self.statuses)

            # Generate alert data
            alert = {
                "id": f"alert_{uuid.uuid4().hex[:16]}",
                "tenant_id": self.tenant_id,
                "timestamp": timestamp.isoformat(),
                "category": category,
                "type": alert_type,
                "severity": severity,
                "status": status,
                "title": self._generate_alert_title(alert_type, severity),
                "description": self._generate_alert_description(alert_type, severity),
                "source": f"system_{random.randint(1, 10)}",
                "tags": self._generate_tags(category, alert_type),
                "metrics": self._generate_metrics(alert_type),
                "ai_analysis": self._generate_ai_analysis(severity, status),
                "resolution_time": random.randint(60, 3600)
                if status in ["resolved", "auto_resolved"]
                else None,
                "assigned_to": random.choice(["ai_system", "noc_team", "auto_escalated"])
                if status == "acknowledged"
                else None,
            }

            alerts.append(alert)

        # Sort by timestamp
        alerts.sort(key=lambda x: x["timestamp"])
        return alerts

    def generate_incidents(self, count: int, alerts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Generate synthetic incidents from alerts."""
        incidents = []
        used_alerts = set()

        for i in range(count):
            # Create incidents from high/critical alerts
            eligible_alerts = [
                a
                for a in alerts
                if a["severity"] in ["high", "critical"] and a["id"] not in used_alerts
            ]

            if not eligible_alerts:
                break

            # Pick a primary alert
            primary_alert = random.choice(eligible_alerts)
            used_alerts.add(primary_alert["id"])

            # Find related alerts within time window
            related_alerts: list[str] = []
            primary_time = datetime.fromisoformat(primary_alert["timestamp"])
            time_window = timedelta(hours=2)

            for alert in alerts:
                if alert["id"] != primary_alert["id"]:
                    alert_time = datetime.fromisoformat(alert["timestamp"])
                    if (
                        abs((alert_time - primary_time).total_seconds())
                        < time_window.total_seconds()
                    ):
                        if alert["category"] == primary_alert["category"]:
                            related_alerts.append(alert["id"])
                            used_alerts.add(alert["id"])

            # Generate incident
            incident = {
                "id": f"incident_{uuid.uuid4().hex[:16]}",
                "tenant_id": self.tenant_id,
                "title": self._generate_incident_title(primary_alert),
                "description": self._generate_incident_description(
                    primary_alert, len(related_alerts)
                ),
                "severity": primary_alert["severity"],
                "status": random.choice(["open", "investigating", "resolved", "closed"]),
                "created_at": primary_alert["timestamp"],
                "updated_at": (
                    datetime.fromisoformat(primary_alert["timestamp"])
                    + timedelta(minutes=random.randint(30, 480))
                ).isoformat(),
                "resolved_at": None,
                "primary_alert": primary_alert["id"],
                "related_alerts": related_alerts,
                "ai_insights": self._generate_incident_insights(primary_alert, len(related_alerts)),
                "actions_taken": self._generate_incident_actions(len(related_alerts)),
                "impact_assessment": self._generate_impact_assessment(primary_alert["severity"]),
                "assigned_team": random.choice(
                    ["Platform Team", "Database Team", "Network Team", "Security Team", "AI Ops"]
                ),
            }

            # Set resolution time if resolved
            if incident["status"] in ["resolved", "closed"]:
                incident["resolved_at"] = incident["updated_at"]
                incident["resolution_time"] = random.randint(1800, 7200)  # 30min to 2hrs

            incidents.append(incident)

        return incidents

    def generate_ai_actions(
        self, alerts: list[dict[str, Any]], incidents: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Generate AI autonomous actions."""
        actions = []

        # Generate actions for alerts
        for alert in alerts:
            if (
                alert["status"] == "auto_resolved" or random.random() < 0.3
            ):  # 30% of alerts get AI actions
                action = {
                    "id": f"action_{uuid.uuid4().hex[:16]}",
                    "tenant_id": self.tenant_id,
                    "timestamp": (
                        datetime.fromisoformat(alert["timestamp"])
                        + timedelta(seconds=random.randint(30, 300))
                    ).isoformat(),
                    "type": random.choice(self.ai_actions),
                    "trigger": "alert",
                    "trigger_id": alert["id"],
                    "confidence_score": random.uniform(0.7, 0.95),
                    "action_taken": self._generate_action_description(
                        random.choice(self.ai_actions)
                    ),
                    "expected_outcome": self._generate_expected_outcome(alert["severity"]),
                    "actual_outcome": random.choice(
                        ["successful", "partially_successful", "failed"]
                    ),
                    "rollback_available": random.random() < 0.8,
                    "audit_trail": self._generate_audit_trail(),
                }
                actions.append(action)

        # Generate actions for incidents
        for incident in incidents:
            if random.random() < 0.6:  # 60% of incidents get AI actions
                action = {
                    "id": f"action_{uuid.uuid4().hex[:16]}",
                    "tenant_id": self.tenant_id,
                    "timestamp": incident["updated_at"],
                    "type": random.choice(self.ai_actions),
                    "trigger": "incident",
                    "trigger_id": incident["id"],
                    "confidence_score": random.uniform(0.75, 0.98),
                    "action_taken": self._generate_action_description(
                        random.choice(self.ai_actions)
                    ),
                    "expected_outcome": "Incident resolution and service restoration",
                    "actual_outcome": "successful"
                    if incident["status"] in ["resolved", "closed"]
                    else random.choice(["partially_successful", "failed"]),
                    "rollback_available": random.random() < 0.9,
                    "audit_trail": self._generate_audit_trail(),
                }
                actions.append(action)

        # Sort by timestamp
        actions.sort(key=lambda x: x["timestamp"])
        return actions

    def generate_metrics(self, days_back: int) -> dict[str, Any]:
        """Generate system metrics data."""
        profile_info = self.profile_definitions.get(
            self.profile, self.profile_definitions.get("general", {})
        )
        metrics = {
            "tenant_id": self.tenant_id,
            "period_start": (datetime.now() - timedelta(days=days_back)).isoformat(),
            "period_end": datetime.now().isoformat(),
            "profile": {
                "name": self.profile,
                "display_name": profile_info.get("name", self.profile.title()),
                "description": profile_info.get("description", "Demo NOC environment"),
                "target_audience": profile_info.get("target_audience", "General IT operations"),
                "generated_at": datetime.now().isoformat(),
            },
            "summary": {
                "total_alerts": 0,  # Will be filled after alert generation
                "total_incidents": 0,  # Will be filled after incident generation
                "auto_resolved_percentage": 0,
                "average_resolution_time": 0,
                "ai_actions_taken": 0,
                "system_uptime": random.uniform(0.95, 0.99),
            },
            "performance": {
                "cpu_usage_avg": random.uniform(0.3, 0.7),
                "memory_usage_avg": random.uniform(0.4, 0.8),
                "disk_usage_avg": random.uniform(0.2, 0.6),
                "network_latency_avg": random.uniform(10, 50),
            },
            "ai_insights": {
                "learning_iterations": random.randint(100, 500),
                "model_accuracy": random.uniform(0.85, 0.95),
                "false_positive_rate": random.uniform(0.02, 0.08),
                "prediction_accuracy": random.uniform(0.88, 0.96),
            },
        }

        return metrics

    def save_data(
        self,
        alerts: list[dict[str, Any]],
        incidents: list[dict[str, Any]],
        actions: list[dict[str, Any]],
        metrics: dict[str, Any],
    ):
        """Save generated data to files."""
        # Update metrics with actual counts
        metrics["summary"]["total_alerts"] = len(alerts)
        metrics["summary"]["total_incidents"] = len(incidents)
        metrics["summary"]["ai_actions_taken"] = len(actions)

        # Calculate auto-resolved percentage
        auto_resolved = sum(1 for a in alerts if a["status"] == "auto_resolved")
        metrics["summary"]["auto_resolved_percentage"] = (
            auto_resolved / len(alerts) if alerts else 0
        )

        # Calculate average resolution time
        resolution_times = [a["resolution_time"] for a in alerts if a.get("resolution_time")]
        metrics["summary"]["average_resolution_time"] = (
            sum(resolution_times) / len(resolution_times) if resolution_times else 0
        )

        # Save alerts
        with open(f"{self.data_dir}/demo_alerts.json", "w") as f:
            json.dump({"alerts": alerts}, f, indent=2)

        # Save incidents
        with open(f"{self.data_dir}/demo_incidents.json", "w") as f:
            json.dump({"incidents": incidents}, f, indent=2)

        # Save AI actions
        with open(f"{self.data_dir}/demo_actions.json", "w") as f:
            json.dump({"actions": actions}, f, indent=2)

        # Save metrics
        with open(f"{self.data_dir}/demo_metrics.json", "w") as f:
            json.dump(metrics, f, indent=2)

        print(f"✅ Demo data saved to {self.data_dir}/")

    # Helper methods for generating realistic data
    def _generate_alert_title(self, alert_type: str, severity: str) -> str:
        """Generate realistic alert titles."""
        templates = {
            "CPU Usage": [
                f"High CPU usage detected on {alert_type}",
                "CPU utilization above threshold",
            ],
            "Memory Usage": ["Memory usage critical", "High memory consumption detected"],
            "Disk Space": ["Disk space running low", "Storage capacity warning"],
            "Network Latency": ["Network latency increased", "Connection delays detected"],
            "Service Down": ["Service unavailable", "Application service failure"],
            "Error Rate": ["Error rate spike detected", "Increased error frequency"],
            "Response Time": ["Slow response times", "Performance degradation"],
            "Database Connections": [
                "Database connection pool exhausted",
                "Connection limit reached",
            ],
        }

        template = templates.get(alert_type, [f"{alert_type} alert"])[0]
        if severity == "critical":
            return f"CRITICAL: {template}"
        elif severity == "high":
            return f"HIGH: {template}"
        else:
            return template

    def _generate_alert_description(self, alert_type: str, severity: str) -> str:
        """Generate detailed alert descriptions."""
        descriptions = {
            "CPU Usage": "System CPU utilization has exceeded normal thresholds, potentially impacting performance.",
            "Memory Usage": "Memory consumption is approaching critical levels, risking system stability.",
            "Disk Space": "Available disk space is below recommended thresholds.",
            "Network Latency": "Network response times have increased significantly.",
            "Service Down": "Critical service is not responding to health checks.",
            "Error Rate": "Application error rate has spiked above acceptable levels.",
            "Response Time": "Application response times are slower than expected.",
            "Database Connections": "Database connection pool is at maximum capacity.",
        }

        return descriptions.get(alert_type, f"Detailed information for {alert_type} alert.")

    def _generate_tags(self, category: str, alert_type: str) -> list[str]:
        """Generate relevant tags for alerts."""
        base_tags = [category, alert_type.lower().replace(" ", "_")]

        additional_tags = {
            "system": ["infrastructure", "performance"],
            "application": ["app", "service"],
            "infrastructure": ["infra", "platform"],
            "security": ["security", "compliance"],
        }

        base_tags.extend(additional_tags.get(category, []))
        return list(set(base_tags))  # Remove duplicates

    def _generate_metrics(self, alert_type: str) -> dict[str, Any]:
        """Generate relevant metrics data for alerts."""
        metrics_templates = {
            "CPU Usage": {
                "cpu_percent": random.uniform(85, 98),
                "load_average": random.uniform(5, 15),
            },
            "Memory Usage": {
                "memory_percent": random.uniform(90, 97),
                "swap_percent": random.uniform(0, 20),
            },
            "Disk Space": {
                "disk_percent": random.uniform(85, 95),
                "available_gb": random.uniform(5, 20),
            },
            "Network Latency": {
                "latency_ms": random.uniform(100, 500),
                "packet_loss": random.uniform(0, 5),
            },
            "Response Time": {
                "response_time_ms": random.uniform(2000, 10000),
                "requests_per_second": random.uniform(10, 100),
            },
        }

        return metrics_templates.get(alert_type, {"value": random.uniform(0, 100)})

    def _generate_ai_analysis(self, severity: str, status: str) -> dict[str, Any]:
        """Generate AI analysis data."""
        confidence = random.uniform(0.7, 0.95)
        if status == "auto_resolved":
            confidence = random.uniform(0.85, 0.98)

        return {
            "confidence_score": confidence,
            "predicted_impact": severity,
            "recommended_action": random.choice(self.ai_actions),
            "estimated_resolution_time": random.randint(300, 1800),
            "similar_incidents": random.randint(0, 5),
        }

    def _generate_incident_title(self, primary_alert: dict[str, Any]) -> str:
        """Generate incident titles from primary alerts."""
        return f"Incident: {primary_alert['title']}"

    def _generate_incident_description(
        self, primary_alert: dict[str, Any], related_count: int
    ) -> str:
        """Generate detailed incident descriptions."""
        description = f"Critical incident triggered by {primary_alert['title']}."

        if related_count > 0:
            description += f" {related_count} related alerts detected in the same time window."

        description += " Investigation and remediation in progress."
        return description

    def _generate_incident_insights(
        self, primary_alert: dict[str, Any], related_count: int
    ) -> dict[str, Any]:
        """Generate AI insights for incidents."""
        return {
            "root_cause_probability": random.uniform(0.6, 0.9),
            "predicted_duration": random.randint(1800, 7200),
            "impact_scope": random.choice(["single_service", "multiple_services", "system_wide"]),
            "similar_incidents": random.randint(1, 10),
            "recommended_actions": random.sample(self.ai_actions, k=min(3, len(self.ai_actions))),
        }

    def _generate_incident_actions(self, related_count: int) -> list[dict[str, Any]]:
        """Generate actions taken during incident response."""
        actions = []
        num_actions = min(related_count + 1, 5)

        for i in range(num_actions):
            actions.append(
                {
                    "timestamp": (
                        datetime.now() - timedelta(hours=random.randint(1, 24))
                    ).isoformat(),
                    "action": random.choice(self.ai_actions),
                    "actor": random.choice(["AI System", "NOC Engineer", "Platform Team"]),
                    "result": random.choice(
                        ["successful", "partially_successful", "investigating"]
                    ),
                }
            )

        return actions

    def _generate_impact_assessment(self, severity: str) -> dict[str, Any]:
        """Generate impact assessment data."""
        impact_levels = {
            "low": {
                "user_impact": "minimal",
                "business_impact": "low",
                "duration_hours": random.randint(1, 4),
            },
            "medium": {
                "user_impact": "moderate",
                "business_impact": "medium",
                "duration_hours": random.randint(2, 8),
            },
            "high": {
                "user_impact": "significant",
                "business_impact": "high",
                "duration_hours": random.randint(4, 24),
            },
            "critical": {
                "user_impact": "severe",
                "business_impact": "critical",
                "duration_hours": random.randint(8, 72),
            },
        }

        return impact_levels.get(severity, impact_levels["medium"])

    def _generate_action_description(self, action_type: str) -> str:
        """Generate human-readable action descriptions."""
        descriptions = {
            "auto_restart_service": "Automatically restarted the affected service",
            "scale_resources": "Scaled up compute resources to handle load",
            "clear_cache": "Cleared application cache to resolve performance issues",
            "kill_process": "Terminated unresponsive process",
            "reroute_traffic": "Rerouted traffic to healthy instances",
            "send_notification": "Sent alert notifications to on-call team",
            "create_ticket": "Created incident ticket in service management system",
            "run_diagnostic": "Executed automated diagnostic scripts",
            "apply_config_change": "Applied configuration changes to resolve issue",
            "rollback_deployment": "Rolled back recent deployment to previous version",
        }

        return descriptions.get(action_type, f"Executed {action_type} action")

    def _generate_expected_outcome(self, severity: str) -> str:
        """Generate expected outcomes for AI actions."""
        outcomes = {
            "low": "Issue resolved with minimal impact",
            "medium": "Service performance restored to normal levels",
            "high": "Critical service availability maintained",
            "critical": "System stability and availability restored",
        }

        return outcomes.get(severity, "Issue mitigation completed")

    def _generate_audit_trail(self) -> list[dict[str, Any]]:
        """Generate audit trail entries for actions."""
        trail = []
        num_entries = random.randint(2, 5)

        for i in range(num_entries):
            trail.append(
                {
                    "timestamp": (
                        datetime.now() - timedelta(minutes=random.randint(1, 60))
                    ).isoformat(),
                    "event": random.choice(
                        [
                            "action_started",
                            "validation_check",
                            "outcome_verified",
                            "rollback_prepared",
                        ]
                    ),
                    "details": f"Automated system check {i+1}",
                    "status": "completed",
                }
            )

        return trail


def main():
    """Main entry point for demo data generation."""
    parser = argparse.ArgumentParser(description="Generate demo data for AetherLink beta tenants")
    parser.add_argument("--tenant-id", required=True, help="Tenant ID to generate data for")
    parser.add_argument("--days", type=int, default=30, help="Number of days of historical data")
    parser.add_argument("--alerts", type=int, default=500, help="Number of alerts to generate")
    parser.add_argument("--incidents", type=int, default=50, help="Number of incidents to generate")
    parser.add_argument(
        "--profile",
        choices=["general", "finserv", "saas", "industrial"],
        default="general",
        help="Industry profile for tailored demo data",
    )

    args = parser.parse_args()

    print(f"🚀 Generating demo data for tenant: {args.tenant_id}")
    print(f"   - Profile: {args.profile}")
    print(f"   - Days of history: {args.days}")
    print(f"   - Alerts to generate: {args.alerts}")
    print(f"   - Incidents to generate: {args.incidents}")

    generator = DemoDataGenerator(args.tenant_id, args.profile)

    # Generate data
    alerts = generator.generate_alerts(args.alerts, args.days)
    incidents = generator.generate_incidents(args.incidents, alerts)
    actions = generator.generate_ai_actions(alerts, incidents)
    metrics = generator.generate_metrics(args.days)

    # Save data
    generator.save_data(alerts, incidents, actions, metrics)

    print("✅ Demo data generation complete!")
    print(f"   - Generated {len(alerts)} alerts")
    print(f"   - Generated {len(incidents)} incidents")
    print(f"   - Generated {len(actions)} AI actions")
    print(f"   - Data saved to: provisioning/config/{args.tenant_id}/")


if __name__ == "__main__":
    main()
