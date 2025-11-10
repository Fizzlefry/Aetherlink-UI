#!/usr/bin/env python3
"""
AetherLink Auto-Heal Worker

Polls for pending auto-heal tasks and executes remediation actions.
Phase XXII: Auto-heal implementation for vertical services.

Supported actions:
- docker compose restart <service> (for containerized services)
- Future: Kubernetes deployments, systemd services, etc.
"""

import asyncio
import os
import subprocess
import sys

import httpx

# Add services/command-center to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "services", "command-center"))


# Configuration
COMMAND_CENTER_URL = os.getenv("COMMAND_CENTER_URL", "http://localhost:8010")
POLL_INTERVAL = int(os.getenv("AUTOHEAL_POLL_INTERVAL", "30"))  # seconds

# Service mapping: which services we can heal and how
HEALABLE_SERVICES = {
    "roofwonder": {
        "type": "docker-compose",
        "compose_file": "./deploy/docker-compose.dev.yml",
        "service_name": "roofwonder",
    },
    "peakpro-crm": {
        "type": "docker-compose",
        "compose_file": "./deploy/docker-compose.dev.yml",
        "service_name": "crm-api",
    },
    "policypal-ai": {
        "type": "docker-compose",
        "compose_file": "./deploy/docker-compose.dev.yml",
        "service_name": "policypal-ai",
    },
}


async def poll_autoheal_tasks():
    """
    Poll Command Center for pending auto-heal tasks.
    In a real implementation, this would query a task queue.
    For now, we'll simulate by checking recent alerts.
    """
    try:
        # For demo: check recent alerts and simulate auto-heal tasks
        # In production, you'd have a proper task queue (Redis, database table, etc.)
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{COMMAND_CENTER_URL}/alerts/operator-view?limit=10")
            if response.status_code == 200:
                alerts = response.json()
                for alert in alerts:
                    # Check if this alert needs auto-healing
                    service = alert.get("labels", {}).get("service")
                    severity = alert.get("severity", "info")
                    fingerprint = alert.get("fingerprint")

                    if (
                        service in HEALABLE_SERVICES
                        and severity in ("critical", "error")
                        and not alert.get("autoheal_results")
                    ):  # Not already healed
                        print(
                            f"[auto-heal] 🚨 Detected critical alert for {service}, attempting heal..."
                        )
                        success, message = await execute_heal(service)

                        # Report result back to Command Center
                        result_payload = {
                            "fingerprint": fingerprint,
                            "service": service,
                            "env": alert.get("env", "local"),
                            "status": "success" if success else "failed",
                            "message": message,
                        }

                        result_response = await client.post(
                            f"{COMMAND_CENTER_URL}/alerts/autoheal-result", json=result_payload
                        )

                        if result_response.status_code == 200:
                            print(f"[auto-heal] ✅ Result reported for {service}")
                        else:
                            print(f"[auto-heal] ❌ Failed to report result: {result_response.text}")

    except Exception as e:
        print(f"[auto-heal] Error polling tasks: {e}")


async def execute_heal(service: str) -> tuple[bool, str]:
    """
    Execute healing action for a service.

    Returns: (success: bool, message: str)
    """
    if service not in HEALABLE_SERVICES:
        return False, f"Service {service} not configured for auto-healing"

    config = HEALABLE_SERVICES[service]

    if config["type"] == "docker-compose":
        try:
            # Run docker compose restart
            cmd = [
                "docker",
                "compose",
                "-f",
                config["compose_file"],
                "restart",
                config["service_name"],
            ]

            print(f"[auto-heal] 🔄 Running: {' '.join(cmd)}")

            # Run synchronously since docker commands are fast
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(__file__),  # Run from project root
            )

            if result.returncode == 0:
                return True, f"Successfully restarted {service} via docker compose"
            else:
                return False, f"Docker compose restart failed: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return False, f"Timeout restarting {service}"
        except Exception as e:
            return False, f"Error restarting {service}: {str(e)}"

    else:
        return False, f"Unsupported heal type: {config['type']}"


async def main():
    """Main auto-heal worker loop."""
    print("[auto-heal] 🚀 Starting AetherLink Auto-Heal Worker")
    print(f"[auto-heal] 📡 Command Center: {COMMAND_CENTER_URL}")
    print(f"[auto-heal] ⏰ Poll interval: {POLL_INTERVAL}s")
    print(f"[auto-heal] 🔧 Healable services: {list(HEALABLE_SERVICES.keys())}")

    while True:
        await poll_autoheal_tasks()
        await asyncio.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    asyncio.run(main())
