import { expect, test } from '@playwright/test';

test('remote phone selects a device and sends input commands', async ({ page }) => {
  const requests = [];
  page.on('request', request => { if (request.url().includes('/api/remote/input/')) requests.push(request); });
  await page.goto('/remote/');
  await expect(page.getByRole('heading', { name: 'Remote Phone' })).toBeVisible();
  await page.getByRole('combobox', { name: 'Device' }).selectOption('acceptance-device');
  await expect(page.getByAltText('Live Android device screen')).toBeVisible();
  await page.getByRole('application', { name: 'Remote phone screen' }).click({ position: { x: 100, y: 100 } });
  await expect.poll(() => requests.length).toBe(1);
  expect(requests[0].url()).toContain('/api/remote/input/tap');
});
