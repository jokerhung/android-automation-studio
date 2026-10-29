import { describe, expect, it } from 'vitest';
import { defaultHistoryDateRange, sessionInDateRange } from '@/features/workspace/history-date-range';
import type { SessionSummary } from '@/features/workspace/types';

const session = (date: Date): SessionSummary => ({ session_id: 'history', status: 'completed', start_time: date.valueOf() / 1000 });
describe('History date filtering', () => {
  it('defaults to seven local calendar days including today across a month boundary', () => {
    expect(defaultHistoryDateRange(new Date(2026, 9, 3, 23, 30))).toEqual({ from: '2026-09-27', to: '2026-10-03' });
  });
  it('includes the full start and end days and excludes adjacent days', () => {
    const range = { from: '2026-10-06', to: '2026-10-12' };
    expect(sessionInDateRange(session(new Date(2026, 9, 6, 0, 0)), range)).toBe(true);
    expect(sessionInDateRange(session(new Date(2026, 9, 12, 23, 59, 59, 999)), range)).toBe(true);
    expect(sessionInDateRange(session(new Date(2026, 9, 5, 23, 59)), range)).toBe(false);
    expect(sessionInDateRange(session(new Date(2026, 9, 13)), range)).toBe(false);
  });
  it('supports ISO timestamps, milliseconds and open-ended ranges', () => {
    const date = new Date(2026, 9, 12, 12);
    expect(sessionInDateRange({ ...session(date), created_at: date.toISOString() }, { from: '2026-10-12', to: '' })).toBe(true);
    expect(sessionInDateRange({ ...session(date), start_time: date.valueOf() }, { from: '', to: '2026-10-12' })).toBe(true);
  });
  it('handles missing timestamps, cleared bounds and reversed dates', () => {
    const item: SessionSummary = { session_id: 'unknown', status: 'completed' };
    expect(sessionInDateRange(item, { from: '2026-10-06', to: '2026-10-12' })).toBe(false);
    expect(sessionInDateRange(item, { from: '', to: '' })).toBe(true);
    expect(sessionInDateRange(session(new Date(2026, 9, 12)), { from: '2026-10-13', to: '2026-10-12' })).toBe(false);
    expect(sessionInDateRange({ ...item, created_at: 'invalid' }, { from: '2026-10-06', to: '' })).toBe(false);
  });
});
