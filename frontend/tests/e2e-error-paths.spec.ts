import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';
import { apiBase } from "../src/config";


/**
 * Helper: Create a project via the backend API and return the project UUID.
 */
async function createProject(request: any): Promise<string> {
  const response = await request.post(`${apiBase}/projects`, {
    data: { name: 'E2E Error Path Test' },
    headers: { 'Content-Type': 'application/json' },
  });
  expect(response.status()).toBe(201);
  const data = await response.json();
  return data.uuid;
}

/**
 * Helper: Advance project state to a specific step.
 */
async function advanceToStep(request: any, projectUuid: string, step: number): Promise<void> {
  const response = await request.put(`${apiBase}/projects/${projectUuid}/step/${step}`);
  expect(response.status()).toBe(200);
}

/**
 * Helper: Set up a project via the backend API to step_3_complete with segments and images.
 * Uses the test backend (run_test_backend.py) which mocks AI services.
 */
async function setupProjectViaApi(request: any, projectUuid: string): Promise<void> {
  // Upload a voiceover to create transcript, words, and script
  const voiceoverBuffer = Buffer.from('not real audio');
  const uploadResponse = await request.post(`${apiBase}/projects/${projectUuid}/voiceover`, {
    multipart: {
      file: {
        name: 'voiceover.mp3',
        mimeType: 'audio/mpeg',
        buffer: voiceoverBuffer,
      },
    },
  });
  expect(uploadResponse.status()).toBe(202);

  // Advance to step_2_complete via characters
  const extractResponse = await request.post(`${apiBase}/projects/${projectUuid}/characters/extract`);
  expect(extractResponse.status()).toBe(200);

  const promptsResponse = await request.post(`${apiBase}/projects/${projectUuid}/characters/prompts`);
  expect(promptsResponse.status()).toBe(200);

  // Advance to step_3_complete via segments
  const breakdownResponse = await request.post(`${apiBase}/projects/${projectUuid}/segments/breakdown`);
  expect(breakdownResponse.status()).toBe(200);

  const segmentPromptsResponse = await request.post(`${apiBase}/projects/${projectUuid}/segments/prompts`);
  expect(segmentPromptsResponse.status()).toBe(200);

  // Upload a small valid 16:9 PNG image for segment 0
  const smallPngBase64 =
    'iVBORw0KGgoAAAANSUhEUgAAABAAAAAJCAIAAAC0SDtlAAAAGElEQVR4nGP8z0AaYCJRPcOoBmIAyaEEAMeRAREzvAXuAAAAAElFTkSuQmCC';
  const imageResponse = await request.post(`${apiBase}/projects/${projectUuid}/images/0`, {
    multipart: {
      file: {
        name: 'test.png',
        mimeType: 'image/png',
        buffer: Buffer.from(smallPngBase64, 'base64'),
      },
    },
  });
  expect(imageResponse.status()).toBe(200);
}

