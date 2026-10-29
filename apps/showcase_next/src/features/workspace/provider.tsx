'use client';
import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, type ReactNode } from 'react';
import { workspaceApi } from './api';
import { readSessionsCache, SESSIONS_CACHE_KEY, writeSessionsCache } from './cache';
import { PollCoordinator } from './poll-coordinator';
import { StreamChunkAccumulator, toWorkspaceStreamEvent } from './realtime';
import { eventsForSelectedSession } from './live-aggregation';
import { VideoFinalizationRetry } from './media';
import { initialWorkspaceState, workspaceReducer } from './reducer';
import type { PlayerMode, RunTaskInput, SessionDetails, StopTaskInput, WorkspacePlayerState, WorkspaceState } from './types';

const STATUS_POLL_MS=2_000;
const SESSIONS_POLL_MS=6_000;
const IDLE_POLL_MS=30_000;
const RECONCILE_DELAY_MS=100;
export const STREAM_STALE_MS=30_000;
const STREAM_BACKOFF_MS=[500,1_000,2_000,5_000,10_000,20_000] as const;
const STREAM_EVENTS=['info','keep-alive','llm_stream','llm_stream_reset','trace_recorded','step_recorded','step_updated','background_tasks_updated','task_paused','task_resumed','llm_retrying','startup_progress','session_started','session_ended','recording_ready','recording_failed','checker_event'] as const;
type WorkspaceContextValue={state:WorkspaceState;refresh():Promise<void>;selectSession(id:string|null):void;loadSessionDetails(id:string):Promise<SessionDetails|null>;setPlayerSession(id:string,mode:PlayerMode):void;patchPlayer(patch:Partial<Omit<WorkspacePlayerState,'sessionId'>>):void;run(input:RunTaskInput):Promise<unknown>;stop(input?:StopTaskInput):Promise<unknown>;resume():Promise<unknown>;deleteSession(id:string):Promise<unknown>;cleanup():Promise<unknown>};
const WorkspaceContext=createContext<WorkspaceContextValue|null>(null);
const errorMessage=(error:unknown)=>error instanceof Error?error.message:String(error);

