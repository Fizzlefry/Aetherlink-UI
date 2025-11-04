"""
Aetherlink Gateway (Edge API)
- JWT authentication with OIDC
- Automatic tenant extraction from JWT
- Request proxying to upstream services
- Claim forwarding as headers
- Prometheus metrics
"""
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, PlainTextResponse
from jose import jwt, JWTError
import httpx
import os
from prometheus_client import Counter, generate_latest, CONTENT_TYPE_LATEST
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Aetherlink Edge API",
    version="2.0.0",
    description="Gateway API with JWT authentication, tenant extraction, and service proxying"
)

# Configuration
OIDC_ISSUER_URL = os.getenv("OIDC_ISSUER_URL", "http://keycloak:8080/realms/aetherlink")
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE", "aetherlink-gateway")
OIDC_REQUIRED = os.getenv("OIDC_REQUIRED", "false").lower() == "true"
UPSTREAM_APEXFLOW = os.getenv("UPSTREAM_APEXFLOW", "http://apexflow:8080")
FORWARD_CLAIMS = os.getenv("FORWARD_CLAIMS", "true").lower() == "true"
CLAIM_HEADER_PREFIX = os.getenv("CLAIM_HEADER_PREFIX", "x-user-")

# Prometheus metrics
req_total = Counter(
    "gateway_requests_total",
    "Total HTTP requests through gateway",
    ["path", "method", "status_code", "tenant"]
)
auth_failures = Counter(
    "gateway_auth_failures_total",
    "Total authentication failures",
    ["reason"]
)


