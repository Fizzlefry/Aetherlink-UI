# monitoring/autoheal/auth.py
"""
OIDC/JWT authentication for Autoheal endpoints.
Protects /audit and /console with bearer token verification.
"""
import os
import time
import json
import urllib.request
import urllib.error
from functools import lru_cache
from typing import Dict, Optional

from jose import jwt, jwk
from jose.utils import base64url_decode
from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

OIDC_ISSUER = os.getenv("OIDC_ISSUER")        # e.g. https://YOUR_DOMAIN/.well-known/openid-configuration
OIDC_AUDIENCE = os.getenv("OIDC_AUDIENCE")    # e.g. peakpro-api
OIDC_JWKS_URI = os.getenv("OIDC_JWKS_URI")    # override if needed; else discovered

security = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def _discover() -> Dict:
    """Discover OIDC configuration from issuer."""
    if OIDC_JWKS_URI:
        return {"jwks_uri": OIDC_JWKS_URI, "issuer": OIDC_ISSUER}
    try:
        with urllib.request.urlopen(OIDC_ISSUER) as r:
            data = json.load(r)
        return {"jwks_uri": data["jwks_uri"], "issuer": data["issuer"]}
    except Exception as e:
        raise RuntimeError(f"OIDC discovery failed: {e}")


@lru_cache(maxsize=1)
def _jwks() -> Dict:
    """Fetch JSON Web Key Set from OIDC provider."""
    info = _discover()
    with urllib.request.urlopen(info["jwks_uri"]) as r:
        return json.load(r)


def _get_key(header):
    """Get signing key from JWKS matching the token's kid."""
    keys = _jwks().get("keys", [])
    for k in keys:
        if k.get("kid") == header.get("kid"):
            return k
    raise HTTPException(status_code=401, detail="Unknown key id")


def _verify(token: str) -> Dict:
    """Verify JWT token signature and claims."""
    try:
        header = jwt.get_unverified_header(token)
        key = _get_key(header)
        
        # Verify signature
        message, encoded_sig = token.rsplit('.', 1)
        decoded_sig = base64url_decode(encoded_sig.encode())
        public_key = jwk.construct(key)
        if not public_key.verify(message.encode(), decoded_sig):
            raise HTTPException(status_code=401, detail="Invalid signature")

        # Verify claims
        claims = jwt.get_unverified_claims(token)
        now = int(time.time())
        
        # Check expiration
        if claims.get("exp") and now > int(claims["exp"]):
            raise HTTPException(status_code=401, detail="Token expired")
        
        # Check audience
        if OIDC_AUDIENCE:
            token_aud = claims.get("aud", [])
            if isinstance(token_aud, str):
                token_aud = [token_aud]
            if OIDC_AUDIENCE not in token_aud:
                raise HTTPException(status_code=401, detail="Invalid audience")
        
        # Check issuer
        if OIDC_ISSUER:
            token_issuer = str(claims.get("iss", ""))
            expected_issuer = str(_discover()["issuer"])
            if not token_issuer.startswith(expected_issuer):
                raise HTTPException(status_code=401, detail="Invalid issuer")
        
        return claims
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Auth error: {e}")


def require_oidc(creds: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Dict:
    """FastAPI dependency to require valid OIDC bearer token."""
    if not creds or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return _verify(creds.credentials)