export function WorkspaceProvider({children}:{children:ReactNode}){
 const [state,dispatch]=useReducer(workspaceReducer,initialWorkspaceState);
 const stateRef=useRef(state);stateRef.current=state;
 const requestId=useRef(0);const mounted=useRef(false);const nextRequest=()=>++requestId.current;
 const videoRetryRef=useRef<VideoFinalizationRetry|null>(null);
 if(!videoRetryRef.current)videoRetryRef.current=new VideoFinalizationRetry({request:id=>workspaceApi.video(id),isCurrent:(id,generation)=>mounted.current&&stateRef.current.selectedSessionId===id&&stateRef.current.selectionGeneration===generation,onUpdate:video=>{const current=stateRef.current;if(current.selectedSessionId)dispatch({type:'videoUpdated',sessionId:current.selectedSessionId,generation:current.selectionGeneration,video});},onTimeout:()=>{const current=stateRef.current;if(current.selectedSessionId)dispatch({type:'videoUpdated',sessionId:current.selectedSessionId,generation:current.selectionGeneration,video:{session_id:current.selectedSessionId,status:'failed',has_video:false,video_url:null,video_segments:[],message:'Recording finalization timed out. You can retry.'}});}});
 const refreshSessions=useCallback(async(signal?:AbortSignal)=>{const id=nextRequest();try{const sessions=await workspaceApi.sessions(signal);const at=Date.now();if(!signal?.aborted){dispatch({type:'sessionsReceived',sessions,requestId:id,receivedAt:at});if(typeof window!=='undefined')writeSessionsCache(sessions,window.localStorage,at);}}catch(error){if(!signal?.aborted)dispatch({type:'error',error:errorMessage(error)});}},[]);
 const refreshStatus=useCallback(async(signal?:AbortSignal)=>{const id=nextRequest();try{const status=await workspaceApi.status(signal);if(!signal?.aborted)dispatch({type:'statusReceived',status,requestId:id,receivedAt:Date.now()});}catch(error){if(!signal?.aborted)dispatch({type:'error',error:errorMessage(error)});}},[]);
 const refresh=useCallback(async()=>{await Promise.all([refreshStatus(),refreshSessions()]);},[refreshSessions,refreshStatus]);
 const loadSessionDetails=useCallback(async(id:string)=>{const idRequest=nextRequest();const generation=stateRef.current.selectionGeneration;dispatch({type:'detailsRequested',sessionId:id,requestId:idRequest,generation});try{const details=await workspaceApi.details(id);if(mounted.current)dispatch({type:'detailsReceived',sessionId:id,requestId:idRequest,generation,details});if(details.video?.status==='processing')videoRetryRef.current?.start(id,generation,details.video);else videoRetryRef.current?.cancel();return details;}catch(error){if(mounted.current)dispatch({type:'detailsFailed',sessionId:id,requestId:idRequest,generation,error:errorMessage(error)});return null;}},[]);
 const mutate=useCallback(async<T,>(operation:()=>Promise<T>,after:()=>void|Promise<void>)=>{try{const result=await operation();await after();return result;}catch(error){dispatch({type:'error',error:errorMessage(error)});throw error;}},[]);
 const run=useCallback((input:RunTaskInput)=>mutate(()=>workspaceApi.run(input),refresh),[mutate,refresh]);
 const stop=useCallback((input:StopTaskInput={})=>mutate(()=>workspaceApi.stop(input),refresh),[mutate,refresh]);
 const resume=useCallback(()=>mutate(()=>workspaceApi.resume(),refresh),[mutate,refresh]);
 const deleteSession=useCallback((id:string)=>mutate(()=>workspaceApi.deleteSession(id),()=>{dispatch({type:'sessionRemoved',sessionId:id});return refreshStatus();}),[mutate,refreshStatus]);
 const cleanup=useCallback(()=>mutate(()=>workspaceApi.cleanup(),()=>{dispatch({type:'sessionsCleared'});if(typeof window!=='undefined')try{window.localStorage.removeItem(SESSIONS_CACHE_KEY);}catch{}return refreshStatus();}),[mutate,refreshStatus]);
 useEffect(()=>{
  mounted.current=true;if(typeof window==='undefined')return()=>{mounted.current=false;};
  const cached=readSessionsCache(window.localStorage);if(cached)dispatch({type:'hydrate',sessions:cached.sessions,cachedAt:cached.cachedAt});
  let streamOpen=false;
  let lastStatusPoll=0;let lastSessionsPoll=0;
  const isIdle=()=>{const status=stateRef.current.status;return status?.status==='idle'&&!status.active_tasks?.length&&!status.queue?.length;};
  const poll=async(kind:'status'|'sessions',signal:AbortSignal)=>{
   if(streamOpen)return;
   const now=Date.now();const last=kind==='status'?lastStatusPoll:lastSessionsPoll;
   if(isIdle()&&last&&now-last<IDLE_POLL_MS)return;
   if(kind==='status'){lastStatusPoll=now;await refreshStatus(signal);}else{lastSessionsPoll=now;await refreshSessions(signal);}
  };
  const coordinator=new PollCoordinator({status:{intervalMs:STATUS_POLL_MS,run:signal=>poll('status',signal)},sessions:{intervalMs:SESSIONS_POLL_MS,run:signal=>poll('sessions',signal)}});coordinator.start();
  let source:EventSource|null=null;let reconnectTimer:number|undefined;let attempt=0;let disposed=false;let lastActivity=Date.now();
  const dispatchSelectedEvents=(events:readonly ReturnType<typeof toWorkspaceStreamEvent>[])=>{const current=stateRef.current;const selected=eventsForSelectedSession(events,current.selectedSessionId);if(current.selectedSessionId&&selected.length)dispatch({type:'streamEventsReceived',sessionId:current.selectedSessionId,generation:current.selectionGeneration,events:selected});};
  const accumulator=new StreamChunkAccumulator(dispatchSelectedEvents);
  let reconcileTimer:number|undefined;
  const detailSessions=new Set<string>();
  const reconcile=(sessionId?:string)=>{
   attempt=0;if(document.hidden)return;
   if(sessionId)detailSessions.add(sessionId);
   if(reconcileTimer!==undefined)return;
   reconcileTimer=window.setTimeout(()=>{
    reconcileTimer=undefined;
    if(disposed||document.hidden){detailSessions.clear();return;}
    void refresh();const selected=stateRef.current.selectedSessionId;
    if(selected&&detailSessions.has(selected))void loadSessionDetails(selected);
    detailSessions.clear();
   },RECONCILE_DELAY_MS);
  };
  const onEvent=(event:Event)=>{if(disposed)return;lastActivity=Date.now();const message=event as MessageEvent<string>;const type=message.type||'message';if(type==='keep-alive'||type==='info')return;let data:Record<string,unknown>;try{const parsed=JSON.parse(message.data);data=typeof parsed==='object'&&parsed!==null?parsed as Record<string,unknown>:{raw:message.data};}catch{data={raw:message.data};}if(type==='llm_stream'){accumulator.push(data);return;}accumulator.beforeNonStream(type,data);dispatchSelectedEvents([toWorkspaceStreamEvent(type,data)]);reconcile(typeof data.session_id==='string'?data.session_id:undefined);};
  const closeSource=()=>{if(source){source.onopen=null;source.onerror=null;source.onmessage=null;source.close();source=null;}};
  const reconnect=()=>{
   streamOpen=false;closeSource();
   if(disposed||reconnectTimer!==undefined)return;
   const delay=STREAM_BACKOFF_MS[Math.min(attempt,STREAM_BACKOFF_MS.length-1)]!;
   attempt=Math.min(attempt+1,STREAM_BACKOFF_MS.length);
   dispatch({type:'connectionChanged',connection:'backoff',attempt});
   reconnectTimer=window.setTimeout(()=>{reconnectTimer=undefined;connect();},delay);
  };
  const connect=()=>{
   if(disposed)return;
   if(typeof EventSource==='undefined'){dispatch({type:'connectionChanged',connection:'unsupported'});return;}
   dispatch({type:'connectionChanged',connection:'connecting',attempt});
   const current=new EventSource('/api/stream');source=current;lastActivity=Date.now();
   current.onopen=()=>{if(disposed||source!==current)return;lastActivity=Date.now();streamOpen=true;attempt=0;void refresh();const currentState=stateRef.current;const selected=currentState.selectedSessionId;const summary=currentState.sessions.find(session=>session.session_id===selected);const terminal=summary&&['completed','failed','stopped','cancelled'].includes(summary.status);if(selected&&!document.hidden&&(!terminal||!currentState.details[selected]?.data))void loadSessionDetails(selected);dispatch({type:'connectionChanged',connection:'open',attempt:0});};
   current.onerror=()=>{if(source===current)reconnect();};
   const receive=(event:Event)=>{if(source===current)onEvent(event);};
   current.onmessage=receive;for(const event of STREAM_EVENTS)current.addEventListener(event,receive);
  };
  // The server sends a heartbeat every 5s. OPEN alone cannot detect a half-open socket.
  const checkStream=()=>{if(!document.hidden&&source&&Date.now()-lastActivity>=STREAM_STALE_MS)reconnect();};
  const onActive=()=>{if(document.hidden)return;checkStream();void refresh();};
  document.addEventListener('visibilitychange',onActive);
  window.addEventListener('focus',onActive);window.addEventListener('online',onActive);
  const watchdog=window.setInterval(checkStream,5_000);
  connect();return()=>{disposed=true;mounted.current=false;coordinator.stop();accumulator.dispose();if(reconcileTimer!==undefined)window.clearTimeout(reconcileTimer);detailSessions.clear();document.removeEventListener('visibilitychange',onActive);window.removeEventListener('focus',onActive);window.removeEventListener('online',onActive);window.clearInterval(watchdog);if(reconnectTimer!==undefined)window.clearTimeout(reconnectTimer);closeSource();videoRetryRef.current?.cancel();};
 },[loadSessionDetails,refresh,refreshSessions,refreshStatus]);
 const value=useMemo<WorkspaceContextValue>(()=>({state,refresh,selectSession:id=>{videoRetryRef.current?.cancel();dispatch({type:'selectSession',sessionId:id});},loadSessionDetails,setPlayerSession:(id,mode)=>dispatch({type:'playerSessionChanged',sessionId:id,mode}),patchPlayer:patch=>dispatch({type:'playerPatched',patch}),run,stop,resume,deleteSession,cleanup}),[state,refresh,loadSessionDetails,run,stop,resume,deleteSession,cleanup]);
 return <WorkspaceContext.Provider value={value}>{children}</WorkspaceContext.Provider>;
}
export function useWorkspace():WorkspaceContextValue{const value=useContext(WorkspaceContext);if(!value)throw new Error('useWorkspace must be used under WorkspaceProvider');return value;}
