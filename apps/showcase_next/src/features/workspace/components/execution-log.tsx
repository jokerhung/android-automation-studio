'use client';
import { ChevronDown, Circle, MousePointer2, Terminal, Clock, AppWindow, CheckCircle2 } from 'lucide-react';
import { useAppPreferences } from '@/app/providers';
import type { SessionStep } from '../types';
import './execution-log.css';

type Data = Record<string, unknown>;
function parsed(value: unknown): unknown {
  if (typeof value !== 'string' || !/^[\[{]/.test(value.trim())) return value;
  try { return JSON.parse(value); } catch { return value; }
}
function object(value: unknown): Data {
  const v = parsed(value);
  return v && typeof v === 'object' && !Array.isArray(v) ? v as Data : {};
}
function words(value: unknown): string {
  return typeof value === 'string' ? value : typeof value === 'number' ? String(value) : '';
}
function readable(value: unknown): string {
  const v = parsed(value);
  if (Array.isArray(v)) return v.map(readable).filter(Boolean).join(' → ');
  if (v && typeof v === 'object') return Object.entries(v).filter(([key])=>!/password|secret|token|api_key/i.test(key)).map(([key,val])=>`${key.replaceAll('_',' ')}: ${readable(val)}`).filter(line=>!line.endsWith(': ')).join(' · ');
  return typeof v === 'boolean' ? (v ? '✓' : '—') : words(v);
}
const titles: Record<string, [string,string]> = {
  tap:['Tapping Element','Chạm phần tử'], click:['Tapping Element','Chạm phần tử'],
  click_sequence:['Tap Sequence','Chuỗi thao tác chạm'], swipe:['Swiping','Vuốt màn hình'], scroll:['Scrolling','Cuộn màn hình'],
  input_text:['Entering Text','Nhập văn bản'], input:['Entering Text','Nhập văn bản'], focus_and_input_text:['Entering Text','Nhập văn bản'],
  wait:['Waiting for Delay','Chờ'], wait_for_delay:['Waiting for Delay','Chờ'],
  launch_app:['Launching Application','Mở ứng dụng'], open_app:['Launching Application','Mở ứng dụng'],
  press_key:['Pressing Key','Nhấn phím'], press_back:['Going Back','Quay lại'], press_home:['Opening Home','Về màn hình chính'],
  long_press:['Long Press','Nhấn giữ'], drag:['Dragging','Kéo'],
  report_task_status:['Task Result','Kết quả tác vụ'], report_status:['Task Result','Kết quả tác vụ'],
  run_adb_command:['ADB Command','Lệnh ADB'], execute_command:['Running Command','Chạy lệnh'],
};
function normalizedAction(value: unknown) {
  const source=object(value), payload=object(source.payload);
  const nested=parsed(object(payload.args).action ?? payload.action);
  const inner=object(Array.isArray(nested)?nested[0]:nested);
  const action={...source,...inner};
  const args={...object(action.args ?? payload.args ?? action.arguments)};
  const name=words(action.action ?? action.name ?? source.tool_name ?? value).replace(/^(_)?(self\.)?exec_/,'');
  const coordinates=action.coordinates ?? args.coordinates ?? args.normalized_coordinates;
  delete args.normalized_coordinates;
  if(coordinates!==undefined&&coordinates!==null)args.coordinates=coordinates;
  return {action,args,name};
}
function canonical(value: unknown): string {
  if(Array.isArray(value))return '['+value.map(canonical).join(',')+']';
  if(value&&typeof value==='object')return '{'+Object.entries(value).sort(([a],[b])=>a.localeCompare(b)).map(([key,val])=>JSON.stringify(key)+':'+canonical(val)).join(',')+'}';
  return JSON.stringify(value)??'';
}
/** Match across the two representations only, once per primary action.
 * Repeated actions within either list are real executions and stay visible. */
function actionCards(primary: unknown[], tools: unknown[]) {
  const cards=primary.map(value=>normalizedAction(value));
  const matched=new Set<number>();
  const extra: unknown[]=[];
  for(const tool of tools){
    const candidate=normalizedAction(tool);
    const index=cards.findIndex((card,i)=>{
      if(matched.has(i)||!card.name||card.name!==candidate.name)return false;
      const leftId=words(card.action.trace_id),rightId=words(candidate.action.trace_id);
      if(leftId&&rightId)return leftId===rightId;
      const shared=Object.keys(card.args).filter(key=>key in candidate.args);
      return shared.length>0&&shared.every(key=>canonical(card.args[key])===canonical(candidate.args[key]))
        && Object.keys({...card.args,...candidate.args}).every(key=>key==='coordinates'||(key in card.args&&key in candidate.args));
    });
    if(index<0){extra.push(tool);continue;}
    matched.add(index);
    const card=cards[index]!;
    const args={...candidate.args,...card.args};
    cards[index]={...card,args,action:{...candidate.action,...card.action,args,coordinates:args.coordinates}};
  }
  return [...cards.map(card=>({...card.action,action:card.name,args:card.args})),...extra];
}
function actionView(value: unknown, vi: boolean) {
  const {action,args,name}=normalizedAction(value);
  const operation=words(args.action);
  const title=name==='manage_app' ? (operation==='launch'?(vi?'Mở ứng dụng':'Launching Application'):operation==='kill'?(vi?'Đóng ứng dụng':'Closing Application'):(vi?'Quản lý ứng dụng':'Managing Application')) : titles[name]?.[vi?1:0] ?? (name.replaceAll('_',' ') || (vi?'Thao tác':'Action'));
  const coordinates=action.coordinates ?? args.coordinates;
  const rows: [string,unknown][] = [
    [vi?'Mục tiêu':'Target',args.target ?? args.app_name ?? args.package_name ?? action.target ?? args.element_description],
    [vi?'Tọa độ':'Coordinates',coordinates],
    [vi?'Thời lượng':'Duration',args.duration ?? args.duration_ms ?? args.delay ?? args.seconds ?? (args.time_in_ms!==undefined?`${args.time_in_ms}ms`:undefined)],
    [vi?'Văn bản':'Text',args.text], [vi?'Hướng':'Direction',args.direction],
    [vi?'Phím':'Key',args.key ?? args.keycode], [vi?'Lệnh':'Command',args.command],
    [vi?'Trạng thái':'Status',args.status],
  ];
  return {title,name,rows:rows.filter(([,val])=>val!==null&&val!==undefined&&val!=='')};
}

function ActionCard({value,vi,target}:{value:unknown;vi:boolean;target?:string}) {
  const {title,name,rows}=actionView(value,vi);
  if(target&&!rows.some(([label])=>label==='Target'||label==='Mục tiêu'))rows.unshift([vi?'Mục tiêu':'Target',target]);
  const Icon=/wait/.test(name)?Clock:/app/.test(name)?AppWindow:/command|adb/.test(name)?Terminal:/report/.test(name)?CheckCircle2:MousePointer2;
  return <details className="execution-action" open>
    <summary><Icon size={15} aria-hidden/><span>{title}</span><ChevronDown size={14} className="execution-chevron" aria-hidden/></summary>
    {rows.length>0&&<dl>{rows.map(([label,value])=><div key={label}><dt>{label}:</dt><dd>{/Coordinates|Tọa độ/.test(label)?<code className="execution-coordinates">{Array.isArray(value)?`[${value.map(readable).join(', ')}]`:readable(value)}</code>:readable(value)}</dd></div>)}</dl>}
  </details>;
}

export function ExecutionLog({steps}:{steps:readonly SessionStep[]}) {
  const {preferences,t}=useAppPreferences(); const vi=preferences.language==='vi';
  if(!steps.length)return <div className="execution-empty">{t('workspace.noSteps')}</div>;
  return <section className="execution-log" aria-label={t('workspace.logs')}>
    {steps.map((step,index)=>{
      const actions=parsed(step.action_taken ?? step.action);
      const list=Array.isArray(actions)?actions:actions?[actions]:[];
      const result=object(step.last_execution_result);
      const activity=words(step.operator_raw_thinking ?? step.operator_native_thinking ?? step.thinking);
      const summary=words(step.summary ?? step.message ?? result.summary ?? result.message);
      const error=words(step.error ?? result.error ?? result.failure_reason);
      const duration=typeof step.duration==='number'?step.duration:null;
      const tokens=step.total_tokens ?? object(step.token_usage).total_tokens;
      const tools=Array.isArray(step.generic_tools)?step.generic_tools:[];
      return <article className="execution-step" key={step.step_id??step.id??`step-${step.step_number??index}`}>
        <div className="execution-meta"><span>{duration!==null?`${vi?'Hoạt động trong':'Worked for'} ${Math.round(duration)}s`:`${vi?'Bước':'Step'} ${step.step_number??index+1}`}</span>{typeof tokens==='number'&&<span> · {new Intl.NumberFormat(vi?'vi':'en',{notation:'compact',maximumFractionDigits:1}).format(tokens)} tokens</span>}</div>
        {actionCards(list,tools).map((action,i)=><ActionCard key={i} value={action} vi={vi} target={words(step.goal)}/>)}
        {activity&&<div className="execution-narrative"><h3><Circle size={8} fill="currentColor" aria-hidden/>{vi?'Hoạt động':'Activity'}</h3><p>{activity}</p></div>}
        {summary&&summary!==activity&&<div className="execution-narrative execution-result"><h3><CheckCircle2 size={13} aria-hidden/>{vi?'Kết quả':'Result'}</h3><p>{summary}</p></div>}
        {error&&<div role="alert" className="execution-error">{error}</div>}
        {!activity&&!summary&&!error&&!list.length&&!tools.length&&<p className="execution-pending">{words(step.goal) || (vi?'Đang chờ nội dung bước…':'Waiting for step details…')}</p>}
      </article>;
    })}
  </section>;
}
