import { test, expect } from '@playwright/test';

const mockTranscript = {
  transcript: 'Welcome to the tutorial. Let us begin with the basics.',
  word_count: 9,
};

async function injectStyles(page: any) {
  await page.addStyleTag({
    content: `
      .font-headline { font-family: 'Playfair Display', serif; }
      .font-body { font-family: 'Source Sans 3', sans-serif; }
      .font-mono { font-family: 'JetBrains Mono', monospace; }
    `,
  });
}

test.describe('Step 1 — Fidelity & Auto-Approve', () => {
  test.beforeEach(async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/state', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'created' }),
      });
    });
  });

  test('Auto-Approve button approves all remaining changes', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockTranscript),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    // Open Original Script panel and type a different script
    await page.locator('button', { hasText: 'Original Script' }).click();
    const scriptInput = page.locator('[data-testid="original-script-input"]');
    await expect(scriptInput).toBeVisible();
    await scriptInput.fill('Welcome to the tutorial. Let us start with the fundamentals.');

    // Diff UI should appear
    const diffUi = page.locator('[data-testid="diff-ui"]');
    await expect(diffUi).toBeVisible();

    // Approve Remaining button should be visible and enabled
    const approveRemaining = page.locator('[data-testid="approve-remaining"]');
    await expect(approveRemaining).toBeVisible();
    await expect(approveRemaining).toBeEnabled();

    // Click Approve Remaining
    await approveRemaining.click();

    // All diff blocks should be approved
    const approveButtons = page.locator('[data-testid="approve-button"]');
    const count = await approveButtons.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      await expect(approveButtons.nth(i)).toHaveText('Approved');
    }

    // Approve Remaining button should now be disabled
    await expect(approveRemaining).toBeDisabled();
  });

  test('Fidelity badge is visible and shows correct percentage', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ transcript: 'Hello world', word_count: 2 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    // Open Original Script panel and type identical script
    await page.locator('button', { hasText: 'Original Script' }).click();
    const scriptInput = page.locator('[data-testid="original-script-input"]');
    await expect(scriptInput).toBeVisible();
    await scriptInput.fill('Hello world');

    // Fidelity badge should be visible
    const badge = page.locator('[data-testid="fidelity-badge"]');
    await expect(badge).toBeVisible();
    await expect(badge).toContainText('100%');

    // Badge should have green color for >= 95% fidelity
    await expect(badge).toHaveCSS('color', 'rgb(34, 197, 94)');
  });

  test('Fidelity badge color changes based on fidelity level', async ({ page }) => {
    // Low fidelity: transcript and script have no common words
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ transcript: 'Hello world', word_count: 2 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Original Script' }).click();
    const scriptInput = page.locator('[data-testid="original-script-input"]');
    await expect(scriptInput).toBeVisible();
    await scriptInput.fill('Completely different text here');

    const badge = page.locator('[data-testid="fidelity-badge"]');
    await expect(badge).toBeVisible();
    await expect(badge).toHaveCSS('color', 'rgb(239, 68, 68)');

    // Medium fidelity: 9 out of 10 words match
    await page.unroute('http://localhost:8000/api/v1/projects/**/transcript');
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ transcript: 'A B C D E F G H I J', word_count: 10 }),
      });
    });

    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Original Script' }).click();
    await scriptInput.fill('A B C D E F G H I X');

    await expect(badge).toBeVisible();
    await expect(badge).toHaveCSS('color', 'rgb(234, 179, 8)');
  });

  test('Next button is enabled when transcript is present, disabled when absent', async ({ page }) => {
    // With transcript present
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockTranscript),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const nextButton = page.locator('button', { hasText: 'Next' });

    // Enabled because transcript is present (even with backend state 'created')
    await expect(nextButton).toBeEnabled();

    // Without transcript
    await page.unroute('http://localhost:8000/api/v1/projects/**/transcript');
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await expect(nextButton).toBeDisabled();
  });

  test('Warning modal appears for low fidelity and can close', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ transcript: 'A B C D E F G H I J', word_count: 10 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    // Open Original Script and type a slightly different script (90% fidelity)
    await page.locator('button', { hasText: 'Original Script' }).click();
    const scriptInput = page.locator('[data-testid="original-script-input"]');
    await expect(scriptInput).toBeVisible();
    await scriptInput.fill('A B C D E F G H I X');

    // Click Next
    const nextButton = page.locator('button', { hasText: 'Next' });
    await expect(nextButton).toBeEnabled();
    await nextButton.click();

    // Warning modal should appear
    const modal = page.locator('[data-testid="warning-modal"]');
    await expect(modal).toBeVisible();
    await expect(modal).toContainText('90%');

    // Click Continue Reviewing
    await page.locator('[data-testid="continue-reviewing"]').click();

    // Modal should close and still be on Step 1
    await expect(modal).not.toBeVisible();
    await expect(page.locator('span', { hasText: 'Step 1 of 5' })).toBeVisible();
  });

  test('Warning modal Review Anyway proceeds to Step 2', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ transcript: 'A B C D E F G H I J', word_count: 10 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Original Script' }).click();
    const scriptInput = page.locator('[data-testid="original-script-input"]');
    await expect(scriptInput).toBeVisible();
    await scriptInput.fill('A B C D E F G H I X');

    const nextButton = page.locator('button', { hasText: 'Next' });
    await expect(nextButton).toBeEnabled();
    await nextButton.click();

    const modal = page.locator('[data-testid="warning-modal"]');
    await expect(modal).toBeVisible();

    await page.locator('[data-testid="review-anyway"]').click();

    await expect(modal).not.toBeVisible();
    await expect(page.locator('span', { hasText: 'Step 2 of 5' })).toBeVisible();
  });

  test('No warning modal for high fidelity and proceeds to Step 2', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ transcript: 'Hello world', word_count: 2 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Original Script' }).click();
    const scriptInput = page.locator('[data-testid="original-script-input"]');
    await expect(scriptInput).toBeVisible();
    await scriptInput.fill('Hello world');

    const nextButton = page.locator('button', { hasText: 'Next' });
    await expect(nextButton).toBeEnabled();
    await nextButton.click();

    const modal = page.locator('[data-testid="warning-modal"]');
    await expect(modal).not.toBeVisible();
    await expect(page.locator('span', { hasText: 'Step 2 of 5' })).toBeVisible();
  });
});
