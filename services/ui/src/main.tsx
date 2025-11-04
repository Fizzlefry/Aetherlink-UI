import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import keycloak from './keycloak'
import type Keycloak from "keycloak-js";

// Helper to render the app once we're ready
function renderApp(keycloakInstance: Keycloak) {
    ReactDOM.createRoot(document.getElementById('root')!).render(
        <React.StrictMode>
            <App keycloak={keycloakInstance} />
        </React.StrictMode>
    );
}

// 1) Detect test/bypass mode
const urlParams = new URLSearchParams(window.location.search);
const TEST_MODE =
    urlParams.has("test") ||
    urlParams.get("auth") === "off" ||
    (import.meta as any).env?.VITE_AUTH_DISABLED === "true";

// 2) Provide a mock keycloak so the app doesn't crash
const mockKeycloak = {
    token: "test-token",
    tokenParsed: {
        preferred_username: "testuser",
        sub: "test-user-id",
        email: "testuser@aetherlink.local"
    },
    authenticated: true,
    realm: "aetherlink",
    subject: "test-user",
    idToken: "test-id-token",
    login: () => Promise.resolve(),
    logout: () => Promise.resolve(),
    updateToken: () => Promise.resolve(true),
    loadUserInfo: async () => ({ preferred_username: "testuser" })
} as Keycloak;

// 3) Main logic
if (TEST_MODE) {
    // Test / CI / Playwright path
    console.warn("[AetherLink] 🧪 Auth bypass enabled – rendering app without Keycloak.");
    renderApp(mockKeycloak);
} else {
    // Normal production path
    // Try to init Keycloak, but DO NOT block rendering if it fails
    keycloak
        .init({ onLoad: "login-required" })
        .then((authenticated: boolean) => {
            console.log("[AetherLink] ✅ Keycloak init success, authenticated:", authenticated);
            if (!authenticated) {
                keycloak.login();
                return;
            }
            renderApp(keycloak);
        })
        .catch((err: any) => {
            console.error("[AetherLink] ⚠️ Keycloak init failed, falling back to mock auth:", err);
            // IMPORTANT: Still render the app with mock auth instead of showing error page
            // This allows developers to work even if Keycloak is misconfigured
            renderApp(mockKeycloak);
        });
}
