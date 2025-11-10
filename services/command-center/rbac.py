# services/command-center/rbac.py


from fastapi import Header, HTTPException, status

# ===== Role Hierarchy =====
# viewer: read-only access to dashboards and analytics
# operator: viewer + job control (pause/resume), health monitoring
# admin: operator + adaptive actions, beta features, system configuration
# system: internal system calls (no human access)


# core helper: "I need one of these roles"
def require_roles(allowed_roles: list[str]):
    async def dependency(x_user_roles: str | None = Header(default="")):
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
async def admin_required(x_user_roles: str | None = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )


# often used for operational endpoints, e.g. replay, alerts, etc.
async def operator_required(x_user_roles: str | None = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if "operator" not in roles and "admin" not in roles:
        # let admin through too
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Operator role required",
        )


# read-only access for dashboards and analytics
async def viewer_required(x_user_roles: str | None = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if not any(role in ["viewer", "operator", "admin"] for role in roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Viewer role required",
        )


# sometimes systems expect this for webhook/test/system calls
async def system_required(x_user_roles: str | None = Header(default="")):
    roles = [r.strip().lower() for r in x_user_roles.split(",") if r.strip()]
    if "system" not in roles and "admin" not in roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System role required",
        )
