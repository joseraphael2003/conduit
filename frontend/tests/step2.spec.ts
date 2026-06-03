import { test, expect } from '@playwright/test';

const mockCharacters = [
  {
    name: 'Alice',
    type: 'protagonist',
    importance: 'main',
    description: 'A curious explorer.',
  },
  {
    name: 'Bob',
    type: 'supporting',
    importance: 'secondary',
    description: 'A loyal companion.',
  },
];

const mockCharactersWithPrompts = [
  {
    name: 'Alice',
    type: 'protagonist',
    importance: 'main',
    description: 'A curious explorer.',
    front_profile_prompt: 'Front profile of Alice, a curious explorer, wearing a leather jacket.',
    turnaround_reference_prompt: 'Turnaround reference of Alice, showing front, side, and back views.',
  },
  {
    name: 'Bob',
    type: 'supporting',
    importance: 'secondary',
    description: 'A loyal companion.',
    front_profile_prompt: 'Front profile of Bob, a loyal companion, wearing casual clothes.',
    turnaround_reference_prompt: 'Turnaround reference of Bob, showing front, side, and back views.',
  },
];

test.describe('Step 2 — Characters', () => {
  test.beforeEach(async ({ page }) => {
    // Mock GET /characters
    await page.route(
      'http://localhost:8000/api/v1/projects/**/characters',
      async route => {
        const url = route.request().url();
        if (url.includes('/extract') || url.includes('/prompts')) {
          route.continue();
          return;
        }
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ characters: [] }),
        });
      }
    );

    // Mock POST /characters/extract
    await page.route(
      'http://localhost:8000/api/v1/projects/**/characters/extract',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ characters: mockCharacters }),
        });
      }
    );

    // Mock PUT /characters
    await page.route(
      'http://localhost:8000/api/v1/projects/**/characters',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true }),
        });
      }
    );

    // Mock POST /characters/prompts
    await page.route(
      'http://localhost:8000/api/v1/projects/**/characters/prompts',
      async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ characters: mockCharactersWithPrompts }),
        });
      }
    );

    await page.goto('http://localhost:5173/project/test-uuid/step/2');
    await page.waitForLoadState('networkidle');

    // Inject font styles
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
        .font-body { font-family: 'Source Sans 3', sans-serif; }
      `,
    });
  });

  test('Extract Characters button is visible', async ({ page }) => {
    const button = page.locator('button', { hasText: 'Extract Characters' });
    await expect(button).toBeVisible();
    await page.screenshot({ path: 'test-results/step2-extract-button.png' });
  });

  test('character table has correct number of rows after extraction', async ({ page }) => {
    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForSelector('table tbody tr');

    const rows = page.locator('table tbody tr');
    await expect(rows).toHaveCount(2);
    await page.screenshot({ path: 'test-results/step2-character-table.png' });
  });

  test('Generate Prompts button is enabled after editing', async ({ page }) => {
    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForSelector('table tbody tr');

    const generateBtn = page.locator('button', { hasText: 'Generate Prompts' });
    await expect(generateBtn).toBeDisabled();

    // Edit a description
    const textarea = page.locator('table tbody tr:first-child textarea');
    await textarea.fill('A curious explorer with a new hat.');

    await expect(generateBtn).toBeEnabled();
    await page.screenshot({ path: 'test-results/step2-generate-enabled.png' });
  });

  test('prompt cards have Copy button', async ({ page }) => {
    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForSelector('table tbody tr');

    // Edit to enable generate button
    const textarea = page.locator('table tbody tr:first-child textarea');
    await textarea.fill('A curious explorer with a new hat.');

    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForSelector('button[aria-label^="Copy front profile prompt"]');

    const copyButtons = page.locator('button[aria-label^="Copy front profile prompt"]');
    await expect(copyButtons).toHaveCount(2);

    // Also check turnaround copy buttons
    const turnaroundButtons = page.locator('button[aria-label^="Copy turnaround reference prompt"]');
    await expect(turnaroundButtons).toHaveCount(2);

    await page.screenshot({ path: 'test-results/step2-prompt-cards.png' });
  });

  test('JSON toggle shows raw JSON', async ({ page }) => {
    await page.locator('button', { hasText: 'Extract Characters' }).click();
    await page.waitForSelector('table tbody tr');

    // Edit to enable generate button
    const textarea = page.locator('table tbody tr:first-child textarea');
    await textarea.fill('A curious explorer with a new hat.');

    await page.locator('button', { hasText: 'Generate Prompts' }).click();
    await page.waitForSelector('button[aria-label="Toggle JSON"]');

    // Toggle JSON for first character
    const jsonToggle = page.locator('button[aria-label="Toggle JSON"]').first();
    await jsonToggle.click();

    await page.waitForSelector('pre');
    const pre = page.locator('pre').first();
    await expect(pre).toContainText('"name": "Alice"');
    await expect(pre).toContainText('"front_profile_prompt"');

    await page.screenshot({ path: 'test-results/step2-json-toggle.png' });
  });
});
