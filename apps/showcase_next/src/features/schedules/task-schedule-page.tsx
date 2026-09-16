'use client';
import { Pause, Play, History, Trash2, CirclePlay } from 'lucide-react';
import { Button } from '@/components/ui/button';
import Link from 'next/link';
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react';
import { PageShell } from '@/components/page-shell';
import { useAppPreferences } from '@/app/providers';
import { ApiError } from '@/lib/api/client';
import { settingsApi,type EmailSettings } from '@/features/settings/api';
import { schedulesApi } from './api';
import type { ScheduleDevice, ScheduleDraft, ScheduleRun, ScheduleStatus, ScheduleType, TaskSchedule } from './types';
import s from './schedule.module.css';

const labelKeys = { new:'schedule.new', active:'schedule.active', paused:'schedule.paused', loading:'schedule.loading', empty:'schedule.empty', create:'schedule.create', name:'schedule.name', device:'schedule.device', goal:'schedule.goal', profile:'schedule.profile', type:'schedule.type', interval:'schedule.interval', daily:'schedule.daily', weekly:'schedule.weekly', minutes:'schedule.minutes', time:'schedule.time', days:'schedule.days', timezone:'schedule.timezone', enabled:'schedule.enabled', email:'schedule.email', recipient:'schedule.recipient', subject:'schedule.subject', preview:'schedule.previewNext', previewHelp:'schedule.previewHelp', save:'schedule.save', cancel:'schedule.cancel', pause:'schedule.pause', resume:'schedule.resume', run:'schedule.run', history:'schedule.history', delete:'schedule.delete', healthy:'schedule.healthy', unavailable:'schedule.unavailable', required:'schedule.required', weekday:'schedule.weekday', previewRequired:'schedule.previewRequired', previewCount:'schedule.previewCount', conflict:'schedule.conflict', prepareRetry:'schedule.prepareRetry', retryReady:'schedule.retryReady', invalidEmail:'schedule.invalidEmail', invalidInterval:'schedule.invalidInterval', noHistory:'schedule.noHistory', retryEmail:'schedule.retryEmail', report:'schedule.report', close:'schedule.close', retry:'schedule.retry', smtpReady:'schedule.smtpReady', smtpNotConfigured:'schedule.smtpNotConfigured', smtpError:'schedule.smtpError', smtpLoading:'schedule.smtpLoading' } as const;
const days = [1,2,3,4,5,6,7] as const;
const dayNames = ['','Mon','Tue','Wed','Thu','Fri','Sat','Sun'];
function time(value?: string|null): NonNullable<ScheduleDraft['time_of_day']> { const p=(value||'00:00:00').split(':'); return [p[0]||'00',p[1]||'00',p[2]||'00'].map(x=>x.padStart(2,'0')).join(':') as NonNullable<ScheduleDraft['time_of_day']>; }
function fresh(): ScheduleDraft { let timezone='UTC'; try { timezone=Intl.DateTimeFormat().resolvedOptions().timeZone||'UTC'; } catch {} return { name:'',goal:'',profile:'flash',device_serial:'',enabled:true,schedule_type:'interval',interval_minutes:15,time_of_day:null,weekdays:[],timezone,email_enabled:false,recipient_name:null,recipient_email:null,email_subject:null }; }
function displayDate(value?: string|null){ if(!value)return '—'; try{return new Intl.DateTimeFormat(undefined,{dateStyle:'medium',timeStyle:'medium'}).format(new Date(value));}catch{return value;} }
function errorText(error:unknown,fallback:string){ if(error instanceof ApiError){ const p=error.payload as {detail?:unknown;message?:unknown}|undefined; const d=p?.detail??p?.message; if(typeof d==='string')return d; if(Array.isArray(d)){const x=d.map(v=>typeof v==='string'?v:(v as {msg?:string}).msg).filter(Boolean).join('; ');if(x)return x;} return error.message;} return fallback; }
function idempotencyKey(){ return typeof crypto!=='undefined'&&'randomUUID'in crypto?crypto.randomUUID():`manual-${Date.now()}-${Math.random()}`; }
type SmtpReadiness='loading'|'ready'|'not-configured'|'error';
function smtpConfigured(settings:EmailSettings){return Boolean(settings.enabled&&settings.smtp_host&&settings.sender_email&&settings.smtp_username&&settings.password_configured);}

