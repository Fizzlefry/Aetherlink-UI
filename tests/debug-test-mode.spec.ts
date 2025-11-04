import { test, expect } from "@playwright/test";

const APP_URL = "http://localhost:5173/?test=true";

test("UI loads in test mode", async ({ page }) => {
    console.log("🧪 Testing if UI loads with ?test=true parameter");

    await page.goto(APP_URL, { waitUntil: "networkidle" });

    console.log("✅ Page loaded");

    // Wait for React to mount
    await page.waitForTimeout(2000);

    // Capture what's in the page
    const pageTitle = await page.title();
    console.log("📄 Page title:", pageTitle);

    const bodyText = await page.textContent("body");
    console.log("📝 Body text length:", bodyText?.length || 0);
    console.log("📝 First 200 chars:", bodyText?.substring(0, 200));

    // Check browser console
    page.on('console', msg => console.log('🖥️ Browser:', msg.text()));

    // Take screenshot
    await page.screenshot({ path: 'test-results/debug-test-mode.png', fullPage: true });

    // Check if root div has content
    const rootHTML = await page.locator('#root').innerHTML();
    console.log("🎯 Root innerHTML length:", rootHTML.length);
    console.log("🎯 Root HTML:", rootHTML.substring(0, 300));

    // Verify page isn't blank
    expect(rootHTML.length).toBeGreaterThan(100);
});
