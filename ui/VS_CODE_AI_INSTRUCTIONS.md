# AetherLink CRM Development Instructions

## For VS Code AI / GitHub Copilot

When building or modifying ANY CRM/front-end component (jobs, leads, permits, roofing verticals, policy verticals, or operator dashboards):

### Data Source
- **ALWAYS fetch from `/ui/bundle`** (served by Command Center on port 8011)
- This endpoint returns consolidated data:
  ```
  {
    status: {...},     // from /status/summary
    federation: {...}, // from /federation/health
    opt: {...},        // from /federation/opt/global
    learn: {...},      // from /federation/learn/explain
    policies: {...},   // from /federation/policy/explain
    alerts: [...]      // from /alerts/operator-view?limit=50
  }
  ```
- **Do NOT call multiple endpoints** - derive UI state from this single payload
- If data is missing, extend the bundle shape in Command Center first

### UI Framework
- **Use the shared CRM library** (`src/crm-lib/`)
- **Implement three main views**:
  - Pipeline View: Kanban/table layout for deals/jobs
  - Record View: Two-column layout (details + messages/docs)
  - Automations View: Rule-builder (When → Then)
- **Wrap in CrmShell** for consistent layout:
  - Top app bar
  - Left collapsible nav (Overview | Communications | Documents | Automations)
  - Main content area
  - Right rail with AetherLink status

### Styling
- **Tailwind CSS** for modern, clean UI
- Rounded cards, subtle shadows, light background
- Responsive design
- Consistent with Monday.com aesthetics

### AetherLink Integration
- **Show operator/infra awareness** in right rail:
  - Service status (RoofWonder: UP ✅, PolicyPal: UP ✅)
  - Active alerts
  - Federation health
  - Learning insights
- **Enable actions**:
  - POST `/alerts/ack` for alert acknowledgment
  - POST `/federation/policy/apply` for policy application

### Vertical-Specific Implementation
- Create new CRM app in `src/verticals/`
- Import shared components from `../crm-lib`
- Implement vertical-specific data models and mock data
- Use CrmShell as root component
- Fetch from `/ui/bundle` for real-time status

### Development Workflow
1. **Start backend**: `python main.py` in `services/command-center/`
2. **Start UI**: `npm run dev` (default) or `npm run dev:peakpro` etc.
3. **Build**: `npm run build`
4. **Test**: Ensure `/ui/bundle` endpoint works

### Key Principles
- **Single source of truth**: `/ui/bundle` for all dashboard data
- **Consistent UX**: Same layout and behavior across all CRMs
- **Real-time awareness**: Always show AetherLink federation status
- **Action-oriented**: Enable key workflows through backend APIs
- **Extensible**: Easy to add new verticals using shared components

### Tenant / Company
- **Default tenant for this project**: `the-expert-co`
- When calling `/api/crm/:vertical/bundle`, always send:
  - `x-tenant: the-expert-co`
- **Do NOT use** `expert-code` (that was an earlier placeholder)
- Reserved / future brand: `the-expert-code` (if needed for spin-off/agency)

### Example Usage
```tsx
// Development (direct backend)
const bundleUrl = 'http://localhost:8011/ui/bundle';

// Production (via Nginx proxy)
const bundleUrl = '/api/ui/bundle';

function MyVerticalCRM() {
  const [bundle, setBundle] = useState(null);

  useEffect(() => {
    fetch(bundleUrl)
      .then(res => res.json())
      .then(setBundle);
  }, []);

  return (
    <CrmShell title="My Vertical CRM" bundle={bundle}>
      <PipelineView deals={myDeals} onDealClick={handleClick} />
    </CrmShell>
  );
}
```

This ensures every CRM screen feels consistent, pulls from the same data source, and presents the same operator+business context without duplicating fetch logic.

---

# AetherLink CRM UI – Runtime Instructions for AI in VS Code

## 1. Always fetch from the backend bundle
All CRM/react screens in this repo MUST get their data from:
GET http://localhost:8011/ui/bundle

Or in production (via Nginx proxy):
GET /api/ui/bundle

This endpoint already returns:
- status  → /status/summary
- federation → /federation/health
- opt → /federation/opt/global
- learn → /federation/learn/explain
- policies → /federation/policy/explain
- alerts → /alerts/operator-view?limit=50

