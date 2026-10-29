import { expect, test } from '@playwright/test';

const STORAGE_KEY = 'artemis.ui.preferences.v1';
const preferences = [
  { language: 'en', theme: 'light' }, { language: 'en', theme: 'dark' },
  { language: 'vi', theme: 'light' }, { language: 'vi', theme: 'dark' },
];
const routes = [
  { path: '/', headings: { en: /What would you like to do on your phone/i, vi: /Bạn muốn làm gì trên điện thoại/i } },
  { path: '/workspace/', headings: { en: /^Workspace$/i, vi: /^Không gian làm việc$/i } },
  { path: '/task-schedule/', headings: { en: /^Task Schedule$/i, vi: /^Lịch tác vụ$/i } },
  { path: '/settings/', headings: { en: /^Settings$/i, vi: /^Cài đặt$/i } },
  { path: '/check/', headings: { en: /^Real-time agent stream$/i, vi: /^Luồng tác nhân thời gian thực$/i } },
];

const serialized = (language, theme) => JSON.stringify({ version: 1, language, theme });
async function seed(page, language, theme) {
  await page.addInitScript(({ key, value }) => localStorage.setItem(key, value), { key: STORAGE_KEY, value: serialized(language, theme) });
}
async function expectPreference(page, language, theme) {
  await expect(page.locator('html')).toHaveAttribute('lang', language);
  await expect(page.locator('html')).toHaveAttribute('data-theme', theme);
}

test.beforeEach(async ({ page }) => { page.on('dialog', dialog => dialog.dismiss()); });

for (const { language, theme } of preferences) {
  test('prepaint applies ' + language + '/' + theme + ' before hydration', async ({ page }) => {
    await seed(page, language, theme);
    await page.route('**/_next/static/**/*.js', route => route.abort());
    expect((await page.goto('/settings/', { waitUntil: 'domcontentloaded' }))?.status()).toBe(200);
    await expectPreference(page, language, theme);
  });
  test('hydration preserves ' + language + '/' + theme, async ({ page }) => {
    await seed(page, language, theme);
    expect((await page.goto('/settings/'))?.status()).toBe(200);
    await expectPreference(page, language, theme);
    await expect(page.getByRole('heading', { level: 1, name: routes[3].headings[language] })).toBeVisible();
    expect(await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY)).toBe(serialized(language, theme));
  });
}

for (const language of ['en', 'vi']) for (const { path, headings } of routes) {
  test('direct navigation and reload: ' + language + ' ' + path, async ({ page }) => {
    await seed(page, language, 'light');
    expect((await page.goto(path))?.status()).toBe(200);
    await expect(page.getByRole('heading', { level: 1, name: headings[language] })).toBeVisible();
    await expectPreference(page, language, 'light');
    expect((await page.reload())?.status()).toBe(200);
    await expect(page.getByRole('heading', { level: 1, name: headings[language] })).toBeVisible();
    await expectPreference(page, language, 'light');
  });
}

test('client navigation covers exported navigation routes', async ({ page }) => {
  await page.goto('/');
  for (const { path, headings } of routes.slice(1, 4)) {
    await page.locator('nav a[href="' + path + '"]').click();
    await expect(page).toHaveURL(new RegExp(path.replaceAll('/', '\\/') + '$'));
    await expect(page.getByRole('heading', { level: 1, name: headings.en })).toBeVisible();
  }
  await page.goto('/check/');
  await expect(page.getByRole('heading', { level: 1, name: routes[4].headings.en })).toBeVisible();
});

test('a real second page receives the browser storage event', async ({ context }) => {
  const producer = await context.newPage(); const observer = await context.newPage();
  await Promise.all([producer.goto('/settings/'), observer.goto('/')]);
  await producer.getByRole('combobox', { name: 'Language' }).selectOption('vi');
  await producer.getByRole('button', { name: 'Tối' }).click();
  await expectPreference(observer, 'vi', 'dark');
  await expect(observer.getByRole('link', { name: 'Trang chủ' })).toBeVisible();
  expect(await observer.evaluate(key => localStorage.getItem(key), STORAGE_KEY)).toBe(serialized('vi', 'dark'));
});

