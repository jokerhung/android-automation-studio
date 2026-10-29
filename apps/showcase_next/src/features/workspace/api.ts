import { apiPath, apiRequest } from '@/lib/api/client';
import { normalizeSessions } from './cache';
import type { RunTaskInput, SessionCheck, SessionDetails, SessionStep, SessionVideo, StopTaskInput, WorkspaceStatus } from './types';
const asArray=(value:unknown):readonly Record<string,unknown>[]=>Array.isArray(value)?value.filter((item):item is Record<string,unknown>=>typeof item==='object'&&item!==null):[];
export const workspaceApi={
 sessions: async(signal?:AbortSignal)=>normalizeSessions(await apiRequest<unknown>('/api/sessions',signal?{signal}:{})),
 status: (signal?:AbortSignal)=>apiRequest<WorkspaceStatus>('/api/status',signal?{signal}:{}),
 video: (id:string,signal?:AbortSignal)=>apiRequest<SessionVideo>(apiPath('/api/sessions',id,'video'),signal?{signal}:{}),
 run: (input:RunTaskInput,signal?:AbortSignal)=>apiRequest<unknown,RunTaskInput>('/api/run',{method:'POST',body:input,...(signal?{signal}:{})}),
 stop: (input:StopTaskInput={},signal?:AbortSignal)=>apiRequest<unknown,StopTaskInput>('/api/stop',{method:'POST',query:{all:input.all??false,session_id:input.session_id,device_id:input.device_id},body:input,...(signal?{signal}:{})}),
 resume: (signal?:AbortSignal)=>apiRequest<unknown>('/api/resume',{method:'POST',...(signal?{signal}:{})}),
 deleteSession: (id:string,signal?:AbortSignal)=>apiRequest<unknown>(apiPath('/api/sessions',id,'delete'),{method:'POST',...(signal?{signal}:{})}),
 cleanup: (signal?:AbortSignal)=>apiRequest<unknown>('/api/cleanup',{method:'POST',...(signal?{signal}:{})}),
 details: async(id:string,signal?:AbortSignal):Promise<SessionDetails>=>{const option=signal?{signal}:{}; const base=apiPath('/api/sessions',id); const [steps,checks,notes,usage,video,startup]=await Promise.all([
  apiRequest<unknown>(apiPath(base,'steps'),option),apiRequest<unknown>(apiPath(base,'checks'),option),apiRequest<unknown>(apiPath(base,'notes'),option),apiRequest<unknown>(apiPath(base,'usage'),option),apiRequest<SessionVideo>(apiPath(base,'video'),option),apiRequest<unknown>(apiPath(base,'startup_progress'),option)
 ]); return {session:{session_id:id},steps:asArray(steps) as readonly SessionStep[],checks:checks as readonly SessionCheck[]|Record<string,unknown>,notes,usage,video,startup:asArray(startup)};}
};
