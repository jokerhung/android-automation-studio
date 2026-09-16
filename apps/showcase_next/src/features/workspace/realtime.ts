import { timestampIso } from './timestamp';

export const STREAM_FOREGROUND_DELAY_MS = 80;
export const STREAM_HIDDEN_DELAY_MS = 500;
export type StreamEventType = 'llm_stream' | 'llm_stream_reset' | string;
export interface WorkspaceStreamEvent { type: StreamEventType; timestamp: string; session_id?: string; data: Record<string, unknown> }
export interface StreamChunkBatch { execution_id: string; stream_type: string; text: string; session_id?: string; step_id?: string; parent_trace_id?: string }
type TimerHandle = ReturnType<typeof setTimeout>;

const text = (value: unknown): string => typeof value === 'string' ? value : '';
export const streamIdentity = (data: Record<string, unknown>): string => String(data.execution_id ?? data.stream_exec_id ?? data.stream_execution_id ?? '') + '|' + String(data.stream_type ?? 'text');

export class StreamChunkAccumulator {
  private pending = new Map<string, StreamChunkBatch>();
  private timer: TimerHandle | null = null;
  constructor(private readonly emit: (events: readonly WorkspaceStreamEvent[]) => void, private readonly hidden: () => boolean = () => typeof document !== 'undefined' && document.hidden) {}
  push(data: Record<string, unknown>): void {
    const executionId = String(data.execution_id ?? '');
    const streamType = String(data.stream_type ?? 'text');
    if (!executionId) return;
    const sessionKey = text(data.session_id);
    const key = sessionKey + '|' + executionId + '|' + streamType;
    const previous = this.pending.get(key);
    const chunk = text(data.chunk) || text(data.text);
    const batch: StreamChunkBatch = { execution_id: executionId, stream_type: streamType, text: (previous?.text ?? '') + chunk };
    const sessionId = text(data.session_id) || previous?.session_id; if (sessionId) batch.session_id = sessionId;
    const stepId = text(data.step_id) || previous?.step_id; if (stepId) batch.step_id = stepId;
    const parentTraceId = text(data.parent_trace_id) || previous?.parent_trace_id; if (parentTraceId) batch.parent_trace_id = parentTraceId;
    this.pending.set(key, batch);
    if (this.timer === null) this.timer = setTimeout(() => this.flush(), this.hidden() ? STREAM_HIDDEN_DELAY_MS : STREAM_FOREGROUND_DELAY_MS);
  }
  beforeNonStream(type: string, data: Record<string, unknown>): void {
    if (type === 'llm_stream_reset') this.discardReset(data);
    this.flush();
  }
  discardReset(data: Record<string, unknown>): void {
    const executionId = String(data.stream_exec_id ?? data.stream_execution_id ?? data.execution_id ?? '');
    const streamType = data.stream_type == null ? null : String(data.stream_type);
    if (!executionId) return;
    const sessionKey = text(data.session_id);
    for (const [key,batch] of this.pending) {
      if (sessionKey && batch.session_id !== sessionKey) continue;
      if (batch.execution_id === executionId && (streamType === null || batch.stream_type === streamType)) this.pending.delete(key);
    }
    if (this.pending.size === 0) this.clearTimer();
  }
  flush(): void {
    this.clearTimer();
    if (!this.pending.size) return;
    const events = [...this.pending.values()].map((batch): WorkspaceStreamEvent => ({ type: 'llm_stream', timestamp: new Date().toISOString(), ...(batch.session_id ? { session_id: batch.session_id } : {}), data: { ...batch, chunk: batch.text } }));
    this.pending.clear();
    this.emit(events);
  }
  dispose(): void { this.pending.clear(); this.clearTimer(); }
  private clearTimer(): void { if (this.timer !== null) clearTimeout(this.timer); this.timer = null; }
}

export function toWorkspaceStreamEvent(type: string, data: Record<string, unknown>, now = Date.now()): WorkspaceStreamEvent {
  return { type, timestamp: timestampIso(data.timestamp, now) ?? new Date(now).toISOString(), ...(typeof data.session_id === 'string' ? { session_id: data.session_id } : {}), data };
}

export function reduceStreamEvents(logs: readonly WorkspaceStreamEvent[], incoming: readonly WorkspaceStreamEvent[]): readonly WorkspaceStreamEvent[] {
  let next = [...logs];
  for (const event of incoming) {
    if (event.type === 'llm_stream') {
      const identity = streamIdentity(event.data);
      const index = next.findIndex(item => item.type === 'llm_stream' && streamIdentity(item.data) === identity);
      if (index >= 0) {
        const current = next[index];
        if (!current) continue;
        const updated: WorkspaceStreamEvent = { ...current, data: { ...current.data, ...event.data, text: text(current.data.text) + (text(event.data.chunk) || text(event.data.text)) } };
        const sessionId = event.session_id ?? current.session_id; if (sessionId) updated.session_id = sessionId;
        next[index] = updated;
      } else next.push({ ...event, data: { ...event.data, text: text(event.data.chunk) || text(event.data.text), isCompleted: false } });
      continue;
    }
    if (event.type === 'llm_stream_reset') {
      const executionId = String(event.data.stream_exec_id ?? event.data.stream_execution_id ?? event.data.execution_id ?? '');
      next = next.map(item => item.type === 'llm_stream' && String(item.data.execution_id ?? '') === executionId ? { ...item, data: { ...item.data, isReset: true, resetMessage: event.data.message } } : item);
    }
    if (event.type === 'trace_recorded' && event.data.trace_id) {
      const index = next.findIndex(item => item.type === 'trace_recorded' && item.data.trace_id === event.data.trace_id);
      if (index >= 0) { next[index] = event; continue; }
    }
    next.push(event);
  }
  return next;
}
