import logging

logger = logging.getLogger(__name__)


def restart_api(reason: str) -> dict:
    """
    Restart API service (stub implementation).
    
    Args:
        reason: Reason for restart
        
    Returns:
        Status dict
    """
    logger.warning(f"ACTION STUB: restart_api called - reason: {reason}")
    return {"action": "restart_api", "status": "logged", "reason": reason}


def scale_up(service: str, replicas: int) -> dict:
    """
    Scale up a service (stub implementation).
    
    Args:
        service: Service name to scale
        replicas: Target replica count
        
    Returns:
        Status dict
    """
    logger.warning(f"ACTION STUB: scale_up called - service: {service}, replicas: {replicas}")
    return {
        "action": "scale_up",
        "status": "logged",
        "service": service,
        "replicas": replicas
    }
