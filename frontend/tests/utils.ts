import type { Page } from '@playwright/test';

export async function injectStyles(page: Page): Promise<void> {
  await page.addStyleTag({
    content: `
      .font-headline { font-family: 'Playfair Display', serif; }
      .font-body { font-family: 'Source Sans 3', sans-serif; }
      .font-mono { font-family: 'JetBrains Mono', monospace; }
    `,
  });
}

export async function isBackendRunning(): Promise<boolean> {
  try {
    const resp = await fetch('http://localhost:8000/health');
    return resp.ok;
  } catch {
    return false;
  }
}
