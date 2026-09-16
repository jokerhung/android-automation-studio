import { describe, expect, it } from 'vitest';
import { aggregateLiveSteps, eventsForSelectedSession, reconcileDetailsWithLive } from '@/features/workspace/live-aggregation';
import { initialWorkspaceState, workspaceReducer } from '@/features/workspace/reducer';
import type { SessionDetails } from '@/features/workspace/types';

const event=(type:string,session_id:string|undefined,data:Record<string,unknown>,timestamp='2026-01-01T00:00:00.000Z')=>({type,timestamp,...(session_id?{session_id}:{}),data});

describe('live details aggregation',()=>{
 it('merges live steps over persisted snapshots and preserves snapshot-only fields',()=>{
  const details:SessionDetails={session:{session_id:'a'},steps:[{step_id:'1',timestamp:1,status:'saved',image_name:'one'}],checks:{},notes:{},usage:{},video:null,startup:[]};
  const result=reconcileDetailsWithLive(details,[event('step_updated','a',{step_id:'1',timestamp:2,status:'running'}),event('step_recorded','a',{step_id:'2',timestamp:3,status:'done'})]);
  expect(result.steps).toEqual([{step_id:'1',timestamp:2,status:'running',image_name:'one'},{step_id:'2',timestamp:3,status:'done'}]);
 });
 it('ports conservative checker parent-trace and trace-id aggregation',()=>{
  const steps=aggregateLiveSteps([event('checker_event','a',{event:'attempt_started',attempt_id:'try-1',trace_id:'checker-trace'}),event('trace_recorded','a',{trace_id:'tool-1',parent_trace_id:'checker-trace',type:'tool',status:'running'}),event('trace_recorded','a',{trace_id:'tool-1',parent_trace_id:'checker-trace',type:'tool',status:'success'})]);
  expect(steps).toHaveLength(1); expect(steps[0]).toMatchObject({block_type:'checker',attempt_id:'try-1',generic_tools:[{trace_id:'tool-1',status:'success'}]});
 });
});

describe('multi-session policy and guards',()=>{
 it('admits only explicitly matching selected-session events',()=>{const events=[event('step_updated','a',{step_id:'1'}),event('step_updated','b',{step_id:'2'}),event('info',undefined,{message:'global'})];expect(eventsForSelectedSession(events,'a')).toEqual([events[0]]);expect(eventsForSelectedSession(events,null)).toEqual([]);});
 it('rejects foreign events and stale selection generations without dirtying selected details',()=>{
  let state=workspaceReducer(initialWorkspaceState,{type:'selectSession',sessionId:'a'}); const generation=state.selectionGeneration;
  const details:SessionDetails={session:{session_id:'a'},steps:[],checks:{},notes:{},usage:{},video:null,startup:[]};
  state=workspaceReducer(state,{type:'detailsRequested',sessionId:'a',requestId:1,generation}); state=workspaceReducer(state,{type:'detailsReceived',sessionId:'a',requestId:1,generation,details});
  const foreign=workspaceReducer(state,{type:'streamEventsReceived',sessionId:'b',generation,events:[event('step_updated','b',{step_id:'bad'})]}); expect(foreign).toBe(state);
  state=workspaceReducer(state,{type:'selectSession',sessionId:'b'}); const stale=workspaceReducer(state,{type:'streamEventsReceived',sessionId:'b',generation,events:[event('step_updated','b',{step_id:'stale'})]}); expect(stale).toBe(state);
 });
 it('rejects an old detail response after selection changes away and back',()=>{
  let state=workspaceReducer(initialWorkspaceState,{type:'selectSession',sessionId:'a'}); const oldGeneration=state.selectionGeneration;
  state=workspaceReducer(state,{type:'detailsRequested',sessionId:'a',requestId:1,generation:oldGeneration}); state=workspaceReducer(state,{type:'selectSession',sessionId:'b'}); state=workspaceReducer(state,{type:'selectSession',sessionId:'a'});
  const details:SessionDetails={session:{session_id:'a'},steps:[{step_id:'old'}],checks:{},notes:{},usage:{},video:null,startup:[]}; expect(workspaceReducer(state,{type:'detailsReceived',sessionId:'a',requestId:1,generation:oldGeneration,details})).toBe(state);
 });
});
