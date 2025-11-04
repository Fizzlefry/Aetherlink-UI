"""
Security middleware for Autoheal production deployment
- OIDC authentication for /audit and /console endpoints
- CORS configuration
- Rate limiting
- Security headers
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import os
import jwt
import time
from typing import List, Optional

# Configuration
OIDC_ENABLED = os.getenv("AUTOHEAL_OIDC_ENABLED", "false").lower() == "true"
OIDC_ISSUER = os.getenv("OIDC_ISSUER", "https://auth.aetherlink.io")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "autoheal-api")
OIDC_JWKS_URL = os.getenv("OIDC_JWKS_URL", f"{OIDC_ISSUER}/.well-known/jwks.json")

# CORS configuration
CORS_ENABLED = os.getenv("AUTOHEAL_CORS_ENABLED", "false").lower() == "true"
CORS_ORIGINS = os.getenv("AUTOHEAL_CORS_ORIGINS", "https://command.aetherlink.io").split(",")

# Protected endpoints (require OIDC in production)
PROTECTED_PATHS = ["/audit", "/console", "/ack"]

# Rate limiting (simple in-memory tracking)
_RATE_LIMIT_STORE = {}
RATE_LIMIT_ENABLED = os.getenv("AUTOHEAL_RATE_LIMIT_ENABLED", "true").lower() == "true"
RATE_LIMIT_REQUESTS = int(os.getenv("AUTOHEAL_RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_WINDOW = int(os.getenv("AUTOHEAL_RATE_LIMIT_WINDOW", "60"))


class OIDCMiddleware(BaseHTTPMiddleware):
    """OIDC authentication middleware for protected endpoints"""
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth if OIDC disabled (dev mode)
        if not OIDC_ENABLED:
            return await call_next(request)
        
        # Check if path requires authentication
        path = request.url.path
        if not any(path.startswith(protected) for protected in PROTECTED_PATHS):
            return await call_next(request)
        
        # Extract bearer token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing or invalid Authorization header"}
            )
        
        token = auth_header.replace("Bearer ", "")
        
        try:
            # Verify JWT (simplified - production should use jwks_client)
            payload = jwt.decode(
                token,
                options={"verify_signature": False},  # TODO: Enable signature verification in prod
                audience=OIDC_AUDIENCE,
                issuer=OIDC_ISSUER
            )
            
            # Attach user info to request state
            request.state.user = payload.get("sub")
            request.state.email = payload.get("email")
            request.state.roles = payload.get("roles", [])
            
            # Check for required role (ops or admin)
            if "ops" not in request.state.roles and "admin" not in request.state.roles:
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"detail": "Insufficient permissions. Requires 'ops' or 'admin' role."}
                )
            
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Token expired"}
            )
        except jwt.InvalidTokenError as e:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": f"Invalid token: {str(e)}"}
            )
        
        response = await call_next(request)
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple rate limiting middleware"""
    
    async def dispatch(self, request: Request, call_next):
        if not RATE_LIMIT_ENABLED:
            return await call_next(request)
        
        # Get client identifier (IP or user if authenticated)
        client_id = request.client.host if request.client else "unknown"
        if hasattr(request.state, "user"):
            client_id = request.state.user
        
        # Current window
        now = int(time.time())
        window_start = now - (now % RATE_LIMIT_WINDOW)
        key = f"{client_id}:{window_start}"
        
        # Check rate limit
        if key in _RATE_LIMIT_STORE:
            if _RATE_LIMIT_STORE[key] >= RATE_LIMIT_REQUESTS:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": f"Rate limit exceeded. Max {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW}s."},
                    headers={
                        "X-RateLimit-Limit": str(RATE_LIMIT_REQUESTS),
                        "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Reset": str(window_start + RATE_LIMIT_WINDOW)
                    }
                )
            _RATE_LIMIT_STORE[key] += 1
        else:
            _RATE_LIMIT_STORE[key] = 1
        
        # Clean old entries
        for old_key in list(_RATE_LIMIT_STORE.keys()):
            if int(old_key.split(":")[1]) < window_start - RATE_LIMIT_WINDOW:
                del _RATE_LIMIT_STORE[old_key]
        
        response = await call_next(request)
        
        # Add rate limit headers
        remaining = max(0, RATE_LIMIT_REQUESTS - _RATE_LIMIT_STORE.get(key, 0))
        response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_REQUESTS)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(window_start + RATE_LIMIT_WINDOW)
        
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
        
        return response


def configure_cors(app):
    """Configure CORS middleware"""
    if CORS_ENABLED:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=CORS_ORIGINS,
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type"],
        )


def configure_security_middleware(app):
    """Apply all security middleware to FastAPI app"""
    # Order matters: security headers -> rate limit -> OIDC auth
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(OIDCMiddleware)
    configure_cors(app)
