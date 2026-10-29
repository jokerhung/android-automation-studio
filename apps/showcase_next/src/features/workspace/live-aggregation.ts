import { reconcileSnapshotSteps } from './snapshot';
import type { SessionDetails, SessionStep } from './types';
import type { WorkspaceStreamEvent } from './realtime';

const text = (value: unknown): string => typeof value === 'string' ? value : value == null ? '' : String(value);
const stepId = (value: Record<string, unknown>): string => text(value.step_id || value.id || value.step_number);
const checkerId = (value: Record<string, unknown>): string => text(value.attempt_id || value.trace_id);
const toolsOf = (step: SessionStep): Record<string, unknown>[] => Array.isArray(step.generic_tools) ? step.generic_tools.filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null) : [];

function mergeTool(step: SessionStep, trace: Record<string, unknown>): SessionStep {
  const tools = toolsOf(step);
  const traceId = text(trace.trace_id);
  const index = traceId ? tools.findIndex(item => text(item.trace_id) === traceId) : -1;
  const generic_tools = [...tools];
  if (index >= 0) generic_tools[index] = { ...generic_tools[index], ...trace };
  else generic_tools.push(trace);
  return { ...step, generic_tools };
}

/** Pure, conservative subset of Angular's step/checker trace routing contract. */
export function aggregateLiveSteps(events: readonly WorkspaceStreamEvent[]): readonly SessionStep[] {
  let steps: SessionStep[] = [];
  for (const event of events) {
    const data = event.data;
    if (event.type === 'step_recorded' || event.type === 'step_updated') {
      const id = stepId(data);
      if (!id) continue;
      const incoming: SessionStep = { ...data, step_id: id, timestamp: data.timestamp ?? event.timestamp };
      steps = [...reconcileSnapshotSteps(steps, [incoming])];
      continue;
    }
    if (event.type === 'checker_event') {
      const attemptId = checkerId(data);
      if (!attemptId) continue;
      const id = 'checker-' + attemptId;
      const incoming: SessionStep = { ...data, step_id: id, block_type: 'checker', attempt_id: attemptId, timestamp: data.timestamp ?? data.ts ?? event.timestamp };
      steps = [...reconcileSnapshotSteps(steps, [incoming])];
      continue;
    }
    if (event.type !== 'trace_recorded' || !data.trace_id) continue;
    const traceId = text(data.trace_id);
    const parentTraceId = text(data.parent_trace_id);
    let index = parentTraceId ? steps.findIndex(step => step.block_type === 'checker' && text(step.trace_id) === parentTraceId) : -1;
    if (index < 0) index = steps.findIndex(step => toolsOf(step).some(tool => text(tool.trace_id) === traceId));
    const targetStepId = stepId(data);
    if (index < 0 && targetStepId) index = steps.findIndex(step => stepId(step) === targetStepId);
    if (index < 0 && targetStepId) {
      steps = [...steps, { step_id: targetStepId, timestamp: event.timestamp, generic_tools: [data] }];
    } else if (index >= 0) {
      steps = steps.map((step, itemIndex) => itemIndex === index ? mergeTool(step, data) : step);
    }
  }
  return steps;
}

export function reconcileDetailsWithLive(details: SessionDetails, events: readonly WorkspaceStreamEvent[]): SessionDetails {
  return { ...details, steps: reconcileSnapshotSteps(details.steps, aggregateLiveSteps(events)) };
}

/** Sessionless events may refresh global snapshots, but never mutate selected-session state. */
export function eventsForSelectedSession(events: readonly WorkspaceStreamEvent[], selectedSessionId: string | null): readonly WorkspaceStreamEvent[] {
  if (!selectedSessionId) return [];
  return events.filter(event => event.session_id === selectedSessionId);
}
