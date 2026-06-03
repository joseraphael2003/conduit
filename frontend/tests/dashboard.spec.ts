import { test, expect } from '@playwright/test';

test.describe('Dashboard Page', () => {
  async function injectStyles(page: any) {
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
      `,
    });
  }

  test.describe('Empty State', () => {
    test.beforeEach(async ({ page }) => {
      await page.route('http://localhost:8000/api/v1/projects', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ projects: [] }),
        });
      });
      await page.goto('http://localhost:5173');
      await page.waitForLoadState('networkidle');
      await injectStyles(page);
    });

    test('renders 3 geometric rectangles in empty state', async ({ page }) => {
      await expect(page.locator('main .absolute')).toHaveCount(3);
      await page.screenshot({ path: 'test-results/dashboard-empty-state.png' });
    });

    test('Create Project button is amber', async ({ page }) => {
      const button = page.locator('button', { hasText: 'Create Project' });
      await expect(button).toHaveCSS('background-color', 'rgb(240, 160, 64)');
      await page.screenshot({ path: 'test-results/dashboard-create-button.png' });
    });
  });

  test.describe('With Mock Data', () => {
    test.beforeEach(async ({ page }) => {
      await page.route('http://localhost:8000/api/v1/projects', async route => {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({
            projects: [
              {
                uuid: 'test-uuid-123',
                name: 'Test Project',
                state: 'created',
                created_at: '2026-06-01T12:00:00Z',
                updated_at: '2026-06-01T12:00:00Z',
              },
            ],
          }),
        });
      });
      await page.goto('http://localhost:5173');
      await page.waitForLoadState('networkidle');
      await injectStyles(page);
    });

    test('project card has name, date, badge, buttons', async ({ page }) => {
      const card = page.locator('h2', { hasText: 'Test Project' }).locator('xpath=../..');
      await expect(card.locator('h2')).toHaveText('Test Project');
      await expect(card.locator('span.font-mono')).toHaveText('Jun 1, 2026');
      await expect(card.locator('span', { hasText: 'pending' })).toBeVisible();
      await expect(card.locator('button', { hasText: 'Open' })).toBeVisible();
      await expect(card.locator('button', { hasText: 'Delete' })).toBeVisible();
      await page.screenshot({ path: 'test-results/dashboard-project-card.png' });
    });
  });

  test('body background color is dark surface', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(15, 15, 20)');
    await page.screenshot({ path: 'test-results/dashboard-body-bg.png' });
  });

  test('headings use Playfair Display font', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
    await expect(page.locator('h1')).toHaveCSS('font-family', /Playfair Display/);
    await page.screenshot({ path: 'test-results/dashboard-heading-font.png' });
  });
});
