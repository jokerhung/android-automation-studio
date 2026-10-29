import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/lib/api/client';
import type { TaskSchedule } from '@/features/schedules/types';

const emailApi = vi.hoisted(() => ({ email: vi.fn() }));
const api = vi.hoisted(() => ({
  list: vi.fn(), devices: vi.fn(), status: vi.fn(), preview: vi.fn(), get: vi.fn(),
  create: vi.fn(), update: vi.fn(), pause: vi.fn(), resume: vi.fn(), delete: vi.fn(),
  runNow: vi.fn(), runs: vi.fn(), retryEmail: vi.fn(), emailReportUrl: vi.fn(),
}));
vi.mock('@/features/schedules/api', () => ({ schedulesApi: api }));
vi.mock('@/features/settings/api', () => ({ settingsApi: emailApi }));
vi.mock('@/app/providers', async () => { const { translate } = await import('@/lib/i18n/translate'); return { useAppPreferences: () => ({ preferences: { language: 'en' }, t: (key: Parameters<typeof translate>[1], values?: Parameters<typeof translate>[2]) => translate('en', key, values) }) }; });
vi.mock('@/components/page-shell', () => ({ PageShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main> }));
vi.mock('next/link', () => ({ default: ({ children, href }: { children: React.ReactNode; href: string }) => <a href={href}>{children}</a> }));

import { TaskSchedulePage } from '@/features/schedules/task-schedule-page';

