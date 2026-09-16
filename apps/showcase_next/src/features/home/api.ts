import { apiRequest } from '@/lib/api/client';
import type { ProTuningDefaults, RunTaskRequest, RunTaskResponse, SystemReadinessReport } from './models';

export const homeApi = {
  readiness: (signal: AbortSignal) => apiRequest<SystemReadinessReport>('/api/system/readiness', { signal }),
  defaults: (signal: AbortSignal) => apiRequest<ProTuningDefaults>('/api/run/defaults', { signal }),
  run: (body: RunTaskRequest, signal: AbortSignal) => apiRequest<RunTaskResponse,RunTaskRequest>('/api/run', { method:'POST', body, signal }),
};
