# Phase XIII: Field Operations Platform - "The AccuLynx Killer"

**Status:** Planning
**Prerequisites:** Phase XI Complete ✅
**Goal:** Build field operations capabilities that beat AccuLynx across all AetherLink CRMs

## Executive Summary

Transform AetherLink into a comprehensive field operations platform by adding shared services that all vertical apps (PeakPro, RoofWonder, PolicyPal, ApexFlow) can leverage. Every feature built once, available everywhere.

## Architecture: Shared Services Layer

```
┌─────────────────────────────────────────────────────────────┐
│          Vertical Apps (Use Shared Services)                │
│  PeakPro | RoofWonder | PolicyPal | ApexFlow CRM            │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│              Shared Services Layer (New)                    │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │  Media   │ │Scheduling│ │  Auth    │ │  Integra │      │
│  │ Service  │ │ Service  │ │ /2FA     │ │   tions  │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │Estimator │ │Custom    │ │  Measure │ │Accounting│      │
│  │  Engine  │ │  Fields  │ │   ments  │ │Connector │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└─────────────────────────────────────────────────────────────┘
```

## Feature Comparison: AccuLynx vs AetherLink

| Feature | AccuLynx | AetherLink (Our Version) | Our Advantage |
|---------|----------|--------------------------|---------------|
| **Photo Management** | Slow, crashes | Client compression + chunked upload + offline queue | 5-8x faster, works offline |
| **CallRail Integration** | Basic sync | Auto-lead + AI intake + recording transcription | Smarter lead routing |
| **2FA** | Optional | Tenant-enforced + device trust | Better security + UX |
| **Mobile Estimation** | Field app only | Web + mobile + AI-assisted | Works everywhere |
| **Custom Fields** | Beta, basic | Dynamic schema + validation + stage gates | More flexible |
| **3D Roof Models** | GeoSpan only | Provider-agnostic + auto-map to estimate | Works with any provider |
| **Calendar** | Single app | Shared across all CRMs + crew load view | Better resource planning |
| **Trade Tracking** | Basic reports | First-class field + profitability + capacity alerts | Actionable insights |
| **DataMart** | Separate add-on | Built-in events → warehouse | Included free |
| **Sage Integration** | Sage only | Multi-provider (Sage/QBO/Xero) | More flexible |
| **Multi-CRM** | ❌ | ✅ All features work in all apps | Massive win |

## Implementation Plan

### Service 1: Media Service (Photo/Video Management)

**Problem Solved:** AccuLynx photos are slow and crash on poor connections

**Our Solution:**
- Client-side compression (5-8x smaller)
- Chunked + resumable uploads
- Offline queue (PWA)
- CDN-ready variants (thumb/medium/full)

**Files:**
```
services/media-service/
├── main.py              # FastAPI app
├── Dockerfile
├── requirements.txt     # pillow, boto3, aiofiles
└── .env.example
    MEDIA_BUCKET=aetherlink-media
    S3_ENDPOINT=https://r2.cloudflare.com
    CDN_BASE=https://cdn.aetherlink.app
```

**API Endpoints:**
- `POST /upload-chunk` - Upload file chunk
- `POST /finalize-upload` - Stitch chunks, create variants
- `GET /variants/{media_id}?size=thumb|medium|full` - Get variant URL
- `POST /ingest-offline` - Sync offline queue

**Integration:**
```python
# In RoofWonder, PeakPro, PolicyPal, etc.
class Job(BaseModel):
    media_ids: List[str]  # Just store IDs, not URLs

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = await db.get(job_id)
    # Fetch media URLs from media service
    async with httpx.AsyncClient() as client:
        media_urls = []
        for mid in job.media_ids:
            r = await client.get(f"{MEDIA_API}/variants/{mid}")
            media_urls.append(r.json()["url"])
    return {**job.dict(), "media_urls": media_urls}
```

**Frontend Component:**
```tsx
// src/components/PhotoUploader.tsx
// - browser-image-compression for client-side shrink
// - Chunked upload with progress bar
// - IndexedDB queue for offline
// - Auto-retry on reconnect
```

---

### Service 2: CallRail Integration (Lead Capture)

**Problem Solved:** Manual lead entry from phone calls

**Our Solution:**
- Webhook receiver for CallRail
- Auto-create lead in all CRMs
- Attach call recording + transcript
- AI intake bot proposes job scope

