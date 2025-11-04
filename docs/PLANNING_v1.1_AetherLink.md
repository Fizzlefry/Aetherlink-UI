# AetherLink v1.1 – UI Auth Resilience & Testability

**Branch**: `v1.1-dev`  
**Target Release**: Week of November 10, 2025  
**Priority**: High (unblocks automated testing)

---

## 🎯 Goal

Make the React UI render **even when Keycloak/OIDC init fails** (e.g. during automated tests), so Playwright and other testing agents can exercise the application.

## 📋 Scope

1. **Add UI test/bypass mode** – Allow disabling authentication for automated testing
2. **Make Keycloak init non-blocking** – Render app even if authentication fails
3. **Re-enable Playwright e2e** – Complete the 80% finished test suite
4. **Close v1.0 known issue** – Move from "Known Issue" to "Fixed in v1.1"

---

## ✅ Tasks

### A. UI/Auth Hardening (`services/ui/src/main.tsx`)

- [ ] **Wrap `keycloak.init()` in try/catch** – Always render `<App />` even on failure
- [ ] **Add test mode detection**:
  - Check `VITE_AUTH_DISABLED=true` environment variable
  - Check `?test=true` URL parameter
  - If either is true, skip Keycloak entirely
- [ ] **Create mock Keycloak object** for test mode:
  ```typescript
  const mockKeycloak = {
    authenticated: false,
    token: null,
    login: () => Promise.resolve(),
    logout: () => Promise.resolve(),
  };
  ```
- [ ] **Add error boundary UI** – Show message instead of blank page when auth fails
- [ ] **Log auth state clearly** – Console messages for debugging

**Expected Outcome**: UI renders in all scenarios (auth success, auth failure, test mode)

### B. Playwright Test Suite Re-enablement

- [ ] **Update `tests/aetherlink-with-auth.spec.ts`**:
  - Add `?test=true` to base URL in config
  - Remove Keycloak login steps (no longer needed)
  - Focus on core flow: AI Extract → Create Lead
- [ ] **Create separate auth test** (`tests/aetherlink-auth.spec.ts`):
  - Keep the Keycloak login flow test
  - Verify OIDC redirect works
  - Run as optional/manual test
- [ ] **Update selectors** to match actual button text from UI
- [ ] **Run full suite**: `npx playwright test --headed --project=chromium`

**Expected Outcome**: All Playwright tests pass in test mode

### C. Documentation Updates

- [ ] **Update `docs/RELEASE_NOTES_v1.0_AetherLink.md`**:
  - Move "UI Authentication" from "Known Issues" to "Fixed in v1.1" section
- [ ] **Update `docs/VALIDATION_REPORT.md`**:
  - Add "v1.1 Resolution" note to UI auth issue
- [ ] **Create `docs/RELEASE_NOTES_v1.1_AetherLink.md`**:
  - Document auth resilience feature
  - Document test mode capability
  - Include Playwright test results

**Expected Outcome**: Clear communication of fix and testing improvements

---

## 🔧 Implementation Details

### Priority 1: Non-Blocking Keycloak Init

**Current Problem** (services/ui/src/main.tsx):
```typescript
keycloak
  .init({ onLoad: "login-required" })
  .then(() => {
    createRoot(document.getElementById("root")!).render(
      <StrictMode>
        <App />
      </StrictMode>
    );
  })
  .catch((error) => {
    console.error("Keycloak init failed", error);
    // ❌ NO RENDER - blank page
  });
```

**New Approach**:
```typescript
// Check for test mode
const testMode =
  import.meta.env.VITE_AUTH_DISABLED === "true" ||
  window.location.search.includes("test=true");

if (testMode) {
  console.log("🧪 Running in TEST MODE - auth disabled");
  // Mock Keycloak and render immediately
  window.keycloak = mockKeycloak;
  renderApp();
} else {
  // Normal auth flow with error resilience
  keycloak
    .init({ onLoad: "login-required" })
    .then(() => renderApp())
    .catch((error) => {
      console.error("⚠️ Keycloak init failed:", error);
      console.log("Rendering app anyway with mock auth...");
      window.keycloak = mockKeycloak;
      renderApp(); // ✅ ALWAYS RENDER
    });
}

function renderApp() {
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App />
    </StrictMode>
  );
}
```

### Priority 2: Environment Variable Support

**Add to `.env.example`**:
```bash
# Testing: Set to "true" to disable Keycloak authentication
VITE_AUTH_DISABLED=false
```

**Add to `playwright.config.ts`**:
```typescript
use: {
  baseURL: 'http://localhost:5173?test=true',
  // Or set env var in docker-compose.dev.yml for test container
}
```

---

## 🧪 Testing Strategy

### Manual Testing
1. **Test Mode via URL**: Visit `http://localhost:5173?test=true`
   - ✅ Should render immediately without Keycloak redirect
   - ✅ Should show mock user or "Test Mode" indicator
   - ✅ Should allow interaction with UI features

2. **Test Mode via ENV**: Set `VITE_AUTH_DISABLED=true` in `.env`
   - ✅ Rebuild UI: `docker-compose up -d --build aether-crm-ui`
   - ✅ Visit `http://localhost:5173`
   - ✅ Should render without authentication

3. **Normal Auth Mode**: Visit `http://localhost:5173` (default)
   - ✅ Should redirect to Keycloak login
   - ✅ After login, should render app successfully
   - ✅ If auth fails, should render with error message (not blank)

### Automated Testing
```powershell
# Run Playwright tests in test mode
npx playwright test tests/aetherlink-with-auth.spec.ts --headed --project=chromium

# Expected results:
# ✅ Test 1: AI Extract → Should pass (no auth blocker)
# ✅ Test 2: Create Lead → Should pass (full flow validated)
```

---

## 📊 Success Criteria

- ✅ UI renders in all scenarios (test mode, auth success, auth failure)
- ✅ Playwright test suite passes completely
- ✅ Test mode can be enabled via URL parameter or environment variable
- ✅ Normal authentication flow still works for production use
- ✅ Error messages displayed gracefully instead of blank page
- ✅ Documentation updated with resolution details
- ✅ All v1.0 "Known Issues" closed

---

## 🚀 Deployment Plan

1. **Development**: Complete work on `v1.1-dev` branch
2. **Testing**: Run full Playwright suite + manual testing
3. **Review**: Code review of auth changes
4. **Merge**: `v1.1-dev` → `master`
5. **Tag**: Create `v1.1.0` tag
6. **Deploy**: Update docker-compose, restart UI service
7. **Validate**: Re-run Playwright tests in production

---

## 📚 Related Documentation

- **v1.0 Validation Report**: `docs/VALIDATION_REPORT.md`
- **v1.0 Release Notes**: `docs/RELEASE_NOTES_v1.0_AetherLink.md`
- **Playwright Test Suite**: `tests/aetherlink-with-auth.spec.ts`
- **Keycloak Config**: `infra/core/keycloak-client.json`

---

## 🔗 Next Steps After v1.1

Once UI auth is stable and tested:
- **Phase II Decision**: Revisit Command Center + AI Orchestrator expansion (see `docs/PHASE_II_DECISION_GUIDE.md`)
- **Production Metrics**: Collect performance data from v1.0 deployment
- **Scale Planning**: Evaluate need for additional features vs optimization
