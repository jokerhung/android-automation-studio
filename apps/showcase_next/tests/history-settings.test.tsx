import '@testing-library/jest-dom/vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '@/app/providers';
import { HistorySettingsPanel } from '@/features/settings/history-panel';
import type { HistorySettings } from '@/features/settings/api';

const json = (value: unknown, status = 200) => Promise.resolve(
  new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } }),
);
const base: HistorySettings = { media_retention_days: 0, history_retention_days: 0, last_run: null, version: 1 };
const sentBodies = (fetchMock: ReturnType<typeof vi.fn>, method: string) =>
  fetchMock.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === method)
    .map(([url, init]) => ({ url: String(url), body: JSON.parse(String((init as RequestInit).body)) }));

function mockApi(initial = base, handlers: Record<string, () => Promise<Response>> = {}) {
  let current = { ...initial };
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input); const method = init?.method ?? 'GET';
    const handler = handlers[`${method} ${url}`]; if (handler) return handler();
    if (url === '/api/settings/history' && method === 'GET') return json(current);
    if (url === '/api/settings/history' && method === 'PUT') {
      current = { ...current, ...JSON.parse(String(init?.body)), version: (current.version ?? 0) + 1 };
      return json(current);
    }
    return json({});
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
async function openPanel() {
  render(<AppProviders><HistorySettingsPanel /></AppProviders>);
  await screen.findByLabelText(/Delete screenshots and videos after/);
  return userEvent.setup();
}
const mediaInput = () => screen.getByLabelText(/Delete screenshots and videos after/);
const historyInput = () => screen.getByLabelText(/Delete task history after/);

beforeEach(() => { localStorage.clear(); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('History settings panel', () => {
  it('loads the saved retention days from the server', async () => {
    mockApi({ ...base, media_retention_days: 7, history_retention_days: 30 });
    await openPanel();
    expect(mediaInput()).toHaveValue(7);
    expect(historyInput()).toHaveValue(30);
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled();
    expect(screen.getByText('No cleanup has run yet.')).toBeInTheDocument();
  });

  it('saves both values after the destructive-change confirmation', async () => {
    const fetchMock = mockApi();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = await openPanel();
    await user.clear(mediaInput()); await user.type(mediaInput(), '7');
    await user.clear(historyInput()); await user.type(historyInput(), '30');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('History settings saved.')).toBeInTheDocument();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(sentBodies(fetchMock, 'PUT')).toEqual([{ url: '/api/settings/history', body: { media_retention_days: 7, history_retention_days: 30 } }]);
  });

  it('does not save when the user declines the confirmation', async () => {
    const fetchMock = mockApi();
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const user = await openPanel();
    await user.clear(mediaInput()); await user.type(mediaInput(), '7');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(sentBodies(fetchMock, 'PUT')).toHaveLength(0);
    expect(mediaInput()).toHaveValue(7);
  });

  it('turning a rule off or lengthening it needs no confirmation', async () => {
    const fetchMock = mockApi({ ...base, media_retention_days: 7, history_retention_days: 30 });
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = await openPanel();
    await user.clear(mediaInput()); await user.type(mediaInput(), '0');
    await user.clear(historyInput()); await user.type(historyInput(), '90');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByText('History settings saved.')).toBeInTheDocument();
    expect(confirm).not.toHaveBeenCalled();
    expect(sentBodies(fetchMock, 'PUT')[0]?.body).toEqual({ media_retention_days: 0, history_retention_days: 90 });
  });

  it('rejects invalid numbers and history shorter than media without calling the API', async () => {
    const fetchMock = mockApi();
    const user = await openPanel();
    await user.clear(mediaInput()); await user.type(mediaInput(), '4000');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Enter whole numbers from 0 to 3650.');

    await user.clear(mediaInput()); await user.type(mediaInput(), '30');
    await user.clear(historyInput()); await user.type(historyInput(), '7');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Task history must be kept at least as long as screenshots and videos.');
    expect(sentBodies(fetchMock, 'PUT')).toHaveLength(0);
  });

  it('shows the server error when saving fails and keeps the typed values', async () => {
    mockApi(base, { 'PUT /api/settings/history': () => json({ detail: 'Unable to save history settings.' }, 500) });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = await openPanel();
    await user.clear(mediaInput()); await user.type(mediaInput(), '7');
    await user.click(screen.getByRole('button', { name: 'Save' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to save history settings.');
    expect(mediaInput()).toHaveValue(7);
  });

  it('shows the last cleanup result', async () => {
    mockApi({ ...base, media_retention_days: 7, last_run: { status: 'completed', ran_at: 1_700_000_000, media_sessions_purged: 3, history_sessions_deleted: 2, bytes_freed: 5 * 1024 * 1024 } });
    await openPanel();
    expect(screen.getByText(/media removed from 3 task\(s\), 2 task\(s\) deleted, 5\.0 MB freed/)).toBeInTheDocument();
  });

  it('refuses to clean up while there are unsaved changes', async () => {
    const fetchMock = mockApi();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = await openPanel();
    await user.clear(mediaInput()); await user.type(mediaInput(), '7');
    await user.click(screen.getByRole('button', { name: 'Clean up now' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Save your changes before cleaning up.');
    expect(confirm).not.toHaveBeenCalled();
    expect(sentBodies(fetchMock, 'POST')).toHaveLength(0);
  });

  it('runs the cleanup after confirmation and reports what was freed', async () => {
    const settings = { ...base, media_retention_days: 7, history_retention_days: 30 };
    const result = { status: 'completed', ran_at: 1_700_000_000, media_sessions_purged: 4, history_sessions_deleted: 1, files_deleted: 9, bytes_freed: 2048, settings: { ...settings, last_run: { status: 'completed', ran_at: 1_700_000_000, media_sessions_purged: 4, history_sessions_deleted: 1, bytes_freed: 2048 } } };
    const fetchMock = mockApi(settings, { 'POST /api/settings/history/run': () => json(result) });
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = await openPanel();
    await user.click(screen.getByRole('button', { name: 'Clean up now' }));
    expect(await screen.findByText(/Cleanup finished: media removed from 4 task\(s\), 1 task\(s\) deleted, 2\.0 KB freed\./)).toBeInTheDocument();
    expect(confirm).toHaveBeenCalledTimes(1);
    expect(sentBodies(fetchMock, 'POST')).toHaveLength(1);
    await waitFor(() => expect(screen.getByText(/Last cleanup/)).toBeInTheDocument());
  });

  it('says there is nothing to clean up when both rules are off', async () => {
    mockApi(base, { 'POST /api/settings/history/run': () => json({ status: 'disabled', ran_at: 1 }) });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = await openPanel();
    await user.click(screen.getByRole('button', { name: 'Clean up now' }));
    expect(await screen.findByText('Both rules are off, so there is nothing to clean up.')).toBeInTheDocument();
  });

  it('surfaces a busy cleanup (409) from the server', async () => {
    mockApi(base, { 'POST /api/settings/history/run': () => json({ detail: 'A history cleanup is already running.' }, 409) });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const user = await openPanel();
    await user.click(screen.getByRole('button', { name: 'Clean up now' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('A history cleanup is already running.');
  });
});
