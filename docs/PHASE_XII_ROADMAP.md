# Phase XII Roadmap: Production-Ready Vertical Apps

**Status:** Planning
**Prerequisites:** Phase XI Complete ✅

## Current State

Phase XI delivered:
- ✅ 3 standalone vertical apps (PeakPro, RoofWonder, PolicyPal)
- ✅ AI Agent Bridge integration
- ✅ 7 MCP tools for AI assistants
- ✅ Unified UI dashboard
- ✅ Complete documentation

All services running, tested, and integrated. Ready for production hardening.

## Phase XII Goals

Transform the three vertical apps from "demo-ready" to "ship-ready" products that can be sold independently or as part of the AetherLink suite.

## Incremental Steps

### Step 1: Lightweight Authentication ⏱️ 30 mins

**Goal:** Make apps secure enough to ship

**Implementation:**
```python
# Add to each FastAPI app
from fastapi import Header, HTTPException

APP_KEY = os.getenv("APP_KEY", "local-dev-key")

async def verify_app_key(x_app_key: str = Header(None)):
    if x_app_key != APP_KEY:
        raise HTTPException(status_code=401, detail="Invalid app key")
```

**Apply to:**
- PeakPro: `POST /crm/contacts`, `POST /crm/deals`, `POST /crm/contacts/{id}/notes`
- RoofWonder: `POST /rw/jobs`, `POST /rw/properties`, `POST /rw/estimates`
- PolicyPal: `POST /pp/policies`, `POST /pp/policies/ingest`, `POST /ai/action`

**Keep Public:**
- `GET /health` (monitoring)
- `GET /ai/snapshot` (bridge/MCP integration)
- All GET endpoints (read-only access)

**Environment Config:**
```env
# .env for each service
APP_KEY=your-secret-key-here
# Production: Generate with secrets.token_urlsafe(32)
```

**Benefits:**
- Prevents unauthorized writes
- Customers can rotate keys
- Simple enough for small deployments

---

### Step 2: Persistence for PeakPro CRM ⏱️ 1 hour

**Goal:** Make PeakPro the flagship "most producty" app

