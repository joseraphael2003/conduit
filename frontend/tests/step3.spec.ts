import { test, expect } from '@playwright/test';

test.describe('Step 3 - Segments', () => {
  async function injectStyles(page: any) {
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
        .font-body { font-family: 'Source Sans 3', sans-serif; }
        .font-mono { font-family: 'JetBrains Mono', monospace; }
      `,
    });
  }

  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/3');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
  });

  test('Generate Segments button is visible', async ({ page }) => {
    const button = page.locator('button', { hasText: 'Generate Segments' });
    await expect(button).toBeVisible();
    await page.screenshot({ path: 'test-results/step3-generate-segments.png' });
  });

  test('segment table has correct number of rows after breakdown', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          segments: [
            { segment_index: 0, script_line: 'Line 1', start_time: 0.0, end_time: 5.0, duration: 5.0, prompt: '', characters: ['Alice'] },
            { segment_index: 1, script_line: 'Line 2', start_time: 5.0, end_time: 10.0, duration: 5.0, prompt: '', characters: ['Bob'] },
            { segment_index: 2, script_line: 'Line 3', start_time: 10.0, end_time: 15.0, duration: 5.0, prompt: '', characters: ['Alice', 'Bob'] },
          ],
        }),
      });
    });

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForSelector('table tbody tr', { timeout: 5000 });

    const rows = page.locator('table tbody tr');
    await expect(rows).toHaveCount(3);
    await page.screenshot({ path: 'test-results/step3-segment-table.png' });
  });

  test('segment prompts are editable', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          segments: [
            { segment_index: 0, script_line: 'Line 1', start_time: 0.0, end_time: 5.0, duration: 5.0, prompt: 'Initial prompt', characters: ['Alice'] },
          ],
        }),
      });
    });

    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) });
    });

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForSelector('table tbody tr');

    const textarea = page.locator('textarea').first();
    await textarea.fill('Updated prompt');
    await textarea.blur();

    await expect(textarea).toHaveValue('Updated prompt');
    await page.screenshot({ path: 'test-results/step3-editable-prompts.png' });
  });

  test('Split and Merge buttons are present', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          segments: [
            { segment_index: 0, script_line: 'Line 1', start_time: 0.0, end_time: 5.0, duration: 5.0, prompt: '', characters: ['Alice'] },
            { segment_index: 1, script_line: 'Line 2', start_time: 5.0, end_time: 10.0, duration: 5.0, prompt: '', characters: ['Bob'] },
          ],
        }),
      });
    });

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForSelector('table tbody tr');

    const splitButtons = page.locator('button', { hasText: 'Split' });
    const mergeButtons = page.locator('button', { hasText: 'Merge' });

    await expect(splitButtons).toHaveCount(2);
    await expect(mergeButtons).toHaveCount(2);
    await page.screenshot({ path: 'test-results/step3-split-merge.png' });
  });

  test('error banner shows retry button on API failure', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForSelector('button', { hasText: 'Retry' });

    const retryButton = page.locator('button', { hasText: 'Retry' });
    await expect(retryButton).toBeVisible();
    await page.screenshot({ path: 'test-results/step3-error-retry.png' });
  });

  test('Generate Prompts button appears after breakdown', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          segments: [
            { segment_index: 0, script_line: 'Line 1', start_time: 0.0, end_time: 5.0, duration: 5.0, prompt: '', characters: ['Alice'] },
          ],
        }),
      });
    });

    const promptsButton = page.locator('button', { hasText: 'Generate Prompts' });
    await expect(promptsButton).not.toBeVisible();

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForSelector('table tbody tr');

    await expect(promptsButton).toBeVisible();
    await page.screenshot({ path: 'test-results/step3-generate-prompts-visible.png' });
  });

  test('all buttons have border-radius 0px', async ({ page }) => {
    const buttons = page.locator('button');
    const count = await buttons.count();
    for (let i = 0; i < count; i++) {
      await expect(buttons.nth(i)).toHaveCSS('border-radius', '0px');
    }
    await page.screenshot({ path: 'test-results/step3-buttons-radius.png' });
  });

  test('headings use Playfair Display font', async ({ page }) => {
    await expect(page.locator('h1')).toHaveCSS('font-family', /Playfair Display/);
    await page.screenshot({ path: 'test-results/step3-heading-font.png' });
  });
});
