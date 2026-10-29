import '@testing-library/jest-dom/vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '@/app/providers';
import { GeneralSettings, ModelSettingsPanel } from '@/features/settings/general-model-panels';
import { EmailSettingsPanel } from '@/features/settings/email-panel';
import { AndroidSettingsPanel, SystemSettingsPanel } from '@/features/settings/android-system-panels';

const json = (value: unknown, status = 200) => Promise.resolve(
  new Response(JSON.stringify(value), {
    status,
    headers: { 'content-type': 'application/json' },
  }),
);

const readiness = {
  overall_ready: false,
  blocker_count: 3,
  passed_blocker_count: 2,
  active_device: {
    serial: 'device-1',
    state: 'device',
    model: 'Pixel 8',
    product: 'husky',
    android_version: '14',
    screen_resolution: '1080x2400',
    is_locked: false,
    is_emulator: false,
  },
  os_type: 'windows',
  timestamp: 2,
  probes: [{
    id: 'android_adb',
    category: 'device',
    title: 'Android device',
    status: 'pass',
    is_blocker: true,
    summary: 'Device connected',
    description: 'ADB and authorization are ready.',
    actions: [],
    metadata: {
      devices: [{ serial: 'device-1', state: 'device', model: 'Pixel 8' }],
      installed_avds: ['Pixel_8_API_34'],
    },
  }],
};

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  localStorage.clear();
});

