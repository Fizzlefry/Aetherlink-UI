# Shim for legacy imports: admin_required
from fastapi import Header
from typing import List, Optional
async def admin_required(x_user_roles: Optional[str] = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

def require_roles(allowed_roles: List[str]):
    async def dependency(x_user_roles: Optional[str] = Header(default="")):
        roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
        allowed = {ar.lower() for ar in allowed_roles}
        if not any(r in allowed for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
    return dependency

# services/command-center/rbac.py

from typing import List, Optional
from fastapi import Header, HTTPException, status

# core helper: “I need one of these roles”
def require_roles(allowed_roles: List[str]):
    async def dependency(x_user_roles: Optional[str] = Header(default="")):
        roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
        allowed = {ar.lower() for ar in allowed_roles}
        if not any(r in allowed for r in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions",
            )
    return dependency

# some routers call this name instead of require_roles
def role_required(role: str):
    return require_roles([role])

# ===== common one-off helpers some routers like to import =====

# used by admin-only /docs-like or operator dashboards
async def admin_required(x_user_roles: Optional[str] = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )

# often used for operational endpoints, e.g. replay, alerts, etc.
async def operator_required(x_user_roles: Optional[str] = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if "operator" not in roles and "admin" not in roles:
        # let admin through too
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )

# sometimes systems expect this for webhook/test/system calls
async def system_required(x_user_roles: Optional[str] = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if "system" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System role required",
        )
