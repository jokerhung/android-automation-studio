import '@testing-library/jest-dom/vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppProviders, useAppPreferences } from '@/app/providers';
import { EmailSettingsPanel } from '@/features/settings/email-panel';
import { AndroidSettingsPanel, SystemSettingsPanel } from '@/features/settings/android-system-panels';
import { UI_PREFERENCES_STORAGE_KEY } from '@/lib/preferences/preferences';

const respond = (body: unknown) => Promise.resolve(new Response(JSON.stringify(body), {
  status: 200,
  headers: { 'content-type': 'application/json' },
}));

const emailSettings = {
  enabled: true,
  smtp_host: 'smtp.example.com',
  smtp_port: 587,
  security: 'starttls',
  sender_email: 'sender@example.com',
  sender_name: 'ARTEMIS',
  smtp_username: 'sender@example.com',
  password_configured: true,
  test_recipient: 'test@example.com',
  version: 2,
};

const readiness = {
  overall_ready: true,
  blocker_count: 0,
  passed_blocker_count: 1,
  active_device: null,
  timestamp: 1,
  probes: [{
    id: 'android_adb',
    category: 'device',
    title: 'Android device',
    status: 'pass',
    is_blocker: true,
    summary: 'ADB ready',
    description: 'ADB is available.',
    actions: [],
    metadata: { devices: [], installed_avds: [] },
  }],
};

const emulator = {
  avd_name: null,
  status: 'idle',
  pid: null,
  serial: null,
  stage_message: 'Idle',
  progress_percent: 0,
  started_at: null,
  elapsed_seconds: 0,
  error: null,
  logs: [],
  can_retry: true,
};

function PreferenceSwitches() {
  const { preferences, setLanguage, setTheme } = useAppPreferences();
  return <>
    <button type="button" data-testid="switch-language" onMouseDown={(event) => event.preventDefault()} onClick={() => setLanguage(preferences.language === 'en' ? 'vi' : 'en')}>switch language</button>
    <button type="button" data-testid="switch-theme" onMouseDown={(event) => event.preventDefault()} onClick={() => setTheme(preferences.theme === 'light' ? 'dark' : 'light')}>switch theme</button>
  </>;
}

function mockSettingsFetch() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
    const url = String(input);
    const method = init?.method ?? 'GET';
    if (method !== 'GET') throw new Error(`Unexpected mutation: ${method} ${url}`);
    if (url === '/api/settings/email') return respond(emailSettings);
    if (url === '/api/system/readiness' || url === '/api/system/readiness?force=true') return respond(readiness);
    if (url === '/api/system/adb/server') return respond({ endpoint: { host: '127.0.0.1', port: 5037, socket: 'tcp:127.0.0.1:5037', mode: 'local', is_local_default: true } });
    if (url === '/api/system/emulator/status') return respond(emulator);
    if (url === '/api/status') return respond({});
    if (url === '/api/sessions') return respond([]);
    throw new Error(`Unexpected GET: ${url}`);
  });
}

const copy = {
  en: { email: 'Email notifications', host: 'SMTP host', password: 'Password', android: 'ADB server', system: 'System diagnostics' },
  vi: { email: 'Thông báo qua email', host: 'Máy chủ SMTP', password: 'Mật khẩu', android: 'Máy chủ ADB', system: 'Chẩn đoán hệ thống' },
} as const;

afterEach(() => {
  vi.restoreAllMocks();
  localStorage.clear();
});

describe('settings locale and theme integration', () => {
  it.each([
    ['en', 'light'],
    ['en', 'dark'],
    ['vi', 'light'],
    ['vi', 'dark'],
  ] as const)('preserves the Email draft and focus for %s/%s preference changes', async (language, theme) => {
    localStorage.setItem(UI_PREFERENCES_STORAGE_KEY, JSON.stringify({ version: 1, language, theme }));
    const fetchMock = mockSettingsFetch();

    render(<AppProviders>
      <PreferenceSwitches />
      <EmailSettingsPanel />
      <AndroidSettingsPanel />
      <SystemSettingsPanel />
    </AppProviders>);

    const initial = copy[language];
    expect(await screen.findByRole('heading', { name: initial.email })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: initial.android })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: initial.system })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('lang', language);
    expect(document.documentElement).toHaveAttribute('data-theme', theme);

    const host = screen.getByLabelText(initial.host);
    const password = screen.getByLabelText(initial.password);
    const user = userEvent.setup();
    await user.clear(host);
    await user.type(host, 'dirty.smtp.example');
    await user.type(password, 'dirty-secret');
    expect(password).toHaveFocus();

    await user.click(screen.getByTestId('switch-language'));
    await user.click(screen.getByTestId('switch-theme'));
    const localLanguage = language === 'en' ? 'vi' : 'en';
    const localTheme = theme === 'light' ? 'dark' : 'light';
    const local = copy[localLanguage];
    expect(await screen.findByRole('heading', { name: local.email })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: local.android })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: local.system })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('lang', localLanguage);
    expect(document.documentElement).toHaveAttribute('data-theme', localTheme);
    expect(screen.getByLabelText(local.host)).toHaveValue('dirty.smtp.example');
    expect(screen.getByLabelText(local.password)).toHaveValue('dirty-secret');
    expect(password).toHaveFocus();

    act(() => window.dispatchEvent(new StorageEvent('storage', {
      key: UI_PREFERENCES_STORAGE_KEY,
      newValue: JSON.stringify({ version: 1, language, theme }),
    })));
    expect(await screen.findByRole('heading', { name: initial.email })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: initial.android })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: initial.system })).toBeInTheDocument();
    expect(document.documentElement).toHaveAttribute('lang', language);
    expect(document.documentElement).toHaveAttribute('data-theme', theme);
    expect(screen.getByLabelText(initial.host)).toHaveValue('dirty.smtp.example');
    expect(screen.getByLabelText(initial.password)).toHaveValue('dirty-secret');
    expect(password).toHaveFocus();

    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) => String(url) === '/api/settings/email')).toHaveLength(1);
      expect(fetchMock.mock.calls.filter(([url]) => String(url) === '/api/system/emulator/status')).toHaveLength(1);
    });
  });
});
