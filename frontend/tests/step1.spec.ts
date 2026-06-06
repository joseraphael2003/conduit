import { test, expect } from '@playwright/test';
import { apiBase } from "../src/config";
import { injectStyles } from './utils';

const mockTranscript = {
  transcript: 'Welcome to the tutorial. Let us begin with the basics.',
  word_count: 9,
};

const mockScript = 'Welcome to the tutorial. Let us start with the fundamentals.';

test.describe('Step 1 — Script', () => {
  test.beforeEach(async ({ page }) => {
    await page.route(apiBase + '/projects/**/state', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'created' }),
      });
    });

    await page.route(apiBase + '/projects/**/transcript', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(mockTranscript),
      });
    });

    await page.route(apiBase + '/projects/**/voiceover', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true }),
      });
    });
  });

  test('voiceover dropzone is visible', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const dropzone = page.locator('[data-testid="voiceover-dropzone"]');
    await expect(dropzone).toBeVisible();
    await page.screenshot({ path: 'test-results/step1-dropzone.png' });
  });

  test('transcript appears after mock API response', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const transcriptDisplay = page.locator('[data-testid="transcript-display"]');
    await expect(transcriptDisplay).toBeVisible();
    await expect(transcriptDisplay).toContainText('Welcome to the tutorial.');
    await page.screenshot({ path: 'test-results/step1-transcript.png' });
  });

  test('diff UI shows changes when script differs from transcript', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    // Open Original Script panel
    await page.locator('button', { hasText: 'Original Script' }).click();
    const scriptInput = page.locator('[data-testid="original-script-input"]');
    await expect(scriptInput).toBeVisible();

    // Type a different script
    await scriptInput.fill(mockScript);

    // Diff UI should appear
    const diffUi = page.locator('[data-testid="diff-ui"]');
    await expect(diffUi).toBeVisible();

    // At least one change block should be visible
    const changes = page.locator('[data-testid="diff-change"]');
    await expect(changes).toHaveCount(2);

    await page.screenshot({ path: 'test-results/step1-diff-ui.png' });
  });

  test('Next button is enabled when transcript is present, disabled when absent', async ({ page }) => {
    let projectState = 'created';

    await page.route(apiBase + '/projects/**/state', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: projectState }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const nextButton = page.locator('button', { hasText: 'Next' });

    // Enabled because transcript is present (even with state 'created')
    await expect(nextButton).toBeEnabled();
    await page.screenshot({ path: 'test-results/step1-next-enabled-with-transcript.png' });

    // Remove transcript and reload
    await page.unroute(apiBase + '/projects/**/transcript');
    await page.route(apiBase + '/projects/**/transcript', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    // Now disabled because no transcript
    await expect(nextButton).toBeDisabled();
    await page.screenshot({ path: 'test-results/step1-next-disabled-no-transcript.png' });
  });

  test('error banner shows retry button on API failure', async ({ page }) => {
    await page.route(apiBase + '/projects/**/transcript', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const retryButton = page.locator('button', { hasText: 'Retry' });
    await expect(retryButton).toBeVisible();
    await page.screenshot({ path: 'test-results/step1-error-retry.png' });
  });

  test('all buttons have border-radius 0px', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const buttons = page.locator('button');
    const count = await buttons.count();
    for (let i = 0; i < count; i++) {
      await expect(buttons.nth(i)).toHaveCSS('border-radius', '0px');
    }
    await page.screenshot({ path: 'test-results/step1-buttons-radius.png' });
  });

  test('headings use Playfair Display font', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await expect(page.locator('h1')).toHaveCSS('font-family', /Playfair Display/);
    await page.screenshot({ path: 'test-results/step1-heading-font.png' });
  });
});
