import { test, expect } from "@playwright/test";

const AUTO_HEAL_URL = "http://localhost:8012";

test.describe("Auto-Heal Service", () => {

    test("ping endpoint works", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/ping`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty("status");
        expect(body.status).toBe("ok");

        console.log("✅ Auto-Heal ping returned:", body);
    });

    test("health endpoint returns up status", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/health`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        expect(body).toHaveProperty("status");
        expect(body.status).toBe("up");
        expect(body).toHaveProperty("service");
        expect(body.service).toBe("auto-heal");

        console.log("✅ Auto-Heal health check passed:", body);
    });

    test("status endpoint returns watch list", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/autoheal/status`);
        expect(res.status()).toBe(200);

        const body = await res.json();

        // Should have watching array
        expect(body).toHaveProperty("watching");
        expect(Array.isArray(body.watching)).toBeTruthy();
        console.log("✅ Auto-Heal is watching:", body.watching);

        // Should have interval
        expect(body).toHaveProperty("interval_seconds");
        expect(typeof body.interval_seconds).toBe("number");
        console.log(`✅ Check interval: ${body.interval_seconds}s`);

        // Should have last_report structure
        expect(body).toHaveProperty("last_report");
        expect(body.last_report).toHaveProperty("last_run");
        expect(body.last_report).toHaveProperty("attempts");
        expect(Array.isArray(body.last_report.attempts)).toBeTruthy();

        console.log("✅ Auto-Heal status structure validated");
    });

    test("status endpoint includes expected services", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/autoheal/status`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        const watching = body.watching;

        // Should be watching the key Phase II services
        expect(watching).toContain("aether-command-center");
        expect(watching).toContain("aether-ai-orchestrator");

        console.log("✅ Auto-Heal is monitoring Phase II services:", watching);
    });

    test("attempts array has correct structure when healing occurs", async ({ request }) => {
        const res = await request.get(`${AUTO_HEAL_URL}/autoheal/status`);
        expect(res.status()).toBe(200);

        const body = await res.json();
        const attempts = body.last_report.attempts;

        // Attempts should be an array (empty if no healing needed)
        expect(Array.isArray(attempts)).toBeTruthy();

        // If there were attempts, validate structure
        if (attempts.length > 0) {
            const firstAttempt = attempts[0];
            expect(firstAttempt).toHaveProperty("service");
            expect(firstAttempt).toHaveProperty("action");
            expect(firstAttempt).toHaveProperty("success");
            expect(firstAttempt).toHaveProperty("msg");
            expect(firstAttempt).toHaveProperty("timestamp");

            console.log(`✅ Found healing attempt for ${firstAttempt.service}:`, firstAttempt);
        } else {
            console.log("✅ No healing attempts needed (all services healthy)");
        }
    });

});
