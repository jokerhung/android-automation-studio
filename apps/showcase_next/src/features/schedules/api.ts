import { apiPath, apiRequest } from '@/lib/api/client';
import type { EmailRetryResult, ScheduleDevice, ScheduleDraft, SchedulePreviewRequest, SchedulePreviewResponse, ScheduleRun, ScheduleRunList, ScheduleStatus, ScheduleUpdate, TaskSchedule } from './types';

const BASE = '/api/schedules';
type UnknownRecord = Record<string, unknown>;
const record = (value: unknown): UnknownRecord => value !== null && typeof value === 'object' && !Array.isArray(value) ? value as UnknownRecord : {};

export function normalizePreview(value: SchedulePreviewResponse | readonly string[]): string[] {
  if (Array.isArray(value)) return [...value];
  const response = value as SchedulePreviewResponse;
  return [...(response.due_times ?? response.next_runs ?? response.occurrences ?? [])];
}
export function normalizeDevices(value: unknown): ScheduleDevice[] {
  const root = record(value);
  const rawDevices = Array.isArray(value) ? value : Array.isArray(root.devices) ? root.devices : [];
  return rawDevices.map(item => record(item)).map(raw => {
    const serial = String(raw.serial ?? raw.device_serial ?? raw.device_id ?? '');
    const fallbackName = raw.name ?? raw.device_name ?? raw.model ?? raw.serial ?? raw.device_serial ?? raw.device_id;
    return {
      serial,
      ...(fallbackName == null ? {} : { name: String(fallbackName) }),
      ...(raw.model == null ? {} : { model: String(raw.model) }),
      ...(raw.status == null ? {} : { status: String(raw.status) }),
      ...((raw.busy ?? raw.is_busy) == null ? {} : { busy: Boolean(raw.busy ?? raw.is_busy) }),
      ...(raw.authorized == null ? {} : { authorized: Boolean(raw.authorized) }),
    };
  }).filter(device => device.serial.length > 0);
}
export function normalizeScheduleStatus(value: unknown): ScheduleStatus {
  const raw = record(value);
  const running = raw.running == null ? undefined : Boolean(raw.running);
  const heartbeat = raw.last_heartbeat == null ? undefined : String(raw.last_heartbeat);
  const healthy = raw.healthy == null ? Boolean(running && heartbeat) : Boolean(raw.healthy);
  return { healthy, ...(running == null ? {} : { running }), ...(raw.leader == null ? {} : { leader: Boolean(raw.leader) }), ...(raw.status == null ? {} : { status: String(raw.status) }), ...(heartbeat == null ? {} : { last_heartbeat: heartbeat }), ...(raw.timezone_support == null ? {} : { timezone_support: Boolean(raw.timezone_support) }), ...(raw.message == null ? {} : { message: String(raw.message) }) };
}
const normalizeSchedules = (value: TaskSchedule[] | { schedules?: TaskSchedule[] }): TaskSchedule[] => Array.isArray(value) ? value : value.schedules ?? [];
const normalizeRuns = (value: ScheduleRun[] | ScheduleRunList): ScheduleRunList => Array.isArray(value) ? { runs: value } : { ...value, runs: value.runs ?? [] };
const updateSchedule = (schedule: Pick<TaskSchedule, 'id' | 'version'>, changes: ScheduleUpdate, signal?: AbortSignal) => apiRequest<TaskSchedule, ScheduleUpdate & { expected_version: number }>(apiPath(BASE, schedule.id), { method: 'PATCH', body: { ...changes, expected_version: schedule.version }, ...(signal ? { signal } : {}) });

export const schedulesApi = {
  list: async (signal?: AbortSignal): Promise<TaskSchedule[]> => normalizeSchedules(await apiRequest<TaskSchedule[] | { schedules?: TaskSchedule[] }>(BASE, signal ? { signal } : {})),
  get: (id: string, signal?: AbortSignal) => apiRequest<TaskSchedule>(apiPath(BASE, id), signal ? { signal } : {}),
  create: (draft: ScheduleDraft, signal?: AbortSignal) => apiRequest<TaskSchedule, ScheduleDraft>(BASE, { method: 'POST', body: draft, ...(signal ? { signal } : {}) }),
  update: updateSchedule,
  pause: (schedule: Pick<TaskSchedule, 'id' | 'version'>, signal?: AbortSignal) => updateSchedule(schedule, { enabled: false }, signal),
  resume: (schedule: Pick<TaskSchedule, 'id' | 'version'>, signal?: AbortSignal) => updateSchedule(schedule, { enabled: true }, signal),
  delete: (schedule: Pick<TaskSchedule, 'id' | 'version'>, signal?: AbortSignal) => apiRequest<void>(apiPath(BASE, schedule.id), { method: 'DELETE', query: { expected_version: schedule.version }, ...(signal ? { signal } : {}) }),
  preview: async (request: SchedulePreviewRequest, signal?: AbortSignal): Promise<string[]> => normalizePreview(await apiRequest<SchedulePreviewResponse | string[], SchedulePreviewRequest>(apiPath(BASE, 'preview'), { method: 'POST', body: request, ...(signal ? { signal } : {}) })),
  runNow: async (id: string, idempotencyKey: string, signal?: AbortSignal): Promise<ScheduleRun> => (await apiRequest<{ created?: boolean; run: ScheduleRun }, { idempotency_key: string }>(apiPath(BASE, id, 'run-now'), { method: 'POST', body: { idempotency_key: idempotencyKey }, ...(signal ? { signal } : {}) })).run,
  runs: async (id: string, options: { limit?: number; offset?: number; signal?: AbortSignal } = {}): Promise<ScheduleRunList> => normalizeRuns(await apiRequest<ScheduleRun[] | ScheduleRunList>(apiPath(BASE, id, 'runs'), { query: { limit: options.limit, offset: options.offset }, ...(options.signal ? { signal: options.signal } : {}) })),
  retryEmail: (scheduleId: string, runId: string, signal?: AbortSignal) => apiRequest<EmailRetryResult, Record<string, never>>(apiPath(BASE, scheduleId, 'runs', runId, 'email', 'retry'), { method: 'POST', body: {}, ...(signal ? { signal } : {}) }),
  emailReportUrl: (scheduleId: string, runId: string): string => apiPath(BASE, scheduleId, 'runs', runId, 'email', 'report'),
  status: async (signal?: AbortSignal): Promise<ScheduleStatus> => normalizeScheduleStatus(await apiRequest<unknown>(apiPath(BASE, 'status'), signal ? { signal } : {})),
  devices: async (signal?: AbortSignal): Promise<ScheduleDevice[]> => normalizeDevices(await apiRequest<unknown>('/api/devices', signal ? { signal } : {})),
};