const schedule: TaskSchedule = {
  id: 'schedule-1', version: 4, name: 'Daily check', goal: 'Check app', profile: 'flash',
  device_serial: 'device-1', enabled: true, schedule_type: 'interval', interval_minutes: 15,
  time_of_day: null, weekdays: [], timezone: 'UTC', email_enabled: false,
};
const occurrences = Array.from({ length: 5 }, (_, index) => `2026-09-${10 + index}T07:15:45Z`);
function deferred<T>() { let resolve!: (value: T) => void; let reject!: (reason?: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }

beforeEach(() => {
  vi.clearAllMocks();
  api.list.mockResolvedValue([schedule]);
  api.devices.mockResolvedValue([{ serial: 'device-1', name: 'Pixel' }]);
  api.status.mockResolvedValue({ healthy: true });
  api.runs.mockResolvedValue({ runs: [] });
  emailApi.email.mockResolvedValue({ enabled: true, smtp_host: 'smtp.example.com', smtp_port: 587, security: 'starttls', sender_email: 'sender@example.com', sender_name: 'ARTEMIS', smtp_username: 'sender@example.com', password_configured: true, version: 2 });
});
async function openEditor() {
  render(<TaskSchedulePage />);
  await screen.findByText('Daily check');
  await userEvent.setup().click(screen.getByRole('button', { name: '✎' }));
  return screen.getByRole('dialog');
}

describe('Task schedule page', () => {
  it('shows ready before email scheduling and saves only the schedule contract', async () => {
    api.preview.mockResolvedValue(occurrences); api.update.mockResolvedValue({ ...schedule, version: 5, email_enabled: true, recipient_email: 'ops@example.com', email_subject: 'Daily result' });
    const dialog = await openEditor(); const user = userEvent.setup();
    await user.click(within(dialog).getByRole('checkbox', { name: 'Send result email' }));
    expect(await within(dialog).findByText('Email delivery is enabled and SMTP credentials are configured.')).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText('Recipient email'), 'ops@example.com');
    await user.type(within(dialog).getByLabelText('Subject'), 'Daily result');
    await user.click(within(dialog).getByRole('button', { name: 'Preview next 5' }));
    await waitFor(() => expect(within(dialog).getAllByRole('listitem')).toHaveLength(5));
    await user.click(within(dialog).getByRole('button', { name: 'Save schedule' }));
    await waitFor(() => expect(api.update).toHaveBeenCalledWith(schedule, expect.objectContaining({ email_enabled: true, recipient_email: 'ops@example.com', email_subject: 'Daily result' })));
    expect(emailApi.email).toHaveBeenCalledTimes(1); expect(api.create).not.toHaveBeenCalled();
  });

  it('shows not configured, preserves the draft, allows preview, and blocks save', async () => {
    emailApi.email.mockResolvedValueOnce({ enabled: false, smtp_host: '', smtp_port: 587, security: 'starttls', sender_email: '', sender_name: 'ARTEMIS', smtp_username: '', password_configured: false, version: 0 });
    api.preview.mockResolvedValue(occurrences);
    const dialog = await openEditor(); const user = userEvent.setup();
    const goal = within(dialog).getByLabelText('Task instructions'); await user.clear(goal); await user.type(goal, 'Unsaved email draft');
    await user.click(within(dialog).getByRole('checkbox', { name: 'Send result email' }));
    expect(await within(dialog).findByText(/Email delivery is disabled or SMTP credentials are incomplete/)).toBeInTheDocument();
    await user.type(within(dialog).getByLabelText('Recipient email'), 'ops@example.com');
    await user.click(within(dialog).getByRole('button', { name: 'Preview next 5' }));
    await waitFor(() => expect(within(dialog).getAllByRole('listitem')).toHaveLength(5));
    await user.click(within(dialog).getByRole('button', { name: 'Save schedule' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Email delivery is disabled or SMTP credentials are incomplete.');
    expect(goal).toHaveValue('Unsaved email draft'); expect(api.create).not.toHaveBeenCalled();
  });

  it('distinguishes a readiness request error and preserves the draft', async () => {
    emailApi.email.mockRejectedValueOnce(new ApiError(500, 'Unable to read SMTP settings.', { detail: 'Unable to read SMTP settings.' }, '/api/settings/email'));
    const dialog = await openEditor(); const user = userEvent.setup();
    const goal = within(dialog).getByLabelText('Task instructions'); await user.clear(goal); await user.type(goal, 'Keep this error draft');
    await user.click(within(dialog).getByRole('checkbox', { name: 'Send result email' }));
    expect(await within(dialog).findByText(/SMTP readiness could not be checked/)).toBeInTheDocument();
    expect(goal).toHaveValue('Keep this error draft'); expect(api.create).not.toHaveBeenCalled();
  });

  it('previews interval, daily, and weekly rules with seconds, timezone, and ISO weekdays', async () => {
    api.preview.mockResolvedValue(occurrences);
    const dialog = await openEditor();
    const user = userEvent.setup();
    const previewButton = within(dialog).getByRole('button', { name: 'Preview next 5' });

    await user.click(previewButton);
    await waitFor(() => expect(api.preview).toHaveBeenLastCalledWith(expect.objectContaining({
      schedule_type: 'interval', interval_minutes: 15, time_of_day: null, weekdays: [], timezone: 'UTC', count: 5,
    })));

    await user.click(within(dialog).getByRole('radio', { name: 'Daily' }));
    fireEvent.change(within(dialog).getByLabelText('Time (HH:mm:ss)'), { target: { value: '08:30:05' } });
    await user.clear(within(dialog).getByLabelText('Timezone'));
    await user.type(within(dialog).getByLabelText('Timezone'), 'Asia/Bangkok');
    await user.click(previewButton);
    await waitFor(() => expect(api.preview).toHaveBeenLastCalledWith(expect.objectContaining({
      schedule_type: 'daily', interval_minutes: null, time_of_day: '08:30:05', weekdays: [], timezone: 'Asia/Bangkok', count: 5,
    })));

    await user.click(within(dialog).getByRole('radio', { name: 'Weekly' }));
    fireEvent.change(within(dialog).getByLabelText('Time (HH:mm:ss)'), { target: { value: '23:59:47' } });
    await user.click(within(dialog).getByRole('checkbox', { name: 'Wed' }));
    await user.click(within(dialog).getByRole('checkbox', { name: 'Mon' }));
    await user.click(within(dialog).getByRole('checkbox', { name: 'Sun' }));
    await user.click(previewButton);
    await waitFor(() => expect(api.preview).toHaveBeenLastCalledWith(expect.objectContaining({
      schedule_type: 'weekly', interval_minutes: null, time_of_day: '23:59:47', weekdays: [1, 3, 7], timezone: 'Asia/Bangkok', count: 5,
    })));
  });

  it('validates required fields, interval bounds, and weekly weekday selection before preview or save', async () => {
    const dialog = await openEditor();
    const user = userEvent.setup();
    const previewButton = within(dialog).getByRole('button', { name: 'Preview next 5' });
    const saveButton = within(dialog).getByRole('button', { name: 'Save schedule' });

    await user.clear(within(dialog).getByLabelText('Schedule name'));
    await user.click(previewButton);
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Complete all required fields.');
    expect(api.preview).not.toHaveBeenCalled();

    await user.type(within(dialog).getByLabelText('Schedule name'), 'Restored name');
    await user.click(within(dialog).getByRole('radio', { name: 'Interval' }));
    await user.clear(within(dialog).getByLabelText('Repeat every (minutes)'));
    fireEvent.change(within(dialog).getByLabelText('Repeat every (minutes)'), { target: { value: '0' } });
    await user.click(saveButton);
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('from 1 to 10080 minutes');
    expect(api.update).not.toHaveBeenCalled();

    await user.click(within(dialog).getByRole('radio', { name: 'Weekly' }));
    fireEvent.change(within(dialog).getByLabelText('Time (HH:mm:ss)'), { target: { value: '09:10:11' } });
    await user.click(previewButton);
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Select at least one weekday.');
    expect(api.preview).not.toHaveBeenCalled();
  });

  it('invalidates an in-flight preview by generation and requires exactly five current occurrences', async () => {
    const first = deferred<string[]>();
    api.preview.mockReturnValueOnce(first.promise).mockResolvedValueOnce(occurrences.slice(0, 4)).mockResolvedValueOnce(occurrences);
    const dialog = await openEditor();
    const user = userEvent.setup();
    await user.click(within(dialog).getByRole('button', { name: 'Preview next 5' }));
    await user.type(within(dialog).getByLabelText('Task instructions'), ' changed');
    first.resolve(occurrences);
    await waitFor(() => expect(api.preview).toHaveBeenCalledTimes(1));
    expect(within(dialog).queryAllByRole('listitem')).toHaveLength(0);

    await user.click(within(dialog).getByRole('button', { name: 'Preview next 5' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('exactly five');
    expect(within(dialog).queryAllByRole('listitem')).toHaveLength(0);

    await user.click(within(dialog).getByRole('button', { name: 'Preview next 5' }));
    await waitFor(() => expect(within(dialog).getAllByRole('listitem')).toHaveLength(5));
    expect(api.preview.mock.calls[2]?.[0]).toMatchObject({ count: 5, goal: 'Check app changed' });
  });

  it('keeps the draft on 409 and reloads only the version before an explicit retry', async () => {
    api.preview.mockResolvedValue(occurrences);
    api.update.mockRejectedValueOnce(new ApiError(409, 'Version conflict', { detail: 'Version conflict' }, '/api/schedules/schedule-1'))
      .mockResolvedValueOnce({ ...schedule, version: 6, goal: 'My local draft' });
    api.get.mockResolvedValue({ ...schedule, version: 5, goal: 'Server copy' });
    const dialog = await openEditor();
    const user = userEvent.setup();
    const goal = within(dialog).getByLabelText('Task instructions');
    await user.clear(goal); await user.type(goal, 'My local draft');
    await user.click(within(dialog).getByRole('button', { name: 'Preview next 5' }));
    await waitFor(() => expect(within(dialog).getAllByRole('listitem')).toHaveLength(5));
    await user.click(within(dialog).getByRole('button', { name: 'Save schedule' }));

    expect(await within(dialog).findByRole('alert')).toHaveTextContent('draft was kept');
    expect(goal).toHaveValue('My local draft');
    expect(api.update).toHaveBeenCalledTimes(1);
    await user.click(within(dialog).getByRole('button', { name: 'Reload version for retry' }));
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('schedule-1'));
    expect(goal).toHaveValue('My local draft');
    expect(api.update).toHaveBeenCalledTimes(1);

    await user.click(within(dialog).getByRole('button', { name: 'Save schedule' }));
    await waitFor(() => expect(api.update).toHaveBeenCalledTimes(2));
    expect(api.update.mock.calls[1]?.[0]).toMatchObject({ id: 'schedule-1', version: 5 });
    expect(api.update.mock.calls[1]?.[1]).toMatchObject({ goal: 'My local draft' });
  });

  it('closes only from the backdrop itself, not clicks inside the dialog', async () => {
    const dialog = await openEditor();
    const backdrop = screen.getByTestId('schedule-backdrop');
    fireEvent.click(dialog);
    expect(screen.getByRole('dialog')).toBeInTheDocument();
    fireEvent.click(backdrop);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('moves focus into the editor, traps Tab in both directions, and restores its opener after Escape', async () => {
    render(<TaskSchedulePage />);
    await screen.findByText('Daily check');
    const user = userEvent.setup();
    const opener = screen.getByRole('button', { name: '✎' });
    await user.click(opener);
    const dialog = screen.getByRole('dialog');
    const close = within(dialog).getByRole('button', { name: 'Close' });
    const save = within(dialog).getByRole('button', { name: 'Save schedule' });

    expect(close).toHaveFocus();
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(save).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: '✎' })).toHaveFocus());
  });

  it('applies focus entry, trapping, Escape close, and restoration to the history dialog', async () => {
    render(<TaskSchedulePage />);
    await screen.findByText('Daily check');
    const user = userEvent.setup();
    const opener = screen.getByRole('button', { name: 'History' });
    await user.click(opener);
    const dialog = screen.getByRole('dialog');
    const close = within(dialog).getByRole('button', { name: 'Close' });

    expect(close).toHaveFocus();
    await user.tab();
    expect(close).toHaveFocus();
    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(close).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'History' })).toHaveFocus());
  });
});
