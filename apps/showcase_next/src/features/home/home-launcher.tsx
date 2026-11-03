'use client';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import { PageShell } from '@/components/page-shell';
import { useAppPreferences } from '@/app/providers';
import { ApiError } from '@/lib/api/client';
import { homeApi } from './api';
import type { ExecutionProfile, ExplorerModeId, RunTaskRequest, SystemReadinessReport, VerificationLevelId } from './models';
import { suggestsPro } from './recommendations';
import { createReadinessRefreshCoordinator, type ReadinessRefreshCoordinator } from './readiness-refresh';
import { DEFAULT_EXPLORER_MODE, DEFAULT_VERIFICATION_LEVEL, EXPLORER_MODES, levelIndex, VERIFICATION_LEVELS } from './tuning';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Zap, Brain, Play } from 'lucide-react';

import { enHome, viHome } from './angular-copy';
type TuningKind='verification'|'explorer';
export function HomeLauncher(){
 const {t,preferences}=useAppPreferences(); const copy=preferences.language==='vi'?viHome:enHome; const router=useRouter();
 const readinessRefresh=useRef<ReadinessRefreshCoordinator|null>(null);
 const [goal,setGoal]=useState(''); const [profile,setProfile]=useState<ExecutionProfile>('flash');
 const [readiness,setReadiness]=useState<SystemReadinessReport|null>(null); const [readinessError,setReadinessError]=useState(false);
 const [verification,setVerification]=useState(DEFAULT_VERIFICATION_LEVEL); const [explorer,setExplorer]=useState(DEFAULT_EXPLORER_MODE);
 const defaults=useRef<{verification:VerificationLevelId;explorer:ExplorerModeId}>({verification:DEFAULT_VERIFICATION_LEVEL,explorer:DEFAULT_EXPLORER_MODE}); const touched=useRef(false);
 const [expectedOutput,setExpectedOutput]=useState(''); const [enableOutputter,setEnableOutputter]=useState(true);
 const [activeTip,setActiveTip]=useState<TuningKind|null>(null);
 const [submitting,setSubmitting]=useState(false); const [error,setError]=useState<string|null>(null); const runController=useRef<AbortController|null>(null);
 useEffect(()=>{
  const defaultsController=new AbortController();
  const readinessCoordinator=createReadinessRefreshCoordinator({
   refresh:signal=>homeApi.readiness(signal).then(result=>{setReadiness(result);setReadinessError(false);}),
   onError:()=>setReadinessError(true),
  });
  readinessRefresh.current=readinessCoordinator;
  readinessCoordinator.start();
  void homeApi.defaults(defaultsController.signal).then(result=>{const v=VERIFICATION_LEVELS[levelIndex(VERIFICATION_LEVELS,result.verification_level,DEFAULT_VERIFICATION_LEVEL)]!.id;const e=EXPLORER_MODES[levelIndex(EXPLORER_MODES,result.explorer_mode,DEFAULT_EXPLORER_MODE)]!.id;defaults.current={verification:v,explorer:e};if(!touched.current){setVerification(v);setExplorer(e);}}).catch(()=>undefined);
  return()=>{readinessRefresh.current=null;readinessCoordinator.stop();defaultsController.abort();runController.current?.abort();};
 },[]);
 const ready=!readinessError&&readiness?.overall_ready===true; const proPrompt=profile==='flash'&&suggestsPro(goal);
 const resetTuning=()=>{setVerification(defaults.current.verification);setExplorer(defaults.current.explorer);touched.current=false;};
 const submit=async(event?:FormEvent)=>{event?.preventDefault();const cleanGoal=goal.trim();if(!cleanGoal){setError(t('home.goalRequired'));return;}if(!ready){setError(t('home.prerequisitesError'));return;}const controller=new AbortController();runController.current=controller;setSubmitting(true);setError(null);const body:RunTaskRequest={goal:cleanGoal,profile};if(profile==='pro'){if(expectedOutput.trim())body.expected_output=expectedOutput.trim();body.enable_outputter=enableOutputter;body.verification_level=verification;body.explorer_mode=explorer;}try{const result=await homeApi.run(body,controller.signal);const task=result.tasks?.find(item=>typeof item.session_id==='string'&&item.session_id)?.session_id;router.push(task?`/workspace/?session=${encodeURIComponent(task)}`:'/workspace');}catch(cause){if((cause as Error).name!=='AbortError'){setError(cause instanceof ApiError?cause.message:t('home.runError'));setSubmitting(false);}}finally{if(runController.current===controller)runController.current=null;}};
 const sliders=[{kind:'verification' as const,label:t('home.resultCheck'),ends:[t('home.off'),t('home.strict')] as const,levels:VERIFICATION_LEVELS,index:levelIndex(VERIFICATION_LEVELS,verification,DEFAULT_VERIFICATION_LEVEL),set:(value:number)=>setVerification(VERIFICATION_LEVELS[value]!.id as VerificationLevelId)},{kind:'explorer' as const,label:t('home.screenReading'),ends:[t('home.faster'),t('home.sharper')] as const,levels:EXPLORER_MODES,index:levelIndex(EXPLORER_MODES,explorer,DEFAULT_EXPLORER_MODE),set:(value:number)=>setExplorer(EXPLORER_MODES[value]!.id as ExplorerModeId)}];
 return <PageShell eyebrow="home.eyebrow" title="home.title" body="home.body">
  {ready && <span className="sr-only" role="status">{t('home.ready')}</span>}
  {!ready && <section className={'homeReadiness '+(ready?'ready':'pending')} aria-live="polite"><span className="readinessDot"/><div><strong>{!readiness&&!readinessError?t('home.checking'):ready?t('home.ready'):t('home.notReady')}</strong><p>{readinessError?t('home.readinessError'):ready?t('home.readyBody'):readiness?t('home.notReadyBody',{count:readiness.blocker_count}):t('home.checkingBody')}</p></div>{readinessError&&<Button variant="outline" type="button" onClick={()=>readinessRefresh.current?.refresh()}>{t('common.retry')}</Button>}{readiness&&!ready&&<a href="/settings?tab=system">{t('home.openSetup')}</a>}</section>}
  <form className={'homeComposer card '+(profile==='pro'?'pro':'')} onSubmit={submit}>
   {proPrompt&&<div className="intentSuggestion"><span>✦ {t('home.proRecommended')} <strong>{t('home.proMode')}</strong></span><Button variant="ghost" type="button" onClick={()=>setProfile('pro')}>{t('home.switchToPro')} →</Button></div>}
   <label className="sr-only" htmlFor="task-goal">{t('home.goal')}</label><Textarea id="task-goal" value={goal} onChange={e=>setGoal(e.target.value)} onKeyDown={e=>{if((e.ctrlKey||e.metaKey)&&e.key==='Enter')void submit();}} disabled={submitting} placeholder={copy['home.taskPlaceholder']} rows={3}/>
   {error&&<div className="homeError" role="alert">⚠ {error}</div>}
   <div className="homeActions"><div className="segmented" role="group" aria-label={t('home.executionMode')}><Button variant="ghost" type="button" className={profile==='flash'?'selected':''} onClick={()=>setProfile('flash')} title={t('home.flashTitle')}><Zap size={16}/> {t('home.flash')}</Button><Button variant="ghost" type="button" className={profile==='pro'?'selected':''} onClick={()=>setProfile('pro')} title={t('home.proTitle')}><Brain size={16}/> {t('home.pro')}</Button></div><span className="charCount">{goal.length? t('home.characterCount',{count:goal.length}):''}</span><Button variant="ghost" className="primary" disabled={!goal.trim()||submitting||!ready} title={!ready?t('home.completeSetup'):t('home.runTask')}>{submitting?t('home.starting'):<><Play size={16}/>{t('home.runTask')}</>}</Button></div>
  </form>
  {profile==='pro'&&<section className="proOptions">
   <div className="card outputCard"><div className="sectionHeading"><strong>{t('home.expectedOutput')}</strong><span>{t('home.optional')}</span></div><Input aria-label={t('home.expectedOutput')} value={expectedOutput} onChange={e=>setExpectedOutput(e.target.value)} placeholder={t('home.expectedOutputPlaceholder')}/><label className="checkLabel"><input type="checkbox" checked={enableOutputter} onChange={e=>setEnableOutputter(e.target.checked)}/>{t('home.enableOutputter')}</label></div>
   <div className="card tuningCard"><div className="sectionHeading"><strong>{t('home.proSettings')}</strong>{(verification!==defaults.current.verification||explorer!==defaults.current.explorer)&&<Button variant="ghost" type="button" onClick={resetTuning}>{t('home.reset')}</Button>}</div>{sliders.map(slider=>{const original=slider.levels[slider.index]!;const prefix=`home.tuning.${slider.kind}.${original.id}`;const level={...original,label:copy[`${prefix}.label`]??original.label,tagline:copy[`${prefix}.tagline`]??original.tagline,latency:copy[`${prefix}.latency`]??original.latency,runs:original.runs.map((line,index)=>copy[`${prefix}.runs.${index}`]??line),skips:original.skips?.map((line,index)=>copy[`${prefix}.skips.${index}`]??line),bestFor:copy[`${prefix}.bestFor`]??original.bestFor};return <div className="tuningRow" key={slider.kind} onMouseEnter={()=>setActiveTip(slider.kind)} onMouseLeave={()=>setActiveTip(null)}><div className="tuningHead"><label htmlFor={slider.kind}>{slider.label}</label><b>{level.label}</b></div><div className="sliderEnds"><span>{slider.ends[0]}</span><span>{slider.ends[1]}</span></div><input id={slider.kind} type="range" min="0" max={slider.levels.length-1} step="1" value={slider.index} aria-valuetext={level.label+': '+level.tagline} onFocus={()=>setActiveTip(slider.kind)} onBlur={()=>setActiveTip(null)} onChange={e=>{touched.current=true;slider.set(Number(e.target.value));setActiveTip(slider.kind);}}/>{activeTip===slider.kind&&<div className="tuningTooltip" role="tooltip"><div><strong>{level.label}</strong><span>{level.latency}</span></div><p>{level.tagline}</p><b>{t('home.whatHappens')}</b><ul>{level.runs.map(line=><li key={line}>{line}</li>)}</ul>{level.skips&&<><b>{t('home.notIncluded')}</b><ul>{level.skips.map(line=><li key={line}>{line}</li>)}</ul></>}<p><strong>{t('home.bestFor')}:</strong> {level.bestFor}</p></div>}</div>})}</div>
  </section>}
 </PageShell>;
}
