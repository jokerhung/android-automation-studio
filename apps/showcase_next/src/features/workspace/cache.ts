import type { SessionStatus, SessionSummary } from './types';
export const SESSIONS_CACHE_KEY = 'artemis.sessions.v1';
export const SESSIONS_CACHE_VERSION = 1;
export const MAX_CACHED_SESSIONS = 250;
export interface SessionsCache { version: 1; cachedAt: number; sessions: readonly SessionSummary[] }
const statuses = new Set<SessionStatus>(['queued','pending','running','paused','completed','failed','stopped','cancelled','unknown']);
const record = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null && !Array.isArray(value);
function session(value: unknown): SessionSummary | null {
  if (!record(value)) return null;
  const id=typeof value.session_id==='string' ? value.session_id : typeof value.id==='string' ? value.id : null;
  if (!id) return null;
  const rawStatus=typeof value.status==='string' ? value.status.toLowerCase() : 'unknown';
  const status:SessionStatus=statuses.has(rawStatus as SessionStatus) ? rawStatus as SessionStatus : 'unknown';
  return { ...value, session_id:id, status };
}
export function normalizeSessions(value: unknown): SessionSummary[] {
  const items=Array.isArray(value) ? value : record(value) && Array.isArray(value.sessions) ? value.sessions : [];
  return items.map(session).filter((item):item is SessionSummary=>item!==null);
}
export function parseSessionsCache(raw: string | null): SessionsCache | null {
  if (!raw) return null;
  try { const value:unknown=JSON.parse(raw); if(!record(value)||value.version!==SESSIONS_CACHE_VERSION||typeof value.cachedAt!=='number'||!Number.isFinite(value.cachedAt)||value.cachedAt<0||!Array.isArray(value.sessions)) return null; const sessions=normalizeSessions(value.sessions); if(sessions.length!==value.sessions.length) return null; return {version:1,cachedAt:value.cachedAt,sessions}; } catch { return null; }
}
export function serializeSessionsCache(sessions: readonly SessionSummary[], cachedAt=Date.now()): string { return JSON.stringify({version:SESSIONS_CACHE_VERSION,cachedAt,sessions:sessions.slice(0,MAX_CACHED_SESSIONS)} satisfies SessionsCache); }
export function readSessionsCache(storage?: Pick<Storage,'getItem'>): SessionsCache | null { if(!storage) return null; try{return parseSessionsCache(storage.getItem(SESSIONS_CACHE_KEY));}catch{return null;} }
export function writeSessionsCache(sessions: readonly SessionSummary[], storage?: Pick<Storage,'setItem'>, cachedAt=Date.now()): void { if(!storage)return; try{storage.setItem(SESSIONS_CACHE_KEY,serializeSessionsCache(sessions,cachedAt));}catch{/* memory state remains authoritative */} }