**Files:**
```
services/integrations/callrail/
├── main.py
├── webhook_handler.py
└── ai_intake.py  # Summarizes call → proposed scope
```

**API Endpoints:**
- `POST /integrations/callrail/webhook` - Receive CallRail event
- `GET /integrations/callrail/recordings/{call_id}` - Get recording URL

**Event Flow:**
```
CallRail → Webhook → AetherLink Event Bus → All CRMs
                           ↓
                    AI Intake Bot → Proposed Scope
```

**Integration:**
```python
# pods/crm/routers/integrations_callrail.py
@router.post("/webhook")
async def callrail_webhook(payload: dict):
    lead = {
        "source": "callrail",
        "caller_number": payload["customer_phone_number"],
        "tracking_number": payload["tracking_phone_number"],
        "call_duration": payload["duration"],
        "recording_url": payload.get("recording"),
        "time": datetime.utcnow().isoformat(),
    }
    # Emit to event bus
    await emit_event("lead.created", lead)

    # Trigger AI intake
    if lead["call_duration"] > 60:  # Only for real conversations
        await ai_intake.analyze_call(lead)

    return {"status": "ok"}
```

---

### Service 3: Two-Factor Authentication (2FA)

**Problem Solved:** Security for field workers + office staff

**Our Solution:**
- TOTP (Google Authenticator, Authy)
- Tenant-enforced policy
- Device trust for 30 days (field workers)
- IP allowlisting (office)

**Files:**
```
services/auth/
├── routers/2fa.py
└── device_trust.py
```

**API Endpoints:**
- `POST /2fa/setup` - Generate TOTP secret + QR code
- `POST /2fa/verify` - Verify TOTP code
- `POST /2fa/trust-device` - Trust device for 30 days
- `GET /2fa/trusted-devices` - List trusted devices

**Integration:**
```python
# All CRMs use same auth service
from auth_service import require_2fa

@router.get("/jobs", dependencies=[Depends(require_2fa)])
async def list_jobs():
    ...
```

---

### Service 4: Estimator Engine

**Problem Solved:** Repetitive estimate building

**Our Solution:**
- Template library (by trade, by region)
- AI-assisted from photos
- Multi-trade support
- Markup/discount rules
- Signature capture

**Files:**
```
services/estimator/
├── main.py
├── templates.py      # Pre-built estimate templates
├── ai_suggest.py     # Analyze photos → line items
└── signature.py      # Capture signature
```

**API Endpoints:**
- `POST /estimates/draft` - Create draft estimate
- `GET /estimates/templates?trade=roofing` - List templates
- `POST /estimates/ai-suggest` - AI proposes line items from photos
- `POST /estimates/{id}/signature` - Add customer signature

**Data Model:**
```python
class EstimateLine(BaseModel):
    name: str
    qty: float
    unit: str  # "sq", "lf", "ea"
    unit_price: float
    trade: str  # "roofing", "siding", "gutters"
    material_cost: float = 0
    labor_hours: float = 0

class Estimate(BaseModel):
    job_id: str
    lines: List[EstimateLine]
    discount_pct: float = 0
    profit_margin_pct: float = 15
    tax_pct: float = 0
    signature_media_id: Optional[str] = None
    status: str = "draft"  # draft, sent, approved, declined
```

---

### Service 5: Custom Fields Engine

**Problem Solved:** Every customer wants different fields

**Our Solution:**
- Tenant-level field definitions
- Entity-agnostic (job, contact, lead, estimate)
- Type validation (text, number, date, picklist)
- Required for stage transitions

**Files:**
```
services/custom-fields/
├── main.py
├── definitions.py    # Manage field definitions
└── values.py         # Store field values
```

**Database Schema:**
```sql
CREATE TABLE custom_field_definitions (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    entity_type VARCHAR(50),  -- 'job', 'contact', 'lead'
    key VARCHAR(100),
    label VARCHAR(200),
    type VARCHAR(50),  -- 'text', 'number', 'date', 'picklist'
    options JSONB,  -- For picklists
    required BOOLEAN DEFAULT false,
    required_for_stage VARCHAR(50)  -- 'sold', 'production', etc.
);

CREATE TABLE custom_field_values (
    entity_id UUID,
    tenant_id UUID,
    key VARCHAR(100),
    value TEXT,
    PRIMARY KEY (entity_id, key)
);
```

