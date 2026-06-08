import { test, expect } from '@playwright/test';
import { apiBase } from "../src/config";
import { injectStyles } from './utils';

test.describe('Step 3 - Segments', () => {
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
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
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
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
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

    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
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
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
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
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.locator('button', { hasText: 'Retry' }).waitFor();

    const retryButton = page.locator('button', { hasText: 'Retry' });
    await expect(retryButton).toBeVisible();
    await page.screenshot({ path: 'test-results/step3-error-retry.png' });
  });

  test('Generate Prompts button appears after breakdown', async ({ page }) => {
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
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

  test('Version dropdown renders for multi-version character', async ({ page }) => {
    const mockCharactersWithVersions = [
      {
        name: 'Alice',
        base_name: 'Alice',
        type: 'speaking',
        importance: 'major',
        description: 'A curious explorer.',
        version_label: 'default',
        version_index: 0,
        appears_from: '00:00:00',
        identity_anchor: 'Blonde hair, blue eyes.',
      },
      {
        name: 'Alice (v2)',
        base_name: 'Alice',
        type: 'speaking',
        importance: 'major',
        description: 'A curious explorer in a dark cave.',
        version_label: 'dark cave',
        version_index: 1,
        appears_from: '00:05:00',
        identity_anchor: 'Blonde hair, blue eyes.',
      },
    ];

    await page.route(apiBase + '/projects/test-uuid/characters', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ characters: mockCharactersWithVersions }),
      });
    });

    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          segments: [
            { segment_index: 0, script_line: 'Line 1', start_time: 0.0, end_time: 5.0, duration: 5.0, prompt: '', characters: ['Alice'], characters_present: ['Alice'] },
          ],
        }),
      });
    });

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForSelector('table tbody tr');

    const select = page.locator('select');
    await expect(select).toBeVisible();
    await expect(select).toHaveCount(1);

    const options = select.locator('option');
    await expect(options).toHaveCount(2);
    await expect(options.nth(0)).toHaveText('Alice');
    await expect(options.nth(1)).toHaveText('Alice (v2)');

    await page.screenshot({ path: 'test-results/step3-version-dropdown.png' });
  });

  test('Regenerate button exists for each segment', async ({ page }) => {
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({
        status: 404,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not found' }),
      });
    });

    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
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

    const regenerateButtons = page.locator('button', { hasText: 'Regenerate' });
    await expect(regenerateButtons).toHaveCount(2);

    await page.screenshot({ path: 'test-results/step3-regenerate-buttons.png' });
  });
});
