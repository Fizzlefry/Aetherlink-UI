# Phase VIII – M3: Delivery History Timeline

**Status:** ✅ Complete
**Services Touched:**
- `services/command-center` (FastAPI)
- `services/ui` (React / Vite)
- `deploy/docker-compose.dev.yml` (rebuild to pick up new routers)

---

## 1. Objective

Extend the Operator Dashboard (built in Phase VIII M1) and the Alert Rule Templates (Phase VIII M2) with **delivery-level observability**, so operators can see **what actually happened** to alerts after they were enqueued by the reliable delivery engine from Phase VII.

This closes the loop:

1. Phase VII = infra (queue, retries, dedupe, dead letters)
2. Phase VIII M1 = visibility
3. Phase VIII M2 = action (create rules from templates)
4. **Phase VIII M3 = confirmation** (did the alert deliver? if not, why?)

---

## 2. What We Added

### 2.1 Backend: Delivery History Router

**File:** `services/command-center/routers/delivery_history.py`

- **`GET /alerts/deliveries/history`**
  - Returns the most recent N deliveries (default 50)
  - Supports `?tenant_id=...` to filter by tenant
  - Sorted newest → oldest
  - Returns status, attempts, target, timestamps, and last error

- **`GET /alerts/deliveries/{delivery_id}`**
  - Returns full detail for a single delivery row
  - Useful for future UI expansions (slide-over, payload view)

- **Seeding:**
  - `seed_delivery_history()` creates ~5 realistic delivery records on startup so the UI is never empty
  - Records include different statuses: `delivered`, `failed`, `pending`, `dead_letter`
  - Good for local/dev demo

### 2.2 main.py Wiring

**File:** `services/command-center/main.py`

- Imported the new router:
  ```python
  from routers import alerts, alert_templates, delivery_history, events
  ```

- Mounted it:
  ```python
  app.include_router(delivery_history.router)
  ```

- Called the seeder in the startup hook:
  ```python
  @app.on_event("startup")
  def startup_event():
      alert_templates.seed_default_templates()
      delivery_history.seed_delivery_history()
  ```

> Note: Because the service is built via Docker, we rebuilt and force-recreated the `command-center` service so the new router files were copied into `/app/routers/` inside the container.

---

## 3. Frontend: Operator Dashboard Update

**File:** `services/ui/src/pages/OperatorDashboard.tsx`

**New section added:** **"📜 Recent Delivery History"**

**Features:**

- Fetches from `GET /alerts/deliveries/history` on load
- Respects the same tenant filter used everywhere else (`All / qa / premium / acme / ...`)
- Shows a **table** with:
  - **Status** (color-coded)
    - ✅ `delivered` → green badge
    - ❗ `failed` → red badge
    - ⏳ `pending` → gray badge
    - 🛑 `dead_letter` → darker/red badge
  - **Event / Rule** (so you know which rule produced it)
  - **Target** (webhook/channel; truncated with ellipsis)
  - **Attempts** (`current/max`)
  - **Next Retry** (if not delivered)
  - **Tenant**
  - **Created time**
  - **Last error** (shown inline, useful for HTTP 503 / timeout)
- Manual **Refresh** button so ops can re-pull without waiting for the auto-refresh loop
- Fits the existing dark theme (slate bg, subtle borders) from M1/M2

---

## 4. End-to-End Flow After M3

```text
Operator creates rule from template (M2)
   ↓
Rule evaluator (Phase VII) fires when condition is met
   ↓
Alert delivery is enqueued with retry metadata
   ↓
Operator Dashboard → "Recent Delivery History" (M3) shows:
   - delivered alerts
   - alerts currently retrying
   - alerts that dead-lettered
   - exact error message from provider
```

This gives operators immediate confirmation that the thing they just set up in M2 is **actually working**.

---

## 5. How to Run / Test

1. **Rebuild command-center** (already done in your session):

   ```powershell
   docker-compose -f "c:\Users\jonmi\OneDrive\Documents\AetherLink\deploy\docker-compose.dev.yml" build command-center
   docker-compose -f "c:\Users\jonmi\OneDrive\Documents\AetherLink\deploy\docker-compose.dev.yml" up -d --force-recreate command-center
   ```

2. **Verify backend endpoint**:

   ```powershell
   Invoke-WebRequest -Uri "http://localhost:8010/alerts/deliveries/history" -Headers @{"X-User-Roles"="operator"}
   ```

   You should see 4–5 demo records.

3. **Run UI**:

   ```bash
   cd services/ui
   npm run dev
   # open http://localhost:5173
   # click 📊 Operator
   # scroll to "Recent Delivery History"
   ```

4. **Change tenant** in the selector and confirm the panel re-queries the API with `?tenant_id=...`.

---

## 6. Notes / Implementation Details

- **Why we saw 404 earlier:** the new router files were in your host repo but not inside the container image; recreating the container pulled them in.
- **RBAC:** you called the endpoint with `X-User-Roles: operator` which matches our intended use. Keep that header in scripts.
- **Seeding:** good for demo; in production you'll want to remove/replace with real DB-backed queries.
- **Limit:** kept to 50 by default to avoid rendering issues on the dashboard.

---

## 7. What This Unlocks Next (Phase VIII M4/M5 Ideas)

1. **Per-delivery detail drawer** – click a row → show raw payload, HTTP status, headers.
2. **Provider health panel** – aggregate failures by domain (`hooks.slack.com`, `office.com`, etc.).
3. **Dead-letter drilldown** – filter to only `dead_letter` and show "replay" action (if you build a replay endpoint).
4. **Time-window filtering** – last 15m / 1h / 24h.

---

## 8. Version / Changelog

- **v1.22.0-ops** (proposed)
  - Added `/alerts/deliveries/history` endpoint
  - Updated Operator Dashboard with Delivery History panel
  - Confirmed tenant-aware UI + API
