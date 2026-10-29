import type { SessionSummary } from './types';

export interface HistoryDateRange { from: string; to: string }
const localDay = (date: Date) => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;

export function defaultHistoryDateRange(now = new Date()): HistoryDateRange {
  const from = new Date(now);
  from.setDate(from.getDate() - 6);
  return { from: localDay(from), to: localDay(now) };
}

export function sessionInDateRange(session: SessionSummary, range: HistoryDateRange): boolean {
  if (!range.from && !range.to) return true;
  if (range.from && range.to && range.from > range.to) return false;
  const value = session.created_at ?? session.start_time;
  if (value === undefined) return false;
  const date = new Date(typeof value === 'number' && value < 10_000_000_000 ? value * 1000 : value);
  if (Number.isNaN(date.valueOf())) return false;
  const day = localDay(date);
  return (!range.from || day >= range.from) && (!range.to || day <= range.to);
}
