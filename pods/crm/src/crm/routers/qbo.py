"""
QuickBooks Online (QBO) Integration Router
OAuth 2.0 authentication, invoice creation, and sync endpoints.
"""
import os
import json
import requests
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from authlib.integrations.requests_client import OAuth2Session
from prometheus_client import Counter

from ..db import get_db
from ..auth_routes import get_current_user
from ..models_v2 import Lead, PortalActivity

router = APIRouter(prefix="/qbo", tags=["qbo"])

# QuickBooks OAuth URLs
QBO_AUTH_URL = "https://appcenter.intuit.com/connect/oauth2"
QBO_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
QBO_API_BASE_SANDBOX = "https://sandbox-quickbooks.api.intuit.com/v3/company"
QBO_API_BASE_PROD = "https://quickbooks.api.intuit.com/v3/company"

SCOPES = "com.intuit.quickbooks.accounting openid profile email phone address"
HDRS = {"Accept": "application/json", "Content-Type": "application/json"}

# Prometheus metrics
QBO_INVOICES_TOTAL = Counter(
    "crm_invoices_generated_total",
    "Invoices created in QuickBooks Online",
    ["org_id"]
)

QBO_ERRORS_TOTAL = Counter(
    "crm_qbo_api_errors_total",
    "QuickBooks Online API failures",
    ["org_id", "op"]
)


def _cfg():
    """Get QBO configuration from environment."""
    return {
        "client_id": os.getenv("QBO_CLIENT_ID", ""),
        "client_secret": os.getenv("QBO_CLIENT_SECRET", ""),
        "redirect_uri": os.getenv("QBO_REDIRECT_URI", "http://localhost:8089/qbo/oauth/callback"),
        "env": os.getenv("QBO_ENV", "sandbox"),
        "item_name": os.getenv("QBO_ITEM_NAME_DEPOSIT", "Roof Deposit"),
    }


def _get_api_base(env: str = "sandbox") -> str:
    """Get QBO API base URL for environment."""
    return QBO_API_BASE_PROD if env == "production" else QBO_API_BASE_SANDBOX


def _get_token_row(db: Session, org_id: int):
    """Retrieve QBO tokens for an organization."""
    result = db.execute(
        text("SELECT * FROM qbo_tokens WHERE org_id=:oid"),
        {"oid": org_id}
    ).mappings().first()
    return dict(result) if result else None


def _upsert_tokens(
    db: Session,
    org_id: int,
    realm_id: str,
    access: str,
    refresh: str,
    expires_at: datetime,
    env: str
):
    """Insert or update QBO tokens for an organization."""
    existing = _get_token_row(db, org_id)
    if existing:
        db.execute(text("""
            UPDATE qbo_tokens 
            SET realm_id=:r, access_token=:a, refresh_token=:rf, 
                expires_at=:e, env=:env, updated_at=CURRENT_TIMESTAMP
            WHERE org_id=:oid
        """), {"r": realm_id, "a": access, "rf": refresh, "e": expires_at, "env": env, "oid": org_id})
    else:
        db.execute(text("""
            INSERT INTO qbo_tokens (org_id, realm_id, access_token, refresh_token, expires_at, env)
            VALUES (:oid, :r, :a, :rf, :e, :env)
        """), {"oid": org_id, "r": realm_id, "a": access, "rf": refresh, "e": expires_at, "env": env})
    db.commit()


def _refresh_if_needed(db: Session, org_id: int):
    """Refresh QBO access token if expired or expiring soon."""
    row = _get_token_row(db, org_id)
    if not row:
        return None
    
    # Check if token is still valid (with 2-minute buffer)
    if row["expires_at"] and datetime.utcnow() < row["expires_at"] - timedelta(minutes=2):
        return row  # Token still good
    
    # Need to refresh
    c = _cfg()
    if not c["client_id"] or not c["client_secret"]:
        return row  # Cannot refresh without credentials
    
    try:
        sess = OAuth2Session(c["client_id"], c["client_secret"])
        new_token = sess.refresh_token(
            QBO_TOKEN_URL,
            refresh_token=row["refresh_token"],
            grant_type="refresh_token",
        )
        expires_at = datetime.utcnow() + timedelta(seconds=int(new_token.get("expires_in", 3600)))
        _upsert_tokens(
            db,
            org_id,
            row["realm_id"],
            new_token["access_token"],
            new_token["refresh_token"],
            expires_at,
            row["env"]
        )
        return _get_token_row(db, org_id)
    except Exception as e:
        QBO_ERRORS_TOTAL.labels(org_id=str(org_id), op="refresh_token").inc()
        raise HTTPException(400, f"Token refresh failed: {str(e)}")


