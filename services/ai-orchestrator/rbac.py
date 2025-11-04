"""
RBAC (Role-Based Access Control) helper for FastAPI services.

Provides a simple dependency injection pattern for protecting endpoints
based on user roles passed via the X-User-Roles header.

Roles:
- admin: Full access to all endpoints
- operator: Ops endpoints (/ops/*), read-only AI stats
- agent: CRM features (leads, AI extract)
- viewer: Read-only UI access

Usage:
    from rbac import require_roles
    from fastapi import Depends
    
    operator_only = require_roles(["operator", "admin"])
    
    @app.get("/ops/health", dependencies=[Depends(operator_only)])
    async def ops_health():
        ...
"""

from fastapi import Header, HTTPException, status
from typing import List, Optional
import json


def require_roles(allowed_roles: List[str]):
    """
    Create a FastAPI dependency that requires one of the specified roles.
    
    Args:
        allowed_roles: List of role strings that are allowed to access the endpoint
        
    Returns:
        Async dependency function for use with Depends()
        
    Raises:
        HTTPException 401: Missing X-User-Roles header
        HTTPException 400: Invalid roles format
        HTTPException 403: User doesn't have required role
        
    Example:
        operator_only = require_roles(["operator", "admin"])
        
        @app.get("/ops/health", dependencies=[Depends(operator_only)])
        async def ops_health():
            return {"status": "ok"}
    """
    async def dependency(x_user_roles: Optional[str] = Header(None)):
        """
        Expect a header like:
        X-User-Roles: ["operator","admin"]
        or
        X-User-Roles: operator,admin
        """
        if not x_user_roles:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing roles header (X-User-Roles required)",
            )
        
        # Support both JSON array and comma-separated formats
        try:
            if x_user_roles.strip().startswith("["):
                # JSON array format: ["operator", "admin"]
                roles = json.loads(x_user_roles)
            else:
                # Comma-separated format: operator,admin
                roles = [r.strip() for r in x_user_roles.split(",")]
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid roles format: {str(e)}",
            )
        
        # Check if user has at least one of the required roles
        if not any(r in allowed_roles for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required roles: {allowed_roles}",
            )
    
    return dependency


# Pre-configured role dependencies for common use cases
admin_only = require_roles(["admin"])
operator_only = require_roles(["operator", "admin"])
agent_or_higher = require_roles(["agent", "operator", "admin"])
authenticated = require_roles(["viewer", "agent", "operator", "admin"])
