# Phase XIV: Command Center – Operational Actions & Hardening

## Context

Phase XIII gave us:
- Persistent, restart-safe scheduler
- UI observability (dashboard + PeakProCRM)
- Full scheduler CRUD
- Centralized API helper
- Known-good launcher + backup

**We now have a stable control plane.** Phase XIV focuses on making the control plane do useful operator actions in real time, and on tightening the runtime for multi-dev / multi-env setups.

## Objectives

1. **Real-time operator action**: Allow ops to trigger work now (not only on interval)
2. **Production-ish configuration**: Stop hardcoding localhost/ports in the UI and API helper
3. **Guardrail & audit improvements**: Make sure operator actions are always logged and visible (same audit stream)
4. **Prep for storage swap**: Identify the seams so we can replace JSON with Postgres later without touching UI

---

## Scope

### 1. "Run Now" for AccuLynx

**Goal**: From PeakProCRM, operator clicks "Run now" on a tenant → backend immediately executes the AccuLynx import logic for that tenant → result shows up in audit → UI refreshes.

#### Backend Work

Add endpoint:
```http
POST /api/crm/import/acculynx/run-now
Headers:
  x-ops: 1
  x-tenant: <tenant>
Body: {}
```

**Implementation details**:
- Look up tenant in persisted schedules
- Call the same internal function the scheduler uses (reuse your "stub: real AccuLynx import not yet enabled" block)
- Write to audit: `scheduler.import.force_run`
- Update `last_run` / `last_status` in memory and re-persist JSON

#### UI Work

In `PeakProCRM.tsx` where you list tenants, add a small button next to pause/resume:
- Label: "Run now"
- On click → `api("/api/crm/import/acculynx/run-now", { method: "POST", headers: { "x-tenant": tenant } })`
- Disable while request is in flight
- On success → refresh schedules + audit

**Outcome**: Ops don't have to wait 180s to test a tenant.

---

### 2. Configurable API Base (No More Hardcoded localhost)

**Goal**: Make `ui/src/lib/api.ts` read the base URL from env (e.g. Vite env vars), so the UI can talk to a remote Command Center.

#### Work

Change `api.ts` to:
```typescript
const API_BASE =
  import.meta.env.VITE_COMMAND_CENTER_URL || "http://localhost:8000";
```

Add to `.env.local` (UI):
```bash
VITE_COMMAND_CENTER_URL=http://localhost:8000
```

**Outcome**: You can point the UI at a remote/staged Command Center without code changes.

---

### 3. Audit Enrichment

**Goal**: All operator actions (create schedule, pause, resume, delete, run-now) should be clearly labeled and include the source (ui, scheduler, command-center, ops).

#### Backend Work

In your existing `log_scheduler_audit(...)`, add optional fields:
- `actor` (e.g. "ui" or "scheduler")
- `action_id` (random UUID/string)

From endpoints that are clearly UI-triggered, call:
```python
log_scheduler_audit(
    tenant=tenant,
    operation="scheduler.schedule.created",
    source="ui",
    metadata={"interval_sec": interval_sec},
)
```

Cap remains at 100 entries ✅

**Outcome**: Dashboard's `LastAuditBadge` becomes even more useful — you can tell who triggered it.

---

### 4. JSON-to-DB Abstraction Note (Prep Only)

**Goal**: Mark the exact functions that must be replaced when moving to Postgres.

#### Work

At the top of `main.py` where you defined `save_json_safe`, `load_json_self_heal`, add comments like:

```python
# PERSISTENCE LAYER V1 (JSON)
# To migrate to Postgres, replace:
# - load_acculynx_schedules()
# - save_acculynx_schedules()
# - load_acculynx_audit()
# - save_acculynx_audit()
```

No code change needed right now — just document it.

**Outcome**: Future storage work doesn't have to diff 2,000 lines.

---

## Acceptance Checklist

- [ ] `POST /api/crm/import/acculynx/run-now` executes immediately for an existing tenant
- [ ] run-now creates an audit row with `operation: "scheduler.import.force_run"` and `source: "ui"`
- [ ] PeakProCRM shows a "Run now" button per tenant and refreshes on success
- [ ] `ui/src/lib/api.ts` uses `VITE_COMMAND_CENTER_URL`
- [ ] Dashboard's `LastAuditBadge` shows "force_run" events too
- [ ] `main.py` has persistence layer clearly marked for future DB swap

---

## Nice-to-haves (Can Punt)

- Optimistic UI for run-now (show "running…" before response)
- Toast/snackbar on success/failure
- Filter in the audit panel (show only a specific tenant)

---

## Implementation Order

1. **Start with #1 (Run Now)** - Gives ops the most obvious "I clicked it and it ran" feeling
2. **Then #3 (Audit Enrichment)** - Makes run-now visible in the dashboard
3. **Then #2 (Configurable API)** - Enables remote/staged testing
4. **Finally #4 (DB Prep)** - Documentation for future work

---

## Related Files

- Backend: `services/command-center/main.py`
- UI Vertical: `ui/src/verticals/PeakProCRM.tsx`
- API Helper: `ui/src/lib/api.ts`
- Dashboard: `ui/src/DashboardHome.tsx`
- Audit Badge: `ui/src/components/LastAuditBadge.tsx`

---

**Status**: Roadmap complete, ready to implement

**Previous Phase**: [Phase XIII: Persistent State](PHASE_XIII_COMPLETE_SUMMARY.md)

**Next Phase**: Phase XV (TBD - Real AccuLynx Integration or PostgreSQL Migration)
