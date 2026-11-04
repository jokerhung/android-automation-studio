'use client';
import { Button } from '@/components/ui/button';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useAppPreferences } from '@/app/providers';
import { settingsApi, type HistoryRunResult, type HistorySettings } from './api';

const MAX_DAYS = 3650;
const message = (e: unknown, fallback: string) => e instanceof Error && e.message ? e.message : fallback;
const parseDays = (value: string): number => /^\d+$/.test(value.trim()) ? Number(value.trim()) : Number.NaN;
const validDays = (value: number) => Number.isInteger(value) && value >= 0 && value <= MAX_DAYS;
const formatBytes = (bytes = 0): string => {
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024; let unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit += 1; }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
};

export function HistorySettingsPanel() {
  const { t } = useAppPreferences(); const tRef = useRef(t); tRef.current = t;
  const [saved, setSaved] = useState<HistorySettings | null>(null);
  const [media, setMedia] = useState('0'); const [history, setHistory] = useState('0');
  const [loading, setLoading] = useState(true); const [busy, setBusy] = useState(false); const [cleaning, setCleaning] = useState(false);
  const [error, setError] = useState(''); const [notice, setNotice] = useState('');

  const apply = (value: HistorySettings) => { setSaved(value); setMedia(String(value.media_retention_days)); setHistory(String(value.history_retention_days)); };
  useEffect(() => {
    const controller = new AbortController();
    settingsApi.history(controller.signal).then(apply)
      .catch(e => { if (!controller.signal.aborted) setError(message(e, tRef.current('settings.history.loadError'))); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, []);

  const mediaDays = parseDays(media); const historyDays = parseDays(history);
  const dirty = saved !== null && (mediaDays !== saved.media_retention_days || historyDays !== saved.history_retention_days);
  const describe = (days: number) => days > 0 ? t('settings.history.daysValue', { count: days }) : t('settings.history.off');
  const validate = (): string => {
    if (!validDays(mediaDays) || !validDays(historyDays)) return t('settings.history.validation');
    if (mediaDays > 0 && historyDays > 0 && historyDays < mediaDays) return t('settings.history.order');
    return '';
  };
  const summary = (run: HistoryRunResult) => t('settings.history.runDone', { media: run.media_sessions_purged ?? 0, history: run.history_sessions_deleted ?? 0, size: formatBytes(run.bytes_freed) });

  async function save(event: FormEvent) {
    event.preventDefault(); setError(''); setNotice('');
    const invalid = validate(); if (invalid) { setError(invalid); return; }
    // Turning a rule on, or shortening it, makes the next pass delete data that is kept today.
    const stricter = (next: number, current: number) => next > 0 && (current === 0 || next < current);
    if (saved && (stricter(mediaDays, saved.media_retention_days) || stricter(historyDays, saved.history_retention_days))
      && !window.confirm(t('settings.history.confirm', { media: describe(mediaDays), history: describe(historyDays) }))) return;
    setBusy(true);
    try { apply(await settingsApi.saveHistory({ media_retention_days: mediaDays, history_retention_days: historyDays })); setNotice(t('settings.history.saved')); }
    catch (e) { setError(message(e, t('settings.history.saveError'))); }
    finally { setBusy(false); }
  }

  async function cleanNow() {
    setError(''); setNotice('');
    if (dirty) { setError(t('settings.history.saveFirst')); return; }
    if (!window.confirm(t('settings.history.runConfirm'))) return;
    setCleaning(true);
    try {
      const run = await settingsApi.runHistoryCleanup();
      if (run.settings) apply(run.settings);
      setNotice(run.status === 'disabled' ? t('settings.history.runDisabled') : summary(run));
    } catch (e) { setError(message(e, t('settings.history.saveError'))); }
    finally { setCleaning(false); }
  }

  const last = saved?.last_run && saved.last_run.status === 'completed' ? saved.last_run : null;
  return <section className="card settingsSection">
    <h2>{t('settings.history.title')}</h2><p>{t('settings.history.body')}</p>
    {loading ? <p role="status">{t('settings.history.loading')}</p> : <form onSubmit={save} noValidate>
      <fieldset disabled={busy || cleaning}>
        <div className="fieldGrid">
          <label>{t('settings.history.mediaDays')}
            <input type="number" inputMode="numeric" min={0} max={MAX_DAYS} step={1} value={media} onChange={e => setMedia(e.target.value)} aria-describedby="history-media-help" />
            <small id="history-media-help">{t('settings.history.mediaHelp')}</small>
          </label>
          <label>{t('settings.history.historyDays')}
            <input type="number" inputMode="numeric" min={0} max={MAX_DAYS} step={1} value={history} onChange={e => setHistory(e.target.value)} aria-describedby="history-days-help" />
            <small id="history-days-help">{t('settings.history.historyHelp')}</small>
          </label>
        </div>
        <div className="buttonRow">
          <Button type="submit" disabled={!dirty}>{t('settings.history.save')}</Button>
          <Button type="button" variant="outline" onClick={() => void cleanNow()}>{cleaning ? t('settings.history.running') : t('settings.history.runNow')}</Button>
        </div>
      </fieldset>
      {error && <div className="inlineError" role="alert">{error}</div>}
      {notice && <div className="inlineSuccess" role="status">{notice}</div>}
      <p>{last ? t('settings.history.lastRun', { time: new Date(last.ran_at * 1000).toLocaleString(), media: last.media_sessions_purged ?? 0, history: last.history_sessions_deleted ?? 0, size: formatBytes(last.bytes_freed) }) : t('settings.history.noRun')}</p>
    </form>}
  </section>;
}