describe('P2 Settings migration', () => {
  it('loads Windows capability and sends one explicit toggle mutation', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((_input, init) =>
      init?.method === 'PUT'
        ? json({ supported: true, enabled: true, port: 8000 })
        : json({ supported: true, enabled: false, port: 8000 }),
    );

    render(<AppProviders><GeneralSettings /></AppProviders>);
    const toggle = await screen.findByRole('switch', { name: /Start with Windows/i });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    await userEvent.click(toggle);
    await waitFor(() => expect(toggle).toHaveAttribute('aria-checked', 'true'));

    const mutations = fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT');
    expect(mutations).toHaveLength(1);
    expect(String(mutations[0]?.[0])).toBe('/api/system/windows-startup');
    expect(JSON.parse(String(mutations[0]?.[1]?.body))).toEqual({ enabled: true });
  });

  it('validates and confirms Models, then reconnects without replaying the mutation', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input);
      if (url === '/api/settings/model' && (!init?.method || init.method === 'GET')) {
        return json({
          provider: 'openai',
          default_model: 'primary',
          fallback_model: 'backup',
          fallback_provider: 'openai',
          base_url: '',
          fallback_url: '',
          version: 'v1',
          keys_configured: { openai: true },
          node_overrides: [],
        });
      }
      if (url === '/api/settings/model' && init?.method === 'PUT') {
        return json({ status: 'restarting', previous_pid: 10 });
      }
      if (url === '/api/system/server-status') return json({ current_pid: 11 });
      throw new Error(url);
    });

    render(<AppProviders><ModelSettingsPanel /></AppProviders>);
    expect(await screen.findByLabelText(/API key/)).toHaveValue('');
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    await user.clear(screen.getByLabelText('Default model'));
    await user.click(screen.getByRole('button', { name: 'Save and restart' }));
    expect(screen.getByRole('alert')).toHaveTextContent(/required/i);
    await user.type(screen.getByLabelText('Default model'), 'new-model');
    await user.click(screen.getByRole('button', { name: 'Save and restart' }));
    expect(screen.getByRole('alertdialog')).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(0);
    await user.click(screen.getByRole('button', { name: 'Save and restart now' }));
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1);
    });
    await vi.advanceTimersByTimeAsync(2500);
    await waitFor(() => expect(screen.getByText(/restarted and reconnected/i)).toBeInTheDocument());
    expect(fetchMock.mock.calls.filter(([, init]) => init?.method === 'PUT')).toHaveLength(1);
  });

  it('keeps Email passwords write-only and supports save, connection test, and send test', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input);
      if (url === '/api/settings/email' && init?.method === 'PUT') {
        return json({
          enabled: true,
          smtp_host: 'smtp.example.com',
          smtp_port: 587,
          security: 'starttls',
          sender_email: 'a@example.com',
          sender_name: 'ARTEMIS',
          smtp_username: 'a@example.com',
          password_configured: true,
          version: 3,
        });
      }
      if (url === '/api/settings/email') {
        return json({
          enabled: true,
          smtp_host: 'smtp.example.com',
          smtp_port: 587,
          security: 'starttls',
          sender_email: 'a@example.com',
          sender_name: 'ARTEMIS',
          smtp_username: 'a@example.com',
          password_configured: true,
          test_recipient: 'test@example.com',
          version: 2,
        });
      }
      if (url.endsWith('/test-connection')) return json({ success: true, message: 'SMTP connection succeeded.' });
      if (url.endsWith('/send-test')) return json({ success: true, message: 'Test email accepted by SMTP.' });
      throw new Error(url);
    });

    render(<AppProviders><EmailSettingsPanel /></AppProviders>);
    expect(await screen.findByLabelText('Password')).toHaveValue('');
    await userEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(screen.getByText('Email settings saved.')).toBeInTheDocument());
    const save = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
    expect(JSON.parse(String(save?.[1]?.body))).not.toHaveProperty('password');
    await userEvent.click(screen.getByRole('button', { name: 'Test connection' }));
    expect(await screen.findByText('SMTP connection succeeded.')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Send test email' }));
    expect(await screen.findByText('Test email accepted by SMTP.')).toBeInTheDocument();
    expect(localStorage.length).toBe(0);
  });

  it('covers Android server, device, wireless, and emulator operations', async () => {
    const localEndpoint = {
      host: '127.0.0.1',
      port: 5037,
      socket: 'tcp:127.0.0.1:5037',
      identity: 'local',
      mode: 'local',
      is_local_default: true,
    } as const;
    const remoteEndpoint = {
      host: '10.0.0.2',
      port: 5038,
      socket: 'tcp:10.0.0.2:5038',
      identity: 'remote',
      mode: 'remote',
      is_local_default: false,
    } as const;
    const idleEmulator = {
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
    const readyEmulator = {
      ...idleEmulator,
      avd_name: 'Pixel_8_API_34',
      status: 'ready',
      pid: 12,
      serial: 'emulator-5554',
      stage_message: 'Ready',
      progress_percent: 100,
      started_at: 1,
      elapsed_seconds: 5,
      can_retry: false,
    };

    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input);
      if (url === '/api/system/readiness' || url === '/api/system/readiness?force=true') {
        return json(readiness);
      }
      if (url === '/api/system/adb/server' && !init?.method) {
        return json({ endpoint: localEndpoint });
      }
      if (url === '/api/system/emulator/status') return json(idleEmulator);
      if (url.endsWith('/adb/server/probe')) {
        return json({
          connection_result: {
            success: true,
            message: 'Endpoint reachable.',
            endpoint: remoteEndpoint,
            devices: [],
          },
        });
      }
      if (url.endsWith('/adb/server/connect')) {
        return json({
          connection_result: {
            success: true,
            message: 'Remote active.',
            endpoint: remoteEndpoint,
            devices: [],
          },
          report: readiness,
        });
      }
      if (url.startsWith('/api/system/adb/server/local')) {
        return json({
          connection_result: {
            success: true,
            message: 'Local active.',
            endpoint: localEndpoint,
            devices: [],
          },
          report: readiness,
        });
      }
      if (url === '/api/system/devices/select' || url === '/api/system/adb/connect') {
        return json({ report: readiness });
      }
      if (url === '/api/system/emulator/launch') return json(readyEmulator);
      throw new Error(`Unexpected request: ${url}`);
    });

    render(<AppProviders><AndroidSettingsPanel /></AppProviders>);
    const user = userEvent.setup();
    expect(await screen.findByRole('button', { name: /Pixel 8/ })).toBeInTheDocument();

    await user.clear(screen.getByLabelText('Host'));
    await user.type(screen.getByLabelText('Host'), '10.0.0.2');
    await user.clear(screen.getByLabelText('Port'));
    await user.type(screen.getByLabelText('Port'), '5038');
    await user.click(screen.getByRole('button', { name: 'Test endpoint' }));
    expect(await screen.findByText('Endpoint reachable.')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Use remote server' }));
    expect(await screen.findByText('Remote active.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Use local ADB' }));
    expect(await screen.findByText('Local active.')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /Pixel 8/ }));
    await user.type(screen.getByLabelText('Wireless device host'), '192.168.1.20');
    await user.click(screen.getByRole('button', { name: 'Connect device' }));
    await user.click(screen.getByRole('button', { name: 'Pixel_8_API_34' }));

    await waitFor(() => {
      expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/system/emulator/launch')).toBe(true);
    });
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/system/devices/select')).toBe(true);
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/system/adb/connect')).toBe(true);
  });

  it('polls active emulator states once per second without overlap and pauses when hidden', async () => {
    vi.useFakeTimers();
    const idle = {
      avd_name: 'Pixel_8_API_34', status: 'starting', pid: 12, serial: null,
      stage_message: 'Starting', progress_percent: 10, started_at: 1, elapsed_seconds: 1,
      error: null, logs: ['launching'], can_retry: false,
    };
    let resolvePoll: ((response: Response) => void) | undefined;
    const pendingPoll = new Promise<Response>((resolve) => { resolvePoll = resolve; });
    let statusCalls = 0;
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input);
      if (url === '/api/system/readiness') return json(readiness);
      if (url === '/api/system/adb/server') return json({ endpoint: { host: '127.0.0.1', port: 5037, socket: 'tcp:127.0.0.1:5037', mode: 'local', is_local_default: true } });
      if (url === '/api/system/emulator/status') {
        statusCalls += 1;
        return statusCalls === 1 ? json(idle) : pendingPoll;
      }
      throw new Error(url);
    });

    const view = render(<AppProviders><AndroidSettingsPanel /></AppProviders>);
    await act(async () => { await Promise.resolve(); });
    expect(statusCalls).toBe(1);

    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    expect(statusCalls).toBe(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(5000); });
    expect(statusCalls).toBe(2);

    Object.defineProperty(document, 'hidden', { configurable: true, value: true });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    expect(resolvePoll).toBeDefined();
    resolvePoll!(await json({ ...idle, status: 'booting', stage_message: 'Booting' }));
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(3000); });
    expect(statusCalls).toBe(2);

    Object.defineProperty(document, 'hidden', { configurable: true, value: false });
    act(() => document.dispatchEvent(new Event('visibilitychange')));
    await act(async () => { await Promise.resolve(); });
    expect(statusCalls).toBe(3);
    view.unmount();
  });

  it('renders failed emulator details and supports retry and dismiss', async () => {
    const failed = {
      avd_name: 'Pixel_8_API_34', status: 'failed', pid: null, serial: null,
      stage_message: 'Launch failed', progress_percent: 20, started_at: 1, elapsed_seconds: 3,
      error: 'ADB never appeared', logs: ['spawned emulator', 'adb timeout'], can_retry: true,
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input);
      if (url === '/api/system/readiness') return json(readiness);
      if (url === '/api/system/adb/server') return json({ endpoint: { host: '127.0.0.1', port: 5037, socket: 'tcp:127.0.0.1:5037', mode: 'local', is_local_default: true } });
      if (url === '/api/system/emulator/status' || url === '/api/system/emulator/launch') return json(failed);
      if (url === '/api/system/emulator/dismiss') return json({});
      throw new Error(url);
    });

    render(<AppProviders><AndroidSettingsPanel /></AppProviders>);
    expect(await screen.findByText('ADB never appeared')).toBeInTheDocument();
    expect(screen.getByLabelText('Emulator logs')).toHaveTextContent('spawned emulator');
    await userEvent.click(screen.getByRole('button', { name: 'Retry launch' }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/system/emulator/launch')).toBe(true));
    await userEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    await waitFor(() => expect(screen.queryByText('ADB never appeared')).not.toBeInTheDocument());
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/system/emulator/dismiss')).toBe(true);
  });

  it('renders System diagnostics and the ready launch CTA', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(() => json({
      ...readiness,
      overall_ready: true,
      probes: [
        ...readiness.probes,
        { id: 'python_runtime', category: 'runtime', title: 'Python runtime', status: 'pass', is_blocker: true, summary: 'Python ready', description: 'Supported runtime detected.', metadata: {}, actions: [] },
      ],
    }));

    render(<AppProviders><SystemSettingsPanel /></AppProviders>);
    expect(await screen.findByText('Python runtime')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Launch a task' })).toHaveAttribute('href', '/');
    await userEvent.click(screen.getByRole('button', { name: 'Run diagnostics' }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([url]) => String(url) === '/api/system/readiness?force=true')).toBe(true));
  });
});