@router.get("/oauth/start")
def qbo_oauth_start(user=Depends(get_current_user)):
    """
    Initiate QuickBooks OAuth 2.0 flow.
    Redirects to Intuit authorization page.
    """
    c = _cfg()
    if not c["client_id"] or not c["client_secret"]:
        raise HTTPException(400, "QBO client_id/client_secret not configured. Set QBO_CLIENT_ID and QBO_CLIENT_SECRET environment variables.")
    
    sess = OAuth2Session(
        c["client_id"],
        c["client_secret"],
        scope=SCOPES,
        redirect_uri=c["redirect_uri"]
    )
    uri, state = sess.create_authorization_url(QBO_AUTH_URL, prompt="consent")
    
    return RedirectResponse(uri)


@router.get("/oauth/callback")
def qbo_oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Handle QuickBooks OAuth callback.
    Exchange authorization code for access/refresh tokens.
    """
    c = _cfg()
    code = request.query_params.get("code")
    realm_id = request.query_params.get("realmId")
    
    if not code or not realm_id:
        raise HTTPException(400, "Missing authorization code or realmId from QuickBooks")
    
    try:
        sess = OAuth2Session(
            c["client_id"],
            c["client_secret"],
            redirect_uri=c["redirect_uri"]
        )
        token = sess.fetch_token(
            QBO_TOKEN_URL,
            code=code,
            grant_type="authorization_code"
        )
        
        expires_at = datetime.utcnow() + timedelta(seconds=int(token.get("expires_in", 3600)))
        _upsert_tokens(
            db,
            user.org_id,
            realm_id,
            token["access_token"],
            token["refresh_token"],
            expires_at,
            c["env"]
        )
        
        return {
            "status": "connected",
            "realm_id": realm_id,
            "env": c["env"],
            "org_id": user.org_id
        }
    except Exception as e:
        QBO_ERRORS_TOTAL.labels(org_id=str(user.org_id), op="oauth_callback").inc()
        raise HTTPException(400, f"OAuth token exchange failed: {str(e)}")


@router.get("/status")
def qbo_connection_status(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Check QuickBooks connection status for current organization."""
    row = _get_token_row(db, user.org_id)
    if not row:
        return {"connected": False}
    
    return {
        "connected": True,
        "realm_id": row["realm_id"],
        "env": row["env"],
        "expires_at": row["expires_at"].isoformat() if row["expires_at"] else None,
        "expired": row["expires_at"] and datetime.utcnow() >= row["expires_at"]
    }