export function TaskSchedulePage(){
  const {t}=useAppPreferences(); const c=Object.fromEntries(Object.entries(labelKeys).map(([name,key])=>[name,t(key)])) as {[K in keyof typeof labelKeys]:string};
  const [items,setItems]=useState<TaskSchedule[]>([]); const [devices,setDevices]=useState<ScheduleDevice[]>([]); const [health,setHealth]=useState<ScheduleStatus|null>(null); const [smtpReadiness,setSmtpReadiness]=useState<SmtpReadiness>('loading');
  const [loading,setLoading]=useState(true); const [error,setError]=useState(''); const [message,setMessage]=useState(''); const [action,setAction]=useState('');
  const [open,setOpen]=useState(false); const [editing,setEditing]=useState<TaskSchedule|null>(null); const [draft,setDraft]=useState<ScheduleDraft>(fresh());
  const [preview,setPreview]=useState<string[]>([]); const [previewFingerprint,setPreviewFingerprint]=useState(''); const [previewError,setPreviewError]=useState(''); const [formError,setFormError]=useState(''); const [conflict,setConflict]=useState(''); const [previewBusy,setPreviewBusy]=useState(false); const [saveBusy,setSaveBusy]=useState(false);
  const previewGeneration=useRef(0); const modalOpener=useRef<HTMLElement|null>(null); const busy=previewBusy||saveBusy;
  const [historyFor,setHistoryFor]=useState<TaskSchedule|null>(null); const [history,setHistory]=useState<ScheduleRun[]>([]); const [historyBusy,setHistoryBusy]=useState(false); const [emailBusy,setEmailBusy]=useState('');
  const load=useCallback(async()=>{setLoading(true);setError('');try{const [a,b,h]=await Promise.all([schedulesApi.list(),schedulesApi.devices(),schedulesApi.status()]);setItems(a);setDevices(b);setHealth(h);}catch(e){setError(errorText(e,t('schedule.unavailable')));}finally{setLoading(false);}},[t]);
  useEffect(()=>{void load();},[load]);
  useEffect(()=>{const controller=new AbortController();settingsApi.email(controller.signal).then(value=>setSmtpReadiness(smtpConfigured(value)?'ready':'not-configured')).catch(()=>{if(!controller.signal.aborted)setSmtpReadiness('error')});return()=>controller.abort();},[]);
  const active=useMemo(()=>items.filter(x=>x.enabled),[items]); const paused=useMemo(()=>items.filter(x=>!x.enabled),[items]);
  const invalidatePreview=()=>{previewGeneration.current+=1;setPreviewBusy(false);setPreview([]);setPreviewFingerprint('');setPreviewError('');};
  const change=<K extends keyof ScheduleDraft>(key:K,value:ScheduleDraft[K])=>{setDraft(d=>({...d,[key]:value}) as ScheduleDraft);invalidatePreview();setFormError('');setConflict('');};
  const create=(opener?:HTMLElement)=>{modalOpener.current=opener??(document.activeElement instanceof HTMLElement?document.activeElement:null);previewGeneration.current+=1;setEditing(null);setDraft(fresh());setPreview([]);setPreviewFingerprint('');setFormError('');setPreviewError('');setConflict('');setOpen(true);};
  const edit=(x:TaskSchedule,opener?:HTMLElement)=>{modalOpener.current=opener??(document.activeElement instanceof HTMLElement?document.activeElement:null);previewGeneration.current+=1;setEditing(x);setDraft({...x,time_of_day:x.schedule_type==='interval'?null:time(x.time_of_day),weekdays:[...(x.weekdays??[])]} as ScheduleDraft);setPreview([]);setPreviewFingerprint('');setFormError('');setPreviewError('');setConflict('');setOpen(true);};
  const payload=():ScheduleDraft=>({...draft,name:draft.name.trim(),goal:draft.goal.trim(),interval_minutes:draft.schedule_type==='interval'?Number(draft.interval_minutes):null,time_of_day:draft.schedule_type==='interval'?null:time(draft.time_of_day),weekdays:draft.schedule_type==='weekly'?draft.weekdays:[],recipient_name:draft.email_enabled?draft.recipient_name?.trim()||null:null,recipient_email:draft.email_enabled?draft.recipient_email?.trim()||null:null,email_subject:draft.email_enabled?draft.email_subject?.trim()||null:null} as ScheduleDraft);
  const validate=()=>{if(!draft.name.trim()||!draft.goal.trim()||!draft.device_serial||!draft.timezone.trim()||(draft.schedule_type!=='interval'&&!draft.time_of_day))return c.required;if(draft.schedule_type==='interval'&&(Number(draft.interval_minutes)<1||Number(draft.interval_minutes)>10080))return c.invalidInterval;if(draft.schedule_type==='weekly'&&!draft.weekdays.length)return c.weekday;if(draft.email_enabled&&!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(draft.recipient_email||''))return c.invalidEmail;return '';};
  const fingerprint=(value:ScheduleDraft)=>JSON.stringify(value);
  const doPreview=async()=>{const invalid=validate();setPreviewError(invalid);setFormError('');setConflict('');if(invalid)return;const request={...payload(),count:5};const requestFingerprint=fingerprint(payload());const generation=++previewGeneration.current;setPreviewBusy(true);try{const result=await schedulesApi.preview(request);if(generation!==previewGeneration.current)return;if(result.length!==5){setPreview([]);setPreviewFingerprint('');setPreviewError(c.previewCount);return;}setPreview(result);setPreviewFingerprint(requestFingerprint);}catch(e){if(generation!==previewGeneration.current)return;setPreview([]);setPreviewFingerprint('');setPreviewError(errorText(e,t('schedule.previewRequired')));}finally{if(generation===previewGeneration.current)setPreviewBusy(false);}};
  const save=async(event:FormEvent)=>{event.preventDefault();const invalid=validate();setFormError(invalid);setConflict('');if(invalid)return;const nextPayload=payload();if(draft.email_enabled&&smtpReadiness!=='ready'){setFormError(smtpReadiness==='error'?c.smtpError:smtpReadiness==='loading'?c.smtpLoading:c.smtpNotConfigured);return;}if(preview.length!==5||previewFingerprint!==fingerprint(nextPayload)){setFormError(c.previewRequired);return;}setSaveBusy(true);try{const saved=editing?await schedulesApi.update(editing,nextPayload):await schedulesApi.create(nextPayload);setItems(xs=>xs.some(x=>x.id===saved.id)?xs.map(x=>x.id===saved.id?saved:x):[saved,...xs]);setOpen(false);setMessage(t(editing?'schedule.updated':'schedule.saved'));}catch(e){if(e instanceof ApiError&&e.status===409){setConflict(c.conflict);setFormError('');}else setFormError(errorText(e,'Could not save schedule.'));}finally{setSaveBusy(false);}};
  const prepareConflictRetry=async()=>{if(!editing||saveBusy)return;setSaveBusy(true);try{const latest=await schedulesApi.get(editing.id);setEditing(latest);setItems(xs=>xs.map(x=>x.id===latest.id?latest:x));setConflict(c.retryReady);}catch(e){setConflict(errorText(e,t('schedule.conflict')));}finally{setSaveBusy(false);}};
  const closeEditor=()=>{if(busy)return;previewGeneration.current+=1;setOpen(false);};
  const runAction=async(x:TaskSchedule,kind:'toggle'|'run'|'delete')=>{if(kind==='delete'&&!window.confirm(t('schedule.deleteConfirm')))return;setAction(x.id);setError('');try{if(kind==='toggle'){const saved=x.enabled?await schedulesApi.pause(x):await schedulesApi.resume(x);setItems(xs=>xs.map(i=>i.id===x.id?saved:i));}else if(kind==='run'){await schedulesApi.runNow(x.id,idempotencyKey());setMessage(t('schedule.manualQueued'));await showHistory(x);}else{await schedulesApi.delete(x);setItems(xs=>xs.filter(i=>i.id!==x.id));}}catch(e){setError(errorText(e,'Schedule action failed.'));}finally{setAction('');}};
  const showHistory=async(x:TaskSchedule,opener?:HTMLElement)=>{modalOpener.current=opener??(document.activeElement instanceof HTMLElement?document.activeElement:null);setHistoryFor(x);setHistory([]);setHistoryBusy(true);try{setHistory((await schedulesApi.runs(x.id,{limit:25})).runs);}catch(e){setError(errorText(e,'Could not load history.'));}finally{setHistoryBusy(false);}};
  const notification=(run:ScheduleRun)=>run.email_notification??run.notification??(run.email_status?{status:run.email_status}:null);
  const retryEmail=async(run:ScheduleRun)=>{if(!historyFor||emailBusy)return;const n=notification(run);if(n?.status==='delivery_unknown'&&!window.confirm(t('schedule.deliveryConfirm')))return;setEmailBusy(run.id);try{const result=await schedulesApi.retryEmail(historyFor.id,run.id);setHistory(xs=>xs.map(x=>x.id===run.id?{...x,email_notification:{...(notification(x)??{}),status:result.status,can_retry:false}}:x));}catch(e){setError(errorText(e,'Could not retry email.'));}finally{setEmailBusy('');}};
  const rule=(x:TaskSchedule)=>x.schedule_type==='interval'?t('schedule.everyMinutes',{count:x.interval_minutes}):x.schedule_type==='daily'?t('schedule.dailyAt',{time:time(x.time_of_day)}):t('schedule.weeklyAt',{days:x.weekdays.map(d=>dayNames[d]).join(', '),time:time(x.time_of_day)});
  const card=(x:TaskSchedule)=>
<article className={s.scheduleCard} data-enabled={x.enabled} key={x.id}>
<div className={s.cardHead}>
<div>
<span className={s.status}>{x.enabled?c.active:c.paused}</span>
<h3>{x.name}</h3>
</div>
<Button variant="outline" className={s.button} onClick={event=>edit(x,event.currentTarget)}>✎</Button>
</div>
<p className={s.goal} tabIndex={0} role="region" aria-label={`${c.goal}: ${x.name}`}>{x.goal}</p>
<dl className={s.facts}>
<div>
<dt>{t('schedule.fact')}</dt>
<dd>{rule(x)}</dd>
</div>
<div>
<dt>{c.timezone}</dt>
<dd>{x.timezone}</dd>
</div>
<div>
<dt>{c.device}</dt>
<dd>{devices.find(d=>d.serial===x.device_serial)?.name||x.device_serial}</dd>
</div>
<div>
<dt>{t('schedule.nextRun')}</dt>
<dd>{displayDate(x.next_run_at)}</dd>
</div>
<div>
<dt>{c.email}</dt>
<dd>{x.email_enabled?(x.recipient_email||t('schedule.on')):t('schedule.off')}</dd>
</div>
</dl>
<div className={s.actions}>
<Button variant="outline" className={s.iconAction} title={x.enabled?c.pause:c.resume} aria-label={x.enabled?c.pause:c.resume} disabled={action===x.id} onClick={()=>void runAction(x,'toggle')}>{x.enabled?<Pause size={16} aria-hidden/>:<Play size={16} aria-hidden/>}</Button>
<Button variant="outline" className={s.iconAction} title={c.run} aria-label={c.run} disabled={action===x.id} onClick={()=>void runAction(x,'run')}><CirclePlay size={16} aria-hidden/></Button>
<Button variant="outline" className={s.iconAction} data-focus-key={`history-${x.id}`} title={c.history} aria-label={c.history} onClick={event=>void showHistory(x,event.currentTarget)}><History size={16} aria-hidden/></Button>
<Button variant="outline" className={`${s.iconAction} ${s.danger}`} title={c.delete} aria-label={c.delete} disabled={action===x.id} onClick={()=>void runAction(x,'delete')}><Trash2 size={16} aria-hidden/></Button>
</div>
</article>;
  return <PageShell eyebrow="schedule.eyebrow" title="schedule.title" body="schedule.body">
<div className={s.toolbar}>
<Button variant="outline" className={s.primary} onClick={event=>create(event.currentTarget)}>＋ {c.new}</Button>
</div>
<section className={s.health} data-healthy={health?.healthy??false}>
<strong>{health?.healthy?c.healthy:c.unavailable}</strong>
<small>{displayDate(health?.last_heartbeat)}</small>
<p>{t('schedule.backendRequired')}</p>
</section>{error&&<div className={`${s.notice} ${s.error}`} role="alert">{error} <Button variant="outline" onClick={()=>void load()}>{c.retry}</Button>
</div>}{message&&<div className={`${s.notice} ${s.success}`} role="status">{message}</div>}{loading?<div className={s.loading}>{c.loading}</div>:items.length===0?<section className={`card ${s.empty}`}>
<h2>{c.empty}</h2>
<Button variant="outline" className={s.primary} onClick={event=>create(event.currentTarget)}>{c.new}</Button>
</section>:<>
<ScheduleGroup title={c.active} items={active} render={card}/>
<ScheduleGroup title={c.paused} items={paused} render={card}/>
</>}
  {open&&<Modal testId="schedule-backdrop" close={closeEditor} opener={modalOpener.current}>
<header className={s.modalHeader}>
<h2>{editing?.name||c.create}</h2>
<Button variant="outline" className={s.close} aria-label={c.close} onClick={closeEditor}>×</Button>
</header>
<form className={s.form} noValidate onSubmit={save}>
<div className={s.formGrid}>
<Field label={c.name}>
<input name="name" value={draft.name} onChange={e=>change('name',e.target.value)}/>
</Field>
<Field label={c.device}>
<select name="device" value={draft.device_serial} onChange={e=>change('device_serial',e.target.value)}>
<option value="">{t('schedule.select')}</option>{devices.map(d=>
<option key={d.serial} value={d.serial}>{d.name||d.model||d.serial}</option>)}</select>
</Field>
</div>
<Field label={c.goal}>
<textarea name="goal" rows={4} value={draft.goal} onChange={e=>change('goal',e.target.value)}/>
</Field>
<fieldset className={s.fieldset}>
<legend>{c.profile}</legend>
<div className={s.segments}>{(['flash','pro'] as const).map(p=>
<label key={p}>
<input type="radio" checked={draft.profile===p} onChange={()=>change('profile',p)}/>{p}</label>)}</div>
</fieldset>
<fieldset className={s.fieldset}>
<legend>{c.type}</legend>
<div className={s.segments}>{(['interval','daily','weekly'] as ScheduleType[]).map(t=>
<label key={t}>
<input type="radio" checked={draft.schedule_type===t} onChange={()=>change('schedule_type',t)}/>{c[t]}</label>)}</div>
</fieldset>{draft.schedule_type==='interval'?<Field label={c.minutes}>
<input name="interval" type="number" min={1} max={10080} value={draft.interval_minutes??''} onChange={e=>change('interval_minutes',Number(e.target.value))}/>
</Field>:<Field label={c.time}>
<input name="time" type="time" step={1} value={time(draft.time_of_day)} onChange={e=>change('time_of_day',time(e.target.value))}/>
</Field>}{draft.schedule_type==='weekly'&&(
  <fieldset className={s.fieldset}>
    <legend>{c.days}</legend>
    <div className={s.weekdays}>
      {days.map(d=><label key={d}><input type="checkbox" checked={draft.weekdays.includes(d)} onChange={e=>change('weekdays',e.target.checked?[...draft.weekdays,d].sort() as typeof draft.weekdays:draft.weekdays.filter(x=>x!==d))}/>{dayNames[d]}</label>)}
    </div>
  </fieldset>
)}
<div className={s.formGrid}>
  <Field label={c.timezone}><input name="timezone" value={draft.timezone} onChange={e=>change('timezone',e.target.value)}/></Field>
  <label className={s.checkbox}><input type="checkbox" checked={draft.enabled} onChange={e=>change('enabled',e.target.checked)}/>{c.enabled}</label>
</div>
<section className={s.email}>
  <label className={s.emailToggle}><strong>{c.email}</strong><input name="email_enabled" type="checkbox" checked={draft.email_enabled??false} onChange={e=>change('email_enabled',e.target.checked)}/></label>
  {draft.email_enabled&&<><p className={smtpReadiness==='ready'?s.smtpReady:s.warning} role="status">{smtpReadiness==='ready'?c.smtpReady:smtpReadiness==='error'?c.smtpError:smtpReadiness==='loading'?c.smtpLoading:c.smtpNotConfigured} {smtpReadiness!=='ready'&&<Link href="/settings/?tab=email">{t('settings.title')} → {t('settings.email')}</Link>}</p><Field label={c.recipient}><input name="recipient_email" type="email" value={draft.recipient_email??''} onChange={e=>change('recipient_email',e.target.value)}/></Field><Field label={c.subject}><input name="email_subject" value={draft.email_subject??''} onChange={e=>change('email_subject',e.target.value)}/></Field></>}
</section>
<section className={s.preview}>
  <div className={s.previewHead}><div><strong>{c.preview}</strong><p>{c.previewHelp}</p></div><Button variant="outline" type="button" className={s.button} disabled={busy} onClick={()=>void doPreview()}>{c.preview}</Button></div>
  {previewError&&<div className={s.error} role="alert">{previewError}</div>}
  {preview.length>0&&<ol>{preview.map((x,i)=><li key={x+i}>{displayDate(x)}</li>)}</ol>}
</section>
{conflict&&<div className={`${s.notice} ${s.error}`} role="alert">{conflict} {editing&&<Button variant="outline" type="button" className={s.button} disabled={busy} onClick={()=>void prepareConflictRetry()}>{c.prepareRetry}</Button>}</div>}
{formError&&<div className={`${s.notice} ${s.error}`} role="alert">{formError}</div>}
<footer className={s.footer}><Button variant="outline" type="button" className={s.button} onClick={closeEditor}>{c.cancel}</Button><Button variant="outline" className={s.primary} disabled={busy}>{c.save}</Button></footer>
</form></Modal>}
{historyFor&&<Modal testId="history-backdrop" close={()=>setHistoryFor(null)} opener={modalOpener.current}>
<header className={s.modalHeader}><h2>{c.history}: {historyFor.name}</h2><Button variant="outline" className={s.close} aria-label={c.close} onClick={()=>setHistoryFor(null)}>×</Button></header>
<div className={s.history}>{historyBusy?<p>{c.loading}</p>:history.length===0?<p>{c.noHistory}</p>:history.map(run=><RunRow key={run.id} run={run} schedule={historyFor} busy={emailBusy===run.id} retry={()=>void retryEmail(run)} labels={{...c,openSession:t('schedule.openSession'),emailStatus:t('schedule.emailStatus')}}/>)}</div>
</Modal>}
</PageShell>;
}
const focusableSelector='a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])';
function Modal({testId,close,opener,children}:{testId:string;close():void;opener:HTMLElement|null;children:React.ReactNode}){
  const dialogRef=useRef<HTMLElement>(null);
  const closeRef=useRef(close);
  closeRef.current=close;
  useEffect(()=>{
    const restoreFocus=()=>{
      if(opener?.isConnected){opener.focus();return;}
      const focusKey=opener?.dataset.focusKey;
      const replacement=Array.from(document.querySelectorAll<HTMLElement>('button')).find(element=>focusKey?element.dataset.focusKey===focusKey:element.textContent===opener?.textContent&&element.className===opener?.className&&element.getAttribute('aria-label')===opener?.getAttribute('aria-label'));
      replacement?.focus();
    };
    const dialog=dialogRef.current;
    if(!dialog)return;
    const focusables=()=>Array.from(dialog.querySelectorAll<HTMLElement>(focusableSelector)).filter(element=>!element.hasAttribute('disabled')&&element.getAttribute('aria-hidden')!=='true');
    (focusables()[0]??dialog).focus();
    const onKeyDown=(event:KeyboardEvent)=>{
      if(event.key==='Escape'){event.preventDefault();closeRef.current();setTimeout(restoreFocus,0);return;}
      if(event.key!=='Tab')return;
      const enabled=focusables();
      if(enabled.length===0){event.preventDefault();dialog.focus();return;}
      const first=enabled[0]!; const last=enabled[enabled.length-1]!; const active=document.activeElement;
      if(event.shiftKey&&(active===first||!dialog.contains(active))){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&(active===last||!dialog.contains(active))){event.preventDefault();first.focus();}
    };
    document.addEventListener('keydown',onKeyDown);
    return()=>{document.removeEventListener('keydown',onKeyDown);setTimeout(restoreFocus,0);};
  },[opener]);
  return <div className={s.backdrop} data-testid={testId} onClick={event=>{if(event.target===event.currentTarget)close();}}>
    <section ref={dialogRef} className={s.modal} role="dialog" aria-modal="true" tabIndex={-1}>{children}</section>
  </div>;
}
function Field({label,children}:{label:string;children:React.ReactNode}){return <label className={s.field}>{label}{children}</label>;}
function ScheduleGroup({title,items,render}:{title:string;items:TaskSchedule[];render(x:TaskSchedule):React.ReactNode}){return <section className={s.section}>
<h2 className={s.sectionTitle}>{title} <span>{items.length}</span>
</h2>
<div className={s.grid}>{items.map(render)}</div>
</section>;}
type RunLabels={report:string;retryEmail:string;openSession:string;emailStatus:string};
function RunRow({run,schedule,busy,retry,labels}:{run:ScheduleRun;schedule:TaskSchedule;busy:boolean;retry():void;labels:RunLabels}){const n=run.email_notification??run.notification??(run.email_status?{status:run.email_status}:null);const canRetry=Boolean(n?.can_retry||['failed','delivery_unknown','report_incomplete','attachment_too_large'].includes(n?.status||''));const canReport=Boolean(n?.report_available||n?.status==='accepted_by_smtp');return <article className={s.run}>
<div className={s.runMeta}>
<strong>{run.status.replaceAll('_',' ')}</strong>
<span>{displayDate(run.due_at)}</span>
<small>{run.trigger}</small>
</div>
<div className={s.runActions}>{run.session_id&&<Link href={`/workspace/?session=${encodeURIComponent(run.session_id)}`}>{labels.openSession}</Link>}{n&&<span className={s.badge}>{labels.emailStatus.replace('{{status}}',n.status.replaceAll('_',' '))}</span>}{n?.safe_error_message&&<small className={s.emailError}>{n.safe_error_message}</small>}<div>{canReport&&<a href={schedulesApi.emailReportUrl(schedule.id,run.id)} target="_blank" rel="noopener noreferrer">{labels.report}</a>} {canRetry&&<Button variant="outline" className={s.button} disabled={busy} onClick={retry}>{labels.retryEmail}</Button>}</div>
</div>
</article>;}
