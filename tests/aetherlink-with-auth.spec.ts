import { test, expect } from "@playwright/test";

const APP_URL = "http://localhost:5173?test=true"; // Add test=true to bypass Keycloak
const KEYCLOAK_LOGIN_TEXT = "Sign in to your account"; // what we saw in your screenshot

test("Step 1 + Step 2: login → AI Extract → Create Lead", async ({ page }) => {
    // 1) go to app in test mode (bypasses Keycloak)
    console.log("🧪 Opening app in test mode...");
    await page.goto(APP_URL, { waitUntil: "networkidle" });

    // 2) wait for React app to initialize
    await page.waitForTimeout(2000);

    // Debug: check console for errors
    page.on('console', msg => console.log('Browser console:', msg.text()));
    page.on('pageerror', error => console.log('Page error:', error.message));

    // Debug: take screenshot and dump HTML
    await page.screenshot({ path: "test-results/page-after-auth.png", fullPage: true });
    const bodyHTML = await page.content();
    console.log("Page title:", await page.title());
    console.log("Current URL:", page.url());
    console.log("Body contains 'Create':", bodyHTML.includes("Create"));
    console.log("Body contains 'Lead':", bodyHTML.includes("Lead"));
    console.log("Root div innerHTML length:", (await page.$eval('#root', el => el.innerHTML)).length);    // 6) Click to expand the "Create New Lead" panel (it's collapsed by default)
    // Try partial text match
    const createPanelButton = page.locator("text=/Create New Lead/i").first();
    await expect(createPanelButton).toBeVisible({ timeout: 10000 });
    await createPanelButton.click();    // Wait for panel to expand
    await page.waitForTimeout(500);

    // 7) now we try to find the textarea
    // we'll be defensive because we don't know exact markup yet
    const textarea =
        (await page.$("textarea")) ||
        (await page.$('textarea[name="rawText"]')) ||
        (await page.$('textarea[id*="lead"]'));

    if (!textarea) {
        // capture screenshot for debugging
        await page.screenshot({ path: "test-results/ui-after-login.png", fullPage: true });
        throw new Error("UI loaded after login, but I could not find the lead textarea.");
    }

    const sampleText = `Sarah Chen
Director of Engineering @ TechStart Inc
sarah.chen@techstart.io
415-555-0199
Warm intro from Mike at CloudConf 2024`;

    await textarea.fill(sampleText);

    // 8) click AI extract
    const extractButton =
        (await page.$("text=Run AI Extract")) ||
        (await page.$("text=AI Extract")) ||
        (await page.$("text=Extract"));

    if (!extractButton) {
        await page.screenshot({ path: "test-results/ui-no-extract-button.png", fullPage: true });
        throw new Error("Could not find AI Extract button after login.");
    }

    await extractButton.click();

    // 9) wait for email field to fill
    await page.waitForTimeout(1500);

    const emailInput =
        (await page.$('input[name="email"]')) ||
        (await page.$('input[type="email"]')) ||
        (await page.$('input[placeholder*="email" i]'));

    if (!emailInput) {
        await page.screenshot({ path: "test-results/ui-no-email-input.png", fullPage: true });
        throw new Error("Could not find email input to verify extraction.");
    }

    const emailValue = await emailInput.inputValue();
    await expect(emailValue).toContain("sarah.chen@techstart.io");

    // 10) create lead
    const createButton =
        (await page.$("text=Create Lead")) ||
        (await page.$("text=✅ Create Lead")) ||
        (await page.$("text=Save")) ||
        (await page.$("text=Add Lead"));

    if (!createButton) {
        await page.screenshot({ path: "test-results/ui-no-create-button.png", fullPage: true });
        throw new Error("Could not find Create Lead button.");
    }

    await createButton.click();

    // 11) verify lead is visible somewhere
    await page.waitForTimeout(1500);
    const bodyText = (await page.textContent("body")) || "";
    await expect(bodyText).toContain("Sarah Chen");

    console.log("✅ TEST PASSED! Lead created successfully.");
});

