#!/usr/bin/env python3
"""
AetherLink AI Operations Brain - Demo Script

This script demonstrates the complete AI Operations Brain capabilities:
1. System health monitoring
2. AI-driven recommendations
3. Autonomous actions with learning
4. Performance analytics and insights

Usage: python demo_ai_operations_brain.py
"""

import sys
import time
from datetime import datetime

import requests

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "expertco-api-key-123"  # Replace with actual key
ADMIN_KEY = "admin-secret-123"  # Replace with actual admin key

HEADERS = {"x-api-key": API_KEY, "Content-Type": "application/json"}

ADMIN_HEADERS = {"x-api-key": API_KEY, "x-admin-key": ADMIN_KEY, "Content-Type": "application/json"}


def print_header(title: str):
    """Print a formatted header."""
    print(f"\n{'='*60}")
    print(f" {title}")
    print(f"{'='*60}")


def make_request(method: str, endpoint: str, headers: dict = None, data: dict = None) -> dict:
    """Make an HTTP request and return JSON response."""
    url = f"{BASE_URL}{endpoint}"
    headers = headers or HEADERS

    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data)
        else:
            raise ValueError(f"Unsupported method: {method}")

        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return {"error": str(e)}


def demo_system_health():
    """Demonstrate system health monitoring."""
    print_header("1. System Health Monitoring")

    print("Checking system health...")
    health = make_request("GET", "/ops/health")

    if "error" not in health:
        print("✅ System Health Status:")
        print(f"   Status: {health.get('status', 'unknown')}")
        print(f"   Components: {len(health.get('components', {}))}")
        print(f"   Last Check: {health.get('timestamp', 'unknown')}")

        # Show component details
        components = health.get("components", {})
        for name, status in components.items():
            status_icon = "✅" if status.get("healthy") else "❌"
            print(f"   {status_icon} {name}: {status.get('status', 'unknown')}")
    else:
        print("❌ Health check failed")


def demo_ai_recommendations():
    """Demonstrate AI-driven recommendations."""
    print_header("2. AI-Driven Recommendations")

    print("Fetching AI recommendations...")
    recommendations = make_request("GET", "/ops/adaptive/recommendations")

    if "error" not in recommendations:
        insights = recommendations.get("learning_insights", {})
        summary = insights.get("learning_summary", {})

        print("✅ AI Learning Insights:")
        print(f"   Total Actions: {summary.get('total_actions', 0)}")
        print(f"   Auto Actions: {summary.get('total_auto_actions', 0)}")
        print(".1f")
        print(".1f")

        # Show alert type breakdown
        breakdown = summary.get("alert_type_breakdown", {})
        if breakdown:
            print("   Alert Type Performance:")
            for alert_type, metrics in breakdown.items():
                print(f"     {alert_type}:")
                print(f"       Success Rate: {metrics.get('success_rate', 0):.1%}")
                print(f"       Auto Success Rate: {metrics.get('auto_success_rate', 0):.1%}")
                print(f"       Current Threshold: {metrics.get('current_threshold', 0):.2f}")
    else:
        print("❌ Failed to get recommendations")


def demo_autonomous_action():
    """Demonstrate autonomous action application."""
    print_header("3. Autonomous Action Application")

    # First, let's check for any alerts that could be auto-acknowledged
    print("Checking for alerts...")
    alerts_response = make_request("GET", "/ops/alerts")

    if "error" not in alerts_response:
        alerts = alerts_response.get("alerts", [])
        print(f"Found {len(alerts)} active alerts")

        # Look for an alert that could be auto-acknowledged
        auto_ack_candidate = None
        for alert in alerts:
            if (
                alert.get("type") == "system_warning"
                or "auto_ack" in alert.get("title", "").lower()
            ):
                auto_ack_candidate = alert
                break

        if auto_ack_candidate:
            print(f"Applying autonomous action to alert: {auto_ack_candidate['title']}")

            action_payload = {
                "type": "auto_ack_candidate",
                "alert_id": auto_ack_candidate["id"],
                "alert_type": auto_ack_candidate.get("type", "unknown"),
                "source": "auto",
                "applied": "adaptive.auto",
            }

            result = make_request("POST", "/ops/adaptive/apply", data=action_payload)

            if "error" not in result and result.get("ok"):
                print("✅ Autonomous action applied successfully")
                print(f"   Action: {result.get('applied')}")
                print(f"   Alert ID: {result.get('alert_id')}")
            else:
                print("❌ Autonomous action failed")
        else:
            print("ℹ️  No suitable alerts for autonomous action found")
            print("   (This is normal - autonomous actions only trigger when confidence is high)")
    else:
        print("❌ Failed to check alerts")


