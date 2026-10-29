import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AppProviders } from '@/app/providers';
import { HomeLauncher } from '@/features/home/home-launcher';

vi.mock('next/navigation',()=>({useRouter:()=>({push:vi.fn()})}));

const json=(body:unknown)=>new Response(JSON.stringify(body),{status:200,headers:{'content-type':'application/json'}});
const readiness=(overallReady:boolean,timestamp:number)=>({overall_ready:overallReady,blocker_count:overallReady?0:1,passed_blocker_count:overallReady?3:2,probes:[],active_device:null,timestamp});
const readinessCalls=(mock:ReturnType<typeof vi.fn>)=>mock.mock.calls.filter(([url])=>url==='/api/system/readiness');

function deferred<T>() {
 let resolve!: (value:T)=>void;
 const promise=new Promise<T>(done=>{resolve=done;});
 return {promise,resolve};
}

describe('Home readiness refresh integration',()=>{
 beforeEach(()=>{vi.useFakeTimers();localStorage.clear();});
 afterEach(()=>{vi.useRealTimers();vi.unstubAllGlobals();vi.restoreAllMocks();});

 it('refreshes every 30s without resetting a dirty Home draft',async()=>{
  const reports=[readiness(true,1),readiness(false,2)];
  const fetchMock=vi.fn().mockImplementation((url:string)=>Promise.resolve(url==='/api/system/readiness'?json(reports.shift()??readiness(false,3)):json({})));
  vi.stubGlobal('fetch',fetchMock);
  render(<AppProviders><HomeLauncher/></AppProviders>);
  await act(async()=>{await Promise.resolve();await Promise.resolve();});
  expect(screen.getByText('System ready')).toBeInTheDocument();
  const goal=screen.getByLabelText('Task goal');
  fireEvent.change(goal,{target:{value:'Keep this draft'}});
  await act(async()=>{await vi.advanceTimersByTimeAsync(30000);});
  expect(screen.getByText('Setup required')).toBeInTheDocument();
  expect(goal).toHaveValue('Keep this draft');
  expect(readinessCalls(fetchMock)).toHaveLength(2);
 });

 it('pauses while hidden and refreshes immediately on visible and focus',async()=>{
  let hidden=false;
  vi.spyOn(document,'hidden','get').mockImplementation(()=>hidden);
  const fetchMock=vi.fn().mockImplementation((url:string)=>Promise.resolve(url==='/api/system/readiness'?json(readiness(true,Date.now())):json({})));
  vi.stubGlobal('fetch',fetchMock);
  render(<AppProviders><HomeLauncher/></AppProviders>);
  await act(async()=>{await Promise.resolve();await Promise.resolve();});
  expect(screen.getByText('System ready')).toBeInTheDocument();
  hidden=true;
  await act(async()=>{await vi.advanceTimersByTimeAsync(9000);});
  expect(readinessCalls(fetchMock)).toHaveLength(1);
  hidden=false;
  await act(async()=>{document.dispatchEvent(new Event('visibilitychange'));await Promise.resolve();await Promise.resolve();});
  expect(readinessCalls(fetchMock)).toHaveLength(2);
  await act(async()=>{window.dispatchEvent(new Event('focus'));await Promise.resolve();await Promise.resolve();});
  expect(readinessCalls(fetchMock)).toHaveLength(3);
 });

 it('does not overlap slow readiness requests and aborts the active request on cleanup',async()=>{
  const pending=deferred<Response>();
  let activeSignal:AbortSignal|undefined;
  const fetchMock=vi.fn().mockImplementation((url:string,init?:RequestInit)=>{
   if(url==='/api/system/readiness'){activeSignal=init?.signal??undefined;return pending.promise;}
   return Promise.resolve(json({}));
  });
  vi.stubGlobal('fetch',fetchMock);
  const view=render(<AppProviders><HomeLauncher/></AppProviders>);
  await act(async()=>{await Promise.resolve();});
  expect(readinessCalls(fetchMock)).toHaveLength(1);
  await act(async()=>{await vi.advanceTimersByTimeAsync(12000);window.dispatchEvent(new Event('focus'));document.dispatchEvent(new Event('visibilitychange'));});
  expect(readinessCalls(fetchMock)).toHaveLength(1);
  expect(activeSignal?.aborted).toBe(false);
  view.unmount();
  expect(activeSignal?.aborted).toBe(true);
  await act(async()=>{await vi.advanceTimersByTimeAsync(6000);});
  expect(readinessCalls(fetchMock)).toHaveLength(1);
 });
 it('shows a timeout and allows retry to recover without losing the draft',async()=>{
  let stall=false;
  const fetchMock=vi.fn().mockImplementation((url:string,init?:RequestInit)=>{
   if(url==='/api/system/readiness'){
    if(stall)return new Promise((_,reject)=>init!.signal!.addEventListener('abort',()=>reject(init!.signal!.reason),{once:true}));
    return Promise.resolve(json(readiness(true,Date.now())));
   }
   return Promise.resolve(json({}));
  });
  vi.stubGlobal('fetch',fetchMock);
  render(<AppProviders><HomeLauncher/></AppProviders>);
  await act(async()=>{await vi.advanceTimersByTimeAsync(0);});
  fireEvent.change(screen.getByLabelText('Task goal'),{target:{value:'Keep this draft'}});
  stall=true;
  await act(async()=>{await vi.advanceTimersByTimeAsync(75_000);});
  expect(screen.getByText('Readiness could not be loaded. Check the server connection.')).toBeInTheDocument();
  expect(screen.queryByText('System ready')).not.toBeInTheDocument();
  stall=false;
  await act(async()=>{fireEvent.click(screen.getByRole('button',{name:'Try again'}));await vi.advanceTimersByTimeAsync(0);});
  expect(screen.getByText('System ready')).toBeInTheDocument();
  expect(screen.getByLabelText('Task goal')).toHaveValue('Keep this draft');
 });

});
