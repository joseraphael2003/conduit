import { test, expect } from '@playwright/test';
import { apiBase } from "../src/config";
import { injectStyles } from './utils';

const mockSegments = [
  { segment_index: 0, script_line: 'Hello', segment_prompt: 'Test', characters_present: [], start_time: 0, end_time: 5 },
  { segment_index: 1, script_line: 'World', segment_prompt: 'Test2', characters_present: [], start_time: 5, end_time: 10 },
];

const mockSegmentsStep3 = [
  { segment_index: 0, script_line: 'Line 1', start_time: 0.0, end_time: 5.0, duration: 5.0, prompt: '', characters: ['Alice'] },
  { segment_index: 1, script_line: 'Line 2', start_time: 5.0, end_time: 10.0, duration: 5.0, prompt: '', characters: ['Bob'] },
];

const smallPngBase64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";
const smallPngBuffer = Buffer.from(smallPngBase64, 'base64');

test.describe('Accessibility Gap Verification', () => {
  test('Step1Script — error banner has role="alert" and aria-live="assertive"', async ({ page }) => {
    await page.route(apiBase + '/projects/**/transcript', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Server error' }) });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const banner = page.locator('[role="alert"]').first();
    await expect(banner).toBeVisible();
    await expect(banner).toHaveAttribute('aria-live', 'assertive');
  });

  test('Step1Script — Original Script toggle has aria-expanded and aria-controls', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const toggle = page.locator('button', { hasText: 'Original Script' });
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(toggle).toHaveAttribute('aria-controls', 'original-script-panel');
  });

  test('Step1Script — dropzone is keyboard accessible', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const dropzone = page.locator('[data-testid="voiceover-dropzone"]');
    await expect(dropzone).toHaveAttribute('tabindex', '0');
    await expect(dropzone).toHaveAttribute('role', 'button');
    await expect(dropzone).toHaveAttribute('aria-label', 'Upload voiceover file');
  });

  test('Step2Characters — error banner has role="alert" and aria-live="assertive"', async ({ page }) => {
    await page.route(apiBase + '/projects/**/characters/extract', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Server error' }) });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/2');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForTimeout(300);

    const banner = page.locator('[role="alert"]').first();
    await expect(banner).toBeVisible();
    await expect(banner).toHaveAttribute('aria-live', 'assertive');
  });

  test('Step2Characters — JSON toggle has aria-expanded and aria-controls', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/2');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.route(apiBase + '/projects/**/characters/extract', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ characters: [{ name: 'Alice', type: 'main', importance: 'main', description: 'Test', front_profile_prompt: 'prompt', turnaround_reference_prompt: 'turn' }] }) });
    });
    await page.route(apiBase + '/projects/**/characters', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) });
    });
    await page.route(apiBase + '/projects/**/characters/prompts', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ characters: [{ name: 'Alice', type: 'main', importance: 'main', description: 'Test', front_profile_prompt: 'prompt', turnaround_reference_prompt: 'turn' }] }) });
    });

    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForTimeout(300);

    // Edit to enable generate button
    const textarea = page.locator('table tbody tr:first-child textarea');
    await textarea.fill('Updated');

    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForTimeout(300);

    const jsonToggle = page.locator('button[aria-label="Toggle JSON"]').first();
    await expect(jsonToggle).toHaveAttribute('aria-expanded', 'false');
    await expect(jsonToggle).toHaveAttribute('aria-controls', 'json-panel-Alice');
  });

  test('Step3Segments — error banner has role="alert" and aria-live="assertive"', async ({ page }) => {
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found' }) });
    });
    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Server error' }) });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/3');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForTimeout(300);

    const banner = page.locator('[role="alert"]').first();
    await expect(banner).toBeVisible();
    await expect(banner).toHaveAttribute('aria-live', 'assertive');
  });

  test('Step3Segments — success banner has role="alert" and aria-live="assertive"', async ({ page }) => {
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found' }) });
    });
    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.route(apiBase + '/projects/test-uuid/segments/prompts', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/3');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForTimeout(300);
    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForTimeout(300);

    const banner = page.locator('[role="alert"]').first();
    await expect(banner).toBeVisible();
    await expect(banner).toHaveAttribute('aria-live', 'assertive');
    await expect(banner).toContainText('Prompts generated successfully');
  });

  test('Step4Images — error banner has role="alert" and aria-live="assertive"', async ({ page }) => {
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegments }) });
    });
    await page.route(apiBase + '/projects/test-uuid/images/**', async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found' }) });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/4');
    await page.waitForLoadState('networkidle');

    // Trigger an error by uploading a non-PNG file
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('[data-testid="upload-button"]').first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({ name: 'test.txt', mimeType: 'text/plain', buffer: Buffer.from('not an image') });
    await page.waitForTimeout(300);

    const banner = page.locator('[role="alert"]').first();
    await expect(banner).toBeVisible();
    await expect(banner).toHaveAttribute('aria-live', 'assertive');
  });

  test('Step4Images — modal traps focus and returns focus on close', async ({ page }) => {
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegments }) });
    });
    await page.route(apiBase + '/projects/test-uuid/images/**', async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found' }) });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/4');
    await page.waitForLoadState('networkidle');

    const detailsButton = page.locator('[data-testid="details-button"]').first();
    await detailsButton.click();

    const modal = page.locator('[data-testid="details-modal"]');
    await expect(modal).toBeVisible();
    await expect(modal).toHaveAttribute('role', 'dialog');
    await expect(modal).toHaveAttribute('aria-modal', 'true');

    // Tab 10 times and check focus never leaves modal
    for (let i = 0; i < 10; i++) {
      await page.keyboard.press('Tab');
      const activeInModal = await page.evaluate(() => {
        const modalEl = document.querySelector('[data-testid="details-modal"]');
        if (!modalEl) return false;
        const active = document.activeElement;
        return modalEl.contains(active);
      });
      expect(activeInModal).toBe(true);
    }

    // Press Escape to close
    await page.keyboard.press('Escape');
    await expect(modal).toBeHidden();

    // Focus should return to trigger button
    await expect(detailsButton).toBeFocused();
  });

  test('Step5Video — error banner has role="alert" and aria-live="assertive"', async ({ page }) => {
    await page.route(apiBase + '/projects/**/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.route(apiBase + '/projects/**/images/**', async route => {
      if (route.request().url().includes('/images/status')) {
        return route.fallback();
      }
      await route.fulfill({ status: 200, contentType: 'image/png', body: smallPngBuffer });
    });
    await page.route(apiBase + '/projects/**/images/status', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ "0": true, "1": true }) });
    });
    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'FFmpeg failed' }) });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('[data-testid="generate-video-button"]').click();
    await page.waitForTimeout(500);

    const banner = page.locator('[role="alert"]').first();
    await expect(banner).toBeVisible();
    await expect(banner).toHaveAttribute('aria-live', 'assertive');
  });

  test('Step5Video — progress bar has role="progressbar" and ARIA values', async ({ page }) => {
    await page.route(apiBase + '/projects/**/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.route(apiBase + '/projects/**/images/**', async route => {
      if (route.request().url().includes('/images/status')) {
        return route.fallback();
      }
      await route.fulfill({ status: 200, contentType: 'image/png', body: smallPngBuffer });
    });
    await page.route(apiBase + '/projects/**/images/status', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ "0": true, "1": true }) });
    });
    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await new Promise(resolve => setTimeout(resolve, 500));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ output_path: 'output.mp4', duration: 10 }) });
    });
    await page.route(apiBase + '/projects/**/video/status', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'processing', current_segment: 1, total_segments: 2, message: 'Processing segment 1' }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('[data-testid="generate-video-button"]').click();
    await page.waitForTimeout(300);

    const progressBar = page.locator('[data-testid="progress-bar"]');
    await expect(progressBar).toHaveAttribute('role', 'progressbar');
    await expect(progressBar).toHaveAttribute('aria-label', 'Video generation progress');
    await expect(progressBar).toHaveAttribute('aria-valuenow', /.*/);
    await expect(progressBar).toHaveAttribute('aria-valuemax', /.*/);
  });

  test('Step5Video — Console toggle has aria-expanded and aria-controls', async ({ page }) => {
    await page.route(apiBase + '/projects/**/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.route(apiBase + '/projects/**/images/**', async route => {
      if (route.request().url().includes('/images/status')) {
        return route.fallback();
      }
      await route.fulfill({ status: 200, contentType: 'image/png', body: smallPngBuffer });
    });
    await page.route(apiBase + '/projects/**/images/status', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ "0": true, "1": true }) });
    });
    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await new Promise(resolve => setTimeout(resolve, 500));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ output_path: 'output.mp4', duration: 10 }) });
    });
    await page.route(apiBase + '/projects/**/video/status', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'processing', current_segment: 1, total_segments: 2, message: 'Processing segment 1' }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('[data-testid="generate-video-button"]').click();
    await page.waitForTimeout(300);

    const toggle = page.locator('[data-testid="console-toggle"]');
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(toggle).toHaveAttribute('aria-controls', 'console-output-panel');
  });

  test('Total role="alert" count across all pages = 6', async ({ page }) => {
    let count = 0;

    // Step 1 error
    await page.route(apiBase + '/projects/**/transcript', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Server error' }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    count += await page.locator('[role="alert"]').count();

    // Step 2 error
    await page.route(apiBase + '/projects/**/characters/extract', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Server error' }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid/step/2');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForTimeout(300);
    count += await page.locator('[role="alert"]').count();

    // Step 3 error
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found' }) });
    });
    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Server error' }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid/step/3');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForTimeout(300);
    count += await page.locator('[role="alert"]').count();

    // Step 3 success
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found' }) });
    });
    await page.route(apiBase + '/projects/test-uuid/segments/breakdown', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.route(apiBase + '/projects/test-uuid/segments/prompts', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid/step/3');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForTimeout(300);
    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForTimeout(300);
    count += await page.locator('[role="alert"]').count();

    // Step 4 error
    await page.route(apiBase + '/projects/test-uuid/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegments }) });
    });
    await page.route(apiBase + '/projects/test-uuid/images/**', async route => {
      await route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ detail: 'Not found' }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid/step/4');
    await page.waitForLoadState('networkidle');
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('[data-testid="upload-button"]').first().click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({ name: 'test.txt', mimeType: 'text/plain', buffer: Buffer.from('not an image') });
    await page.waitForTimeout(300);
    count += await page.locator('[role="alert"]').count();

    // Step 5 error
    await page.route(apiBase + '/projects/**/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.route(apiBase + '/projects/**/images/**', async route => {
      if (route.request().url().includes('/images/status')) {
        return route.fallback();
      }
      await route.fulfill({ status: 200, contentType: 'image/png', body: smallPngBuffer });
    });
    await page.route(apiBase + '/projects/**/images/status', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ "0": true, "1": true }) });
    });
    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'FFmpeg failed' }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await page.locator('[data-testid="generate-video-button"]').click();
    await page.waitForTimeout(500);
    count += await page.locator('[role="alert"]').count();

    expect(count).toBe(6);
  });

  test('Total [aria-expanded] count across all pages = 3', async ({ page }) => {
    let count = 0;

    // Step 1
    await page.goto('http://localhost:5173/project/test-uuid/step/1');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    count += await page.locator('[aria-expanded]').count();

    // Step 2
    await page.route(apiBase + '/projects/**/characters/extract', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ characters: [{ name: 'Alice', type: 'main', importance: 'main', description: 'Test', front_profile_prompt: 'prompt', turnaround_reference_prompt: 'turn' }] }) });
    });
    await page.route(apiBase + '/projects/**/characters', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true }) });
    });
    await page.route(apiBase + '/projects/**/characters/prompts', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ characters: [{ name: 'Alice', type: 'main', importance: 'main', description: 'Test', front_profile_prompt: 'prompt', turnaround_reference_prompt: 'turn' }] }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid/step/2');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForTimeout(300);
    const textarea = page.locator('table tbody tr:first-child textarea');
    await textarea.fill('Updated');
    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForTimeout(300);
    count += await page.locator('[aria-expanded]').count();

    // Step 5
    await page.route(apiBase + '/projects/**/segments', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ segments: mockSegmentsStep3 }) });
    });
    await page.route(apiBase + '/projects/**/images/**', async route => {
      if (route.request().url().includes('/images/status')) {
        return route.fallback();
      }
      await route.fulfill({ status: 200, contentType: 'image/png', body: smallPngBuffer });
    });
    await page.route(apiBase + '/projects/**/images/status', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ "0": true, "1": true }) });
    });
    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await new Promise(resolve => setTimeout(resolve, 500));
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ output_path: 'output.mp4', duration: 10 }) });
    });
    await page.route(apiBase + '/projects/**/video/status', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'processing', current_segment: 1, total_segments: 2, message: 'Processing segment 1' }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await page.locator('[data-testid="generate-video-button"]').click();
    await page.waitForTimeout(300);
    count += await page.locator('[aria-expanded]').count();

    expect(count).toBe(3);
  });
});
