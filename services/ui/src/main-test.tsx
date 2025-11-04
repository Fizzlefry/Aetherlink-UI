import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App.tsx'
import keycloak from './keycloak'

// Check if we're in test mode (no auth)
const isTestMode = window.location.search.includes('test=true');

if (isTestMode) {
    console.log("🧪 TEST MODE: Bypassing Keycloak authentication");

    // Create a mock keycloak object
    const mockKeycloak: any = {
        token: "test-token",
        tokenParsed: {
            preferred_username: "testuser",
            sub: "test-user-id",
            tenant_id: "test-tenant"
        },
        authenticated: true,
        login: () => Promise.resolve(),
        logout: () => Promise.resolve(),
        updateToken: () => Promise.resolve(true)
    };

    ReactDOM.createRoot(document.getElementById('root')!).render(
        <React.StrictMode>
            <App keycloak={mockKeycloak} />
        </React.StrictMode>
    );
} else {
    // Normal Keycloak flow
    keycloak
        .init({ onLoad: "login-required" })
        .then((authenticated) => {
            if (!authenticated) {
                keycloak.login();
                return;
            }

            ReactDOM.createRoot(document.getElementById('root')!).render(
                <React.StrictMode>
                    <App keycloak={keycloak} />
                </React.StrictMode>
            );
        })
        .catch((err) => {
            console.error("Keycloak init failed", err);
            // Render error state
            document.getElementById('root')!.innerHTML = `
                <div style="padding: 20px; color: red;">
                    <h2>Authentication Error</h2>
                    <p>Keycloak initialization failed. Please refresh the page.</p>
                    <pre>${err}</pre>
                </div>
            `;
        });
}