**API Endpoints:**
- `POST /custom-fields/definitions` - Create field definition
- `GET /custom-fields/definitions?entity_type=job` - List definitions
- `PUT /custom-fields/values/{entity_id}` - Set field values
- `GET /custom-fields/values/{entity_id}` - Get field values

---

### Service 6: Measurements Integration

**Problem Solved:** Manual entry of roof measurements

**Our Solution:**
- Provider-agnostic (EagleView, GeoSpan, Hover, etc.)
- Store measurement report + 3D model link
- Auto-map to estimate line items
- Embed 3D viewer in CRMs

**Files:**
```
services/measurements/
├── main.py
├── providers/
│   ├── eagleview.py
│   ├── geospan.py
│   └── hover.py
└── mapper.py  # Map measurements → estimate
```

**API Endpoints:**
- `POST /measurements/ingest` - Import measurement report
- `GET /measurements/{job_id}` - Get measurement data
- `POST /measurements/map-to-estimate` - Auto-create estimate lines

**Integration:**
```python
# RoofWonder job detail
@router.get("/jobs/{job_id}/measurement")
async def get_measurement(job_id: str):
    meas = await measurements_api.get(job_id)
    return {
        "provider": meas["provider"],
        "report_url": meas["report_url"],
        "viewer_embed": meas["viewer_embed"],
        "total_squares": meas["data"]["total_squares"],
        "slopes": meas["data"]["slopes"],
        "ridges_lf": meas["data"]["ridges_lf"],
    }
```

---

### Service 7: Scheduling Service

**Problem Solved:** Crew scheduling across teams

**Our Solution:**
- Multi-resource scheduling (users, crews, trucks)
- Sync to Google/Outlook calendars
- Crew load view (capacity planning)
- Auto-schedule from lead intake

**Files:**
```
services/scheduling/
├── main.py
├── resources.py      # Users, crews, equipment
├── appointments.py   # Scheduling logic
└── sync_adapters/
    ├── google.py
    └── microsoft.py
```

**Data Model:**
```python
class Resource(BaseModel):
    id: str
    type: str  # "user", "crew", "truck"
    name: str
    capacity_per_day: float = 1.0  # crews might handle 2 jobs

class Appointment(BaseModel):
    id: str
    job_id: str
    resource_ids: List[str]
    start: datetime
    end: datetime
    type: str  # "inspection", "installation", "warranty"
    status: str  # "scheduled", "in_progress", "completed", "cancelled"
```

**API Endpoints:**
- `POST /appointments` - Create appointment
- `GET /appointments?start=...&end=...` - List appointments
- `GET /resources/{id}/availability` - Check availability
- `POST /appointments/auto-schedule` - Suggest next available slot

---

### Service 8: Trade-Based Tracking

**Problem Solved:** Multi-trade contractors need profitability by trade

**Our Solution:**
- Trade as first-class field on estimates, jobs, line items
- Profitability reports by trade
- Capacity tracking by trade
- Backlog alerts

**Integration:**
```python
# Add to all estimate line items
class EstimateLine(BaseModel):
    ...
    trade: str  # Required field

# Reporting endpoint
@router.get("/reports/trades")
async def trade_report(tenant_id: str):
    return {
        "roofing": {
            "jobs": 45,
            "revenue": 1250000,
            "cost": 875000,
            "profit_margin": 30,
            "backlog_days": 14,
        },
        "siding": {
            "jobs": 12,
            "revenue": 340000,
            "cost": 255000,
            "profit_margin": 25,
            "backlog_days": 7,
        },
    }
```

---

### Service 9: Analytics / DataMart

**Problem Solved:** Reporting locked behind add-on

**Our Solution:**
- AetherLink events → data warehouse
- Pre-built views per tenant
- AI Report Builder (natural language → SQL)

**Files:**
```
services/analytics/
├── main.py
├── warehouse.py      # ClickHouse/Postgres connector
├── views.py          # Pre-built report views
└── ai_query.py       # Natural language → SQL
```

**Database Views:**
```sql
-- Per-tenant materialized views
CREATE MATERIALIZED VIEW tenant_123_vw_jobs AS
SELECT
    j.id, j.status, j.value, j.created_at, j.closed_at,
    c.name as customer_name,
    e.total as estimate_total,
    COUNT(m.id) as photo_count
FROM jobs j
LEFT JOIN contacts c ON j.contact_id = c.id
LEFT JOIN estimates e ON j.id = e.job_id
LEFT JOIN job_media jm ON j.id = jm.job_id
LEFT JOIN media m ON jm.media_id = m.id
WHERE j.tenant_id = 'tenant_123'
GROUP BY j.id, c.name, e.total;
```

