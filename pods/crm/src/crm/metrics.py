"""
Prometheus metrics for CRM portal and email automation.
"""
from prometheus_client import Counter

# Email automation metrics
CRM_EMAILS_SENT = Counter(
    "crm_emails_sent_total",
    "Emails sent by type",
    ["type"]
)

# Portal activity metrics
CRM_PORTAL_VIEWS = Counter(
    "crm_portal_views_total",
    "Portal views",
    ["event"]  # event=view|download
)

CRM_PORTAL_APPROVALS = Counter(
    "crm_portal_approvals_total",
    "Approvals"
)

# Sprint 5: QuickBooks Customer & Invoice Sync
CRM_QBO_CUSTOMER_SYNC = Counter(
    "crm_qbo_customer_sync_total",
    "CRM↔QBO customer sync operations",
    ["org_id", "result"]  # result: created|updated|skipped|error
)

CRM_INVOICES_PAID = Counter(
    "crm_invoices_paid_total",
    "Invoices transitioned to Paid via polling",
    ["org_id"]
)

CRM_INVOICE_PAYMENTS_CENTS = Counter(
    "crm_invoice_payments_cents_total",
    "Total cents of invoice payments recorded via QBO polling",
    ["org_id"]
)

CRM_INVOICE_SYNC_ERRORS = Counter(
    "crm_invoice_sync_errors_total",
    "Errors during invoice status polling",
    ["org_id", "stage"]  # stage: fetch|parse|update
)
