import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { defineConfig, devices } from '@playwright/test';

const port = Number(process.env.ARTEMIS_ACCEPTANCE_PORT ?? 4173);
const baseURL = process.env.ARTEMIS_ACCEPTANCE_BASE_URL ?? `http://127.0.0.1:${port}`;
const repositoryRoot = resolve(import.meta.dirname, '../..');
const localPython = process.platform === 'win32'
  ? resolve(repositoryRoot, '.venv/Scripts/python.exe')
  : resolve(repositoryRoot, '.venv/bin/python');
const acceptancePython = process.env.ARTEMIS_ACCEPTANCE_PYTHON ?? (existsSync(localPython) ? localPython : 'python');

export default defineConfig({
  testDir: './tests/acceptance',
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL,
    ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? { launchOptions: { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } } : {}),
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: process.env.ARTEMIS_ACCEPTANCE_BASE_URL ? undefined : {
    command: `"${acceptancePython}" scripts/serve-acceptance.py`,
    url: baseURL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
    env: { ...process.env, ARTEMIS_ACCEPTANCE_PORT: String(port) },
  },
});
