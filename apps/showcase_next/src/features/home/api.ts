import { apiRequest, READINESS_REQUEST_TIMEOUT_MS } from '@/lib/api/client';
import type { ProTuningDefaults, RunTaskRequest, RunTaskResponse, SystemReadinessReport } from './models';

export const homeApi = {
  readiness: (signal: AbortSignal) => apiRequest<SystemReadinessReport>('/api/system/readiness', { signal, timeoutMs: READINESS_REQUEST_TIMEOUT_MS }),
  defaults: (signal: AbortSignal) => apiRequest<ProTuningDefaults>('/api/run/defaults', { signal }),
  run: (body: RunTaskRequest, signal: AbortSignal) => apiRequest<RunTaskResponse,RunTaskRequest>('/api/run', { method:'POST', body, signal }),
};
