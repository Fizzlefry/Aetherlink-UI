"""
Portal helpers for email and MinIO URL signing.
"""

import datetime as dt
import os
import smtplib
from email.mime.text import MIMEText

from minio import Minio

# SMTP Configuration
SMTP_HOST = os.getenv("SMTP_HOST", "mailhog")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

# MinIO Configuration
INTERNAL_ENDPOINT = os.getenv("MINIO_INTERNAL_ENDPOINT", "minio:9000")
PUBLIC_ENDPOINT = os.getenv("MINIO_PUBLIC_ENDPOINT", "localhost:9000")
ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "admin")
SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "admin123")
BUCKET = os.getenv("MINIO_BUCKET", "crm-proposals")


def signed_proposal_url(object_name: str, expires_seconds: int = 3600) -> str:
    """
    Generate a presigned URL for a proposal PDF.
    Uses internal endpoint to check bucket, public endpoint to sign URL.
    """
    # Ensure bucket exists using internal network path
    internal = Minio(INTERNAL_ENDPOINT, access_key=ACCESS_KEY, secret_key=SECRET_KEY, secure=False)
    if not internal.bucket_exists(BUCKET):
        internal.make_bucket(BUCKET)

    # Sign the URL against the PUBLIC endpoint so browser links work
    public = Minio(PUBLIC_ENDPOINT, access_key=ACCESS_KEY, secret_key=SECRET_KEY, secure=False)
    return public.presigned_get_object(
        BUCKET, object_name, expires=dt.timedelta(seconds=expires_seconds)
    )


def send_proposal_email(to_email: str, proposal_url: str, org_name: str = "PeakPro CRM"):
    """
    Send a proposal email with a view/approve link.
    """
    subject = f"{org_name} Proposal – Review & Approve"
    html = f"""
    <div style="font-family:sans-serif">
      <h2>{org_name} Proposal</h2>
      <p>Hi,</p>
      <p>Your proposal is ready. Review and approve using the link below:</p>
      <p><a href="{proposal_url}" style="background:#007bff;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;display:inline-block" target="_blank">View Proposal</a></p>
      <p>This link is valid for 24 hours.</p>
      <p>Thank you!</p>
      <p style="color:#666;font-size:12px;margin-top:30px">PeakPro CRM · Professional Roofing Services</p>
    </div>
    """
    msg = MIMEText(html, "html")
    msg["Subject"] = subject
    msg["From"] = "noreply@peakpro.io"
    msg["To"] = to_email

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(msg["From"], [to_email], msg.as_string())
