import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.route('**/api/**', route => {
    const path = new URL(route.request().url()).pathname;
    if (route.request().method() !== 'GET') throw new Error('Visual tests must never mutate the backend');
    let data = {};
    if (path.endsWith('/readiness')) data = { overall_ready: true, probes: [], timestamp: 1, blocker_count: 0 };
    else if (path.endsWith('/emulator/status')) data = { status: 'idle', logs: [] };
    else if (path.endsWith('/sessions')) data = [];
    else if (path.endsWith('/devices')) data = { devices: [] };
    else if (path.endsWith('/windows-startup')) data = { supported: true, enabled: true, port: 8009 };
    else if (path.endsWith('/settings/model')) data = { provider: 'openai', default_model: 'test-model', fallback_model: 'backup', version: 'test', keys_configured: {}, node_overrides: [] };
    else if (path.endsWith('/schedules')) data = { schedules: [] };
    else if (path.endsWith('/stream')) return route.fulfill({ contentType: 'text/event-stream', body: ':fixture\n\n' });
    return route.fulfill({ json: data });
  });
});

for (const theme of ['light', 'dark']) {
  test(`Angular layout contract: ${theme}`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.addInitScript(theme => localStorage.setItem('artemis.ui.preferences.v1', JSON.stringify({version:1,language:'en',theme})), theme);
    await page.goto('/');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('What would you like to do on your phone?');
    await expect(page.locator('.suggestionCard')).toHaveCount(18);
    expect((await page.locator('.topbar').boundingBox()).height).toBe(36);
    expect((await page.locator('.homeComposer').boundingBox()).width).toBe(912);
    await expect(page.locator('footer')).toHaveCount(0);
    await expect(page.locator('[data-slot="textarea"]')).toBeVisible();
    await page.goto('/settings/');
    await expect(page.getByRole('tab', { name: 'General', exact: true })).toHaveAttribute('data-state', 'active');
    const list = await page.getByRole('tablist').boundingBox();
    const panel = await page.getByRole('tabpanel', { name: 'General' }).boundingBox();
    expect(list.width).toBe(220);
    expect(panel.x).toBeGreaterThan(list.x + list.width);
    await expect(page.locator('[data-slot="switch"]')).toBeVisible();
    const toggle = page.locator('[data-slot="switch"]');
    await expect(toggle).toHaveAttribute('data-state','checked');
    const track = await toggle.boundingBox();
    const thumb = await toggle.locator('[data-slot="switch-thumb"]').boundingBox();
    expect(thumb.x).toBeGreaterThanOrEqual(track.x);
    expect(thumb.x + thumb.width).toBeLessThanOrEqual(track.x + track.width);
    const payloadRequests=[];
    page.on('request',request=>{if(new URL(request.url()).pathname==='/settings/index.txt')payloadRequests.push(request.url());});
    await page.getByRole('tab', { name: 'Models', exact: true }).click();
    const input = page.getByLabel('Default model', { exact: true });
    await input.fill('unsaved-custom-model');
    await page.getByRole('tab', { name: 'General', exact: true }).click();
    await page.getByRole('tab', { name: 'Models', exact: true }).click();
    await expect(input).toHaveValue('unsaved-custom-model');
    await expect(page).toHaveURL(/\/settings\/\?tab=models$/);
    expect(payloadRequests).toEqual([]);
    await page.goto('/workspace/');
    const main = await page.locator('.ws-main').boundingBox();
    const rail = await page.locator('.ws-rail').boundingBox();
    expect(rail.x).toBeGreaterThan(main.x + main.width);
    await page.screenshot({ path: `test-results/design/verified-workspace-${theme}.png`, fullPage: true });
  });
}

test('mobile navigation and Settings remain usable without horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/settings/');
  await expect(page.getByRole('tab', { name: 'General', exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
  await page.getByRole('tab', { name: 'Models', exact: true }).click();
  await expect(page.getByLabel('Default model', { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(390);
});
