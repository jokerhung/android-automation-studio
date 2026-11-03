'use client';
import { Button } from '@/components/ui/button';
import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { useSearchParams } from 'next/navigation';
import { useAppPreferences } from '@/app/providers';
import { useWorkspace } from '../provider';
import { selectActiveSessions, selectSessionById } from '../selectors';
import { aggregateLiveSteps } from '../live-aggregation';
import { defaultHistoryDateRange, sessionInDateRange } from '../history-date-range';
import { DeviceViewer, SessionDetailsPanel, TaskList, sessionGoal, sessionProfile } from './workspace-panels';
import { HistoryDateInput } from './history-date-input';
import { DeleteFilteredHistory } from './delete-filtered-history';
import './workspace.css';
import './workspace-columns.css';
import './workspace-scroll.css';

const ACTIVE = new Set(['queued','pending','running','paused']);
export function WorkspaceClient() {
 const {t}=useAppPreferences();
 const composerRef=useRef<HTMLFormElement>(null);
 useEffect(()=>{
  const composer=composerRef.current;
  const page=composer?.closest<HTMLElement>('.workspace-page');
  if(!composer||!page)return;
  const update=()=>{
   const bottom=Number.parseFloat(window.getComputedStyle(composer).bottom)||0;
   page.style.setProperty('--ws-composer-clearance',`${Math.ceil(composer.getBoundingClientRect().height+bottom+12)}px`);
  };
  update();
  const observer=typeof ResizeObserver==='undefined'?null:new ResizeObserver(update);
  observer?.observe(composer);
  window.addEventListener('resize',update);
  return()=>{observer?.disconnect();window.removeEventListener('resize',update);page.style.removeProperty('--ws-composer-clearance');};
 },[]);

 const {state,refresh,selectSession,run,stop,resume,deleteSession}=useWorkspace(); const searchParams=useSearchParams(); const querySession=searchParams.get('session'); const query=searchParams.get('q')??'';
 const [goal,setGoal]=useState(searchParams.get('goal')??''); const [profile,setProfile]=useState<'flash'|'pro'>(searchParams.get('profile')==='pro'?'pro':'flash'); const [submitting,setSubmitting]=useState(false); const [notice,setNotice]=useState<string|null>(null);
 const [dateRange,setDateRange]=useState(()=>defaultHistoryDateRange());
 const invalidRange=Boolean(dateRange.from&&dateRange.to&&dateRange.from>dateRange.to);
 const filtered=useMemo(()=>{const needle=query.trim().toLocaleLowerCase();return state.sessions.filter(session=>!needle||[session.session_id,session.goal,session.initial_goal,session.device_id,session.device_serial].some(value=>typeof value==='string'&&value.toLocaleLowerCase().includes(needle)));},[query,state.sessions]);
 const queue=useMemo(()=>selectActiveSessions({...state,sessions:filtered}),[filtered,state]); const history=useMemo(()=>filtered.filter(item=>!ACTIVE.has(item.status)&&sessionInDateRange(item,dateRange)),[filtered,dateRange]); const selected=selectSessionById(state,state.selectedSessionId); const detailResource=state.selectedSessionId?state.details[state.selectedSessionId]:undefined; const details=selected&&ACTIVE.has(selected.status)?{session:selected,steps:aggregateLiveSteps(state.streamEvents),checks:[],notes:null,usage:null,video:null,startup:[]}:detailResource?.data??null;
 useEffect(()=>{if(querySession&&querySession!==state.selectedSessionId&&state.sessions.some(session=>session.session_id===querySession)){selectSession(querySession);return;}const running=queue.filter(session=>['running','pending','queued'].includes(session.status));if(!querySession&&!state.selectedSessionId&&running.length===1)selectSession(running[0]!.session_id);},[querySession,selectSession,state.selectedSessionId,state.sessions,queue]);
 const choose=(id:string)=>{selectSession(id);const params=new URLSearchParams(window.location.search);params.set('session',id);window.history.replaceState(null,'',window.location.pathname+'?'+params.toString());};
 const submit=async(event:FormEvent)=>{event.preventDefault();const clean=goal.trim();if(!clean||submitting)return;setSubmitting(true);setNotice(null);try{const result=await run({goal:clean,profile});const response=typeof result==='object'&&result!==null?result as Record<string,unknown>:{};const id=typeof response.session_id==='string'?response.session_id:null;if(id){selectSession(id);const params=new URLSearchParams(window.location.search);params.set('session',id);window.history.replaceState(null,'',window.location.pathname+'?'+params.toString());}setGoal('');setNotice(t(profile==='pro'?'workspace.proQueued':'workspace.flashQueued'));}catch(error){setNotice(error instanceof Error?error.message:t('workspace.startError'));}finally{setSubmitting(false);}};
 const liveStatus=state.status?.session_id===selected?.session_id?state.status?.status:null; const selectedStatus=liveStatus??selected?.status??state.status?.status??'unknown'; const running=selected?['running','queued','pending'].includes(selectedStatus):false; const paused=selectedStatus==='paused';
 return <main className="workspace-page ws-three-columns"><header className="ws-hero"><div><span className="ws-kicker">{t('workspace.kicker')}</span><h1 className="ws-sr-only">{t('workspace.title')}</h1><p>{t('workspace.heroBody')}</p></div><div className="ws-connection"><span className={'is-'+state.connection}>{state.connection}</span><Button variant="outline" type="button" className="ws-refresh" onClick={()=>void refresh()}>↻ {t('workspace.refresh')}</Button></div></header>{state.error?<div className="ws-alert" role="alert">{state.error}</div>:null}<div className="ws-layout"><aside className="ws-rail"><TaskList title={t('workspace.queue')} empty={t('workspace.queueEmpty')} tasks={queue} selectedId={state.selectedSessionId} onSelect={choose}/><fieldset className="ws-history-dates"><legend>{t('workspace.historyDateRange')}</legend><div className="ws-history-date-inputs"><HistoryDateInput label={t('workspace.historyFrom')} value={dateRange.from} invalid={invalidRange} onChange={from=>setDateRange(current=>({...current,from}))}/><HistoryDateInput label={t('workspace.historyTo')} value={dateRange.to} invalid={invalidRange} onChange={to=>setDateRange(current=>({...current,to}))}/></div>{invalidRange?<p role="alert">{t('workspace.historyInvalidDates')}</p>:null}</fieldset><TaskList title={t(query||dateRange.from||dateRange.to?'workspace.historyFiltered':'workspace.history')} empty={t(query||dateRange.from||dateRange.to?'workspace.historyFilteredEmpty':'workspace.historyEmpty')} tasks={history} selectedId={state.selectedSessionId} onSelect={choose} headerAction={<DeleteFilteredHistory sessions={history} deleteSession={deleteSession} onDeleted={ids=>{const params=new URLSearchParams(window.location.search);const id=params.get('session');if(id&&ids.includes(id)){params.delete('session');window.history.replaceState(null,'',window.location.pathname+(params.size?'?'+params.toString():''));}void refresh();}}/>}/></aside><section className="ws-main">{selected?<><article className="ws-session-header"><div><span className={'ws-status-badge is-'+selectedStatus}>{selectedStatus}</span><h2>{sessionGoal(selected)}</h2><p>{t('workspace.profileSession',{profile:sessionProfile(selected),id:selected.session_id})}</p></div><div className="ws-session-actions">{running?<Button variant="outline" type="button" className="danger" onClick={()=>void stop({session_id:selected.session_id})}>■ {t('workspace.stop')}</Button>:null}{paused?<Button variant="outline" type="button" className="primary" onClick={()=>void resume()}>▶ {t('workspace.resume')}</Button>:null}</div></article>{detailResource?.error?<div className="ws-alert" role="alert">{detailResource.error}</div>:null}<div className="ws-runtime-grid"><SessionDetailsPanel key={selected.session_id} details={details} followLogs={selectedStatus==='running'} isRunning={ACTIVE.has(selected.status)} sessionId={selected.session_id}/></div></>:<section className="ws-empty-state"><span aria-hidden>⌁</span><h2>{t('workspace.select')}</h2><p>{t('workspace.selectBody')}</p></section>}</section><section className="ws-viewer-column" aria-label={t('workspace.deviceReplay')}>{selected?<DeviceViewer key={selected.session_id} session={selected} details={details} isActive={ACTIVE.has(selected.status)}/>:<div className="ws-viewer-placeholder"><span aria-hidden>▯</span><h2>{t('workspace.deviceReplay')}</h2><p>{t('workspace.selectBody')}</p></div>}</section></div><form ref={composerRef} className={'ws-composer is-'+profile} onSubmit={submit}><div className="ws-profile" role="group" aria-label="Execution profile"><Button variant="outline" type="button" className={profile==='flash'?'active':''} onClick={()=>setProfile('flash')}>⚡ Flash</Button><Button variant="outline" type="button" className={profile==='pro'?'active':''} onClick={()=>setProfile('pro')}>✦ Pro</Button></div><label><span className="ws-sr-only">Task goal</span><textarea value={goal} onChange={event=>setGoal(event.target.value)} placeholder={profile==='pro'?'Describe a complex goal for deliberate planning…':'Describe a goal for fast autonomous execution…'} rows={2} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();event.currentTarget.form?.requestSubmit();}}}/></label><Button variant="outline" className="ws-submit" type="submit" disabled={!goal.trim()||submitting}>{submitting?'Starting…':'Start task ↑'}</Button>{notice?<div className="ws-notice" role="status">{notice}</div>:null}</form></main>;
}

