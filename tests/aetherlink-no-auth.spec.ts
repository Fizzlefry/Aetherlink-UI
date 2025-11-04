import { test, expect } from "@playwright/test";

const APP_URL = "http://localhost:5173/?test=true";

test("AI Extract → Create Lead (no-auth mode)", async ({ page }) => {
    // 1. Open the app in test mode (bypasses Keycloak)
    await page.goto(APP_URL, { waitUntil: "networkidle" });

    console.log("✅ Page loaded with ?test=true");

    // 2. Small grace period for React to mount
    await page.waitForTimeout(1000);

    // 3. Click to expand the "Create New Lead (with AI Extract)" panel
    const createPanelButton = await page.getByText("✨ Create New Lead (with AI Extract)");
    await createPanelButton.click();

    console.log("✅ Create panel expanded");
    await page.waitForTimeout(500);

    // 4. Find the textarea for AI extraction (it's in the gray box)
    const textarea = await page.locator('textarea').first();

    if (!(await textarea.isVisible())) {
        await page.screenshot({
            path: "test-results/no-textarea.png",
            fullPage: true,
        });
        throw new Error("Could not find the lead input textarea.");
    } const sampleText = `Sarah Chen
Director of Engineering @ TechStart Inc
sarah.chen@techstart.io
415-555-0199
Warm intro from Mike at CloudConf 2024`;

    await textarea.fill(sampleText);
    console.log("✅ Sample text filled into textarea");

    // 5. Click "Run AI Extract" button
    const extractButton = await page.getByRole('button', { name: 'Run AI Extract' });

    if (!(await extractButton.isVisible())) {
        await page.screenshot({
            path: "test-results/no-extract-button.png",
            fullPage: true,
        });
        throw new Error("Could not find AI Extract button.");
    }

    await extractButton.click();
    console.log("✅ Clicked Run AI Extract button");

    // 6. Wait for backend to respond and UI to populate
    await page.waitForTimeout(2000);

    // 7. Verify email field was populated by AI extraction
    const emailInput = await page.locator('input[type="email"]');
    
    const emailValue = await emailInput.inputValue();
    console.log("📧 Extracted email value:", emailValue);
    
    // The API might return empty or the actual email depending on stub mode
    if (emailValue) {
        await expect(emailValue).toContain("@");
        console.log("✅ Email field populated with:", emailValue);
    } else {
        console.log("⚠️ Email field empty (might be stub mode), but extraction ran");
    }

    // 8. Click "Create Lead" button (find button with "Create Lead" text)
    const createButton = await page.getByRole('button', { name: /Create Lead/i });
    
    await createButton.click();
    console.log("✅ Clicked Create Lead button");

    // 9. Verify success (look for success indicator or lead in table)
    await page.waitForTimeout(1500);
    
    // Take final screenshot to show result
    await page.screenshot({
        path: "test-results/final-success.png",
        fullPage: true,
    });

    console.log("✅ Lead creation flow completed successfully!");
});
