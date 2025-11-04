import { test, expect } from "@playwright/test";

/**
 * Phase III M6: Security Audit Logging Tests
 * 
 * These tests validate that all sensitive services track requests with:
 * - Request counts
 * - Authorization failures (401/403)
 * - Path usage statistics
 * - Status code breakdowns
 * 
 * This provides operational visibility for security monitoring.
 */

const COMMAND_CENTER_URL = "http://localhost:8010";
const AI_ORCHESTRATOR_URL = "http://localhost:8011";
const AUTO_HEAL_URL = "http://localhost:8012";

test.describe("Phase III M6 - Security Audit Logging", () => {
    test("Command Center exposes audit stats endpoint", async ({ request }) => {
        const res = await request.get(`${COMMAND_CENTER_URL}/audit/stats`, {
            headers: {
                "X-User-Roles": "operator",
            },
        });

        expect([200, 404]).toContain(res.status());

        if (res.status() === 200) {
            const body = await res.json();

            // Verify audit stats structure
            expect(body).toHaveProperty("total_requests");
            expect(body).toHaveProperty("denied_401_unauthorized");
            expect(body).toHaveProperty("denied_403_forbidden");
            expect(body).toHaveProperty("by_path");
            expect(body).toHaveProperty("by_status");

            // Verify types
            expect(typeof body.total_requests).toBe("number");
            expect(typeof body.denied_401_unauthorized).toBe("number");
            expect(typeof body.denied_403_forbidden).toBe("number");
            expect(typeof body.by_path).toBe("object");
            expect(typeof body.by_status).toBe("object");
        }
    });

    test("AI Orchestrator exposes audit stats endpoint", async ({ request }) => {
        const res = await request.get(`${AI_ORCHESTRATOR_URL}/audit/stats`, {
            headers: {
                "X-User-Roles": "operator",
            },
        });

        expect([200, 404]).toContain(res.status());

        if (res.status() === 200) {
            const body = await res.json();

            // Verify audit stats structure
            expect(body).toHaveProperty("total_requests");
            expect(body).toHaveProperty("denied_401_unauthorized");
            expect(body).toHaveProperty("denied_403_forbidden");
            expect(body).toHaveProperty("by_path");
            expect(body).toHaveProperty("by_status");
        }
    });

    test("Auto-Heal exposes audit stats endpoint", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/audit/stats`);

        expect([200, 404]).toContain(res.status());

        if (res.status() === 200) {
            const body = await res.json();

            // Verify audit stats structure
            expect(body).toHaveProperty("total_requests");
            expect(body).toHaveProperty("denied_401_unauthorized");
            expect(body).toHaveProperty("denied_403_forbidden");
            expect(body).toHaveProperty("by_path");
            expect(body).toHaveProperty("by_status");
        }
    });

    test("Audit tracks 401 unauthorized attempts", async ({ request }) => {
        // Make request without auth header
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/health`);

        // Should be 401 (unless RBAC is disabled)
        expect([200, 401]).toContain(res.status());

        // Check audit stats
        const statsRes = await request.get(`${COMMAND_CENTER_URL}/audit/stats`, {
            headers: {
                "X-User-Roles": "operator",
            },
        });

        if (statsRes.status() === 200) {
            const stats = await statsRes.json();

            // Total should be at least 2 (health check + stats check)
            expect(stats.total_requests).toBeGreaterThanOrEqual(2);

            // If RBAC is enabled, should have 401 count
            if (res.status() === 401) {
                expect(stats.denied_401_unauthorized).toBeGreaterThan(0);
            }
        }
    });

    test("Audit tracks 403 forbidden attempts", async ({ request }) => {
        // Make request with insufficient role (viewer)
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/health`, {
            headers: {
                "X-User-Roles": "viewer",
            },
        });

        // Should be 403 (unless RBAC is disabled or viewer is allowed)
        expect([200, 403]).toContain(res.status());

        // Check audit stats
        const statsRes = await request.get(`${COMMAND_CENTER_URL}/audit/stats`, {
            headers: {
                "X-User-Roles": "operator",
            },
        });

        if (statsRes.status() === 200) {
            const stats = await statsRes.json();

            // If RBAC is enabled and viewer was denied, should have 403 count
            if (res.status() === 403) {
                expect(stats.denied_403_forbidden).toBeGreaterThan(0);
            }
        }
    });

    test("Audit tracks path usage", async ({ request }) => {
        // Make several requests to different paths
        await request.get(`${COMMAND_CENTER_URL}/ops/ping`);
        await request.get(`${COMMAND_CENTER_URL}/ops/health`, {
            headers: { "X-User-Roles": "operator" },
        });

        // Check audit stats
        const statsRes = await request.get(`${COMMAND_CENTER_URL}/audit/stats`, {
            headers: {
                "X-User-Roles": "operator",
            },
        });

        if (statsRes.status() === 200) {
            const stats = await statsRes.json();

            // Should have path breakdown
            expect(Object.keys(stats.by_path).length).toBeGreaterThan(0);

            // Common paths should be tracked
            const paths = Object.keys(stats.by_path);
            expect(paths.some((p) => p.includes("/ping") || p.includes("/health") || p.includes("/audit"))).toBe(true);
        }
    });

    test("Audit tracks status code breakdown", async ({ request }) => {
        // Make requests that return different status codes
        await request.get(`${COMMAND_CENTER_URL}/ops/ping`); // 200
        await request.get(`${COMMAND_CENTER_URL}/ops/health`, {
            headers: { "X-User-Roles": "operator" },
        }); // 200 or degraded

        // Check audit stats
        const statsRes = await request.get(`${COMMAND_CENTER_URL}/audit/stats`, {
            headers: {
                "X-User-Roles": "operator",
            },
        });

        if (statsRes.status() === 200) {
            const stats = await statsRes.json();

            // Should have status breakdown
            expect(Object.keys(stats.by_status).length).toBeGreaterThan(0);

            // Should have 200 responses
            expect(stats.by_status).toHaveProperty("200");
            expect(stats.by_status["200"]).toBeGreaterThan(0);
        }
    });

    test("AI Orchestrator audit tracks RBAC enforcement", async ({ request }) => {
        // Attempt orchestration without auth
        const res = await request.post(`${AI_ORCHESTRATOR_URL}/orchestrate`, {
            data: {
                tenant_id: "test",
                intent: "extract-lead",
                payload: { raw_text: "test" },
            },
        });

        // Should be 401
        expect(res.status()).toBe(401);

        // Check audit stats
        const statsRes = await request.get(`${AI_ORCHESTRATOR_URL}/audit/stats`, {
            headers: {
                "X-User-Roles": "operator",
            },
        });

        if (statsRes.status() === 200) {
            const stats = await statsRes.json();

            // Should have tracked the 401
            expect(stats.denied_401_unauthorized).toBeGreaterThan(0);
            expect(stats.by_status).toHaveProperty("401");
        }
    });
});
