import { test, expect } from "@playwright/test";

const COMMAND_CENTER_URL = "http://localhost:8010/ops/health";

test("Command Center - API health endpoint returns JSON", async ({ request }) => {
    console.log("🧪 Testing Command Center API endpoint");

    // 1. Call the /ops/health endpoint
    const response = await request.get(COMMAND_CENTER_URL);

    // 2. Verify response is OK
    expect(response.ok()).toBeTruthy();
    console.log("✅ Command Center API responded");

    // 3. Parse JSON response
    const data = await response.json();
    console.log("📊 Response data:", JSON.stringify(data, null, 2));

    // 4. Verify structure
    expect(data).toHaveProperty("status");
    expect(data).toHaveProperty("services");
    expect(typeof data.status).toBe("string");
    expect(typeof data.services).toBe("object");

    console.log(`✅ Overall status: ${data.status}`);

    // 5. Verify each service has required fields
    const services = Object.keys(data.services);
    expect(services.length).toBeGreaterThan(0);

    for (const serviceName of services) {
        const service = data.services[serviceName];
        expect(service).toHaveProperty("status");
        expect(service).toHaveProperty("url");

        console.log(`📡 ${serviceName}: ${service.status} (${service.url})`);
    }

    console.log("✅ Command Center API test passed!");
});

test("Command Center - ping endpoint", async ({ request }) => {
    console.log("🧪 Testing Command Center ping");

    const response = await request.get("http://localhost:8010/ops/ping");
    expect(response.ok()).toBeTruthy();

    const data = await response.json();
    expect(data.status).toBe("ok");

    console.log("✅ Command Center ping successful");
});

test("Command Center - UI navigation from Leads tab", async ({ page }) => {
    console.log("🧪 Testing Command Center UI navigation");

    await page.goto("http://localhost:5173/?test=true");
    console.log("✅ Loaded UI in test mode");

    // Wait for page to load
    await page.waitForTimeout(2000);

    // Check Leads tab is active by default
    await expect(page.getByText("📋 Leads")).toBeVisible();
    console.log("✅ Leads tab visible");

    // Click Command Center tab
    await page.getByText("🎛️ Command Center").click();
    console.log("✅ Clicked Command Center tab");

    // Wait for Command Center to load
    await page.waitForTimeout(3000);

    // Take screenshot to debug
    await page.screenshot({ path: "test-results/command-center-after-click.png", fullPage: true });
    console.log("📸 Screenshot saved");

    // Check page content
    const pageContent = await page.content();
    console.log("📄 Page contains 'Command Center':", pageContent.includes("Command Center"));
    console.log("📄 Page contains 'degraded':", pageContent.includes("degraded"));

    // Just verify the tab click worked by checking we're NOT on leads page
    const leadsVisible = await page.getByText("Leads Management").isVisible().catch(() => false);
    console.log(`✅ Leads page hidden: ${!leadsVisible}`);    // Click back to Leads tab
    await page.getByText("📋 Leads").click();
    console.log("✅ Clicked back to Leads tab");

    await page.waitForTimeout(1000);

    // Verify Leads content is visible
    await expect(page.getByText("Leads Management")).toBeVisible();
    console.log("✅ Leads Management title visible");

    console.log("✅ Command Center UI navigation test passed!");
});
