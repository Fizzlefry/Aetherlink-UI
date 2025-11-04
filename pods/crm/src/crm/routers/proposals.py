"""
Proposal generation router - creates PDFs and stores in MinIO.
"""

import os
from datetime import datetime, timedelta
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from jinja2 import Template
from minio import Minio
from prometheus_client import Counter
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from ..auth_routes import get_current_user
from ..db import get_db
from ..models_v2 import Attachment, Lead

router = APIRouter(prefix="/proposals", tags=["proposals"])

PROPOSALS_CREATED = Counter(
    "crm_proposals_generated_total", "Total proposals generated", ["org_id"]
)

# Proposal template
TEMPLATE = Template(
    """
PROPOSAL

Date: {{ now }}

CLIENT INFORMATION
{{ lead.name }}
{{ lead.email }}
{{ lead.phone }}
Company: {{ lead.company or 'N/A' }}

PROJECT SCOPE
{{ scope or 'Standard roofing proposal with tear-off, underlayment, ridge cap, pipe boots, and debris disposal.' }}

INVESTMENT
${{ "{:,.2f}".format(price or 0) }}

TERMS
Payment: Net 30 days
Warranty: Per contract specifications
Valid for: 30 days from proposal date

Thank you for considering PeakPro Roofing for your project!
""".strip()
)


def s3_client() -> Minio:
    """Get MinIO client instance."""
    return Minio(
        os.getenv("MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("MINIO_ACCESS_KEY", "admin"),
        secret_key=os.getenv("MINIO_SECRET_KEY", "admin123"),
        secure=False,
    )


def render_pdf(text: str) -> bytes:
    """Render text to PDF using ReportLab."""
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=LETTER)
    width, height = LETTER
    y = height - 72  # Start 1 inch from top

    for line in text.splitlines():
        if not line.strip():
            y -= 14  # Empty line
            continue

        # Handle long lines
        line_text = line[:100]  # Truncate very long lines
        c.drawString(72, y, line_text)
        y -= 14

        # New page if needed
        if y < 72:
            c.showPage()
            y = height - 72

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


@router.post("/{lead_id}/generate")
def generate_proposal(
    lead_id: int,
    price: float,
    scope: str = "",
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Generate a proposal PDF for a lead and store in MinIO."""
    # Get lead (with org isolation)
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.org_id == user.org_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    # Render proposal text
    text = TEMPLATE.render(
        now=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"), lead=lead, scope=scope, price=price
    )

    # Generate PDF
    pdf_bytes = render_pdf(text)

    # Upload to MinIO
    client = s3_client()
    bucket = f"org-{user.org_id}"

    # Create bucket if it doesn't exist
    try:
        if not client.bucket_exists(bucket):
            client.make_bucket(bucket)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MinIO error: {str(e)}")

    # Generate unique key
    key = f"proposals/lead-{lead.id}-{int(datetime.utcnow().timestamp())}.pdf"

    # Upload PDF
    try:
        client.put_object(
            bucket, key, BytesIO(pdf_bytes), length=len(pdf_bytes), content_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Create attachment record
    att = Attachment(
        org_id=user.org_id,
        job_id=None,  # Could link to job later
        filename=f"proposal-lead-{lead.id}.pdf",
        key=key,
        content_type="application/pdf",
        size_bytes=len(pdf_bytes),
    )
    db.add(att)
    db.commit()

    # Increment metric
    PROPOSALS_CREATED.labels(org_id=str(user.org_id)).inc()

    # Generate signed URL (valid for 15 minutes)
    try:
        url = client.get_presigned_url("GET", bucket, key, expires=timedelta(minutes=15))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"URL generation failed: {str(e)}")

    return {
        "lead_id": lead.id,
        "proposal_url": url,
        "attachment_id": att.id,
        "expires_in_minutes": 15,
    }
