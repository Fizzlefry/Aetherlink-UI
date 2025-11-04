"""
Multi-tenant API key authentication with rate limiting and quotas.
"""
from __future__ import annotations
import os
import time
from collections import deque
from typing import Dict, Literal, Optional, Tuple
from typing_extensions import TypedDict
from fastapi import Header, HTTPException, Request

from pods.customer_ops.db_duck import get_api_key, bump_api_key_counters


Role = Literal["admin", "editor", "viewer"]


class TenantContext(TypedDict):
    """Authentication context with tenant and role."""
    tenant_id: Optional[str]
    role: str


# In-memory rate limiters (per-key RPM tracking)
_rpm_limiters: dict[str, deque] = {}


def _check_rpm_limit(api_key: str, rpm_limit: int) -> bool:
    """
    Check if API key is within RPM limit using sliding window.
    
    Args:
        api_key: API key string
        rpm_limit: Requests per minute limit
    
    Returns:
        True if within limit, False if exceeded
    """
    now = time.time()
    window = 60.0  # 1 minute window
    
    # Initialize deque for this key if needed
    if api_key not in _rpm_limiters:
        _rpm_limiters[api_key] = deque()
    
    timestamps = _rpm_limiters[api_key]
    
    # Remove timestamps outside window
    while timestamps and timestamps[0] < now - window:
        timestamps.popleft()
    
    # Check limit
    if len(timestamps) >= rpm_limit:
        return False
    
    # Add current request
    timestamps.append(now)
    return True


def resolve_auth(
    request: Request,
    x_admin_key: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None)
) -> TenantContext:
    """
    Resolve authentication from headers with API key lookup and quota enforcement.
    
    Priority:
    1. x-admin-key (if matches env) -> admin role, no tenant
    2. x-api-key (lookup in DB) -> enforce quotas, return tenant + role
    3. Fallback to x-role header (dev mode, optional)
    
    Args:
        request: FastAPI request
        x_admin_key: Admin key from header
        x_api_key: API key from header
        x_role: Role from header (fallback)
    
    Returns:
        TenantContext with tenant_id and role
    
    Raises:
        HTTPException: 401 if unauthorized, 429 if rate limited
    """
    # 1) Admin key check (existing behavior)
    admin_key = os.getenv("API_ADMIN_KEY", "admin-secret-123")
    if x_admin_key and x_admin_key == admin_key:
        return TenantContext(tenant_id=None, role="admin")
    
    # 2) API key lookup
    if x_api_key:
        key_data = get_api_key(x_api_key)
        
        if not key_data:
            raise HTTPException(status_code=401, detail="Invalid API key")
        
        if not key_data.get("enabled"):
            raise HTTPException(status_code=401, detail="API key disabled")
        
        # Check RPM limit
        rpm_limit = key_data.get("rpm_limit")
        if rpm_limit is not None:
            if not _check_rpm_limit(x_api_key, rpm_limit):
                raise HTTPException(
                    status_code=429,
                    detail=f"Rate limit exceeded: {rpm_limit} requests/minute"
                )
        
        # Check daily quota
        ok, reason = bump_api_key_counters(x_api_key)
        if not ok:
            if reason == "daily_quota_exceeded":
                raise HTTPException(
                    status_code=429,
                    detail=f"Daily quota exceeded: {key_data.get('daily_quota')} requests/day"
                )
            else:
                raise HTTPException(status_code=401, detail=f"API key error: {reason}")
        
        return TenantContext(
            tenant_id=key_data.get("tenant_id"),
            role=key_data.get("role", "viewer")
        )
    
    # 3) Fallback to header-based role (dev mode)
    if x_role:
        return TenantContext(tenant_id="default", role=x_role)
    
    # No authentication provided
    raise HTTPException(status_code=401, detail="Authentication required")


# FastAPI dependency helpers
def ApiKeyRequired(
    request: Request,
    x_admin_key: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None)
) -> str:
    """
    FastAPI dependency that returns tenant_id.
    Compatible with existing endpoints expecting tenant string.
    """
    context = resolve_auth(request, x_admin_key, x_api_key, x_role)
    return context["tenant_id"] or "default"


def RequireRole(min_role: str):
    """
    Create FastAPI dependency that requires minimum role.
    
    Role hierarchy: admin > editor > viewer
    
    Usage:
        @app.post("/endpoint", dependencies=[Depends(RequireRole("editor"))])
    """
    role_order = {"viewer": 1, "editor": 2, "admin": 3}
    min_level = role_order.get(min_role, 1)
    
    def check_role(
        request: Request,
        x_admin_key: Optional[str] = Header(None),
        x_api_key: Optional[str] = Header(None),
        x_role: Optional[str] = Header(None)
    ) -> TenantContext:
        context = resolve_auth(request, x_admin_key, x_api_key, x_role)
        user_level = role_order.get(context["role"], 0)
        
        if user_level < min_level:
            raise HTTPException(
                status_code=403,
                detail=f"Requires {min_role} role or higher (you have: {context['role']})"
            )
        
        return context
    
    return check_role


def AdminOnly(
    request: Request,
    x_admin_key: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None)
) -> TenantContext:
    """FastAPI dependency requiring admin role."""
    context = resolve_auth(request, x_admin_key, x_api_key, x_role)
    if context["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return context


def EditorOrAdmin(
    request: Request,
    x_admin_key: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None),
    x_role: Optional[str] = Header(None)
) -> TenantContext:
    """FastAPI dependency requiring editor or admin role."""
    context = resolve_auth(request, x_admin_key, x_api_key, x_role)
    if context["role"] not in ("editor", "admin"):
        raise HTTPException(status_code=403, detail="Editor or admin access required")
    return context


# Legacy compatibility functions (keep for now)
def require_api_key_dynamic(enabled: bool):
    """Read keys from app.state.AUTH_KEYS each request."""
    async def dep(request: Request, x_api_key: str | None = Header(default=None, alias="x-api-key")):
        if not enabled:
            return
        keys: Dict[str, str] = getattr(request.app.state, "AUTH_KEYS", {}) or {}
        if not x_api_key or x_api_key not in keys:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
        request.state.tenant = keys[x_api_key]  # optional downstream use
        return request.state.tenant
    return dep


def require_admin_key(admin_key: str | None):
    """Simple admin gate via X-Admin-Key header (optional)."""
    async def dep(x_admin_key: str | None = Header(default=None, alias="x-admin-key")):
        if not admin_key:
            return  # disabled if not set
        if x_admin_key != admin_key:
            raise HTTPException(status_code=401, detail="Invalid or missing admin key")
    return dep


def require_role(*allowed: Role):
    """
    RBAC gate: checks x-role header against allowed roles.
    Also honors admin key (admin key = implicit admin role).
    Defaults to 'viewer' if no role header present (backward-compatible).
    """
    async def dep(
        request: Request,
        x_role: str | None = Header(default=None, alias="x-role"),
        x_admin_key: str | None = Header(default=None, alias="x-admin-key")
    ):
        # Admin key grants admin role automatically
        admin_key = getattr(request.app.state, "ADMIN_KEY", None)
        if admin_key and x_admin_key == admin_key:
            request.state.role = "admin"
            return "admin"
        
        # Default to viewer if no role specified (backward-compatible)
        role = x_role or "viewer"
        
        # Validate role
        if role not in ["admin", "editor", "viewer"]:
            raise HTTPException(status_code=403, detail=f"Invalid role: {role}")
        
        # Check if role is allowed
        if role not in allowed:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required role: {' or '.join(allowed)}. Your role: {role}"
            )
        
        request.state.role = role
        return role
    return dep