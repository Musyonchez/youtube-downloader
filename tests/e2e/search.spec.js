const { test, expect } = require('@playwright/test');

test('search by name renders results with no console errors', async ({ page }) => {
  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  await page.goto('/app/name');
  await page.fill('#search-input', 'lofi hip hop');
  await page.click('#search-btn');

  await expect(page.locator('.video-card')).toHaveCount(2, { timeout: 10000 });
  await expect(page.locator('.video-card').first()).toContainText('Fake Test Video One');

  expect(consoleErrors).toEqual([]);
});

test('add to queue updates the queue count with no console errors', async ({ page }) => {
  const consoleErrors = [];
  page.on('console', (msg) => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', (err) => consoleErrors.push(err.message));

  page.on('dialog', (dialog) => dialog.accept());

  await page.goto('/app/name');
  await page.fill('#search-input', 'lofi hip hop');
  await page.click('#search-btn');
  await page.waitForSelector('.video-card');

  await page.click('.add-to-queue-btn >> nth=0');
  await expect(page.locator('#queue-count')).toHaveText('1', { timeout: 5000 });

  // Clean up (clearQueue() uses confirm(), auto-accepted above) so repeated
  // local runs against the same dev DB stay idempotent.
  await page.click('#clear-btn');
  await expect(page.locator('#queue-count')).toHaveText('0', { timeout: 5000 });

  expect(consoleErrors).toEqual([]);
});
