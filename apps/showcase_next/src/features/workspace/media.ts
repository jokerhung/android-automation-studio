import type { SessionVideo, VideoSegment } from './types';

export const VIDEO_RETRY_MIN_MS = 500;
export const VIDEO_RETRY_MAX_MS = 3_000;
export const VIDEO_FINALIZATION_DEADLINE_MS = 120_000;

export const clampVideoRetryDelay = (value: unknown): number => {
  const delay = typeof value === 'number' && Number.isFinite(value) ? value : 1_000;
  return Math.max(VIDEO_RETRY_MIN_MS, Math.min(VIDEO_RETRY_MAX_MS, delay));
};

export function directMediaUrl(value: unknown, origin?: string): string | null {
  if (typeof value !== 'string' || !value.trim()) return null;
  try {
    const base = origin ?? (typeof window === 'undefined' ? 'http://localhost' : window.location.origin);
    const url = new URL(value, base);
    if (url.origin !== new URL(base).origin || !url.pathname.startsWith('/videos/')) return null;
    return value.startsWith('/') ? url.pathname + url.search + url.hash : url.href;
  } catch { return null; }
}

export interface TimelineLocation { index: number; localTime: number; timelineTime: number }
const clamp=(value:number,min:number,max:number)=>Math.max(min,Math.min(max,value));
export const hasSessionOffsets=(segments:readonly VideoSegment[])=>segments.length>0&&segments.every(segment=>Number.isFinite(segment.offset_ms)&&Number.isFinite(segment.duration_ms));
export function locateTimelineTime(segments:readonly VideoSegment[],seconds:number):TimelineLocation|null {
  if (!segments.length) return null;
  const total=segments.reduce((sum,segment)=>sum+Math.max(0,segment.duration),0);
  const target=clamp(Number.isFinite(seconds)?seconds:0,0,total);
  let index=segments.findIndex(segment=>target<segment.start+segment.duration);
  if(index<0) index=segments.length-1;
  const segment=segments[index]!; const localTime=clamp(target-segment.start,0,Math.max(0,segment.duration));
  return {index,localTime,timelineTime:segment.start+localTime};
}
export function locateSessionTime(segments:readonly VideoSegment[],seconds:number):TimelineLocation|null {
  if(!segments.length)return null;
  if(!hasSessionOffsets(segments))return locateTimelineTime(segments,seconds);
  const target=(Number.isFinite(seconds)?seconds:0)*1000;
  for(let index=0;index<segments.length;index++){
    const segment=segments[index]!; const offset=segment.offset_ms as number; const end=offset+(segment.duration_ms as number);
    if(target<offset)return {index,localTime:0,timelineTime:segment.start};
    if(target<=end){const localTime=clamp((target-offset)/1000,0,Math.max(0,segment.duration));return {index,localTime,timelineTime:segment.start+localTime};}
  }
  const index=segments.length-1; const segment=segments[index]!; const localTime=Math.max(0,segment.duration);
  return {index,localTime,timelineTime:segment.start+localTime};
}

interface TimerApi { setTimeout(callback:()=>void,delay:number):ReturnType<typeof setTimeout>; clearTimeout(handle:ReturnType<typeof setTimeout>):void }
export interface VideoFinalizationRetryOptions {
  request(sessionId:string):Promise<SessionVideo>;
  isCurrent(sessionId:string,generation:number):boolean;
  onUpdate(video:SessionVideo):void;
  onTimeout():void;
  now?:()=>number;
  timers?:TimerApi;
}
export class VideoFinalizationRetry {
  private timer:ReturnType<typeof setTimeout>|null=null; private deadline=0; private sessionId=''; private generation=0;
  private readonly now:()=>number; private readonly timers:TimerApi;
  constructor(private readonly options:VideoFinalizationRetryOptions){this.now=options.now??Date.now;this.timers=options.timers??{setTimeout:(cb,ms)=>setTimeout(cb,ms),clearTimeout:handle=>clearTimeout(handle)};}
  start(sessionId:string,generation:number,initial?:SessionVideo):void { this.cancel();this.sessionId=sessionId;this.generation=generation;this.deadline=this.now()+VIDEO_FINALIZATION_DEADLINE_MS;if(initial)this.accept(initial);else void this.poll(); }
  accept(video:SessionVideo):void { if(!this.current())return;this.options.onUpdate(video);if(video.status==='processing')this.schedule(video.retry_after_ms);else this.cancelTimer(); }
  cancel():void {this.cancelTimer();this.sessionId='';}
  private current(){return Boolean(this.sessionId)&&this.options.isCurrent(this.sessionId,this.generation);}
  private async poll(){if(!this.current())return;if(this.now()>=this.deadline){this.timeout();return;}const sessionId=this.sessionId;const generation=this.generation;try{const video=await this.options.request(sessionId);if(sessionId!==this.sessionId||generation!==this.generation||!this.options.isCurrent(sessionId,generation))return;this.accept(video);}catch{if(sessionId===this.sessionId&&generation===this.generation&&this.current())this.schedule(1_000);}}
  private schedule(delay:unknown){this.cancelTimer();if(!this.current())return;const remaining=this.deadline-this.now();if(remaining<=0){this.timeout();return;}this.timer=this.timers.setTimeout(()=>{this.timer=null;if(this.now()>=this.deadline){this.timeout();return;}void this.poll();},Math.min(clampVideoRetryDelay(delay),remaining));}
  private timeout(){if(!this.current())return;this.cancelTimer();this.options.onTimeout();}
  private cancelTimer(){if(this.timer!==null){this.timers.clearTimeout(this.timer);this.timer=null;}}
}
