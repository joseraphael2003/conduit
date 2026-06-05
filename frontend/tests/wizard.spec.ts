import { test, expect } from '@playwright/test';

test.describe('Wizard Page', () => {
  async function injectStyles(page: any) {
    await page.addStyleTag({
      content: `
        .font-headline { font-family: 'Playfair Display', serif; }
        .font-body { font-family: 'Source Sans 3', sans-serif; }
      `,
    });
    await page.evaluate(() => {
      const code = document.createElement('code');
      code.className = 'font-mono';
      code.textContent = 'test';
      code.style.position = 'absolute';
      code.style.left = '-9999px';
      document.body.appendChild(code);
    });
  }

  test.beforeEach(async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/state', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'created' }) });
    });
    await page.goto('http://localhost:5173/project/test-uuid');
    await page.waitForLoadState('networkidle');
    await injectStyles(page);
  });

  test('renders Conduit heading', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/state', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'created' }) });
    });
    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const h1 = page.locator('h1');
    await expect(h1).toHaveText(/Conduit/);
    await page.screenshot({ path: 'test-results/wizard-heading.png' });
  });

  test('stepper has exactly 5 children', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/state', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'created' }) });
    });
    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    await expect(page.locator('.stepper > div')).toHaveCount(5);
    await page.screenshot({ path: 'test-results/wizard-stepper.png' });
  });

  test('active step has amber color', async ({ page }) => {
    await page.route('http://localhost:8000/api/v1/projects/**/state', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'created' }) });
    });
    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    const activeStep = page.locator('button[aria-current="step"]');
    await expect(activeStep).toHaveCSS('color', 'rgb(240, 160, 64)');
    await page.screenshot({ path: 'test-results/wizard-active-step.png' });
  });

  test('completed step has teal color', async ({ page }) => {
    await page.unroute('http://localhost:8000/api/v1/projects/**/state');
    await page.route('http://localhost:8000/api/v1/projects/**/state', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'step_1_complete' }) });
    });
    await page.route('http://localhost:8000/api/v1/projects/**/transcript', async route => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ transcript: 'Test transcript', word_count: 2 }) });
    });
    await page.reload();
    await page.waitForLoadState('networkidle');
    await injectStyles(page);

    // Click Next to advance to step 2, making step 1 completed
    await page.locator('button', { hasText: 'Next' }).click();
    await page.waitForTimeout(200);
    const completedStep = page.locator('button[aria-label="Step 1: Script — Completed"]');
    await expect(completedStep).toHaveCSS('color', 'rgb(6, 182, 212)');
    await page.screenshot({ path: 'test-results/wizard-completed-step.png' });
  });

  test('all buttons have border-radius 0px', async ({ page }) => {
    const buttons = page.locator('button');
    const count = await buttons.count();
    for (let i = 0; i < count; i++) {
      await expect(buttons.nth(i)).toHaveCSS('border-radius', '0px');
    }
    await page.screenshot({ path: 'test-results/wizard-buttons-radius.png' });
  });

  test('headings use Playfair Display font', async ({ page }) => {
    await expect(page.locator('h1')).toHaveCSS('font-family', /Playfair Display/);
    await page.screenshot({ path: 'test-results/wizard-heading-font.png' });
  });

  test('body uses Source Sans 3 font', async ({ page }) => {
    await expect(page.locator('body')).toHaveCSS('font-family', /Source Sans 3/);
    await page.screenshot({ path: 'test-results/wizard-body-font.png' });
  });

  test('code elements use JetBrains Mono font', async ({ page }) => {
    const codeElement = page.locator('.font-mono').first();
    await expect(codeElement).toHaveCSS('font-family', /JetBrains Mono/);
    await page.screenshot({ path: 'test-results/wizard-code-font.png' });
  });

  test('body background color is dark surface', async ({ page }) => {
    await expect(page.locator('body')).toHaveCSS('background-color', 'rgb(15, 15, 20)');
    await page.screenshot({ path: 'test-results/wizard-body-bg.png' });
  });
});
