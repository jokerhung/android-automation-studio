'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent as ReactPointerEvent } from 'react';
import { useWorkspace } from '@/features/workspace';
import { useAppPreferences } from '@/app/providers';
import type { SessionStep, SessionSummary } from '@/features/workspace/types';
import styles from './legacy-check.module.css';

type StreamEvent = { type: string; timestamp?: string | number; data: unknown };

const MIN_LEFT = 360;
const MIN_RIGHT = 300;
const DEFAULT_RIGHT = 390;
const ACTIVE_STATUSES = new Set(['running', 'paused', 'pending', 'queued']);

function asText(value: unknown, fallback = ''): string {
  return typeof value === 'string' || typeof value === 'number' ? String(value) : fallback;
}

function sessionGoal(session: SessionSummary): string {
  return asText(session.initial_goal ?? session.goal, 'Unnamed goal');
}

function sessionTime(session: SessionSummary): string | number | undefined {
  return session.created_at ?? session.start_time;
}

function normalizeStep(item: SessionStep): StreamEvent {
  const record = item as Record<string, unknown>;
  if (typeof record.type === 'string' && 'data' in record) {
    const timestamp = asText(record.timestamp);
    return { type: record.type, ...(timestamp ? { timestamp } : {}), data: record.data };
  }
  const timestamp = typeof record.timestamp === 'number' ? record.timestamp : asText(record.timestamp);
  return { type: 'step_updated', ...(timestamp !== '' ? { timestamp } : {}), data: record };
}

