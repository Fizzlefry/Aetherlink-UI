import { test, expect } from "@playwright/test";

/**
 * Phase IV: Service Registry Tests (v1.13.0)
 * 
 * Tests for the dynamic service registration feature in Command Center.
 * Services can now announce themselves at startup instead of being hardcoded.
 */

const COMMAND_CENTER_URL = "http://localhost:8010";

test.describe("Service Registry", () => {

    test("POST /ops/register without roles returns 401", async ({ request }) => {
        const res = await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            data: {
                name: "test-service",
                url: "http://test-service:9000",
            },
        });
        expect(res.status()).toBe(401);
    });

    test("POST /ops/register with operator role registers service", async ({ request }) => {
        const serviceName = `test-service-${Date.now()}`;

        const res = await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://test-service:9000",
                health_url: "http://test-service:9000/health",
                version: "v1.0.0",
                tags: ["test", "api"],
            },
        });

        expect(res.status()).toBe(200);
        const body = await res.json();
        expect(body).toHaveProperty("status", "ok");
        expect(body).toHaveProperty("registered", serviceName);
        expect(body).toHaveProperty("service_count");
    });

    test("POST /ops/register updates existing service (upsert)", async ({ request }) => {
        const serviceName = `upsert-test-${Date.now()}`;

        // Register first time
        await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://old-url:9000",
                version: "v1.0.0",
            },
        });

        // Update with new URL
        const res = await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://new-url:9001",
                version: "v1.1.0",
            },
        });

        expect(res.status()).toBe(200);

        // Verify update
        const listRes = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });
        const listBody = await listRes.json();
        const service = listBody.services.find((s: any) => s.name === serviceName);
        expect(service).toBeTruthy();
        expect(service.url).toBe("http://new-url:9001");
        expect(service.version).toBe("v1.1.0");
    });

    test("GET /ops/services without roles returns 401", async ({ request }) => {
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/services`);
        expect(res.status()).toBe(401);
    });

    test("GET /ops/services with operator role lists services", async ({ request }) => {
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });

        expect(res.status()).toBe(200);
        const body = await res.json();
        expect(body).toHaveProperty("status", "ok");
        expect(body).toHaveProperty("count");
        expect(body).toHaveProperty("services");
        expect(Array.isArray(body.services)).toBe(true);
    });

    test("GET /ops/services returns registered service details", async ({ request }) => {
        const serviceName = `details-test-${Date.now()}`;

        // Register a service
        await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://details-service:9000",
                health_url: "http://details-service:9000/ping",
                version: "v2.0.0",
                roles_required: ["agent", "operator"],
                tags: ["ai", "production"],
            },
        });

        // List services
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });

        const body = await res.json();
        const service = body.services.find((s: any) => s.name === serviceName);

        expect(service).toBeTruthy();
        expect(service.name).toBe(serviceName);
        expect(service.url).toBe("http://details-service:9000");
        expect(service.health_url).toBe("http://details-service:9000/ping");
        expect(service.version).toBe("v2.0.0");
        expect(service.roles_required).toEqual(["agent", "operator"]);
        expect(service.tags).toEqual(["ai", "production"]);
        expect(service).toHaveProperty("last_seen");
    });

    test("DELETE /ops/services/{name} without roles returns 401", async ({ request }) => {
        const res = await request.delete(`${COMMAND_CENTER_URL}/ops/services/test-service`);
        expect(res.status()).toBe(401);
    });

    test("DELETE /ops/services/{name} removes service from registry", async ({ request }) => {
        const serviceName = `delete-test-${Date.now()}`;

        // Register a service
        await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://delete-service:9000",
            },
        });

        // Delete it
        const deleteRes = await request.delete(`${COMMAND_CENTER_URL}/ops/services/${serviceName}`, {
            headers: { "X-User-Roles": "operator" },
        });

        expect(deleteRes.status()).toBe(200);
        const deleteBody = await deleteRes.json();
        expect(deleteBody).toHaveProperty("status", "ok");
        expect(deleteBody).toHaveProperty("deleted", serviceName);
        expect(deleteBody).toHaveProperty("remaining_count");

        // Verify it's gone
        const listRes = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });
        const listBody = await listRes.json();
        const service = listBody.services.find((s: any) => s.name === serviceName);
        expect(service).toBeUndefined();
    });

    test("DELETE /ops/services/{name} returns 404 for non-existent service", async ({ request }) => {
        const res = await request.delete(`${COMMAND_CENTER_URL}/ops/services/does-not-exist-${Date.now()}`, {
            headers: { "X-User-Roles": "operator" },
        });

        expect(res.status()).toBe(404);
        const body = await res.json();
        expect(body).toHaveProperty("detail");
        expect(body.detail).toContain("not found");
    });

    test("Service registration defaults health_url to /ping", async ({ request }) => {
        const serviceName = `default-health-${Date.now()}`;

        // Register without health_url
        await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://default-service:9000",
            },
        });

        // Check default was applied
        const res = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });
        const body = await res.json();
        const service = body.services.find((s: any) => s.name === serviceName);

        expect(service.health_url).toBe("http://default-service:9000/ping");
    });

    test("Service registration with admin role works", async ({ request }) => {
        const serviceName = `admin-test-${Date.now()}`;

        const res = await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "admin" },
            data: {
                name: serviceName,
                url: "http://admin-service:9000",
            },
        });

        expect(res.status()).toBe(200);
    });

    test("Service registration updates last_seen timestamp", async ({ request }) => {
        const serviceName = `timestamp-test-${Date.now()}`;

        // Register first time
        await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://timestamp-service:9000",
            },
        });

        // Get first timestamp
        const res1 = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });
        const body1 = await res1.json();
        const service1 = body1.services.find((s: any) => s.name === serviceName);
        const firstTimestamp = service1.last_seen;

        // Wait a bit
        await new Promise(resolve => setTimeout(resolve, 1000));

        // Re-register (upsert)
        await request.post(`${COMMAND_CENTER_URL}/ops/register`, {
            headers: { "X-User-Roles": "operator" },
            data: {
                name: serviceName,
                url: "http://timestamp-service:9000",
            },
        });

        // Get second timestamp
        const res2 = await request.get(`${COMMAND_CENTER_URL}/ops/services`, {
            headers: { "X-User-Roles": "operator" },
        });
        const body2 = await res2.json();
        const service2 = body2.services.find((s: any) => s.name === serviceName);
        const secondTimestamp = service2.last_seen;

        // Timestamps should be different
        expect(secondTimestamp).not.toBe(firstTimestamp);
        expect(new Date(secondTimestamp).getTime()).toBeGreaterThan(new Date(firstTimestamp).getTime());
    });

});
