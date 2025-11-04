import { test, expect } from "@playwright/test";

const UI_URL = "http://localhost:5173";

test.describe("UI Health Endpoint", () => {

    test("health.json responds with 200", async ({ request }) => {
        const res = await request.get(`${UI_URL}/health.json`);
        expect(res.status()).toBe(200);

        console.log("✅ UI health endpoint is accessible");
    });

    test("health.json has correct structure", async ({ request }) => {
        const res = await request.get(`${UI_URL}/health.json`);
        expect(res.status()).toBe(200);

        const body = await res.json();

        // Should have status field
        expect(body).toHaveProperty("status");
        expect(body.status).toBe("ok");

        // Should have service field
        expect(body).toHaveProperty("service");
        expect(body.service).toBe("aetherlink-ui");

        // Should have version field
        expect(body).toHaveProperty("version");

        console.log("✅ UI health structure validated:", body);
    });

    test("health.json is valid JSON", async ({ request }) => {
        const res = await request.get(`${UI_URL}/health.json`);
        expect(res.status()).toBe(200);

        const contentType = res.headers()["content-type"];
        expect(contentType).toContain("application/json");

        // Should parse without error
        const body = await res.json();
        expect(body).toBeTruthy();

        console.log("✅ UI health returns valid JSON with correct content-type");
    });

    test("health.json is served from public directory", async ({ page }) => {
        // Navigate to the health endpoint
        await page.goto(`${UI_URL}/health.json`);

        // Should display JSON in browser
        const content = await page.textContent("body");
        expect(content).toBeTruthy();

        // Should be parseable JSON
        const json = JSON.parse(content!);
        expect(json.status).toBe("ok");

        console.log("✅ UI health.json accessible via browser navigation");
    });

});