**Why PeakPro First:**
- CRM data is critical (can't lose contacts/deals)
- Most likely to be sold standalone
- Simplest data model (good proof of concept)

**Implementation:**
```python
# services/peakpro-crm/db.py
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv("DB_PATH", "./peakpro.db")

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                company TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                value REAL,
                stage TEXT,
                contact_id INTEGER,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contact_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (contact_id) REFERENCES contacts(id)
            )
        """)
        conn.commit()
```

**Migration Path:**
1. Add `db.py` with schema
2. Update endpoints to use SQL instead of in-memory lists
3. Keep API contracts identical (no breaking changes)
4. Add optional import/export for existing data

**Later:** PostgreSQL for production scale

---

### Step 3: Normalize Snapshot Shapes ⏱️ 30 mins

**Goal:** Lock in API contracts so UI/bridge never break

**Current State:**
UI expects these exact keys (already working):
- PeakPro: `contacts`, `deals`, `recommendations`
- RoofWonder: `jobs_today`, `missing_photos`, `recommendations`
- PolicyPal: `policies_recent`, `expiring`, `recommendations`

**Action Items:**
1. Document the exact JSON schema for each `/ai/snapshot`
2. Add TypeScript types to match
3. Create JSON Schema validators (optional)
4. Add integration tests that verify shape

**Example Schema Doc:**
```typescript
// PeakPro /ai/snapshot response
interface PeakProSnapshot {
  service: "peakpro-crm";
  timestamp: string; // ISO 8601
  contacts: Contact[];
  deals: {
    open: Deal[];
    stale: Deal[];
  };
  recommendations: Recommendation[];
}
```

**Benefits:**
- UI developers know exactly what to expect
- API versioning becomes easier
- Integration tests catch breaking changes

---

### Step 4: Package for "Sell Separately" ⏱️ 1 hour

**Goal:** Make each app distributable as standalone product

**For Each App, Create:**

#### `run.bat` (Windows)
```batch
@echo off
echo Starting PeakPro CRM...
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8021
```

#### `run.sh` (Linux/Mac)
```bash
#!/bin/bash
echo "Starting PeakPro CRM..."
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8021
```

#### `README.md` Template
```markdown
# PeakPro CRM

Standalone CRM for managing contacts, deals, and follow-ups.

## Quick Start (Standalone)

1. Install Python 3.11+
2. Run: `./run.sh` (or `run.bat` on Windows)
3. Open: http://localhost:8021/docs

## Integration with AetherLink (Optional)

To connect to AetherLink:
1. Set environment variable: `PEAKPRO_URL=http://localhost:8021`
2. Restart AetherLink AI Agent Bridge
3. PeakPro data now appears in AetherLink dashboard

## Configuration

Edit `.env`:
- `PORT=8021` - Change port
- `APP_KEY=secret` - Set API key for security
- `DB_PATH=./peakpro.db` - Database location
```

#### `Dockerfile` (Optional)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8021
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8021"]
```

**Marketing Angle:**
- "Run standalone for $29/mo"
- "Or integrate with AetherLink suite for $99/mo"
- Customer chooses deployment model

---

### Step 5: Enhance MCP Tool Descriptions ⏱️ 15 mins

**Goal:** Help AI assistants choose the right tool

**Current (Generic):**
```javascript
{
  name: "peakpro.get_snapshot",
  description: "Get CRM snapshot from PeakPro (contacts, deals, notes)"
}
```

**Enhanced (Context-Rich):**
```javascript
{
  name: "peakpro.get_snapshot",
  description: "Get CRM snapshot from PeakPro. Use when user asks about: contacts, follow-ups, deals, pipeline, sales opportunities, customer relationships. Returns contacts, open deals, stale deals, and actionable recommendations."
}

{
  name: "roofwonder.get_snapshot",
  description: "Get roofing jobs snapshot from RoofWonder. Use when user asks about: today's jobs, scheduled work, missing photos, job completion, property inspections. Returns jobs scheduled for today, jobs missing completion photos, and work status."
}

{
  name: "policypal.get_snapshot",
  description: "Get insurance policies snapshot from PolicyPal AI. Use when user asks about: insurance policies, coverage, expirations, renewals, policy requirements. Returns recent policies, policies expiring within 30 days, and renewal recommendations."
}
```

**Benefits:**
- Claude Code/ChatGPT choose correct tool more often
- Fewer "which tool should I use?" moments
- Better user experience with AI assistants

---

## Success Criteria

After Phase XII, each vertical app should be:
- ✅ **Secure** - API key authentication on write endpoints
- ✅ **Persistent** - Data survives restarts (at least PeakPro)
- ✅ **Documented** - README with standalone + integration instructions
- ✅ **Runnable** - One-command startup scripts
- ✅ **Discoverable** - Rich MCP descriptions for AI
- ✅ **Shippable** - Can be sold as standalone product

## Timeline Estimate

- **Minimum Viable:** Steps 1-3 (~2 hours)
- **Production Ready:** Steps 1-5 (~3 hours)
- **Fully Polished:** Add Dockerfiles, CI/CD (~5 hours)

## Future Phases (Beyond XII)

### Phase XIII: Multi-Tenancy
- Add `tenant_id` to all tables
- Tenant isolation at API level
- Separate databases per tenant (optional)

### Phase XIV: Advanced Features
- Background jobs (Celery/RQ)
- File uploads for RoofWonder photos
- Email notifications
- Webhooks for integrations

### Phase XV: Production Deployment
- Kubernetes manifests
- Monitoring (Prometheus/Grafana)
- Backup automation
- High availability setup

## Current Achievement

**Right Now, You Can Say:**
- ✅ "I have 3 mini SaaS apps"
- ✅ "They run independently"
- ✅ "They plug into my AetherLink platform"
- ✅ "My AI can call them through MCP"
- ✅ "They're integrated in a single dashboard"

**After Phase XII, You'll Add:**
- ✅ "They're production-ready and secure"
- ✅ "They persist data reliably"
- ✅ "Customers can deploy them standalone"
- ✅ "They're packaged for distribution"

---

## Decision Points

**Before Starting Phase XII:**

1. **Authentication Strategy**
   - Simple header auth (recommended for v1)
   - OAuth2/JWT (overkill for small deployments)
   - API Gateway (for enterprise)

2. **Database Choice**
   - SQLite (good for <10k records, single server)
   - PostgreSQL (recommended for production)
   - Per-tenant DBs (best isolation)

3. **Packaging Strategy**
   - Docker only
   - Native installers (electron-style)
   - SaaS-only (you host it)

4. **Pricing Model**
   - Per-app pricing
   - Bundle discount
   - Usage-based (API calls)

## Next Session

When ready to start Phase XII, begin with **Step 1 (Auth)** for all three apps. It's the quickest win and makes everything immediately more "real" as a product.

The order of steps is optimized for:
1. Security first (auth)
2. Critical data persistence (PeakPro)
3. API stability (schema normalization)
4. Distribution readiness (packaging)
5. AI discoverability (MCP descriptions)

Each step is independently valuable and can be done incrementally.
