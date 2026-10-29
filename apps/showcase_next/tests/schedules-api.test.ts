import { afterEach, describe, expect, it, vi } from 'vitest';
import { normalizeDevices, normalizePreview, normalizeScheduleStatus, schedulesApi } from '@/features/schedules/api';
import type { ScheduleDraft, TaskSchedule } from '@/features/schedules/types';

afterEach(() => vi.unstubAllGlobals());
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status, headers: { 'content-type': 'application/json' } });
const daily: ScheduleDraft = { name: 'Daily check', goal: 'Check app', profile: 'flash', device_serial: 'device-1', schedule_type: 'daily', time_of_day: '08:30:05', timezone: 'Asia/Bangkok', enabled: true };
const schedule: TaskSchedule = { ...daily, id: 'schedule/1', version: 4 };

describe('schedule API', () => {
  it('implements list, get, create, and optimistic update/delete CRUD', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(json({ schedules: [schedule] }))
      .mockResolvedValueOnce(json(schedule))
      .mockResolvedValueOnce(json({ ...schedule, id: 'created' }, 201))
      .mockResolvedValueOnce(json({ ...schedule, version: 5, name: 'Changed' }))
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);
    await expect(schedulesApi.list()).resolves.toEqual([schedule]);
    await schedulesApi.get(schedule.id);
    await schedulesApi.create(daily);
    await schedulesApi.update(schedule, { name: 'Changed' });
    await schedulesApi.delete(schedule);
    expect(fetchMock.mock.calls.map(call => call[0])).toEqual(['/api/schedules', '/api/schedules/schedule%2F1', '/api/schedules', '/api/schedules/schedule%2F1', '/api/schedules/schedule%2F1?expected_version=4']);
    expect(JSON.parse(String(fetchMock.mock.calls[2]?.[1]?.body))).toMatchObject({ time_of_day: '08:30:05', timezone: 'Asia/Bangkok' });
    expect(JSON.parse(String(fetchMock.mock.calls[3]?.[1]?.body))).toEqual({ name: 'Changed', expected_version: 4 });
    expect(fetchMock.mock.calls[4]?.[1]).toEqual(expect.objectContaining({ method: 'DELETE', credentials: 'same-origin' }));
  });

  it('uses expected_version when pausing and resuming', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(json(schedule)));
    vi.stubGlobal('fetch', fetchMock);
    await schedulesApi.pause(schedule);
    await schedulesApi.resume(schedule);
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ enabled: false, expected_version: 4 });
    expect(JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body))).toEqual({ enabled: true, expected_version: 4 });
  });

  it('preserves seconds, timezone, and ISO weekdays in preview and normalizes response variants without imposing a limit', async () => {
    const weekly: ScheduleDraft = { ...daily, schedule_type: 'weekly', time_of_day: '09:15:45', weekdays: [1, 3, 7], timezone: 'Europe/Paris' };
    const occurrences = Array.from({ length: 6 }, (_, index) => `2026-09-${10 + index}T07:15:45Z`);
    const fetchMock = vi.fn().mockResolvedValue(json({ occurrences }));
    vi.stubGlobal('fetch', fetchMock);
    await expect(schedulesApi.preview({ ...weekly, count: 6 })).resolves.toEqual(occurrences);
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(body).toMatchObject({ time_of_day: '09:15:45', timezone: 'Europe/Paris', weekdays: [1, 3, 7], count: 6 });
    expect(normalizePreview({ due_times: ['a'] })).toEqual(['a']);
    expect(normalizePreview({ next_runs: ['b'] })).toEqual(['b']);
    expect(normalizePreview(['c'])).toEqual(['c']);
  });

  it('posts the caller idempotency key to run-now and loads paged run history', async () => {
    const run = { id: 'run/1', schedule_id: schedule.id, due_at: '2026-09-15T01:30:00Z', trigger: 'manual', status: 'queued' } as const;
    const fetchMock = vi.fn().mockResolvedValueOnce(json({ created: true, run })).mockResolvedValueOnce(json({ runs: [run], total: 1, limit: 25, offset: 10 }));
    vi.stubGlobal('fetch', fetchMock);
    await expect(schedulesApi.runNow(schedule.id, 'click-123')).resolves.toEqual(run);
    await expect(schedulesApi.runs(schedule.id, { limit: 25, offset: 10 })).resolves.toMatchObject({ runs: [run], total: 1 });
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/schedules/schedule%2F1/run-now');
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ idempotency_key: 'click-123' });
    expect(fetchMock.mock.calls[1]?.[0]).toBe('/api/schedules/schedule%2F1/runs?limit=25&offset=10');
  });

  it('retries email via its notification endpoint and never calls run-now', async () => {
    const fetchMock = vi.fn().mockResolvedValue(json({ run_id: 'run/1', status: 'pending' }));
    vi.stubGlobal('fetch', fetchMock);
    await schedulesApi.retryEmail('schedule/1', 'run/1');
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/schedules/schedule%2F1/runs/run%2F1/email/retry');
    expect(fetchMock.mock.calls[0]?.[0]).not.toContain('run-now');
    expect(fetchMock.mock.calls[0]?.[1]).toEqual(expect.objectContaining({ method: 'POST', body: '{}' }));
    expect(schedulesApi.emailReportUrl('schedule/1', 'run/1')).toBe('/api/schedules/schedule%2F1/runs/run%2F1/email/report');
  });

  it('normalizes device aliases and scheduler health', () => {
    expect(normalizeDevices({ devices: [{ device_id: 'abc', model: 'Pixel', is_busy: true }, { device_serial: 'def', device_name: 'Tablet', authorized: false }] })).toEqual([
      { serial: 'abc', name: 'Pixel', model: 'Pixel', busy: true },
      { serial: 'def', name: 'Tablet', authorized: false },
    ]);
    expect(normalizeScheduleStatus({ running: true, last_heartbeat: '2026-09-15T00:00:00Z', status: 'leader' })).toEqual({ healthy: true, running: true, last_heartbeat: '2026-09-15T00:00:00Z', status: 'leader' });
    expect(normalizeScheduleStatus({ healthy: false, running: true })).toMatchObject({ healthy: false, running: true });
  });
});
