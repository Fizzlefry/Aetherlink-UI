import { test, expect } from "@playwright/test";

test("Command Center - rejects request without role header", async ({ request }) => {
    console.log("🧪 Testing Command Center RBAC - no roles");

    const response = await request.get("http://localhost:8010/ops/health");

    expect(response.status()).toBe(401);

    const data = await response.json();
    expect(data.detail).toContain("Missing roles header");

    console.log("✅ Command Center correctly rejects unauthenticated requests");
});

test("Command Center - rejects request with insufficient role", async ({ request }) => {
    console.log("🧪 Testing Command Center RBAC - insufficient role (viewer)");

    const response = await request.get("http://localhost:8010/ops/health", {
        headers: {
            "X-User-Roles": "viewer"
        }
    });

    expect(response.status()).toBe(403);

    const data = await response.json();
    expect(data.detail).toContain("Insufficient permissions");

    console.log("✅ Command Center correctly rejects viewer role");
});

test("Command Center - allows operator role", async ({ request }) => {
    console.log("🧪 Testing Command Center RBAC - operator role");

    const response = await request.get("http://localhost:8010/ops/health", {
        headers: {
            "X-User-Roles": "operator"
        }
    });

    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty("status");
    expect(data).toHaveProperty("services");

    console.log(`✅ Command Center allows operator: status=${data.status}`);
});

test("Command Center - allows admin role", async ({ request }) => {
    console.log("🧪 Testing Command Center RBAC - admin role");

    const response = await request.get("http://localhost:8010/ops/health", {
        headers: {
            "X-User-Roles": "admin"
        }
    });

    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data).toHaveProperty("status");
    expect(data).toHaveProperty("services");

    console.log(`✅ Command Center allows admin: status=${data.status}`);
});

test("Command Center - supports multiple roles (comma-separated)", async ({ request }) => {
    console.log("🧪 Testing Command Center RBAC - multiple roles");

    const response = await request.get("http://localhost:8010/ops/health", {
        headers: {
            "X-User-Roles": "viewer,operator,admin"
        }
    });

    expect(response.status()).toBe(200);

    console.log("✅ Command Center correctly handles comma-separated roles");
});

test("Command Center - supports JSON array roles", async ({ request }) => {
    console.log("🧪 Testing Command Center RBAC - JSON array roles");

    const response = await request.get("http://localhost:8010/ops/health", {
        headers: {
            "X-User-Roles": JSON.stringify(["operator", "viewer"])
        }
    });

    expect(response.status()).toBe(200);

    console.log("✅ Command Center correctly handles JSON array roles");
});

test("AI Orchestrator - rejects request without role header", async ({ request }) => {
    console.log("🧪 Testing AI Orchestrator RBAC - no roles");

    const response = await request.post("http://localhost:8011/orchestrate", {
        data: {
            tenant_id: "test-tenant",
            intent: "extract-lead",
            payload: { raw_text: "test" }
        }
    });

    expect(response.status()).toBe(401);

    const data = await response.json();
    expect(data.detail).toContain("Missing roles header");

    console.log("✅ AI Orchestrator correctly rejects unauthenticated requests");
});

test("AI Orchestrator - rejects request with insufficient role", async ({ request }) => {
    console.log("🧪 Testing AI Orchestrator RBAC - insufficient role (viewer)");

    const response = await request.post("http://localhost:8011/orchestrate", {
        headers: {
            "X-User-Roles": "viewer"
        },
        data: {
            tenant_id: "test-tenant",
            intent: "extract-lead",
            payload: { raw_text: "test" }
        }
    });

    expect(response.status()).toBe(403);

    const data = await response.json();
    expect(data.detail).toContain("Insufficient permissions");

    console.log("✅ AI Orchestrator correctly rejects viewer role");
});

test("AI Orchestrator - allows agent role", async ({ request }) => {
    console.log("🧪 Testing AI Orchestrator RBAC - agent role");

    const response = await request.post("http://localhost:8011/orchestrate", {
        headers: {
            "X-User-Roles": "agent"
        },
        data: {
            tenant_id: "test-tenant",
            intent: "extract-lead",
            payload: { raw_text: "John Doe, CEO" }
        }
    });

    // Expect 502 since ai-summarizer isn't running, but proves auth passed
    expect([200, 502]).toContain(response.status());

    console.log(`✅ AI Orchestrator allows agent: status=${response.status()}`);
});

test("AI Orchestrator - allows operator role", async ({ request }) => {
    console.log("🧪 Testing AI Orchestrator RBAC - operator role");

    const response = await request.post("http://localhost:8011/orchestrate", {
        headers: {
            "X-User-Roles": "operator"
        },
        data: {
            tenant_id: "test-tenant",
            intent: "extract-lead",
            payload: { raw_text: "John Doe" }
        }
    });

    // Expect 502 since ai-summarizer isn't running, but proves auth passed
    expect([200, 502]).toContain(response.status());

    console.log(`✅ AI Orchestrator allows operator: status=${response.status()}`);
});

test("AI Orchestrator - allows admin role", async ({ request }) => {
    console.log("🧪 Testing AI Orchestrator RBAC - admin role");

    const response = await request.post("http://localhost:8011/orchestrate", {
        headers: {
            "X-User-Roles": "admin"
        },
        data: {
            tenant_id: "test-tenant",
            intent: "extract-lead",
            payload: { raw_text: "John Doe" }
        }
    });

    // Expect 502 since ai-summarizer isn't running, but proves auth passed
    expect([200, 502]).toContain(response.status());

    console.log(`✅ AI Orchestrator allows admin: status=${response.status()}`);
});
