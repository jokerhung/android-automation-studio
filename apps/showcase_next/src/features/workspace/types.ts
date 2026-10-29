export type SessionId = string;
export type SessionStatus = 'queued' | 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'stopped' | 'cancelled' | 'unknown';
export type ConnectionStatus = 'idle' | 'connecting' | 'open' | 'backoff' | 'unsupported';

export interface SessionSummary {
  session_id: SessionId;
  status: SessionStatus;
  goal?: string;
  initial_goal?: string;
  start_time?: number;
  end_time?: number | null;
  created_at?: string;
  updated_at?: string;
  device_id?: string | null;
  device_serial?: string | null;
  video_url?: string | null;
  recording_status?: string;
  [key: string]: unknown;
}

export interface ActiveTask { session_id?: SessionId | null; device_id?: string; goal?: string; [key: string]: unknown }
export interface WorkspaceStatus {
  status: string;
  session_id?: SessionId | null;
  goal?: string | null;
  paused_error?: string | null;
  queue?: readonly Record<string, unknown>[];
  active_tasks?: readonly ActiveTask[];
  background_tasks?: readonly Record<string, unknown>[];
  [key: string]: unknown;
}
export interface SessionStep { step_id?: string; id?: string; step_number?: number; status?: string; [key: string]: unknown }
export interface SessionCheck { name?: string; status?: string; passed?: boolean; message?: string; [key: string]: unknown }
export type RecordingPlaybackStatus = 'idle' | 'live' | 'processing' | 'ready' | 'failed' | 'unavailable';
export interface VideoSegment { url: string; start: number; duration: number; width?: number; height?: number; offset_ms?: number; duration_ms?: number }
export interface SessionVideo { session_id?: string; status?: 'processing' | 'ready' | 'failed' | 'unavailable'; has_video?: boolean; video_url?: string | null; video_segments?: readonly VideoSegment[]; retry_after_ms?: number; message?: string; [key: string]: unknown }
export type PlayerMode = 'live' | 'steps' | 'video';
export interface WorkspacePlayerState { sessionId: SessionId | null; mode: PlayerMode; stepIndex: number; playing: boolean; playbackRate: number; currentTime: number; activeSegmentIndex: number }
export interface SessionDetails { session: Record<string, unknown>; steps: readonly SessionStep[]; checks: unknown; notes: unknown; usage: unknown; video: SessionVideo | null; startup: readonly Record<string, unknown>[] }
export interface AsyncResource<T> { data: T | null; loading: boolean; error: string | null; requestId: number }
import type { WorkspaceStreamEvent } from './realtime';

export interface WorkspaceState {
  sessions: readonly SessionSummary[];
  sessionsRequestId: number;
  sessionsUpdatedAt: number;
  status: WorkspaceStatus | null;
  statusRequestId: number;
  statusUpdatedAt: number;
  selectedSessionId: SessionId | null;
  selectionGeneration: number;
  details: Readonly<Record<SessionId, AsyncResource<SessionDetails>>>;
  connection: ConnectionStatus;
  streamAttempt: number;
  error: string | null;
  streamEvents: readonly WorkspaceStreamEvent[];
  player: WorkspacePlayerState;
}
export type WorkspaceAction =
  | { type: 'hydrate'; sessions: readonly SessionSummary[]; cachedAt: number }
  | { type: 'sessionsReceived'; sessions: readonly SessionSummary[]; requestId: number; receivedAt: number }
  | { type: 'statusReceived'; status: WorkspaceStatus; requestId: number; receivedAt: number }
  | { type: 'selectSession'; sessionId: SessionId | null }
  | { type: 'detailsRequested'; sessionId: SessionId; requestId: number; generation: number }
  | { type: 'detailsReceived'; sessionId: SessionId; requestId: number; generation: number; details: SessionDetails }
  | { type: 'detailsFailed'; sessionId: SessionId; requestId: number; generation: number; error: string }
  | { type: 'sessionRemoved'; sessionId: SessionId }
  | { type: 'sessionsCleared' }
  | { type: 'connectionChanged'; connection: ConnectionStatus; attempt?: number }
  | { type: 'streamEventsReceived'; sessionId: SessionId; generation: number; events: readonly WorkspaceStreamEvent[] }
  | { type: 'videoUpdated'; sessionId: SessionId; generation: number; video: SessionVideo }
  | { type: 'playerSessionChanged'; sessionId: SessionId; mode: PlayerMode }
  | { type: 'playerPatched'; patch: Partial<Omit<WorkspacePlayerState, 'sessionId'>> }
  | { type: 'error'; error: string | null };

export interface RunTaskInput { goal?: string; goals?: readonly string[]; profile?: string; expected_output?: string; enable_outputter?: boolean; verification_level?: number; explorer_mode?: string; locked_app_package?: string; app_path?: string; device_serial?: string; ingress?: string; session_id?: string; conversation_id?: string }
export interface StopTaskInput { all?: boolean; session_id?: string; device_id?: string }