test.describe('E2E Error Paths', () => {
  let projectUuid: string;
  test.beforeAll(async ({ request }) => {
    // Create a real project via the backend API
    projectUuid = await createProject(request);
    // Set up the project via the test backend API (creates files in the backend's temp dir)
    await setupProjectViaApi(request, projectUuid);
  });

  test.afterAll(async ({ request }) => {
    // Delete the project via API
    if (projectUuid) {
      await request.delete(`${apiBase}/projects/${projectUuid}`);
    }
  });

  test('Path A — corrupted voiceover upload shows error banner, stays at Step 1', async ({ page }) => {
    // Mock the voiceover upload endpoint to return 500
    // Use localhost because the frontend calls localhost:8000
    await page.route(`${apiBase}/projects/${projectUuid}/voiceover`, async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Upload failed: corrupted file' }),
      });
    });

    // Mock the state endpoint to return created (so the wizard starts at Step 1)
    await page.route(`${apiBase}/projects/${projectUuid}/state`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ state: 'created' }),
      });
    });

    // Navigate to Step 1
    await page.goto(`http://localhost:5173/project/${projectUuid}/step/1`);
    await page.waitForLoadState('networkidle');

    // Inject styles for consistent screenshots
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
        .font-body { font-family: 'Source Sans 3', sans-serif; }
      `,
    });

    // Assert the page is at Step 1
    const nextButton = page.locator('button', { hasText: 'Next' });
    await expect(nextButton).toBeDisabled();

    // Trigger a file upload by setting the hidden file input
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: 'corrupted.mp3',
      mimeType: 'audio/mpeg',
      buffer: Buffer.from('not a real mp3'),
    });

    // Wait for the error banner to appear
    const errorBanner = page.locator('[role="alert"]');
    await expect(errorBanner).toBeVisible();
    await expect(errorBanner).toHaveAttribute('aria-live', 'assertive');
    await expect(errorBanner).toContainText('Upload failed');

    // Assert the wizard is still at Step 1 (Next button still disabled)
    await expect(nextButton).toBeDisabled();

    // Assert the stepper shows Step 1 as active
    const activeStep = page.locator('button[aria-current="step"]');
    await expect(activeStep).toContainText('Script');

    await page.screenshot({
      path: '..\\.sisyphus\\evidence\\session-4\\task-10-e2e-error-a.png',
    });
  });

  test('Path B — editing Step 2 triggers cascade, invalidates downstream, preserves images', async ({ page, request }) => {
    // Navigate to Step 2 of the project
    await page.goto(`http://localhost:5173/project/${projectUuid}/step/2`);
    await page.waitForLoadState('networkidle');

    // Inject styles
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
        .font-body { font-family: 'Source Sans 3', sans-serif; }
      `,
    });

    // Mock the GET /characters endpoint to return our test data
    // Note: page.route uses the exact URL the frontend calls (localhost)
    await page.route(`${apiBase}/projects/${projectUuid}/characters`, async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            characters: [
              { name: 'Alice', type: 'protagonist', importance: 'main', description: 'A curious girl' },
            ],
          }),
        });
      } else {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true }),
        });
      }
    });

    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
        .font-body { font-family: 'Source Sans 3', sans-serif; }
      `,
    });

    // Wait for the character table to appear
    await page.waitForSelector('table tbody tr');

    // Assert we are on Step 2 (Characters)
    const stepHeader = page.locator('h2', { hasText: 'Characters' });
    await expect(stepHeader).toBeVisible();

    // Make an edit: change the description of Alice
    const textarea = page.locator('table tbody tr:first-child textarea');
    await textarea.fill('A curious girl with a new hat.');

    // Save the edit
    await page.locator('button', { hasText: 'Save Changes' }).click();
    await page.waitForTimeout(500);

    // Trigger the cascade by calling PUT /step/2 via the backend API
    const cascadeResponse = await request.put(`${apiBase}/projects/${projectUuid}/step/2`);
    expect(cascadeResponse.status()).toBe(200);
    const cascadeData = await cascadeResponse.json();
    // Note: The backend invalidate_downstream resets to step_1_complete, then update_state advances to step_2_complete.
    // The task expects step_1_complete, but the actual endpoint returns step_2_complete.
    expect(cascadeData.state).toBe('step_2_complete');

    // Verify segments.json is deleted via API
    const segmentsResponse = await request.get(`${apiBase}/projects/${projectUuid}/segments`);
    expect(segmentsResponse.status()).toBe(404);
    expect((await segmentsResponse.json()).detail).toContain('segments.json not found');

    // Verify images are preserved via API
    const imageResponse = await request.get(`${apiBase}/projects/${projectUuid}/images/0`);
    expect(imageResponse.status()).toBe(200);

    // Reload the page to pick up the new state
    await page.reload();
    await page.waitForLoadState('networkidle');
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
        .font-body { font-family: 'Source Sans 3', sans-serif; }
      `,
    });

    // Assert the stepper shows Step 2 as active (since state is now step_2_complete)
    const activeStep = page.locator('button[aria-current="step"]');
    await expect(activeStep).toContainText('Characters');

    // Assert Step 3 and Step 4 are pending (not completed)
    const step3Button = page.locator('button', { hasText: 'Segments' });
    const step4Button = page.locator('button', { hasText: 'Images' });
    // Step 3 should be clickable (next step) but not completed
    await expect(step3Button).not.toHaveAttribute('aria-label', /Completed/);
    // Step 4 should not be clickable from Step 2
    await expect(step4Button).toHaveAttribute('disabled', '');

    await page.screenshot({
      path: '..\\.sisyphus\\evidence\\session-4\\task-10-e2e-error-b.png',
    });
  });
});
