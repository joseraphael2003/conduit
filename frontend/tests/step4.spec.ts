import { test, expect } from '@playwright/test';

const mockSegments = [
  {
    segment_index: 0,
    script_line: "Welcome to the tutorial.",
    segment_prompt: "A welcoming scene with a host standing in front of a bright backdrop.",
    characters_present: ["Host"],
    start_time: 0,
    end_time: 5.2,
  },
  {
    segment_index: 1,
    script_line: "Let's begin with the basics.",
    segment_prompt: "Close-up of the host pointing at a whiteboard.",
    characters_present: ["Host"],
    start_time: 5.2,
    end_time: 12.8,
  },
  {
    segment_index: 2,
    script_line: "Now we move to advanced topics.",
    segment_prompt: "Split screen showing code and the host.",
    characters_present: ["Host", "Guest"],
    start_time: 12.8,
    end_time: 20.0,
  },
];

const smallPngBase64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==";

const smallPngBuffer = Buffer.from(smallPngBase64, 'base64');

test.describe.configure({ mode: 'serial' });

test.describe('Step 4 Images Page', () => {
  const uploadedSegments = new Set<number>();

  test.beforeEach(async ({ page }) => {
    uploadedSegments.clear();
    uploadedSegments.add(0);


    await page.route('http://localhost:8000/api/v1/projects/test-uuid/segments', async route => {
      console.log(`[ROUTE] GET /segments - returning mock segments`);
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ segments: mockSegments }),
      });
    });

    await page.route(
      'http://localhost:8000/api/v1/projects/test-uuid/images/**',
      async route => {
        const url = route.request().url();
        const method = route.request().method();
        const segmentIndex = parseInt(url.split('/').pop() || '0', 10);
        console.log(`[ROUTE] ${method} ${url} segmentIndex=${segmentIndex} uploadedSegments=${Array.from(uploadedSegments)}`);

        if (method === 'POST') {
          uploadedSegments.add(segmentIndex);
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ success: true }),
          });
          return;
        }

        if (uploadedSegments.has(segmentIndex)) {
          await route.fulfill({
            status: 200,
            contentType: 'image/png',
            body: smallPngBuffer,
          });
        } else {
          await route.fulfill({
            status: 404,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Not found' }),
          });
        }
      }
    );

    await page.goto('http://localhost:5173/project/test-uuid/step/4');
    await page.waitForLoadState('networkidle');
  });

  test('grid has correct number of cells', async ({ page }) => {
    const segments = await page.evaluate(() => {
      // @ts-ignore
      return window.segments || 'no segments';
    });
    console.log('Segments from page:', segments);
    const cells = page.locator('[data-testid="segment-cell"]');
    await expect(cells).toHaveCount(mockSegments.length);
  });

  test('each cell has Upload button', async ({ page }) => {
    const uploadButtons = page.locator('[data-testid="upload-button"]');
    await expect(uploadButtons).toHaveCount(mockSegments.length);
  });

  test('each cell has Details button', async ({ page }) => {
    const detailsButtons = page.locator('[data-testid="details-button"]');
    await expect(detailsButtons).toHaveCount(mockSegments.length);
  });

  test('placeholder is grey rectangle', async ({ page }) => {
    const placeholders = page.locator('[data-testid="segment-placeholder"]');
    await expect(placeholders).toHaveCount(mockSegments.length - 1);
    const firstPlaceholder = placeholders.first();
    await expect(firstPlaceholder).toHaveCSS('background-color', 'rgb(42, 42, 53)');
  });

  test('uploaded image shows thumbnail', async ({ page }) => {
    const thumbnails = page.locator('[data-testid="segment-thumbnail"]');
    await expect(thumbnails).toHaveCount(1);
    const firstThumbnail = thumbnails.first();
    await expect(firstThumbnail).toBeVisible();
    await page.screenshot({ path: 'test-results/step4-thumbnail.png' });
  });

  test('clicking Details opens modal with segment info', async ({ page }) => {
    await page.locator('[data-testid="details-button"]').first().click();
    const modal = page.locator('[data-testid="details-modal"]');
    await expect(modal).toBeVisible();

    await expect(modal.locator('text=Welcome to the tutorial.')).toBeVisible();
    await expect(modal.getByText('Host', { exact: true })).toBeVisible();
    await expect(modal.locator('text=0:00')).toBeVisible();
  });

  test('uploading a PNG file shows thumbnail', async ({ page }) => {
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('[data-testid="upload-button"]').nth(1).click();
    const fileChooser = await fileChooserPromise;

    await fileChooser.setFiles({
      name: 'test-image.png',
      mimeType: 'image/png',
      buffer: smallPngBuffer,
    });

    await page.waitForTimeout(500);

    const thumbnails = page.locator('[data-testid="segment-thumbnail"]');
    await expect(thumbnails).toHaveCount(2);
    await page.screenshot({ path: 'test-results/step4-upload.png' });
  });
});
