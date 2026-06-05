import { test, expect } from '@playwright/test';
import { apiBase } from "../src/config";

const mockSegments = [
  {
    segment_index: 0,
    script_line: 'Welcome to the tutorial.',
    start_time: 0,
    end_time: 5.2,
    duration: 5.2,
    effect: 'none',
  },
  {
    segment_index: 1,
    script_line: 'Let us begin with the basics.',
    start_time: 5.2,
    end_time: 12.8,
    duration: 7.6,
    effect: 'none',
  },
  {
    segment_index: 2,
    script_line: 'Now we move to advanced topics.',
    start_time: 12.8,
    end_time: 20.0,
    duration: 7.2,
    effect: 'none',
  },
];

async function injectStyles(page: any) {
  await page.addStyleTag({
    content: `
      .font-headline { font-family: 'Playfair Display', serif; }
      .font-body { font-family: 'Source Sans 3', sans-serif; }
      .font-mono { font-family: 'JetBrains Mono', monospace; }
    `,
  });
}

test.describe('Step 5 — Video Generation', () => {
  test.beforeEach(async ({ page }) => {
    await page.route(apiBase + '/projects/**/state', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'step_4_complete' }),
      });
    });

    await page.route(apiBase + '/projects/**/segments', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ segments: mockSegments }),
      });
    });

    await page.route(
      apiBase + '/projects/**/images/**',
      async route => {
        await route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Not found' }),
        });
      }
    );

    await page.route(apiBase + '/projects/**/video/srt', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/octet-stream',
        body: '1\n00:00:00,000 --> 00:00:05,000\nWelcome to the tutorial.',
      });
    });
  });

  test('effect grid is visible', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const grid = page.locator('[data-testid="effect-selection-grid"]');
    await expect(grid).toBeVisible();

    // Should have segment cards
    const selects = page.locator('select');
    await expect(selects).toHaveCount(mockSegments.length);

    await page.screenshot({ path: 'test-results/step5-effect-grid.png' });
  });

  test('Randomize button works', async ({ page }) => {
    const putEffects: { index: number; effect: string }[] = [];

    await page.route(apiBase + '/projects/**/segments/**/effect', async route => {
      const url = route.request().url();
      const index = parseInt(url.split('/').slice(-2)[0], 10);
      const body = await route.request().postDataJSON();
      putEffects.push({ index, effect: body.effect });
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ segment_index: index, effect: body.effect }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const randomizeButton = page.locator('[data-testid="randomize-button"]');
    await expect(randomizeButton).toBeVisible();
    await expect(randomizeButton).toBeEnabled();

    await randomizeButton.click();
    await page.waitForTimeout(500);

    // Should have sent PUT requests for each segment
    await expect(putEffects.length).toBeGreaterThanOrEqual(mockSegments.length);
    await page.screenshot({ path: 'test-results/step5-randomize.png' });
  });

  test('Burn captions checkbox is unchecked by default', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const checkbox = page.locator('[data-testid="burn-captions-checkbox"]');
    await expect(checkbox).not.toBeChecked();
    await page.screenshot({ path: 'test-results/step5-burn-captions.png' });
  });

  test('Generate Video button is disabled if missing images', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const generateButton = page.locator('[data-testid="generate-video-button"]');
    await expect(generateButton).toBeDisabled();

    // Warning message should be visible
    await expect(page.locator('text=Upload images for all segments')).toBeVisible();
    await page.screenshot({ path: 'test-results/step5-generate-disabled.png' });
  });

  test('Generate Video button is enabled when all images are present', async ({ page }) => {
    await page.route(
      apiBase + '/projects/**/images/**',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'image/png',
          body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            'base64'
          ),
        });
      }
    );

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const generateButton = page.locator('[data-testid="generate-video-button"]');
    await expect(generateButton).toBeEnabled();
    await page.screenshot({ path: 'test-results/step5-generate-enabled.png' });
  });

  test('progress bar appears during generation', async ({ page }) => {
    await page.route(
      apiBase + '/projects/**/images/**',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'image/png',
          body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            'base64'
          ),
        });
      }
    );

    // Delay the generate endpoint so we can catch the progress bar
    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await new Promise(resolve => setTimeout(resolve, 800));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ output_path: 'output/output.mp4', duration: 20.0 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const generateButton = page.locator('[data-testid="generate-video-button"]');
    await expect(generateButton).toBeEnabled();
    await generateButton.click();

    // Progress bar should appear while generating
    const progressBar = page.locator('[data-testid="progress-bar"]');
    await expect(progressBar).toBeVisible();

    await page.screenshot({ path: 'test-results/step5-progress-bar.png' });

    // Wait for generation to complete
    await page.waitForSelector('[data-testid="download-video-button"]', { timeout: 10000 });
  });

  test('download button appears after generation', async ({ page }) => {
    await page.route(
      apiBase + '/projects/**/images/**',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'image/png',
          body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            'base64'
          ),
        });
      }
    );

    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ output_path: 'output/output.mp4', duration: 20.0 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('[data-testid="generate-video-button"]').click();

    // Download button should appear after generation
    const downloadButton = page.locator('[data-testid="download-video-button"]');
    await expect(downloadButton).toBeVisible();
    await expect(downloadButton).toBeEnabled();
    await page.screenshot({ path: 'test-results/step5-download-button.png' });
  });

  test('console output panel is visible after generation', async ({ page }) => {
    await page.route(
      apiBase + '/projects/**/images/**',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'image/png',
          body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            'base64'
          ),
        });
      }
    );

    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ output_path: 'output/output.mp4', duration: 20.0 }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('[data-testid="generate-video-button"]').click();

    // Console toggle should be visible
    const consoleToggle = page.locator('[data-testid="console-toggle"]');
    await expect(consoleToggle).toBeVisible();

    // Click to expand console output
    await consoleToggle.click();
    const consoleOutput = page.locator('[data-testid="console-output"]');
    await expect(consoleOutput).toBeVisible();
    await page.screenshot({ path: 'test-results/step5-console-output.png' });
  });

  test('error banner shows on generation failure', async ({ page }) => {
    await page.route(
      apiBase + '/projects/**/images/**',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'image/png',
          body: Buffer.from(
            'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==',
            'base64'
          ),
        });
      }
    );

    await page.route(apiBase + '/projects/**/video/generate', async route => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'FFmpeg failed' }),
      });
    });

    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await page.locator('[data-testid="generate-video-button"]').click();

    await expect(page.locator('text=FFmpeg failed')).toBeVisible();
    await page.screenshot({ path: 'test-results/step5-error-banner.png' });
  });

  test('all buttons have border-radius 0px', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const buttons = page.locator('button');
    const count = await buttons.count();
    for (let i = 0; i < count; i++) {
      await expect(buttons.nth(i)).toHaveCSS('border-radius', '0px');
    }
    await page.screenshot({ path: 'test-results/step5-buttons-radius.png' });
  });

  test('headings use Playfair Display font', async ({ page }) => {
    await page.goto('http://localhost:5173/project/test-uuid/step/5');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await expect(page.locator('h1')).toHaveCSS('font-family', /Playfair Display/);
    await page.screenshot({ path: 'test-results/step5-heading-font.png' });
  });
});
