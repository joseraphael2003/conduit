import { test, expect } from '@playwright/test';
import { execSync } from 'child_process';
import { existsSync, readFileSync, readdirSync, statSync, mkdirSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import os from 'os';
import { apiBase } from "../src/config";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);


function isBackendRunning(): boolean {
  try {
    execSync('curl -s http://localhost:8000/health', { stdio: 'pipe', shell: 'cmd.exe' });
    return true;
  } catch {
    return false;
  }
}

async function injectStyles(page: any) {
  await page.addStyleTag({
    content: `
      .font-headline { font-family: 'Playfair Display', serif; }
      .font-body { font-family: 'Source Sans 3', sans-serif; }
      .font-mono { font-family: 'JetBrains Mono', monospace; }
    `,
  });
}

// Small valid MP3 header for test uploads
const testMp3Buffer = Buffer.from([0xff, 0xfb, 0x90, 0x00]);

// 16:9 PNG test image path
const testPngPath = path.resolve(__dirname, '../../backend/tests/fixtures/test_image.png');

test.describe.configure({ mode: 'serial' });

test.describe('E2E Happy Path — Full 5-Step Wizard', () => {
  let projectUuid: string = '';
  let testProjectsDir: string = '';

  test.beforeAll(async () => {
    if (!isBackendRunning()) {
      throw new Error('Test backend is not running on port 8000. Please start it with: python backend/run_test_backend.py');
    }
    console.log('Backend confirmed running on port 8000');
  });

  test.beforeEach(async ({ page }) => {
    await injectStyles(page);
  });

  test('Step 0: Create project from dashboard', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');

    // Handle the prompt dialog
    page.on('dialog', async dialog => {
      if (dialog.type() === 'prompt') {
        await dialog.accept('E2E Happy Path Test');
      } else {
        await dialog.dismiss();
      }
    });

    // Click Create Project
    await page.locator('button', { hasText: 'Create Project' }).click();

    // Wait for the project to appear in the list
    await page.waitForSelector('h2', { hasText: 'E2E Happy Path Test' });

    // Click Open on the first matching project
    const projectCard = page.locator('h2', { hasText: 'E2E Happy Path Test' }).first().locator('xpath=../..');
    await projectCard.locator('button', { hasText: 'Open' }).first().click();

    // Wait for navigation to project wizard
    await page.waitForURL(/\/project\/[^/]+/);
    const url = page.url();
    const match = url.match(/\/project\/([^/]+)/);
    expect(match).toBeTruthy();
    projectUuid = match![1];
    console.log(`Created project: ${projectUuid}`);
  });

  test('Step 1: Upload voiceover and verify transcript', async ({ page }) => {
    await page.goto(`http://localhost:5173/project/${projectUuid}/step/1`);
    await page.waitForLoadState('networkidle');

    // Wait for dropzone
    await expect(page.locator('[data-testid="voiceover-dropzone"]')).toBeVisible();

    // Upload MP3 file via filechooser
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('[data-testid="voiceover-dropzone"]').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles({
      name: 'test-voiceover.mp3',
      mimeType: 'audio/mpeg',
      buffer: testMp3Buffer,
    });

    // Wait for transcript to appear
    await page.waitForSelector('[data-testid="transcript-display"]', { timeout: 10000 });
    await expect(page.locator('[data-testid="transcript-display"]')).toBeVisible();

    // Verify state is step_1_complete
    const stateResp = await fetch(`${apiBase}/projects/${projectUuid}/state`);
    const stateData = await stateResp.json();
    expect(stateData.state).toBe('step_1_complete');

    await page.screenshot({ path: 'test-results/e2e-step1-complete.png' });
  });

  test('Step 2: Extract characters and generate prompts', async ({ page }) => {
    await page.goto(`http://localhost:5173/project/${projectUuid}/step/2`);
    await page.waitForLoadState('networkidle');

    // Click Extract Characters
    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForSelector('table tbody tr', { timeout: 10000 });

    // Verify character table has rows
    const rows = page.locator('table tbody tr');
    await expect(rows).toHaveCount(1);
    await expect(page.locator('text=Alice')).toBeVisible();

    // Edit description to enable Generate Prompts
    const textarea = page.locator('table tbody tr:first-child textarea');
    await textarea.fill('A curious explorer with a new hat.');

    // Click Generate Prompts
    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForSelector('button[aria-label^="Copy front profile prompt"]', { timeout: 10000 });

    // Verify prompt cards
    await expect(page.locator('button[aria-label^="Copy front profile prompt"]')).toHaveCount(1);

    // Verify state is step_2_complete
    const stateResp = await fetch(`${apiBase}/projects/${projectUuid}/state`);
    const stateData = await stateResp.json();
    expect(stateData.state).toBe('step_2_complete');

    await page.screenshot({ path: 'test-results/e2e-step2-complete.png' });
  });

  test('Step 3: Generate segments and prompts', async ({ page }) => {
    await page.goto(`http://localhost:5173/project/${projectUuid}/step/3`);
    await page.waitForLoadState('networkidle');

    // Click Generate Segments
    await page.locator('button', { hasText: 'Generate Segments' }).click();
    await page.waitForSelector('table tbody tr', { timeout: 10000 });

    // Verify segment table has rows
    const rows = page.locator('table tbody tr');
    await expect(rows).toHaveCount(2);

    // Click Generate Prompts
    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForTimeout(1000);

    // Verify state is step_3_complete
    const stateResp = await fetch(`${apiBase}/projects/${projectUuid}/state`);
    const stateData = await stateResp.json();
    expect(stateData.state).toBe('step_3_complete');

    await page.screenshot({ path: 'test-results/e2e-step3-complete.png' });
  });

  test('Step 4: Upload images for all segments', async ({ page }) => {
    await page.goto(`http://localhost:5173/project/${projectUuid}/step/4`);
    await page.waitForLoadState('networkidle');

    // Wait for segment cells
    await page.waitForSelector('[data-testid="segment-cell"]');
    const cells = page.locator('[data-testid="segment-cell"]');
    await expect(cells).toHaveCount(2);

    // Upload images for each segment
    for (let i = 0; i < 2; i++) {
      const fileChooserPromise = page.waitForEvent('filechooser');
      const uploadButton = page.locator('[data-testid="upload-button"]').nth(i);
      await uploadButton.click();
      const fileChooser = await fileChooserPromise;
      await fileChooser.setFiles(testPngPath);

      // Wait for thumbnail to appear
      await page.waitForTimeout(500);
    }

    // Verify all segments have thumbnails
    const thumbnails = page.locator('[data-testid="segment-thumbnail"]');
    await expect(thumbnails).toHaveCount(2);

    // Advance state to step_4_complete so video generation can proceed
    const advanceResp = await fetch(`${apiBase}/projects/${projectUuid}/step/4`, {
      method: 'PUT',
    });
    expect(advanceResp.status).toBe(200);

    await page.screenshot({ path: 'test-results/e2e-step4-complete.png' });
  });

  test('Step 5: Auto-assign effects and generate video', async ({ page }) => {
    await page.goto(`http://localhost:5173/project/${projectUuid}/step/5`);
    await page.waitForLoadState('networkidle');

    // Wait for effect grid
    await page.waitForSelector('[data-testid="effect-selection-grid"]');

    // Click Randomize button to auto-assign effects
    await page.locator('[data-testid="randomize-button"]').click();
    await page.waitForTimeout(500);

    // Click Generate Video
    await page.locator('[data-testid="generate-video-button"]').click();

    // Wait for download button to appear
    await page.waitForSelector('[data-testid="download-video-button"]', { timeout: 15000 });

    // Verify state is step_5_complete
    const stateResp = await fetch(`${apiBase}/projects/${projectUuid}/state`);
    const stateData = await stateResp.json();
    expect(stateData.state).toBe('step_5_complete');

    await page.screenshot({ path: 'test-results/e2e-step5-complete.png' });

    // Create evidence directory and save screenshot
    const evidenceDir = path.resolve(__dirname, '../.sisyphus/evidence/session-4');
    if (!existsSync(evidenceDir)) {
      mkdirSync(evidenceDir, { recursive: true });
    }
    await page.screenshot({ path: path.join(evidenceDir, 'task-9-e2e-happy.png') });
    console.log(`Evidence screenshot saved to ${path.join(evidenceDir, 'task-9-e2e-happy.png')}`);
  });

  test('Final: Verify output files exist', async () => {
    // Find the latest test projects directory
    const tmpDir = os.tmpdir();
    const dirs = readdirSync(tmpDir).filter((d: string) => d.startsWith('test_e2e_projects_'));
    expect(dirs.length).toBeGreaterThan(0);
    const latestDir = dirs.reduce((a: string, b: string) => {
      const aTime = statSync(path.join(tmpDir, a)).mtimeMs;
      const bTime = statSync(path.join(tmpDir, b)).mtimeMs;
      return aTime > bTime ? a : b;
    });
    testProjectsDir = path.join(tmpDir, latestDir);

    const projectDir = path.join(testProjectsDir, projectUuid);
    expect(existsSync(projectDir)).toBe(true);

    // Verify output.mp4 exists
    const outputPath = path.join(projectDir, 'output', 'output.mp4');
    expect(existsSync(outputPath)).toBe(true);
    console.log(`output.mp4 exists: ${outputPath}`);

    // Verify captions.srt exists
    const srtPath = path.join(projectDir, 'captions.srt');
    expect(existsSync(srtPath)).toBe(true);
    console.log(`captions.srt exists: ${srtPath}`);

    // Verify state.json has step_5_complete
    const statePath = path.join(projectDir, '.conduit', 'state.json');
    expect(existsSync(statePath)).toBe(true);
    const stateData = JSON.parse(readFileSync(statePath, 'utf-8'));
    expect(stateData.state).toBe('step_5_complete');
  });

});
