'use client';
import { useEffect, useState } from 'react';
import { CalendarDays } from 'lucide-react';

export function formatHistoryDate(value: string): string {
  return value ? value.split('-').reverse().join('/') : '';
}

export function parseHistoryDate(value: string): string | null {
  if (!value) return '';
  const match = /^(\d{2})\/(\d{2})\/(\d{4})$/.exec(value);
  if (!match) return null;
  const [, day, month, year] = match;
  const date = new Date(Number(year), Number(month) - 1, Number(day));
  if (Number(year) < 100 || date.getFullYear() !== Number(year) || date.getMonth() !== Number(month) - 1 || date.getDate() !== Number(day)) return null;
  return `${year}-${month}-${day}`;
}

export function HistoryDateInput({ label, value, invalid, onChange }: { label: string; value: string; invalid: boolean; onChange(value: string): void }) {
  const [draft, setDraft] = useState(() => formatHistoryDate(value));
  useEffect(() => { setDraft(formatHistoryDate(value)); }, [value]);
  const invalidDraft = parseHistoryDate(draft) === null;
  return <div className="ws-history-date-field"><label><span>{label}</span><input type="text" inputMode="numeric" placeholder="dd/MM/yyyy" maxLength={10} value={draft} aria-invalid={invalid || invalidDraft} onChange={event => {
    const next = event.target.value;
    setDraft(next);
    const parsed = parseHistoryDate(next);
    if (parsed !== null) onChange(parsed);
  }} onBlur={() => { if (invalidDraft) setDraft(formatHistoryDate(value)); }} /></label><div className="ws-history-calendar"><CalendarDays size={16} aria-hidden="true"/><input type="date" aria-label={`${label} (dd/MM/yyyy)`} value={value} onChange={event => { onChange(event.target.value); setDraft(formatHistoryDate(event.target.value)); }} /></div></div>;
}
