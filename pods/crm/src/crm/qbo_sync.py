"""
QuickBooks Online sync utilities for customers and invoice status polling.
Sprint 5: Customer Sync + Invoice Status Poller
"""

from datetime import UTC, datetime

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

from .metrics import (
    CRM_INVOICE_PAYMENTS_CENTS,
    CRM_INVOICE_SYNC_ERRORS,
    CRM_INVOICES_PAID,
    CRM_QBO_CUSTOMER_SYNC,
)
from .models_v2 import Customer, Lead, PortalActivity


def _get_qbo_config(db: Session, org_id: int) -> dict | None:
    """Get QBO configuration and tokens for an organization."""
    row = (
        db.execute(text("SELECT * FROM qbo_tokens WHERE org_id=:oid"), {"oid": org_id})
        .mappings()
        .first()
    )

    if not row:
        return None

    env = row.get("env", "sandbox")
    api_base = (
        "https://quickbooks.api.intuit.com/v3/company"
        if env == "production"
        else "https://sandbox-quickbooks.api.intuit.com/v3/company"
    )

    return {
        "realm_id": row["realm_id"],
        "access_token": row["access_token"],
        "api_base": api_base,
        "env": env,
    }


def ensure_customer_in_qbo(db: Session, org_id: int, customer: Customer) -> str | None:
    """
    Sync CRM customer to QuickBooks Online.
    Creates new customer if doesn't exist, updates if already linked.

    Returns:
        QBO customer ID if successful, None if skipped or failed
    """
    config = _get_qbo_config(db, org_id)
    if not config:
        CRM_QBO_CUSTOMER_SYNC.labels(org_id=str(org_id), result="skipped").inc()
        return None

    try:
        headers = {
            "Authorization": f"Bearer {config['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # If already linked, try update
        if customer.qbo_customer_id:
            url = f"{config['api_base']}/{config['realm_id']}/customer?operation=update"
            payload = {
                "Id": customer.qbo_customer_id,
                "sparse": True,
                "DisplayName": customer.full_name or customer.email or f"Customer {customer.id}",
            }
            if customer.email:
                payload["PrimaryEmailAddr"] = {"Address": customer.email}

            response = requests.post(url, headers=headers, json=payload, timeout=10)
            response.raise_for_status()

            customer.qbo_last_sync_at = datetime.now(UTC)
            db.commit()

            CRM_QBO_CUSTOMER_SYNC.labels(org_id=str(org_id), result="updated").inc()
            return customer.qbo_customer_id

        # Create new customer
        url = f"{config['api_base']}/{config['realm_id']}/customer"
        payload = {
            "DisplayName": customer.full_name or customer.email or f"Customer {customer.id}",
        }
        if customer.email:
            payload["PrimaryEmailAddr"] = {"Address": customer.email}
        if customer.phone:
            payload["PrimaryPhone"] = {"FreeFormNumber": customer.phone}

        response = requests.post(url, headers=headers, json=payload, timeout=10)
        response.raise_for_status()

        data = response.json()
        qbo_id = data["Customer"]["Id"]

        customer.qbo_customer_id = qbo_id
        customer.qbo_last_sync_at = datetime.now(UTC)
        db.commit()

        CRM_QBO_CUSTOMER_SYNC.labels(org_id=str(org_id), result="created").inc()
        return qbo_id

    except Exception:
        CRM_QBO_CUSTOMER_SYNC.labels(org_id=str(org_id), result="error").inc()
        db.rollback()
        return None


def poll_invoice_status(db: Session, org_id: int, proposal_id: int) -> tuple[bool, str | None]:
    """
    Poll QuickBooks invoice status and update local proposal.

    Returns:
        (changed_to_paid, error_message)
        - changed_to_paid: True if invoice just became fully paid
        - error_message: None on success, error string on failure
    """
    # Get proposal (stored in leads table for now)
    proposal = db.query(Lead).filter(Lead.id == proposal_id, Lead.org_id == org_id).first()

    if not proposal or not hasattr(proposal, "qbo_invoice_id") or not proposal.qbo_invoice_id:
        return (False, "No QBO invoice linked")

    config = _get_qbo_config(db, org_id)
    if not config:
        return (False, "QBO not connected")

    try:
        headers = {
            "Authorization": f"Bearer {config['access_token']}",
            "Accept": "application/json",
        }

        url = f"{config['api_base']}/{config['realm_id']}/invoice/{proposal.qbo_invoice_id}"
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        invoice_data = response.json()["Invoice"]

        # Parse invoice status
        balance = float(invoice_data.get("Balance", 0.0))
        total_amt = float(invoice_data.get("TotalAmt", 0.0))

        old_status = getattr(proposal, "qbo_status", None)

        if balance == 0 and total_amt > 0:
            proposal.qbo_status = "Paid"
        elif balance > 0:
            proposal.qbo_status = "Open"
        else:
            proposal.qbo_status = "Unknown"

        proposal.qbo_balance_cents = int(round(balance * 100))
        proposal.qbo_paid_cents = int(round((total_amt - balance) * 100))
        proposal.qbo_invoice_number = invoice_data.get("DocNumber")
        proposal.qbo_last_sync_at = datetime.now(UTC)

        # Check if transitioned to Paid
        became_paid = old_status != "Paid" and proposal.qbo_status == "Paid"

        if became_paid:
            CRM_INVOICES_PAID.labels(org_id=str(org_id)).inc()
            CRM_INVOICE_PAYMENTS_CENTS.labels(org_id=str(org_id)).inc(proposal.qbo_paid_cents or 0)

            # Log activity
            activity = PortalActivity(
                org_id=org_id,
                customer_id=0,
                proposal_id=proposal_id,
                event="invoice_paid",
                meta={
                    "qbo_invoice_id": proposal.qbo_invoice_id,
                    "qbo_invoice_number": proposal.qbo_invoice_number,
                    "amount_cents": proposal.qbo_paid_cents,
                },
            )
            db.add(activity)

        db.commit()
        return (became_paid, None)

    except requests.HTTPError as e:
        CRM_INVOICE_SYNC_ERRORS.labels(org_id=str(org_id), stage="fetch").inc()
        db.rollback()
        return (False, f"HTTP error: {e}")

    except Exception as e:
        CRM_INVOICE_SYNC_ERRORS.labels(org_id=str(org_id), stage="parse").inc()
        db.rollback()
        return (False, str(e))