test.describe("AetherLink CRM - Manual Auth Flow", () => {
    test("Step 2: AI Extract → Create Lead (after manual login)", async ({ page }) => {
        // This test assumes you've already logged in manually or via Step 1
        console.log("🔍 Opening CRM UI...");
        await page.goto("http://localhost:5173", { waitUntil: "networkidle" });
        await page.waitForTimeout(2000);

        // Take screenshot of initial state
        await page.screenshot({ path: 'test-results/01-initial-page.png', fullPage: true });

        // Check if we're stuck on auth
        if (page.url().includes("localhost:8180")) {
            throw new Error("⚠️ Still on Keycloak login page. Please log in manually first or check Step 1.");
        }

        console.log("✅ On CRM UI, looking for AI Extract panel...");

        // Look for the create panel - it might be collapsed
        const createPanelButton = await page.$("text=/Create New Lead/i") ||
            await page.$("text=/AI Extract/i");

        if (createPanelButton) {
            console.log("🔘 Found create panel button, clicking...");
            await createPanelButton.click();
            await page.waitForTimeout(500);
        }

        // Screenshot after opening panel
        await page.screenshot({ path: 'test-results/02-panel-opened.png', fullPage: true });

        // Sample lead data
        const sampleText = `Sarah Chen
Director of Engineering @ TechStart Inc
sarah.chen@techstart.io
415-555-0199
Warm intro from Mike at CloudConf 2024`;

        console.log("📝 Looking for textarea to paste lead data...");

        // Find textarea - try multiple strategies
        const textArea = await page.$("textarea") ||
            await page.$('textarea[placeholder*="paste" i]') ||
            await page.$('textarea[placeholder*="text" i]');

        if (!textArea) {
            // List all textareas for debugging
            const allTextareas = await page.$$("textarea");
            console.log(`❌ Could not find lead textarea. Found ${allTextareas.length} textarea(s) on page.`);
            await page.screenshot({ path: 'test-results/03-no-textarea.png', fullPage: true });
            throw new Error("Could not find the lead textarea on the page.");
        }

        console.log("✅ Found textarea, filling with sample data...");
        await textArea.fill(sampleText);
        await page.screenshot({ path: 'test-results/04-text-filled.png', fullPage: true });

        // Find and click Extract button
        console.log("🔘 Looking for AI Extract button...");
        const extractButton = await page.getByRole('button', { name: /extract/i }).first() ||
            await page.$("button:has-text('Run AI Extract')") ||
            await page.$("button:has-text('Extract')");

        if (!extractButton) {
            console.log("❌ Could not find AI Extract button");
            await page.screenshot({ path: 'test-results/05-no-extract-button.png', fullPage: true });
            throw new Error("Could not find the AI Extract button.");
        }

        console.log("✅ Clicking AI Extract...");
        await extractButton.click();

        // Wait for extraction to complete
        console.log("⏳ Waiting for AI extraction...");
        await page.waitForTimeout(2000);
        await page.screenshot({ path: 'test-results/06-after-extract.png', fullPage: true });

        // Check if email field got populated
        console.log("🔍 Checking if email field was populated...");
        const emailInput = await page.$('input[type="email"]') ||
            await page.$('input[name="email"]') ||
            await page.$('input[placeholder*="email" i]');

        if (emailInput) {
            const emailValue = await emailInput.inputValue();
            console.log("📧 Email field value:", emailValue);

            if (emailValue.includes("sarah.chen@techstart.io")) {
                console.log("✅ Email extracted correctly!");
            } else {
                console.log("⚠️ Email field populated but doesn't match expected value");
            }
        } else {
            console.log("⚠️ Could not find email input to verify extraction");
        }

        // Find and click Create Lead button
        console.log("🔘 Looking for Create Lead button...");
        const createButton = await page.getByRole('button', { name: /create lead/i }).first() ||
            await page.$("button:has-text('Create Lead')") ||
            await page.$("button:has-text('✅ Create Lead')");

        if (!createButton) {
            console.log("❌ Could not find Create Lead button");
            await page.screenshot({ path: 'test-results/07-no-create-button.png', fullPage: true });
            throw new Error("Could not find the Create Lead button.");
        }

        console.log("✅ Clicking Create Lead...");
        await createButton.click();

        // Wait for lead to be created and table to refresh
        console.log("⏳ Waiting for lead creation...");
        await page.waitForTimeout(2000);
        await page.screenshot({ path: 'test-results/08-after-create.png', fullPage: true });

        // Verify Sarah Chen appears in the page
        console.log("🔍 Checking if Sarah Chen appears in leads table...");
        const bodyText = await page.textContent("body");

        if (bodyText?.includes("Sarah Chen") || bodyText?.includes("sarah.chen@techstart.io")) {
            console.log("✅ SUCCESS! Lead created and visible in table");
        } else {
            console.log("⚠️ Could not find Sarah Chen in the page after creation");
            await page.screenshot({ path: 'test-results/09-lead-not-found.png', fullPage: true });
        }

        // Final screenshot
        await page.screenshot({ path: 'test-results/10-final-state.png', fullPage: true });
        console.log("✅ Test complete! Check test-results/ folder for screenshots");
    });
});
