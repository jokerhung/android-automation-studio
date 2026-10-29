import { parseTimestamp } from './timestamp';
import type { SessionStep } from './types';

const stepKey = (step: SessionStep): string => String(step.step_id ?? step.id ?? step.step_number ?? '');
const stepTime = (step: SessionStep): number => parseTimestamp(step.updated_at ?? step.timestamp ?? step.created_at, 0);

export function reconcileSnapshotSteps(snapshot: readonly SessionStep[], live: readonly SessionStep[]): readonly SessionStep[] {
  const byKey = new Map<string, SessionStep>();
  const anonymous: SessionStep[] = [];
  for (const item of snapshot) {
    const key = stepKey(item);
    if (key) byKey.set(key, item); else anonymous.push(item);
  }
  for (const item of live) {
    const key = stepKey(item);
    if (!key) { anonymous.push(item); continue; }
    const persisted = byKey.get(key);
    if (!persisted) byKey.set(key, item);
    else byKey.set(key, stepTime(item) >= stepTime(persisted) ? { ...persisted, ...item } : { ...item, ...persisted });
  }
  return [...byKey.values(), ...anonymous].sort((a, b) => stepTime(a) - stepTime(b));
}

export function snapshotIsCurrent(input: { requestId: number; appliedRequestId: number; sessionId: string; selectedSessionId: string | null; generation: number; currentGeneration: number }): boolean {
  return input.requestId >= input.appliedRequestId && input.generation === input.currentGeneration && input.selectedSessionId === input.sessionId;
}