Do NOT create extra fetches unless the bundle is missing a field. If data is missing, extend the bundle in `services/command-center/main.py`.

## 2. Use the shared CRM shell
When generating new UI, wrap it in the shared shell from `src/crm-lib/`:
- `CrmShell.tsx` – top-level layout
- `PipelineView.tsx` – list/kanban/pipeline page
- `RecordView.tsx` – single job/deal view (tabs)
- `AutomationsView.tsx` – rule builder like Monday.com

Prefer composition over new layouts.

## 3. Styling rules
- Use Tailwind classes (already installed and configured).
- Cards: `bg-white rounded-xl shadow-sm p-4`
- Page background: `bg-slate-50 min-h-screen`
- Tabs: bottom-border pattern (`border-b-2 border-slate-900`) for active tab.
- Keep it cleaner than AccuLynx, closer to Monday.com.

## 4. Show ops context in every CRM screen
Every CRM view must show AetherLink ops awareness in a right-hand panel:
- service up/down from `bundle.status.services`
- federation health from `bundle.federation.status`
- alerts count from `bundle.alerts.length`

This keeps ops + business in the same UI.

## 5. Actions to implement
- Acknowledge alert:
  POST /alerts/ack { "fingerprint": "<id>" }
- Apply policy:
  POST /federation/policy/apply { "key": "...", "value": ... }
Use fetch with JSON and show success in UI.

## 6. Vertical CRM mapping
- PeakProCRM → use shared shell, load bundle, show pipeline for sales
- PolicyPalCRM → use shared shell, show claims/documents tab
- RoofWonder / construction jobs → show Photos/Permits tab in RecordView

All verticals should reuse the same shell; only inner tab content changes.

## 7. Vite/React setup
- Entry: `src/App.tsx`
- Import your components from `src/crm-lib/`
- Keep `index.css` with Tailwind base:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

## 8. Routing Structure
- `/` → Dashboard home (shows all CRM verticals)
- `/peakpro` → PeakPro CRM (roofing services)
- `/policypal` → PolicyPal CRM (insurance claims)
- `/roofwonder`, `/clientellme`, `/apexflow` → Coming soon placeholders

Each vertical route renders its own CRM component with shared shell.

## 9. Don't overwrite these files

* `src/crm-lib/*`
* `VS_CODE_AI_INSTRUCTIONS.md`
* `services/command-center` bundle route
* `src/DashboardHome.tsx`
* `src/App.tsx` routing structure

Instead, extend them.

## 10. CRM AccuLynx Sync Rules

### Endpoints Usage
- **GET /api/crm/import/status** - Check sync status for tenant
- **POST /api/crm/import/acculynx/pull** - Manual sync from AccuLynx
- **POST /api/crm/import/acculynx/schedule** - Set auto-sync interval (body: {interval_sec: 300})
- **POST /api/crm/import/acculynx/preview** - Preview what would be imported
- **POST /api/crm/import/file** - Upload file attachments (body: {name, content: base64, record_id?})
- **GET /api/files/{tenant}/{filename}** - Download uploaded files

### Tenant Scoping
- All endpoints require `x-tenant` header
- Default tenant: `the-expert-co`
- Data stored per-tenant in in-memory CRM store

### File Handling
- Files uploaded as base64 content
- Stored locally in `./attachments/{tenant}/` directory
- Served via `/api/files/{tenant}/{filename}` endpoint
- Linked to CRM records via `record_id` field

### File Handling
- Files uploaded as base64 content
- Stored locally in `./attachments/{tenant}/` directory
- Served via `/api/files/{tenant}/{filename}` endpoint
- Linked to CRM records via `record_id` field

### Sync Status Display
- Show last_synced_at from bundle data
- Display sync status chip (OK/Error with message)
- Auto-refresh sync status every 15 seconds
- Provide manual resync and auto-sync buttons

## Agent Actions (AetherLink)

- To run safe, whitelisted local commands, call **POST /api/local/run** with JSON `{ "action": "<name>" }`.
- Always send header `x-tenant: the-expert-co`.
- Only call actions that are in the backend `ALLOWED_LOCAL_CMDS` map.
- Show `stdout` and `stderr` in the UI so operators can see what happened.
- Do **not** loop or spam actions; these are operator-triggered.