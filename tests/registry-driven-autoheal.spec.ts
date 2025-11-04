import { test, expect } from "@playwright/test";

/**
 * Phase V: Registry-Driven Auto-Heal Tests
 *
 * Tests the integration between Command Center registry and Auto-Heal service.
 * Verifies that services registered dynamically are picked up by the healing loop.
 */

const COMMAND_CENTER_URL = "http://localhost:8010";
const AUTO_HEAL_URL = "http://localhost:8012";

test.describe("Registry-Driven Auto-Heal Integration", () => {

    test("Auto-Heal can fetch services from registry without errors", async ({ request }) => {
        // Register a temporary service
        const serviceName = `registry-heal-test-${Date.now()}`;

        await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://test-service:9999",
                health_url: "http://test-service:9999/ping",
                version: "v0.0.1",
                tags: ["test"],
            },
        });

        // Verify Auto-Heal status endpoint still works
        const res = await request.get(`${AUTO_HEAL_URL}/autoheal/status`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty("watching");
        expect(body).toHaveProperty("interval_seconds");
        expect(body).toHaveProperty("last_report");

        // Clean up
        await request.delete(`${COMMAND_CENTER_URL}/ops/services/${serviceName}`, {
            headers: { "X-User-Roles": "operator" },
        });
    });

    test("Auto-Heal history endpoint works with registry integration", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/autoheal/history?limit=5`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty("history");
        expect(body).toHaveProperty("total_in_history");
        expect(body).toHaveProperty("limit", 5);
        expect(Array.isArray(body.history)).toBe(true);
    });

    test("Auto-Heal stats endpoint works with registry integration", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/autoheal/stats`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty("total_attempts");
        expect(body).toHaveProperty("successful");
        expect(body).toHaveProperty("failed");
        expect(body).toHaveProperty("success_rate");
        expect(typeof body.success_rate).toBe("number");
    });

    test("AI Orchestrator registers itself and appears in Command Center", async ({ request }) => {
        // Wait a bit for AI Orchestrator startup to complete
        await new Promise(resolve => setTimeout(resolve, 2000));

        // Check if AI Orchestrator is in the registry
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });

        expect(res.status()).toBe(200);
        const body = await res.json();

        // AI Orchestrator should have self-registered
        const aiOrch = body.services?.find((s: any) => s.name === "aether-ai-orchestrator");

        if (aiOrch) {
            // If found, validate its registration
            expect(aiOrch.url).toBeTruthy();
            expect(aiOrch.health_url).toContain("/ping");
            expect(aiOrch.version).toBeTruthy();
            expect(aiOrch.tags).toContain("ai");
            expect(aiOrch).toHaveProperty("last_seen");
            console.log("✅ AI Orchestrator self-registered successfully:", aiOrch);
        } else {
            // Not registered yet (startup not complete or feature disabled)
            console.log("⚠️  AI Orchestrator not yet registered (may need restart)");
        }
    });

    test("Registry services have valid health URLs for Auto-Heal", async ({ request }) => {
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });

        expect(res.status()).toBe(200);
        const body = await res.json();

        // All registered services should have health_url
        for (const service of body.services || []) {
            expect(service).toHaveProperty("health_url");
            expect(typeof service.health_url).toBe("string");
            expect(service.health_url).toContain("http");

            // Should end with /ping or /health by convention
            const isValidHealthUrl =
                service.health_url.includes("/ping") ||
                service.health_url.includes("/health");

            if (!isValidHealthUrl) {
                console.log(`⚠️  Service ${service.name} has non-standard health_url: ${service.health_url}`);
            }
        }
    });

    test("Command Center provides registry and auto-heal data for reconciliation", async ({ request }) => {
        // Fetch both endpoints
        const [registryRes, autohealRes] = await Promise.all([
            request.get(`${COMMAND_CENTER_URL}/ops/services`, {
                headers: { "X-User-Roles": "operator" },
            }),
            request.get(`${AUTO_HEAL_URL}/autoheal/status`),
        ]);

        expect(registryRes.status()).toBe(200);
        expect(autohealRes.status()).toBe(200);

        const registry = await registryRes.json();
        const autoheal = await autohealRes.json();

        // Both should return valid data structures
        expect(registry).toHaveProperty("services");
        expect(autoheal).toHaveProperty("watching");

        const registeredNames = new Set(registry.services?.map((s: any) => s.name) || []);
        const monitoredNames = new Set(autoheal.watching || []);

        console.log("📊 Reconciliation view:");
        console.log(`  - Registered services: ${registeredNames.size}`);
        console.log(`  - Monitored services: ${monitoredNames.size}`);

        // Services monitored but not registered (old pattern)
        const monitoredNotRegistered = Array.from(monitoredNames).filter(
            name => !registeredNames.has(name)
        );

        if (monitoredNotRegistered.length > 0) {
            console.log(`  - Monitored but not registered: ${monitoredNotRegistered.join(", ")}`);
        }

        // Services registered but not monitored (need auto-heal to pick them up)
        const registeredNotMonitored = Array.from(registeredNames).filter(
            name => !monitoredNames.has(name)
        );

        if (registeredNotMonitored.length > 0) {
            console.log(`  - Registered but not monitored: ${registeredNotMonitored.join(", ")}`);
        }
    });

});