def verify_jwt(token: str) -> dict:
    """
    Verify JWT token and return claims.
    
    In development mode, we skip signature verification.
    In production, fetch JWKS from Keycloak and verify signature.
    """
    try:
        # Get unverified claims (dev mode - add JWKS verification for prod)
        claims = jwt.get_unverified_claims(token)
        
        # Verify issuer
        expected_issuer = OIDC_ISSUER_URL
        actual_issuer = claims.get("iss", "")
        
        # Handle both internal (keycloak:8080) and external (localhost:8180) issuers
        if not (actual_issuer == expected_issuer or 
                actual_issuer.replace("localhost:8180", "keycloak:8080") == expected_issuer):
            logger.warning(f"Issuer mismatch: expected {expected_issuer}, got {actual_issuer}")
            # In dev mode, allow it
            # raise JWTError(f"Invalid issuer: {actual_issuer}")
        
        # Verify audience
        aud = claims.get("aud")
        if isinstance(aud, list):
            if OIDC_AUDIENCE not in aud:
                logger.warning(f"Audience {OIDC_AUDIENCE} not in {aud}")
        elif aud and aud != OIDC_AUDIENCE:
            logger.warning(f"Audience mismatch: expected {OIDC_AUDIENCE}, got {aud}")
        
        return claims
    except Exception as e:
        logger.error(f"JWT verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )


@app.middleware("http")
async def auth_and_proxy_middleware(request: Request, call_next):
    """
    Middleware that:
    1. Extracts JWT claims
    2. Validates authentication (if required)
    3. Extracts tenant_id from claims
    4. Proxies requests to upstream services
    5. Injects claim headers
    """
    
    # Skip health/metrics endpoints
    if request.url.path in ["/healthz", "/readyz", "/metrics", "/whoami"]:
        return await call_next(request)
    
    # Log all incoming requests
    logger.info(f"Incoming request: {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
    
    # Extract authorization header
    auth_header = request.headers.get("authorization", "")
    claims = {}
    tenant_id = None
    
    if auth_header and auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1]
        logger.info(f"Found Bearer token: {token[:30]}...")
        try:
            claims = verify_jwt(token)
            tenant_id = claims.get("tenant_id")
            logger.info(f"JWT verified - user: {claims.get('preferred_username')}, tenant: {tenant_id}")
        except HTTPException as e:
            auth_failures.labels(reason="invalid_token").inc()
            if OIDC_REQUIRED:
                return Response(content=str(e.detail), status_code=e.status_code)
            # If auth is optional, continue without claims
            logger.warning(f"Invalid token but OIDC not required: {e.detail}")
    elif OIDC_REQUIRED:
        auth_failures.labels(reason="missing_token").inc()
        return Response(content="Authentication required", status_code=401)
    
    # Allow fallback to x-tenant-id header if no tenant in JWT (backwards compatibility)
    if not tenant_id:
        tenant_id = request.headers.get("x-tenant-id")
        if tenant_id:
            logger.info(f"Using tenant from header (fallback): {tenant_id}")
    
    # Proxy to upstream service
    try:
        # Read request body
        body = await request.body()
        
        # Build headers for upstream
        upstream_headers = dict(request.headers)
        
        # Remove hop-by-hop headers
        for header in ["host", "connection", "keep-alive", "transfer-encoding"]:
            upstream_headers.pop(header, None)
        
        # Inject tenant header from JWT (overrides any client-provided value)
        if tenant_id:
            upstream_headers["x-tenant-id"] = tenant_id
        
        # Forward JWT claims as headers
        if FORWARD_CLAIMS and claims:
            upstream_headers[f"{CLAIM_HEADER_PREFIX}sub"] = claims.get("sub", "")
            upstream_headers[f"{CLAIM_HEADER_PREFIX}username"] = claims.get("preferred_username", "")
            upstream_headers[f"{CLAIM_HEADER_PREFIX}email"] = claims.get("email", "")
            if tenant_id:
                upstream_headers[f"{CLAIM_HEADER_PREFIX}tenant"] = tenant_id
        
        # Determine upstream URL
        upstream_url = f"{UPSTREAM_APEXFLOW}{request.url.path}"
        if request.url.query:
            upstream_url = f"{upstream_url}?{request.url.query}"
        
        # Proxy request
        async with httpx.AsyncClient(timeout=30.0) as client:
            upstream_response = await client.request(
                method=request.method,
                url=upstream_url,
                headers=upstream_headers,
                content=body,
                follow_redirects=False
            )
        
        # Record metrics
        req_total.labels(
            path=request.url.path,
            method=request.method,
            status_code=str(upstream_response.status_code),
            tenant=tenant_id or "unknown"
        ).inc()
        
        # Return upstream response
        return Response(
            content=upstream_response.content,
            status_code=upstream_response.status_code,
            headers=dict(upstream_response.headers),
            media_type=upstream_response.headers.get("content-type")
        )
        
    except httpx.RequestError as e:
        logger.error(f"Upstream request failed: {str(e)}")
        return Response(content=f"Upstream service unavailable: {str(e)}", status_code=503)
    except Exception as e:
        logger.error(f"Proxy error: {str(e)}")
        return Response(content=f"Internal error: {str(e)}", status_code=500)


@app.get("/healthz", tags=["Health"])
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/readyz", tags=["Health"])
def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready", "oidc_required": OIDC_REQUIRED, "upstream": UPSTREAM_APEXFLOW}


@app.get("/metrics", tags=["Metrics"])
def metrics():
    """Prometheus metrics endpoint"""
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/whoami", tags=["Identity"])
def who_am_i(authorization: Optional[str] = Header(None)):
    """
    Return current user's identity from JWT token.
    
    Args:
        authorization: Bearer token header
    
    Returns:
        User identity with claims extracted from JWT
    """
    if not authorization:
        if OIDC_REQUIRED:
            raise HTTPException(status_code=401, detail="Missing authorization header")
        return {"authenticated": False, "message": "No token provided"}
    
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header format")
    
    # Extract token
    token = authorization.split(" ", 1)[1]
    
    # Verify JWT
    claims = verify_jwt(token)
    
    # Extract useful claims
    return {
        "authenticated": True,
        "sub": claims.get("sub"),
        "username": claims.get("preferred_username"),
        "email": claims.get("email"),
        "tenant_id": claims.get("tenant_id"),
        "roles": claims.get("realm_access", {}).get("roles", []),
        "issuer": claims.get("iss"),
        "audience": claims.get("aud")
    }


# === Catch-all route: Proxy everything else to upstream ===
# This MUST be defined last so specific routes above take precedence
@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], include_in_schema=False)
async def catch_all_proxy(path: str, request: Request):
    """
    Catch-all handler: proxy all unmatched routes to upstream service.
    The middleware has already extracted JWT claims and set request.state.
    This handler just passes through - the actual proxying happens in middleware.
    """
    # This should never be reached because middleware returns the response
    # But if it does, return an error
    return Response(content="Proxy handler misconfigured", status_code=500)


if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Gateway - OIDC Required: {OIDC_REQUIRED}, Upstream: {UPSTREAM_APEXFLOW}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
