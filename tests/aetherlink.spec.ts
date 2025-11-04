import { test, expect } from "@playwright/test";

test("AI Extract → Create Lead flow", async ({ page }) => {
    // 1. open your app
    await page.goto("http://localhost:5173", { waitUntil: "networkidle" });

    // 2. wait for page to render
    await page.waitForTimeout(1000);

    // NOTE:
    // The selectors below are guesses based on your description.
    // If your textarea or buttons have slightly different text,
    // we can tweak them after the first run.

    // 3. fill in the raw text / lead input
    const sampleText = `Sarah Chen
Director of Engineering @ TechStart Inc
sarah.chen@techstart.io
415-555-0199
Warm intro from Mike at CloudConf 2024`;

    // try a few common selectors
    const textArea =
        (await page.$("textarea")) ||
        (await page.$('textarea[name="rawText"]')) ||
        (await page.$('textarea[id*="lead"]'));

    if (!textArea) {
        throw new Error("Could not find the lead textarea on the page.");
    }

    await textArea.fill(sampleText);

    // 4. click the AI extract button
    // adjust the text here to match your UI if needed
    const extractButton =
        (await page.$("text=Run AI Extract")) ||
        (await page.$("text=AI Extract")) ||
        (await page.$("text=Extract"));

    if (!extractButton) {
        throw new Error("Could not find the AI Extract button on the page.");
    }

    await extractButton.click();

    // 5. wait a bit for backend to respond and UI to populate
    await page.waitForTimeout(1500);

    // 6. check that the email field got populated
    // again, adjust the selector if your input is named differently
    const emailInput =
        (await page.$('input[name="email"]')) ||
        (await page.$('input[type="email"]')) ||
        (await page.$('input[placeholder*="email" i]'));

    if (!emailInput) {
        throw new Error("Could not find the email input to verify extraction.");
    }

    const emailValue = await emailInput.inputValue();
    await expect(emailValue).toContain("sarah.chen@techstart.io");

    // 7. click Create Lead
    const createButton =
        (await page.$("text=Create Lead")) ||
        (await page.$("text=Save")) ||
        (await page.$("text=Add Lead"));

    if (!createButton) {
        throw new Error("Could not find the Create Lead button.");
    }

    await createButton.click();

    // 8. wait for table/list to refresh
    await page.waitForTimeout(1500);

    // 9. assert the new lead shows up somewhere on the page
    const bodyText = await page.textContent("body");
    await expect(bodyText || "").toContain("Sarah Chen");
});
