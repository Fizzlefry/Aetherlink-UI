import { test, expect } from "@playwright/test";

/**
 * Phase III M4: Auto-Heal History & Statistics Tests
 * 
 * These tests validate the new operational intelligence endpoints added in v1.9.0:
 * - GET /autoheal/history?limit=N - Recent healing attempts with configurable limit
 * - GET /autoheal/stats - Success rate, service counts, and most healed service
 * 
 * Tests ensure backward compatibility and protect the new observability features.
 */

const AUTO_HEAL_BASE_URL = "http://localhost:8012";

test.describe("Auto-Heal History Endpoint", () => {
    test("GET /autoheal/history returns 200 with correct structure", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/history`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // Validate response structure
        expect(body).toHaveProperty("history");
        expect(body).toHaveProperty("total_in_history");
        expect(body).toHaveProperty("limit");

        // Validate data types
        expect(Array.isArray(body.history)).toBe(true);
        expect(typeof body.total_in_history).toBe("number");
        expect(typeof body.limit).toBe("number");
    });

    test("GET /autoheal/history respects limit parameter", async ({ request }) => {
        const requestedLimit = 5;
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/history?limit=${requestedLimit}`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // Returned limit should match requested (or be capped at MAX_HISTORY)
        expect(body.limit).toBe(requestedLimit);

        // History array should not exceed requested limit
        expect(body.history.length).toBeLessThanOrEqual(requestedLimit);
    });

    test("GET /autoheal/history enforces MAX_HISTORY cap", async ({ request }) => {
        const oversizedLimit = 100;
        const maxHistory = 50; // Server-side MAX_HISTORY constant

        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/history?limit=${oversizedLimit}`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // Limit should be capped at MAX_HISTORY
        expect(body.limit).toBe(maxHistory);
        expect(body.history.length).toBeLessThanOrEqual(maxHistory);
    });

    test("GET /autoheal/history returns newest attempts first", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/history?limit=10`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // If there's history, validate ordering (newer timestamps come first)
        if (body.history.length > 1) {
            for (let i = 0; i < body.history.length - 1; i++) {
                const current = body.history[i];
                const next = body.history[i + 1];

                expect(current).toHaveProperty("timestamp");
                expect(next).toHaveProperty("timestamp");

                // Current timestamp should be >= next (descending order)
                expect(current.timestamp).toBeGreaterThanOrEqual(next.timestamp);
            }
        }
    });

    test("GET /autoheal/history items have required fields", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/history?limit=1`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // If there's any history, validate item structure
        if (body.history.length > 0) {
            const attempt = body.history[0];

            expect(attempt).toHaveProperty("service");
            expect(attempt).toHaveProperty("action");
            expect(attempt).toHaveProperty("success");
            expect(attempt).toHaveProperty("msg");
            expect(attempt).toHaveProperty("timestamp");

            expect(typeof attempt.service).toBe("string");
            expect(typeof attempt.action).toBe("string");
            expect(typeof attempt.success).toBe("boolean");
            expect(typeof attempt.msg).toBe("string");
            expect(typeof attempt.timestamp).toBe("number");
        }
    });
});

test.describe("Auto-Heal Statistics Endpoint", () => {
    test("GET /autoheal/stats returns 200 with correct structure", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/stats`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // Validate response structure
        expect(body).toHaveProperty("total_attempts");
        expect(body).toHaveProperty("successful");
        expect(body).toHaveProperty("failed");
        expect(body).toHaveProperty("success_rate");
        expect(body).toHaveProperty("services");

        // Validate data types
        expect(typeof body.total_attempts).toBe("number");
        expect(typeof body.successful).toBe("number");
        expect(typeof body.failed).toBe("number");
        expect(typeof body.success_rate).toBe("number");
        expect(typeof body.services).toBe("object");
    });

    test("GET /autoheal/stats calculates totals correctly", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/stats`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // total_attempts should equal successful + failed
        expect(body.total_attempts).toBe(body.successful + body.failed);

        // All counts should be non-negative
        expect(body.total_attempts).toBeGreaterThanOrEqual(0);
        expect(body.successful).toBeGreaterThanOrEqual(0);
        expect(body.failed).toBeGreaterThanOrEqual(0);
    });

    test("GET /autoheal/stats success_rate is valid percentage", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/stats`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // Success rate should be between 0 and 100
        expect(body.success_rate).toBeGreaterThanOrEqual(0);
        expect(body.success_rate).toBeLessThanOrEqual(100);

        // If there are attempts, validate the calculation
        if (body.total_attempts > 0) {
            const expectedRate = (body.successful / body.total_attempts) * 100;
            expect(Math.abs(body.success_rate - expectedRate)).toBeLessThan(0.1); // Allow for rounding
        } else {
            // No attempts should mean 0% success rate
            expect(body.success_rate).toBe(0);
        }
    });

    test("GET /autoheal/stats services counts match total", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/stats`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // Sum of per-service counts should equal total_attempts
        const servicesTotal = Object.values(body.services).reduce((sum: number, count) => sum + (count as number), 0);
        expect(servicesTotal).toBe(body.total_attempts);
    });

    test("GET /autoheal/stats most_healed is correct", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/stats`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // If there's a most_healed service, it should exist in services
        if (body.most_healed) {
            expect(body.services).toHaveProperty(body.most_healed);

            // It should have the highest count
            const mostHealedCount = body.services[body.most_healed];
            const allCounts = Object.values(body.services) as number[];
            const maxCount = Math.max(...allCounts);

            expect(mostHealedCount).toBe(maxCount);
        } else {
            // No most_healed means no attempts
            expect(body.total_attempts).toBe(0);
        }
    });
});

test.describe("Auto-Heal Backward Compatibility", () => {
    test("GET /autoheal/status still works (backward compatibility)", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_BASE_URL}/autoheal/status`);

        expect(res.status()).toBe(200);

        const body = await res.json();

        // Original status endpoint structure unchanged
        expect(body).toHaveProperty("watching");
        expect(body).toHaveProperty("interval_seconds");
        expect(body).toHaveProperty("last_report");

        expect(Array.isArray(body.watching)).toBe(true);
        expect(typeof body.interval_seconds).toBe("number");
    });
});