test('malformed preference is harmless before and after hydration', async ({ page }) => {
  await page.addInitScript(key => localStorage.setItem(key, '{ definitely-not-json'), STORAGE_KEY);
  await page.goto('/settings/');
  await expectPreference(page, 'en', 'light');
  await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible();
  expect(await page.evaluate(key => localStorage.getItem(key), STORAGE_KEY)).toBe('{ definitely-not-json');
});

test('settings query survives direct load and refresh without mutation', async ({ page }) => {
  const mutations = [];
  page.on('request', request => { if (request.url().includes('/api/') && request.method() !== 'GET') mutations.push(request.method()); });
  await page.goto('/settings/?tab=models');
  await expect(page.getByRole('tab', { name: 'Models' })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('tabpanel', { name: 'Models' })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('tab', { name: 'Models' })).toHaveAttribute('aria-selected', 'true');
  expect(mutations).toEqual([]);
});

test('an emitted _next asset is served immutably', async ({ page, request }) => {
  await page.goto('/'); const source = await page.locator('script[src^="/_next/static/"]').first().getAttribute('src');
  expect(source).toBeTruthy(); const asset = await request.get(source); expect(asset.status()).toBe(200);
  expect(asset.headers()['cache-control']).toBe('public, max-age=31536000, immutable');
});

test('unknown UI route renders exported 404 with HTTP 404', async ({ page }) => {
  expect((await page.goto('/not-an-exported-page'))?.status()).toBe(404);
  await expect(page.getByRole('heading', { level: 1, name: 'Page not found' })).toBeVisible();
});

test('reserved API and asset paths never fall through to UI', async ({ request }) => {
  for (const path of [
    '/api/definitely-missing', '/api', '/images/definitely-missing.png',
    '/videos/definitely-missing.mp4', '/local_file/definitely-missing',
    '/openapi.json', '/docs', '/redoc',
  ]) {
    const response = await request.get(path); expect(response.status(), path).toBe(404);
    expect(await response.text(), path).not.toContain('Page not found');
  }
  const api = await request.get('/api/definitely-missing');
  expect(api.headers()['x-artemis-acceptance']).toBe('controlled');
  expect((await api.json()).detail).toContain('Controlled acceptance API');
  const asset = await request.get('/_next/static/chunks/definitely-missing.js');
  expect(asset.status()).toBe(404); expect(await asset.text()).not.toContain('Page not found');
});


test('controlled sample video supports full and single-range requests', async ({ request }) => {
  const expected = Buffer.from('00000018667479706d703432415254454d49532d616363657074616e63652d766964656f', 'hex');
  const full = await request.get('/videos/sample.mp4');
  expect(full.status()).toBe(200);
  expect(full.headers()['content-type']).toContain('video/mp4');
  expect(full.headers()['accept-ranges']).toBe('bytes');
  expect(Buffer.from(await full.body())).toEqual(expected);

  const range = await request.get('/videos/sample.mp4', { headers: { Range: 'bytes=4-11' } });
  expect(range.status()).toBe(206);
  expect(range.headers()['accept-ranges']).toBe('bytes');
  expect(range.headers()['content-range']).toBe('bytes 4-11/' + expected.length);
  expect(Buffer.from(await range.body())).toEqual(expected.subarray(4, 12));

  const invalid = await request.get('/videos/sample.mp4', { headers: { Range: 'bytes=999-1000' } });
  expect(invalid.status()).toBe(416);
  expect(invalid.headers()['content-range']).toBe('bytes */' + expected.length);
});

test('controlled device-live endpoint returns finite MJPEG frames', async ({ request }) => {
  const response = await request.get('/api/stream/device-live');
  expect(response.status()).toBe(200);
  expect(response.headers()['content-type']).toContain(
    'multipart/x-mixed-replace; boundary=artemis-acceptance-frame',
  );
  const body = Buffer.from(await response.body());
  expect(body.includes(Buffer.from('ARTEMIS-MJPEG-FRAME'))).toBe(true);
  expect(body.toString('latin1').match(/--artemis-acceptance-frame\r\n/g)).toHaveLength(2);
});

test('/admin keeps priority over the Next UI catch-all', async ({ page }) => {
  expect((await page.goto('/admin'))?.status()).toBe(200);
  await expect(page).toHaveTitle('Artemis Debug UI');
  await expect(page.getByRole('heading', { name: 'Run Task' })).toBeVisible();
  await expect(page.getByText('Page not found')).toHaveCount(0);
});
