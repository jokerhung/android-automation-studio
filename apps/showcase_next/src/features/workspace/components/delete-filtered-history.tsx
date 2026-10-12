'use client';
import { useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { useAppPreferences } from '@/app/providers';
import type { SessionSummary } from '../types';

const active = new Set(['queued', 'pending', 'running', 'paused']);
export function DeleteFilteredHistory({ sessions, deleteSession, onDeleted }: {
  sessions: readonly SessionSummary[];
  deleteSession(id: string): Promise<unknown>;
  onDeleted(ids: readonly string[]): void;
}) {
  const { t } = useAppPreferences();
  const lock = useRef(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const remove = async () => {
    if (lock.current) return;
    const ids = [...new Set(sessions.filter(session => !active.has(session.status)).map(session => session.session_id))];
    if (!ids.length || !window.confirm(t('workspace.deleteHistoryConfirm', { count: ids.length }))) return;
    lock.current = true;
    setBusy(true);
    setMessage(null);
    const deleted: string[] = [];
    let failed = 0;
    try {
      for (const id of ids) {
        try { await deleteSession(id); deleted.push(id); }
        catch { failed++; }
      }
      onDeleted(deleted);
      setMessage(t(failed ? 'workspace.deleteHistoryPartial' : 'workspace.deleteHistorySuccess', { count: deleted.length, failed }));
    } finally {
      lock.current = false;
      setBusy(false);
    }
  };
  return <div className="ws-history-delete"><Button variant="outline" type="button" className="danger" disabled={busy || !sessions.length} onClick={() => void remove()}>{t(busy ? 'workspace.deletingHistory' : 'workspace.deleteHistory')}</Button>{message ? <span role="status">{message}</span> : null}</div>;
}
