import { test, expect } from '@playwright/test';

test.describe('Command Center UI Tests', () => {
    test.beforeEach(async ({ page }) => {
        // Navigate to the application
        await page.goto('/');
    });

    test('should load the main command center page', async ({ page }) => {
        // Check that the page title is present
        await expect(page.locator('h1').filter({ hasText: 'AetherLink Command Center' })).toBeVisible();
    });

    test('should display role selector', async ({ page }) => {
        // Check that role selector is present
        const roleSelector = page.locator('select').first();
        await expect(roleSelector).toBeVisible();

        // Check that it has the expected options
        await expect(page.locator('option').filter({ hasText: 'Select Role' })).toBeVisible();
        await expect(page.locator('option').filter({ hasText: 'Operator' })).toBeVisible();
        await expect(page.locator('option').filter({ hasText: 'Manager' })).toBeVisible();
        await expect(page.locator('option').filter({ hasText: 'Admin' })).toBeVisible();
    });

    test('should switch to operator dashboard', async ({ page }) => {
        // Select operator role
        await page.locator('select').first().selectOption('operator');

        // Check that operator dashboard is displayed
        await expect(page.locator('h2').filter({ hasText: 'Operator Dashboard' })).toBeVisible();
    });

    test('should display delivery history table', async ({ page }) => {
        // Select operator role
        await page.locator('select').first().selectOption('operator');

        // Check that delivery history table is present
        await expect(page.locator('table')).toBeVisible();

        // Check table headers
        await expect(page.locator('th').filter({ hasText: 'ID' })).toBeVisible();
        await expect(page.locator('th').filter({ hasText: 'Tenant' })).toBeVisible();
        await expect(page.locator('th').filter({ hasText: 'Status' })).toBeVisible();
        await expect(page.locator('th').filter({ hasText: 'Timestamp' })).toBeVisible();
    });

    test('should filter deliveries by tenant', async ({ page }) => {
        // Select operator role
        await page.locator('select').first().selectOption('operator');

        // Wait for deliveries to load
        await page.waitForTimeout(1000);

        // Check that tenant filter is present
        const tenantFilter = page.locator('select').nth(1);
        await expect(tenantFilter).toBeVisible();

        // Get initial row count
        const initialRows = await page.locator('tbody tr').count();

        // Select a specific tenant if available
        const tenantOptions = await tenantFilter.locator('option').allTextContents();
        if (tenantOptions.length > 1) {
            await tenantFilter.selectOption(tenantOptions[1]);
            await page.waitForTimeout(500);

            // Check that filtering worked (rows should be less or equal)
            const filteredRows = await page.locator('tbody tr').count();
            expect(filteredRows).toBeLessThanOrEqual(initialRows);
        }
    });

    test('should filter deliveries by status', async ({ page }) => {
        // Select operator role
        await page.locator('select').first().selectOption('operator');

        // Wait for deliveries to load
        await page.waitForTimeout(1000);

        // Check that status filter is present
        const statusFilter = page.locator('select').nth(2);
        await expect(statusFilter).toBeVisible();

        // Get initial row count
        const initialRows = await page.locator('tbody tr').count();

        // Select a specific status if available
        const statusOptions = await statusFilter.locator('option').allTextContents();
        if (statusOptions.length > 1) {
            await statusFilter.selectOption(statusOptions[1]);
            await page.waitForTimeout(500);

            // Check that filtering worked (rows should be less or equal)
            const filteredRows = await page.locator('tbody tr').count();
            expect(filteredRows).toBeLessThanOrEqual(initialRows);
        }
    });

    test('should persist filter preferences in localStorage', async ({ page }) => {
        // Select operator role
        await page.locator('select').first().selectOption('operator');

        // Wait for deliveries to load
        await page.waitForTimeout(1000);

        // Set filters
        const tenantFilter = page.locator('select').nth(1);
        const statusFilter = page.locator('select').nth(2);

        const tenantOptions = await tenantFilter.locator('option').allTextContents();
        const statusOptions = await statusFilter.locator('option').allTextContents();

        if (tenantOptions.length > 1) {
            await tenantFilter.selectOption(tenantOptions[1]);
        }
        if (statusOptions.length > 1) {
            await statusFilter.selectOption(statusOptions[1]);
        }

        // Wait for localStorage to be updated
        await page.waitForTimeout(500);

        // Check localStorage
        const storageData: { selectedTenant: string | null; selectedStatus: string | null } = await page.evaluate(() => {
            return {
                selectedTenant: localStorage.getItem('selectedTenant'),
                selectedStatus: localStorage.getItem('selectedStatus')
            };
        });

        if (tenantOptions.length > 1) {
            expect(storageData.selectedTenant).toBe(tenantOptions[1]);
        }
        if (statusOptions.length > 1) {
            expect(storageData.selectedStatus).toBe(statusOptions[1]);
        }
    });

    test('should switch to manager dashboard', async ({ page }) => {
        // Select manager role
        await page.locator('select').first().selectOption('manager');

        // Check that manager dashboard is displayed
        await expect(page.locator('h2').filter({ hasText: 'Manager Dashboard' })).toBeVisible();
    });

    test('should switch to admin dashboard', async ({ page }) => {
        // Select admin role
        await page.locator('select').first().selectOption('admin');

        // Check that admin dashboard is displayed
        await expect(page.locator('h2').filter({ hasText: 'Admin Dashboard' })).toBeVisible();
    });

    test('should display real-time event stream', async ({ page }) => {
        // Select operator role
        await page.locator('select').first().selectOption('operator');

        // Check that event stream section is present
        await expect(page.locator('h3').filter({ hasText: 'Real-time Events' })).toBeVisible();
    });
});