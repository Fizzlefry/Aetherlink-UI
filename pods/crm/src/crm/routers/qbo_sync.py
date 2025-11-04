"""
QuickBooks Online sync endpoints for customer and invoice management.
Sprint 5: Customer Sync + Invoice Status Poller
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth_routes import get_current_user
from ..db import get_db
from ..models_v2 import Customer, Lead
from ..qbo_sync import ensure_customer_in_qbo, poll_invoice_status

router = APIRouter(prefix="/qbo/sync", tags=["qbo-sync"])


@router.post("/customer/{customer_id}")
def sync_customer(customer_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):
    """
    Sync a CRM customer to QuickBooks Online.
    Creates new customer if doesn't exist, updates if already linked.
    """
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.org_id == user.org_id)
        .first()
    )

    if not customer:
        raise HTTPException(404, "Customer not found")

    qbo_id = ensure_customer_in_qbo(db, user.org_id, customer)

    return {"ok": bool(qbo_id), "qbo_customer_id": qbo_id, "customer_id": customer_id}


@router.post("/invoice/{proposal_id}/check")
def check_invoice_status(
    proposal_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """
    Check QuickBooks invoice status for a proposal.
    Updates local proposal with QBO status, balance, and paid amounts.
    Logs 'invoice_paid' activity if invoice became fully paid.
    """
    proposal = db.query(Lead).filter(Lead.id == proposal_id, Lead.org_id == user.org_id).first()

    if not proposal:
        raise HTTPException(404, "Proposal not found")

    changed_to_paid, error = poll_invoice_status(db, user.org_id, proposal_id)

    if error:
        return {"ok": False, "changed_to_paid": False, "error": error}

    return {
        "ok": True,
        "changed_to_paid": changed_to_paid,
        "qbo_status": getattr(proposal, "qbo_status", None),
        "qbo_balance_cents": getattr(proposal, "qbo_balance_cents", None),
        "qbo_invoice_number": getattr(proposal, "qbo_invoice_number", None),
    }


@router.post("/invoice/poll_all")
def poll_all_invoices(
    background_tasks: BackgroundTasks, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    """
    Schedule background polling of all open invoices for current organization.
    Checks QuickBooks status for all proposals with linked invoices.
    """
    # Get all proposals with QBO invoices that aren't marked Paid
    proposals = (
        db.query(Lead.id).filter(Lead.org_id == user.org_id, Lead.qbo_invoice_id.isnot(None)).all()
    )

    proposal_ids = [p.id for p in proposals]

    # Schedule background tasks
    for pid in proposal_ids:
        background_tasks.add_task(_check_invoice_bg, pid, user.org_id)

    return {"ok": True, "scheduled": len(proposal_ids), "proposal_ids": proposal_ids}


def _check_invoice_bg(proposal_id: int, org_id: int):
    """Background task to check invoice status."""
    from ..db import SessionLocal

    db = SessionLocal()
    try:
        poll_invoice_status(db, org_id, proposal_id)
    except Exception:
        pass  # Silent fail in background
    finally:
        db.close()
