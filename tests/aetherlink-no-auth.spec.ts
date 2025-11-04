import { test, expect } from "@playwright/test";

const APP_URL = "http://localhost:5173/?test=true";

test("AI Extract → Create Lead (no-auth mode)", async ({ page }) => {
    // 1. Open the app in test mode (bypasses Keycloak)
    await page.goto(APP_URL, { waitUntil: "networkidle" });

    // 2. Small grace period for React to mount
    await page.waitForTimeout(800);

    // 3. Open the create panel if it's collapsed
    // Adjust text to your actual button label
    const createPanelButton =
        (await page.$("text=Create New Lead")) ||
        (await page.$("text=with AI Extract")) ||
        (await page.$("text=AI Extract"));

    if (createPanelButton) {
        await createPanelButton.click();
        await page.waitForTimeout(400);
    }

    // 4. Find the textarea/input where we paste the messy lead text
    const textarea =
        (await page.$("textarea")) ||
        (await page.$('textarea[name="rawText"]')) ||
        (await page.$('textarea[id*="lead"]'));

    if (!textarea) {
        await page.screenshot({
            path: "test-results/no-textarea.png",
            fullPage: true,
        });
        throw new Error("Could not find the lead input textarea.");
    }

    const sampleText = `Sarah Chen
Director of Engineering @ TechStart Inc
sarah.chen@techstart.io
415-555-0199
Warm intro from Mike at CloudConf 2024`;

    await textarea.fill(sampleText);

    // 5. Click AI extract
    const extractButton =
        (await page.$("text=Run AI Extract")) ||
        (await page.$("text=AI Extract")) ||
        (await page.$("text=Extract"));

    if (!extractButton) {
        await page.screenshot({
            path: "test-results/no-extract-button.png",
            fullPage: true,
        });
        throw new Error("Could not find AI Extract button.");
    }

    await extractButton.click();

    // 6. Wait for backend to respond and UI to populate
    await page.waitForTimeout(1500);

    // 7. Read the email field
    const emailInput =
        (await page.$('input[name="email"]')) ||
        (await page.$('input[type="email"]')) ||
        (await page.$('input[placeholder*="email" i]'));

    if (!emailInput) {
        await page.screenshot({
            path: "test-results/no-email-input.png",
            fullPage: true,
        });
        throw new Error("Could not find email input to verify extraction.");
    }

    const emailValue = await emailInput.inputValue();
    await expect(emailValue).toContain("sarah.chen@techstart.io");

    console.log("✅ Email extracted successfully:", emailValue);

    // 8. Click Create Lead
    const createButton =
        (await page.$("text=Create Lead")) ||
        (await page.$("text=Save")) ||
        (await page.$("text=Add Lead"));

    if (!createButton) {
        await page.screenshot({
            path: "test-results/no-create-button.png",
            fullPage: true,
        });
        throw new Error("Could not find Create Lead button.");
    }

    await createButton.click();

    // 9. Verify lead shows up somewhere
    await page.waitForTimeout(1000);
    const bodyText = (await page.textContent("body")) || "";
    await expect(bodyText).toContain("Sarah Chen");

    console.log("✅ Lead created and verified in UI!");
});
