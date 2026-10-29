export type ApiQueryValue = string | number | boolean | null | undefined;
export interface ApiRequestOptions<TBody = unknown> { method?: 'GET'|'POST'|'PUT'|'PATCH'|'DELETE'; query?: Readonly<Record<string, ApiQueryValue>>; body?: TBody; signal?: AbortSignal; headers?: HeadersInit; timeoutMs?: number }
export const API_REQUEST_TIMEOUT_MS = 15_000;
export const API_MUTATION_TIMEOUT_MS = 60_000;
// A readiness probe may take up to 30s on the server before reporting failure.
export const READINESS_REQUEST_TIMEOUT_MS = 45_000;
export class ApiTimeoutError extends Error { constructor(public readonly url: string) { super("Request timed out. Please try again."); this.name = "TimeoutError"; } }
export interface ApiErrorPayload { detail?: unknown; message?: unknown; [key: string]: unknown }
export class ApiError extends Error { constructor(public readonly status: number, message: string, public readonly payload: unknown, public readonly url: string) { super(message); this.name = 'ApiError'; } }

function createUrl(path: string, query?: Readonly<Record<string, ApiQueryValue>>): string {
  if (!path.startsWith('/api/')) throw new Error('API paths must be same-origin and start with /api/');
  const params = new URLSearchParams();
  Object.entries(query ?? {}).forEach(([key, value]) => { if (value !== null && value !== undefined) params.set(key, String(value)); });
  const suffix = params.toString(); return suffix ? `${path}?${suffix}` : path;
}
async function decode(response: Response): Promise<unknown> { if (response.status === 204) return undefined; const type=response.headers.get('content-type') ?? ''; return type.includes('application/json') ? response.json() : response.text(); }
export async function apiRequest<TResponse, TBody = never>(path: string, options: ApiRequestOptions<TBody> = {}): Promise<TResponse> {
  const url=createUrl(path, options.query); const headers=new Headers(options.headers); let body: BodyInit|undefined;
  if (options.body !== undefined) { headers.set('content-type','application/json'); body=JSON.stringify(options.body); }
  const init: RequestInit = { method: options.method ?? 'GET', headers, credentials: 'same-origin' };
  if (body !== undefined) init.body = body;
  const controller = new AbortController();
  const abort = () => controller.abort(options.signal?.reason);
  if (options.signal?.aborted) abort();
  else options.signal?.addEventListener('abort', abort, { once: true });
  init.signal = controller.signal;
  const timer = setTimeout(() => controller.abort(new ApiTimeoutError(url)), options.timeoutMs ?? (init.method === 'GET' ? API_REQUEST_TIMEOUT_MS : API_MUTATION_TIMEOUT_MS));
  try {
    const response=await fetch(url,init);
    const payload=await decode(response); if (!response.ok) { const record=payload && typeof payload==='object' ? payload as ApiErrorPayload : undefined; const message=typeof record?.detail==='string' ? record.detail : typeof record?.message==='string' ? record.message : `Request failed (${response.status})`; throw new ApiError(response.status,message,payload,url); }
    return payload as TResponse;
  } catch (error) {
    if (controller.signal.aborted) throw controller.signal.reason;
    throw error;
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener('abort', abort);
  }
}
export const apiPath = (base: string, ...segments: readonly (string|number)[]): string => [base.replace(/\/$/,''), ...segments.map(value=>encodeURIComponent(String(value)))].join('/');

export interface SystemReadinessReport { ready: boolean; score?: number; checks?: ReadonlyArray<{ name: string; ready: boolean; message?: string }> }
export interface SessionSummary { id: string; status: string; goal?: string; created_at?: string }
export interface ScheduleSummary { id: string; version: number; name: string; enabled: boolean; next_run_at?: string|null }
export interface ScheduleListResponse { schedules: ScheduleSummary[] }
export interface DeviceSummary { serial: string; name?: string; model?: string; status?: string; busy?: boolean; authorized?: boolean }
export const artemisApi = {
  readiness: (signal?: AbortSignal) => apiRequest<SystemReadinessReport>('/api/system/readiness',{...(signal ? {signal} : {}), timeoutMs: READINESS_REQUEST_TIMEOUT_MS}),
  sessions: (signal?: AbortSignal) => apiRequest<SessionSummary[]>('/api/sessions',signal ? {signal} : {}),
  schedules: (signal?: AbortSignal) => apiRequest<ScheduleListResponse>('/api/schedules',signal ? {signal} : {}),
  devices: (signal?: AbortSignal) => apiRequest<{devices: DeviceSummary[]}>('/api/devices',signal ? {signal} : {}),
};