function formatTime(value?: string | number): string {
  if (value === undefined || value === '') return 'Time unavailable';
  const parsed = typeof value === 'number' ? new Date(value * 1000) : new Date(value);
  if (Number.isNaN(parsed.getTime())) return asText(value, 'Time unavailable');
  return parsed.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

function pretty(value: unknown): string {
  if (typeof value === 'string') {
    try { return JSON.stringify(JSON.parse(value), null, 2); } catch { return value; }
  }
  try { return JSON.stringify(value, null, 2) ?? String(value); } catch { return String(value); }
}

function field(data: unknown, key: string): unknown {
  return data && typeof data === 'object' ? (data as Record<string, unknown>)[key] : undefined;
}

function TextDetails({ title, value, tone, defaultOpen = false, code = false }: { title: string; value: unknown; tone: string; defaultOpen?: boolean; code?: boolean }) {
  return (
    <details className={styles.details} data-tone={tone} open={defaultOpen}>
      <summary>{title}</summary>
      {code ? <pre><code>{pretty(value)}</code></pre> : <div className={styles.plainText}>{asText(value, pretty(value))}</div>}
    </details>
  );
}

function LegacyEventCard({ event, index }: { event: StreamEvent; index: number }) {
  const isStep = event.type === 'step_recorded' || event.type === 'step_updated';
  const summary = field(event.data, 'summary');
  const thinking = field(event.data, 'operator_native_thinking');
  const plan = field(event.data, 'operator_raw_thinking');
  const action = field(event.data, 'action_taken');
  const result = field(event.data, 'last_execution_result');
  const shortPayload = pretty(event.data).length < 200;
  return (
    <article className={styles.eventCard}>
      <header className={styles.eventHeader}>
        <span className={styles.index}>#{index + 1}</span>
        <span className={styles.eventType}>{event.type.replaceAll('_', ' ')}</span>
        <time className={styles.time}>{formatTime(event.timestamp)}</time>
      </header>
      {isStep ? (
        <div className={styles.eventBody}>
          {summary !== undefined && <div className={styles.summary}><strong>Message / summary</strong><p>{asText(summary, pretty(summary))}</p></div>}
          {thinking !== undefined && <TextDetails title="Model thinking process" value={thinking} tone="green" />}
          {plan !== undefined && <TextDetails title="Raw plan / thoughts" value={plan} tone="violet" />}
          {action !== undefined && <TextDetails title="Tool call details" value={action} tone="blue" defaultOpen={pretty(action).length < 200} code />}
          {result !== undefined && <TextDetails title="Execution result" value={result} tone="cyan" code />}
          {summary === undefined && thinking === undefined && plan === undefined && action === undefined && result === undefined && <TextDetails title="Step payload" value={event.data} tone="slate" defaultOpen={shortPayload} code />}
        </div>
      ) : <TextDetails title="Raw payload data" value={event.data} tone="slate" defaultOpen={shortPayload} code />}
    </article>
  );
}

function SessionCard({ session, selected, onSelect }: { session: SessionSummary; selected: boolean; onSelect(): void }) {
  const device = asText(session.device_serial ?? session.device_id, 'No device');
  return (
    <button type="button" className={styles.sessionCard} data-selected={selected} onClick={onSelect} aria-pressed={selected}>
      <span className={styles.sessionMeta}><span className={styles.status} data-status={session.status}>{session.status}</span><time>{formatTime(sessionTime(session))}</time></span>
      <strong>{sessionGoal(session)}</strong>
      <span className={styles.sessionFooter}><span>{device}</span><code>{session.session_id}</code></span>
    </button>
  );
}

export function LegacyCheck() {
  const { t } = useAppPreferences();
  const { state, refresh, selectSession, loadSessionDetails } = useWorkspace();
  const shellRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT);
  const [view, setView] = useState<'tasks' | 'history'>('tasks');
  const [refreshing, setRefreshing] = useState(false);
  const sessions = state.sessions;
  const selectedId = state.selectedSessionId ?? '';
  const selected = sessions.find(item => item.session_id === selectedId) ?? null;
  const detailsResource = selectedId ? state.details[selectedId] : undefined;
  const events = useMemo(() => (detailsResource?.data?.steps ?? []).map(normalizeStep), [detailsResource?.data?.steps]);

  const clampWidth = useCallback((width: number) => {
    const total = shellRef.current?.getBoundingClientRect().width ?? 0;
    return Math.max(MIN_RIGHT, Math.min(width, Math.max(MIN_RIGHT, total - MIN_LEFT)));
  }, []);

  useEffect(() => {
    if (!selectedId && sessions[0]) selectSession(sessions[0].session_id);
  }, [selectSession, selectedId, sessions]);

  useEffect(() => {
    if (selectedId && !detailsResource?.loading && !detailsResource?.data) void loadSessionDetails(selectedId);
  }, [detailsResource?.data, detailsResource?.loading, loadSessionDetails, selectedId]);

  useEffect(() => {
    const move = (event: PointerEvent) => { const drag = dragRef.current; if (drag) setRightWidth(clampWidth(drag.startWidth - (event.clientX - drag.startX))); };
    const stop = () => { dragRef.current = null; document.body.classList.remove(styles.draggingBody!); };
    window.addEventListener('pointermove', move); window.addEventListener('pointerup', stop);
    return () => { window.removeEventListener('pointermove', move); window.removeEventListener('pointerup', stop); document.body.classList.remove(styles.draggingBody!); };
  }, [clampWidth]);

  const chooseSession = useCallback((id: string) => {
    selectSession(id || null);
    if (id) void loadSessionDetails(id);
  }, [loadSessionDetails, selectSession]);

  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    try { await refresh(); if (selectedId) await loadSessionDetails(selectedId); } finally { setRefreshing(false); }
  }, [loadSessionDetails, refresh, selectedId]);

  const startDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (window.matchMedia('(max-width: 800px)').matches) return;
    dragRef.current = { startX: event.clientX, startWidth: rightWidth };
    document.body.classList.add(styles.draggingBody!); event.preventDefault();
  };
  const resizeByKeyboard = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return;
    event.preventDefault(); setRightWidth(current => clampWidth(current + (event.key === 'ArrowLeft' ? 24 : -24)));
  };

  const visibleSessions = useMemo(() => sessions.filter(item => view === 'tasks' ? ACTIVE_STATUSES.has(item.status) : !ACTIVE_STATUSES.has(item.status)), [sessions, view]);
  const loadingEvents = Boolean(detailsResource?.loading);
  const error = detailsResource?.error ?? state.error;

  return (
    <main className={styles.page}>
      <div className={styles.aurora} aria-hidden="true"><span /><span /><span /></div>
      <div ref={shellRef} className={styles.splitShell} style={{ '--legacy-right-width': rightWidth + 'px' } as CSSProperties}>
        <section className={styles.streamPanel} aria-label={t('check.streamLabel')}>
          <header className={styles.streamHeader}>
            <div><p className={styles.eyebrow}>{t('check.kicker')}</p><h1>{t('check.streamTitle')}</h1><p>{t('check.streamBody')}</p></div>
            <label>{t('check.activeSession')}<select value={selectedId} onChange={event => chooseSession(event.target.value)} disabled={!sessions.length}><option value="">{t('check.selectSession')}</option>{sessions.map(item => <option key={item.session_id} value={item.session_id}>{sessionGoal(item)} · {item.status}</option>)}</select></label>
          </header>
          {error && <div className={styles.error} role="alert">{error}</div>}
          <div className={styles.logArea}>
            {loadingEvents ? <div className={styles.empty}><span>…</span><h2>{t('check.loadingActivity')}</h2><p>{t('check.loadingBody')}</p></div> : events.length ? events.map((event, index) => <LegacyEventCard key={index + '-' + event.type + '-' + asText(event.timestamp)} event={event} index={index} />) : <div className={styles.empty}><span>◉</span><h2>{t('check.noActivity')}</h2><p>{selected ? t('check.noActivitySelected') : t('check.noActivityNone')}</p></div>}
          </div>
        </section>
        <div className={styles.resizer} role="separator" aria-label={t('check.resize')} aria-orientation="vertical" aria-valuemin={MIN_RIGHT} aria-valuenow={rightWidth} tabIndex={0} onPointerDown={startDrag} onKeyDown={resizeByKeyboard}><span /></div>
        <aside className={styles.taskPanel} aria-label={t('check.selection')}>
          <header className={styles.taskHeader}><div className={styles.tabs} role="tablist" aria-label={t('check.sessionType')}><button type="button" role="tab" aria-selected={view === 'tasks'} onClick={() => setView('tasks')}>{t('check.tasks')}</button><button type="button" role="tab" aria-selected={view === 'history'} onClick={() => setView('history')}>{t('check.history')}</button></div><button className={styles.refresh} type="button" onClick={() => void refreshAll()} disabled={refreshing}>{refreshing ? t('check.loading') : t('check.refresh')}</button></header>
          <div className={styles.sessionList}>{visibleSessions.length ? visibleSessions.map(item => <SessionCard key={item.session_id} session={item} selected={selectedId === item.session_id} onSelect={() => chooseSession(item.session_id)} />) : <div className={styles.listEmpty}><strong>{t('check.noItems',{type:t(view==='tasks'?'check.tasks':'check.history').toLocaleLowerCase()})}</strong><span>{t(view === 'tasks' ? 'check.tasksEmpty' : 'check.historyEmpty')}</span></div>}</div>
          {selected && <footer className={styles.selection}><span>{t('check.inspecting',{connection:state.connection})}</span><strong>{sessionGoal(selected)}</strong><code>{selected.session_id}</code></footer>}
        </aside>
      </div>
    </main>
  );
}