**API Endpoints:**
- `GET /analytics/dataset?view=jobs` - Get dataset
- `POST /analytics/query` - AI natural language query
- `GET /analytics/reports/predefined` - List pre-built reports

---

### Service 10: Accounting Connector

**Problem Solved:** Manual invoice entry in Sage/QBO

**Our Solution:**
- Multi-provider (Sage, QuickBooks Online, Xero)
- Auto-sync on job close-out
- Reconciliation (flags rejected invoices)

**Files:**
```
services/accounting/
├── main.py
├── connectors/
│   ├── sage.py
│   ├── quickbooks.py
│   └── xero.py
└── reconciler.py
```

**API Endpoints:**
- `POST /accounting/sage/config` - Configure Sage connection
- `POST /accounting/sync-invoice` - Push invoice to accounting
- `GET /accounting/reconcile` - Check sync status

**Integration:**
```python
# Trigger on job close
@router.post("/jobs/{job_id}/close")
async def close_job(job_id: str):
    job = await db.get(job_id)

    # Create invoice in accounting system
    invoice = {
        "customer": job.contact_id,
        "line_items": job.estimate.lines,
        "total": job.estimate.total,
        "job_number": job.number,
    }

    result = await accounting_api.sync_invoice(invoice)

    if not result["success"]:
        # Flag for manual review
        await create_alert("Invoice sync failed", job_id)

    return {"status": "closed"}
```

---

## Docker Compose Integration

```yaml
# deploy/docker-compose.dev.yml

services:
  # New shared services
  media-service:
    build: ./services/media-service
    environment:
      - MEDIA_BUCKET=aetherlink-media
      - S3_ENDPOINT=${S3_ENDPOINT}
      - CDN_BASE=${CDN_BASE}
    ports:
      - "9109:8000"
    depends_on:
      - minio

  scheduling-service:
    build: ./services/scheduling
    environment:
      - DATABASE_URL=${DATABASE_URL}
    ports:
      - "9110:8000"

  estimator-service:
    build: ./services/estimator
    ports:
      - "9111:8000"

  custom-fields-service:
    build: ./services/custom-fields
    ports:
      - "9112:8000"

  measurements-service:
    build: ./services/measurements
    ports:
      - "9113:8000"

  analytics-service:
    build: ./services/analytics
    environment:
      - CLICKHOUSE_URL=${CLICKHOUSE_URL}
    ports:
      - "9114:8000"

  accounting-service:
    build: ./services/accounting
    ports:
      - "9115:8000"

  # Existing services still work
  peakpro-crm:
    environment:
      - MEDIA_API=http://media-service:8000
      - SCHEDULING_API=http://scheduling-service:8000
      - ESTIMATOR_API=http://estimator-service:8000
    depends_on:
      - media-service
      - scheduling-service
      - estimator-service

  roofwonder:
    environment:
      - MEDIA_API=http://media-service:8000
      - MEASUREMENTS_API=http://measurements-service:8000
    depends_on:
      - media-service
      - measurements-service

  policypal-ai:
    environment:
      - MEDIA_API=http://media-service:8000
      - CUSTOM_FIELDS_API=http://custom-fields-service:8000
    depends_on:
      - media-service
      - custom-fields-service
```

---

## UI Integration Pattern

Each CRM gets shared React components:

```tsx
// services/ui/src/shared-components/
├── PhotoUploader.tsx       # From media-service
├── EstimateBuilder.tsx     # From estimator-service
├── CalendarView.tsx        # From scheduling-service
├── CustomFieldsEditor.tsx  # From custom-fields-service
└── MeasurementViewer.tsx   # From measurements-service
```

Then in each CRM:

```tsx
// RoofWonder job detail page
import { PhotoUploader, MeasurementViewer, EstimateBuilder } from '@shared/components';

export function JobDetailPage({ jobId }) {
  return (
    <div>
      <PhotoUploader
        jobId={jobId}
        onUploaded={(media_id) => addPhotoToJob(jobId, media_id)}
      />

      <MeasurementViewer jobId={jobId} />

      <EstimateBuilder
        jobId={jobId}
        onGenerate={() => generateFromMeasurement(jobId)}
      />
    </div>
  );
}
```

---

## Extra Features (Beat AccuLynx)

