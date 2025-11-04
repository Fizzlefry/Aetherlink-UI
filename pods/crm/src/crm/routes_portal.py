"""
Customer portal routes for proposal viewing and approvals.
"""
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from .db import get_db
from .auth_routes import get_current_user
from .models_v2 import PortalActivity
from .portal import send_proposal_email, signed_proposal_url
from .metrics import CRM_EMAILS_SENT, CRM_PORTAL_VIEWS, CRM_PORTAL_APPROVALS

router = APIRouter(prefix="/portal", tags=["portal"])


@router.get("/me")
def portal_me(user=Depends(get_current_user)):
    """Get current user identity for portal."""
    return {"email": user.email, "org_id": user.org_id, "full_name": user.full_name}


@router.get("/proposals")
def list_proposals(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """List proposals (MVP stub - will be implemented in Sprint 3)."""
    return {"items": []}


@router.get("/proposals/{proposal_id}")
def get_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Get a signed URL for a proposal PDF.
    Object name convention: proposals/org-{org_id}/lead-{proposal_id}-{timestamp}.pdf
    """
    # For now, use simplified path - in production would query attachments table
    object_name = f"proposals/lead-{proposal_id}-*.pdf"  # Will need to query actual filename
    
    try:
        url = signed_proposal_url(object_name, 3600)
        
        # Log view event
        CRM_PORTAL_VIEWS.labels(event="view").inc()
        activity = PortalActivity(
            org_id=user.org_id,
            customer_id=0,  # TODO: link to actual customer when implemented
            proposal_id=proposal_id,
            event="view"
        )
        db.add(activity)
        db.commit()
        
        return {"url": url, "proposal_id": proposal_id, "expires_in_seconds": 3600}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Proposal not found: {str(e)}")


@router.post("/approve/{proposal_id}")
def approve_proposal(
    proposal_id: int,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """Approve a proposal."""
    # Increment approval metric
    CRM_PORTAL_APPROVALS.inc()
    
    # Log approval event
    activity = PortalActivity(
        org_id=user.org_id,
        customer_id=0,  # TODO: link to actual customer
        proposal_id=proposal_id,
        event="approve"
    )
    db.add(activity)
    db.commit()
    
    return {"status": "approved", "proposal_id": proposal_id}


@router.post("/email/{proposal_id}")
def email_proposal(
    proposal_id: int,
    to_email: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    """
    Send a proposal email with a 24-hour signed URL.
    Email is sent asynchronously in background.
    """
    # Generate 24-hour signed URL
    object_name = f"proposals/lead-{proposal_id}-*.pdf"
    
    try:
        url = signed_proposal_url(object_name, 24*3600)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Proposal not found: {str(e)}")
    
    def _send():
        """Background task to send email and log activity."""
        try:
            send_proposal_email(to_email=to_email, proposal_url=url, org_name="PeakPro CRM")
            
            # Increment email metric
            CRM_EMAILS_SENT.labels(type="proposal").inc()
            
            # Log email sent event
            activity = PortalActivity(
                org_id=user.org_id,
                customer_id=0,
                proposal_id=proposal_id,
                event="email_sent",
                meta={"to": to_email}
            )
            db.add(activity)
            db.commit()
        except Exception as e:
            print(f"Error sending email: {e}")
    
    background.add_task(_send)
    
    return {"status": "queued", "proposal_id": proposal_id, "to": to_email}
