"""
AetherLink Auto-Heal Service

Monitors service health and automatically restarts failed containers.
Provides API endpoints for monitoring and status reporting.
"""

import os
import time
import json
from typing import Dict, List, Any
import httpx
import docker
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="AetherLink Auto-Heal", version="0.1.0")

# CORS for UI access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Services to watch (container names)
WATCH: List[str] = json.loads(
    os.getenv(
        "AUTOHEAL_SERVICES",
        '["aether-crm-ui","aether-command-center","aether-ai-orchestrator"]'
    )
)

# Health check endpoints for each service
HEALTH_ENDPOINTS: Dict[str, str] = json.loads(
    os.getenv(
        "AUTOHEAL_HEALTH_ENDPOINTS",
        '{"aether-command-center":"http://aether-command-center:8000/ops/ping","aether-ai-orchestrator":"http://aether-ai-orchestrator:8001/ping"}'
    )
)

# Check interval in seconds
INTERVAL = int(os.getenv("AUTOHEAL_INTERVAL_SECONDS", "30"))

# Docker client for container management
docker_client = docker.from_env()

# Last report cache
last_report: Dict[str, Any] = {
    "last_run": None,
    "attempts": [],
}

# History of healing attempts (keep last 50)
healing_history: List[Dict[str, Any]] = []
MAX_HISTORY = 50


def check_service(name: str) -> bool:
    """
    Check if a service is healthy.
    
    Args:
        name: Container name to check
        
    Returns:
        True if service is healthy, False otherwise
    """
    url = HEALTH_ENDPOINTS.get(name)
    
    if not url:
        # If no health URL, just check docker status
        try:
            container = docker_client.containers.get(name)
            return container.status == "running"
        except Exception:
            return False
    
    # Check via HTTP health endpoint
    try:
        resp = httpx.get(url, timeout=2.5)
        return resp.status_code == 200
    except Exception:
        return False


def restart_service(name: str) -> tuple[bool, str]:
    """
    Attempt to restart a failed service container.
    
    Args:
        name: Container name to restart
        
    Returns:
        Tuple of (success: bool, message: str)
    """
    try:
        container = docker_client.containers.get(name)
        container.restart()
        return True, "restarted"
    except Exception as e:
        return False, str(e)


@app.get("/autoheal/status")
def autoheal_status():
    """
    Get current auto-heal status and last run report.
    
    Returns:
        Status including watched services and last healing attempts
    """
    return {
        "watching": WATCH,
        "interval_seconds": INTERVAL,
        "last_report": last_report,
    }


@app.get("/autoheal/history")
def autoheal_history(limit: int = 10):
    """
    Get history of healing attempts.
    
    Args:
        limit: Number of recent attempts to return (default: 10, max: 50)
        
    Returns:
        List of recent healing attempts, newest first
    """
    # Limit to MAX_HISTORY
    actual_limit = min(limit, MAX_HISTORY)
    
    # Return newest first
    return {
        "history": list(reversed(healing_history[-actual_limit:])),
        "total_in_history": len(healing_history),
        "limit": actual_limit,
    }


@app.get("/autoheal/stats")
def autoheal_stats():
    """
    Get statistics about healing attempts.
    
    Returns:
        Statistics including success rate, most healed service, etc.
    """
    if not healing_history:
        return {
            "total_attempts": 0,
            "successful": 0,
            "failed": 0,
            "success_rate": 0.0,
            "services": {},
        }
    
    total = len(healing_history)
    successful = sum(1 for h in healing_history if h["success"])
    failed = total - successful
    
    # Count by service
    service_counts: Dict[str, int] = {}
    for h in healing_history:
        svc = h["service"]
        service_counts[svc] = service_counts.get(svc, 0) + 1
    
    return {
        "total_attempts": total,
        "successful": successful,
        "failed": failed,
        "success_rate": round(successful / total * 100, 2) if total > 0 else 0.0,
        "services": service_counts,
        "most_healed": max(service_counts.items(), key=lambda x: x[1])[0] if service_counts else None,
    }


@app.get("/ping")
def ping():
    """
    Simple health check endpoint.
    """
    return {"status": "ok"}


@app.get("/health")
def health():
    """
    Health check endpoint for monitoring.
    """
    return {"status": "up", "service": "auto-heal"}


def loop_once():
    """
    Run one iteration of health checks and healing attempts.
    
    Checks all watched services and restarts any that are down.
    Updates last_report with results and maintains history.
    """
    attempts = []
    
    for svc in WATCH:
        ok = check_service(svc)
        if not ok:
            print(f"Service {svc} is down, attempting restart...")
            success, msg = restart_service(svc)
            attempt = {
                "service": svc,
                "action": "restart",
                "success": success,
                "msg": msg,
                "timestamp": time.time(),
            }
            attempts.append(attempt)
            
            # Add to history
            healing_history.append(attempt)
            # Keep only last MAX_HISTORY items
            if len(healing_history) > MAX_HISTORY:
                healing_history.pop(0)
            
            if success:
                print(f"✅ Successfully restarted {svc}")
            else:
                print(f"❌ Failed to restart {svc}: {msg}")
    
    last_report["last_run"] = time.time()
    last_report["attempts"] = attempts
    
    if attempts:
        print(f"Healing attempt complete: {len(attempts)} services processed")


# Background loop for standalone execution
if __name__ == "__main__":
    print(f"🏥 AetherLink Auto-Heal starting...")
    print(f"📋 Watching services: {WATCH}")
    print(f"⏱️  Check interval: {INTERVAL}s")
    
    while True:
        loop_once()
        time.sleep(INTERVAL)
