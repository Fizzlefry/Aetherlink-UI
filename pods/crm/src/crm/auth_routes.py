"""
Auth routes: login, token refresh, user management.
"""

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import Counter
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .auth import create_access_token, decode_access_token, verify_password
from .auth_models import User
from .config import settings
from .db import get_db

# Prometheus metrics
auth_attempts_total = Counter(
    "crm_auth_attempts_total",
    "Total authentication attempts",
    ["result"],  # success, failed
)

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()


# Pydantic schemas
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str | None
    org_id: int
    is_active: bool

    class Config:
        from_attributes = True


# Dependency: get current user from JWT token
async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Extract and validate JWT token, return current user."""
    token = credentials.credentials
    payload = decode_access_token(token)

    if payload is None:
        auth_attempts_total.labels(result="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id: int | None = payload.get("sub")
    if user_id is None:
        auth_attempts_total.labels(result="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if user is None or not user.is_active:
        auth_attempts_total.labels(result="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


@router.post("/login", response_model=TokenResponse)
def login(login_request: LoginRequest, db: Annotated[Session, Depends(get_db)]):
    """Authenticate user and return JWT token."""
    # Find user by email
    user = db.query(User).filter(User.email == login_request.email).first()

    if not user or not verify_password(login_request.password, user.hashed_password):
        auth_attempts_total.labels(result="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        auth_attempts_total.labels(result="failed").inc()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive",
        )

    # Create access token
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id, "org_id": user.org_id}, expires_delta=access_token_expires
    )

    auth_attempts_total.labels(result="success").inc()
    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]):
    """Get current authenticated user info."""
    return current_user