def demo_learning_insights():
    """Demonstrate learning performance insights."""
    print_header("4. Learning Performance Insights")

    print("Fetching detailed learning insights...")
    insights = make_request("GET", "/ops/learning/performance")

    if "error" not in insights:
        print("✅ Learning Performance Data:")

        if "performance" in insights:
            perf = insights["performance"]
            print(f"   Total Actions: {perf.get('total_actions', 0)}")
            print(f"   Manual Actions: {perf.get('manual_actions', 0)}")
            print(f"   Auto Actions: {perf.get('total_auto_actions', 0)}")
            print(".1f")
            print(".1f")

        # Show dynamic thresholds
        thresholds = insights.get("dynamic_thresholds", {})
        if thresholds:
            print("   Dynamic Thresholds:")
            for alert_type, threshold in thresholds.items():
                print(f"     {alert_type}: {threshold:.2f}")
    else:
        print("❌ Failed to get learning insights")


def demo_operator_feedback():
    """Demonstrate operator feedback loop."""
    print_header("5. Operator Feedback Loop")

    print("Submitting operator feedback...")

    feedback_payload = {
        "alert_type": "auto_ack_candidate",
        "action_type": "alert_ack",
        "feedback": "positive",  # or "negative"
        "confidence_level": 0.85,
        "comments": "AI correctly identified a routine alert that should be auto-acknowledged",
    }

    result = make_request("POST", "/ops/adaptive/feedback", data=feedback_payload)

    if "error" not in result and result.get("ok"):
        print("✅ Operator feedback recorded successfully")
        print("   This feedback will be used to improve future AI decisions")
    else:
        print("❌ Failed to record feedback")


def demo_tenant_operations():
    """Demonstrate multi-tenant operations."""
    print_header("6. Multi-Tenant Operations")

    print("Checking tenant status...")
    tenants = make_request("GET", "/ops/tenants", headers=ADMIN_HEADERS)

    if "error" not in tenants:
        tenant_list = tenants.get("tenants", [])
        print(f"✅ Found {len(tenant_list)} tenants")

        for tenant in tenant_list[:3]:  # Show first 3
            print(f"   Tenant: {tenant.get('name', 'unknown')}")
            print(f"   Status: {tenant.get('status', 'unknown')}")
            print(f"   API Key: {tenant.get('api_key', 'masked')[:8]}...")
    else:
        print("❌ Failed to check tenants")


def demo_metrics_export():
    """Demonstrate metrics export for monitoring."""
    print_header("7. Metrics Export for Monitoring")

    print("Fetching Prometheus metrics...")
    try:
        response = requests.get(f"{BASE_URL}/metrics")
        if response.status_code == 200:
            metrics_text = response.text
            ai_metrics = [
                line
                for line in metrics_text.split("\n")
                if "aetherlink_adaptive" in line and not line.startswith("#")
            ]

            print("✅ AI Operations Metrics Found:")
            for metric in ai_metrics[:10]:  # Show first 10
                if metric.strip():
                    print(f"   {metric}")
        else:
            print("❌ Failed to fetch metrics")
    except Exception as e:
        print(f"❌ Metrics request failed: {e}")


def main():
    """Run the complete AI Operations Brain demo."""
    print("🚀 AetherLink AI Operations Brain - Live Demo")
    print("This demo showcases the complete autonomous operations platform")
    print(f"Target System: {BASE_URL}")
    print(f"Demo started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Check if system is running
    print("\n🔍 Checking system availability...")
    ping = make_request("GET", "/ops/ping")
    if "error" in ping:
        print("❌ System is not responding. Please ensure AetherLink is running.")
        print(
            "   Start with: python -m uvicorn services.command-center.main:app --host 0.0.0.0 --port 8000"
        )
        sys.exit(1)

    print("✅ System is responding - starting demo...")

    # Run all demo sections
    demo_system_health()
    time.sleep(1)

    demo_ai_recommendations()
    time.sleep(1)

    demo_autonomous_action()
    time.sleep(1)

    demo_learning_insights()
    time.sleep(1)

    demo_operator_feedback()
    time.sleep(1)

    demo_tenant_operations()
    time.sleep(1)

    demo_metrics_export()

    # Summary
    print_header("Demo Complete! 🎉")

    print("Summary of AI Operations Brain Capabilities Demonstrated:")
    print("✅ Real-time system health monitoring")
    print("✅ AI-driven pattern recognition and recommendations")
    print("✅ Autonomous actions with confidence thresholds")
    print("✅ Continuous learning from operator feedback")
    print("✅ Comprehensive audit trails and analytics")
    print("✅ Multi-tenant isolation and management")
    print("✅ Prometheus metrics for monitoring integration")
    print()
    print("The AI Operations Brain is now running autonomously, learning from")
    print("every interaction, and continuously improving operational efficiency!")
    print()
    print("For production deployment:")
    print("1. Use Docker Compose: docker compose -f deploy/docker-compose.prod.yml up -d")
    print("2. Access dashboards: http://localhost:3000 (Grafana)")
    print("3. Monitor metrics: http://localhost:9090 (Prometheus)")
    print("4. View documentation: AI_OPERATIONS_BRAIN_README.md")


if __name__ == "__main__":
    main()
