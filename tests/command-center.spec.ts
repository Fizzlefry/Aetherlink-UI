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
