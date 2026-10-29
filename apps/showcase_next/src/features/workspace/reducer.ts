import { reconcileDetailsWithLive } from './live-aggregation';
import { reduceStreamEvents } from './realtime';
import { snapshotIsCurrent } from './snapshot';
import type { AsyncResource, SessionDetails, WorkspaceAction, WorkspaceState } from './types';

export const initialWorkspaceState: WorkspaceState = { sessions: [], sessionsRequestId: 0, sessionsUpdatedAt: 0, status: null, statusRequestId: 0, statusUpdatedAt: 0, selectedSessionId: null, selectionGeneration: 0, details: {}, connection: 'idle', streamAttempt: 0, error: null, streamEvents: [], player: { sessionId: null, mode: 'video', stepIndex: 0, playing: false, playbackRate: 1, currentTime: 0, activeSegmentIndex: 0 } };
const emptyDetails = (requestId: number): AsyncResource<SessionDetails> => ({ data: null, loading: true, error: null, requestId });

export function workspaceReducer(state: WorkspaceState, action: WorkspaceAction): WorkspaceState {
  switch (action.type) {
    case 'hydrate': if (state.sessionsUpdatedAt > action.cachedAt) return state; return { ...state, sessions: action.sessions, sessionsUpdatedAt: action.cachedAt };
    case 'sessionsReceived': if (action.requestId < state.sessionsRequestId || action.receivedAt < state.sessionsUpdatedAt) return state; return { ...state, sessions: action.sessions, sessionsRequestId: action.requestId, sessionsUpdatedAt: action.receivedAt, error: null };
    case 'statusReceived': if (action.requestId < state.statusRequestId || action.receivedAt < state.statusUpdatedAt) return state; return { ...state, status: action.status, statusRequestId: action.requestId, statusUpdatedAt: action.receivedAt, error: null };
    case 'selectSession': return action.sessionId === state.selectedSessionId ? state : { ...state, selectedSessionId: action.sessionId, selectionGeneration: state.selectionGeneration + 1, streamEvents: [] };
    case 'detailsRequested': {
      const previous=state.details[action.sessionId];
      if (action.generation !== state.selectionGeneration || action.sessionId !== state.selectedSessionId || (previous && action.requestId < previous.requestId)) return state;
      return { ...state, details: { ...state.details, [action.sessionId]: { ...(previous ?? emptyDetails(action.requestId)), loading: true, error: null, requestId: action.requestId } } };
    }
    case 'detailsReceived': {
      const previous=state.details[action.sessionId];
      if (!snapshotIsCurrent({requestId:action.requestId,appliedRequestId:previous?.requestId??0,sessionId:action.sessionId,selectedSessionId:state.selectedSessionId,generation:action.generation,currentGeneration:state.selectionGeneration})) return state;
      const details=reconcileDetailsWithLive(action.details,state.streamEvents);
      return { ...state, details: { ...state.details, [action.sessionId]: { data: details, loading: false, error: null, requestId: action.requestId } } };
    }
    case 'detailsFailed': {
      const previous=state.details[action.sessionId];
      if (!snapshotIsCurrent({requestId:action.requestId,appliedRequestId:previous?.requestId??0,sessionId:action.sessionId,selectedSessionId:state.selectedSessionId,generation:action.generation,currentGeneration:state.selectionGeneration})) return state;
      return { ...state, details: { ...state.details, [action.sessionId]: { data: previous?.data ?? null, loading: false, error: action.error, requestId: action.requestId } } };
    }
    case 'sessionRemoved': { const details={...state.details}; delete details[action.sessionId]; const selected=state.selectedSessionId===action.sessionId; return { ...state, sessions: state.sessions.filter(item=>item.session_id!==action.sessionId), selectedSessionId: selected ? null : state.selectedSessionId, selectionGeneration: selected ? state.selectionGeneration+1 : state.selectionGeneration, streamEvents: selected ? [] : state.streamEvents, details }; }
    case 'sessionsCleared': return { ...state, sessions: [], selectedSessionId: null, selectionGeneration: state.selectionGeneration+1, streamEvents: [], details: {} };
    case 'connectionChanged': return { ...state, connection: action.connection, streamAttempt: action.attempt ?? state.streamAttempt };
    case 'videoUpdated': {
      if (action.sessionId !== state.selectedSessionId || action.generation !== state.selectionGeneration) return state;
      const resource=state.details[action.sessionId]; if(!resource?.data)return state;
      return { ...state, details: { ...state.details, [action.sessionId]: { ...resource, data: { ...resource.data, video: action.video } } } };
    }
    case 'playerSessionChanged': return state.player.sessionId===action.sessionId ? state : { ...state, player: { sessionId: action.sessionId, mode: action.mode, stepIndex: 0, playing: false, playbackRate: 1, currentTime: 0, activeSegmentIndex: 0 } };
    case 'playerPatched': return { ...state, player: { ...state.player, ...action.patch } };
    case 'streamEventsReceived': {
      if (action.sessionId !== state.selectedSessionId || action.generation !== state.selectionGeneration) return state;
      const streamEvents=reduceStreamEvents(state.streamEvents,action.events);
      const resource=state.details[action.sessionId];
      if (!resource?.data) return { ...state, streamEvents };
      return { ...state, streamEvents, details: { ...state.details, [action.sessionId]: { ...resource, data: reconcileDetailsWithLive(resource.data,action.events) } } };
    }
    case 'error': return { ...state, error: action.error };
  }
}
