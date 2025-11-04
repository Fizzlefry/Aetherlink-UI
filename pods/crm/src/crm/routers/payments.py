"""
Stripe payment integration for proposal deposits.
"""
import os
import json
from datetime import datetime
from typing import Optional
import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status, BackgroundTasks
from sqlalchemy.orm import Session
from prometheus_client import Counter

from ..db import get_db
from ..auth_routes import get_current_user
from ..models_v2 import Attachment, PortalActivity, Lead

router = APIRouter(prefix="/payments", tags=["payments"])

# Configuration
DEPOSIT_PERCENT = float(os.getenv("DEPOSIT_PERCENT", "30"))
PORTAL_PUBLIC_URL = os.getenv("PORTAL_PUBLIC_URL", "http://localhost:5173")

# Configure Stripe (only if valid key is set)
stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
if stripe_key and len(stripe_key) > 30:
    stripe.api_key = stripe_key

# Prometheus metrics
PAYMENTS_TOTAL = Counter(
    "crm_portal_payments_total",
    "Portal payments (count)",
    ["org_id"]
)

PAYMENTS_AMOUNT_SUM = Counter(
    "crm_portal_payment_amount_cents_sum",
    "Portal payments total amount (cents)",
    ["org_id"]
)


@router.post("/checkout_session")
def create_checkout_session(
    proposal_id: int,
    amount_dollars: float,
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """
    Create a Stripe Checkout session for proposal deposit payment.
    
    In dev mode (no valid STRIPE_SECRET_KEY), returns mock checkout URL.
    
    Args:
        proposal_id: The proposal/lead ID
        amount_dollars: Total proposal amount in dollars
    """
    # Validate amount
    if amount_dollars <= 0:
        raise HTTPException(status_code=400, detail="Amount must be positive")
    
    # Compute deposit
    amount_cents = int(round(amount_dollars * 100))
    deposit_cents = int(round(amount_cents * (DEPOSIT_PERCENT / 100.0)))
    
    if deposit_cents < 100:  # $1 minimum
        deposit_cents = 100
    
    # Check if Stripe is configured (valid key is > 30 chars)
    stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
    dev_mode = not stripe_key or len(stripe_key) <= 30
    
    if dev_mode:
        # Dev mode: return mock checkout URL
        mock_session_id = f"cs_test_mock_{proposal_id}_{int(datetime.now().timestamp())}"
        activity = PortalActivity(
            org_id=user.org_id,
            customer_id=0,
            proposal_id=proposal_id,
            event="checkout_created",
            meta={"session_id": mock_session_id, "deposit_cents": deposit_cents, "dev_mode": True}
        )
        db.add(activity)
        db.commit()
        
        return {
            "checkout_url": f"{PORTAL_PUBLIC_URL}/proposal/{proposal_id}?mock_payment=true",
            "session_id": mock_session_id,
            "deposit_cents": deposit_cents,
            "total_cents": amount_cents,
            "dev_mode": True
        }
    
    # Production mode: Create Stripe Checkout Session
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": f"Deposit for Proposal #{proposal_id}",
                            "description": f"{DEPOSIT_PERCENT:.0f}% deposit (${deposit_cents/100:.2f} of ${amount_dollars:.2f})",
                        },
                        "unit_amount": deposit_cents,
                    },
                    "quantity": 1,
                }
            ],
            success_url=f"{PORTAL_PUBLIC_URL}/proposal/{proposal_id}?approved=true",
            cancel_url=f"{PORTAL_PUBLIC_URL}/proposal/{proposal_id}?cancelled=true",
            metadata={
                "proposal_id": str(proposal_id),
                "org_id": str(user.org_id),
                "deposit_percent": str(DEPOSIT_PERCENT),
                "total_amount_cents": str(amount_cents),
            },
        )
        
        # Log checkout session creation
        activity = PortalActivity(
            org_id=user.org_id,
            customer_id=0,
            proposal_id=proposal_id,
            event="checkout_created",
            meta={"session_id": session.id, "deposit_cents": deposit_cents}
        )
        db.add(activity)
        db.commit()
        
        return {
            "checkout_url": session.url,
            "session_id": session.id,
            "deposit_cents": deposit_cents,
            "total_cents": amount_cents
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Stripe error: {str(e)}")


@router.post("/webhook")
async def stripe_webhook(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Handle Stripe webhook events.
    Processes checkout.session.completed to mark proposals as paid.
    Triggers auto-invoice creation in QuickBooks (if connected).
    """
    payload = await request.body()
    sig = request.headers.get("stripe-signature")
    whsec = os.getenv("STRIPE_WEBHOOK_SECRET", "")
    
    event = None
    try:
        if whsec:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload=payload,
                sig_header=sig,
                secret=whsec
            )
        else:
            # Development mode: accept without verification
            event = json.loads(payload.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")
    
    # Handle checkout.session.completed event
    if event.get("type") == "checkout.session.completed":
        obj = event["data"]["object"]
        metadata = obj.get("metadata", {})
        
        proposal_id = int(metadata.get("proposal_id", "0"))
        org_id = int(metadata.get("org_id", "0"))
        amount_total = int(obj.get("amount_total", 0))  # cents
        
        if proposal_id and org_id:
            # Log payment success
            activity = PortalActivity(
                org_id=org_id,
                customer_id=0,
                proposal_id=proposal_id,
                event="payment_success",
                meta={
                    "amount_cents": amount_total,
                    "stripe_session_id": obj.get("id"),
                    "payment_status": obj.get("payment_status")
                }
            )
            db.add(activity)
            db.commit()
            
            # Increment metrics
            PAYMENTS_TOTAL.labels(org_id=str(org_id)).inc()
            PAYMENTS_AMOUNT_SUM.labels(org_id=str(org_id)).inc(amount_total)
            
            # Trigger QuickBooks invoice creation in background
            from crm.routers.qbo import create_invoice_background
            background_tasks.add_task(create_invoice_background, proposal_id, org_id, db)
    
    return {"received": True}
