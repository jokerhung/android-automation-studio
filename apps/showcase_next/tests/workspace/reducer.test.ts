import { describe,expect,it } from 'vitest';
import { initialWorkspaceState,workspaceReducer } from '@/features/workspace/reducer';

describe('workspaceReducer',()=>{
 it('rejects stale sessions and status snapshots',()=>{
  const fresh=workspaceReducer(initialWorkspaceState,{type:'sessionsReceived',sessions:[{session_id:'new',status:'running'}],requestId:2,receivedAt:200});
  expect(workspaceReducer(fresh,{type:'sessionsReceived',sessions:[{session_id:'old',status:'failed'}],requestId:1,receivedAt:100})).toBe(fresh);
  const status=workspaceReducer(fresh,{type:'statusReceived',status:{status:'running'},requestId:4,receivedAt:400});
  expect(workspaceReducer(status,{type:'statusReceived',status:{status:'idle'},requestId:3,receivedAt:300})).toBe(status);
 });
 it('rejects stale detail responses and clears selection on delete',()=>{
  let state=workspaceReducer(initialWorkspaceState,{type:'sessionsReceived',sessions:[{session_id:'a',status:'completed'}],requestId:1,receivedAt:1});
  state=workspaceReducer(state,{type:'selectSession',sessionId:'a'});
  state=workspaceReducer(state,{type:'detailsRequested',sessionId:'a',requestId:5,generation:state.selectionGeneration});
  expect(workspaceReducer(state,{type:'detailsFailed',sessionId:'a',requestId:4,generation:state.selectionGeneration,error:'old'})).toBe(state);
  const removed=workspaceReducer(state,{type:'sessionRemoved',sessionId:'a'});
  expect(removed.sessions).toEqual([]); expect(removed.selectedSessionId).toBeNull(); expect(removed.details.a).toBeUndefined();
 });
 it('keeps duplicate removal harmless and resets session state',()=>{
  let state=workspaceReducer(initialWorkspaceState,{type:'sessionsReceived',sessions:[{session_id:'a',status:'completed'}],requestId:1,receivedAt:1});
  state=workspaceReducer(state,{type:'selectSession',sessionId:'a'});
  const removed=workspaceReducer(state,{type:'sessionRemoved',sessionId:'a'});
  const duplicate=workspaceReducer(removed,{type:'sessionRemoved',sessionId:'a'});
  expect(duplicate.sessions).toEqual([]); expect(duplicate.selectedSessionId).toBeNull();
  expect(workspaceReducer(state,{type:'sessionsCleared'})).toMatchObject({sessions:[],selectedSessionId:null,details:{}});
 });
 it('coalesces stream identities and deduplicates traces through reducer actions',()=>{
  let state=workspaceReducer(initialWorkspaceState,{type:'selectSession',sessionId:'a'});
  state=workspaceReducer(state,{type:'streamEventsReceived',sessionId:'a',generation:state.selectionGeneration,events:[{type:'llm_stream',timestamp:'2026-01-01T00:00:00.000Z',data:{execution_id:'e1',stream_type:'text',chunk:'a'}},{type:'llm_stream',timestamp:'2026-01-01T00:00:00.001Z',data:{execution_id:'e1',stream_type:'thinking',chunk:'x'}}]});
  state=workspaceReducer(state,{type:'streamEventsReceived',sessionId:'a',generation:state.selectionGeneration,events:[{type:'llm_stream',timestamp:'2026-01-01T00:00:00.002Z',data:{execution_id:'e1',stream_type:'text',chunk:'b'}},{type:'trace_recorded',timestamp:'2026-01-01T00:00:00.003Z',data:{trace_id:'t1',status:'running'}},{type:'trace_recorded',timestamp:'2026-01-01T00:00:00.004Z',data:{trace_id:'t1',status:'success'}}]});
  expect(state.streamEvents).toHaveLength(3);
  expect(state.streamEvents[0]?.data.text).toBe('ab');expect(state.streamEvents[1]?.data.text).toBe('x');expect(state.streamEvents[2]?.data.status).toBe('success');
 });
 it('tracks bounded reconnect state transitions without losing sessions',()=>{
  const hydrated=workspaceReducer(initialWorkspaceState,{type:'hydrate',sessions:[{session_id:'cached',status:'completed'}],cachedAt:1});
  const backoff=workspaceReducer(hydrated,{type:'connectionChanged',connection:'backoff',attempt:4});
  const open=workspaceReducer(backoff,{type:'connectionChanged',connection:'open',attempt:0});
  expect(backoff.streamAttempt).toBe(4); expect(open.connection).toBe('open'); expect(open.streamAttempt).toBe(0);
  expect(open.sessions).toEqual(hydrated.sessions);
 });
});