### 1. Unified Media Timeline
Show everything on one job page:
- Photos (with timestamps)
- 3D measurement report
- Estimate PDFs
- Call recordings
- Text transcripts
- Signature

### 2. AI Follow-Up Sequences
When appointment is missed:
- Auto-text homeowner
- Update job status → "follow-up needed"
- Notify sales rep
- Suggest 3 new time slots

### 3. Photo Rules Engine
Define required photos per job type:
```python
{
  "roof_replacement": {
    "required_photos": [
      "front_elevation",
      "back_elevation",
      "left_side",
      "right_side",
      "chimney_detail",
      "valley_detail",
      "edge_detail",
      "decking_condition"
    ],
    "min_count": 8,
    "stage_gate": "production_ready"  # Can't advance without photos
  }
}
```

### 4. Field-Friendly Batching
Snap 30 photos in 2 minutes:
- Auto-tag with job ID
- Auto-tag with elevation (AI detects "front", "side", etc.)
- Auto-tag with trade
- Queue for upload when back in wifi

### 5. Multi-Brand Tenanting
Run multiple CRM brands from one codebase:
- `roofwonder.com` → RoofWonder branding
- `peakprocrm.com` → PeakPro branding
- `yourcompany.com` → White-label
- All share same services underneath

---

## Implementation Timeline

### Phase XIII-A: Media Service (Week 1)
- Build media-service
- Add PhotoUploader component
- Test chunked upload + offline queue
- Deploy to all CRMs

**Deliverable:** Photos 5-8x faster, work offline

### Phase XIII-B: CallRail + 2FA (Week 2)
- CallRail webhook receiver
- AI intake bot
- TOTP 2FA implementation

**Deliverable:** Automatic lead capture, secure auth

### Phase XIII-C: Estimator Engine (Week 3)
- Template library
- AI-assisted estimates
- Signature capture

**Deliverable:** 10x faster estimate building

### Phase XIII-D: Scheduling + Custom Fields (Week 4)
- Multi-resource scheduler
- Custom field engine
- Calendar sync

**Deliverable:** Better crew planning, flexible data

### Phase XIII-E: Measurements + Analytics (Week 5)
- Measurement provider integrations
- Data warehouse pipeline
- Trade-based reports

**Deliverable:** 3D models → estimates, actionable insights

### Phase XIII-F: Accounting Integration (Week 6)
- Sage/QBO/Xero connectors
- Auto-sync on close
- Reconciliation

**Deliverable:** No more manual invoice entry

---

## Success Metrics

After Phase XIII, we can say:

✅ **Photos:** 5-8x faster than AccuLynx, work offline
✅ **Leads:** Auto-capture from calls + AI intake
✅ **Security:** Tenant-enforced 2FA + device trust
✅ **Estimates:** AI-assisted, 10x faster
✅ **Flexibility:** Custom fields per tenant
✅ **3D Integration:** Works with any provider
✅ **Scheduling:** Multi-resource, crew load view
✅ **Analytics:** Built-in, not an add-on
✅ **Accounting:** Multi-provider, auto-sync
✅ **Multi-CRM:** All features in all apps

**Marketing Message:**
"Everything AccuLynx does, but faster, offline-capable, and available across our entire CRM suite for one price."

---

## Cost Comparison

**AccuLynx:**
- Base: $165/user/month
- Field App: +$25/user/month
- DataMart: +$49/month
- **Total:** ~$200+/user/month

**AetherLink:**
- All features included
- No per-module pricing
- **Suggested:** $99/user/month or $999/company/month unlimited users

**Win:** Same features for 50% of the price, plus multi-CRM access

---

## Next Steps

1. **Start with Media Service** (biggest immediate win)
2. **Add CallRail + 2FA** (competitive differentiator)
3. **Roll out Estimator** (field team productivity)
4. **Deploy rest incrementally** (6-week sprint)

Each service is independently valuable and can be deployed without the others.

---

## Decision Points

Before starting Phase XIII:

1. **Storage Provider:** Cloudflare R2 (recommended) vs MinIO (self-hosted) vs AWS S3
2. **Calendar Sync:** Google Calendar (easier) vs Microsoft 365 (enterprise) vs both
3. **Accounting Priority:** Sage first (their focus) vs QBO (more common) vs both
4. **AI Model:** GPT-4 (best quality) vs Claude (faster) vs local Llama (private)

Ready to make this real?