@router.post("/invoice/{proposal_id}")
def create_invoice_for_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Create a QuickBooks invoice for a proposal.
    
    Maps proposal deposit amount to QBO invoice with single line item.
    Stores QBO invoice ID in portal_activity_log for audit trail.
    """
    # Get and refresh tokens
    row = _refresh_if_needed(db, user.org_id)
    if not row:
        raise HTTPException(
            400,
            "QuickBooks not connected for your organization. Visit /qbo/oauth/start to connect."
        )
    
    realm_id = row["realm_id"]
    access_token = row["access_token"]
    env = row["env"]
    
    # Get proposal details from portal_activity_log (latest payment_success event)
    activity = db.query(PortalActivity).filter(
        PortalActivity.org_id == user.org_id,
        PortalActivity.proposal_id == proposal_id,
        PortalActivity.event == "payment_success"
    ).order_by(PortalActivity.created_at.desc()).first()
    
    if not activity:
        raise HTTPException(404, f"No payment found for proposal #{proposal_id}")
    
    # Extract amount from metadata
    amount_cents = activity.meta.get("amount_cents", 0) if activity.meta else 0
    amount_usd = round(amount_cents / 100.0, 2)
    
    if amount_usd <= 0:
        raise HTTPException(400, "Invalid payment amount")
    
    # Build QBO invoice payload
    c = _cfg()
    invoice_payload = {
        "CustomerRef": {
            "value": "1",  # Default customer ID (can be enhanced to lookup by email)
            "name": "PeakPro Customer"
        },
        "PrivateNote": f"Auto-created from PeakPro CRM (Proposal #{proposal_id})",
        "TxnDate": datetime.utcnow().strftime("%Y-%m-%d"),
        "Line": [{
            "DetailType": "SalesItemLineDetail",
            "Amount": amount_usd,
            "SalesItemLineDetail": {
                "ItemRef": {
                    "value": "1",  # Default item ID (can be configured)
                    "name": c["item_name"]
                }
            }
        }]
    }
    
    # Call QBO API
    api_base = _get_api_base(env)
    url = f"{api_base}/{realm_id}/invoice?minorversion=65"
    
    try:
        response = requests.post(
            url,
            headers={**HDRS, "Authorization": f"Bearer {access_token}"},
            data=json.dumps(invoice_payload)
        )
        
        if response.status_code >= 300:
            QBO_ERRORS_TOTAL.labels(org_id=str(user.org_id), op="create_invoice").inc()
            raise HTTPException(400, f"QuickBooks API error: {response.text}")
        
        data = response.json()
        qbo_invoice_id = data.get("Invoice", {}).get("Id")
        
        # Log invoice creation
        invoice_activity = PortalActivity(
            org_id=user.org_id,
            customer_id=0,
            proposal_id=proposal_id,
            event="invoice_created",
            meta={
                "qbo_invoice_id": qbo_invoice_id,
                "amount_usd": amount_usd,
                "env": env,
                "realm_id": realm_id
            }
        )
        db.add(invoice_activity)
        db.commit()
        
        # Increment metrics
        QBO_INVOICES_TOTAL.labels(org_id=str(user.org_id)).inc()
        
        return {
            "status": "created",
            "qbo_invoice_id": qbo_invoice_id,
            "amount_usd": amount_usd,
            "proposal_id": proposal_id,
            "env": env
        }
    
    except requests.exceptions.RequestException as e:
        QBO_ERRORS_TOTAL.labels(org_id=str(user.org_id), op="create_invoice").inc()
        raise HTTPException(500, f"QuickBooks API request failed: {str(e)}")


def create_invoice_background(proposal_id: int, org_id: int, db: Session):
    """
    Background task to create QBO invoice after Stripe payment.
    Called by Stripe webhook handler.
    """
    try:
        row = _refresh_if_needed(db, org_id)
        if not row:
            # QBO not connected, skip invoice creation
            return
        
        # Check if invoice already created
        existing = db.query(PortalActivity).filter(
            PortalActivity.org_id == org_id,
            PortalActivity.proposal_id == proposal_id,
            PortalActivity.event == "invoice_created"
        ).first()
        
        if existing:
            return  # Already created
        
        # Get payment activity
        payment = db.query(PortalActivity).filter(
            PortalActivity.org_id == org_id,
            PortalActivity.proposal_id == proposal_id,
            PortalActivity.event == "payment_success"
        ).order_by(PortalActivity.created_at.desc()).first()
        
        if not payment:
            return  # No payment found
        
        amount_cents = payment.meta.get("amount_cents", 0) if payment.meta else 0
        amount_usd = round(amount_cents / 100.0, 2)
        
        if amount_usd <= 0:
            return
        
        # Create invoice
        c = _cfg()
        realm_id = row["realm_id"]
        access_token = row["access_token"]
        env = row["env"]
        
        invoice_payload = {
            "CustomerRef": {"value": "1", "name": "PeakPro Customer"},
            "PrivateNote": f"Auto-created from PeakPro CRM (Proposal #{proposal_id})",
            "TxnDate": datetime.utcnow().strftime("%Y-%m-%d"),
            "Line": [{
                "DetailType": "SalesItemLineDetail",
                "Amount": amount_usd,
                "SalesItemLineDetail": {
                    "ItemRef": {"value": "1", "name": c["item_name"]}
                }
            }]
        }
        
        api_base = _get_api_base(env)
        url = f"{api_base}/{realm_id}/invoice?minorversion=65"
        
        response = requests.post(
            url,
            headers={**HDRS, "Authorization": f"Bearer {access_token}"},
            data=json.dumps(invoice_payload),
            timeout=10
        )
        
        if response.status_code < 300:
            data = response.json()
            qbo_invoice_id = data.get("Invoice", {}).get("Id")
            
            # Log success
            invoice_activity = PortalActivity(
                org_id=org_id,
                customer_id=0,
                proposal_id=proposal_id,
                event="invoice_created",
                meta={
                    "qbo_invoice_id": qbo_invoice_id,
                    "amount_usd": amount_usd,
                    "env": env,
                    "auto_created": True
                }
            )
            db.add(invoice_activity)
            db.commit()
            
            QBO_INVOICES_TOTAL.labels(org_id=str(org_id)).inc()
        else:
            QBO_ERRORS_TOTAL.labels(org_id=str(org_id), op="auto_invoice").inc()
    
    except Exception:
        # Silent fail - don't break Stripe webhook processing
        QBO_ERRORS_TOTAL.labels(org_id=str(org_id), op="auto_invoice").inc()
